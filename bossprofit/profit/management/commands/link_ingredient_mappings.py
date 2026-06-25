"""재료와 KAMIS 시장품목을 자동으로 연결한다.

seed_data.py 로 재료를 적재한 뒤 이 커맨드를 실행하면
IngredientMarketMapping(status=CONFIRMED) 이 생성되어
대시보드의 '재료 가격 위험' 분석이 활성화된다.

사용법:
    python manage.py link_ingredient_mappings --owner=ksm960mm
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from profit.models import Ingredient, IngredientMarketMapping, MarketItem
from accounts.services import get_user_store

# ingredient_id → (kamis_code, unit_factor, confidence)
#   unit_factor: KAMIS 가격(원/단위) → 재료 단위(g 또는 ea)로 환산
#   예) KAMIS 양파 1kg 가격 × 0.001 = 원/g
MAPPING = {
    # 채소류
    "ONION_G":       ("KAMIS:245:00:04", 0.001,  0.95),   # 양파 1kg → /g
    "GREEN_ONION_G": ("KAMIS:246:00:04", 0.001,  0.95),   # 대파 1kg → /g
    "CARROT_G":      ("KAMIS:152:01:04", 0.01,   0.90),   # 당근 100g → /g
    "CABBAGE_G":     ("KAMIS:212:00:04", 0.0005, 0.80),   # 양배추 ~1포기≈2kg → /g
    "POTATO_G":      ("POTATO",          0.00005, 0.85),  # 감자 20kg → /g
    "CHILI_EA":      ("KAMIS:222:00:04", 0.001,  0.75),   # 청양고추 10개 ≈ 1kg → /ea 근사
    # 축산·수산
    "PORK_LOIN_G":   ("KAMIS:231:01:04", 0.001,  0.80),   # 돼지고기 1마리 단가 근사
    "PORK_NECK_G":   ("KAMIS:231:01:04", 0.001,  0.75),   # 목살도 같은 품목으로 근사
}


class Command(BaseCommand):
    help = "재료(Ingredient)와 KAMIS 시장품목을 연결해 가격 위험 분석을 활성화합니다."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="연결할 계정(username)")
        parser.add_argument(
            "--dry-run", action="store_true", help="실제 저장하지 않고 결과만 출력"
        )

    def handle(self, *args, **opts):
        User = get_user_model()
        try:
            owner = User.objects.get(username=opts["owner"])
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"계정을 찾을 수 없음: {opts['owner']}"))
            return

        store = get_user_store(owner)
        if store is None:
            self.stderr.write(self.style.ERROR(f"{owner.username}의 매장이 없습니다."))
            return

        self.stdout.write(f"대상 매장: {store.name}\n")

        created = updated = skipped = 0

        for ing_id, (kamis_code, unit_factor, confidence) in MAPPING.items():
            ing = Ingredient.objects.filter(store=store, ingredient_id=ing_id).first()
            if ing is None:
                self.stdout.write(f"  재료 없음: {ing_id} — 건너뜀")
                skipped += 1
                continue

            market_item = MarketItem.objects.filter(code=kamis_code).first()
            if market_item is None:
                self.stdout.write(
                    self.style.WARNING(f"  시장품목 없음: {kamis_code} — {ing.name} 건너뜀")
                )
                skipped += 1
                continue

            obs_count = market_item.observations.count()
            self.stdout.write(
                f"  {ing.name} ({ing_id}) → {market_item.name} ({kamis_code})"
                f"  [factor={unit_factor}, conf={confidence}, obs={obs_count}]"
            )

            if not opts["dry_run"]:
                obj, is_created = IngredientMarketMapping.objects.update_or_create(
                    ingredient=ing,
                    market_item=market_item,
                    defaults={
                        "confidence": confidence,
                        "status": "CONFIRMED",
                        "reviewed_at": timezone.now(),
                    },
                )
                # ingredient.market_item 도 함께 설정 (예측 엔진용)
                if hasattr(ing, "market_item") and ing.market_item != market_item:
                    ing.market_item = market_item
                    ing.save(update_fields=["market_item"])
                if hasattr(ing, "commodity_unit_factor"):
                    ing.commodity_unit_factor = unit_factor
                    ing.save(update_fields=["commodity_unit_factor"])

                if is_created:
                    created += 1
                else:
                    updated += 1

        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING("\n[DRY-RUN] 실제 저장되지 않았습니다."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n완료: 신규 {created}건 / 갱신 {updated}건 / 건너뜀 {skipped}건"
                )
            )
