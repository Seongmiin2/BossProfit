"""Rolling-origin (expanding window) 백테스트 (항목 8).

원칙 (누수 방지):
- 무작위 분할 금지. origin(예측 기준시점)을 시간순으로 전진시킨다.
- 각 origin에서 모델은 그 시점까지의 과거만으로 학습/예측한다.
- horizon별(1·7·30일) 독립 평가.
- test_start 로 'untouched test 구간'을 지정하면 그 이후 target만 집계에 포함한다.
- MASE 분모(scale)는 test 구간 '이전'의 학습 데이터에서만 계산해 누수를 막는다.

주의: horizon은 '관측 시퀀스 상의 스텝'이다. 달력일 기준 horizon을 원하면
data.to_regular_daily 로 일 단위 정규화한 시계열을 넣는다(테스트는 연속 일자 사용).
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import pandas as pd

from .baselines import DEFAULT_BASELINES
from .metrics import all_metrics, naive_scale


def rolling_origin_backtest(
    series: pd.Series,
    model_factories: dict[str, Callable],
    horizons: list[int],
    min_train: int,
    step: int = 1,
    test_start: Optional[date] = None,
) -> pd.DataFrame:
    """origin을 전진시키며 (model, horizon, origin, target, y_true, y_pred) 기록."""
    s = series.dropna().astype(float).sort_index()
    n = len(s)
    dates = list(s.index)
    vals = s.values
    ts = pd.Timestamp(test_start) if test_start is not None else None

    records = []
    for o in range(min_train - 1, n - 1, step):
        train = s.iloc[: o + 1]
        fitted = {name: f().fit(train) for name, f in model_factories.items()}
        for h in horizons:
            tpos = o + h
            if tpos >= n:
                continue
            target_date = dates[tpos]
            if ts is not None and target_date < ts:
                continue
            y_true = float(vals[tpos])
            for name, model in fitted.items():
                records.append({
                    "model": name,
                    "horizon": h,
                    "origin_date": dates[o],
                    "target_date": target_date,
                    "y_true": y_true,
                    "y_pred": model.predict(h),
                })
    return pd.DataFrame.from_records(
        records,
        columns=["model", "horizon", "origin_date", "target_date", "y_true", "y_pred"],
    )


def summarize(predictions: pd.DataFrame, scale: float) -> pd.DataFrame:
    """(model, horizon)별 지표 집계표."""
    if predictions.empty:
        return pd.DataFrame(
            columns=["model", "horizon", "mae", "rmse", "wape", "bias", "mase", "n"]
        )
    rows = []
    for (model, horizon), grp in predictions.groupby(["model", "horizon"]):
        m = all_metrics(grp["y_true"].values, grp["y_pred"].values, scale=scale)
        m["model"] = model
        m["horizon"] = horizon
        rows.append(m)
    cols = ["model", "horizon", "mae", "rmse", "wape", "bias", "mase", "n"]
    return pd.DataFrame(rows)[cols].sort_values(["horizon", "wape"]).reset_index(drop=True)


def evaluate_baselines(
    series: pd.Series,
    horizons: list[int] = (1, 7, 30),
    min_train: int = 30,
    test_start: Optional[date] = None,
    mase_season: int = 1,
    model_factories: Optional[dict[str, Callable]] = None,
    step: int = 1,
) -> pd.DataFrame:
    """baseline 일괄 평가. test 구간 이전 데이터로 MASE scale을 고정한다."""
    model_factories = model_factories or DEFAULT_BASELINES
    s = series.dropna().astype(float).sort_index()

    # MASE scale: test_start 이전(없으면 학습 최소구간) 데이터에서만 계산
    if test_start is not None:
        scale_series = s[s.index < pd.Timestamp(test_start)]
    else:
        scale_series = s.iloc[:min_train]
    scale = naive_scale(scale_series, season_length=mase_season)

    preds = rolling_origin_backtest(
        s, model_factories, list(horizons), min_train=min_train,
        step=step, test_start=test_start,
    )
    return summarize(preds, scale)
