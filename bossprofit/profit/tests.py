from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import Workbook
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APITestCase

from accounts.models import Store, StoreMember, OnboardingProgress
from .models import (
    Ingredient,
    IngredientMarketMapping,
    Menu,
    RecipeItem,
    DailyMenuSale,
    MenuProfitSnapshot,
    ProfitAssumption,
    ForecastRun,
    MarketItem,
    MarketPriceObservation,
    MarketRankingSnapshot,
    ActionPlan,
)
from .forecasting import ForecastEngine
from .integrations.kamis import parse_month_day
from .sales_import import parse_pos_workbook


class ProfitApiTests(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="owner",
            password="test-password",
        )
        self.other_user = user_model.objects.create_user(
            username="other-owner",
            password="test-password",
        )
        self.store = Store.objects.create(
            name="테스트 매장",
            business_type="KOREAN",
        )
        self.other_store = Store.objects.create(
            name="다른 매장",
            business_type="CAFE",
        )
        StoreMember.objects.create(store=self.store, user=self.user, role="OWNER")
        StoreMember.objects.create(
            store=self.other_store,
            user=self.other_user,
            role="OWNER",
        )
        self.menu = Menu.objects.create(
            store=self.store,
            menu_id="M001",
            name="테스트 메뉴",
            category="기타",
            price=10000,
            monthly_orders=10,
            packaging_cost=500,
        )
        self.other_menu = Menu.objects.create(
            store=self.other_store,
            menu_id="M001",
            name="다른 매장 메뉴",
            category="기타",
            price=12000,
            monthly_orders=5,
            packaging_cost=500,
        )
        self.public_assumption = ProfitAssumption.objects.create(
            label="공용 기본 가정",
            owner=None,
            store=None,
        )

    def create_snapshot(self, store, menu, monthly_profit):
        return MenuProfitSnapshot.objects.create(
            store=store,
            owner=None,
            menu=menu,
            base_cost=1000,
            food_cost_rate=0.1,
            dine_in_margin=9000,
            takeout_margin=8500,
            delivery_margin=3000,
            weighted_margin=7000,
            monthly_profit=monthly_profit,
            monthly_revenue=100000,
            signal="🟢 간판 메뉴",
        )

    def test_recalculate_requires_authentication(self):
        response = self.client.post(reverse("api-recalculate"))
        self.assertEqual(response.status_code, 401)

    def test_store_data_endpoints_require_authentication(self):
        endpoints = [
            reverse("api-dashboard"),
            reverse("api-menu-list"),
            reverse("api-menu-detail", args=[self.menu.menu_id]),
            reverse("api-ingredient-list"),
            reverse("api-history"),
        ]
        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.get(endpoint)
                self.assertEqual(response.status_code, 401)

    def test_authenticated_recalculation_uses_store_assumption(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(reverse("api-recalculate"))

        self.assertEqual(response.status_code, 200)
        assumption = ProfitAssumption.objects.get(
            store=self.store,
            is_active=True,
        )
        self.assertEqual(assumption.label, self.public_assumption.label)
        self.assertTrue(
            MenuProfitSnapshot.objects.filter(store=self.store).exists()
        )
        self.assertFalse(
            MenuProfitSnapshot.objects.filter(store=self.other_store).exists()
        )

    def test_history_is_scoped_to_store(self):
        self.create_snapshot(self.store, self.menu, monthly_profit=2000)
        self.create_snapshot(
            self.other_store,
            self.other_menu,
            monthly_profit=9000,
        )
        self.client.force_authenticate(self.user)

        response = self.client.get(reverse("api-history"), {"days": 30})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["profit"], [2000.0])

    def test_user_cannot_read_other_store_menu(self):
        self.client.force_authenticate(self.user)

        response = self.client.get(
            reverse("api-menu-detail", args=[self.other_menu.menu_id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["menu"]["name"], self.menu.name)

    def test_assumption_rejects_invalid_sales_share_sum(self):
        self.client.force_authenticate(self.user)

        response = self.client.put(
            reverse("api-assumption-update"),
            {
                "dine_in_share": 0.5,
                "delivery_share": 0.5,
                "takeout_share": 0.5,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_daily_sale_completes_onboarding_and_updates_orders(self):
        ingredient = Ingredient.objects.create(
            store=self.store,
            ingredient_id="ING001",
            name="테스트 재료",
            category="기타",
            purchase_quantity=1000,
            purchase_price=5000,
            unit="g",
        )
        RecipeItem.objects.create(
            menu=self.menu,
            ingredient=ingredient,
            quantity=100,
        )
        OnboardingProgress.objects.create(
            store=self.store,
            current_step="SALES",
            ingredient_completed=True,
            menu_completed=True,
            recipe_completed=True,
        )
        self.client.force_authenticate(self.user)

        response = self.client.post(
            reverse("api-daily-sales"),
            {
                "menu_id": self.menu.menu_id,
                "sale_date": timezone.localdate().isoformat(),
                "quantity": 12,
                "channel": "ALL",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            DailyMenuSale.objects.filter(
                store=self.store,
                menu=self.menu,
                quantity=12,
            ).exists()
        )
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.monthly_orders, 12)
        progress = OnboardingProgress.objects.get(store=self.store)
        self.assertEqual(progress.current_step, "COMPLETE")


class DemoAccountSeedTests(TestCase):
    def test_demo_account_seed_is_complete_and_idempotent(self):
        command_options = {
            "username": "demo-owner",
            "password": "demo-password",
            "store_name": "우동·돈까스 테스트 매장",
        }

        call_command("seed_demo_account", **command_options)
        call_command("seed_demo_account", **command_options)

        user = get_user_model().objects.get(username="demo-owner")
        self.assertTrue(user.check_password("demo-password"))
        self.assertEqual(user.store_memberships.filter(is_active=True).count(), 1)

        store = user.store_memberships.get(is_active=True).store
        self.assertEqual(store.name, "우동·돈까스 테스트 매장")
        self.assertEqual(store.ingredients.count(), 35)
        self.assertEqual(store.menus.count(), 21)
        self.assertEqual(
            RecipeItem.objects.filter(menu__store=store).count(),
            118,
        )
        self.assertEqual(store.daily_sales.count(), 21)
        self.assertEqual(store.profit_snapshots.count(), 21)
        self.assertEqual(store.onboarding.current_step, "COMPLETE")


class MarketRankingApiTests(APITestCase):
    def setUp(self):
        call_command("seed_market_demo")

    def test_public_market_ranking_returns_top_five(self):
        response = self.client.get(
            reverse("api-market-ranking", args=["tomorrow"])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 5)
        self.assertEqual(response.data["items"][0]["name"], "양파")
        self.assertTrue(response.data["is_demo"])
        self.assertFalse(response.data["metrics"]["is_verified"])

    def test_market_ranking_search_filters_items(self):
        response = self.client.get(
            reverse("api-market-ranking", args=["tomorrow"]),
            {"q": "감자"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["name"] for item in response.data["items"]], ["감자"])

    def test_market_ranking_has_previous_rank_and_outlooks(self):
        response = self.client.get(
            reverse("api-market-ranking", args=["volume"])
        )

        first = response.data["items"][0]
        self.assertEqual(first["previous_rank"], 2)
        self.assertEqual(first["rank_delta"], 1)
        self.assertEqual(
            [item["horizon_days"] for item in first["outlooks"]],
            [1, 7, 30],
        )
        self.assertEqual(
            MarketRankingSnapshot.objects.filter(
                ranking_type="VOLUME"
            ).count(),
            5,
        )


class ForecastEngineTests(TestCase):
    def setUp(self):
        self.item = MarketItem.objects.create(
            code="KAMIS:TEST:00:04",
            name="테스트 양파",
            category="200",
            unit="1kg",
        )
        start = timezone.localdate() - timedelta(days=39)
        collected_at = timezone.now()
        for index in range(40):
            MarketPriceObservation.objects.create(
                item=self.item,
                observed_date=start + timedelta(days=index),
                region_code="AVERAGE",
                region_name="평균",
                market_type="RETAIL",
                unit="1kg",
                price=Decimal("1800") + Decimal(index * 3),
                source="KAMIS_PERIOD",
                collected_at=collected_at,
            )

    def test_forecast_persists_additive_components_without_future_data(self):
        as_of_date = timezone.localdate()
        MarketPriceObservation.objects.create(
            item=self.item,
            observed_date=as_of_date + timedelta(days=1),
            region_code="AVERAGE",
            region_name="평균",
            market_type="RETAIL",
            unit="1kg",
            price=Decimal("999999"),
            source="KAMIS_PERIOD",
            collected_at=timezone.now(),
        )

        # 이 테스트는 통계 가산 파이프라인(base+weather+residual)의 무누설 속성을
        # 검증하므로 LightGBM 경로를 끈다.
        ForecastEngine(use_lightgbm=False).run(
            self.item, as_of_date, horizons=(1, 60, 90)
        )

        run = ForecastRun.objects.get(item=self.item, as_of_date=as_of_date)
        self.assertEqual(run.status, "SUCCEEDED")
        self.assertEqual(run.points.count(), 3)
        for point in run.points.select_related("components"):
            components = point.components
            self.assertEqual(
                point.median,
                components.base_prediction
                + components.weather_adjustment
                + components.residual_adjustment,
            )
            self.assertLessEqual(point.lower, point.median)
            self.assertLessEqual(point.median, point.upper)
            self.assertEqual(
                components.details["base"]["last_observed_date"],
                as_of_date.isoformat(),
            )

    def test_kamis_comparison_label_date_is_parsed(self):
        parsed = parse_month_day("당일 (06/24)", timezone.localdate())
        self.assertEqual(parsed.month, 6)
        self.assertEqual(parsed.day, 24)


class PosSalesImportParserTests(TestCase):
    def test_product_change_without_repeated_category_is_preserved(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "sales.xlsx"
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["상품-일자별"])
            sheet.append([])
            sheet.append(["조회일자"])
            sheet.append([
                "대분류",
                "상품코드",
                "상품명",
                "일자",
                "수량",
                "총매출액",
                "총할인액",
                "실매출액",
            ])
            sheet.append(["메뉴", "000001", "우동(순)", "2026-01-01", 1, 8000, 0, 8000])
            sheet.append([None, "000002", "우동(보)", "2026-01-02", 2, 16000, 0, 16000])
            workbook.save(path)

            rows = parse_pos_workbook(path)

        self.assertEqual([row.product_code for row in rows], ["000001", "000002"])
        self.assertEqual([row.product_name for row in rows], ["우동(순)", "우동(보)"])
        self.assertTrue(all(row.category == "메뉴" for row in rows))


class StoreAnalysisApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="analysis-owner",
            password="test-password",
        )
        self.other_user = get_user_model().objects.create_user(
            username="analysis-other",
            password="test-password",
        )
        self.store = Store.objects.create(name="분석 매장")
        self.other_store = Store.objects.create(name="다른 분석 매장")
        StoreMember.objects.create(store=self.store, user=self.user, role="OWNER")
        StoreMember.objects.create(
            store=self.other_store,
            user=self.other_user,
            role="OWNER",
        )
        self.menu = Menu.objects.create(
            store=self.store,
            menu_id="POS001",
            name="돈까스",
            category="메뉴",
            price=13000,
        )
        other_menu = Menu.objects.create(
            store=self.other_store,
            menu_id="POS001",
            name="노출 금지 메뉴",
            category="메뉴",
            price=10000,
        )
        DailyMenuSale.objects.create(
            store=self.store,
            menu=self.menu,
            sale_date=timezone.localdate(),
            quantity=10,
            gross_revenue=130000,
            net_revenue=129000,
            discount_amount=1000,
        )
        DailyMenuSale.objects.create(
            store=self.other_store,
            menu=other_menu,
            sale_date=timezone.localdate(),
            quantity=999,
            gross_revenue=9990000,
            net_revenue=9990000,
        )

    def test_store_analysis_uses_actual_sales_and_keeps_profitability_pending(self):
        self.client.force_authenticate(self.user)

        response = self.client.get(reverse("api-store-analysis"))

        self.assertEqual(response.status_code, 200)
        analysis = response.data["analysis"]
        self.assertEqual(analysis["summary"]["food_quantity"], 10)
        self.assertEqual(analysis["summary"]["food_net_revenue"], 129000)
        self.assertEqual(analysis["top_menus"][0]["name"], "돈까스")
        self.assertEqual(
            analysis["top_menus"][0]["profitability_state"],
            "INSUFFICIENT",
        )
        self.assertNotContains(response, "노출 금지 메뉴")

    def test_store_market_ranking_excludes_unrelated_market_items(self):
        cabbage = MarketItem.objects.create(
            code="KAMIS:CABBAGE",
            name="배추",
            category="채소",
            unit="1포기",
        )
        MarketRankingSnapshot.objects.create(
            ranking_type="TOMORROW",
            as_of_date=timezone.localdate(),
            item=cabbage,
            rank=1,
            score=Decimal("20.8"),
            display_change_rate=Decimal("0.208"),
        )
        self.client.force_authenticate(self.user)

        response = self.client.get(reverse("api-store-analysis"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["market_risks"]["state"], "INSUFFICIENT")
        self.assertEqual(response.data["market_risks"]["items"], [])
        self.assertNotContains(response, "배추")

        ingredient = Ingredient.objects.create(
            store=self.store,
            ingredient_id="CABBAGE",
            name="배추",
            category="공통",
            purchase_quantity=1,
            purchase_price=3000,
            unit="ea",
        )
        RecipeItem.objects.create(
            menu=self.menu,
            ingredient=ingredient,
            quantity=1,
        )
        IngredientMarketMapping.objects.create(
            ingredient=ingredient,
            market_item=cabbage,
            confidence=Decimal("1"),
            status="CONFIRMED",
        )

        response = self.client.get(reverse("api-store-analysis"))

        self.assertEqual(response.data["market_risks"]["state"], "SUCCESS")
        self.assertEqual(
            response.data["market_risks"]["items"][0]["item"]["name"],
            "배추",
        )
        self.assertEqual(
            response.data["market_risks"]["items"][0]["affected_menus"][0]["name"],
            "돈까스",
        )

    def test_action_plan_is_scoped_to_authenticated_store(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            reverse("api-action-plan-create"),
            {
                "title": "레시피 확인",
                "period": "오늘",
                "reason": "원가 위험 계산",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        plan = ActionPlan.objects.get(id=response.data["id"])
        self.assertEqual(plan.store, self.store)
        self.assertEqual(plan.created_by, self.user)
