from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from profit.models import (
    MarketRankingSnapshot,
    MarketRecommendation,
    MarketItem,
)


DEFAULT_ITEM_IMAGES = {
    "KAMIS:245:00:04": ("양파", "onion"),
    "KAMIS:246:00:04": ("대파", "green-onion"),
    "KAMIS:258:01:04": ("마늘", "garlic"),
    "KAMIS:211:01:04": ("배추", "napa-cabbage"),
    "KAMIS:152:01:04": ("감자", "potato"),
}


def decision_for(change_rate):
    if change_rate >= Decimal("0.03"):
        return (
            "BUY",
            "가격 상승 가능성이 있어 필요한 물량을 분할 선매입하는 방안을 검토하세요.",
        )
    if change_rate <= Decimal("-0.03"):
        return (
            "AVOID",
            "가격 하락 가능성이 있어 대량 선매입보다 필요한 만큼만 구매하세요.",
        )
    return (
        "WATCH",
        "변동 신호가 크지 않습니다. 재고를 늘리기보다 다음 관측을 확인하세요.",
    )


class Command(BaseCommand):
    help = "실제 KAMIS 관측과 예측으로 오늘·내일 TOP5 랭킹을 재생성합니다."

    def add_arguments(self, parser):
        parser.add_argument("--date", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        as_of_date = date.fromisoformat(options["date"])
        rows = []
        for code, (display_name, image_key) in DEFAULT_ITEM_IMAGES.items():
            item = MarketItem.objects.filter(code=code).first()
            if item is None:
                continue
            item.name = display_name
            item.image_key = image_key
            item.save(update_fields=["name", "image_key"])
            observations = list(
                item.observations.filter(
                    source="KAMIS_PERIOD",
                    region_code="AVERAGE",
                    observed_date__lte=as_of_date,
                ).order_by("-observed_date")[:2]
            )
            forecast = item.forecasts.filter(
                as_of_date__lte=as_of_date,
                horizon_days=1,
                is_demo=False,
            ).order_by("-as_of_date", "-created_at").first()
            if len(observations) < 2 or forecast is None:
                continue
            latest, previous = observations
            today_change = (
                (latest.price - previous.price) / previous.price
                if previous.price
                else Decimal("0")
            )
            tomorrow_change = forecast.expected_change_rate
            rows.append((item, latest, forecast, today_change, tomorrow_change))

        if len(rows) < 3:
            raise CommandError("실제 관측과 예측이 있는 품목이 3개 미만입니다.")

        for ranking_type, change_index in (("TODAY", 3), ("TOMORROW", 4)):
            previous_ranks = {
                snapshot.item_id: snapshot.rank
                for snapshot in MarketRankingSnapshot.objects.filter(
                    ranking_type=ranking_type,
                ).order_by("-as_of_date", "rank")
            }
            ranked = sorted(
                rows,
                key=lambda row: abs(row[change_index]),
                reverse=True,
            )[:5]
            MarketRankingSnapshot.objects.filter(
                ranking_type=ranking_type,
                as_of_date=as_of_date,
            ).delete()
            for rank, row in enumerate(ranked, start=1):
                item, latest, forecast, today_change, tomorrow_change = row
                display_change = row[change_index]
                MarketRankingSnapshot.objects.create(
                    ranking_type=ranking_type,
                    as_of_date=as_of_date,
                    item=item,
                    rank=rank,
                    previous_rank=previous_ranks.get(item.id),
                    score=abs(display_change),
                    display_change_rate=display_change,
                    is_demo=False,
                )
                decision, action = decision_for(tomorrow_change)
                MarketRecommendation.objects.update_or_create(
                    item=item,
                    as_of_date=as_of_date,
                    defaults={
                        "decision": decision,
                        "summary": (
                            f"최근 실제 가격은 {float(today_change) * 100:+.1f}%, "
                            f"1일 예측은 {float(tomorrow_change) * 100:+.1f}%입니다."
                        ),
                        "action": action,
                        "evidence": [
                            {
                                "label": "KAMIS 최근 실제가격",
                                "value": f"{latest.price:,.0f}원/{item.unit}",
                            },
                            {
                                "label": "1일 예측구간",
                                "value": (
                                    f"{forecast.lower_price:,.0f}~"
                                    f"{forecast.upper_price:,.0f}원"
                                ),
                            },
                            {
                                "label": "모델 상태",
                                "value": forecast.confidence_grade,
                            },
                        ],
                        "is_demo": False,
                    },
                )
        self.stdout.write(
            self.style.SUCCESS(f"{as_of_date} 실제 오늘·내일 TOP5 생성 완료")
        )
