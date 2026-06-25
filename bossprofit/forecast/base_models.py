"""Base Price Model (항목 9).

세 모델을 동일 Forecaster 인터페이스로 제공해 rolling-origin 평가에 그대로 투입한다.
- SarimaxForecaster: 추세·자기상관·계절성 + 통계 신뢰구간
- LightGBMQuantileForecaster: lag/rolling/달력/거래량 feature로 분위수(80% 구간) 직접 예측
- EnsembleForecaster: validation 구간 성능으로 고정한 가중치 결합 (test로 가중치 정하지 않음)

분위수 예측을 위해 predict_quantiles(horizon) -> {q: value} 를 추가로 제공한다.
"""
from __future__ import annotations

import warnings
from typing import Callable, Optional

import numpy as np
import pandas as pd

from .baselines import Forecaster
from .features import build_price_features, feature_columns
from .metrics import wape

DEFAULT_QUANTILES = (0.1, 0.5, 0.9)
_MIN_ROWS = 24


class SarimaxForecaster(Forecaster):
    """statsmodels SARIMAX. order/seasonal_order는 보수적 기본값."""

    def __init__(self, order=(1, 1, 1), seasonal_order=(0, 0, 0, 0)):
        self.order = order
        self.seasonal_order = seasonal_order
        self.name = f"sarimax_{order}"

    def fit(self, history: pd.Series) -> "SarimaxForecaster":
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        self.history_ = history.dropna().astype(float)
        y = self.history_.values
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            self.res_ = SARIMAX(
                y, order=self.order, seasonal_order=self.seasonal_order,
                enforce_stationarity=False, enforce_invertibility=False,
            ).fit(disp=False)
        return self

    def predict(self, horizon: int) -> float:
        if self.history_.empty:
            return float("nan")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fc = self.res_.forecast(horizon)
        return float(np.asarray(fc)[-1])

    def predict_quantiles(self, horizon: int, quantiles=DEFAULT_QUANTILES) -> dict:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            f = self.res_.get_forecast(horizon)
            mean = float(np.asarray(f.predicted_mean)[-1])
            se = float(np.asarray(f.se_mean)[-1])
        from scipy.stats import norm
        return {q: mean + norm.ppf(q) * se for q in quantiles}


class LightGBMQuantileForecaster(Forecaster):
    """LightGBM 분위수 회귀. horizon별 direct 예측 모델을 학습한다.

    volume(도매 거래량)·holidays는 외생 입력으로 생성자에서 받는다(평가 시 factory가 주입).
    """

    def __init__(
        self,
        horizons=(1, 7, 30),
        quantiles=DEFAULT_QUANTILES,
        volume: Optional[pd.Series] = None,
        holidays: Optional[set] = None,
        weather: Optional[pd.DataFrame] = None,
        params: Optional[dict] = None,
        name: str = "lightgbm_quantile",
    ):
        self.horizons = tuple(horizons)
        self.quantiles = tuple(quantiles)
        self.volume = volume
        self.holidays = holidays
        self.weather = weather
        self.params = params or dict(
            n_estimators=120, learning_rate=0.05, num_leaves=15,
            min_child_samples=5, subsample=0.9, colsample_bytree=0.9,
            verbose=-1,
        )
        self.name = name

    def fit(self, history: pd.Series) -> "LightGBMQuantileForecaster":
        import lightgbm as lgb

        self.history_ = history.dropna().astype(float)
        feats = build_price_features(
            history, volume=self.volume, holidays=self.holidays, weather=self.weather
        )
        price = feats["price"]
        self.feature_cols_ = feature_columns(feats)
        X_all = feats[self.feature_cols_]
        self.last_X_ = X_all.iloc[[-1]]
        self.models_ = {}

        for h in self.horizons:
            target = price.shift(-h).rename("y")
            data = X_all.join(target).dropna(subset=["y"])
            if len(data) < _MIN_ROWS:
                continue
            Xh, yh = data[self.feature_cols_], data["y"]
            for q in self.quantiles:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    m = lgb.LGBMRegressor(objective="quantile", alpha=q, **self.params)
                    m.fit(Xh, yh)
                self.models_[(h, q)] = m
        return self

    def predict_quantiles(self, horizon: int) -> dict:
        fallback = float(self.history_.iloc[-1]) if not self.history_.empty else float("nan")
        out = {}
        for q in self.quantiles:
            m = self.models_.get((horizon, q))
            if m is None:
                out[q] = fallback
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    out[q] = float(m.predict(self.last_X_)[0])
        # 분위수 단조성 보정 (quantile crossing 방지)
        qs = sorted(out)
        vals = np.maximum.accumulate([out[q] for q in qs])
        return {q: float(v) for q, v in zip(qs, vals)}

    def predict(self, horizon: int) -> float:
        q = self.predict_quantiles(horizon)
        return q.get(0.5, next(iter(q.values())))


def compute_ensemble_weights(
    series: pd.Series,
    member_factories: dict[str, Callable],
    horizons: list[int],
    val_start,
    min_train: int,
    val_end=None,
    eps: float = 1e-6,
) -> dict:
    """validation 구간 rolling-origin WAPE로 horizon별 가중치를 고정한다.

    가중치 = (1/WAPE) 정규화. test 구간은 보지 않는다.
    """
    from .evaluation import rolling_origin_backtest

    preds = rolling_origin_backtest(
        series, member_factories, horizons, min_train=min_train, test_start=val_start
    )
    if val_end is not None:
        preds = preds[preds["target_date"] <= pd.Timestamp(val_end)]

    weights = {}
    for h in horizons:
        sub = preds[preds["horizon"] == h]
        inv = {}
        for name, grp in sub.groupby("model"):
            w = wape(grp["y_true"].values, grp["y_pred"].values)
            inv[name] = 1.0 / (w + eps) if np.isfinite(w) else 0.0
        total = sum(inv.values())
        if total <= 0:
            n = len(member_factories)
            weights[h] = {name: 1.0 / n for name in member_factories}
        else:
            weights[h] = {name: v / total for name, v in inv.items()}
    return weights


class EnsembleForecaster(Forecaster):
    """고정 가중치로 멤버 예측을 결합. 가중치는 validation에서 미리 계산해 주입한다."""

    def __init__(self, member_factories: dict[str, Callable], weights: dict):
        self.member_factories = member_factories
        self.weights = weights  # {horizon: {member_name: weight}}
        self.name = "ensemble"

    def fit(self, history: pd.Series) -> "EnsembleForecaster":
        self.history_ = history.dropna().astype(float)
        self.members_ = {name: f().fit(history) for name, f in self.member_factories.items()}
        return self

    def predict(self, horizon: int) -> float:
        w = self.weights.get(horizon)
        if not w:
            # 가중치 없으면 단순 평균
            vals = [m.predict(horizon) for m in self.members_.values()]
            return float(np.nanmean(vals))
        total = 0.0
        for name, member in self.members_.items():
            total += w.get(name, 0.0) * member.predict(horizon)
        return float(total)
