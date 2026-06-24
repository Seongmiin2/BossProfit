from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Store, StoreMember, OnboardingProgress


class AccountOnboardingTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="new-owner",
            password="test-password",
        )
        self.client.force_authenticate(self.user)

    def test_new_user_starts_without_store(self):
        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["store"])
        self.assertEqual(response.data["onboarding"]["current_step"], "STORE")

    def test_user_can_create_one_store(self):
        response = self.client.post(
            reverse("auth-store-create"),
            {
                "name": "민이네 식당",
                "business_type": "KOREAN",
                "region": "서울 마포구",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        store = Store.objects.get(name="민이네 식당")
        self.assertTrue(
            StoreMember.objects.filter(
                store=store,
                user=self.user,
                role="OWNER",
            ).exists()
        )
        progress = OnboardingProgress.objects.get(store=store)
        self.assertEqual(progress.current_step, "INGREDIENT")

        duplicate = self.client.post(
            reverse("auth-store-create"),
            {
                "name": "두 번째 매장",
                "business_type": "OTHER",
                "region": "",
            },
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400)

    def test_logout_blacklists_refresh_token(self):
        refresh = RefreshToken.for_user(self.user)
        access = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        response = self.client.post(
            reverse("auth-logout"),
            {"refresh": str(refresh)},
            format="json",
        )

        self.assertEqual(response.status_code, 204)
        refresh_response = self.client.post(
            reverse("auth-refresh"),
            {"refresh": str(refresh)},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, 401)

    def test_owner_can_update_profile_and_store(self):
        store = Store.objects.create(
            name="수정 전 매장",
            business_type="OTHER",
        )
        StoreMember.objects.create(store=store, user=self.user, role="OWNER")

        profile_response = self.client.put(
            reverse("auth-profile-update"),
            {"username": "updated-owner", "email": "owner@example.com"},
            format="json",
        )
        store_response = self.client.put(
            reverse("auth-store-update"),
            {
                "name": "수정된 매장",
                "business_type": "JAPANESE",
                "region": "서울 마포구",
            },
            format="json",
        )

        self.assertEqual(profile_response.status_code, 200)
        self.assertEqual(store_response.status_code, 200)
        self.user.refresh_from_db()
        store.refresh_from_db()
        self.assertEqual(self.user.username, "updated-owner")
        self.assertEqual(self.user.email, "owner@example.com")
        self.assertEqual(store.name, "수정된 매장")
        self.assertEqual(store.business_type, "JAPANESE")

    def test_password_change_requires_current_password(self):
        wrong_response = self.client.post(
            reverse("auth-password-change"),
            {
                "current_password": "wrong-password",
                "new_password": "new-secure-password",
                "new_password2": "new-secure-password",
            },
            format="json",
        )
        success_response = self.client.post(
            reverse("auth-password-change"),
            {
                "current_password": "test-password",
                "new_password": "new-secure-password",
                "new_password2": "new-secure-password",
            },
            format="json",
        )

        self.assertEqual(wrong_response.status_code, 400)
        self.assertEqual(success_response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("new-secure-password"))

    def test_non_owner_cannot_update_store(self):
        store = Store.objects.create(name="직원 매장")
        StoreMember.objects.create(store=store, user=self.user, role="STAFF")

        response = self.client.put(
            reverse("auth-store-update"),
            {"name": "바꾸면 안 되는 이름"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        store.refresh_from_db()
        self.assertEqual(store.name, "직원 매장")


class FullOnboardingFlowTests(APITestCase):
    def test_new_owner_can_complete_first_analysis_flow(self):
        register_response = self.client.post(
            reverse("auth-register"),
            {
                "username": "flow-owner",
                "password": "secure-password",
                "password2": "secure-password",
            },
            format="json",
        )
        self.assertEqual(register_response.status_code, 201)

        login_response = self.client.post(
            reverse("auth-login"),
            {
                "username": "flow-owner",
                "password": "secure-password",
            },
            format="json",
        )
        self.assertEqual(login_response.status_code, 200)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_response.data['access']}"
        )

        store_response = self.client.post(
            reverse("auth-store-create"),
            {
                "name": "플로우 테스트 식당",
                "business_type": "KOREAN",
                "region": "서울",
            },
            format="json",
        )
        self.assertEqual(store_response.status_code, 201)

        ingredient_response = self.client.post(
            reverse("api-ingredient-create"),
            {
                "ingredient_id": "FLOW_ING",
                "name": "돼지고기",
                "category": "돈까스",
                "purchase_quantity": 1000,
                "purchase_price": 9000,
                "unit": "g",
                "memo": "",
            },
            format="json",
        )
        self.assertEqual(ingredient_response.status_code, 201)

        menu_response = self.client.post(
            reverse("api-menu-create"),
            {
                "menu_id": "FLOW_MENU",
                "name": "왕돈까스",
                "category": "돈까스",
                "price": 13000,
                "monthly_orders": 0,
                "packaging_cost": 500,
                "is_active": True,
                "recipe_items": [
                    {
                        "ingredient_id": "FLOW_ING",
                        "quantity": 200,
                        "memo": "",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(menu_response.status_code, 201)

        sales_response = self.client.post(
            reverse("api-daily-sales"),
            {
                "menu_id": "FLOW_MENU",
                "sale_date": timezone.localdate().isoformat(),
                "quantity": 18,
                "channel": "ALL",
            },
            format="json",
        )
        self.assertEqual(sales_response.status_code, 200)

        me_response = self.client.get(reverse("auth-me"))
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.data["store"]["name"], "플로우 테스트 식당")
        self.assertTrue(me_response.data["onboarding"]["is_complete"])

        dashboard_response = self.client.get(reverse("api-dashboard"))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(dashboard_response.data["store_name"], "플로우 테스트 식당")
        self.assertEqual(len(dashboard_response.data["snapshots"]), 1)
