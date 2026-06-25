"""
시세 연동 REST API 엔드포인트 테스트.

검증 대상:
- GET  /api/v1/market/preview/            (공개)
- POST /api/v1/market/sync/               (인증 필요)
- GET  /api/v1/ingredients/<id>/price-history/
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from profit.models import Store, StoreMember, Ingredient, Menu, RecipeItem, ProfitAssumption, IngredientPriceHistory

User = get_user_model()


class MarketAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="pw12345!")
        self.store = Store.objects.create(owner=self.user, name="테스터 매장")
        StoreMember.objects.create(store=self.store, user=self.user, role="OWNER")
        self.ingredient = Ingredient.objects.create(
            store=self.store,
            ingredient_id="ING_A", name="재료A",
            purchase_quantity=1000, purchase_price=10000, unit="g",
        )
        self.menu = Menu.objects.create(
            store=self.store,
            menu_id="M001", name="메뉴1", category="돈까스",
            price=10000, monthly_orders=100,
        )
        RecipeItem.objects.create(menu=self.menu, ingredient=self.ingredient, quantity=1000)
        ProfitAssumption.objects.create(store=self.store, is_active=True)

    def test_preview_requires_auth(self):
        url = reverse("api-market-preview")
        res = self.client.get(url)
        self.assertIn(res.status_code, (401, 403))

    def test_preview_authenticated_scoped_to_store(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("api-market-preview")
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["source"], "mock")
        self.assertIn("changes", res.data)
        self.assertEqual(res.data["summary"]["total"], 1)

    def test_sync_requires_auth(self):
        url = reverse("api-market-sync")
        res = self.client.post(url, {}, format="json")
        self.assertIn(res.status_code, (401, 403))

    def test_sync_with_auth_applies_and_recalculates(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("api-market-sync")
        res = self.client.post(url, {}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertIn("applied_count", res.data)
        self.assertIn("message", res.data)
        # 변경이 있었다면 이력이 남아야 함
        if res.data["applied_count"] > 0:
            self.assertTrue(IngredientPriceHistory.objects.exists())

    def test_sync_rejects_non_list_ingredient_ids(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("api-market-sync")
        res = self.client.post(url, {"ingredient_ids": "ING_A"}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_price_history_endpoint(self):
        self.client.force_authenticate(user=self.user)
        # 이력 1건 생성
        IngredientPriceHistory.objects.create(
            ingredient=self.ingredient, old_price=10000, new_price=10500, source="mock",
        )
        url = reverse("api-ingredient-price-history", args=["ING_A"])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["ingredient_id"], "ING_A")
        self.assertEqual(len(res.data["history"]), 1)
        row = res.data["history"][0]
        self.assertEqual(row["delta"], 500)
        self.assertEqual(row["old_price"], 10000)

    def test_price_history_unknown_ingredient_404(self):
        self.client.force_authenticate(user=self.user)
        url = reverse("api-ingredient-price-history", args=["NOPE"])
        res = self.client.get(url)
        self.assertEqual(res.status_code, 404)
