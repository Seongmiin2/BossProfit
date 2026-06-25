"""품목·주산지·관측소 데모 매핑 (항목 6).

실제 운영에서는 통계청 주산지 비중과 관측소 좌표로 채우지만, MVP 데모/테스트를 위해
대표 품목(양파·배추)의 주산지·관측소·생육단계를 결정적으로 구성한다.

    python manage.py seed_market_mappings
"""
from django.core.management.base import BaseCommand

from market.models import MarketItem, ProductionRegion, CropProductionRegion, CropGrowthStage
from weather.models import WeatherStation, WeatherStationMapping

# region_code, name, station_id
REGIONS = [
    ("46", "전남", "165", "목포"),
    ("42", "강원", "105", "강릉"),
]

# item_code -> [(region_code, weight)]
CROP_REGIONS = {
    "ONION": [("46", 0.6), ("42", 0.4)],
    "NAPA_CABBAGE": [("42", 0.7), ("46", 0.3)],
}

# item_code -> [(stage, start_day, end_day)]
GROWTH = {
    "ONION": [("정식", 60, 120), ("비대기", 121, 160), ("수확", 161, 180)],
    "NAPA_CABBAGE": [("정식", 220, 250), ("결구기", 251, 290), ("수확", 291, 320)],
}


class Command(BaseCommand):
    help = "대표 품목의 주산지·관측소·생육단계 데모 매핑을 생성합니다."

    def handle(self, *args, **opts):
        regions = {}
        for code, name, station_id, station_name in REGIONS:
            region, _ = ProductionRegion.objects.update_or_create(
                code=code, defaults={"name": name}
            )
            regions[code] = region
            station, _ = WeatherStation.objects.update_or_create(
                station_id=station_id, defaults={"name": station_name, "source": "asos"}
            )
            WeatherStationMapping.objects.update_or_create(
                region=region, station=station, defaults={"weight": 1.0}
            )
        self.stdout.write(self.style.SUCCESS(f"✓ 지역·관측소 매핑 {len(REGIONS)}건"))

        for item_code, shares in CROP_REGIONS.items():
            item = MarketItem.objects.filter(code=item_code).first()
            if not item:
                self.stdout.write(self.style.WARNING(f"  품목 {item_code} 없음 — 건너뜀"))
                continue
            for region_code, weight in shares:
                CropProductionRegion.objects.update_or_create(
                    item=item, region=regions[region_code], valid_from=None,
                    defaults={"weight": weight},
                )
            for stage, start_day, end_day in GROWTH.get(item_code, []):
                CropGrowthStage.objects.update_or_create(
                    item=item, region=None, stage=stage,
                    defaults={"start_day": start_day, "end_day": end_day},
                )
        self.stdout.write(self.style.SUCCESS("✓ 주산지 비중·생육단계 매핑 완료"))
