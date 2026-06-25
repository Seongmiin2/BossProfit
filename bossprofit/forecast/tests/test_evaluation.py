"""Rolling-origin 백테스트 테스트 (항목 8)."""
import pandas as pd
from django.test import SimpleTestCase

from forecast.baselines import LastValueForecaster, SeasonalNaiveForecaster
from forecast.evaluation import rolling_origin_backtest, evaluate_baselines


def _series(values, start="2026-01-01"):
    idx = pd.date_range(start, periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype="float64")


class RollingOriginTests(SimpleTestCase):
    def test_prediction_count_and_no_future_leak(self):
        s = _series(list(range(10)))  # 길이 10
        preds = rolling_origin_backtest(
            s, {"last_value": lambda: LastValueForecaster()},
            horizons=[1, 2], min_train=5, step=1,
        )
        # origin o=4..8: h1 5건, h2 4건(o<=7) → 9건
        self.assertEqual(len(preds), 9)
        # target은 항상 origin보다 미래
        self.assertTrue((preds["target_date"] > preds["origin_date"]).all())

    def test_seasonal_naive_perfect_on_periodic(self):
        # 순수 주기 7 패턴 → seasonal_naive_7 오차 0
        pattern = [10, 12, 11, 15, 14, 9, 13]
        s = _series(pattern * 8)  # 56일
        summary = evaluate_baselines(
            s, horizons=[1, 7], min_train=14, mase_season=7,
            model_factories={"seasonal_naive_7": lambda: SeasonalNaiveForecaster(7)},
        )
        for _, row in summary.iterrows():
            self.assertAlmostEqual(row["wape"], 0.0, places=9)
            self.assertAlmostEqual(row["mae"], 0.0, places=9)

    def test_test_start_filters_targets(self):
        s = _series(list(range(40)))
        cutoff = s.index[30].date()
        preds = rolling_origin_backtest(
            s, {"last_value": lambda: LastValueForecaster()},
            horizons=[1], min_train=10, test_start=cutoff,
        )
        # 모든 target은 test_start 이후
        self.assertTrue((preds["target_date"] >= pd.Timestamp(cutoff)).all())
        self.assertGreater(len(preds), 0)

    def test_summary_has_all_metrics(self):
        s = _series([float(i % 5) + 1 for i in range(40)])
        summary = evaluate_baselines(s, horizons=[1, 7], min_train=14, mase_season=7)
        for col in ["model", "horizon", "mae", "rmse", "wape", "bias", "mase", "n"]:
            self.assertIn(col, summary.columns)
        # 기본 3개 baseline × 2 horizon = 6행
        self.assertEqual(len(summary), 6)
