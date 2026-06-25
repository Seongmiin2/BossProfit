from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Max, Min, Sum
from django.db.models.functions import TruncMonth

from .models import (
    DailyMenuSale,
    IngredientMarketMapping,
    MarketRankingSnapshot,
    Menu,
    ProfitAssumption,
    RecipeItem,
)


FOOD_CATEGORIES = ("메뉴", "기타(대)")
MENU_IMAGE_KEYS = {
    "돈까스": "tonkatsu",
    "우동(보)": "udon",
    "어묵우동(보)": "fishcake-udon",
    "우동(매)": "spicy-udon",
    "튀김만두": "fried-dumplings",
    "1인세트 돈가스": "tonkatsu-set",
}


def resolve_menu_image_key(name):
    """메뉴명에서 사진 키를 결정. 정확히 일치하면 그 사진을, 아니면
    같은 종류(우동·돈까스·만두)의 대표 사진을 매칭한다."""
    if not name:
        return None
    exact = MENU_IMAGE_KEYS.get(name)
    if exact:
        return exact
    n = name.replace(" ", "")
    if "우동" in n:
        if "어묵" in n:
            return "fishcake-udon"
        if "매" in n:  # 매운 계열
            return "spicy-udon"
        return "udon"
    if ("돈까스" in n) or ("돈가스" in n) or ("카츠" in n):
        if ("세트" in n) or ("1인" in n) or ("2인" in n):
            return "tonkatsu-set"
        return "tonkatsu"
    if ("만두" in n) or ("튀만" in n) or ("찐만" in n):  # 튀만=튀김만두, 찐만=찐만두
        return "fried-dumplings"
    return None


def _percent(value):
    return float((value or Decimal("0")) * Decimal("100"))


def _sale_period(sales):
    values = sales.aggregate(
        start=Min("sale_date"),
        end=Max("sale_date"),
        record_days=Count("sale_date", distinct=True),
    )
    return {
        "from": values["start"].isoformat() if values["start"] else None,
        "to": values["end"].isoformat() if values["end"] else None,
        "record_days": values["record_days"],
        "missing_days_are_zero": False,
    }


def _menu_recipe_status(menu):
    recipe_items = list(
        RecipeItem.objects.filter(menu=menu).select_related("ingredient")
    )
    recipe_count = len(recipe_items)
    if recipe_count == 0:
        return {
            "status": "INSUFFICIENT",
            "reason": "레시피 데이터 없음",
            "recipe_count": 0,
            "mapped_ingredient_count": 0,
        }

    # 본사 납품 재료는 납품가가 고정이라 시장가격 변동 영향이 거의 없으므로
    # 시장 품목 연결이 필요 없다. 시장 연결 대상은 본사 납품이 아닌 재료뿐이다.
    market_ingredient_ids = {
        ri.ingredient_id
        for ri in recipe_items
        if not ri.ingredient.is_hq_supplied
    }

    if not market_ingredient_ids:
        # 모든 재료가 본사 납품 → 시장 연결 불필요, 분석 준비 완료
        return {
            "status": "READY",
            "reason": "본사 납품 재료로 구성되어 시장 연결이 필요 없습니다.",
            "recipe_count": recipe_count,
            "mapped_ingredient_count": 0,
            "hq_only": True,
        }

    mapped_ids = set(
        IngredientMarketMapping.objects.filter(
            ingredient_id__in=market_ingredient_ids,
            status="CONFIRMED",
        ).values_list("ingredient_id", flat=True)
    )
    unmapped = market_ingredient_ids - mapped_ids

    if unmapped:
        return {
            "status": "INSUFFICIENT",
            "reason": "시장 품목 연결 없음",
            "recipe_count": recipe_count,
            "mapped_ingredient_count": len(mapped_ids),
        }
    return {
        "status": "READY",
        "reason": None,
        "recipe_count": recipe_count,
        "mapped_ingredient_count": len(mapped_ids),
    }


