"""데이터 품질·누락률 보고 테스트 (항목 7)."""
from datetime import date

from django.test import TestCase

from market.models import MarketItem
from market.ingestion.clients import FixtureKamisDailyClient
from market.ingestion.service import ingest_daily_prices
from market.quality import price_quality_report, full_report

FIXTURE = {
    "245": [
        {"observation_date": "2026-06-15", "unit": "g", "price": "2.10", "raw_ref": "a"},
        {"observation_date": "2026-06-16", "unit": "g", "price": "2.20", "raw_ref": "b"},
        # 06-17 결측 (gap)
        {"observation_date": "2026-06-18", "unit": "g", "price": "2.30", "raw_ref": "d"},
    ],
}


class QualityReportTests(TestCase):
    def setUp(self):
        self.item = MarketItem.objects.create(code="ONION", name="양파", source_item_code="245")
        ingest_daily_prices(items=[self.item], start=date(2026, 6, 15), end=date(2026, 6, 18),
                            client=FixtureKamisDailyClient(data=FIXTURE))

    def test_missing_rate_reflects_gap(self):
        rep = price_quality_report(date(2026, 6, 15), date(2026, 6, 18))
        row = rep[0]
        self.assertEqual(row["expected_days"], 4)
        self.assertEqual(row["observed_days"], 3)  # 06-17 결측
        self.assertEqual(row["missing_rate"], 0.25)

    def test_full_report_sections(self):
        rep = full_report(date(2026, 6, 15), date(2026, 6, 18))
        self.assertIn("price", rep)
        self.assertIn("wholesale", rep)
        self.assertIn("weather", rep)
        self.assertEqual(rep["window"]["start"], "2026-06-15")
