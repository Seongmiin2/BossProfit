"""
BOSSPROFIT REST API Views
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models.deletion import ProtectedError
from django.db import transaction
from django.db.models import Sum, Avg
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta

from accounts.services import get_user_store
from accounts.onboarding import refresh_onboarding_progress
from .models import (
    Menu,
    Ingredient,
    DailyMenuSale,
    ProfitAssumption,
    MenuProfitSnapshot,
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
