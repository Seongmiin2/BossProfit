"""예측 평가 지표 (항목 8).

- MAE, RMSE: 절대오차
- WAPE: sum(|y-ŷ|)/sum(|y|)  — 규모 보정 백분율 오차
- Bias: mean(ŷ-y)  — 계통 편향(양수=과대예측)
- MASE: MAE / naive_scale  — 단순 나이브 대비 상대 성능(<1이면 나이브보다 우수)

MASE의 scale은 '학습 구간'의 계절 나이브 1스텝 오차 평균으로 고정한다(누수 방지).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _align(y_true, y_pred):
    y = np.asarray(y_true, dtype="float64")
    p = np.asarray(y_pred, dtype="float64")
    mask = ~(np.isnan(y) | np.isnan(p))
    return y[mask], p[mask]


def mae(y_true, y_pred) -> float:
    y, p = _align(y_true, y_pred)
    return float(np.mean(np.abs(y - p))) if len(y) else float("nan")


def rmse(y_true, y_pred) -> float:
    y, p = _align(y_true, y_pred)
    return float(np.sqrt(np.mean((y - p) ** 2))) if len(y) else float("nan")


def wape(y_true, y_pred) -> float:
    y, p = _align(y_true, y_pred)
    denom = np.sum(np.abs(y))
    return float(np.sum(np.abs(y - p)) / denom) if denom else float("nan")


def bias(y_true, y_pred) -> float:
    y, p = _align(y_true, y_pred)
    return float(np.mean(p - y)) if len(y) else float("nan")


def naive_scale(train_series: pd.Series, season_length: int = 1) -> float:
    """학습 구간의 계절 나이브 1스텝 절대오차 평균. MASE 분모."""
    s = train_series.dropna().astype(float).values
    if len(s) <= season_length:
        return float("nan")
    diffs = np.abs(s[season_length:] - s[:-season_length])
    scale = np.mean(diffs)
    return float(scale) if scale > 0 else float("nan")


def mase(y_true, y_pred, scale: float) -> float:
    if scale is None or np.isnan(scale) or scale == 0:
        return float("nan")
    return mae(y_true, y_pred) / scale


def all_metrics(y_true, y_pred, scale: float | None = None) -> dict:
    out = {
        "mae": mae(y_true, y_pred),
        "rmse": rmse(y_true, y_pred),
        "wape": wape(y_true, y_pred),
        "bias": bias(y_true, y_pred),
        "n": int(len(_align(y_true, y_pred)[0])),
    }
    if scale is not None:
        out["mase"] = mase(y_true, y_pred, scale)
    return out
