"""예측 영속화 + 백엔드 계약 응답 (항목 13).

백엔드↔ML 계약(통합 보고서 11.4 / 개발기획서 9)을 그대로 만족하는 응답을 만든다:
base_prediction + weather_adjustment + residual_adjustment = median, 구간·신뢰등급·모델버전 포함.
숫자는 문자열 Decimal로 전달한다(부동소수 오차 방지).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.db import transaction

from .models import (
    ModelRegistry, ForecastRun, ForecastPoint, ForecastComponent,
)


def register_model(model_version: str, stage: str, **kwargs) -> ModelRegistry:
    obj, _ = ModelRegistry.objects.update_or_create(
        model_version=model_version, defaults={"stage": stage, **kwargs}
    )
    return obj


@transaction.atomic
def persist_forecast(
    item,
    as_of,
    points: list[dict],
    model_versions: dict,
    data_quality: Optional[list] = None,
    weather_forecast_issued_at=None,
) -> ForecastRun:
    """ForecastRun + Point + Component 를 멱등 저장.

    points[i] 키: horizon, target_date, base, weather_delta, residual_delta,
                  median, lower_80, upper_80, [lower_95, upper_95],
                  confidence, weather_disabled, residual_disabled
    """
    run, _ = ForecastRun.objects.update_or_create(
        item=item, as_of=as_of,
        defaults={
            "model_versions": model_versions,
            "data_quality": data_quality or [],
            "weather_forecast_issued_at": weather_forecast_issued_at,
            "status": "success",
        },
    )
    run.points.all().delete()  # 같은 as_of 재생성 시 교체
    for p in points:
        point = ForecastPoint.objects.create(
            run=run, horizon=p["horizon"], target_date=p["target_date"],
            median=p["median"], lower_80=p["lower_80"], upper_80=p["upper_80"],
            lower_95=p.get("lower_95"), upper_95=p.get("upper_95"),
            confidence=p.get("confidence", "MEDIUM"),
        )
        ForecastComponent.objects.create(
            point=point, base=p["base"],
            weather_delta=p.get("weather_delta", 0),
            residual_delta=p.get("residual_delta", 0),
            weather_disabled=p.get("weather_disabled", False),
            residual_disabled=p.get("residual_disabled", False),
        )
    return run


def _s(value) -> Optional[str]:
    if value is None:
        return None
    return str(Decimal(value).quantize(Decimal("0.01")))


def forecast_response(run: ForecastRun, horizon: int) -> Optional[dict]:
    """단일 horizon의 백엔드 계약 응답(통합 보고서 11.4)."""
    point = run.points.filter(horizon=horizon).select_related("component").first()
    if point is None:
        return None
    c = point.component
    return {
        "target_type": run.target_type,
        "target_id": run.item.code,
        "as_of": run.as_of.isoformat(),
        "horizon_days": point.horizon,
        "target_date": point.target_date.isoformat(),
        "base_prediction": _s(c.base),
        "weather_adjustment": _s(c.weather_delta),
        "residual_adjustment": _s(c.residual_delta),
        "median": _s(point.median),
        "lower_80": _s(point.lower_80),
        "upper_80": _s(point.upper_80),
        "lower_95": _s(point.lower_95),
        "upper_95": _s(point.upper_95),
        "confidence": point.confidence,
        "weather_forecast_issued_at": (
            run.weather_forecast_issued_at.isoformat()
            if run.weather_forecast_issued_at else None
        ),
        "model_version": run.model_versions,
        "data_quality": run.data_quality,
        "stage_flags": {
            "weather_disabled": c.weather_disabled,
            "residual_disabled": c.residual_disabled,
        },
    }


def forecast_response_all(run: ForecastRun) -> list[dict]:
    return [forecast_response(run, p.horizon) for p in run.points.all()]
