from datetime import date, datetime
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from profit.integrations.base import payload_sha256, redact_params
from profit.integrations.data_go_kr import (
    fetch_wholesale_auctions,
    response_items,
)
from profit.models import (
    IngestionRun,
    MarketItem,
    RawSourcePayload,
    WholesaleAuctionObservation,
)


class Command(BaseCommand):
    help = "전국 공영도매시장 실시간 경매정보를 페이지 단위로 수집합니다."

    def add_arguments(self, parser):
        parser.add_argument("--date", required=True)
        parser.add_argument("--pages", type=int, default=1)
        parser.add_argument("--rows", type=int, default=1000)
        parser.add_argument("--market-code")
        parser.add_argument("--large-code")
        parser.add_argument("--middle-code")
        parser.add_argument("--small-code")

    def handle(self, *args, **options):
        trade_date = date.fromisoformat(options["date"])
        run = IngestionRun.objects.create(
            source="AT_WHOLESALE",
            dataset="REALTIME_AUCTIONS",
            observation_cutoff=timezone.now(),
            requested_params={
                key: options[key]
                for key in (
                    "date",
                    "pages",
                    "rows",
                    "market_code",
                    "large_code",
                    "middle_code",
                    "small_code",
                )
            },
            source_version="katRealTime2/trades2",
        )
        fetched = created = updated = rejected = 0
        try:
            for page in range(1, options["pages"] + 1):
                payload, url, params = fetch_wholesale_auctions(
                    trade_date=trade_date,
                    page=page,
                    rows=options["rows"],
                    market_code=options["market_code"],
                    large_code=options["large_code"],
                    middle_code=options["middle_code"],
                    small_code=options["small_code"],
                )
                rows = response_items(payload)
                collected_at = timezone.now()
                raw = RawSourcePayload.objects.create(
                    ingestion_run=run,
                    source_url=url.split("?", 1)[0],
                    request_params=redact_params(params),
                    payload=payload,
                    payload_sha256=payload_sha256(payload),
                    collected_at=collected_at,
                )
                for row in rows:
                    fetched += 1
                    source_record_id = ":".join(
                        str(row.get(key) or "")
                        for key in (
                            "trd_clcln_ymd",
                            "whsl_mrkt_cd",
                            "corp_cd",
                            "spm_no",
                            "auctn_seq",
                            "corp_gds_cd",
                            "scsbd_dt",
                        )
                    )
                    try:
                        auctioned_at = timezone.make_aware(
                            datetime.strptime(
                                row["scsbd_dt"],
                                "%Y-%m-%d %H:%M:%S",
                            )
                        )
                        volume = Decimal(str(row["qty"]))
                        price = Decimal(str(row["scsbd_prc"]))
                    except (KeyError, ValueError, TypeError):
                        rejected += 1
                        continue
                    source_name = str(row.get("corp_gds_item_nm") or "").strip()
                    mapped_item = (
                        MarketItem.objects.filter(name=source_name).first()
                        if source_name
                        else None
                    )
                    _, was_created = WholesaleAuctionObservation.objects.update_or_create(
                        source="AT_WHOLESALE",
                        source_record_id=source_record_id,
                        defaults={
                            "auctioned_at": auctioned_at,
                            "market_code": str(row.get("whsl_mrkt_cd") or ""),
                            "market_name": str(row.get("whsl_mrkt_nm") or ""),
                            "item": mapped_item,
                            "source_item_code": str(
                                row.get("corp_gds_cd")
                                or row.get("gds_sclsf_cd")
                                or ""
                            ),
                            "source_item_name": source_name,
                            "origin_name": str(row.get("plor_nm") or ""),
                            "grade": "",
                            "unit": (
                                f"{row.get('unit_qty', '')}{row.get('unit_nm', '')}"
                            ),
                            "volume": volume,
                            "price": price,
                            "collected_at": collected_at,
                            "raw_payload": raw,
                        },
                    )
                    created += int(was_created)
                    updated += int(not was_created)
                if not rows:
                    break
            run.status = "SUCCEEDED"
            run.fetched_count = fetched
            run.created_count = created
            run.updated_count = updated
            run.rejected_count = rejected
        except Exception as exc:
            run.status = "FAILED"
            run.error_message = str(exc)
            run.finished_at = timezone.now()
            run.save(update_fields=["status", "error_message", "finished_at"])
            raise CommandError(str(exc)) from exc
        run.finished_at = timezone.now()
        run.save(
            update_fields=[
                "status",
                "fetched_count",
                "created_count",
                "updated_count",
                "rejected_count",
                "finished_at",
            ]
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"도매경매 {trade_date}: 조회 {fetched}, 생성 {created}, "
                f"갱신 {updated}, 제외 {rejected}"
            )
        )
