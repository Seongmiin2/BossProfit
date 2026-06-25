"""도매시장 경락가격·거래량 수집 커맨드 (항목 4).

    python manage.py ingest_wholesale --start 2026-06-15 --end 2026-06-18
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from market.ingestion.wholesale import FixtureWholesaleClient, ingest_wholesale_auction


class Command(BaseCommand):
    help = "도매 경락가격·거래량을 수집해 멱등 적재합니다."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--start", default=None)
        parser.add_argument("--end", default=None)
        parser.add_argument("--fixture", default=None)

    def handle(self, *args, **opts):
        end = date.fromisoformat(opts["end"]) if opts["end"] else timezone.localdate()
        start = date.fromisoformat(opts["start"]) if opts["start"] else end - timedelta(days=opts["days"])
        client = FixtureWholesaleClient(opts["fixture"]) if opts["fixture"] else FixtureWholesaleClient()
        run = ingest_wholesale_auction(start=start, end=end, client=client)
        self.stdout.write(self.style.SUCCESS(
            f"[{run.status}] fetched={run.fetched_count} created={run.created_count} "
            f"updated={run.updated_count} skipped={run.skipped_count} "
            f"quality_issues={run.quality_issue_count}"
        ))
