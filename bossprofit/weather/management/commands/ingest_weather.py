"""기상 관측·예보 수집 커맨드 (항목 5).

    python manage.py ingest_weather --seed-stations --start 2026-06-15 --end 2026-06-17
    python manage.py ingest_weather --forecast        # 예보 스냅샷만
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from weather.models import WeatherStation, WeatherStationMapping
from weather.ingestion.service import (
    get_asos_client, get_agri_client, get_forecast_client, get_mid_forecast_client,
    ingest_weather_observations, ingest_forecast_snapshots,
)

DEMO_STATIONS = [
    dict(station_id="133", name="대전", source="asos", latitude=36.37, longitude=127.37),
    dict(station_id="159", name="부산", source="asos", latitude=35.10, longitude=129.03),
    # 양파·배추 주산지 관측소
    dict(station_id="165", name="목포", source="asos", latitude=34.82, longitude=126.38),
    dict(station_id="105", name="강릉", source="asos", latitude=37.75, longitude=128.89),
]
# 농업기상(농진청) 상세관측 지점 — 토양수분 제공. 강원 주산지에 매핑.
AGRI_STATION = dict(station_id="233852A002", name="정선군 임계면", source="aws_agri",
                    latitude=37.51, longitude=128.71)
AGRI_REGION_CODE = "42"  # 강원


class Command(BaseCommand):
    help = "기상 관측(ASOS) 및 예보 스냅샷을 수집합니다."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--start", default=None)
        parser.add_argument("--end", default=None)
        parser.add_argument("--seed-stations", action="store_true")
        parser.add_argument("--forecast", action="store_true", help="예보 스냅샷도 수집")
        parser.add_argument("--agri", action="store_true", help="농업기상(토양수분) 수집")

    def handle(self, *args, **opts):
        if opts["seed_stations"]:
            for s in DEMO_STATIONS:
                WeatherStation.objects.update_or_create(station_id=s["station_id"], defaults=s)
            self.stdout.write(self.style.SUCCESS(f"✓ 관측소 {len(DEMO_STATIONS)}개 등록"))

        end = date.fromisoformat(opts["end"]) if opts["end"] else timezone.localdate()
        start = date.fromisoformat(opts["start"]) if opts["start"] else end - timedelta(days=opts["days"])

        # ASOS는 source=asos 관측소만 (농업기상 지점이 섞이지 않게)
        asos_stations = WeatherStation.objects.filter(is_active=True, source="asos")
        client = get_asos_client()
        self.stdout.write(f"ASOS 클라이언트: {type(client).__name__} / {start} ~ {end}")
        run = ingest_weather_observations(stations=asos_stations, start=start, end=end, client=client)
        self.stdout.write(self.style.SUCCESS(
            f"[관측 {run.status}] fetched={run.fetched_count} created={run.created_count} "
            f"updated={run.updated_count}"
        ))

        if opts["agri"]:
            self._ingest_agri(start, end)

        if opts["forecast"]:
            fclient = get_forecast_client()
            self.stdout.write(f"단기예보 클라이언트: {type(fclient).__name__}")
            frun = ingest_forecast_snapshots(client=fclient)
            self.stdout.write(self.style.SUCCESS(
                f"[단기예보 {frun.status}] fetched={frun.fetched_count} created={frun.created_count} "
                f"updated={frun.updated_count}"
            ))
            mclient = get_mid_forecast_client()
            if mclient is not None:
                self.stdout.write(f"중기예보 클라이언트: {type(mclient).__name__}")
                mrun = ingest_forecast_snapshots(client=mclient)
                self.stdout.write(self.style.SUCCESS(
                    f"[중기예보 {mrun.status}] fetched={mrun.fetched_count} created={mrun.created_count} "
                    f"updated={mrun.updated_count}"
                ))

    def _ingest_agri(self, start, end):
        from market.models import ProductionRegion
        aclient = get_agri_client()
        if aclient is None:
            self.stdout.write(self.style.WARNING("농업기상: DATA_GO_KR_API_KEY 없음 — 건너뜀"))
            return
        # 농업기상 관측소 등록 + 강원 주산지 매핑(토양수분이 강원 품목 기상에 결합)
        station, _ = WeatherStation.objects.update_or_create(
            station_id=AGRI_STATION["station_id"], defaults=AGRI_STATION
        )
        region = ProductionRegion.objects.filter(code=AGRI_REGION_CODE).first()
        if region:
            WeatherStationMapping.objects.update_or_create(
                region=region, station=station, defaults={"weight": 1.0}
            )
        self.stdout.write(f"농업기상 클라이언트: {type(aclient).__name__} / {start} ~ {end} ({station.name})")
        run = ingest_weather_observations(
            stations=[station], start=start, end=end, client=aclient
        )
        self.stdout.write(self.style.SUCCESS(
            f"[농업기상 {run.status}] fetched={run.fetched_count} created={run.created_count} "
            f"updated={run.updated_count}"
        ))
