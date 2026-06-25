"""Weather & Supply Impact Model — Stage 2 (항목 10).

인과 순서 구현:
1) WeatherSupplyAnomalyModel: 주산지 기상 노출 → 거래량(출하량) 예측.
   기상이 가격 이전에 '수급'으로 먼저 드러난다는 가설을 검증·활용한다.
2) 가격 모델에 기상 노출 feature를 추가(weather-aware)하고, 추가하지 않은 base와
   rolling-origin ablation으로 비교한다. weather_adjustment = weather_pred - base_pred.
3) 기상 충격 구간과 평시 구간을 분리 평가한다(충격 구간에서 개선되는지가 채택 기준).

기상이 특정 품목·horizon에서 개선을 못 주면 그 보정은 채택하지 않는다(평가표로 판단).
"""
from __future__ import annotations

import warnings
from typing import Optional

import numpy as np
import pandas as pd

from .base_models import LightGBMQuantileForecaster
from .evaluation import rolling_origin_backtest, summarize
from .metrics import naive_scale


class WeatherSupplyAnomalyModel:
    """기상 노출 → 거래량 예측 (수급 매개). 기상→수급 연결을 보여준다."""

    def __init__(self, params: Optional[dict] = None):
        self.params = params or dict(
            n_estimators=120, learning_rate=0.05, num_leaves=15,
            min_child_samples=5, verbose=-1,
        )

    def fit(self, exposure: pd.DataFrame, volume: pd.Series) -> "WeatherSupplyAnomalyModel":
        import lightgbm as lgb

        df = exposure.copy()
        df["__y"] = volume.reindex(df.index)
        df = df.dropna(subset=["__y"])
        self.feature_cols_ = [c for c in exposure.columns]
        if len(df) < 12:
            self.model_ = None
            return self
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.model_ = lgb.LGBMRegressor(**self.params).fit(
                df[self.feature_cols_], df["__y"]
            )
        return self

    def predict(self, exposure_row: pd.DataFrame) -> float:
        if self.model_ is None:
            return float("nan")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return float(self.model_.predict(exposure_row[self.feature_cols_])[0])


def detect_weather_shocks(
    exposure: pd.DataFrame, heat_thresh: int = 3, rain_window: int = 7, rain_quantile: float = 0.9
) -> set:
    """노출 feature에서 기상 충격일(date) 집합을 추출.

    - 최근 7일 폭염일수 >= heat_thresh, 또는
    - 최근 7일 누적강수가 상위 rain_quantile 분위 초과.
    """
    if exposure is None or exposure.empty:
        return set()
    shocks = pd.Series(False, index=exposure.index)
    heat_col = "wx_heat_days_7"
    rain_col = f"wx_rain_sum_{rain_window}"
    if heat_col in exposure:
        shocks |= exposure[heat_col].fillna(0) >= heat_thresh
    if rain_col in exposure:
        thr = exposure[rain_col].quantile(rain_quantile)
        shocks |= exposure[rain_col].fillna(0) > thr
    return {d.date() for d in exposure.index[shocks]}


def evaluate_weather_ablation(
    price: pd.Series,
    volume: Optional[pd.Series],
    weather_exposure: pd.DataFrame,
    horizons=(1, 7, 30),
    min_train: int = 60,
    test_start=None,
    step: int = 1,
    mase_season: int = 7,
    shock_dates: Optional[set] = None,
) -> dict:
    """base(no weather) vs weather-aware LightGBM ablation.

    반환: {"overall": df, "shock": df, "normal": df} 각각 (model, horizon)별 지표.
    """
    horizons = list(horizons)
    factories = {
        "base_lgbm": lambda: LightGBMQuantileForecaster(
            horizons=horizons, volume=volume, name="base_lgbm"
        ),
        "weather_lgbm": lambda: LightGBMQuantileForecaster(
            horizons=horizons, volume=volume, weather=weather_exposure, name="weather_lgbm"
        ),
    }
    preds = rolling_origin_backtest(
        price, factories, horizons, min_train=min_train, step=step, test_start=test_start
    )
    s = price.dropna().astype(float).sort_index()
    if test_start is not None:
        scale_series = s[s.index < pd.Timestamp(test_start)]
    else:
        scale_series = s.iloc[:min_train]
    scale = naive_scale(scale_series, season_length=mase_season)

    result = {"overall": summarize(preds, scale)}
    if shock_dates:
        shock_ts = {pd.Timestamp(d) for d in shock_dates}
        is_shock = preds["target_date"].isin(shock_ts)
        result["shock"] = summarize(preds[is_shock], scale)
        result["normal"] = summarize(preds[~is_shock], scale)
    return result
