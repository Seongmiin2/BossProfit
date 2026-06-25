import subprocess
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from profit.integrations.base import payload_sha256, redact_params
from profit.integrations.kamis import fetch_daily_price_by_category, iter_daily_prices
from profit.models import (
    IngestionRun,
    MarketItem,
    MarketPriceObservation,
    RawSourcePayload,
)


def current_revision():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            timeout=3,
        ).strip()
    except Exception:
        return ""


class Command(BaseCommand):
    help = "KAMIS 일별 품목 가격을 원본과 함께 증분 저장합니다."

    def add_arguments(self, parser):
        parser.add_argument("--date", default=timezone.localdate().isoformat())
        parser.add_argument("--category-code", default="200")
        parser.add_argument("--country-code", default="1101")
        parser.add_argument("--product-class-code", default="01")

    def handle(self, *args, **options):
        as_of_date = date.fromisoformat(options["date"])
        safe_params = {
            "date": options["date"],
            "category_code": options["category_code"],
            "country_code": options["country_code"],
            "product_class_code": options["product_class_code"],
        }
        run = IngestionRun.objects.create(
            source="KAMIS",
            dataset="dailyPriceByCategoryList",
            requested_params=safe_params,
            observation_cutoff=timezone.now(),
            source_version="KAMIS_OPEN_API",
            code_revision=current_revision(),
        )
        try:
            payload, url, request_params = fetch_daily_price_by_category(
                regday=as_of_date,
                category_code=options["category_code"],
                country_code=options["country_code"],
                product_class_code=options["product_class_code"],
            )
            collected_at = timezone.now()
            raw_payload = RawSourcePayload.objects.create(
                ingestion_run=run,
                source_url=url.split("?", 1)[0],
                request_params=redact_params(request_params),
                payload=payload,
                payload_sha256=payload_sha256(payload),
                collected_at=collected_at,
            )
            created = updated = rejected = fetched = 0
            for source_item, observed_date, price in iter_daily_prices(
                payload,
                as_of_date,
            ):
                fetched += 1
                item_code = str(source_item.get("item_code") or "").strip()
                kind_code = str(source_item.get("kind_code") or "").strip()
                rank_code = str(source_item.get("rank_code") or "").strip()
                if not item_code:
                    rejected += 1
                    continue
                code = f"KAMIS:{item_code}:{kind_code}:{rank_code}"
                item, _ = MarketItem.objects.update_or_create(
                    code=code,
                    defaults={
                        "name": str(source_item.get("item_name") or code).strip(),
                        "category": options["category_code"],
                        "variety": str(source_item.get("kind_name") or "").strip(),
                        "grade": str(source_item.get("rank") or "").strip(),
                        "region": str(source_item.get("countyname") or "전국").strip(),
                        "unit": str(source_item.get("unit") or "").strip(),
                    },
                )
                lookup = {
                    "item": item,
                    "observed_date": observed_date,
                    "source": "KAMIS",
                    "region_code": options["country_code"],
                    "market_type": (
                        "RETAIL"
                        if options["product_class_code"] == "01"
                        else "WHOLESALE"
                    ),
                    "unit": item.unit,
                }
                _, was_created = MarketPriceObservation.objects.update_or_create(
                    **lookup,
                    defaults={
                        "region_name": item.region,
                        "price": price,
                        "source_item_code": item_code,
                        "source_unique_key": (
                            f"{code}:{observed_date}:{options['country_code']}:"
                            f"{options['product_class_code']}"
                        ),
                        "raw_payload": raw_payload,
                        "collected_at": collected_at,
                        "is_demo": False,
                    },
                )
                created += int(was_created)
                updated += int(not was_created)
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
                f"KAMIS {as_of_date}: 조회 {fetched}, 생성 {created}, "
                f"갱신 {updated}, 제외 {rejected}"
            )
        )
