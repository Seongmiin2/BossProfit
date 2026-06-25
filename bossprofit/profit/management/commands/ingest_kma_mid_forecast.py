from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from profit.integrations.base import payload_sha256, redact_params
from profit.integrations.data_go_kr import fetch_mid_land_forecast, response_items
from profit.models import IngestionRun, RawSourcePayload, WeatherForecastSnapshot


class Command(BaseCommand):
    help = "기상청 중기 육상예보를 발행시각별 snapshot으로 저장합니다."

    def add_arguments(self, parser):
        parser.add_argument("--region-id", required=True)
        parser.add_argument("--issued-at", required=True, help="YYYY-MM-DDTHH:MM")

    def handle(self, *args, **options):
        issued_at = timezone.make_aware(
            datetime.fromisoformat(options["issued_at"])
        )
        run = IngestionRun.objects.create(
            source="KMA",
            dataset="MID_LAND_FORECAST",
            observation_cutoff=timezone.now(),
            requested_params={
                "region_id": options["region_id"],
                "issued_at": options["issued_at"],
            },
            source_version="MidFcstInfoService",
        )
        try:
            payload, url, params = fetch_mid_land_forecast(
                region_id=options["region_id"],
                issued_at=issued_at,
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
            created = updated = 0
            if rows:
                row = rows[0]
                for day in range(3, 11):
                    variables = {
                        key: value
                        for key, value in row.items()
                        if key.lower().endswith(str(day))
                        or key.lower().endswith(f"{day}am")
                        or key.lower().endswith(f"{day}pm")
                    }
                    if not variables:
                        continue
                    valid_at = (issued_at + timedelta(days=day)).replace(
                        hour=0,
                        minute=0,
                        second=0,
                        microsecond=0,
                    )
                    _, was_created = WeatherForecastSnapshot.objects.update_or_create(
                        provider="KMA",
                        forecast_type="MID",
                        location_key=options["region_id"],
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
            self.style.SUCCESS(f"중기예보 snapshot 생성 {created}, 갱신 {updated}")
        )
