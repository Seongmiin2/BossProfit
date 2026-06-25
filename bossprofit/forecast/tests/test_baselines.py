"""Baseline 예측기 테스트 (항목 8)."""
import pandas as pd
from django.test import SimpleTestCase

from forecast.baselines import (
    LastValueForecaster, SeasonalNaiveForecaster, MovingAverageForecaster,
)


def _series(values):
    idx = pd.date_range("2026-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype="float64")


class LastValueTests(SimpleTestCase):
    def test_predicts_last(self):
        f = LastValueForecaster().fit(_series([1, 2, 3, 9]))
        self.assertEqual(f.predict(1), 9)
        self.assertEqual(f.predict(30), 9)  # 모든 horizon 동일


class SeasonalNaiveTests(SimpleTestCase):
    def test_weekly_pattern(self):
        # 주기 7 패턴
        pattern = [10, 11, 12, 13, 14, 15, 16]
        f = SeasonalNaiveForecaster(7).fit(_series(pattern * 3))  # 21일
        # 마지막 위치는 패턴 끝(16). h=7 → 동일 위치(16)
        self.assertEqual(f.predict(7), 16)
        # h=1 → 다음 주기 첫 값(10)
        self.assertEqual(f.predict(1), 10)

    def test_fallback_when_short(self):
        f = SeasonalNaiveForecaster(7).fit(_series([5, 6, 7]))  # 7일 미만
        self.assertEqual(f.predict(3), 7)  # last value 폴백


class MovingAverageTests(SimpleTestCase):
    def test_window_mean(self):
        f = MovingAverageForecaster(3).fit(_series([1, 2, 3, 10, 20, 30]))
        self.assertEqual(f.predict(1), (10 + 20 + 30) / 3)
