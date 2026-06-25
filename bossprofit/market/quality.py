"""데이터 품질·누락률 보고 (항목 7).

품목·관측소별로 수집 커버리지와 결측률, 품질 플래그 분포를 집계한다.
'누락률'은 [start, end] 기대 일수 대비 실제 관측이 존재한 일수의 비율로 정의한다.
모델 학습 전, 어떤 품목/지역이 충분한 데이터를 가졌는지 판단하는 근거가 된다.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Optional

from django.db.models import Count, Min, Max

from .models import MarketItem, MarketPriceObservation, WholesaleAuctionObservation


def _expected_days(start: date, end: date) -> int:
    return (end - start).days + 1


def price_quality_report(start: date, end: date) -> list[dict]:
    """품목별 KAMIS 가격 관측 커버리지/결측률/플래그 분포."""
    expected = _expected_days(start, end)
    report = []
    for item in MarketItem.objects.filter(is_active=True):
        obs = MarketPriceObservation.objects.filter(
            item=item, observation_date__gte=start, observation_date__lte=end
        )
        distinct_days = obs.values("observation_date").distinct().count()
        flags = Counter(obs.values_list("quality_flag", flat=True))
        report.append({
            "item_code": item.code,
            "item_name": item.name,
            "expected_days": expected,
            "observed_days": distinct_days,
            "missing_rate": round(1 - distinct_days / expected, 4) if expected else None,
            "row_count": obs.count(),
            "flags": dict(flags),
        })
    return report


def wholesale_quality_report(start: date, end: date) -> list[dict]:
    """품목별 도매 경락 커버리지 + 거래량 결측 여부."""
    expected = _expected_days(start, end)
    report = []
    for item in MarketItem.objects.filter(is_active=True):
        obs = WholesaleAuctionObservation.objects.filter(
            item=item, observation_date__gte=start, observation_date__lte=end
        )
        distinct_days = obs.values("observation_date").distinct().count()
        volume_missing = obs.filter(volume__isnull=True).count()
        report.append({
            "item_code": item.code,
            "item_name": item.name,
            "expected_days": expected,
            "observed_days": distinct_days,
            "missing_rate": round(1 - distinct_days / expected, 4) if expected else None,
            "row_count": obs.count(),
            "volume_missing": volume_missing,
        })
    return report


def weather_quality_report(start: date, end: date) -> list[dict]:
    """관측소별 기상 관측 커버리지/결측률."""
    from weather.models import WeatherStation, WeatherObservation  # 지연 import (앱 경계)

    expected = _expected_days(start, end)
    report = []
    for station in WeatherStation.objects.filter(is_active=True):
        obs = WeatherObservation.objects.filter(
            station=station, observed_date__gte=start, observed_date__lte=end
        )
        distinct_days = obs.values("observed_date").distinct().count()
        report.append({
            "station_id": station.station_id,
            "station_name": station.name,
            "expected_days": expected,
            "observed_days": distinct_days,
            "missing_rate": round(1 - distinct_days / expected, 4) if expected else None,
            "row_count": obs.count(),
        })
    return report


def full_report(start: date, end: date) -> dict:
    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "price": price_quality_report(start, end),
        "wholesale": wholesale_quality_report(start, end),
        "weather": weather_quality_report(start, end),
    }
