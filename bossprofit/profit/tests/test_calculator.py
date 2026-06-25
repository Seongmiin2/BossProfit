"""
수익성 계산 로직(calculator.py) 단위 테스트.

검증 대상:
- calculate_menu: 마진/원가율 산식
- classify: 신호등 분류 규칙
- recalculate_all: 활성 메뉴당 스냅샷 생성
- get_latest_snapshots: 메뉴별 최신 스냅샷 반환
- dashboard_summary: KPI 집계
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from profit.models import Store, Ingredient, Menu, RecipeItem, ProfitAssumption, MenuProfitSnapshot
from profit.calculator import (
    calculate_menu,
    classify,
    recalculate_all,
    get_latest_snapshots,
    dashboard_summary,
)

User = get_user_model()


class CalculateMenuTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner_a", password="pw12345!")
        self.store = Store.objects.create(owner=self.owner, name="매장A")
        # unit_cost = 1000 / 1000 = 1.0 원/g
        self.ingredient = Ingredient.objects.create(
            store=self.store,
            ingredient_id="ING_A", name="재료A",
            purchase_quantity=1000, purchase_price=1000, unit="g",
        )
        self.menu = Menu.objects.create(
            store=self.store,
            menu_id="M001", name="메뉴1", category="돈까스",
            price=10000, monthly_orders=100, packaging_cost=500,
        )
        # 사용량 2000g → 원가 2000원
        RecipeItem.objects.create(menu=self.menu, ingredient=self.ingredient, quantity=2000)

        self.assumption = ProfitAssumption.objects.create(
            label="테스트 가정",
            dine_in_share=0.5, delivery_share=0.3, takeout_share=0.2,
            delivery_commission_rate=0.1, rider_fee=4000, rider_fee_store_share=1.0,
            target_food_cost_rate=0.35,
        )

    def test_base_cost_and_rate(self):
        result = calculate_menu(self.menu, self.assumption)
        self.assertEqual(result["base_cost"], 2000)
        self.assertAlmostEqual(result["food_cost_rate"], 0.2, places=4)

    def test_margins(self):
        result = calculate_menu(self.menu, self.assumption)
        # 홀: 10000 - 2000
        self.assertEqual(result["dine_in_margin"], 8000)
        # 포장: 10000 - 2000 - 500
        self.assertEqual(result["takeout_margin"], 7500)
        # 배달: 10000 - 2000 - 500 - (10000*0.1) - (4000*1.0)
        self.assertEqual(result["delivery_margin"], 2500)
        # 가중: 8000*0.5 + 2500*0.3 + 7500*0.2
        self.assertEqual(result["weighted_margin"], 6250)

    def test_monthly_aggregates(self):
        result = calculate_menu(self.menu, self.assumption)
        self.assertEqual(result["monthly_profit"], 625000)
        self.assertEqual(result["monthly_revenue"], 1000000)

    def test_zero_price_does_not_divide(self):
        self.menu.price = 0
        self.menu.save()
        result = calculate_menu(self.menu, self.assumption)
        self.assertEqual(result["food_cost_rate"], 0.0)


class ClassifyTests(TestCase):
    def _result(self, **overrides):
        base = {
            "menu": Menu(menu_id="X", name="X", category="기타", price=10000, monthly_orders=100),
            "food_cost_rate": 0.2,
            "delivery_margin": 1000,
            "weighted_margin": 5000,
        }
        base.update(overrides)
        return base

    def test_green_signboard(self):
        # 판매 많고 원가 낮음
        r = self._result()
        r["menu"].monthly_orders = 200
        self.assertEqual(classify(r, average_orders=100, target_food_cost_rate=0.35), "🟢 간판 메뉴")

    def test_yellow_loss_bestseller(self):
        # 판매 많지만 원가 높음
        r = self._result(food_cost_rate=0.5)
        r["menu"].monthly_orders = 200
        self.assertEqual(classify(r, average_orders=100, target_food_cost_rate=0.35), "🟡 손해 보는 베스트셀러")

    def test_yellow_hidden_gem(self):
        # 판매 적지만 원가 낮음
        r = self._result()
        r["menu"].monthly_orders = 10
        self.assertEqual(classify(r, average_orders=100, target_food_cost_rate=0.35), "🟡 숨은 효자")

    def test_red_cleanup(self):
        # 판매 적고 원가 높음
        r = self._result(food_cost_rate=0.5)
        r["menu"].monthly_orders = 10
        self.assertEqual(classify(r, average_orders=100, target_food_cost_rate=0.35), "🔴 정리 검토")

    def test_red_delivery_loss(self):
        # 배달 마진/가중 마진 모두 음수면 무조건 배달 손실
        r = self._result(delivery_margin=-500, weighted_margin=-100)
        r["menu"].monthly_orders = 200
        self.assertEqual(classify(r, average_orders=100, target_food_cost_rate=0.35), "🔴 배달 손실")


class RecalculateAllTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="owner_b", password="pw12345!")
        self.store = Store.objects.create(owner=self.owner, name="매장B")
        self.ingredient = Ingredient.objects.create(
            store=self.store,
            ingredient_id="ING_A", name="재료A",
            purchase_quantity=1000, purchase_price=1000, unit="g",
        )
        self.active1 = Menu.objects.create(
            store=self.store,
            menu_id="M001", name="활성1", category="돈까스",
            price=10000, monthly_orders=100, packaging_cost=0,
        )
        self.active2 = Menu.objects.create(
            store=self.store,
            menu_id="M002", name="활성2", category="우동",
            price=8000, monthly_orders=50, packaging_cost=0,
        )
        self.inactive = Menu.objects.create(
            store=self.store,
            menu_id="M003", name="비활성", category="기타",
            price=5000, monthly_orders=10, is_active=False,
        )
        for m in (self.active1, self.active2, self.inactive):
            RecipeItem.objects.create(menu=m, ingredient=self.ingredient, quantity=1000)
        ProfitAssumption.objects.create(store=self.store, is_active=True)

    def test_creates_snapshot_per_active_menu(self):
        snaps = recalculate_all(store=self.store)
        self.assertEqual(len(snaps), 2)  # 비활성 제외
        self.assertEqual(MenuProfitSnapshot.objects.count(), 2)

    def test_get_latest_snapshots_returns_most_recent(self):
        recalculate_all(store=self.store)
        recalculate_all(store=self.store)  # 두 번째 호출 → 각 메뉴당 2개씩 스냅샷
        latest = get_latest_snapshots(store=self.store)
        self.assertEqual(len(latest), 2)
        # 각 메뉴별 가장 최근 1개만
        menu_ids = sorted(s.menu.menu_id for s in latest)
        self.assertEqual(menu_ids, ["M001", "M002"])

    def test_dashboard_summary_aggregates(self):
        snaps = recalculate_all(store=self.store)
        summary = dashboard_summary(snaps)
        self.assertEqual(summary["total_orders"], 150)  # 100 + 50
        self.assertIn("total_revenue", summary)
        self.assertIn("avg_food_cost_rate", summary)

    def test_dashboard_summary_empty(self):
        summary = dashboard_summary([])
        self.assertEqual(summary["total_revenue"], 0)
        self.assertEqual(summary["delivery_loss_count"], 0)
