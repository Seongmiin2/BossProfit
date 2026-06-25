"""주산지 가중 기상 노출 feature (항목 10).

인과 순서:
    주산지 기상 → 생육·수확 충격 → 출하량·거래량 변화 → 가격 보정량

여기서는 '주산지 기상'을 품목 단위로 집계해 노출 feature를 만든다.
- 품목 주산지 비중(CropProductionRegion)으로 지역을 가중
- 지역-관측소 매핑(WeatherStationMapping)으로 관측소를 가중
- 같은 강수·기온이라도 생육단계(CropGrowthStage)에 따라 다르므로 단계 지표를 덧붙인다

모든 노출은 '관측일 t까지 알려진 관측'만 사용한다(미래 누수 없음).
운영의 미래 구간 예보 사용은 항목 5의 WeatherForecastSnapshot(issued_at) 단계에서 결합한다.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd
from django.utils import timezone

WEATHER_VARS = ["tavg", "tmin", "tmax", "rain", "humidity", "sunshine", "soil_moisture"]
GDD_BASE = 10.0          # 생육도일 기준온도
HEAT_TMAX = 33.0         # 폭염 기준
COLD_TMIN = 0.0          # 한파 기준
DRY_RAIN = 1.0           # 무강수 기준(mm)
EXPOSURE_WINDOWS = [3, 7, 14, 30]


def load_item_weather(item, start: Optional[date] = None, end: Optional[date] = None) -> pd.DataFrame:
    """품목의 주산지·관측소 가중 일별 기상 DataFrame(컬럼=WEATHER_VARS)."""
    from market.models import CropProductionRegion
    from weather.models import WeatherStationMapping, WeatherObservation

    region_shares = list(
        CropProductionRegion.objects.filter(item=item).select_related("region")
    )
    if not region_shares:
        return pd.DataFrame()

    region_frames = []
    region_weights = []
    for cpr in region_shares:
        mappings = list(
            WeatherStationMapping.objects.filter(region=cpr.region).select_related("station")
        )
        if not mappings:
            continue
        station_ids = [m.station_id for m in mappings]
        st_weight = {m.station_id: m.weight for m in mappings}

        qs = WeatherObservation.objects.filter(station_id__in=station_ids)
        if start:
            qs = qs.filter(observed_date__gte=start)
        if end:
            qs = qs.filter(observed_date__lte=end)
        rows = list(qs.values("station_id", "observed_date", "variables"))
        if not rows:
            continue

        recs = []
        for r in rows:
            rec = {"date": r["observed_date"], "w": st_weight.get(r["station_id"], 1.0)}
            for v in WEATHER_VARS:
                rec[v] = r["variables"].get(v)
            recs.append(rec)
        sdf = pd.DataFrame(recs)
        sdf["date"] = pd.to_datetime(sdf["date"])

        # 관측소 가중 평균(결측 변수는 가중에서 제외)
        agg = {}
        for v in WEATHER_VARS:
            vals = sdf[["date", v, "w"]].dropna(subset=[v])
            if vals.empty:
                continue
            num = vals.assign(wv=vals[v] * vals["w"]).groupby("date")["wv"].sum()
            den = vals.groupby("date")["w"].sum()
            agg[v] = num / den
        if not agg:
            continue
        region_frames.append(pd.DataFrame(agg))
        region_weights.append(cpr.weight)

    if not region_frames:
        return pd.DataFrame()

    # 지역 가중 평균
    all_dates = sorted(set().union(*[f.index for f in region_frames]))
    out = pd.DataFrame(index=pd.DatetimeIndex(all_dates))
    for v in WEATHER_VARS:
        num = pd.Series(0.0, index=out.index)
        den = pd.Series(0.0, index=out.index)
        for f, w in zip(region_frames, region_weights):
            if v in f.columns:
                col = f[v].reindex(out.index)
                mask = col.notna()
                num[mask] += col[mask] * w
                den[mask] += w
        with np.errstate(invalid="ignore"):
            out[v] = np.where(den > 0, num / den, np.nan)
    return out.sort_index()


def load_item_forecast_weather(item, as_of: date, horizon: int):
    """품목의 주산지 미래 기상 예보 DataFrame(컬럼=WEATHER_VARS).

    point-in-time 보장: as_of 시점까지 발행된(issued_at <= as_of) 예보만 사용하고,
    (as_of, as_of+horizon] 구간 valid_at만 반환한다. 같은 (관측소, valid_at)에
    여러 발행본이 있으면 가장 최근 발행본을 쓴다.
    반환: (DataFrame, 사용된 최신 issued_at 또는 None)
    """
    from datetime import timedelta
    from market.models import CropProductionRegion
    from weather.models import WeatherStationMapping, WeatherForecastSnapshot

    region_shares = list(
        CropProductionRegion.objects.filter(item=item).select_related("region")
    )
    if not region_shares:
        return pd.DataFrame(), None

    end = as_of + timedelta(days=horizon)
    latest_issued = None
    region_frames, region_weights = [], []

    for cpr in region_shares:
        mappings = list(
            WeatherStationMapping.objects.filter(region=cpr.region).select_related("station")
        )
        if not mappings:
            continue
        station_ids = [m.station_id for m in mappings]
        st_weight = {m.station_id: m.weight for m in mappings}

        qs = (
            WeatherForecastSnapshot.objects.filter(
                station_id__in=station_ids,
                valid_at__gt=as_of, valid_at__lte=end,
            )
            .order_by("issued_at")
            .values("station_id", "valid_at", "variables", "issued_at")
        )
        # point-in-time: 발행일이 as_of 당일 이하인 예보만(아직 발행 안 된 예보 차단)
        rows = [
            r for r in qs
            if r["issued_at"] is None or timezone.localtime(r["issued_at"]).date() <= as_of
        ]
        if not rows:
            continue

        # (관측소, valid_at) 별 최신 발행본만
        dedup = {}
        for r in rows:
            dedup[(r["station_id"], r["valid_at"])] = r
        recs = []
        for r in dedup.values():
            if r["issued_at"] and (latest_issued is None or r["issued_at"] > latest_issued):
                latest_issued = r["issued_at"]
            rec = {"date": r["valid_at"], "w": st_weight.get(r["station_id"], 1.0)}
            for v in WEATHER_VARS:
                rec[v] = r["variables"].get(v)
            recs.append(rec)
        sdf = pd.DataFrame(recs)
        sdf["date"] = pd.to_datetime(sdf["date"])

        agg = {}
        for v in WEATHER_VARS:
            vals = sdf[["date", v, "w"]].dropna(subset=[v])
            if vals.empty:
                continue
            num = vals.assign(wv=vals[v] * vals["w"]).groupby("date")["wv"].sum()
            den = vals.groupby("date")["w"].sum()
            agg[v] = num / den
        if not agg:
            continue
        region_frames.append(pd.DataFrame(agg))
        region_weights.append(cpr.weight)

    if not region_frames:
        return pd.DataFrame(), latest_issued

    all_dates = sorted(set().union(*[f.index for f in region_frames]))
    out = pd.DataFrame(index=pd.DatetimeIndex(all_dates))
    for v in WEATHER_VARS:
        num = pd.Series(0.0, index=out.index)
        den = pd.Series(0.0, index=out.index)
        for f, w in zip(region_frames, region_weights):
            if v in f.columns:
                col = f[v].reindex(out.index)
                mask = col.notna()
                num[mask] += col[mask] * w
                den[mask] += w
        with np.errstate(invalid="ignore"):
            out[v] = np.where(den > 0, num / den, np.nan)
    return out.sort_index(), latest_issued


def build_weather_exposure(weather: pd.DataFrame, growth_doy: Optional[set] = None) -> pd.DataFrame:
    """일별 기상에서 누적·이상 노출 feature를 만든다(컬럼 접두사 wx_).

    growth_doy: 민감 생육단계에 해당하는 day-of-year 집합(있으면 단계 지표 추가).
    """
    if weather is None or weather.empty:
        return pd.DataFrame()

    w = weather.sort_index()
    idx = pd.date_range(w.index.min(), w.index.max(), freq="D")
    w = w.reindex(idx)
    out = pd.DataFrame(index=idx)

    tavg = w.get("tavg")
    tmax = w.get("tmax")
    tmin = w.get("tmin")
    rain = w.get("rain")
    soil = w.get("soil_moisture")  # 농업기상(농진청)에서만 제공

    # 일 단위 파생
    if tavg is not None:
        gdd = (tavg - GDD_BASE).clip(lower=0)
    else:
        gdd = pd.Series(np.nan, index=idx)
    heat = (tmax >= HEAT_TMAX).astype(float) if tmax is not None else pd.Series(np.nan, index=idx)
    cold = (tmin <= COLD_TMIN).astype(float) if tmin is not None else pd.Series(np.nan, index=idx)
    dry = (rain < DRY_RAIN).astype(float) if rain is not None else pd.Series(np.nan, index=idx)

    # 누적/이상 노출 (관측일 t까지 포함 — t에 알려진 정보)
    for win in EXPOSURE_WINDOWS:
        if rain is not None:
            out[f"wx_rain_sum_{win}"] = rain.rolling(win, min_periods=1).sum()
        out[f"wx_gdd_sum_{win}"] = gdd.rolling(win, min_periods=1).sum()
        out[f"wx_heat_days_{win}"] = heat.rolling(win, min_periods=1).sum()
        out[f"wx_dry_days_{win}"] = dry.rolling(win, min_periods=1).sum()
        if tavg is not None:
            roll = tavg.rolling(win, min_periods=2)
            out[f"wx_tavg_mean_{win}"] = roll.mean()

    # 평년(긴 롤링) 대비 기온 이상편차
    if tavg is not None:
        normal = tavg.rolling(30, min_periods=10).mean()
        out["wx_tavg_anomaly"] = tavg - normal
    # 토양수분(농업기상): 수준 + 평년 대비 편차(가뭄/과습 신호)
    if soil is not None and soil.notna().any():
        out["wx_soil_moisture"] = soil.ffill()
        soil_normal = soil.rolling(30, min_periods=5).mean()
        out["wx_soil_anomaly"] = soil - soil_normal
    # 연속 무강수일수
    if rain is not None:
        dryb = (rain < DRY_RAIN)
        grp = (~dryb).cumsum()
        out["wx_consec_dry"] = dryb.groupby(grp).cumsum()

    # 생육단계 지표
    if growth_doy:
        doy = idx.dayofyear
        out["wx_in_sensitive_stage"] = pd.Series(
            [1 if d in growth_doy else 0 for d in doy], index=idx
        )
    else:
        out["wx_in_sensitive_stage"] = 0

    return out


def sensitive_growth_doys(item) -> set:
    """품목의 생육단계 start_day~end_day를 day-of-year 집합으로."""
    from market.models import CropGrowthStage
    doys = set()
    for st in CropGrowthStage.objects.filter(item=item):
        doys.update(range(st.start_day, st.end_day + 1))
    return doys
