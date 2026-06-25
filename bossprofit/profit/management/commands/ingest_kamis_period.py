from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from profit.integrations.base import payload_sha256, redact_params
from profit.integrations.kamis import fetch_period_product, iter_period_prices
from profit.models import (
    IngestionRun,
    MarketItem,
    MarketPriceObservation,
    RawSourcePayload,
)


class Command(BaseCommand):
    help = "KAMIS 기간별 품목 일평균 가격을 예측용 연속 시계열로 저장합니다."

    def add_arguments(self, parser):
        parser.add_argument("--start-date", required=True)
        parser.add_argument("--end-date", required=True)
        parser.add_argument("--category-code", required=True)
        parser.add_argument("--item-code", required=True)
        parser.add_argument("--kind-code", required=True)
        parser.add_argument("--rank-code", required=True)
        parser.add_argument("--country-code", default="1101")
        parser.add_argument("--product-class-code", default="01")

    def handle(self, *args, **options):
        start_date = date.fromisoformat(options["start_date"])
        end_date = date.fromisoformat(options["end_date"])
        market_item_code = (
            f"KAMIS:{options['item_code']}:{options['kind_code']}:"
            f"{options['rank_code']}"
        )
        item = MarketItem.objects.filter(code=market_item_code).first()
        if item is None:
            raise CommandError(
                f"먼저 일별 카테고리 수집으로 품목을 등록하세요: {market_item_code}"
            )
        run = IngestionRun.objects.create(
            source="KAMIS",
            dataset="periodProductList",
            observation_cutoff=timezone.now(),
            requested_params={
                key: options[key]
                for key in (
                    "start_date",
                    "end_date",
                    "category_code",
                    "item_code",
                    "kind_code",
                    "rank_code",
                    "country_code",
                    "product_class_code",
                )
            },
            source_version="KAMIS_OPEN_API",
        )
        try:
            payload, url, params = fetch_period_product(
                start_date=start_date,
                end_date=end_date,
                category_code=options["category_code"],
                item_code=options["item_code"],
                kind_code=options["kind_code"],
                rank_code=options["rank_code"],
                country_code=options["country_code"],
                product_class_code=options["product_class_code"],
            )
            collected_at = timezone.now()
            raw = RawSourcePayload.objects.create(
                ingestion_run=run,
                source_url=url.split("?", 1)[0],
                request_params=redact_params(params),
                payload=payload,
                payload_sha256=payload_sha256(payload),
                collected_at=collected_at,
            )
            created = updated = 0
            rows = list(iter_period_prices(payload))
            for source_row, observed_date, price in rows:
                _, was_created = MarketPriceObservation.objects.update_or_create(
                    item=item,
                    observed_date=observed_date,
                    source="KAMIS_PERIOD",
                    region_code="AVERAGE",
                    market_type=(
                        "RETAIL"
                        if options["product_class_code"] == "01"
                        else "WHOLESALE"
                    ),
                    unit=item.unit,
                    defaults={
                        "region_name": "평균",
                        "price": price,
                        "source_item_code": options["item_code"],
                        "source_unique_key": (
                            f"{market_item_code}:{observed_date}:AVERAGE:"
                            f"{options['product_class_code']}"
                        ),
                        "raw_payload": raw,
                        "collected_at": collected_at,
                        "is_demo": False,
                    },
                )
                created += int(was_created)
                updated += int(not was_created)
            run.status = "SUCCEEDED"
            run.fetched_count = len(rows)
            run.created_count = created
            run.updated_count = updated
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
                "finished_at",
            ]
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{item.name} 기간시세: 생성 {created}, 갱신 {updated}"
            )
        )
