from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APITestCase

from accounts.models import Store, StoreMember, OnboardingProgress
from .models import (
    Ingredient,
    Menu,
    RecipeItem,
    DailyMenuSale,
    MenuProfitSnapshot,
    ProfitAssumption,
)


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
