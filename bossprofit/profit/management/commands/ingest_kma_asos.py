from datetime import date, datetime, time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from profit.integrations.base import payload_sha256, redact_params
from profit.integrations.data_go_kr import fetch_asos_daily, response_items
from profit.models import IngestionRun, RawSourcePayload, WeatherObservation


VARIABLE_FIELDS = (
    "avgTa",
    "minTa",
    "maxTa",
    "sumRn",
    "avgRhm",
    "avgWs",
    "sumSsHr",
    "sumGsr",
    "avgTs",
)


class Command(BaseCommand):
    help = "기상청 ASOS 일자료를 원본과 함께 저장합니다."

    def add_arguments(self, parser):
        parser.add_argument("--station-id", required=True)
        parser.add_argument("--start-date", required=True)
        parser.add_argument("--end-date", required=True)

    def handle(self, *args, **options):
        start_date = date.fromisoformat(options["start_date"])
        end_date = date.fromisoformat(options["end_date"])
        run = IngestionRun.objects.create(
            source="KMA",
            dataset="ASOS_DAILY",
            observation_cutoff=timezone.now(),
            requested_params={
                "station_id": options["station_id"],
                "start_date": options["start_date"],
                "end_date": options["end_date"],
            },
            source_version="AsosDalyInfoService",
        )
        try:
            payload, url, params = fetch_asos_daily(
                station_id=options["station_id"],
                start_date=start_date,
                end_date=end_date,
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
            for row in rows:
                observed_at = timezone.make_aware(
                    datetime.combine(
                        date.fromisoformat(row["tm"]),
                        time.min,
                    )
                )
                variables = {
                    field: row.get(field)
                    for field in VARIABLE_FIELDS
                    if row.get(field) not in (None, "")
                }
                _, was_created = WeatherObservation.objects.update_or_create(
                    provider="KMA_ASOS",
                    station_id=str(row.get("stnId") or options["station_id"]),
                    observed_at=observed_at,
                    defaults={
                        "variables": variables,
                        "quality": {"station_name": row.get("stnNm", "")},
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
            self.style.SUCCESS(
                f"ASOS {options['station_id']}: 생성 {created}, 갱신 {updated}"
            )
        )
