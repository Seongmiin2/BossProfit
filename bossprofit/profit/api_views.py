"""
BOSSPROFIT REST API Views
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Avg
from django.db.models.functions import TruncDate
from datetime import datetime, timedelta

from .models import Menu, Ingredient, ProfitAssumption, MenuProfitSnapshot
from .calculator import (
    calculate_menu,
    dashboard_summary,
    get_latest_snapshots,
    recalculate_all,
)
from .views import _bucket_by_signal, _build_insights
from .serializers import (
    MenuProfitSnapshotSerializer,
    ProfitAssumptionSerializer,
    MenuWriteSerializer,
    IngredientWriteSerializer,
    IngredientSerializer,
    ProfitAssumptionWriteSerializer,
)


@api_view(['GET'])
def api_dashboard(request):
    """
    대시보드: KPI + 스냅샷 + 인사이트
    """
    snapshots = get_latest_snapshots()
    summary = dashboard_summary(snapshots)
    insights = _build_insights(snapshots)
    user = request.user if request.user.is_authenticated else None
    assumption = ProfitAssumption.get_active(user=user)

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
        "store_name": "우동·돈까스 매장",
    })


@api_view(['GET'])
def api_menu_list(request):
    """
    메뉴 목록: 스냅샷 리스트
    """
    snapshots = get_latest_snapshots()
    return Response(MenuProfitSnapshotSerializer(snapshots, many=True).data)


@api_view(['GET'])
def api_menu_detail(request, menu_id):
    """
    메뉴 상세: 마진 분해 + 레시피 분해
    """
    menu = get_object_or_404(Menu, menu_id=menu_id)
    user = request.user if request.user.is_authenticated else None
    assumption = ProfitAssumption.get_active(user=user)
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
def api_recalculate(request):
    """
    전체 메뉴 재계산
    """
    snaps = recalculate_all()
    return Response({
        "message": f"메뉴 {len(snaps)}개 재계산 완료",
        "count": len(snaps),
    })


# ===== Menu CRUD =====

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_menu_create(request):
    """메뉴 생성"""
    serializer = MenuWriteSerializer(data=request.data)
    if serializer.is_valid():
        menu = serializer.save()
        return Response({"menu_id": menu.menu_id, "name": menu.name}, status=201)
    return Response(serializer.errors, status=400)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def api_menu_update(request, menu_id):
    """메뉴 수정"""
    menu = get_object_or_404(Menu, menu_id=menu_id)
    serializer = MenuWriteSerializer(menu, data=request.data, partial=True)
    if serializer.is_valid():
        menu = serializer.save()
        return Response({"menu_id": menu.menu_id, "name": menu.name})
    return Response(serializer.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_menu_delete(request, menu_id):
    """메뉴 삭제"""
    menu = get_object_or_404(Menu, menu_id=menu_id)
    menu.delete()
    return Response({"message": f"메뉴 '{menu.name}' 삭제 완료"})


# ===== Ingredient CRUD =====

@api_view(['GET'])
def api_ingredient_list(request):
    """재료 목록"""
    ingredients = Ingredient.objects.all()
    serializer = IngredientSerializer(ingredients, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_ingredient_create(request):
    """재료 생성"""
    serializer = IngredientWriteSerializer(data=request.data)
    if serializer.is_valid():
        ingredient = serializer.save()
        return Response({"ingredient_id": ingredient.ingredient_id, "name": ingredient.name}, status=201)
    return Response(serializer.errors, status=400)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def api_ingredient_update(request, ingredient_id):
    """재료 수정"""
    ingredient = get_object_or_404(Ingredient, ingredient_id=ingredient_id)
    serializer = IngredientWriteSerializer(ingredient, data=request.data, partial=True)
    if serializer.is_valid():
        ingredient = serializer.save()
        return Response({"ingredient_id": ingredient.ingredient_id, "name": ingredient.name})
    return Response(serializer.errors, status=400)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def api_ingredient_delete(request, ingredient_id):
    """재료 삭제"""
    ingredient = get_object_or_404(Ingredient, ingredient_id=ingredient_id)
    ingredient.delete()
    return Response({"message": f"재료 '{ingredient.name}' 삭제 완료"})


# ===== Assumption CRUD =====

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def api_assumption_update(request):
    """가정 수정 (현재 활성 가정)"""
    assumption = ProfitAssumption.get_active(user=request.user)
    serializer = ProfitAssumptionWriteSerializer(assumption, data=request.data, partial=True)
    if serializer.is_valid():
        assumption = serializer.save()
        return Response({"label": assumption.label, "message": "가정 수정 완료"})
    return Response(serializer.errors, status=400)


# ===== History =====

@api_view(['GET'])
def api_history(request):
    """시계열 수익성 데이터"""
    # 쿼리 파라미터
    days = request.query_params.get('days', '30')
    menu_id = request.query_params.get('menu_id', None)

    try:
        days = int(days)
    except ValueError:
        days = 30

    # 기간 계산
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)

    # 쿼리셋
    snapshots = MenuProfitSnapshot.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date
    )

    if menu_id:
        snapshots = snapshots.filter(menu__menu_id=menu_id)

    # 날짜별 그룹화
    daily_data = snapshots.annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        total_profit=Sum('monthly_profit'),
        total_revenue=Sum('monthly_revenue'),
        avg_food_cost_rate=Avg('food_cost_rate'),
        menu_count=Sum('menu_id')  # 개수 세기 위한 더미
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
