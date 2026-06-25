"""KAMIS 수집 서비스 테스트 (fixture 기반, API 키 불필요).

검증 대상 (담당 B 핵심 완료 기준):
- 멱등 upsert: 같은 범위 재수집 시 중복 없음
- 값 변경 시 갱신 (KAMIS 수정 반영)
- 품질검사: 0/음수 skip, 급등락 플래그 (삭제하지 않음)
- IngestionRun 카운트/상태/파라미터 기록
- collected_at / observation_date 시간 구분 + first_collected_at 보존
"""
from datetime import date

from django.test import TestCase

from market.models import MarketItem, IngestionRun, MarketPriceObservation
from market.ingestion.clients import FixtureKamisDailyClient
from market.ingestion.service import ingest_daily_prices

FIXTURE = {
    "245": [
        {"observation_date": "2026-06-15", "region": "서울", "market_type": "retail",
         "grade": "상", "unit": "g", "price": "2.10", "raw_ref": "r1"},
        {"observation_date": "2026-06-16", "region": "서울", "market_type": "retail",
         "grade": "상", "unit": "g", "price": "2.20", "raw_ref": "r2"},
        # 전일 2.20 → 3.80: +72% 급등락 플래그
        {"observation_date": "2026-06-17", "region": "서울", "market_type": "retail",
         "grade": "상", "unit": "g", "price": "3.80", "raw_ref": "r3"},
        # 0원: skip
        {"observation_date": "2026-06-18", "region": "서울", "market_type": "retail",
         "grade": "상", "unit": "g", "price": "0", "raw_ref": "r4"},
    ],
}


class IngestDailyPricesTests(TestCase):
    def setUp(self):
        self.item = MarketItem.objects.create(
            code="ONION", name="양파", standard_unit="g",
            source="kamis", source_item_code="245",
        )
        self.client = FixtureKamisDailyClient(data=FIXTURE)
        self.start = date(2026, 6, 15)
        self.end = date(2026, 6, 18)

    def test_first_run_creates_observations(self):
        run = ingest_daily_prices(
            items=[self.item], start=self.start, end=self.end, client=self.client
        )
        self.assertEqual(run.status, "success")
        # 4행 fetch, 0원 1건 skip → 관측 3건
        self.assertEqual(run.fetched_count, 4)
        self.assertEqual(run.created_count, 3)
        self.assertEqual(run.skipped_count, 1)
        self.assertEqual(MarketPriceObservation.objects.count(), 3)

    def test_idempotent_no_duplicates(self):
        ingest_daily_prices(items=[self.item], start=self.start, end=self.end, client=self.client)
        run2 = ingest_daily_prices(items=[self.item], start=self.start, end=self.end, client=self.client)
        # 재수집: 생성 0, 갱신 3, 중복 없음
        self.assertEqual(MarketPriceObservation.objects.count(), 3)
        self.assertEqual(run2.created_count, 0)
        self.assertEqual(run2.updated_count, 3)

    def test_value_change_updates_in_place(self):
        ingest_daily_prices(items=[self.item], start=self.start, end=self.end, client=self.client)
        changed = {"245": [dict(FIXTURE["245"][0], price="9.99")]}
        client2 = FixtureKamisDailyClient(data=changed)
        ingest_daily_prices(items=[self.item], start=self.start, end=date(2026, 6, 15), client=client2)
        obs = MarketPriceObservation.objects.get(
            item=self.item, observation_date=date(2026, 6, 15)
        )
        self.assertEqual(str(obs.price), "9.9900")
        self.assertEqual(MarketPriceObservation.objects.filter(observation_date=date(2026, 6, 15)).count(), 1)

    def test_anomaly_flagged_not_dropped(self):
        ingest_daily_prices(items=[self.item], start=self.start, end=self.end, client=self.client)
        spike = MarketPriceObservation.objects.get(observation_date=date(2026, 6, 17))
        self.assertEqual(spike.quality_flag, "anomaly_jump")
        # 삭제하지 않고 보존
        self.assertTrue(MarketPriceObservation.objects.filter(pk=spike.pk).exists())

    def test_nonpositive_price_skipped(self):
        ingest_daily_prices(items=[self.item], start=self.start, end=self.end, client=self.client)
        self.assertFalse(
            MarketPriceObservation.objects.filter(observation_date=date(2026, 6, 18)).exists()
        )

    def test_run_records_params_and_time_fields(self):
        run = ingest_daily_prices(items=[self.item], start=self.start, end=self.end, client=self.client)
        self.assertEqual(run.params["start"], "2026-06-15")
        self.assertEqual(run.params["item_codes"], ["ONION"])
        self.assertIsNotNone(run.finished_at)
        obs = MarketPriceObservation.objects.first()
        # 시간 구분: 수집시각과 관측일이 별개로 보존
        self.assertIsNotNone(obs.collected_at)
        self.assertIsNotNone(obs.first_collected_at)
        self.assertEqual(obs.first_collected_at, obs.collected_at)

    def test_first_collected_at_preserved_on_update(self):
        ingest_daily_prices(items=[self.item], start=self.start, end=date(2026, 6, 15), client=self.client)
        obs1 = MarketPriceObservation.objects.get(observation_date=date(2026, 6, 15))
        original_first = obs1.first_collected_at
        changed = {"245": [dict(FIXTURE["245"][0], price="5.55")]}
        ingest_daily_prices(items=[self.item], start=self.start, end=date(2026, 6, 15),
                            client=FixtureKamisDailyClient(data=changed))
        obs1.refresh_from_db()
        # 최초 수집 시각은 갱신돼도 보존(point-in-time 추적)
        self.assertEqual(obs1.first_collected_at, original_first)


class FixtureClientTests(TestCase):
    def test_filters_by_date_range(self):
        item = MarketItem.objects.create(code="ONION", name="양파", source_item_code="245")
        client = FixtureKamisDailyClient(data=FIXTURE)
        rows = client.fetch_daily(item, date(2026, 6, 16), date(2026, 6, 17))
        dates = sorted(r["observation_date"] for r in rows)
        self.assertEqual(dates, ["2026-06-16", "2026-06-17"])

    def test_unknown_item_returns_empty(self):
        item = MarketItem.objects.create(code="GARLIC", name="마늘", source_item_code="999")
        client = FixtureKamisDailyClient(data=FIXTURE)
        self.assertEqual(client.fetch_daily(item, date(2026, 6, 1), date(2026, 6, 30)), [])
