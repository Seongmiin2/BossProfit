"""Weather & Supply Impact ablation 보고 (항목 10).

    python manage.py weather_ablation --item ONION --horizons 7 --min-train 60

base(기상 미사용) vs weather-aware LightGBM을 rolling-origin으로 비교하고,
기상 충격 구간과 평시 구간을 분리해 보고한다.
"""
from datetime import date

from django.core.management.base import BaseCommand

from market.models import MarketItem
from forecast.data import load_price_series, load_volume_series
from forecast.weather_features import load_item_weather, build_weather_exposure, sensitive_growth_doys
from forecast.weather_model import detect_weather_shocks, evaluate_weather_ablation


class Command(BaseCommand):
    help = "기상·수급 보정(Stage 2) ablation을 충격/평시 구간으로 보고합니다."

    def add_arguments(self, parser):
        parser.add_argument("--item", required=True)
        parser.add_argument("--horizons", default="7")
        parser.add_argument("--min-train", type=int, default=60)
        parser.add_argument("--step", type=int, default=3)
        parser.add_argument("--test-start", default=None)

    def handle(self, *args, **opts):
        item = MarketItem.objects.filter(code=opts["item"]).first()
        if not item:
            self.stdout.write(self.style.ERROR(f"품목 {opts['item']} 없음"))
            return

        horizons = [int(h) for h in opts["horizons"].split(",") if h.strip()]
        test_start = date.fromisoformat(opts["test_start"]) if opts["test_start"] else None

        price = load_price_series(item)
        volume = load_volume_series(item)
        wdf = load_item_weather(item)
        if wdf.empty:
            self.stdout.write(self.style.WARNING(
                "주산지 기상 데이터가 없습니다. seed_market_mappings + ingest_weather 후 재시도하세요."
            ))
            return
        exposure = build_weather_exposure(wdf, growth_doy=sensitive_growth_doys(item))
        shocks = detect_weather_shocks(exposure)

        res = evaluate_weather_ablation(
            price, volume=volume, weather_exposure=exposure,
            horizons=horizons, min_train=opts["min_train"], step=opts["step"],
            test_start=test_start, shock_dates=shocks,
        )

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n[{item.code}] 기상 ablation (충격일 {len(shocks)}건)"))
        for section in ("overall", "shock", "normal"):
            df = res.get(section)
            if df is None or df.empty:
                continue
            self.stdout.write(f"\n[{section}]")
            self.stdout.write(df.to_string(
                index=False,
                formatters={"mae": "{:.3f}".format, "rmse": "{:.3f}".format,
                            "wape": "{:.4f}".format, "bias": "{:+.3f}".format,
                            "mase": "{:.3f}".format},
            ))
