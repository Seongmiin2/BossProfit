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
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError

from django.conf import settings
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


def _f(v):
    """ASOS 숫자 필드 파싱. 빈값/'-'는 None."""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s == "-":
        return None
    try:
        return float(s)
    except ValueError:
        return None


class RealAsosClient(BaseAsosClient):
    """기상청 ASOS 일자료(공공데이터포털) 실연동 클라이언트.

    settings.DATA_GO_KR_API_KEY 가 필요하다. https + 브라우저 UA 로 호출하고,
    응답(response.body.items.item[])을 forecast 파이프라인이 읽는 변수명으로 정규화한다.
    """

    BASE_URL = "https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )
    # ASOS 응답 필드 → forecast WEATHER_VARS
    FIELD_MAP = {
        "avgTa": "tavg", "minTa": "tmin", "maxTa": "tmax",
        "sumRn": "rain", "avgRhm": "humidity", "sumSsHr": "sunshine",
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or getattr(settings, "DATA_GO_KR_API_KEY", "")

    def fetch(self, station, start: date, end: date) -> list[dict]:
        if not self.api_key:
            return []
        params = {
            "serviceKey": self.api_key,
            "dataType": "JSON",
            "dataCd": "ASOS",
            "dateCd": "DAY",
            "startDt": start.strftime("%Y%m%d"),
            "endDt": end.strftime("%Y%m%d"),
            "stnIds": station.station_id,
            "numOfRows": "999",
            "pageNo": "1",
        }
        url = f"{self.BASE_URL}?{urlencode(params)}"
        req = Request(url, headers={"User-Agent": self.USER_AGENT})
        try:
            with urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (URLError, ValueError, TimeoutError, OSError):
            return []

        try:
            header = payload["response"]["header"]
            if header.get("resultCode") not in ("00", 0):
                return []
            items = payload["response"]["body"]["items"]["item"]
        except (KeyError, TypeError):
            return []
        if isinstance(items, dict):
            items = [items]

        out = []
        for it in items:
            tm = it.get("tm")
            if not tm:
                continue
            variables = {}
            for src, dst in self.FIELD_MAP.items():
                v = _f(it.get(src))
                # 강수량 빈값은 무강수(0)로 본다(ASOS는 무강수일 sumRn을 비워둠)
                if v is None and dst == "rain" and str(it.get(src, "")).strip() == "":
                    v = 0.0
                if v is not None:
                    variables[dst] = v
            out.append({
                "observed_date": tm,
                "variables": variables,
                "raw_ref": f"asos:{station.station_id}:{tm}",
            })
        return out


def get_asos_client() -> BaseAsosClient:
    """키가 있으면 실 ASOS API, 없으면 fixture."""
    if getattr(settings, "DATA_GO_KR_API_KEY", ""):
        return RealAsosClient()
    return FixtureAsosClient()


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
