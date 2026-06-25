"""매장의 모든 재료를 가격 예측 대상으로 만들고 예측을 생성한다.

각 재료는 전용 MarketItem(코드 ING-<store>-<ingredient_id>)에 1:1로 연동된다.
실제 KAMIS 시세가 없는 가공재료가 대부분이므로, 재료의 현재 단가(unit_cost)를
기준점으로 합성(synthetic) 일별 가격 시계열을 만들어 예측 파이프라인에 태운다.
시계열만 있으면 base + 구간보정 예측이 나오고, 날씨·잔차 단계는 자동 비활성된다.

사용법:
    python manage.py forecast_ingredients --owner=조윤
    python manage.py forecast_ingredients --owner=조윤 --as-of 2026-06-25 --horizons 7,30 --history-days 120
"""
import math
import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from profit.models import Ingredient
from profit.scoping import get_active_store
from market.models import MarketItem, MarketPriceObservation
from forecast.pipeline import produce_forecast


def _synthetic_series(anchor: float, days: int, end: date, seed: int):
    """anchor(현재 단가) 주변으로 완만한 추세·주간 계절성·소량 노이즈를 가진 일별 시계열."""
    rng = random.Random(seed)
    # 결정적 추세 방향(-1~+1)과 진폭
    drift = (rng.random() - 0.5) * 0.18          # 전체 구간 누적 ±9%
    season_amp = 0.04 + rng.random() * 0.05      # 주간 파형 4~9%
    phase = rng.random() * 2 * math.pi
    floor = max(anchor * 0.2, 0.01)
    out = []
    for i in range(days):
        t = i / max(days - 1, 1)                  # 0 → 1
        trend = 1 + drift * t
        season = 1 + season_amp * math.sin(2 * math.pi * (i / 7.0) + phase)
        noise = 1 + rng.uniform(-0.015, 0.015)
        price = max(anchor * trend * season * noise, floor)
        out.append((end - timedelta(days=days - 1 - i), round(price, 4)))
    return out


class Command(BaseCommand):
    help = "매장 재료별 합성 시세를 만들어 가격 예측을 생성합니다."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="대상 계정(username)")
        parser.add_argument("--as-of", default=None, help="예측 기준일 YYYY-MM-DD (기본: 오늘)")
        parser.add_argument("--horizons", default="7,30")
        parser.add_argument("--history-days", type=int, default=120)

    def handle(self, *args, **opts):
        User = get_user_model()
        try:
            owner = User.objects.get(username=opts["owner"])
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"계정을 찾을 수 없음: {opts['owner']}"))
            return
        store = get_active_store(owner)
        if store is None:
            self.stderr.write(self.style.ERROR(f"{owner.username}의 매장이 없습니다. 먼저 seed_data를 실행하세요."))
            return

        as_of = date.fromisoformat(opts["as_of"]) if opts["as_of"] else timezone.localdate()
        horizons = [int(h) for h in opts["horizons"].split(",") if h.strip()]
        history_days = max(opts["history_days"], 95)

        ingredients = list(Ingredient.objects.filter(store=store).order_by("category", "name"))
        if not ingredients:
            self.stderr.write(self.style.ERROR("재료가 없습니다."))
            return

        self.stdout.write(f"매장 [{store.name}] 재료 {len(ingredients)}개 · as_of={as_of} · horizons={horizons}\n")

        ok, failed, skipped, now = 0, 0, 0, timezone.now()
        for ing in ingredients:
            # 본사 발주 재료(고정가)는 시세 변동이 없어 예측 대상에서 제외한다.
            if ing.is_supplied:
                self.stdout.write(f"  · {ing.name}: 본사 발주(고정가) — 예측 제외")
                skipped += 1
                continue
            # 이미 실 commodity(KAMIS·기상 실데이터)에 연결된 재료는 합성으로 덮지 않는다.
            if ing.market_item_id and ing.market_item.source != "manual":
                self.stdout.write(f"  · {ing.name}: 실 commodity({ing.market_item.code}) 연결됨 — 합성 제외")
                skipped += 1
                continue
            anchor = ing.unit_cost
            if not anchor or anchor <= 0:
                self.stdout.write(f"  - {ing.name}: 단가 0 — 건너뜀")
                failed += 1
                continue

            code = f"ING-{store.id}-{ing.ingredient_id}"
            with transaction.atomic():
                item, _ = MarketItem.objects.update_or_create(
                    code=code,
                    defaults={
                        "name": ing.name,
                        "category": ing.category or "재료",
                        "standard_unit": ing.unit,
                        "source": "manual",
                        "is_active": True,
                    },
                )
                if ing.market_item_id != item.id:
                    ing.market_item = item
                    ing.save(update_fields=["market_item"])

                # 합성 시세 멱등 적재 (load_price_series 기본 필터: retail/region=""/kamis)
                series = _synthetic_series(float(anchor), history_days, as_of, seed=hash(code) & 0xFFFFFFFF)
                for obs_date, price in series:
                    MarketPriceObservation.objects.update_or_create(
                        source="kamis", item=item, observation_date=obs_date,
                        region="", market_type="retail", grade="", unit=ing.unit,
                        defaults={
                            "price": Decimal(str(price)),
                            "collected_at": now,
                            "raw_ref": "synthetic",
                            "quality_flag": "ok",
                        },
                    )

            out = produce_forecast(item, as_of, horizons=horizons, persist=True)
            if out.get("ok"):
                ok += 1
                meds = ", ".join(f"{p['horizon']}d={p['median']}" for p in out["points"])
                self.stdout.write(self.style.SUCCESS(f"  ✓ {ing.name} ({ing.unit}) base={anchor:.3f} → {meds}"))
            else:
                failed += 1
                self.stdout.write(self.style.WARNING(f"  ✗ {ing.name}: {out.get('reason')}"))

        self.stdout.write(self.style.SUCCESS(f"\n완료: 예측 {ok}건 / 본사발주제외 {skipped}건 / 실패 {failed}건"))
