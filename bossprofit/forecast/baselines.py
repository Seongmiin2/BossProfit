"""Baseline 예측 모델 (항목 8).

모든 예측기는 동일 인터페이스를 따른다 → 이후 Base/Weather/Residual 모델도 같은
인터페이스로 갈아끼워 rolling-origin 평가에 그대로 투입한다.

    class Forecaster:
        name: str
        def fit(self, history: pd.Series) -> "Forecaster"
        def predict(self, horizon: int) -> float        # 점예측
        # (분위수 모델은 predict_quantiles 를 추가로 제공)

baseline은 과거 실제값만 사용하므로 미래 누수가 없다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class Forecaster:
    name = "base"

    def fit(self, history: pd.Series) -> "Forecaster":
        self.history_ = history.dropna().astype(float)
        return self

    def predict(self, horizon: int) -> float:  # pragma: no cover
        raise NotImplementedError


class LastValueForecaster(Forecaster):
    """마지막 관측값을 모든 horizon에 대해 그대로 예측 (random walk)."""

    name = "last_value"

    def predict(self, horizon: int) -> float:
        if self.history_.empty:
            return float("nan")
        return float(self.history_.iloc[-1])


class SeasonalNaiveForecaster(Forecaster):
    """season_length 이전의 값을 예측. 예) 주간 계절성=7, 연간=365.

    horizon h 예측 = history[-(season_length) + ((h-1) mod season_length)] 위치의 값.
    충분한 이력이 없으면 LastValue로 폴백한다.
    """

    def __init__(self, season_length: int = 7):
        self.season_length = season_length
        self.name = f"seasonal_naive_{season_length}"

    def predict(self, horizon: int) -> float:
        h = self.history_
        m = self.season_length
        if h.empty:
            return float("nan")
        if len(h) < m:
            return float(h.iloc[-1])
        # 마지막 한 주기 내에서 대응 위치를 집어 미래로 투영
        idx = -m + ((horizon - 1) % m)
        return float(h.iloc[idx])


class MovingAverageForecaster(Forecaster):
    """최근 window 평균을 모든 horizon에 대해 예측."""

    def __init__(self, window: int = 7):
        self.window = window
        self.name = f"moving_average_{window}"

    def predict(self, horizon: int) -> float:
        h = self.history_
        if h.empty:
            return float("nan")
        return float(h.iloc[-self.window:].mean())


# 모델 팩토리: 평가에서 origin마다 새 인스턴스를 만들기 위해 callable 사용
DEFAULT_BASELINES = {
    "last_value": lambda: LastValueForecaster(),
    "seasonal_naive_7": lambda: SeasonalNaiveForecaster(7),
    "moving_average_7": lambda: MovingAverageForecaster(7),
}
