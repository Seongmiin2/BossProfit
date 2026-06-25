"""OOF 잔차 생성 테스트 (항목 11).

핵심 불변식:
- residual = log(actual) - log(pred), OOF 예측에서만 생성
- 각 OOF 예측은 origin_date 까지의 과거만으로 생성(미래 누수 없음)
- 멱등 저장
- load_residuals(as_of=...)는 이미 관측된(target_date<=as_of) 잔차만 반환
"""
from datetime import date

import numpy as np
import pandas as pd
from django.test import TestCase

from market.models import MarketItem
from forecast.baselines import LastValueForecaster
from forecast.models import OutOfFoldForecast, ResidualObservation
from forecast.residuals import (
    compute_oof_residuals, generate_oof_residuals, load_residuals,
)


def _series(values, start="2026-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype="float64")


class ComputeResidualTests(TestCase):
    def setUp(self):
        self.item = MarketItem.objects.create(code="ONION", name="양파", source_item_code="245")

    def test_residual_is_log_actual_minus_log_pred(self):
        # LastValue: pred(t->t+1) = price[t]. residual = log(price[t+1]) - log(price[t])
        s = _series([10, 11, 12, 13, 14, 15])
        df = compute_oof_residuals(
            s, lambda: LastValueForecaster(), horizons=[1], min_train=3,
            model_version="last_value",
        )
        # 첫 잔차: origin=index2(12), target=index3(13) → log(13)-log(12)
        row = df.sort_values("target_date").iloc[0]
        self.assertAlmostEqual(row["residual"], np.log(13) - np.log(12), places=9)

    def test_oof_uses_only_past_no_leak(self):
        # LastValue 예측은 origin 시점 값과 같아야 한다(미래 미사용)
        s = _series([5, 6, 7, 8, 9, 10, 11])
        df = compute_oof_residuals(
            s, lambda: LastValueForecaster(), horizons=[1], min_train=3,
            model_version="lv",
        ).sort_values("origin_date")
        for _, r in df.iterrows():
            origin_val = float(s.loc[pd.Timestamp(r["origin_date"])])
            self.assertAlmostEqual(r["y_pred"], origin_val, places=9)
            self.assertLess(pd.Timestamp(r["origin_date"]), pd.Timestamp(r["target_date"]))

    def test_nonpositive_excluded(self):
        s = _series([10, 0, 12, 13, 14])  # 0 포함
        df = compute_oof_residuals(
            s, lambda: LastValueForecaster(), horizons=[1], min_train=2,
            model_version="lv",
        )
        # y_true=0 또는 y_pred=0 인 행은 제외 → 모든 잔차 유한
        self.assertTrue(np.isfinite(df["residual"]).all())


class PersistResidualTests(TestCase):
    def setUp(self):
        self.item = MarketItem.objects.create(code="ONION", name="양파", source_item_code="245")
        self.s = _series(list(range(10, 40)))  # 30일 증가 시계열

    def test_persist_creates_oof_and_residual(self):
        df = generate_oof_residuals(
            self.item, self.s, lambda: LastValueForecaster(), horizons=[1, 7],
            min_train=10, model_version="lv", persist=True,
        )
        self.assertGreater(len(df), 0)
        self.assertEqual(OutOfFoldForecast.objects.count(), len(df))
        self.assertEqual(ResidualObservation.objects.count(), len(df))

    def test_idempotent_persist(self):
        for _ in range(2):
            generate_oof_residuals(
                self.item, self.s, lambda: LastValueForecaster(), horizons=[1],
                min_train=10, model_version="lv", persist=True,
            )
        # 재실행해도 중복 없음
        n = OutOfFoldForecast.objects.count()
        self.assertEqual(ResidualObservation.objects.count(), n)
        self.assertGreater(n, 0)

    def test_load_residuals_as_of_filters_future(self):
        generate_oof_residuals(
            self.item, self.s, lambda: LastValueForecaster(), horizons=[1],
            min_train=10, model_version="lv", persist=True,
        )
        cutoff = self.s.index[20].date()
        loaded = load_residuals(self.item, "lv", horizon=1, as_of=cutoff)
        # as_of 이후 target은 제외
        self.assertTrue((loaded["target_date"] <= cutoff).all())
        self.assertGreater(len(loaded), 0)
