"""Residual Correction Model 테스트 (항목 12).

불변식:
- 잔차 feature는 origin O에서 target_date<=O 인 잔차만 사용(누수 차단)
- 학습 가능한 편향(bias)이 있으면 보정이 stage2를 개선
- 순수 노이즈 잔차면 auto-disable (보정량 0)
- 최종 = exp(log(stage2)+resid_hat)
"""
from datetime import date, timedelta

import numpy as np
import pandas as pd
from django.test import SimpleTestCase

from forecast.residual_model import (
    build_residual_training_table, ResidualCorrector,
    evaluate_residual_correction, residual_diagnostics,
)


def _residual_df(residuals, preds, actuals, h=7, start="2026-01-01"):
    """origin_date/target_date를 h간격으로 구성한 잔차 DataFrame."""
    origins = pd.date_range(start, periods=len(residuals), freq="D")
    return pd.DataFrame({
        "origin_date": origins,
        "target_date": origins + pd.Timedelta(days=h),
        "prediction": preds,
        "actual": actuals,
        "residual": residuals,
    })


class FeatureLeakageTests(SimpleTestCase):
    def test_features_use_only_observed_residuals(self):
        # residual[i] 은 target = origin+7 에 관측. origin O의 r_lag1은 target<=O 중 최신.
        n = 40
        res = [0.01 * i for i in range(n)]  # 단조 증가 잔차 (식별 쉽게)
        df = _residual_df(res, preds=[10.0] * n, actuals=[10.0] * n, h=7)
        table = build_residual_training_table(df, min_history=3)
        # 임의 행 검증: r_lag1 은 target_date<=origin 인 잔차 중 최신값
        observed = pd.Series(df["residual"].values, index=df["target_date"])
        for _, row in table.iterrows():
            O = row["origin_date"]
            hist = observed[observed.index <= O]
            self.assertAlmostEqual(row["r_lag1"], hist.iloc[-1], places=9)
            # 라벨(y)의 target은 origin보다 미래
            self.assertGreater(row["target_date"], O)


class CorrectionImprovesOnBiasTests(SimpleTestCase):
    def test_constant_bias_is_corrected(self):
        # stage2가 일정하게 과소예측: actual = pred * exp(0.05), residual=+0.05 일정
        n = 80
        bias = 0.05
        preds = [10.0] * n
        actuals = [10.0 * np.exp(bias)] * n
        res = [bias] * n
        df = _residual_df(res, preds, actuals, h=7)
        test_start = df["target_date"].iloc[50].date()
        out = evaluate_residual_correction(df, test_start, min_history=5, min_train_rows=8)
        self.assertTrue(out["applied"])
        self.assertFalse(out["disabled"])
        # 보정 후 WAPE가 크게 감소(거의 0)
        self.assertLess(out["corrected_wape"], out["stage2_wape"])
        self.assertLess(out["corrected_wape"], 0.01)


class AutoDisableTests(SimpleTestCase):
    def test_pure_noise_disables_correction(self):
        rng = np.random.RandomState(0)
        n = 80
        res = rng.normal(0, 0.05, n)  # 평균0 노이즈 → 예측 불가
        preds = (10 + rng.normal(0, 0.1, n)).tolist()
        actuals = [p * np.exp(r) for p, r in zip(preds, res)]
        df = _residual_df(res.tolist(), preds, actuals, h=7)
        test_start = df["target_date"].iloc[50].date()
        # 출시 게이트 3% 적용 → 노이즈의 우연한 미세 개선은 비활성화돼야 함
        out = evaluate_residual_correction(df, test_start, min_improvement=0.03)
        self.assertTrue(out["applied"])
        # 개선 없으면 비활성화 → corrected_wape == stage2_wape
        self.assertTrue(out["disabled"])
        self.assertAlmostEqual(out["corrected_wape"], out["stage2_wape"], places=9)


class DiagnosticsTests(SimpleTestCase):
    def test_detects_bias_and_autocorr(self):
        # 양의 자기상관 잔차
        n = 60
        r = [0.0]
        for i in range(1, n):
            r.append(0.8 * r[-1] + 0.01)
        df = _residual_df(r, [10.0] * n, [10.0] * n)
        diag = residual_diagnostics(df)
        self.assertEqual(diag["n"], n)
        self.assertGreater(diag["acf_lag1"], 0.3)  # 자기상관 존재 → 보정 여지
