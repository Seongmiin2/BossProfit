"""
BOSSPROFIT REST API Views
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models.deletion import ProtectedError
from django.db import transaction
from django.db.models import Sum, Avg
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import date, timedelta

from accounts.services import get_user_store
from accounts.onboarding import refresh_onboarding_progress
from .models import (
    Menu,
    Ingredient,
    DailyMenuSale,
    ProfitAssumption,
    MenuProfitSnapshot,
    MarketModelMetric,
    MarketRankingSnapshot,
    MarketRecommendation,
    ActionPlan,
)
from .analysis_service import (
    build_analysis_report,
    build_market_risk,
    build_store_market_risks,
    build_store_analysis,
    _percent,
)
from .calculator import (
    calculate_menu,
    dashboard_summary,
    get_latest_snapshots,
    recalculate_all,
)
from .views import _build_insights
from .serializers import (
    MenuProfitSnapshotSerializer,
    ProfitAssumptionSerializer,
    MenuWriteSerializer,
    IngredientWriteSerializer,
    IngredientSerializer,
    ProfitAssumptionWriteSerializer,
    DailyMenuSaleWriteSerializer,
)


def _recalculate_for_user(request):
    store = get_user_store(request.user)
    if store is None:
        return []
    assumption = ProfitAssumption.get_active(user=request.user, store=store)
    return recalculate_all(assumption=assumption, store=store)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_dashboard(request):
    """
    대시보드: KPI + 스냅샷 + 인사이트
    """
    user = request.user if request.user.is_authenticated else None
    store = get_user_store(user)
    snapshots = get_latest_snapshots(user=user, store=store)
    summary = dashboard_summary(snapshots)
    insights = _build_insights(snapshots)
    assumption = ProfitAssumption.get_active(
        user=user if store else None,
        store=store,
    )

    # 정렬: 신호 우선순위 + monthly_orders 내림차순
    signal_order = {
        "🟢 간판 메뉴": 1,
        "🟡 손해 보는 베스트셀러": 2,
        "🟡 숨은 효자": 3,
        "🔴 정리 검토": 4,
        "🔴 배달 손실": 5,
    }
    snapshots_sorted = sorted(
        snapshots,
        key=lambda s: (signal_order.get(s.signal, 99), -s.menu.monthly_orders),
    )

    return Response({
        "summary": summary,
        "snapshots": MenuProfitSnapshotSerializer(snapshots_sorted, many=True).data,
        "insights": insights,
        "assumption": ProfitAssumptionSerializer(assumption).data,
        "store_name": store.name if store else "BOSSPROFIT 데모 매장",
        "has_store": store is not None,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_menu_list(request):
    """
    메뉴 목록: 스냅샷 리스트
    """
    user = request.user if request.user.is_authenticated else None
    store = get_user_store(user)
    snapshots = get_latest_snapshots(user=user, store=store)
    return Response(MenuProfitSnapshotSerializer(snapshots, many=True).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_menu_detail(request, menu_id):
    """
    메뉴 상세: 마진 분해 + 레시피 분해
    """
    user = request.user if request.user.is_authenticated else None
    store = get_user_store(user)
    if user and store is None:
        return Response({"detail": "먼저 매장을 등록해주세요."}, status=409)
    menu = get_object_or_404(Menu, store=store, menu_id=menu_id)
    assumption = ProfitAssumption.get_active(user=user, store=store)
    result = calculate_menu(menu, assumption)
    recipe_items = menu.recipe_items.select_related("ingredient").all()

    # 재료별 원가 비중
    total_cost = sum(item.cost for item in recipe_items)
    recipe_rows = []
    for item in recipe_items:
        recipe_rows.append({
            "ingredient_id": item.ingredient.ingredient_id,
            "ingredient_name": item.ingredient.name,
            "quantity": item.quantity,
            "unit": item.ingredient.unit,
            "unit_cost": item.ingredient.unit_cost,
            "cost": item.cost,
            "share": (item.cost / total_cost * 100) if total_cost else 0,
            "memo": item.memo,
        })
    recipe_rows.sort(key=lambda r: r["cost"], reverse=True)

    # ORM 객체 제거
    result_data = {k: v for k, v in result.items() if k != "menu"}

    return Response({
        "menu": {
            "menu_id": menu.menu_id,
            "name": menu.name,
            "category": menu.category,
            "price": menu.price,
            "monthly_orders": menu.monthly_orders,
            "packaging_cost": menu.packaging_cost,
        },
        "result": result_data,
        "recipe_rows": recipe_rows,
        "assumption": ProfitAssumptionSerializer(assumption).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_recalculate(request):
    """
    전체 메뉴 재계산
    """
    snaps = _recalculate_for_user(request)
    return Response({
        "message": f"메뉴 {len(snaps)}개 재계산 완료",
        "count": len(snaps),
    })


# ===== Menu CRUD =====

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_menu_create(request):
    """메뉴 생성"""
    store = get_user_store(request.user)
    if store is None:
        return Response({"detail": "먼저 매장을 등록해주세요."}, status=409)
    serializer = MenuWriteSerializer(
        data=request.data,
        context={"store": store},
    )
    if serializer.is_valid():
        menu = serializer.save()
        refresh_onboarding_progress(store)
        _recalculate_for_user(request)
        return Response({"menu_id": menu.menu_id, "name": menu.name}, status=201)
    return Response(serializer.errors, status=400)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def api_menu_update(request, menu_id):
    """메뉴 수정"""
    store = get_user_store(request.user)
    if store is None:
        return Response({"detail": "먼저 매장을 등록해주세요."}, status=409)
    menu = get_object_or_404(Menu, store=store, menu_id=menu_id)
    serializer = MenuWriteSerializer(
        menu,
        data=request.data,
        partial=True,
        context={"store": store},
    )
    if serializer.is_valid():
        menu = serializer.save()
        refresh_onboarding_progress(store)
        _recalculate_for_user(request)
        return Response({"menu_id": menu.menu_id, "name": menu.name})
    return Response(serializer.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_menu_delete(request, menu_id):
    """메뉴 삭제"""
    store = get_user_store(request.user)
    if store is None:
        return Response({"detail": "먼저 매장을 등록해주세요."}, status=409)
    menu = get_object_or_404(Menu, store=store, menu_id=menu_id)
    menu_name = menu.name
    menu.delete()
    refresh_onboarding_progress(store)
    _recalculate_for_user(request)
    return Response({"message": f"메뉴 '{menu_name}' 삭제 완료"})


# ===== Ingredient CRUD =====

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_ingredient_list(request):
    """재료 목록"""
    user = request.user if request.user.is_authenticated else None
    store = get_user_store(user)
    ingredients = (
        Ingredient.objects.none()
        if user and store is None
        else Ingredient.objects.filter(store=store)
    )
    serializer = IngredientSerializer(ingredients, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_ingredient_create(request):
    """재료 생성"""
    store = get_user_store(request.user)
    if store is None:
        return Response({"detail": "먼저 매장을 등록해주세요."}, status=409)
    serializer = IngredientWriteSerializer(
        data=request.data,
        context={"store": store},
    )
    if serializer.is_valid():
        ingredient = serializer.save()
        refresh_onboarding_progress(store)
        _recalculate_for_user(request)
        return Response({"ingredient_id": ingredient.ingredient_id, "name": ingredient.name}, status=201)
    return Response(serializer.errors, status=400)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def api_ingredient_update(request, ingredient_id):
    """재료 수정"""
    store = get_user_store(request.user)
    if store is None:
        return Response({"detail": "먼저 매장을 등록해주세요."}, status=409)
    ingredient = get_object_or_404(
        Ingredient,
        store=store,
        ingredient_id=ingredient_id,
    )
    serializer = IngredientWriteSerializer(
        ingredient,
        data=request.data,
        partial=True,
        context={"store": store},
    )
    if serializer.is_valid():
        ingredient = serializer.save()
        _recalculate_for_user(request)
        return Response({"ingredient_id": ingredient.ingredient_id, "name": ingredient.name})
    return Response(serializer.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_ingredient_delete(request, ingredient_id):
    """재료 삭제"""
    store = get_user_store(request.user)
    if store is None:
        return Response({"detail": "먼저 매장을 등록해주세요."}, status=409)
    ingredient = get_object_or_404(
        Ingredient,
        store=store,
        ingredient_id=ingredient_id,
    )
    ingredient_name = ingredient.name
    try:
        ingredient.delete()
    except ProtectedError:
        return Response(
            {"detail": "레시피에서 사용 중인 재료는 삭제할 수 없습니다."},
            status=409,
        )
    _recalculate_for_user(request)
    refresh_onboarding_progress(store)
    return Response({"message": f"재료 '{ingredient_name}' 삭제 완료"})


# ===== Assumption CRUD =====

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def api_assumption_update(request):
    """가정 수정 (현재 활성 가정)"""
    store = get_user_store(request.user)
    if store is None:
        return Response({"detail": "먼저 매장을 등록해주세요."}, status=409)
    assumption = ProfitAssumption.get_active(user=request.user, store=store)
    serializer = ProfitAssumptionWriteSerializer(assumption, data=request.data, partial=True)
    if serializer.is_valid():
        assumption = serializer.save()
        snaps = recalculate_all(assumption=assumption, store=store)
        return Response({
            "label": assumption.label,
            "message": "가정 수정 및 재계산 완료",
            "count": len(snaps),
        })
    return Response(serializer.errors, status=400)


# ===== Daily Sales =====

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
def api_daily_sales_upsert(request):
    """일별 메뉴 판매량을 저장하고 최근 30일 판매량을 갱신한다."""
    store = get_user_store(request.user)
    if store is None:
        return Response({"detail": "먼저 매장을 등록해주세요."}, status=409)

    items = request.data if isinstance(request.data, list) else [request.data]
    serializer = DailyMenuSaleWriteSerializer(
        data=items,
        many=True,
        context={"store": store},
    )
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    saved = 0
    for item in serializer.validated_data:
        menu = Menu.objects.get(store=store, menu_id=item["menu_id"])
        DailyMenuSale.objects.update_or_create(
            store=store,
            menu=menu,
            sale_date=item["sale_date"],
            channel=item["channel"],
            defaults={"quantity": item["quantity"]},
        )
        saved += 1

    start_date = timezone.localdate() - timedelta(days=29)
    menus = Menu.objects.filter(store=store)
    for menu in menus:
        monthly_orders = (
            menu.daily_sales.filter(sale_date__gte=start_date)
            .aggregate(total=Sum("quantity"))["total"]
            or 0
        )
        if menu.monthly_orders != monthly_orders:
            menu.monthly_orders = monthly_orders
            menu.save(update_fields=["monthly_orders"])

    refresh_onboarding_progress(store)
    snaps = _recalculate_for_user(request)
    return Response({
        "message": "판매량 저장 및 수익 재계산 완료",
        "saved": saved,
        "snapshot_count": len(snaps),
    })


@api_view(["GET"])
@permission_classes([AllowAny])
def api_public_product_preview(request):
    return Response({
        "product_statement": (
            "어떤 재료의 가격이 오르고, 내 매장의 어떤 메뉴를 먼저 "
            "확인해야 하는지 알려주는 서비스"
        ),
        "market_risk": build_market_risk(),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_store_analysis(request):
    store = get_user_store(request.user)
    if store is None:
        return Response({"detail": "먼저 매장을 등록해주세요."}, status=409)

    def _parse_date(value):
        try:
            return date.fromisoformat(value) if value else None
        except ValueError:
            return None

    date_from = _parse_date(request.query_params.get("from"))
    date_to = _parse_date(request.query_params.get("to"))
    return Response({
        "analysis": build_store_analysis(store, date_from=date_from, date_to=date_to),
        "market_risks": build_store_market_risks(store),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def api_analysis_report(request):
    store = get_user_store(request.user)
    if store is None:
        return Response({"detail": "먼저 매장을 등록해주세요."}, status=409)
    return Response(build_analysis_report(store))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_action_plan_create(request):
    store = get_user_store(request.user)
    if store is None:
        return Response({"detail": "먼저 매장을 등록해주세요."}, status=409)
    required = ("title", "period", "reason")
    missing = [key for key in required if not request.data.get(key)]
    if missing:
        return Response(
            {"detail": f"필수 항목이 없습니다: {', '.join(missing)}"},
            status=400,
        )
    review_date = request.data.get("review_date")
    try:
        parsed_review_date = date.fromisoformat(review_date) if review_date else None
    except ValueError:
        return Response({"detail": "점검일 형식은 YYYY-MM-DD입니다."}, status=400)
    plan = ActionPlan.objects.create(
        store=store,
        created_by=request.user,
        title=request.data["title"],
        period_label=request.data["period"],
        reason=request.data["reason"],
        data_used=request.data.get("data_used", []),
        source_documents=request.data.get("source_documents", []),
        expected_effect=request.data.get("expected_effect", ""),
        success_criteria=request.data.get("success_criteria", ""),
        stop_criteria=request.data.get("stop_criteria", ""),
        review_date=parsed_review_date,
    )
    return Response({"id": plan.id, "status": plan.status}, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_analysis_follow_up(request):
    store = get_user_store(request.user)
    if store is None:
        return Response({"detail": "먼저 매장을 등록해주세요."}, status=409)
    question = str(request.data.get("question") or "").strip()
    if not question:
        return Response({"detail": "질문을 입력해주세요."}, status=400)

    report = build_analysis_report(store)

    # 1차: OpenAI LLM
    try:
        from .llm_service import build_store_context, call_openai_follow_up
        context = build_store_context(report)
        answer, engine = call_openai_follow_up(question, context)
    except (ValueError, ImportError):
        # API 키 미설정 또는 패키지 미설치 → 규칙 기반 폴백
        engine = "STRUCTURED_ANALYSIS"
        top = report["sales_analysis"]["summary"]["top_food_menu"]
        if "가장" in question or "먼저" in question:
            answer = (
                f"현재 먼저 확인할 메뉴는 {top['name']}입니다. 최근 분석기간 "
                f"판매량 {top['quantity']:,}개로 음식 메뉴 1위입니다. "
                "다만 레시피 연결 전에는 원가 위험이나 수익성을 판단할 수 없습니다."
                if top
                else "판매 데이터가 없어 우선 메뉴 판매자료를 연결해야 합니다."
            )
        else:
            answer = (
                "OPENAI_API_KEY가 설정되지 않아 규칙 기반 분석만 제공합니다. "
                ".env에 OPENAI_API_KEY를 추가하면 더 정확한 답변을 드릴 수 있습니다."
            )
    except Exception:
        engine = "STRUCTURED_ANALYSIS"
        answer = "AI 답변 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."

    return Response({
        "answer": answer,
        "engine": engine,
        "used_tools": [
            "get_store_sales_summary",
            "get_menu_sales_ranking",
            "get_market_forecast",
        ],
        "sources": [],
        "limitations": report["limitations"],
    })


# ===== History =====

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_history(request):
    """시계열 수익성 데이터"""
    # 쿼리 파라미터
    days = request.query_params.get('days', '30')
    menu_id = request.query_params.get('menu_id', None)

    try:
        days = int(days)
    except ValueError:
        days = 30
    days = min(max(days, 1), 365)

    # 기간 계산
    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=days - 1)

    # 쿼리셋
    snapshots = MenuProfitSnapshot.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )
    store = get_user_store(request.user)
    if request.user.is_authenticated and store is None:
        snapshots = snapshots.none()
    elif request.user.is_authenticated:
        snapshots = snapshots.filter(store=store)
    else:
        snapshots = snapshots.filter(store__isnull=True, owner__isnull=True)

    if menu_id:
        snapshots = snapshots.filter(menu__menu_id=menu_id)

    # 날짜별 그룹화
    daily_data = snapshots.annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        total_profit=Sum('monthly_profit'),
        total_revenue=Sum('monthly_revenue'),
        avg_food_cost_rate=Avg('food_cost_rate'),
    ).order_by('date')

    # 응답 포맷
    result = {
        'dates': [],
        'profit': [],
        'revenue': [],
        'cost_rate': [],
    }

    for item in daily_data:
        result['dates'].append(item['date'].isoformat())
        result['profit'].append(float(item['total_profit'] or 0))
        result['revenue'].append(float(item['total_revenue'] or 0))
        result['cost_rate'].append(float(item['avg_food_cost_rate'] or 0) * 100)

    return Response(result)


MARKET_RANKING_TYPES = {
    "volume": "VOLUME",
    "today": "TODAY",
    "tomorrow": "TOMORROW",
}


def _market_item_payload(snapshot):
    item = snapshot.item
    recommendation = item.recommendations.filter(
        as_of_date__lte=snapshot.as_of_date
    ).first()
    forecasts = {}
    for forecast in item.forecasts.filter(
        as_of_date__lte=snapshot.as_of_date,
        horizon_days__in=[1, 7, 30],
        is_demo=False,
    ).order_by("horizon_days", "-as_of_date", "-created_at"):
        forecasts.setdefault(forecast.horizon_days, forecast)
    observation_query = item.observations.filter(
        observed_date__lte=snapshot.as_of_date
    )
    if observation_query.filter(
        source="KAMIS_PERIOD",
        region_code="AVERAGE",
    ).exists():
        observation_query = observation_query.filter(
            source="KAMIS_PERIOD",
            region_code="AVERAGE",
        )
    observations = list(observation_query[:14])
    latest = observations[0] if observations else None

    # 일주일치 일별 예측 시계열 (그래프용): 최신 예측 실행의 +1~+7일 포인트
    forecast_run = item.forecast_runs.filter(
        as_of_date__lte=snapshot.as_of_date,
        status="SUCCEEDED",
    ).order_by("-as_of_date", "-created_at").first()
    forecast_series = []
    if forecast_run:
        for point in forecast_run.points.filter(
            horizon_days__lte=7
        ).order_by("horizon_days"):
            forecast_series.append({
                "date": point.target_date.isoformat(),
                "horizon_days": point.horizon_days,
                "median": float(point.median),
                "lower": float(point.lower),
                "upper": float(point.upper),
            })

    decision = recommendation.decision if recommendation else "WATCH"
    decision_labels = dict(MarketRecommendation.DECISION_CHOICES)
    tones = {"BUY": "buy", "WATCH": "watch", "AVOID": "avoid"}

    return {
        "code": item.code,
        "name": item.name,
        "category": item.category,
        "region": item.region,
        "unit": item.unit,
        "image_key": item.image_key,
        "rank": snapshot.rank,
        "previous_rank": snapshot.previous_rank,
        "rank_delta": (
            snapshot.previous_rank - snapshot.rank
            if snapshot.previous_rank is not None
            else None
        ),
        "score": float(snapshot.score),
        "change_rate": _percent(snapshot.display_change_rate),
        "current_price": float(latest.price) if latest else None,
        "decision": decision_labels.get(decision, "관망"),
        "decision_code": decision,
        "decision_tone": tones.get(decision, "watch"),
        "summary": recommendation.summary if recommendation else "분석 준비 중입니다.",
        "action": recommendation.action if recommendation else "데이터를 더 확인해주세요.",
        "evidence": recommendation.evidence if recommendation else [],
        "outlooks": [
            {
                "horizon_days": horizon,
                "change_rate": _percent(forecasts[horizon].expected_change_rate),
                "predicted_price": float(forecasts[horizon].predicted_price),
                "lower_price": float(forecasts[horizon].lower_price),
                "upper_price": float(forecasts[horizon].upper_price),
                "confidence_grade": forecasts[horizon].confidence_grade,
                "model_version": forecasts[horizon].model_version,
            }
            for horizon in [1, 7, 30]
            if horizon in forecasts
        ],
        "history": [
            {
                "date": observation.observed_date.isoformat(),
                "price": float(observation.price),
                "volume": (
                    float(observation.volume)
                    if observation.volume is not None
                    else None
                ),
            }
            for observation in reversed(observations)
        ],
        "forecast_series": forecast_series,
        "source": latest.source if latest else None,
        "is_demo": snapshot.is_demo,
    }


@api_view(["GET"])
@permission_classes([AllowAny])
def api_market_ranking(request, ranking_type):
    normalized_type = MARKET_RANKING_TYPES.get(ranking_type)
    if normalized_type is None:
        return Response({"detail": "지원하지 않는 랭킹 유형입니다."}, status=404)

    try:
        limit = min(max(int(request.query_params.get("limit", 5)), 1), 20)
    except ValueError:
        limit = 5
    query = request.query_params.get("q", "").strip()

    latest_date = (
        MarketRankingSnapshot.objects.filter(ranking_type=normalized_type)
        .order_by("-as_of_date")
        .values_list("as_of_date", flat=True)
        .first()
    )
    if latest_date is None:
        return Response({
            "ranking_type": ranking_type,
            "as_of_date": None,
            "generated_at": None,
            "items": [],
            "metrics": {"is_verified": False},
            "is_demo": False,
        })

    snapshots = MarketRankingSnapshot.objects.filter(
        ranking_type=normalized_type,
        as_of_date=latest_date,
    ).select_related("item")
    if query:
        snapshots = snapshots.filter(item__name__icontains=query)
    snapshots = list(snapshots.order_by("rank")[:limit])

    metric = MarketModelMetric.objects.filter(
        is_verified=True,
        item__isnull=True,
        horizon_days=1,
    ).order_by("-evaluation_end").first()
    item_metrics = list(
        MarketModelMetric.objects.filter(
            is_verified=True,
            item_id__in=[snapshot.item_id for snapshot in snapshots],
            horizon_days=1,
        ).order_by("-evaluation_end")
    )
    if metric is None and item_metrics:
        metric_payload = {
            "is_verified": True,
            "direction_accuracy": sum(
                float(value.direction_accuracy)
                for value in item_metrics
                if value.direction_accuracy is not None
            ) / len(item_metrics),
            "wape": sum(
                float(value.wape)
                for value in item_metrics
                if value.wape is not None
            ) / len(item_metrics),
            "interval_coverage": sum(
                float(value.interval_coverage)
                for value in item_metrics
                if value.interval_coverage is not None
            ) / len(item_metrics),
            "model_version": item_metrics[0].model_version,
            "evaluation_start": min(
                value.evaluation_start for value in item_metrics
            ).isoformat(),
            "evaluation_end": max(
                value.evaluation_end for value in item_metrics
            ).isoformat(),
        }
    else:
        metric_payload = {
            "is_verified": bool(metric),
            "direction_accuracy": (
                float(metric.direction_accuracy)
                if metric and metric.direction_accuracy is not None
                else None
            ),
            "wape": float(metric.wape) if metric and metric.wape is not None else None,
            "interval_coverage": (
                float(metric.interval_coverage)
                if metric and metric.interval_coverage is not None
                else None
            ),
            "model_version": metric.model_version if metric else None,
            "evaluation_start": (
                metric.evaluation_start.isoformat()
                if metric and metric.evaluation_start
                else None
            ),
            "evaluation_end": (
                metric.evaluation_end.isoformat()
                if metric and metric.evaluation_end
                else None
            ),
        }
    generated_at = snapshots[0].generated_at if snapshots else None

    return Response({
        "ranking_type": ranking_type,
        "as_of_date": latest_date.isoformat(),
        "generated_at": generated_at.isoformat() if generated_at else None,
        "items": [_market_item_payload(snapshot) for snapshot in snapshots],
        "metrics": metric_payload,
        "is_demo": any(snapshot.is_demo for snapshot in snapshots),
    })
