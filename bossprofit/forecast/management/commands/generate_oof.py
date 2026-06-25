"""OOF 잔차 생성·저장 커맨드 (항목 11).

    python manage.py generate_oof --item ONION --model last_value --horizons 1,7 --min-train 30
    python manage.py generate_oof --item ONION --model lgbm --horizons 7 --min-train 60 --step 5

잔차는 OutOfFoldForecast/ResidualObservation 에 멱등 저장된다(Stage 3 학습 입력).
"""
from datetime import date

from django.core.management.base import BaseCommand

from market.models import MarketItem
from forecast.data import load_price_series, load_volume_series
from forecast.baselines import LastValueForecaster, SeasonalNaiveForecaster
from forecast.base_models import LightGBMQuantileForecaster
from forecast.residuals import generate_oof_residuals


class Command(BaseCommand):
    help = "Stage1/2 OOF 예측에서 로그 잔차를 생성·저장합니다(Stage 3 학습용)."

    def add_arguments(self, parser):
        parser.add_argument("--item", required=True)
        parser.add_argument("--model", default="last_value",
                            choices=["last_value", "seasonal_naive_7", "lgbm"])
        parser.add_argument("--horizons", default="1,7")
        parser.add_argument("--min-train", type=int, default=30)
        parser.add_argument("--step", type=int, default=1)
        parser.add_argument("--test-start", default=None)

    def handle(self, *args, **opts):
        item = MarketItem.objects.filter(code=opts["item"]).first()
        if not item:
            self.stdout.write(self.style.ERROR(f"품목 {opts['item']} 없음"))
            return
        horizons = [int(h) for h in opts["horizons"].split(",") if h.strip()]
        test_start = date.fromisoformat(opts["test_start"]) if opts["test_start"] else None
        price = load_price_series(item)

        name = opts["model"]
        if name == "last_value":
            factory = lambda: LastValueForecaster()
        elif name == "seasonal_naive_7":
            factory = lambda: SeasonalNaiveForecaster(7)
        else:
            volume = load_volume_series(item)
            factory = lambda v=volume, hs=tuple(horizons): LightGBMQuantileForecaster(
                horizons=hs, volume=v
            )

        df = generate_oof_residuals(
            item, price, factory, horizons, min_train=opts["min_train"],
            model_version=name, step=opts["step"], test_start=test_start, persist=True,
        )
        if df.empty:
            self.stdout.write(self.style.WARNING("생성된 OOF 잔차가 없습니다(데이터 부족)."))
            return

        self.stdout.write(self.style.SUCCESS(
            f"[{item.code}/{name}] OOF 잔차 {len(df)}건 저장"
        ))
        for h, grp in df.groupby("horizon"):
            r = grp["residual"]
            self.stdout.write(
                f"  h{h}: n={len(grp)} 평균잔차(bias)={r.mean():+.4f} "
                f"std={r.std():.4f} |절대평균|={r.abs().mean():.4f}"
            )
