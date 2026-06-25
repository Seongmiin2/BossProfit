"""
외부 시세 연동(market_price.py) 테스트.

검증 대상:
- MockMarketPriceProvider: 결정성, 변동폭(±12%), 10원 단위 반올림
- get_provider: KAMIS 키 유무에 따른 provider 선택
- preview_price_changes: 집계 일관성(상승+하락+변동없음 == 총계), 쓰기 없음
- apply_price_changes: 단가 반영 + 이력 기록 + 스냅샷 재계산
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from profit.models import Store, Ingredient, Menu, RecipeItem, ProfitAssumption, IngredientPriceHistory

User = get_user_model()


def _make_store(username="mp_owner", name="시세테스트 매장"):
    owner = User.objects.create_user(username=username, password="pw12345!")
    return Store.objects.create(owner=owner, name=name)
from profit.market_price import (
    MockMarketPriceProvider,
    KamisMarketPriceProvider,
    get_provider,
    preview_price_changes,
    apply_price_changes,
    _extract_kamis_price,
    _parse_price,
)


class MockProviderTests(TestCase):
    def setUp(self):
        self.store = _make_store()
        self.ingredient = Ingredient.objects.create(
            store=self.store,
            ingredient_id="ING_A", name="재료A",
            purchase_quantity=1000, purchase_price=10000, unit="g",
        )
        self.provider = MockMarketPriceProvider()

    def test_deterministic(self):
        d = date(2026, 1, 1)
        first = self.provider.fetch_price(self.ingredient, d)
        second = self.provider.fetch_price(self.ingredient, d)
        self.assertEqual(first, second)

    def test_within_swing_band(self):
        d = date(2026, 1, 1)
        price = self.provider.fetch_price(self.ingredient, d)
        # ±12% 밴드 (10원 반올림 여유 포함)
        self.assertGreaterEqual(price, 10000 * 0.88 - 10)
        self.assertLessEqual(price, 10000 * 1.12 + 10)

    def test_rounded_to_ten(self):
        price = self.provider.fetch_price(self.ingredient, date(2026, 1, 1))
        self.assertEqual(price % 10, 0)

    def test_zero_price_returns_none(self):
        self.ingredient.purchase_price = 0
        self.assertIsNone(self.provider.fetch_price(self.ingredient, date(2026, 1, 1)))

    def test_different_dates_vary(self):
        # 충분히 많은 날짜 중 최소 일부는 값이 달라야 결정적 변동이 의미가 있음
        prices = {
            self.provider.fetch_price(self.ingredient, date(2026, 1, day))
            for day in range(1, 21)
        }
        self.assertGreater(len(prices), 1)


class KamisParserTests(TestCase):
    """실 API 없이 KAMIS 응답 파싱 로직을 검증."""

    def test_parse_price_variants(self):
        self.assertEqual(_parse_price("12,300"), 12300.0)
        self.assertEqual(_parse_price("5000"), 5000.0)
        self.assertIsNone(_parse_price("-"))
        self.assertIsNone(_parse_price(""))
        self.assertIsNone(_parse_price("0"))
        self.assertIsNone(_parse_price(["list"]))
        self.assertIsNone(_parse_price(None))

    def test_extract_filters_by_item_and_kind(self):
        payload = {
            "data": {
                "item": [
                    {"item_code": "111", "kind_code": "01", "dpr1": "1,000"},
                    {"item_code": "222", "kind_code": "02", "dpr1": "2,000"},
                ]
            }
        }
        self.assertEqual(_extract_kamis_price(payload, item_code="222", kind_code="02"), 2000.0)
        self.assertEqual(_extract_kamis_price(payload, item_code="111"), 1000.0)

    def test_extract_handles_single_dict_item(self):
        payload = {"data": {"item": {"item_code": "111", "dpr1": "3,300"}}}
        self.assertEqual(_extract_kamis_price(payload, item_code="111"), 3300.0)

    def test_extract_error_response_returns_none(self):
        # 오류 시 data가 리스트로 오는 경우
        self.assertIsNone(_extract_kamis_price({"data": ["001"]}, item_code="111"))
        self.assertIsNone(_extract_kamis_price({}, item_code="111"))

    def test_extract_no_match_returns_none(self):
        payload = {"data": {"item": [{"item_code": "111", "dpr1": "1,000"}]}}
        self.assertIsNone(_extract_kamis_price(payload, item_code="999"))


class GetProviderTests(TestCase):
    def test_defaults_to_mock(self):
        self.assertIsInstance(get_provider(), MockMarketPriceProvider)

    @override_settings(KAMIS_CERT_KEY="key", KAMIS_CERT_ID="id", KAMIS_ITEM_MAP={})
    def test_kamis_when_keys_present(self):
        self.assertIsInstance(get_provider(), KamisMarketPriceProvider)


class PreviewTests(TestCase):
    def setUp(self):
        self.store = _make_store()
        for i in range(5):
            Ingredient.objects.create(
                store=self.store,
                ingredient_id=f"ING_{i}", name=f"재료{i}",
                purchase_quantity=1000, purchase_price=10000 + i * 100, unit="g",
            )

    def test_summary_consistency(self):
        result = preview_price_changes(as_of=date(2026, 1, 1))
        s = result["summary"]
        self.assertEqual(s["total"], 5)
        self.assertEqual(s["up"] + s["down"] + s["unchanged"], s["total"])
        self.assertEqual(result["source"], "mock")

    def test_preview_does_not_write(self):
        before = [i.purchase_price for i in Ingredient.objects.order_by("ingredient_id")]
        preview_price_changes(as_of=date(2026, 1, 1))
        after = [i.purchase_price for i in Ingredient.objects.order_by("ingredient_id")]
        self.assertEqual(before, after)
        self.assertEqual(IngredientPriceHistory.objects.count(), 0)


class ApplyTests(TestCase):
    def setUp(self):
        self.store = _make_store()
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

    def test_apply_updates_price_and_records_history(self):
        as_of = date(2026, 1, 1)
        provider = MockMarketPriceProvider()
        original = self.ingredient.purchase_price
        expected = provider.fetch_price(self.ingredient, as_of)

        result = apply_price_changes(as_of=as_of)
        self.ingredient.refresh_from_db()

        if expected != original:
            self.assertEqual(self.ingredient.purchase_price, expected)
            self.assertEqual(result["applied_count"], 1)
            history = IngredientPriceHistory.objects.get(ingredient=self.ingredient)
            self.assertEqual(history.old_price, original)
            self.assertEqual(history.new_price, expected)
            self.assertEqual(history.source, "mock")
            # 단가가 바뀌었으니 재계산되어 스냅샷 생성
            self.assertEqual(result["recalculated"], 1)
        else:
            self.assertEqual(result["applied_count"], 0)

    def test_apply_specific_ingredient_only(self):
        other = Ingredient.objects.create(
            store=self.store,
            ingredient_id="ING_B", name="재료B",
            purchase_quantity=1000, purchase_price=5000, unit="g",
        )
        as_of = date(2026, 1, 1)
        apply_price_changes(ingredient_ids=["ING_A"], as_of=as_of)
        other.refresh_from_db()
        # 대상에서 제외된 재료는 이력/변경 없음
        self.assertFalse(IngredientPriceHistory.objects.filter(ingredient=other).exists())
        self.assertEqual(other.purchase_price, 5000)
