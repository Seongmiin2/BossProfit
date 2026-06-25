"""데이터 품질·누락률 보고 커맨드 (항목 7).

    python manage.py data_quality_report --start 2026-06-15 --end 2026-06-18
"""
import json
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from market.quality import full_report


class Command(BaseCommand):
    help = "수집 데이터의 커버리지·결측률·품질 플래그 분포를 보고합니다."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--start", default=None)
        parser.add_argument("--end", default=None)
        parser.add_argument("--json", action="store_true", help="JSON으로 출력")

    def handle(self, *args, **opts):
        end = date.fromisoformat(opts["end"]) if opts["end"] else timezone.localdate()
        start = date.fromisoformat(opts["start"]) if opts["start"] else end - timedelta(days=opts["days"])
        report = full_report(start, end)

        if opts["json"]:
            self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
            return

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n데이터 품질 보고 {start} ~ {end}"
        ))
        for section, rows in (("가격", report["price"]), ("도매", report["wholesale"])):
            self.stdout.write(f"\n[{section}]")
            for r in rows:
                self.stdout.write(
                    f"  {r['item_name']:8} 관측 {r['observed_days']}/{r['expected_days']}일 "
                    f"결측률 {r['missing_rate']:.0%} 행 {r['row_count']}"
                    + (f" 플래그 {r['flags']}" if r.get('flags') else "")
                )
        self.stdout.write("\n[기상]")
        for r in report["weather"]:
            self.stdout.write(
                f"  {r['station_name']:8} 관측 {r['observed_days']}/{r['expected_days']}일 "
                f"결측률 {r['missing_rate']:.0%} 행 {r['row_count']}"
            )
