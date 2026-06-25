"""가격 예측용 feature 엔지니어링 (항목 9).

원칙 (누수 방지):
- 모든 feature는 '예측 기준시점(t)까지 공개된 정보'만으로 만든다.
- lag/rolling은 shift로 t 시점 이전 값만 사용한다.
- 거래량 등 외생계열은 같은 날짜로 join하되, 운영에서는 t 시점에 가용한 lag만 쓴다
  (여기서는 학습 feature 생성이므로 과거 거래량 lag를 사용).
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

PRICE_LAGS = [1, 2, 7, 14, 28, 365]
ROLL_WINDOWS = [7, 14, 28]


def build_price_features(
    price: pd.Series,
    volume: Optional[pd.Series] = None,
    holidays: Optional[set] = None,
    weather: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """일별 가격 시계열에서 supervised feature 행렬을 만든다.

    반환 DataFrame은 price와 같은 인덱스를 가지며, 각 행 t의 feature는
    t 시점에 알 수 있는 정보(과거 lag·rolling, 달력)만 포함한다.
    target(미래값)은 포함하지 않는다 — 평가/학습 측에서 horizon만큼 shift해 만든다.
    """
    s = price.astype(float).sort_index()
    # 달력 정합을 위해 일 단위로 정규화(결측은 NaN). 운영도 동일 규칙.
    full_idx = pd.date_range(s.index.min(), s.index.max(), freq="D")
    s = s.reindex(full_idx)
    df = pd.DataFrame(index=full_idx)
    df["price"] = s

    # 1) lag
    for lag in PRICE_LAGS:
        df[f"lag_{lag}"] = s.shift(lag)

    # 2) rolling (shift(1)로 현재값 누수 차단)
    base = s.shift(1)
    for w in ROLL_WINDOWS:
        roll = base.rolling(window=w, min_periods=max(2, w // 2))
        df[f"roll_mean_{w}"] = roll.mean()
        df[f"roll_std_{w}"] = roll.std()
        df[f"roll_min_{w}"] = roll.min()
        df[f"roll_max_{w}"] = roll.max()

    # 3) 전년 동기/평년 대비 편차
    df["yoy_diff"] = s.shift(1) - s.shift(366)

    # 4) 달력
    idx = df.index
    df["dow"] = idx.dayofweek
    df["month"] = idx.month
    df["is_weekend"] = (idx.dayofweek >= 5).astype(int)
    if holidays:
        hol = pd.to_datetime(sorted(holidays))
        df["is_holiday"] = idx.normalize().isin(hol).astype(int)
    else:
        df["is_holiday"] = 0

    # 5) 외생: 도매 거래량 lag (수급 선행신호)
    if volume is not None and not volume.empty:
        v = volume.astype(float).sort_index().reindex(full_idx)
        df["vol_lag_1"] = v.shift(1)
        df["vol_lag_7"] = v.shift(7)
        df["vol_roll_mean_7"] = v.shift(1).rolling(7, min_periods=3).mean()
    else:
        df["vol_lag_1"] = np.nan
        df["vol_lag_7"] = np.nan
        df["vol_roll_mean_7"] = np.nan

    # 6) 주산지 기상 노출 (항목 10) — wx_ 컬럼 병합.
    #    관측일 t의 노출은 t에 알려진 정보이므로 t+h 예측 feature로 사용 가능.
    if weather is not None and not weather.empty:
        wx = weather.reindex(full_idx)
        for col in weather.columns:
            df[col] = wx[col]

    return df


def feature_columns(df: pd.DataFrame) -> list:
    """학습에 쓸 feature 컬럼(원본 price 제외, 동적으로 weather 컬럼 포함)."""
    return [c for c in df.columns if c != "price"]


FEATURE_COLUMNS = (
    [f"lag_{l}" for l in PRICE_LAGS]
    + [f"roll_{stat}_{w}" for w in ROLL_WINDOWS for stat in ("mean", "std", "min", "max")]
    + ["yoy_diff", "dow", "month", "is_weekend", "is_holiday",
       "vol_lag_1", "vol_lag_7", "vol_roll_mean_7"]
)