def build_market_risk(as_of_date=None):
    snapshots = MarketRankingSnapshot.objects.filter(
        ranking_type="TOMORROW",
        is_demo=False,
    )
    if as_of_date:
        snapshots = snapshots.filter(as_of_date__lte=as_of_date)
    latest_date = snapshots.order_by("-as_of_date").values_list(
        "as_of_date",
        flat=True,
    ).first()
    if latest_date is None:
        return {
            "state": "EMPTY",
            "message": "실제 시장가격 예측이 아직 없습니다.",
            "action": {"label": "시장 전망 확인", "path": "/market"},
        }
    snapshot = (
        snapshots.filter(as_of_date=latest_date)
        .select_related("item")
        .order_by("rank")
        .first()
    )
    item = snapshot.item
    observation = item.observations.filter(
        observed_date__lte=latest_date,
        is_demo=False,
    ).order_by("-observed_date", "-collected_at").first()
    forecasts = {}
    for forecast in item.forecasts.filter(
        as_of_date__lte=latest_date,
        horizon_days__in=(7, 30),
        is_demo=False,
    ).order_by("horizon_days", "-as_of_date", "-created_at"):
        forecasts.setdefault(forecast.horizon_days, forecast)
    primary_forecast = forecasts.get(30) or forecasts.get(7)
    affected_menus = list(
        Menu.objects.filter(
            is_active=True,
            recipe_items__ingredient__market_mappings__market_item=item,
            recipe_items__ingredient__market_mappings__status="CONFIRMED",
        )
        .distinct()
        .values("menu_id", "name")[:5]
    )
    return {
        "state": "SUCCESS",
        "item": {
            "code": item.code,
            "name": item.name,
            "unit": item.unit,
            "image_key": item.image_key,
        },
        "current_price": float(observation.price) if observation else None,
        "current_price_date": (
            observation.observed_date.isoformat() if observation else None
        ),
        "forecasts": [
            {
                "horizon_days": horizon,
                "change_rate": _percent(forecasts[horizon].expected_change_rate),
                "predicted_price": float(forecasts[horizon].predicted_price),
                "lower_price": float(forecasts[horizon].lower_price),
                "upper_price": float(forecasts[horizon].upper_price),
                "confidence": forecasts[horizon].confidence_grade,
                "model_version": forecasts[horizon].model_version,
            }
            for horizon in (7, 30)
            if horizon in forecasts
        ],
        "headline_change_rate": (
            _percent(primary_forecast.expected_change_rate)
            if primary_forecast
            else _percent(snapshot.display_change_rate)
        ),
        "cause": "최근 실제 가격 흐름과 시계열 추세를 반영한 예측입니다.",
        "affected_menus": affected_menus,
        "impact_state": "READY" if affected_menus else "INSUFFICIENT",
        "impact_message": (
            None
            if affected_menus
            else f"{item.name}과 연결된 메뉴가 없습니다. 메뉴 재료 연결을 확인해주세요."
        ),
        "as_of_date": latest_date.isoformat(),
        "is_demo": False,
    }


