"""KAMIS 일별 가격 수집 서비스.

핵심:
- 멱등 upsert: (source, item, observation_date, region, market_type, grade, unit) 자연키로
  같은 범위를 다시 수집해도 중복 행이 생기지 않는다. 값이 바뀌면 갱신(KAMIS 수정 반영).
- 품질검사: 0/음수, 전일 대비 비정상 급등락, 결측을 플래그한다. 이상치는 삭제하지 않는다.
- run 추적: 모든 적재는 IngestionRun에 연결되고 카운트/상태가 기록된다.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional

from django.db import transaction
from django.utils import timezone

from ..models import IngestionRun, MarketItem, MarketPriceObservation
from .clients import BaseKamisDailyClient, get_daily_client

# 전일 대비 이 비율을 넘는 변화는 급등락 의심으로 플래그(삭제하지 않음).
ANOMALY_JUMP_RATE = 0.5  # 50%


def _to_decimal(value) -> Optional[Decimal]:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return d


def _quality_flag(price: Decimal, prev_price: Optional[Decimal]) -> str:
    if prev_price and prev_price > 0:
        change = abs(price - prev_price) / prev_price
        if change >= Decimal(str(ANOMALY_JUMP_RATE)):
            return "anomaly_jump"
    return "ok"


@transaction.atomic
def _upsert_observation(item, row, source, collected_at, run, prev_price):
    """단일 관측을 upsert. (created: bool|None, quality_flag) 반환.

    KAMIS는 미조사일을 0/'-'로 표기하므로 0 이하 가격은 결측으로 보고 skip 한다.
    """
    price = _to_decimal(row.get("price"))
    if price is None or price <= 0:
        return None, "skip"

    flag = _quality_flag(price, prev_price)
    natural = dict(
        source=source,
        item=item,
        observation_date=date.fromisoformat(row["observation_date"]),
        region=row.get("region", ""),
        market_type=row.get("market_type", "retail"),
        grade=row.get("grade", ""),
        unit=row.get("unit", item.standard_unit),
    )
    defaults = dict(
        price=price,
        raw_ref=row.get("raw_ref", ""),
        collected_at=collected_at,
        quality_flag=flag,
        ingestion_run=run,
    )
    obj, created = MarketPriceObservation.objects.update_or_create(
        **natural, defaults=defaults
    )
    if created:
        obj.first_collected_at = collected_at
        obj.save(update_fields=["first_collected_at"])
    return created, flag


def ingest_daily_prices(
    items: Optional[Iterable[MarketItem]] = None,
    start: Optional[date] = None,
    end: Optional[date] = None,
    client: Optional[BaseKamisDailyClient] = None,
    code_version: str = "",
) -> IngestionRun:
    """대상 품목의 [start, end] 일별 가격을 수집·정규화·upsert 한다."""
    end = end or timezone.localdate()
    start = start or (end - timedelta(days=7))
    client = client or get_daily_client()
    source = client.source
    if items is None:
        items = MarketItem.objects.filter(is_active=True)
    items = list(items)

    run = IngestionRun.objects.create(
        source="kamis_daily",
        status="running",
        params={"start": start.isoformat(), "end": end.isoformat(),
                "item_codes": [i.code for i in items]},
        code_version=code_version,
    )

    had_error = False
    try:
        for item in items:
            try:
                rows = client.fetch_daily(item, start, end)
            except Exception as exc:  # 개별 품목 실패는 부분성공으로 흡수
                had_error = True
                run.skipped_count += 1
                run.error += f"[{item.code}] fetch 실패: {exc}\n"
                continue

            run.fetched_count += len(rows)
            # 전일 대비 비교를 위해 날짜 오름차순 처리
            rows = sorted(rows, key=lambda r: r["observation_date"])
            prev_price = None
            collected_at = timezone.now()
            for row in rows:
                created, flag = _upsert_observation(
                    item, row, source, collected_at, run, prev_price
                )
                if created is None:
                    run.skipped_count += 1
                    continue
                if created:
                    run.created_count += 1
                else:
                    run.updated_count += 1
                if flag != "ok":
                    run.quality_issue_count += 1
                prev_price = _to_decimal(row.get("price"))
    except Exception as exc:
        run.mark("failed", error=str(exc))
        return run

    status = "partial" if had_error else "success"
    run.mark(status)
    return run
