from decimal import Decimal

from django.test import SimpleTestCase

from profit.forecasting.evaluation import (
    conformal_error_quantile,
    empirical_coverage,
    last_value,
    metric_bundle,
    naive_scale,
    seasonal_naive,
)


class ForecastEvaluationTests(SimpleTestCase):
    def test_metrics_preserve_error_direction_and_scale(self):
        scale = naive_scale([1, 2, 3, 4])
        metrics = metric_bundle([10, 20, 30], [12, 18, 33], scale=scale)

        self.assertEqual(scale, Decimal("1"))
        self.assertAlmostEqual(float(metrics["mae"]), 7 / 3)
        self.assertAlmostEqual(float(metrics["wape"]), 7 / 60)
        self.assertGreater(metrics["bias"], 0)
        self.assertAlmostEqual(float(metrics["mase"]), 7 / 3)

    def test_interval_metrics_and_finite_sample_calibration(self):
        width = conformal_error_quantile([1, 2, 3, 4], Decimal("0.8"))
        coverage = empirical_coverage([8, 18, 28], [12, 22, 32], [10, 24, 30])

        self.assertEqual(width, Decimal("4"))
        self.assertEqual(coverage, Decimal("2") / Decimal("3"))

    def test_baselines_use_only_available_history(self):
        history = [10, 12, 11, 15, 14, 9, 13]

        self.assertEqual(last_value(history), 13)
        self.assertEqual(seasonal_naive(history, horizon=1, season_length=7), 10)
        self.assertEqual(seasonal_naive(history, horizon=7, season_length=7), 13)
