"""예측용 시계열 로더.

MarketPriceObservation 을 품목별 일별 시계열(pd.Series)로 변환한다.
- 같은 (날짜) 중복은 자연키 unique로 이미 1건이지만, 방어적으로 마지막 값을 사용한다.
- 결측일은 비워둔 채 반환하고, 필요 시 호출측에서 reindex/보간한다.
- 품질 플래그가 'ok'가 아닌 관측은 기본 포함하되 옵션으로 제외할 수 있다.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from market.models import MarketPriceObservation, WholesaleAuctionObservation


def load_price_series(
    item,
    market_type: str = "retail",
    region: str = "",
    unit: Optional[str] = None,
    source: str = "kamis",
    start: Optional[date] = None,
    end: Optional[date] = None,
    exclude_flagged: bool = False,
) -> pd.Series:
    """품목의 일별 가격 시계열을 DatetimeIndex pd.Series(float)로 반환."""
    qs = MarketPriceObservation.objects.filter(
        item=item, market_type=market_type, region=region, source=source
    )
    if unit is not None:
        qs = qs.filter(unit=unit)
    if start:
        qs = qs.filter(observation_date__gte=start)
    if end:
        qs = qs.filter(observation_date__lte=end)
    if exclude_flagged:
        qs = qs.filter(quality_flag="ok")

    rows = list(qs.values("observation_date", "price").order_by("observation_date"))
    if not rows:
        return pd.Series(dtype="float64")

    df = pd.DataFrame(rows)
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df["price"] = df["price"].astype(float)
    s = df.set_index("observation_date")["price"]
    # 동일 날짜 중복 방어: 마지막 값
    s = s[~s.index.duplicated(keep="last")].sort_index()
    s.name = item.code
    return s


def load_volume_series(
    item,
    market: Optional[str] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> pd.Series:
    """품목의 일별 도매 거래량 시계열(여러 시장이면 일자 합계)."""
    qs = WholesaleAuctionObservation.objects.filter(item=item)
    if market:
        qs = qs.filter(market=market)
    if start:
        qs = qs.filter(observation_date__gte=start)
    if end:
        qs = qs.filter(observation_date__lte=end)
    rows = list(qs.values("observation_date", "volume"))
    if not rows:
        return pd.Series(dtype="float64")
    df = pd.DataFrame(rows)
    df = df.dropna(subset=["volume"])
    if df.empty:
        return pd.Series(dtype="float64")
    df["observation_date"] = pd.to_datetime(df["observation_date"])
    df["volume"] = df["volume"].astype(float)
    s = df.groupby("observation_date")["volume"].sum().sort_index()
    s.name = f"{item.code}_volume"
    return s


def to_regular_daily(series: pd.Series) -> pd.Series:
    """일 단위로 reindex(결측일을 NaN으로 노출). 보간은 호출측 판단."""
    if series.empty:
        return series
    full = pd.date_range(series.index.min(), series.index.max(), freq="D")
    return series.reindex(full)
