"""글로벌 LightGBM 분위 모델을 학습해 아티팩트로 저장한다.

엔진(``ForecastEngine``)이 장기 horizon 예측에 사용하는 모델을 만든다. 학습은
오프라인 1회성이며, 산출물은 ``DEFAULT_ARTIFACT_PATH`` 에 pickle로 저장된다.
분위구간(10/50/90)은 시간 분할 홀드아웃에서 목표 80% 커버리지를 맞추도록
보정계수 ``k`` 를 horizon별로 추정해 함께 저장한다.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from profit.forecasting.lightgbm_model import (
    LIGHTGBM_AVAILABLE,
    DEFAULT_ARTIFACT_PATH,
    LightGBMGlobalForecaster,
    TrainedLightGBMArtifact,
    build_samples,
)
from profit.models import MarketItem


def _load_series(items):
    series = []
    for item in items:
        q = item.observations.filter(is_demo=False)
        period = q.filter(source="KAMIS_PERIOD", region_code="AVERAGE")
        if period.exists():
            q = period
        rows = list(q.order_by("observed_date", "id").values_list("observed_date", "price"))
        if len(rows) < 8:
            continue
        series.append(
            {
                "item_id": item.id,
                "item_code": item.code,
                "category": item.category,
                "rows": rows,
            }
        )
    return series


def _coverage(samples, preds, k):
    covered = 0
    for s, p in zip(samples, preds):
        lo = p["median"] - k * (p["median"] - p["lower"])
        hi = p["median"] + k * (p["upper"] - p["median"])
        if lo <= s.actual <= hi:
            covered += 1
    return covered / len(samples) if samples else 0.0


def _calibrate_scale(holdout_by_h, forecaster, target=0.80):
    """horizon별로 목표 커버리지를 맞추는 최소 k(이분탐색)를 찾는다."""
    scale = {}
    for horizon, samples in holdout_by_h.items():
        if len(samples) < 10:
            scale[horizon] = {"k": 1.0, "coverage": None, "samples": len(samples)}
            continue
        preds = forecaster.predict(samples)
        lo_k, hi_k = 0.5, 5.0
        # 단조 증가 가정 — 이분탐색
        for _ in range(25):
            mid = (lo_k + hi_k) / 2
            if _coverage(samples, preds, mid) >= target:
                hi_k = mid
            else:
                lo_k = mid
        k = round(hi_k, 4)
        scale[horizon] = {
            "k": k,
            "coverage": round(_coverage(samples, preds, k), 4),
            "samples": len(samples),
        }
    return scale


class Command(BaseCommand):
    help = "글로벌 LightGBM 분위 예측 모델을 학습·저장한다."

    def add_arguments(self, parser):
        parser.add_argument("--horizons", default="14,30,60,90")
        parser.add_argument("--holdout", type=float, default=0.2)
        parser.add_argument("--output", default=DEFAULT_ARTIFACT_PATH)

    def handle(self, *args, **options):
        if not LIGHTGBM_AVAILABLE:
            raise CommandError("lightgbm/numpy/joblib 미설치 — pip install lightgbm scikit-learn")

        horizons = tuple(sorted({int(v) for v in options["horizons"].split(",") if v.strip()}))
        series = _load_series(MarketItem.objects.filter(is_active=True))
        if not series:
            raise CommandError("학습할 관측 시계열이 없습니다.")

        all_samples = build_samples(series, horizons)
        if len(all_samples) < 50:
            raise CommandError(f"학습 샘플 부족({len(all_samples)}건).")

        # 시간 분할: 보정계수 추정용 홀드아웃
        target_dates = sorted({s.target_date for s in all_samples})
        cut = target_dates[int(len(target_dates) * (1 - options["holdout"]))]
        train_split = [s for s in all_samples if s.target_date < cut]
        holdout = [s for s in all_samples if s.target_date >= cut]
        holdout_by_h = {}
        for s in holdout:
            holdout_by_h.setdefault(s.horizon, []).append(s)

        self.stdout.write(
            f"품목 {len(series)} · 샘플 {len(all_samples)} "
            f"(train {len(train_split)} / holdout {len(holdout)}) · horizons {horizons}"
        )

        # 1) 홀드아웃으로 분위구간 보정계수 추정
        cal_forecaster = LightGBMGlobalForecaster().fit(train_split)
        interval_scale = _calibrate_scale(holdout_by_h, cal_forecaster)
        for h in sorted(interval_scale):
            sc = interval_scale[h]
            cov = f"{sc['coverage']:.1%}" if sc["coverage"] is not None else "n/a"
            self.stdout.write(f"  h={h:>2}: k={sc['k']} → 커버리지 {cov} (표본 {sc['samples']})")

        # 2) 전체 데이터로 운영 모델 재학습
        forecaster = LightGBMGlobalForecaster().fit(all_samples)
        artifact = TrainedLightGBMArtifact(
            forecaster=forecaster,
            interval_scale=interval_scale,
            metadata={
                "trained_at": timezone.now().isoformat(),
                "sample_count": len(all_samples),
                "item_count": len(series),
                "horizons": list(horizons),
                "train_end": target_dates[-1].isoformat(),
            },
        )
        path = artifact.save(options["output"])
        self.stdout.write(self.style.SUCCESS(f"아티팩트 저장: {path}"))
