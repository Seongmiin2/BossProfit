"""도매 경락 수집 테스트 (항목 4)."""
from datetime import date

from django.test import TestCase

from market.models import MarketItem, WholesaleAuctionObservation
from market.ingestion.wholesale import FixtureWholesaleClient, ingest_wholesale_auction

FIXTURE = {
    "245": [
        {"observation_date": "2026-06-15", "market": "가락시장", "origin": "전남",
         "grade": "상", "unit": "g", "price": "1.95", "volume": "120000", "raw_ref": "a"},
        {"observation_date": "2026-06-16", "market": "가락시장", "origin": "전남",
         "grade": "상", "unit": "g", "price": "2.00", "volume": "98000", "raw_ref": "b"},
        # +70% 급등락
        {"observation_date": "2026-06-17", "market": "가락시장", "origin": "전남",
         "grade": "상", "unit": "g", "price": "3.40", "volume": "31000", "raw_ref": "c"},
    ],
}


class WholesaleIngestTests(TestCase):
    def setUp(self):
        self.item = MarketItem.objects.create(code="ONION", name="양파", source_item_code="245")
        self.client = FixtureWholesaleClient(data=FIXTURE)

    def test_creates_with_volume(self):
        run = ingest_wholesale_auction(
            items=[self.item], start=date(2026, 6, 15), end=date(2026, 6, 17),
            client=self.client,
        )
        self.assertEqual(run.status, "success")
        self.assertEqual(WholesaleAuctionObservation.objects.count(), 3)
        obs = WholesaleAuctionObservation.objects.get(observation_date=date(2026, 6, 15))
        self.assertEqual(str(obs.volume), "120000.00")

    def test_idempotent(self):
        for _ in range(2):
            ingest_wholesale_auction(items=[self.item], start=date(2026, 6, 15),
                                     end=date(2026, 6, 17), client=self.client)
        self.assertEqual(WholesaleAuctionObservation.objects.count(), 3)

    def test_anomaly_flagged(self):
        ingest_wholesale_auction(items=[self.item], start=date(2026, 6, 15),
                                 end=date(2026, 6, 17), client=self.client)
        spike = WholesaleAuctionObservation.objects.get(observation_date=date(2026, 6, 17))
        self.assertEqual(spike.quality_flag, "anomaly_jump")
