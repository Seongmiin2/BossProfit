"""시장 가격 수집 실행 커맨드.

사용법:
    python manage.py ingest_market --days 7
    python manage.py ingest_market --start 2026-06-15 --end 2026-06-20
    python manage.py ingest_market --fixture market/fixtures/kamis_daily_sample.json
    python manage.py ingest_market --seed-items   # 데모 품목 등록 후 수집

API 키(KAMIS_CERT_KEY/ID)가 없으면 fixture 클라이언트로 동작한다.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from market.models import MarketItem
from market.ingestion.clients import FixtureKamisDailyClient, get_daily_client
from market.ingestion.service import ingest_daily_prices


DEMO_ITEMS = [
    dict(code="ONION", name="양파", category="채소", standard_unit="g",
         source="kamis", source_category_code="200", source_item_code="245"),
    dict(code="NAPA_CABBAGE", name="배추", category="채소", standard_unit="g",
         source="kamis", source_category_code="200", source_item_code="211"),
]


class Command(BaseCommand):
    help = "KAMIS 일별 가격을 수집해 MarketPriceObservation에 멱등 적재합니다."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--start", default=None, help="YYYY-MM-DD")
        parser.add_argument("--end", default=None, help="YYYY-MM-DD")
        parser.add_argument("--fixture", default=None, help="fixture JSON 경로")
        parser.add_argument(
            "--seed-items", action="store_true",
            help="데모 품목(양파·배추)을 먼저 등록",
        )

    def handle(self, *args, **opts):
        if opts["seed_items"]:
            for d in DEMO_ITEMS:
                MarketItem.objects.update_or_create(code=d["code"], defaults=d)
            self.stdout.write(self.style.SUCCESS(f"✓ 데모 품목 {len(DEMO_ITEMS)}개 등록"))

        end = date.fromisoformat(opts["end"]) if opts["end"] else timezone.localdate()
        start = (
            date.fromisoformat(opts["start"]) if opts["start"]
            else end - timedelta(days=opts["days"])
        )

        client = FixtureKamisDailyClient(opts["fixture"]) if opts["fixture"] else get_daily_client()
        self.stdout.write(
            f"수집: {client.__class__.__name__} / {start} ~ {end}"
        )

        run = ingest_daily_prices(start=start, end=end, client=client)
        self.stdout.write(self.style.SUCCESS(
            f"[{run.status}] fetched={run.fetched_count} "
            f"created={run.created_count} updated={run.updated_count} "
            f"skipped={run.skipped_count} quality_issues={run.quality_issue_count}"
        ))
        if run.error:
            self.stdout.write(self.style.WARNING(run.error))
