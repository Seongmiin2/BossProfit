"""기상 관측·예보 수집 테스트 (항목 5).

핵심: 예보 스냅샷은 issued_at 이 다르면 같은 valid_at 이라도 별개 행으로 보존돼야 한다
(point-in-time 평가에서 미래 예보 누수를 막기 위함).
"""
from datetime import date, datetime

from django.test import TestCase
from django.utils import timezone

from market.models import IngestionRun
from weather.models import WeatherStation, WeatherObservation, WeatherForecastSnapshot
from weather.ingestion.service import (
    FixtureAsosClient, FixtureForecastClient,
    ingest_weather_observations, ingest_forecast_snapshots,
)

ASOS = {
    "133": [
        {"observed_date": "2026-06-15", "variables": {"tavg": 23.1, "rain": 0.0}, "raw_ref": "a"},
        {"observed_date": "2026-06-16", "variables": {"tavg": 24.0, "rain": 2.5}, "raw_ref": "b"},
    ],
}

FORECAST = [
    {"provider": "kma_short", "issued_at": "2026-06-17T05:00:00+09:00", "valid_at": "2026-06-18",
     "station_id": "133", "variables": {"tmax": 34.0}, "raw_ref": "am"},
    # 같은 valid_at, 다른 issued_at → 별개 스냅샷
    {"provider": "kma_short", "issued_at": "2026-06-17T17:00:00+09:00", "valid_at": "2026-06-18",
     "station_id": "133", "variables": {"tmax": 35.0}, "raw_ref": "pm"},
]


class WeatherObservationTests(TestCase):
    def setUp(self):
        self.station = WeatherStation.objects.create(station_id="133", name="대전")

    def test_creates_observations(self):
        run = ingest_weather_observations(
            stations=[self.station], start=date(2026, 6, 15), end=date(2026, 6, 16),
            client=FixtureAsosClient(data=ASOS),
        )
        self.assertEqual(run.status, "success")
        self.assertEqual(WeatherObservation.objects.count(), 2)
        obs = WeatherObservation.objects.get(observed_date=date(2026, 6, 15))
        self.assertEqual(obs.variables["tavg"], 23.1)

    def test_idempotent(self):
        for _ in range(2):
            ingest_weather_observations(stations=[self.station], start=date(2026, 6, 15),
                                        end=date(2026, 6, 16), client=FixtureAsosClient(data=ASOS))
        self.assertEqual(WeatherObservation.objects.count(), 2)


class ForecastSnapshotTests(TestCase):
    def setUp(self):
        self.station = WeatherStation.objects.create(station_id="133", name="대전")

    def test_same_valid_at_different_issued_at_kept_separate(self):
        run = ingest_forecast_snapshots(client=FixtureForecastClient(data=FORECAST))
        self.assertEqual(run.status, "success")
        snaps = WeatherForecastSnapshot.objects.filter(valid_at=date(2026, 6, 18))
        # 발행시각이 다른 두 예보가 모두 보존 (누수 방지의 전제)
        self.assertEqual(snaps.count(), 2)
        # KST 기준 발행시각 05시/17시 (USE_TZ=True 이므로 localtime 변환 후 비교)
        issued = sorted(timezone.localtime(s.issued_at).hour for s in snaps)
        self.assertEqual(issued, [5, 17])

    def test_idempotent(self):
        for _ in range(2):
            ingest_forecast_snapshots(client=FixtureForecastClient(data=FORECAST))
        self.assertEqual(WeatherForecastSnapshot.objects.count(), 2)

    def test_point_in_time_filter(self):
        ingest_forecast_snapshots(client=FixtureForecastClient(data=FORECAST))
        # as_of=06-17 12:00 기준이면 오전 발행 예보만 보여야 한다.
        as_of = datetime.fromisoformat("2026-06-17T12:00:00+09:00")
        visible = WeatherForecastSnapshot.objects.filter(
            valid_at=date(2026, 6, 18), issued_at__lte=as_of
        )
        self.assertEqual(visible.count(), 1)
        self.assertEqual(visible.first().variables["tmax"], 34.0)