def build_store_market_risks(store, as_of_date=None, limit=5):
    """Return only market risks connected to ingredients this store actually uses."""

    mapped_item_ids = IngredientMarketMapping.objects.filter(
        ingredient__store=store,
        ingredient__used_in__menu__store=store,
        ingredient__used_in__menu__is_active=True,
        status="CONFIRMED",
    ).values_list("market_item_id", flat=True).distinct()
    snapshots = MarketRankingSnapshot.objects.filter(
        ranking_type="TOMORROW",
        item_id__in=mapped_item_ids,
        is_demo=False,
    )
    if as_of_date:
        snapshots = snapshots.filter(as_of_date__lte=as_of_date)
    latest_date = snapshots.order_by("-as_of_date").values_list(
        "as_of_date",
        flat=True,
    ).first()
    if latest_date is None:
        mapped_count = IngredientMarketMapping.objects.filter(
            ingredient__store=store,
            ingredient__used_in__menu__store=store,
            ingredient__used_in__menu__is_active=True,
            status="CONFIRMED",
        ).values("market_item_id").distinct().count()
        return {
            "state": "INSUFFICIENT",
            "items": [],
            "connected_item_count": mapped_count,
            "message": (
                "내 가게 메뉴에 연결된 시장 품목이 없습니다."
                if mapped_count == 0
                else "연결된 재료의 실제 시장 예측이 아직 없습니다."
            ),
            "action": {
                "label": "판매 주력 메뉴부터 재료 연결",
                "path": "/ingredients",
            },
        }

    results = []
    ranked = snapshots.filter(as_of_date=latest_date).select_related(
        "item"
    ).order_by("-display_change_rate", "rank")[:limit]
    for store_rank, snapshot in enumerate(ranked, start=1):
        item = snapshot.item
        observation = item.observations.filter(
            observed_date__lte=latest_date,
            is_demo=False,
        ).order_by("-observed_date", "-collected_at").first()
        forecasts = {}
        for forecast in item.forecasts.filter(
            as_of_date__lte=latest_date,
            horizon_days__in=(7, 30),
            is_demo=False,
        ).order_by("horizon_days", "-as_of_date", "-created_at"):
            forecasts.setdefault(forecast.horizon_days, forecast)
        primary_forecast = forecasts.get(30) or forecasts.get(7)
        affected_menus = list(
            Menu.objects.filter(
                store=store,
                is_active=True,
                recipe_items__ingredient__market_mappings__market_item=item,
                recipe_items__ingredient__market_mappings__status="CONFIRMED",
            )
            .distinct()
            .values("menu_id", "name")[:5]
        )
        results.append({
            "rank": store_rank,
            "as_of_date": latest_date.isoformat(),
            "item": {
                "code": item.code,
                "name": item.name,
                "unit": item.unit,
                "image_key": item.image_key,
            },
            "current_price": float(observation.price) if observation else None,
            "current_price_date": (
                observation.observed_date.isoformat() if observation else None
            ),
            "headline_change_rate": (
                _percent(primary_forecast.expected_change_rate)
                if primary_forecast
                else _percent(snapshot.display_change_rate)
            ),
            "forecasts": [
                {
                    "horizon_days": horizon,
                    "change_rate": _percent(
                        forecasts[horizon].expected_change_rate
                    ),
                    "predicted_price": float(
                        forecasts[horizon].predicted_price
                    ),
                    "lower_price": float(forecasts[horizon].lower_price),
                    "upper_price": float(forecasts[horizon].upper_price),
                    "confidence": forecasts[horizon].confidence_grade,
                    "model_version": forecasts[horizon].model_version,
                }
                for horizon in (7, 30)
                if horizon in forecasts
            ],
            "affected_menus": affected_menus,
            "impact_state": "READY",
            "impact_message": (
                f"{', '.join(menu['name'] for menu in affected_menus)} 메뉴가 "
                f"{item.name} 가격 변화의 영향을 받을 수 있습니다."
            ),
            "cause": "실제 시장가격과 시계열 예측을 반영했습니다.",
        })
    return {
        "state": "SUCCESS",
        "items": results,
        "connected_item_count": len(results),
        "as_of_date": latest_date.isoformat(),
        "message": None,
    }


