"""
BOSSPROFIT 뷰

URL 구성:
  /                  → dashboard (preview 이미지와 동일한 화면)
  /menus/            → 메뉴 전체 리스트
  /menus/<menu_id>/  → 메뉴 1개 상세 (레시피, 마진 분해)
  /recalculate/      → POST로 재계산 트리거
"""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_POST

from .calculator import (
    calculate_menu,
    dashboard_summary,
    get_latest_snapshots,
    recalculate_all,
)
from .models import Menu, ProfitAssumption, RecipeItem


def _bucket_by_signal(snapshots):
    """신호별로 그룹핑."""
    groups = {
        "🟢 간판 메뉴": [],
        "🟡 손해 보는 베스트셀러": [],
        "🟡 숨은 효자": [],
        "🔴 정리 검토": [],
        "🔴 배달 손실": [],
    }
    for s in snapshots:
        groups.setdefault(s.signal, []).append(s)
    return groups


def _build_insights(snapshots):
    """Top 핵심 인사이트 자동 생성.

    preview의 4개 인사이트는 사람이 손으로 쓴 것이지만, MVP에서는
    데이터로 자동 추출 가능한 4가지만 추려서 보여줌.
    """
    if not snapshots:
        return []

    insights = []

    # 1. 가장 많이 팔리는 메뉴
    top_seller = max(snapshots, key=lambda s: s.menu.monthly_orders)
    insights.append({
        "label": f"{top_seller.menu.name} 월판매량",
        "value": f"{top_seller.menu.monthly_orders}건",
        "comment": f"현재 매장의 핵심 메뉴. 원가율 {top_seller.food_cost_rate*100:.1f}%, 원가 관리 1순위",
    })

    # 2. 배달 손실 메뉴 중 최악
    delivery_losers = [s for s in snapshots if s.delivery_margin < 0]
    if delivery_losers:
        worst = min(delivery_losers, key=lambda s: s.delivery_margin)
        insights.append({
            "label": f"{worst.menu.name} 배달 1건 손실",
            "value": f"{abs(worst.delivery_margin):,.0f}원",
            "comment": "배달 기사 수수료 부담으로 단품 배달 시 적자. 묶음 판매 또는 최소 주문 정책 필요",
        })

    # 3. 가장 수익이 큰 메뉴
    top_profit = max(snapshots, key=lambda s: s.monthly_profit)
    insights.append({
        "label": f"{top_profit.menu.name} 월 예상 이익",
        "value": f"{top_profit.monthly_profit:,.0f}원",
        "comment": f"가중 마진 {top_profit.weighted_margin:,.0f}원 × {top_profit.menu.monthly_orders}건",
    })

    # 4. 정리 검토 대상이 가장 많은 카테고리
    review = [s for s in snapshots if "정리" in s.signal]
    if review:
        from collections import Counter
        cat = Counter(s.menu.category for s in review).most_common(1)[0]
        insights.append({
            "label": f"{cat[0]} 카테고리 정리 검토",
            "value": f"{cat[1]}개 메뉴",
            "comment": "원가율이 목표(35%)를 초과하거나 판매량이 평균 미만. 가격·레시피 재검토 필요",
        })

    return insights


@staff_member_required
def dashboard(request):
    """1주차 핵심 화면."""
    snapshots = get_latest_snapshots()
    summary = dashboard_summary(snapshots)
    groups = _bucket_by_signal(snapshots)
    insights = _build_insights(snapshots)
    assumption = ProfitAssumption.get_active()

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

    context = {
        "summary": summary,
        "snapshots": snapshots_sorted,
        "groups": groups,
        "insights": insights,
        "assumption": assumption,
        "store_name": "우동·돈까스 매장",
    }
    return render(request, "profit/dashboard.html", context)


@staff_member_required
def menu_list(request):
    snapshots = get_latest_snapshots()
    return render(
        request,
        "profit/menu_list.html",
        {"snapshots": snapshots},
    )


@staff_member_required
def menu_detail(request, menu_id):
    menu = get_object_or_404(Menu, menu_id=menu_id)
    assumption = ProfitAssumption.get_active()
    result = calculate_menu(menu, assumption)
    recipe_items = menu.recipe_items.select_related("ingredient").all()

    # 재료별 원가 비중
    total_cost = sum(item.cost for item in recipe_items)
    recipe_rows = []
    for item in recipe_items:
        recipe_rows.append({
            "ingredient": item.ingredient,
            "quantity": item.quantity,
            "cost": item.cost,
            "share": (item.cost / total_cost * 100) if total_cost else 0,
        })
    recipe_rows.sort(key=lambda r: r["cost"], reverse=True)

    return render(
        request,
        "profit/menu_detail.html",
        {
            "menu": menu,
            "result": result,
            "recipe_rows": recipe_rows,
            "assumption": assumption,
        },
    )


@require_POST
@staff_member_required
def recalculate(request):
    snaps = recalculate_all()
    messages.success(request, f"✓ 메뉴 {len(snaps)}개 재계산 완료")
    return HttpResponseRedirect(reverse("dashboard"))
