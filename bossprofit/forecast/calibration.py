"""예측구간 conformal 보정 + 신뢰등급 (항목 13).

LightGBM 분위수 구간을 그대로 신뢰하지 않는다. 분위수 모델은 종종 구간이 좁아
실제 coverage가 목표(80%)에 못 미친다. Conformalized Quantile Regression(CQR)으로
validation 적합도 점수를 이용해 구간을 보정하면 유한표본에서도 목표 coverage를 보장한다.

CQR:
  conformity score E_i = max(lower_i - y_i, y_i - upper_i)
  d = (1-alpha) 분위수(유한표본 보정) of {E_i}
  보정 구간 = [lower - d, upper + d]

추가:
- 극단 기상/데이터 부족 시 구간을 넓히고 신뢰등급을 낮춘다.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np


class ConformalIntervalCalibrator:
    """horizon별 CQR 보정량 d를 학습/적용한다."""

    def __init__(self, target_coverage: float = 0.8):
        self.target_coverage = target_coverage
        self.alpha = 1.0 - target_coverage
        self.d_: Optional[float] = None

    def fit(self, lower, upper, actual) -> "ConformalIntervalCalibrator":
        lower = np.asarray(lower, dtype="float64")
        upper = np.asarray(upper, dtype="float64")
        y = np.asarray(actual, dtype="float64")
        mask = ~(np.isnan(lower) | np.isnan(upper) | np.isnan(y))
        lower, upper, y = lower[mask], upper[mask], y[mask]
        n = len(y)
        if n == 0:
            self.d_ = 0.0
            return self
        scores = np.maximum(lower - y, y - upper)
        # 유한표본 보정 분위수 레벨
        level = min(1.0, math.ceil((n + 1) * self.target_coverage) / n)
        self.d_ = float(np.quantile(scores, level, method="higher"))
        return self

    def calibrate(self, lower: float, upper: float) -> tuple[float, float]:
        d = self.d_ or 0.0
        return lower - d, upper + d


def empirical_coverage(lower, upper, actual) -> float:
    """[lower, upper] 안에 actual이 들어간 비율."""
    lower = np.asarray(lower, dtype="float64")
    upper = np.asarray(upper, dtype="float64")
    y = np.asarray(actual, dtype="float64")
    mask = ~(np.isnan(lower) | np.isnan(upper) | np.isnan(y))
    lower, upper, y = lower[mask], upper[mask], y[mask]
    if len(y) == 0:
        return float("nan")
    inside = (y >= lower) & (y <= upper)
    return float(np.mean(inside))


def confidence_grade(
    n_history: int,
    interval_width: float,
    median: float,
    extreme: bool = False,
    min_history: int = 60,
    wide_ratio: float = 0.30,
) -> str:
    """예측 신뢰등급. 데이터 부족·극단 사건·과도하게 넓은 구간이면 낮춘다."""
    rel_width = interval_width / abs(median) if median else float("inf")
    if n_history < 30 or extreme or rel_width > wide_ratio:
        return "LOW"
    if n_history < min_history or rel_width > wide_ratio * 0.6:
        return "MEDIUM"
    return "HIGH"


def widen_for_low_confidence(
    lower: float, upper: float, median: float, grade: str
) -> tuple[float, float]:
    """신뢰등급이 낮으면 구간을 넓혀 과신을 방지한다."""
    factor = {"HIGH": 1.0, "MEDIUM": 1.25, "LOW": 1.6}.get(grade, 1.0)
    half = (upper - lower) / 2.0 * factor
    return median - half, median + half