def build_store_analysis(store, date_from=None, date_to=None):
    all_sales = DailyMenuSale.objects.filter(store=store)
    available_period = _sale_period(all_sales)  # 선택 가능한 전체 데이터 범위

    sales = all_sales
    if date_from:
        sales = sales.filter(sale_date__gte=date_from)
    if date_to:
        sales = sales.filter(sale_date__lte=date_to)

    active_menus = Menu.objects.filter(store=store, is_active=True)
    food_sales = sales.filter(menu__category__in=FOOD_CATEGORIES)
    period = _sale_period(sales)

    overall = sales.aggregate(
        quantity=Sum("quantity"),
        gross_revenue=Sum("gross_revenue"),
        discount_amount=Sum("discount_amount"),
        net_revenue=Sum("net_revenue"),
    )
    food = food_sales.aggregate(
        quantity=Sum("quantity"),
        gross_revenue=Sum("gross_revenue"),
        discount_amount=Sum("discount_amount"),
        net_revenue=Sum("net_revenue"),
    )
    ranking_rows = list(
        food_sales.values(
            "menu_id",
            "menu__menu_id",
            "menu__name",
            "menu__category",
        )
        .annotate(
            quantity=Sum("quantity"),
            net_revenue=Sum("net_revenue"),
            discount_amount=Sum("discount_amount"),
            record_days=Count("sale_date", distinct=True),
        )
        .order_by("-quantity", "-net_revenue")
    )

    if period["to"]:
        period_end = Max("sale_date")
        latest_date = sales.aggregate(value=period_end)["value"]
    else:
        latest_date = None
    recent_start = latest_date - timedelta(days=29) if latest_date else None
    previous_start = latest_date - timedelta(days=59) if latest_date else None

    menus = []
    for index, row in enumerate(ranking_rows, start=1):
        menu = active_menus.get(id=row["menu_id"])
        recipe = _menu_recipe_status(menu)
        recent = (
            sales.filter(
                menu=menu,
                sale_date__gte=recent_start,
                sale_date__lte=latest_date,
            ).aggregate(
                quantity=Sum("quantity"),
                record_days=Count("sale_date", distinct=True),
            )
            if latest_date
            else {"quantity": None, "record_days": 0}
        )
        previous = (
            sales.filter(
                menu=menu,
                sale_date__gte=previous_start,
                sale_date__lt=recent_start,
            ).aggregate(
                quantity=Sum("quantity"),
                record_days=Count("sale_date", distinct=True),
            )
            if latest_date
            else {"quantity": None, "record_days": 0}
        )
        recent_quantity = recent["quantity"]
        previous_quantity = previous["quantity"]
        trend_rate = (
            ((recent_quantity - previous_quantity) / previous_quantity) * 100
            if recent_quantity is not None
            and previous_quantity not in (None, 0)
            else None
        )
        # 수익성(원가율·마진)은 레시피와 가격만 있으면 계산 가능하다.
        # 시장 품목 연결은 시장가격 위험 계산에만 필요하므로 분리한다.
        can_cost = recipe["recipe_count"] > 0 and (menu.price or 0) > 0
        if can_cost:
            food_cost = round(menu.food_cost())
            packaging = menu.packaging_cost or 0
            total_cost = food_cost + packaging
            margin_amount = menu.price - total_cost
            profitability = {
                "food_cost": food_cost,
                "packaging_cost": packaging,
                "total_cost": total_cost,
                "food_cost_rate": round(food_cost / menu.price, 4),
                "margin_amount": margin_amount,
                "margin_rate": round(margin_amount / menu.price, 4),
                "price": menu.price,
                "basis": "재료원가 기준 (인건비·임대료 등 고정비 제외)",
            }
        else:
            profitability = None

        # 판매량 상위 메뉴는 원가 준비 여부와 무관하게 '판매 주력'으로 유지한다.
        # (본사 납품 등으로 READY가 되어도 주력 판매 메뉴에서 빠지지 않도록)
        if index <= 5:
            state = "SALES_LEADER"
            state_label = "판매 주력"
            state_reason = f"음식 판매량 {index}위"
        elif recipe["status"] == "READY":
            state = "COST_DEFENSE"
            state_label = "원가 방어"
            state_reason = "레시피와 시장 품목 연결 완료"
        else:
            state = "ANALYSIS_PENDING"
            state_label = "분석 대기"
            state_reason = recipe["reason"]
        menus.append({
            "menu_id": row["menu__menu_id"],
            "name": row["menu__name"],
            "category": row["menu__category"],
            "image_key": resolve_menu_image_key(row["menu__name"]),
            "rank": index,
            "quantity": row["quantity"],
            "net_revenue": row["net_revenue"],
            "discount_amount": row["discount_amount"],
            "record_days": row["record_days"],
            "average_selling_price": (
                round(row["net_revenue"] / row["quantity"])
                if row["quantity"]
                else None
            ),
            "recent_30d_quantity": recent_quantity,
            "recent_30d_record_days": recent["record_days"],
            "previous_30d_quantity": previous_quantity,
            "previous_30d_record_days": previous["record_days"],
            "trend_rate": float(trend_rate) if trend_rate is not None else None,
            "state": state,
            "state_label": state_label,
            "state_reason": state_reason,
            "recipe": recipe,
            "profitability_state": (
                "AVAILABLE" if can_cost else "INSUFFICIENT"
            ),
            "profitability_message": (
                None
                if can_cost
                else "레시피 연결이 없어 수익성을 판단하지 않습니다."
            ),
            "profitability": profitability,
            "price_risk_state": (
                "AVAILABLE" if recipe["status"] == "READY" else "INSUFFICIENT"
            ),
        })

    monthly = list(
        food_sales.annotate(month=TruncMonth("sale_date"))
        .values("month")
        .annotate(
            quantity=Sum("quantity"),
            net_revenue=Sum("net_revenue"),
            record_days=Count("sale_date", distinct=True),
        )
        .order_by("month")
    )
    category_rows = list(
        sales.values("menu__category")
        .annotate(
            quantity=Sum("quantity"),
            net_revenue=Sum("net_revenue"),
        )
        .order_by("-quantity")
    )
    ready_count = sum(menu["recipe"]["status"] == "READY" for menu in menus)

    # 오늘 매출: 가장 최근 판매일의 실제 매출.
    today_revenue = (
        sales.filter(sale_date=latest_date).aggregate(rev=Sum("net_revenue"))["rev"]
        if latest_date
        else 0
    ) or 0
    # AI 예측 매출: 최근 30일 기록일의 일평균 매출(하루치 예상).
    recent_revenue = (
        sales.filter(
            sale_date__gte=recent_start,
            sale_date__lte=latest_date,
        ).aggregate(
            rev=Sum("net_revenue"),
            days=Count("sale_date", distinct=True),
        )
        if latest_date
        else {"rev": 0, "days": 0}
    )
    recent_days = recent_revenue["days"] or 0
    ai_forecast = (
        round((recent_revenue["rev"] or 0) / recent_days) if recent_days else 0
    )
    # 채널 분리(매장/배달) 데이터가 없으므로 매장 운영 가정 비중으로 예측을 분할한다.
    assumption = ProfitAssumption.get_active(store=store) if store else None
    delivery_share = assumption.delivery_share if assumption else 0.3
    store_share = max(0.0, 1.0 - delivery_share)  # 홀+포장
    today_estimate_block = {
        "total": today_revenue,
        "date": latest_date.isoformat() if latest_date else None,
        "ai_forecast": ai_forecast,
        "basis_days": recent_days,
        "dine_in": round(ai_forecast * store_share),
        "delivery": round(ai_forecast * delivery_share),
        "delivery_share": round(delivery_share, 2),
    }

    return {
        "state": "SUCCESS" if sales.exists() else "EMPTY",
        "store": {"id": store.id, "name": store.name, "region": store.region},
        "period": period,
        "available_period": available_period,
        "data_as_of": period["to"],
        "summary": {
            "product_count": active_menus.count(),
            "food_menu_count": active_menus.filter(
                category__in=FOOD_CATEGORIES
            ).count(),
            "liquor_count": active_menus.filter(category="주류").count(),
            "total_quantity": overall["quantity"] or 0,
            "total_net_revenue": overall["net_revenue"] or 0,
            "total_discount_amount": overall["discount_amount"] or 0,
            "food_quantity": food["quantity"] or 0,
            "food_net_revenue": food["net_revenue"] or 0,
            "top_food_menu": menus[0] if menus else None,
            "price_risk_ready_menu_count": ready_count,
            "today_estimate": today_estimate_block,
        },
        "menus": menus,
        "top_menus": menus[:5],
        "monthly_trend": [
            {
                "month": row["month"].isoformat(),
                "quantity": row["quantity"],
                "net_revenue": row["net_revenue"],
                "record_days": row["record_days"],
            }
            for row in monthly
        ],
        "category_share": [
            {
                "category": row["menu__category"],
                "quantity": row["quantity"],
                "net_revenue": row["net_revenue"],
            }
            for row in category_rows
        ],
        "limitations": [
            "판매 기록이 없는 날은 판매량 0으로 처리하지 않았습니다.",
            "판매량과 실매출은 판매성과이며 수익성을 의미하지 않습니다.",
            (
                "레시피와 시장 품목 연결이 없는 메뉴는 원가 위험과 "
                "수익성을 판단하지 않았습니다."
            ),
        ],
    }


