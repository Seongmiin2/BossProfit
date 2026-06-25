"""Base Price Model 테스트 (항목 9).

성능 비교는 변동이 있으므로, 회귀가 깨지지 않을 견고한 성질만 단언한다:
- 분위수 단조성(lower<=median<=upper), 예측값 유한성
- feature 누수 차단(예측 시 origin 시점 정보만 사용)
- 앙상블 가중치가 validation에서 결정되고 합=1
- 전체가 rolling-origin 평가에 그대로 투입됨
"""
import numpy as np
import pandas as pd
from django.test import SimpleTestCase

from forecast.features import build_price_features, FEATURE_COLUMNS
from forecast.base_models import (
    SarimaxForecaster, LightGBMQuantileForecaster,
    EnsembleForecaster, compute_ensemble_weights,
)
from forecast.baselines import LastValueForecaster
from forecast.evaluation import rolling_origin_backtest


def _series(n=220, start="2025-06-01"):
    idx = pd.date_range(start, periods=n, freq="D")
    t = np.arange(n)
    vals = 100 + 0.1 * t + 6 * np.sin(2 * np.pi * t / 7) + 2 * np.sin(t * 1.1)
    return pd.Series(vals, index=idx, dtype="float64")


class FeatureTests(SimpleTestCase):
    def test_no_target_leak_in_features(self):
        s = _series(60)
        feats = build_price_features(s)
        # lag_1[t]는 price[t-1]과 같아야 한다(현재값 누수 없음)
        self.assertAlmostEqual(feats["lag_1"].iloc[10], s.iloc[9])
        # FEATURE_COLUMNS에 원본 price가 포함되지 않음
        self.assertNotIn("price", FEATURE_COLUMNS)

    def test_rolling_uses_past_only(self):
        s = _series(60)
        feats = build_price_features(s)
        # roll_mean_7[t]는 price[t-7..t-1] 평균(현재 제외)
        expected = s.iloc[3:10].mean()
        self.assertAlmostEqual(feats["roll_mean_7"].iloc[10], expected, places=6)


class SarimaxTests(SimpleTestCase):
    def test_fit_predict_and_interval_order(self):
        f = SarimaxForecaster(order=(1, 1, 0)).fit(_series(120))
        self.assertTrue(np.isfinite(f.predict(1)))
        q = f.predict_quantiles(7)
        self.assertLessEqual(q[0.1], q[0.5])
        self.assertLessEqual(q[0.5], q[0.9])


class LightGBMTests(SimpleTestCase):
    def test_quantiles_monotonic_and_finite(self):
        f = LightGBMQuantileForecaster(horizons=(1, 7), quantiles=(0.1, 0.5, 0.9)).fit(_series(220))
        for h in (1, 7):
            q = f.predict_quantiles(h)
            self.assertTrue(all(np.isfinite(list(q.values()))))
            self.assertLessEqual(q[0.1], q[0.5])
            self.assertLessEqual(q[0.5], q[0.9])

    def test_short_history_falls_back(self):
        f = LightGBMQuantileForecaster(horizons=(1,)).fit(_series(10))  # _MIN_ROWS 미만
        # 모델 학습 못 함 → last value 폴백
        self.assertAlmostEqual(f.predict(1), float(_series(10).iloc[-1]))

    def test_runs_in_rolling_origin(self):
        s = _series(120)
        preds = rolling_origin_backtest(
            s, {"lgbm": lambda: LightGBMQuantileForecaster(horizons=(1,))},
            horizons=[1], min_train=60, step=10,
        )
        self.assertGreater(len(preds), 0)
        self.assertTrue(np.isfinite(preds["y_pred"]).all())


class EnsembleTests(SimpleTestCase):
    def test_weights_from_validation_sum_to_one(self):
        s = _series(160)
        members = {
            "last_value": lambda: LastValueForecaster(),
            "lgbm": lambda: LightGBMQuantileForecaster(horizons=(1, 7)),
        }
        val_start = s.index[110].date()
        weights = compute_ensemble_weights(s, members, [1, 7], val_start=val_start, min_train=60)
        for h in (1, 7):
            self.assertIn(h, weights)
            self.assertAlmostEqual(sum(weights[h].values()), 1.0, places=6)

    def test_ensemble_predict_is_weighted_combo(self):
        s = _series(160)
        members = {"last_value": lambda: LastValueForecaster()}
        weights = {1: {"last_value": 1.0}}
        ens = EnsembleForecaster(members, weights).fit(s)
        # 단일 멤버 가중 1.0 → 멤버 예측과 동일
        self.assertAlmostEqual(ens.predict(1), float(s.iloc[-1]))
