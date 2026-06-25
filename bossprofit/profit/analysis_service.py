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
    recipe_count = RecipeItem.objects.filter(menu=menu).count()
    mapped_count = IngredientMarketMapping.objects.filter(
        ingredient__used_in__menu=menu,
        status="CONFIRMED",
    ).distinct().count()
    if recipe_count == 0:
        return {
            "status": "INSUFFICIENT",
            "reason": "레시피 데이터 없음",
            "recipe_count": 0,
            "mapped_ingredient_count": 0,
        }
    if mapped_count == 0:
        return {
            "status": "INSUFFICIENT",
            "reason": "시장 품목 연결 없음",
            "recipe_count": recipe_count,
            "mapped_ingredient_count": 0,
        }
    return {
        "status": "READY",
        "reason": None,
        "recipe_count": recipe_count,
        "mapped_ingredient_count": mapped_count,
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


def build_store_analysis(store):
    sales = DailyMenuSale.objects.filter(store=store)
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
        if recipe["status"] == "READY":
            state = "COST_DEFENSE"
            state_label = "원가 방어"
            state_reason = "레시피와 시장 품목 연결 완료"
        elif index <= 5:
            state = "SALES_LEADER"
            state_label = "판매 주력"
            state_reason = f"음식 판매량 {index}위"
        else:
            state = "ANALYSIS_PENDING"
            state_label = "분석 대기"
            state_reason = recipe["reason"]
        menus.append({
            "menu_id": row["menu__menu_id"],
            "name": row["menu__name"],
            "category": row["menu__category"],
            "image_key": MENU_IMAGE_KEYS.get(row["menu__name"]),
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
                "AVAILABLE"
                if recipe["status"] == "READY"
                else "INSUFFICIENT"
            ),
            "profitability_message": (
                None
                if recipe["status"] == "READY"
                else "원가 또는 레시피 연결이 없어 수익성을 판단하지 않습니다."
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

    return {
        "state": "SUCCESS" if sales.exists() else "EMPTY",
        "store": {"id": store.id, "name": store.name, "region": store.region},
        "period": period,
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
    market_risk = build_market_risk()
    top = analysis["summary"]["top_food_menu"]
    summary = (
        f"{analysis['period']['from']}부터 {analysis['period']['to']}까지 "
        f"음식·사이드 {analysis['summary']['food_menu_count']}개에서 "
        f"{analysis['summary']['food_quantity']:,}개가 판매됐습니다."
    )
    if top:
        summary += (
            f" {top['name']}가 {top['quantity']:,}개로 음식 판매량 1위입니다."
            " 이는 판매성과이며 수익성 1위를 의미하지 않습니다."
        )
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
    return {
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
        "market_risks": [market_risk] if market_risk["state"] == "SUCCESS" else [],
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
        "limitations": analysis["limitations"] + [
            "현재 리포트 설명은 SQL 집계와 규칙 기반 해석이며 외부 LLM이 아닙니다.",
            "RAG 문서가 없어 문서 근거를 생성하지 않았습니다.",
        ],
    }