def build_analysis_report(store):
    analysis = build_store_analysis(store)
    store_market_risks = build_store_market_risks(store)
    top = analysis["summary"]["top_food_menu"]
    summary = (
        f"{analysis['period']['from']}부터 {analysis['period']['to']}까지 "
        f"음식·사이드 {analysis['summary']['food_menu_count']}개에서 "
        f"{analysis['summary']['food_quantity']:,}개가 판매됐습니다."
    )
    if top:
        summary += (
            f" {top['name']}가 {top['quantity']:,}개로 음식 판매량 1위입니다."
        )
    used_llm = False
    findings = []
    for menu in analysis["top_menus"][:3]:
        findings.append({
            "title": f"{menu['name']}가 음식 판매량 {menu['rank']}위입니다.",
            "evidence": [
                {"label": "판매량", "value": menu["quantity"], "unit": "개"},
                {
                    "label": "실매출",
                    "value": menu["net_revenue"],
                    "unit": "원",
                },
                {
                    "label": "판매 기록일",
                    "value": menu["record_days"],
                    "unit": "일",
                },
            ],
            "interpretation": (
                "현재 매장의 핵심 판매 메뉴입니다. 원가와 고정비가 "
                "충분하지 않아 수익성 순위는 판단하지 않습니다."
            ),
            "confidence": "high",
            "limitations": [menu["profitability_message"]] if menu[
                "profitability_message"
            ] else [],
        })
    findings.append({
        "title": "가격위험 분석 연결이 필요합니다.",
        "evidence": [{
            "label": "분석 가능 메뉴",
            "value": analysis["summary"]["price_risk_ready_menu_count"],
            "unit": "개",
        }],
        "interpretation": (
            "시장가격은 확인할 수 있지만 레시피와 시장 품목 연결이 없는 "
            "메뉴의 원가 영향은 계산할 수 없습니다."
        ),
        "confidence": "high",
        "limitations": ["메뉴별 레시피·시장 품목 매핑 필요"],
    })
    report = {
        "state": analysis["state"],
        "summary": summary,
        "confidence": "medium",
        "data_period": {
            "from": analysis["period"]["from"],
            "to": analysis["period"]["to"],
        },
        "data_as_of": analysis["data_as_of"],
        "key_metrics": [
            {
                "label": "음식 메뉴 판매량",
                "value": analysis["summary"]["food_quantity"],
                "unit": "개",
            },
            {
                "label": "음식 메뉴 실매출",
                "value": analysis["summary"]["food_net_revenue"],
                "unit": "원",
            },
            {
                "label": "판매량 1위",
                "value": top["name"] if top else None,
                "unit": None,
            },
            {
                "label": "가격위험 분석 가능",
                "value": analysis["summary"]["price_risk_ready_menu_count"],
                "unit": "개",
            },
        ],
        "findings": findings,
        "market_risks": store_market_risks["items"],
        "recommended_actions": [
            {
                "period": "오늘",
                "title": "판매 주력 메뉴의 레시피 연결 상태 확인",
                "reason": "판매량 상위 메뉴부터 시장가격 영향을 계산하기 위해서입니다.",
                "data_used": ["최근 6개월 POS 판매량", "메뉴별 실매출"],
                "source_documents": [],
                "expected_effect": "원가 위험 분석 가능 메뉴 확대",
                "success_criteria": "상위 5개 메뉴의 레시피 연결 완료",
                "stop_criteria": "재료 단위 또는 구매단가를 확인할 수 없음",
                "review_date": None,
            },
            {
                "period": "이번 주",
                "title": "상승 전망 재료와 실제 구매단가 비교",
                "reason": "시장가격과 내 매장 구매가격의 차이를 확인하기 위해서입니다.",
                "data_used": ["KAMIS 가격", "1·7·30일 예측"],
                "source_documents": [],
                "expected_effect": "선매입 또는 관망 판단의 근거 확보",
                "success_criteria": "핵심 재료 구매단가 3개 이상 기록",
                "stop_criteria": "단위가 일치하지 않음",
                "review_date": None,
            },
        ],
        "sources": [],
        "source_state": {
            "state": "EMPTY",
            "message": "관련 근거 문서를 찾지 못했습니다.",
        },
        "sales_analysis": analysis,
        "limitations": analysis["limitations"],
        "used_llm": used_llm,
    }

    # LLM 요약 시도 (API 키 있을 때만)
    try:
        from .llm_service import generate_report_summary
        llm_text, ok = generate_report_summary(report)
        if ok and llm_text:
            report["summary"] = llm_text
            report["used_llm"] = True
    except Exception:
        pass

    return report
