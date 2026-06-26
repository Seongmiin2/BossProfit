"""LightGBM 글로벌 분위 모델 vs 기존 통계 모델·naive 베이스라인 비교 백테스트.

누설 없는 rolling-origin 프로토콜로 동일 샘플 위에서 4개 모델을 비교한다.
각 평가일 ``D`` 에 대해 ``target_date < D`` 인 샘플로만 글로벌 LightGBM을 학습하고
``target_date == D`` 샘플을 예측한다(미래 타깃 누설 없음). 결과는 화면 출력만
하며 DB는 건드리지 않는다 — "LightGBM이 베이스라인을 이길 여지가 있는가"를
검증하는 게이트 용도다.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from profit.forecasting.engine import BasePriceModel
from profit.forecasting.evaluation import metric_bundle, seasonal_naive
from profit.forecasting.lightgbm_model import (
    LIGHTGBM_AVAILABLE,
    LightGBMGlobalForecaster,
    build_samples,
)
from profit.models import MarketItem


def _load_series(items):
    """엔진과 동일한 관측 선택 규칙으로 품목별 시계열·관측객체를 적재."""
    series = []
    obs_by_item = {}
    for item in items:
        q = item.observations.filter(is_demo=False)
        period = q.filter(source="KAMIS_PERIOD", region_code="AVERAGE")
        if period.exists():
            q = period
        rows = list(q.order_by("observed_date", "id"))
        if len(rows) < 8:
            continue
        obs_by_item[item.id] = rows
        series.append(
            {
                "item_id": item.id,
                "item_code": item.code,
                "category": item.category,
                "rows": [(r.observed_date, r.price) for r in rows],
            }
        )
    return series, obs_by_item


def _fmt(value):
    if value is None:
        return "  n/a"
    return f"{float(value):6.4f}"


class Command(BaseCommand):
    help = "글로벌 LightGBM 분위 모델을 기존 통계·naive 베이스라인과 비교한다."

    def add_arguments(self, parser):
        parser.add_argument("--horizons", default="1,7,30")
        parser.add_argument("--holdout", type=float, default=0.4,
                            help="평가에 쓸 후반부 비율(기본 0.4)")
        parser.add_argument("--refit-every", type=int, default=7,
                            help="LightGBM 재학습 주기(평가일 수, 기본 7)")

    def handle(self, *args, **options):
        if not LIGHTGBM_AVAILABLE:
            raise CommandError("lightgbm/numpy 미설치 — pip install lightgbm")

        horizons = tuple(sorted({int(v) for v in options["horizons"].split(",") if v.strip()}))
        items = MarketItem.objects.filter(is_active=True)
        series, obs_by_item = _load_series(items)
        if not series:
            raise CommandError("관측 시계열이 없습니다.")

        self.stdout.write(
            f"품목 {len(series)}개 · horizons={horizons} · holdout={options['holdout']}"
        )

        all_samples = build_samples(series, horizons)
        if not all_samples:
            raise CommandError("학습 샘플이 없습니다.")

        # 시간 순서대로 정렬, 후반 holdout 구간을 평가 대상으로.
        target_dates = sorted({s.target_date for s in all_samples})
        split = int(len(target_dates) * (1 - options["holdout"]))
        eval_dates = target_dates[max(split, 1):]
        samples_by_target = defaultdict(list)
        for s in all_samples:
            samples_by_target[s.target_date].append(s)

        self.stdout.write(
            f"총 샘플 {len(all_samples)}건 · 평가일 {len(eval_dates)}개 "
            f"({eval_dates[0]} ~ {eval_dates[-1]})"
        )

        base_model = BasePriceModel()
        forecaster = None
        # 결과 누적: per-horizon, per-model 예측/실측
        records = []  # dict per evaluated sample
        refit_every = max(1, options["refit_every"])

        for i, eval_date in enumerate(eval_dates):
            if forecaster is None or i % refit_every == 0:
                train = [s for s in all_samples if s.target_date < eval_date]
                if len(train) < 50:
                    continue
                forecaster = LightGBMGlobalForecaster().fit(train)

            todays = samples_by_target[eval_date]
            preds = forecaster.predict(todays)
            for s, p in zip(todays, preds):
                rows = obs_by_item[s.item_id]
                eligible = [r for r in rows if r.observed_date <= s.origin_date]
                # 기존 통계 모델 (가능할 때만)
                stat_pred = None
                if len(eligible) >= base_model.minimum_observations:
                    try:
                        stat_pred = float(base_model.predict(eligible, s.horizon).value)
                    except Exception:
                        stat_pred = None
                hist_prices = [float(r.price) for r in eligible]
                snaive = seasonal_naive(hist_prices, horizon=s.horizon, season_length=7)
                records.append(
                    {
                        "horizon": s.horizon,
                        "actual": s.actual,
                        "lgbm": p["median"],
                        "lgbm_lo": p["lower"],
                        "lgbm_hi": p["upper"],
                        "stat": stat_pred,
                        "last_value": s.price_t,
                        "snaive": float(snaive) if snaive is not None else None,
                    }
                )

        if not records:
            raise CommandError("평가 샘플이 생성되지 않았습니다(데이터 부족).")

        self._report(records, horizons)

    def _report(self, records, horizons):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            "== 공통 샘플(모든 모델 예측 가능) 기준 WAPE / MAE 비교 =="
        ))
        for horizon in (None, *horizons):
            subset = [
                r for r in records
                if (horizon is None or r["horizon"] == horizon) and r["stat"] is not None
            ]
            if not subset:
                continue
            actual = [r["actual"] for r in subset]
            label = "전체" if horizon is None else f"h={horizon:>2}"
            self.stdout.write(
                f"\n[{label}] 공통표본 {len(subset)}건"
            )
            self.stdout.write(
                f"  {'model':<16}{'WAPE':>8}{'MAE':>10}{'MASE':>8}{'pinball':>9}"
            )
            for name, key in (
                ("LightGBM", "lgbm"),
                ("기존통계모델", "stat"),
                ("LastValue", "last_value"),
                ("SeasonalNaive", "snaive"),
            ):
                pred = [r[key] for r in subset]
                m = metric_bundle(actual, pred)
                self.stdout.write(
                    f"  {name:<16}{_fmt(m['wape']):>8}{_fmt(m['mae']):>10}"
                    f"{_fmt(m['mase']):>8}{_fmt(m['pinball_loss']):>9}"
                )

        # LightGBM 예측구간 커버리지 (목표 80%)
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            "== LightGBM 80% 예측구간 실측 커버리지 =="
        ))
        for horizon in (None, *horizons):
            subset = [r for r in records if horizon is None or r["horizon"] == horizon]
            if not subset:
                continue
            covered = sum(r["lgbm_lo"] <= r["actual"] <= r["lgbm_hi"] for r in subset)
            label = "전체" if horizon is None else f"h={horizon:>2}"
            self.stdout.write(
                f"  [{label}] {covered}/{len(subset)} = "
                f"{covered/len(subset):.1%} (목표 80%)"
            )

        # LightGBM 단독 커버리지 (통계모델이 못 푸는 표본 포함)
        full = len(records)
        stat_ok = sum(1 for r in records if r["stat"] is not None)
        self.stdout.write("")
        self.stdout.write(
            f"표본 커버리지: LightGBM {full}건 / 기존통계모델 {stat_ok}건 "
            f"(통계모델은 관측 30개 미만 품목을 예측 못함)"
        )
        self.stdout.write(self.style.SUCCESS("백테스트 완료"))
