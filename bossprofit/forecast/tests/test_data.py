"""시계열 로더 ORM 통합 테스트 (항목 8)."""
from datetime import date

from django.test import TestCase

from market.models import MarketItem
from market.ingestion.clients import FixtureKamisDailyClient
from market.ingestion.service import ingest_daily_prices
from forecast.data import load_price_series, to_regular_daily

FIXTURE = {
    "245": [
        {"observation_date": "2026-06-15", "unit": "g", "price": "2.10", "raw_ref": "a"},
        {"observation_date": "2026-06-16", "unit": "g", "price": "2.20", "raw_ref": "b"},
        {"observation_date": "2026-06-18", "unit": "g", "price": "2.30", "raw_ref": "d"},  # 17 결측
    ],
}


class LoadPriceSeriesTests(TestCase):
    def setUp(self):
        self.item = MarketItem.objects.create(code="ONION", name="양파", source_item_code="245")
        ingest_daily_prices(items=[self.item], start=date(2026, 6, 15), end=date(2026, 6, 18),
                            client=FixtureKamisDailyClient(data=FIXTURE))

    def test_loads_sorted_series(self):
        s = load_price_series(self.item)
        self.assertEqual(len(s), 3)
        self.assertEqual(list(s.values), [2.10, 2.20, 2.30])
        self.assertEqual(s.name, "ONION")
        self.assertTrue(s.index.is_monotonic_increasing)

    def test_regular_daily_exposes_gap(self):
        s = to_regular_daily(load_price_series(self.item))
        # 06-15 ~ 06-18 → 4일, 06-17은 NaN
        self.assertEqual(len(s), 4)
        self.assertTrue(s.isna().sum() == 1)

    def test_empty_when_no_data(self):
        other = MarketItem.objects.create(code="GARLIC", name="마늘", source_item_code="999")
        self.assertTrue(load_price_series(other).empty)
