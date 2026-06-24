from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Menu, MenuProfitSnapshot, ProfitAssumption


class ProfitApiTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="owner",
            password="test-password",
        )
        self.menu = Menu.objects.create(
            menu_id="M001",
            name="테스트 메뉴",
            category="기타",
            price=10000,
            monthly_orders=10,
            packaging_cost=500,
        )
        self.public_assumption = ProfitAssumption.objects.create(
            label="공용 기본 가정",
            owner=None,
        )

    def create_snapshot(self, owner, monthly_profit):
        return MenuProfitSnapshot.objects.create(
            owner=owner,
            menu=self.menu,
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

    def test_authenticated_recalculation_uses_user_assumption_and_owner(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(reverse("api-recalculate"))

        self.assertEqual(response.status_code, 200)
        assumption = ProfitAssumption.objects.get(owner=self.user, is_active=True)
        self.assertEqual(assumption.label, self.public_assumption.label)
        self.assertTrue(MenuProfitSnapshot.objects.filter(owner=self.user).exists())

    def test_history_does_not_mix_public_and_user_snapshots(self):
        self.create_snapshot(owner=None, monthly_profit=1000)
        self.create_snapshot(owner=self.user, monthly_profit=2000)
        self.client.force_authenticate(self.user)

        response = self.client.get(reverse("api-history"), {"days": 30})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["profit"], [2000.0])

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
