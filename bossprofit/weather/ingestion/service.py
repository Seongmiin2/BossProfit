"""기상 관측·예보 수집 (항목 5).

- 관측(ASOS/농업기상): station×observed_date 자연키 멱등 upsert.
- 예보 스냅샷: provider×issued_at×valid_at×(region|station) 자연키.
  issued_at 을 그대로 보존해 point-in-time 평가에서 미래 예보 누수를 막는다.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

from django.db import transaction
from django.utils import timezone

from market.models import IngestionRun
from ..models import WeatherStation, WeatherObservation, WeatherForecastSnapshot

_FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"


# ===== 관측 =====

class BaseAsosClient:
    source = "asos"

    def fetch(self, station, start: date, end: date) -> list[dict]:  # pragma: no cover
        raise NotImplementedError


class FixtureAsosClient(BaseAsosClient):
    """fixture: { "<station_id>": [ {observed_date, variables, raw_ref}, ... ] }."""

    def __init__(self, fixture_path=None, data=None):
        if data is not None:
            self._data = data
        else:
            path = Path(fixture_path) if fixture_path else _FIXTURE_DIR / "asos_sample.json"
            with open(path, encoding="utf-8") as f:
                self._data = json.load(f)

    def fetch(self, station, start, end):
        rows = self._data.get(station.station_id, [])
        return [r for r in rows if start <= date.fromisoformat(r["observed_date"]) <= end]


@transaction.atomic
def _upsert_obs(station, row, source, collected_at, run):
    natural = dict(
        source=source, station=station,
        observed_date=date.fromisoformat(row["observed_date"]),
    )
    obj, created = WeatherObservation.objects.update_or_create(
        **natural,
        defaults=dict(
            variables=row.get("variables", {}),
            quality_flag=row.get("quality_flag", "ok"),
            raw_ref=row.get("raw_ref", ""),
            collected_at=collected_at, ingestion_run=run,
        ),
    )
    if created:
        obj.first_collected_at = collected_at
        obj.save(update_fields=["first_collected_at"])
    return created


def ingest_weather_observations(
    stations: Optional[Iterable[WeatherStation]] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    client: Optional[BaseAsosClient] = None,
    code_version: str = "",
) -> IngestionRun:
    end = end or timezone.localdate()
    start = start or (end - timedelta(days=7))
    client = client or FixtureAsosClient()
    if stations is None:
        stations = WeatherStation.objects.filter(is_active=True)
    stations = list(stations)

    run = IngestionRun.objects.create(
        source="weather_asos", status="running",
        params={"start": start.isoformat(), "end": end.isoformat(),
                "stations": [s.station_id for s in stations]},
        code_version=code_version,
    )
    had_error = False
    try:
        for station in stations:
            try:
                rows = client.fetch(station, start, end)
            except Exception as exc:
                had_error = True
                run.skipped_count += 1
                run.error += f"[{station.station_id}] fetch 실패: {exc}\n"
                continue
            run.fetched_count += len(rows)
            collected_at = timezone.now()
            for row in rows:
                created = _upsert_obs(station, row, client.source, collected_at, run)
                run.created_count += 1 if created else 0
                run.updated_count += 0 if created else 1
    except Exception as exc:
        run.mark("failed", error=str(exc))
        return run
    run.mark("partial" if had_error else "success")
    return run


# ===== 예보 스냅샷 =====

class BaseForecastClient:
    source = "kma"

    def fetch(self) -> list[dict]:  # pragma: no cover
        raise NotImplementedError


class FixtureForecastClient(BaseForecastClient):
    """fixture: [ {provider, issued_at, valid_at, station_id|region_code, variables, raw_ref}, ... ]."""

    def __init__(self, fixture_path=None, data=None):
        if data is not None:
            self._data = data
        else:
            path = Path(fixture_path) if fixture_path else _FIXTURE_DIR / "forecast_sample.json"
            with open(path, encoding="utf-8") as f:
                self._data = json.load(f)

    def fetch(self):
        return self._data


@transaction.atomic
def _upsert_forecast(row, source, collected_at, run, station_map):
    station = station_map.get(row.get("station_id")) if row.get("station_id") else None
    natural = dict(
        provider=row["provider"],
        issued_at=datetime.fromisoformat(row["issued_at"]),
        valid_at=date.fromisoformat(row["valid_at"]),
        region=None,
        station=station,
    )
    obj, created = WeatherForecastSnapshot.objects.update_or_create(
        **natural,
        defaults=dict(
            variables=row.get("variables", {}),
            source=source, raw_ref=row.get("raw_ref", ""),
            collected_at=collected_at, ingestion_run=run,
        ),
    )
    return created


def ingest_forecast_snapshots(
    client: Optional[BaseForecastClient] = None,
    code_version: str = "",
) -> IngestionRun:
    client = client or FixtureForecastClient()
    rows = client.fetch()
    station_map = {s.station_id: s for s in WeatherStation.objects.all()}

    run = IngestionRun.objects.create(
        source="weather_forecast", status="running",
        params={"count": len(rows)}, code_version=code_version,
    )
    try:
        collected_at = timezone.now()
        run.fetched_count = len(rows)
        for row in rows:
            created = _upsert_forecast(row, client.source, collected_at, run, station_map)
            run.created_count += 1 if created else 0
            run.updated_count += 0 if created else 1
    except Exception as exc:
        run.mark("failed", error=str(exc))
        return run
    run.mark("success")
    return run
