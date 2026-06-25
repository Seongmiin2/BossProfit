"""Baseline rolling-origin 백테스트 보고 (항목 8).

    python manage.py backtest --item ONION --horizons 1,7,30 --min-train 30
    python manage.py backtest --item ONION --test-start 2026-05-01

데이터가 horizon+min_train 보다 짧으면 해당 품목은 건너뛴다.
"""
from datetime import date

from django.core.management.base import BaseCommand

from market.models import MarketItem
from forecast.data import load_price_series, load_volume_series
from forecast.baselines import DEFAULT_BASELINES
from forecast.base_models import LightGBMQuantileForecaster
from forecast.evaluation import evaluate_baselines


class Command(BaseCommand):
    help = "품목별 baseline 모델을 rolling-origin으로 백테스트합니다."

    def add_arguments(self, parser):
        parser.add_argument("--item", default=None, help="품목 코드(생략 시 전체)")
        parser.add_argument("--horizons", default="1,7,30")
        parser.add_argument("--min-train", type=int, default=30)
        parser.add_argument("--test-start", default=None, help="YYYY-MM-DD")
        parser.add_argument("--mase-season", type=int, default=7)
        parser.add_argument("--include-lgbm", action="store_true",
                            help="LightGBM 분위수 모델을 비교에 추가(느림)")
        parser.add_argument("--step", type=int, default=1,
                            help="origin 전진 간격(크게 하면 빠름)")

    def handle(self, *args, **opts):
        horizons = [int(h) for h in opts["horizons"].split(",") if h.strip()]
        test_start = date.fromisoformat(opts["test_start"]) if opts["test_start"] else None
        items = (
            MarketItem.objects.filter(code=opts["item"]) if opts["item"]
            else MarketItem.objects.filter(is_active=True)
        )
        if not items:
            self.stdout.write(self.style.WARNING("대상 품목이 없습니다."))
            return

        for item in items:
            s = load_price_series(item)
            need = opts["min_train"] + max(horizons)
            if len(s) < need:
                self.stdout.write(self.style.WARNING(
                    f"[{item.code}] 데이터 {len(s)}일 < 필요 {need}일 — 건너뜀"
                ))
                continue

            factories = dict(DEFAULT_BASELINES)
            if opts["include_lgbm"]:
                volume = load_volume_series(item)
                factories["lightgbm_quantile"] = (
                    lambda v=volume, hs=tuple(horizons):
                    LightGBMQuantileForecaster(horizons=hs, volume=v)
                )

            summary = evaluate_baselines(
                s, horizons=horizons, min_train=opts["min_train"],
                test_start=test_start, mase_season=opts["mase_season"],
                model_factories=factories, step=opts["step"],
            )
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n[{item.code}] {item.name}"))
            self.stdout.write(
                summary.to_string(
                    index=False,
                    formatters={
                        "mae": "{:.3f}".format, "rmse": "{:.3f}".format,
                        "wape": "{:.4f}".format, "bias": "{:+.3f}".format,
                        "mase": "{:.3f}".format,
                    },
                )
            )
