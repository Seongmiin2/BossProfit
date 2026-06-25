"""예측구간 conformal 보정 테스트 (항목 13)."""
import numpy as np
from django.test import SimpleTestCase

from forecast.calibration import (
    ConformalIntervalCalibrator, empirical_coverage,
    confidence_grade, widen_for_low_confidence,
)


class ConformalTests(SimpleTestCase):
    def test_calibration_fixes_undercoverage(self):
        rng = np.random.RandomState(0)
        n = 1000
        y = rng.normal(0, 1, n)
        # 일부러 좁은 구간(±0.5σ) → 명백한 under-coverage(~38%)
        lower = np.full(n, -0.5)
        upper = np.full(n, 0.5)

        cal_idx, test_idx = slice(0, 500), slice(500, 1000)
        raw_cov = empirical_coverage(lower[test_idx], upper[test_idx], y[test_idx])
        self.assertLess(raw_cov, 0.6)  # 보정 전 과소

        calib = ConformalIntervalCalibrator(target_coverage=0.8).fit(
            lower[cal_idx], upper[cal_idx], y[cal_idx]
        )
        lo_c, up_c = calib.calibrate(-0.5, 0.5)
        cov = empirical_coverage(
            np.full(500, lo_c), np.full(500, up_c), y[test_idx]
        )
        # 보정 후 목표 80% 근처(±5%p)
        self.assertGreaterEqual(cov, 0.75)
        self.assertLessEqual(cov, 0.85)

    def test_calibration_widens_interval(self):
        rng = np.random.RandomState(1)
        y = rng.normal(0, 1, 400)
        calib = ConformalIntervalCalibrator(0.8).fit(
            np.full(400, -0.5), np.full(400, 0.5), y
        )
        lo, up = calib.calibrate(-0.5, 0.5)
        self.assertLess(lo, -0.5)
        self.assertGreater(up, 0.5)


class ConfidenceGradeTests(SimpleTestCase):
    def test_low_when_scarce_or_extreme(self):
        self.assertEqual(confidence_grade(n_history=20, interval_width=10, median=1000), "LOW")
        self.assertEqual(
            confidence_grade(n_history=200, interval_width=10, median=1000, extreme=True), "LOW"
        )

    def test_low_when_interval_too_wide(self):
        self.assertEqual(
            confidence_grade(n_history=200, interval_width=500, median=1000), "LOW"
        )

    def test_high_when_ample_and_tight(self):
        self.assertEqual(
            confidence_grade(n_history=200, interval_width=80, median=1000), "HIGH"
        )

    def test_widen_lowers_confidence_widens_more(self):
        lo_h, up_h = widen_for_low_confidence(90, 110, 100, "HIGH")
        lo_l, up_l = widen_for_low_confidence(90, 110, 100, "LOW")
        self.assertEqual((lo_h, up_h), (90, 110))      # HIGH: 변화 없음
        self.assertLess(lo_l, 90)                       # LOW: 더 넓게
        self.assertGreater(up_l, 110)
