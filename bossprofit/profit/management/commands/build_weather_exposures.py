from datetime import date, datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from profit.models import MarketItem, WeatherExposureFeature, WeatherObservation


WINDOWS = (3, 7, 14, 30, 60, 90)
AVERAGE_FIELDS = (
    "tmprt",
    "tmprt_Top",
    "tmprt_Lwet",
    "solrad_Qy",
    "arvlty",
    "frfr_Tp",
    "udgr_Tp",
    "soil_Mitr_Cmst",
)
SUM_FIELDS = ("afp", "sunshn_Time")


def numeric(value):
    if value in (None, "", "-"):
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


class Command(BaseCommand):
    help = "주산지 농업기상 관측을 3·7·14·30·60·90일 노출 피처로 집계합니다."

    def add_arguments(self, parser):
        parser.add_argument("--item-code", required=True)
        parser.add_argument("--date", required=True)
        parser.add_argument("--feature-version", default="rda-exposure-v1")

    def handle(self, *args, **options):
        item = MarketItem.objects.filter(code=options["item_code"]).first()
        if item is None:
            raise CommandError(f"품목을 찾을 수 없습니다: {options['item_code']}")
        as_of_date = date.fromisoformat(options["date"])
        cutoff = timezone.make_aware(datetime.combine(as_of_date, time.max))
        created = updated = 0
        regions_by_code = {}
        for region in item.production_regions.filter(
            valid_from__lte=as_of_date
        ).order_by("region_code", "-valid_from", "-id"):
            regions_by_code.setdefault(region.region_code, region)
        selected_regions = list(regions_by_code.values())
        WeatherExposureFeature.objects.filter(
            item=item,
            as_of_date=as_of_date,
            feature_version=options["feature_version"],
        ).exclude(
            production_region_id__in=[region.id for region in selected_regions]
        ).delete()
        for region in selected_regions:
            mapping = region.station_mappings.filter(provider="RDA_AGRI").first()
            if mapping is None:
                continue
            weather_rows = list(
                WeatherObservation.objects.filter(
                    provider="RDA_AGRI",
                    station_id=mapping.station_id,
                    observed_at__lte=cutoff,
                    observed_at__gte=cutoff - timedelta(days=max(WINDOWS)),
                ).order_by("observed_at")
            )
            windows = {}
            for window in WINDOWS:
                start_at = cutoff - timedelta(days=window)
                rows = [row for row in weather_rows if row.observed_at > start_at]
                values = {"available_days": len(rows)}
                for field in AVERAGE_FIELDS:
                    field_values = [
                        value
                        for value in (numeric(row.variables.get(field)) for row in rows)
                        if value is not None
                    ]
                    values[f"{field}_mean"] = (
                        str(sum(field_values, Decimal("0")) / Decimal(len(field_values)))
                        if field_values
                        else None
                    )
                for field in SUM_FIELDS:
                    field_values = [
                        value
                        for value in (numeric(row.variables.get(field)) for row in rows)
                        if value is not None
                    ]
                    values[f"{field}_sum"] = (
                        str(sum(field_values, Decimal("0")))
                        if field_values
                        else None
                    )
                windows[str(window)] = values
            _, was_created = WeatherExposureFeature.objects.update_or_create(
                item=item,
                production_region=region,
                as_of_date=as_of_date,
                feature_version=options["feature_version"],
                defaults={
                    "windows": windows,
                    "anomalies": {
                        "status": "CLIMATOLOGY_REQUIRED",
                        "mapping_review_status": region.review_status,
                    },
                    "observation_cutoff": cutoff,
                },
            )
            created += int(was_created)
            updated += int(not was_created)
        self.stdout.write(
            self.style.SUCCESS(
                f"{item.name} 기상 노출 피처: 생성 {created}, 갱신 {updated}"
            )
        )
