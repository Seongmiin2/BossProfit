"""평가 지표 단위 테스트 (항목 8)."""
import numpy as np
import pandas as pd
from django.test import SimpleTestCase

from forecast import metrics


class MetricsTests(SimpleTestCase):
    def test_mae_rmse(self):
        y = [10, 20, 30]
        p = [12, 18, 33]  # 오차 +2, -2, +3
        self.assertAlmostEqual(metrics.mae(y, p), (2 + 2 + 3) / 3)
        self.assertAlmostEqual(metrics.rmse(y, p), np.sqrt((4 + 4 + 9) / 3))

    def test_wape(self):
        y = [10, 20, 30]   # sum|y|=60
        p = [12, 18, 33]   # sum|err|=7
        self.assertAlmostEqual(metrics.wape(y, p), 7 / 60)

    def test_bias_sign(self):
        # 과대예측 → 양수 bias
        self.assertGreater(metrics.bias([10, 10], [12, 13]), 0)
        # 과소예측 → 음수 bias
        self.assertLess(metrics.bias([10, 10], [8, 9]), 0)

    def test_nan_pairs_ignored(self):
        self.assertAlmostEqual(metrics.mae([10, np.nan, 30], [11, 5, 28]), (1 + 2) / 2)

    def test_naive_scale_and_mase(self):
        # 1스텝 차이 평균 = scale
        s = pd.Series([1.0, 2.0, 3.0, 4.0])  # diff=1 일정 → scale=1
        scale = metrics.naive_scale(s, season_length=1)
        self.assertAlmostEqual(scale, 1.0)
        # MAE=2면 MASE=2
        self.assertAlmostEqual(metrics.mase([10, 10], [12, 12], scale), 2.0)

    def test_mase_nan_scale(self):
        self.assertTrue(np.isnan(metrics.mase([1], [1], float("nan"))))
