"""도매시장 경락가격·거래량 수집 (항목 4).

가격 수집과 동일한 원칙: 멱등 upsert, run 추적, 이상치 플래그(삭제 안 함).
거래량(volume)을 함께 보존해 수급 선행신호로 사용한다.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Optional

from django.db import transaction
from django.utils import timezone

from ..models import IngestionRun, MarketItem, WholesaleAuctionObservation

ANOMALY_JUMP_RATE = 0.5


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


class BaseWholesaleClient:
    source = "wholesale"

    def fetch(self, item, start: date, end: date) -> list[dict]:  # pragma: no cover
        raise NotImplementedError


class FixtureWholesaleClient(BaseWholesaleClient):
    """fixture: { "<source_item_code|code>": [ {정규화 행}, ... ] }.

    행 스키마: observation_date, market, origin, grade, unit, price, volume, raw_ref
    """

    def __init__(self, fixture_path: str | Path | None = None, data: dict | None = None):
        if data is not None:
            self._data = data
        else:
            path = Path(fixture_path) if fixture_path else (
                Path(__file__).resolve().parent.parent / "fixtures" / "wholesale_sample.json"
            )
            with open(path, encoding="utf-8") as f:
                self._data = json.load(f)

    def fetch(self, item, start, end):
        rows = self._data.get(item.source_item_code) or self._data.get(item.code) or []
        return [r for r in rows if start <= date.fromisoformat(r["observation_date"]) <= end]


def _quality_flag(price, prev_price):
    if prev_price and prev_price > 0:
        if abs(price - prev_price) / prev_price >= Decimal(str(ANOMALY_JUMP_RATE)):
            return "anomaly_jump"
    return "ok"


@transaction.atomic
def _upsert(item, row, source, collected_at, run, prev_price):
    price = _to_decimal(row.get("price"))
    if price is None or price <= 0:
        return None, "skip"
    volume = _to_decimal(row.get("volume"))
    natural = dict(
        source=source, item=item,
        observation_date=date.fromisoformat(row["observation_date"]),
        market=row.get("market", ""), origin=row.get("origin", ""),
        grade=row.get("grade", ""), unit=row.get("unit", item.standard_unit),
    )
    obj, created = WholesaleAuctionObservation.objects.update_or_create(
        **natural,
        defaults=dict(
            price=price, volume=volume, raw_ref=row.get("raw_ref", ""),
            collected_at=collected_at, quality_flag=_quality_flag(price, prev_price),
            ingestion_run=run,
        ),
    )
    if created:
        obj.first_collected_at = collected_at
        obj.save(update_fields=["first_collected_at"])
    return created, obj.quality_flag


def ingest_wholesale_auction(
    items: Optional[Iterable[MarketItem]] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    client: Optional[BaseWholesaleClient] = None,
    code_version: str = "",
) -> IngestionRun:
    end = end or timezone.localdate()
    start = start or (end - timedelta(days=7))
    client = client or FixtureWholesaleClient()
    if items is None:
        items = MarketItem.objects.filter(is_active=True)
    items = list(items)

    run = IngestionRun.objects.create(
        source="wholesale_auction", status="running",
        params={"start": start.isoformat(), "end": end.isoformat(),
                "item_codes": [i.code for i in items]},
        code_version=code_version,
    )
    had_error = False
    try:
        for item in items:
            try:
                rows = client.fetch(item, start, end)
            except Exception as exc:
                had_error = True
                run.skipped_count += 1
                run.error += f"[{item.code}] fetch 실패: {exc}\n"
                continue
            run.fetched_count += len(rows)
            rows = sorted(rows, key=lambda r: r["observation_date"])
            prev_price = None
            collected_at = timezone.now()
            for row in rows:
                created, flag = _upsert(item, row, client.source, collected_at, run, prev_price)
                if created is None:
                    run.skipped_count += 1
                    continue
                run.created_count += 1 if created else 0
                run.updated_count += 0 if created else 1
                if flag != "ok":
                    run.quality_issue_count += 1
                prev_price = _to_decimal(row.get("price"))
    except Exception as exc:
        run.mark("failed", error=str(exc))
        return run
    run.mark("partial" if had_error else "success")
    return run
