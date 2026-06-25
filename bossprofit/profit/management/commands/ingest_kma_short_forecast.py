from collections import defaultdict
from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from profit.integrations.base import payload_sha256, redact_params
from profit.integrations.data_go_kr import fetch_short_forecast, response_items
from profit.models import IngestionRun, RawSourcePayload, WeatherForecastSnapshot


class Command(BaseCommand):
    help = "기상청 단기예보를 발행시각·유효시각별 snapshot으로 저장합니다."

    def add_arguments(self, parser):
        parser.add_argument("--base-date", required=True)
        parser.add_argument("--base-time", required=True)
        parser.add_argument("--nx", required=True, type=int)
        parser.add_argument("--ny", required=True, type=int)

    def handle(self, *args, **options):
        base_date = date.fromisoformat(options["base_date"])
        run = IngestionRun.objects.create(
            source="KMA",
            dataset="SHORT_FORECAST",
            observation_cutoff=timezone.now(),
            requested_params={
                key: options[key]
                for key in ("base_date", "base_time", "nx", "ny")
            },
            source_version="VilageFcstInfoService_2.0",
        )
        try:
            payload, url, params = fetch_short_forecast(
                base_date=base_date,
                base_time=options["base_time"],
                nx=options["nx"],
                ny=options["ny"],
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
            issued_at = timezone.make_aware(
                datetime.strptime(
                    f"{options['base_date']} {options['base_time']}",
                    "%Y-%m-%d %H%M",
                )
            )
            grouped = defaultdict(dict)
            for row in rows:
                valid_at = timezone.make_aware(
                    datetime.strptime(
                        f"{row['fcstDate']} {row['fcstTime']}",
                        "%Y%m%d %H%M",
                    )
                )
                grouped[valid_at][row["category"]] = row.get("fcstValue")
            created = updated = 0
            location_key = f"{options['nx']}:{options['ny']}"
            for valid_at, variables in grouped.items():
                _, was_created = WeatherForecastSnapshot.objects.update_or_create(
                    provider="KMA",
                    forecast_type="SHORT",
                    location_key=location_key,
                    issued_at=issued_at,
                    valid_at=valid_at,
                    defaults={
                        "variables": variables,
                        "collected_at": collected_at,
                        "raw_payload": raw,
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
            self.style.SUCCESS(f"단기예보 snapshot 생성 {created}, 갱신 {updated}")
        )
