"""end-to-end 예측 생성 + 백엔드 계약 응답 출력 (항목 13).

    python manage.py produce_forecast --item ONION --as-of 2026-06-01 --horizons 7,30
"""
import json
from datetime import date

from django.core.management.base import BaseCommand

from market.models import MarketItem
from forecast.pipeline import produce_forecast
from forecast.models import ForecastRun
from forecast.serving import forecast_response_all


class Command(BaseCommand):
    help = "base→weather→residual→conformal 을 조립해 예측을 생성·저장하고 계약 응답을 출력합니다."

    def add_arguments(self, parser):
        parser.add_argument("--item", required=True)
        parser.add_argument("--as-of", required=True, help="YYYY-MM-DD")
        parser.add_argument("--horizons", default="7,30")
        parser.add_argument("--residual-version", default="last_value")

    def handle(self, *args, **opts):
        item = MarketItem.objects.filter(code=opts["item"]).first()
        if not item:
            self.stdout.write(self.style.ERROR(f"품목 {opts['item']} 없음"))
            return
        horizons = [int(h) for h in opts["horizons"].split(",") if h.strip()]
        out = produce_forecast(
            item, date.fromisoformat(opts["as_of"]), horizons=horizons,
            residual_version=opts["residual_version"], persist=True,
        )
        if not out.get("ok"):
            self.stdout.write(self.style.WARNING(f"생성 실패: {out.get('reason')}"))
            return
        run = ForecastRun.objects.get(id=out["run_id"])
        self.stdout.write(self.style.SUCCESS(f"\n[{item.code}] 예측 저장 (run={run.id})"))
        for resp in forecast_response_all(run):
            self.stdout.write(json.dumps(resp, ensure_ascii=False, indent=2))
