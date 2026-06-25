"""기상 관측·예보 수집 커맨드 (항목 5).

    python manage.py ingest_weather --seed-stations --start 2026-06-15 --end 2026-06-17
    python manage.py ingest_weather --forecast        # 예보 스냅샷만
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from weather.models import WeatherStation
from weather.ingestion.service import (
    FixtureForecastClient, get_asos_client,
    ingest_weather_observations, ingest_forecast_snapshots,
)

DEMO_STATIONS = [
    dict(station_id="133", name="대전", source="asos", latitude=36.37, longitude=127.37),
    dict(station_id="159", name="부산", source="asos", latitude=35.10, longitude=129.03),
    # 양파·배추 주산지 관측소
    dict(station_id="165", name="목포", source="asos", latitude=34.82, longitude=126.38),
    dict(station_id="105", name="강릉", source="asos", latitude=37.75, longitude=128.89),
]


class Command(BaseCommand):
    help = "기상 관측(ASOS) 및 예보 스냅샷을 수집합니다."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--start", default=None)
        parser.add_argument("--end", default=None)
        parser.add_argument("--seed-stations", action="store_true")
        parser.add_argument("--forecast", action="store_true", help="예보 스냅샷도 수집")

    def handle(self, *args, **opts):
        if opts["seed_stations"]:
            for s in DEMO_STATIONS:
                WeatherStation.objects.update_or_create(station_id=s["station_id"], defaults=s)
            self.stdout.write(self.style.SUCCESS(f"✓ 관측소 {len(DEMO_STATIONS)}개 등록"))

        end = date.fromisoformat(opts["end"]) if opts["end"] else timezone.localdate()
        start = date.fromisoformat(opts["start"]) if opts["start"] else end - timedelta(days=opts["days"])

        client = get_asos_client()
        self.stdout.write(f"ASOS 클라이언트: {type(client).__name__} / {start} ~ {end}")
        run = ingest_weather_observations(start=start, end=end, client=client)
        self.stdout.write(self.style.SUCCESS(
            f"[관측 {run.status}] fetched={run.fetched_count} created={run.created_count} "
            f"updated={run.updated_count}"
        ))

        if opts["forecast"]:
            frun = ingest_forecast_snapshots(client=FixtureForecastClient())
            self.stdout.write(self.style.SUCCESS(
                f"[예보 {frun.status}] fetched={frun.fetched_count} created={frun.created_count} "
                f"updated={frun.updated_count}"
            ))
