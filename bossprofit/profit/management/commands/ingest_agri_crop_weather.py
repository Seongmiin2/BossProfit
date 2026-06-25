from datetime import date, datetime, time
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from profit.integrations.base import payload_sha256, redact_params
from profit.integrations.data_go_kr import (
    fetch_agri_crop_daily,
    fetch_agri_crop_stations,
    xml_response_items,
)
from profit.models import (
    CropProductionRegion,
    IngestionRun,
    MarketItem,
    RawSourcePayload,
    WeatherObservation,
    WeatherStationMapping,
)


NON_VARIABLE_FIELDS = {"no", "obsr_Datetm", "obsr_Spot_Code"}


class Command(BaseCommand):
    help = "농촌진흥청 주산지 농업기상 관측소와 일자료를 품목에 연결합니다."

    def add_arguments(self, parser):
        parser.add_argument("--item-code", required=True)
        parser.add_argument("--crop-code", required=True)
        parser.add_argument("--start-date", required=True)
        parser.add_argument("--end-date", required=True)

    def handle(self, *args, **options):
        item = MarketItem.objects.filter(code=options["item_code"]).first()
        if item is None:
            raise CommandError(f"시장 품목을 찾을 수 없습니다: {options['item_code']}")
        start_date = date.fromisoformat(options["start_date"])
        end_date = date.fromisoformat(options["end_date"])
        run = IngestionRun.objects.create(
            source="RDA_AGRI_WEATHER",
            dataset="CROP_PRODUCTION_REGION_DAILY",
            observation_cutoff=timezone.now(),
            requested_params={
                key: options[key]
                for key in ("item_code", "crop_code", "start_date", "end_date")
            },
            source_version="frcPlpd",
        )
        fetched = created = updated = rejected = 0
        try:
            station_payload, station_url, station_params = fetch_agri_crop_stations(
                crop_code=options["crop_code"]
            )
            station_rows = xml_response_items(station_payload)
            collected_at = timezone.now()
            RawSourcePayload.objects.create(
                ingestion_run=run,
                source_url=station_url.split("?", 1)[0],
                request_params=redact_params(station_params),
                payload=station_payload,
                payload_sha256=payload_sha256(station_payload),
                collected_at=collected_at,
            )
            if not station_rows:
                raise ValueError("주산지 관측소가 없습니다.")
            equal_weight = Decimal("1") / Decimal(len(station_rows))
            for station in station_rows:
                station_code = str(station["obsr_Spot_Code"])
                region_name = " ".join(
                    part
                    for part in (
                        str(station.get("do_Nm") or "").strip(),
                        str(station.get("spot_Nm") or "").strip(),
                    )
                    if part
                )
                region, _ = CropProductionRegion.objects.update_or_create(
                    item=item,
                    region_code=station_code,
                    valid_from=start_date,
                    defaults={
                        "region_name": region_name,
                        "weight": equal_weight,
                        "mapping_confidence": Decimal("0.5000"),
                        "review_status": "PENDING",
                        "source": "RDA_frcPlpd",
                    },
                )
                WeatherStationMapping.objects.update_or_create(
                    production_region=region,
                    provider="RDA_AGRI",
                    station_id=station_code,
                    defaults={
                        "station_name": region_name,
                        "weight": Decimal("1"),
                        "mapping_confidence": Decimal("0.5000"),
                        "review_status": "PENDING",
                    },
                )
                payload, url, params = fetch_agri_crop_daily(
                    crop_code=options["crop_code"],
                    station_code=station_code,
                    start_date=start_date,
                    end_date=end_date,
                )
                weather_rows = xml_response_items(payload)
                raw = RawSourcePayload.objects.create(
                    ingestion_run=run,
                    source_url=url.split("?", 1)[0],
                    request_params=redact_params(params),
                    payload=payload,
                    payload_sha256=payload_sha256(payload),
                    collected_at=collected_at,
                )
                for row in weather_rows:
                    fetched += 1
                    try:
                        observed_at = timezone.make_aware(
                            datetime.combine(
                                date.fromisoformat(row["obsr_Datetm"]),
                                time.min,
                            )
                        )
                    except (KeyError, ValueError):
                        rejected += 1
                        continue
                    variables = {
                        key: value
                        for key, value in row.items()
                        if key not in NON_VARIABLE_FIELDS
                    }
                    _, was_created = WeatherObservation.objects.update_or_create(
                        provider="RDA_AGRI",
                        station_id=station_code,
                        observed_at=observed_at,
                        defaults={
                            "variables": variables,
                            "quality": {
                                "crop_code": options["crop_code"],
                                "mapping_review_status": "PENDING",
                            },
                            "collected_at": collected_at,
                            "raw_payload": raw,
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
                f"{item.name} 주산지 농업기상: 관측 {fetched}, 생성 {created}, "
                f"갱신 {updated}"
            )
        )
