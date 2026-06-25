"""멀티테넌트 격리 테스트 (출시 게이트: 타 매장 데이터 노출 0건).

두 매장 A/B를 만들고, A로 로그인했을 때 B의 메뉴·재료·대시보드에
어떤 경로로도 접근되지 않음을 검증한다.
"""
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from profit.models import Store, StoreMember, Ingredient, Menu, RecipeItem, ProfitAssumption
from profit.calculator import recalculate_all

User = get_user_model()


def _setup_store(username, store_name, menu_id, ingredient_id):
    user = User.objects.create_user(username=username, password="pw12345!")
    store = Store.objects.create(owner=user, name=store_name)
    StoreMember.objects.create(store=store, user=user, role="OWNER")
    ing = Ingredient.objects.create(
        store=store, ingredient_id=ingredient_id, name=f"{store_name}-재료",
        purchase_quantity=1000, purchase_price=10000, unit="g",
    )
    menu = Menu.objects.create(
        store=store, menu_id=menu_id, name=f"{store_name}-메뉴",
        category="돈까스", price=10000, monthly_orders=100,
    )
    RecipeItem.objects.create(menu=menu, ingredient=ing, quantity=500)
    ProfitAssumption.objects.create(store=store, is_active=True)
    recalculate_all(store=store)  # 대시보드·목록이 보여줄 스냅샷 생성
    return user, store, menu, ing


class StoreIsolationTests(APITestCase):
    def setUp(self):
        self.user_a, self.store_a, self.menu_a, self.ing_a = _setup_store(
            "owner_a", "매장A", "M001", "ING_A"
        )
        self.user_b, self.store_b, self.menu_b, self.ing_b = _setup_store(
            "owner_b", "매장B", "M001", "ING_B"  # 일부러 같은 menu_id 사용
        )

    def test_same_menu_id_allowed_across_stores(self):
        # 매장 스코프 unique이므로 두 매장이 동일 menu_id를 가질 수 있다.
        self.assertEqual(self.menu_a.menu_id, self.menu_b.menu_id)

    def test_dashboard_only_shows_own_store(self):
        self.client.force_authenticate(user=self.user_a)
        res = self.client.get(reverse("api-dashboard"))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["store_name"], "매장A")
        names = {s["menu"]["name"] for s in res.data["snapshots"]}
        self.assertIn("매장A-메뉴", names)
        self.assertNotIn("매장B-메뉴", names)

    def test_menu_list_scoped(self):
        self.client.force_authenticate(user=self.user_a)
        res = self.client.get(reverse("api-menu-list"))
        self.assertEqual(res.status_code, 200)
        names = {s["menu"]["name"] for s in res.data}
        self.assertEqual(names, {"매장A-메뉴"})

    def test_ingredient_list_scoped(self):
        self.client.force_authenticate(user=self.user_a)
        res = self.client.get(reverse("api-ingredient-list"))
        self.assertEqual(res.status_code, 200)
        ids = {row["ingredient_id"] for row in res.data}
        self.assertEqual(ids, {"ING_A"})

    def test_cannot_read_other_store_menu_detail(self):
        # 매장 A로 로그인해도 menu_id=M001은 A 것만 보인다 (B 것이 아님).
        self.client.force_authenticate(user=self.user_a)
        res = self.client.get(reverse("api-menu-detail", args=["M001"]))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["menu"]["name"], "매장A-메뉴")

    def test_cannot_update_other_store_ingredient(self):
        # B에만 있는 ING_B를 A로 수정 시도 → 404
        self.client.force_authenticate(user=self.user_a)
        res = self.client.put(
            reverse("api-ingredient-update", args=["ING_B"]),
            {"name": "탈취시도"}, format="json",
        )
        self.assertEqual(res.status_code, 404)
        self.ing_b.refresh_from_db()
        self.assertEqual(self.ing_b.name, "매장B-재료")

    def test_cannot_delete_other_store_menu(self):
        # 동일 menu_id라도 A가 삭제하면 A 것만 지워지고 B는 남는다.
        self.client.force_authenticate(user=self.user_a)
        res = self.client.delete(reverse("api-menu-delete", args=["M001"]))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(Menu.objects.filter(pk=self.menu_b.pk).exists())
        self.assertFalse(Menu.objects.filter(pk=self.menu_a.pk).exists())

    def test_anonymous_blocked(self):
        res = self.client.get(reverse("api-dashboard"))
        self.assertIn(res.status_code, (401, 403))

    def test_user_without_store_gets_412(self):
        no_store = User.objects.create_user(username="nostore", password="pw12345!")
        self.client.force_authenticate(user=no_store)
        res = self.client.get(reverse("api-dashboard"))
        self.assertEqual(res.status_code, 412)
        self.assertEqual(res.data["code"], "STORE_REQUIRED")
