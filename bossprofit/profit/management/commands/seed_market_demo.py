from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from profit.models import (
    MarketForecast,
    MarketItem,
    MarketModelMetric,
    MarketPriceObservation,
    MarketRankingSnapshot,
    MarketRecommendation,
)


ITEMS = [
    ("ONION", "양파", "채소류", "20kg", "onion", 42000, "BUY"),
    ("NAPA_CABBAGE", "배추", "엽채류", "10kg", "napa-cabbage", 31500, "WATCH"),
    ("GREEN_ONION", "대파", "조미채소", "1kg", "green-onion", 5900, "AVOID"),
    ("POTATO", "감자", "서류", "20kg", "potato", 38500, "WATCH"),
    ("GARLIC", "마늘", "조미채소", "10kg", "garlic", 76500, "AVOID"),
]

ANALYSIS = {
    "ONION": {
        "summary": "가격·거래량·주산지 기상 신호가 단기 상승 방향을 가리키는 데모 시나리오입니다.",
        "action": "확정 사용량 범위에서 1~2주 물량의 분할 선구매를 검토합니다.",
        "evidence": ["최근 가격 모멘텀", "출하량 감소 신호", "주산지 강수 위험"],
        "changes": {1: 7.6, 7: 9.8, 30: 12.1},
    },
    "NAPA_CABBAGE": {
        "summary": "반입량은 유지되지만 가격 변동성이 커 방향을 더 확인해야 하는 데모 시나리오입니다.",
        "action": "대량 선구매보다 3일 단위 구매를 유지합니다.",
        "evidence": ["반입량 평년 수준", "시장별 가격 편차 확대", "예측구간 폭 증가"],
        "changes": {1: 2.9, 7: 1.8, 30: 4.2},
    },
    "GREEN_ONION": {
        "summary": "반입량 증가와 단기 하락 전망이 겹쳐 기다리는 편이 유리한 데모 시나리오입니다.",
        "action": "오늘은 최소량만 구매하고 내일 가격을 다시 확인합니다.",
        "evidence": ["도매 반입량 증가", "최근 상승 피로", "단기 하락 예측"],
        "changes": {1: -5.9, 7: -4.1, 30: 0.8},
    },
    "POTATO": {
        "summary": "상승 방향은 보이지만 예측구간이 넓어 확신하기 어려운 데모 시나리오입니다.",
        "action": "정상 구매를 유지하고 대량 선구매는 보류합니다.",
        "evidence": ["가격 완만한 상승", "거래량 중립", "예측 불확실성 높음"],
        "changes": {1: 3.8, 7: 2.4, 30: -0.6},
    },
    "GARLIC": {
        "summary": "단기 상승 이후 중기 되돌림 가능성이 더 큰 데모 시나리오입니다.",
        "action": "급등 가격에 대량 구매하지 말고 기존 재고를 우선 사용합니다.",
        "evidence": ["단기 가격 급등", "저장물량 출하 가능성", "7일 평균회귀 신호"],
        "changes": {1: -2.4, 7: -3.8, 30: -5.1},
    },
}

RANKINGS = {
    "VOLUME": [
        ("ONION", 2, 12.4, 884.0),
        ("NAPA_CABBAGE", 1, 8.7, 761.0),
        ("GREEN_ONION", 4, 6.2, 648.0),
        ("POTATO", 5, 4.8, 592.0),
        ("GARLIC", 3, 3.5, 544.0),
    ],
    "TODAY": [
        ("GARLIC", 3, 9.5, 9.5),
        ("ONION", 4, 8.1, 8.1),
        ("NAPA_CABBAGE", 1, -7.3, 7.3),
        ("GREEN_ONION", 5, -5.8, 5.8),
        ("POTATO", 2, 4.6, 4.6),
    ],
    "TOMORROW": [
        ("ONION", 3, 7.6, 7.6),
        ("GREEN_ONION", 1, -5.9, 5.9),
        ("POTATO", 4, 3.8, 3.8),
        ("NAPA_CABBAGE", 5, 2.9, 2.9),
        ("GARLIC", 2, -2.4, 2.4),
    ],
}


class Command(BaseCommand):
    help = "시장 랭킹 개발용 데모 데이터를 생성합니다."

    @transaction.atomic
    def handle(self, *args, **options):
        today = timezone.localdate()
        now = timezone.now()
        item_map = {}

        for code, name, category, unit, image_key, base_price, decision in ITEMS:
            item, _ = MarketItem.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "category": category,
                    "region": "전국",
                    "unit": unit,
                    "image_key": image_key,
                    "is_active": True,
                },
            )
            item_map[code] = item

            for offset in range(13, -1, -1):
                date = today - timedelta(days=offset)
                drift = Decimal(str((13 - offset) * 0.004 - 0.02))
                price = Decimal(str(base_price)) * (Decimal("1") + drift)
                volume = Decimal("420") + Decimal(str((13 - offset) * 18 + item.id * 7))
                MarketPriceObservation.objects.update_or_create(
                    item=item,
                    observed_date=date,
                    source="BOSSPROFIT_DEMO",
                    defaults={
                        "price": price.quantize(Decimal("0.01")),
                        "volume": volume,
                        "collected_at": now,
                        "is_demo": True,
                    },
                )

            for horizon, change in ANALYSIS[code]["changes"].items():
                current = Decimal(str(base_price))
                predicted = current * (Decimal("1") + Decimal(str(change / 100)))
                MarketForecast.objects.update_or_create(
                    item=item,
                    as_of_date=today,
                    horizon_days=horizon,
                    model_version="demo-ranking-v1",
                    defaults={
                        "target_date": today + timedelta(days=horizon),
                        "predicted_price": predicted.quantize(Decimal("0.01")),
                        "lower_price": (predicted * Decimal("0.92")).quantize(Decimal("0.01")),
                        "upper_price": (predicted * Decimal("1.08")).quantize(Decimal("0.01")),
                        "expected_change_rate": Decimal(str(change)),
                        "confidence_grade": "검증 전",
                        "is_demo": True,
                    },
                )

            MarketRecommendation.objects.update_or_create(
                item=item,
                as_of_date=today,
                defaults={
                    "decision": decision,
                    "summary": ANALYSIS[code]["summary"],
                    "action": ANALYSIS[code]["action"],
                    "evidence": ANALYSIS[code]["evidence"],
                    "is_demo": True,
                },
            )

        MarketRankingSnapshot.objects.filter(as_of_date=today, is_demo=True).delete()
        for ranking_type, rows in RANKINGS.items():
            for rank, (code, previous_rank, change_rate, score) in enumerate(rows, start=1):
                MarketRankingSnapshot.objects.create(
                    ranking_type=ranking_type,
                    as_of_date=today,
                    item=item_map[code],
                    rank=rank,
                    previous_rank=previous_rank,
                    score=Decimal(str(score)),
                    display_change_rate=Decimal(str(change_rate)),
                    is_demo=True,
                )

        MarketModelMetric.objects.update_or_create(
            item=None,
            model_version="demo-ranking-v1",
            horizon_days=1,
            defaults={"is_verified": False},
        )

        self.stdout.write(self.style.SUCCESS("시장 데모 품목 5개와 랭킹 3종을 생성했습니다."))
