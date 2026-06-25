from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from profit.forecasting import ForecastEngine
from profit.models import MarketItem


class Command(BaseCommand):
    help = "단계별 시장가격 예측을 실행하고 각 구성요소를 별도로 저장합니다."

    def add_arguments(self, parser):
        parser.add_argument("--item-code")
        parser.add_argument("--date", default=timezone.localdate().isoformat())
        parser.add_argument("--horizons", default="1,7,30,60,90")

    def handle(self, *args, **options):
        as_of_date = date.fromisoformat(options["date"])
        horizons = tuple(
            sorted(
                {
                    int(value.strip())
                    for value in options["horizons"].split(",")
                    if value.strip()
                }
            )
        )
        items = MarketItem.objects.filter(is_active=True)
        if options["item_code"]:
            items = items.filter(code=options["item_code"])
        if not items.exists():
            raise CommandError("예측할 품목이 없습니다.")

        engine = ForecastEngine()
        succeeded = failed = 0
        for item in items:
            try:
                forecasts = engine.run(item, as_of_date, horizons)
                succeeded += 1
                self.stdout.write(f"{item.name}: {len(forecasts)}개 horizon 생성")
            except Exception as exc:
                failed += 1
                self.stderr.write(f"{item.name}: {exc}")
        if succeeded == 0:
            raise CommandError(f"모든 예측이 실패했습니다({failed}개 품목).")
        self.stdout.write(
            self.style.SUCCESS(f"예측 완료: 성공 {succeeded}, 실패 {failed}")
        )
