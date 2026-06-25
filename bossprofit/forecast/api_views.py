"""예측 REST API (가격 예측 파이프라인 노출).

forecast 파이프라인이 만든 ForecastRun/Point/Component를 프론트가 소비할 수 있게 노출한다.
시장 가격 예측은 매장에 종속되지 않는 공용 데이터이므로 store 스코핑은 하지 않고
인증만 요구한다(LLM '자영업 119'가 SQL로 끌어다 쓰는 선행 데이터).
"""
from __future__ import annotations

from datetime import timedelta

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from market.models import MarketItem, MarketPriceObservation
from profit.models import Ingredient
from profit.scoping import get_active_store
from .data import load_price_series
from .models import ForecastRun
from .serving import forecast_response_all


def _latest_run(item):
    return (
        ForecastRun.objects.filter(item=item, status="success")
        .order_by("-as_of", "-created_at")
        .first()
    )


def _latest_market_price(item):
    """품목의 가장 최근 시세(KAMIS) 관측가. load_price_series 기본 필터와 동일."""
    obs = (
        MarketPriceObservation.objects.filter(
            item=item, market_type="retail", region="", source="kamis"
        )
        .order_by("-observation_date")
        .first()
    )
    return round(float(obs.price), 2) if obs else None


def _store_required(request):
    store = get_active_store(request.user)
    if store is None:
        return None, Response(
            {"code": "STORE_REQUIRED", "message": "매장이 아직 준비되지 않았습니다."},
            status=412,
        )
    return store, None


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_forecast_items(request):
    """예측이 1건 이상 생성된 실 시장품목 목록(합성 재료품목 ING-* 제외)."""
    item_ids = (
        ForecastRun.objects.filter(status="success")
        .values_list("item_id", flat=True)
        .distinct()
    )
    items = (
        MarketItem.objects.filter(id__in=list(item_ids))
        .exclude(source="manual")  # 매장 재료별 합성 품목(ING-*) 제외
        .order_by("name")
    )
    return Response(
        [
            {
                "code": it.code,
                "name": it.name,
                "category": it.category,
                "unit": it.standard_unit,
            }
            for it in items
        ]
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_forecast_ingredients(request):
    """현재 매장의 재료별 가격 예측 요약(목록).

    각 재료의 현재 단가와 연동 시장품목의 최신 예측(horizon별 중앙값·구간·신뢰등급·변화율)을
    함께 돌려준다. 예측이 없는 재료는 points=[] / as_of=null.
    """
    store, err = _store_required(request)
    if err:
        return err

    # 본사 발주(고정가) 재료는 시세 변동이 없어 예측표에서 제외한다.
    ingredients = (
        Ingredient.objects.filter(store=store)
        .exclude(is_supplied=True)
        .select_related("market_item")
        .order_by("category", "name")
    )

    out = []
    for ing in ingredients:
        cur = round(ing.unit_cost, 4)
        row = {
            "ingredient_id": ing.ingredient_id,
            "name": ing.name,
            "category": ing.category,
            "unit": ing.unit,
            "supply_unit_cost": cur,           # 내가 구입한 공급단가(원/단위)
            "market_price": None,              # KAMIS 시세 상의 현재 단가
            "is_supplied": ing.is_supplied,
            "market_code": ing.market_item.code if ing.market_item_id else None,
            "as_of": None,
            "points": [],
        }
        # 본사 발주 재료(고정가)는 시세 변동이 없어 예측에서 제외한다.
        if not ing.is_supplied and ing.market_item_id:
            row["market_price"] = _latest_market_price(ing.market_item)
        run = None if ing.is_supplied else (_latest_run(ing.market_item) if ing.market_item_id else None)
        if run is not None:
            row["as_of"] = run.as_of.isoformat()
            # 변화율 기준은 현재 시세(market_price), 없으면 공급단가로 폴백
            base = row["market_price"] or cur
            for p in forecast_response_all(run):
                if p is None:
                    continue
                median = float(p["median"])
                row["points"].append({
                    "horizon_days": p["horizon_days"],
                    "target_date": p["target_date"],
                    "median": p["median"],
                    "lower_80": p["lower_80"],
                    "upper_80": p["upper_80"],
                    "confidence": p["confidence"],
                    "delta_rate": round((median - base) / base * 100, 1) if base else None,
                })
        out.append(row)

    return Response({"store": store.name, "ingredients": out})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_forecast_detail(request, item_code: str):
    """품목의 최신 예측 + 차트용 실제가격 히스토리.

    응답:
      item        : 품목 메타
      as_of       : 예측 기준일
      model_version, points[]  : 백엔드 계약 응답(horizon별 base/weather/residual/구간/신뢰등급)
      history     : 최근 실제가격 시계열(차트 컨텍스트)
    """
    item = MarketItem.objects.filter(code=item_code).first()
    if item is None:
        return Response({"code": "ITEM_NOT_FOUND", "message": f"품목 {item_code} 없음"}, status=404)

    run = (
        ForecastRun.objects.filter(item=item, status="success")
        .order_by("-as_of", "-created_at")
        .first()
    )
    if run is None:
        return Response(
            {"code": "FORECAST_NOT_FOUND", "message": f"{item.name} 예측이 아직 없습니다."},
            status=404,
        )

    points = [p for p in forecast_response_all(run) if p is not None]

    # 차트 컨텍스트: as_of 기준 직전 N일 실제가격
    history_days = int(request.query_params.get("history_days", 90))
    start = run.as_of - timedelta(days=history_days)
    series = load_price_series(item, start=start, end=run.as_of)
    history = {
        "dates": [d.date().isoformat() for d in series.index],
        "prices": [round(float(v), 2) for v in series.values],
    }

    return Response(
        {
            "item": {
                "code": item.code,
                "name": item.name,
                "category": item.category,
                "unit": item.standard_unit,
            },
            "as_of": run.as_of.isoformat(),
            "model_version": run.model_versions,
            "points": points,
            "history": history,
        }
    )
