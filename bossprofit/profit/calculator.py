"""
BOSSPROFIT 수익성 계산기 (DB 모델 버전)

bossprofit_calculator.py의 dataclass 기반 로직을 Django 모델로 이식.
함수는 두 종류:
  1. calculate_menu(menu, assumption): 단일 메뉴 계산 결과 dict 반환
  2. recalculate_all(assumption=None): 모든 활성 메뉴 재계산 + Snapshot 저장
"""
from typing import Optional

from django.db import transaction

from .models import Menu, ProfitAssumption, MenuProfitSnapshot


def calculate_menu(menu: Menu, assumption: ProfitAssumption) -> dict:
    """단일 메뉴의 수익성을 계산해 dict로 반환."""
    base_cost = menu.food_cost()
    price = menu.price

    food_cost_rate = (base_cost / price) if price else 0.0

    dine_in_margin = price - base_cost
    takeout_margin = price - base_cost - menu.packaging_cost

    delivery_commission = price * assumption.delivery_commission_rate
    rider_cost = assumption.rider_fee * assumption.rider_fee_store_share

    delivery_margin = (
        price
        - base_cost
        - menu.packaging_cost
        - delivery_commission
        - rider_cost
    )

    weighted_margin = (
        dine_in_margin * assumption.dine_in_share
        + delivery_margin * assumption.delivery_share
        + takeout_margin * assumption.takeout_share
    )

    monthly_profit = weighted_margin * menu.monthly_orders
    monthly_revenue = price * menu.monthly_orders

    return {
        "menu": menu,
        "base_cost": round(base_cost, 2),
        "food_cost_rate": round(food_cost_rate, 4),
        "dine_in_margin": round(dine_in_margin, 2),
        "takeout_margin": round(takeout_margin, 2),
        "delivery_commission": round(delivery_commission, 2),
        "rider_cost": round(rider_cost, 2),
        "delivery_margin": round(delivery_margin, 2),
        "weighted_margin": round(weighted_margin, 2),
        "monthly_profit": round(monthly_profit, 2),
        "monthly_revenue": round(monthly_revenue, 2),
    }


def classify(result: dict, average_orders: float, target_food_cost_rate: float) -> str:
    """신호등 분류. 학술 용어 대신 사장님 언어."""
    # 배달 마진이 마이너스면 무조건 빨강
    if result["delivery_margin"] < 0 and result["weighted_margin"] < 0:
        return "🔴 배달 손실"

    high_sales = result["menu"].monthly_orders >= average_orders
    low_cost = result["food_cost_rate"] <= target_food_cost_rate

    if high_sales and low_cost:
        return "🟢 간판 메뉴"
    if high_sales and not low_cost:
        return "🟡 손해 보는 베스트셀러"
    if not high_sales and low_cost:
        return "🟡 숨은 효자"
    return "🔴 정리 검토"


@transaction.atomic
def recalculate_all(assumption: Optional[ProfitAssumption] = None) -> list[MenuProfitSnapshot]:
    """모든 활성 메뉴를 재계산하고 Snapshot을 새로 저장.

    이전 스냅샷은 보존(시계열용). 호출하면 항상 새 행이 21개 생성됨.
    """
    if assumption is None:
        assumption = ProfitAssumption.get_active()

    menus = list(Menu.objects.filter(is_active=True).prefetch_related(
        "recipe_items__ingredient"
    ))

    # 1차 패스: 모든 메뉴의 raw 계산 결과
    results = [calculate_menu(m, assumption) for m in menus]

    # 평균 판매량 (분류 기준)
    total_orders = sum(m.monthly_orders for m in menus)
    avg_orders = (total_orders / len(menus)) if menus else 0

    # 2차 패스: 분류 + Snapshot 생성
    snapshots = []
    for result in results:
        signal = classify(result, avg_orders, assumption.target_food_cost_rate)
        snapshots.append(
            MenuProfitSnapshot.objects.create(
                menu=result["menu"],
                base_cost=result["base_cost"],
                food_cost_rate=result["food_cost_rate"],
                dine_in_margin=result["dine_in_margin"],
                takeout_margin=result["takeout_margin"],
                delivery_margin=result["delivery_margin"],
                weighted_margin=result["weighted_margin"],
                monthly_profit=result["monthly_profit"],
                monthly_revenue=result["monthly_revenue"],
                signal=signal,
            )
        )

    return snapshots


def get_latest_snapshots() -> list[MenuProfitSnapshot]:
    """각 메뉴별 가장 최근 Snapshot만 반환."""
    latest = []
    for menu in Menu.objects.filter(is_active=True).order_by("menu_id"):
        snap = menu.snapshots.first()  # ordering = ['-created_at']
        if snap:
            latest.append(snap)
    return latest


def dashboard_summary(snapshots: list[MenuProfitSnapshot]) -> dict:
    """대시보드 상단 요약 KPI."""
    if not snapshots:
        return {
            "total_revenue": 0,
            "total_profit": 0,
            "total_orders": 0,
            "avg_food_cost_rate": 0,
            "avg_orders": 0,
            "delivery_loss_count": 0,
        }

    total_revenue = sum(s.monthly_revenue for s in snapshots)
    total_profit = sum(s.monthly_profit for s in snapshots)
    total_orders = sum(s.menu.monthly_orders for s in snapshots)
    avg_food_cost_rate = (
        sum(s.food_cost_rate for s in snapshots) / len(snapshots)
    )
    avg_orders = total_orders / len(snapshots)
    delivery_loss_count = sum(1 for s in snapshots if s.delivery_margin < 0)

    return {
        "total_revenue": round(total_revenue),
        "total_profit": round(total_profit),
        "total_orders": total_orders,
        "avg_food_cost_rate": round(avg_food_cost_rate * 100, 1),
        "avg_orders": round(avg_orders, 1),
        "delivery_loss_count": delivery_loss_count,
    }
