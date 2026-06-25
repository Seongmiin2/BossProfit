"""매장 재료를 실 시장품목(commodity)에 연결한다.

합성 시세(ING-*) 대신 실 KAMIS 가격 + 기상 데이터로 만든 commodity 예측을
재료 예측에 사용하도록 ingredient.market_item 을 실품목으로 바꾼다.
단위가 다르면(예: commodity 원/kg vs 재료 원/g) commodity_unit_factor 로 환산한다.

사용법:
    python manage.py link_commodities --owner=조윤
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from profit.models import Ingredient
from profit.scoping import get_active_store
from market.models import MarketItem

# 재료ID → 실 commodity 코드 + 단가 환산계수(commodity 가격단위 → 재료 단위)
#   KAMIS convert_kg_yn=Y → 원/kg. 재료가 원/g 이면 ×0.001.
COMMODITY_MAP = {
    "ONION_G": {"code": "ONION", "unit_factor": 0.001},   # 양파: 원/kg → 원/g
}


class Command(BaseCommand):
    help = "매장 재료를 실 시장품목(commodity)에 연결합니다."

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="대상 계정(username)")

    def handle(self, *args, **opts):
        User = get_user_model()
        try:
            owner = User.objects.get(username=opts["owner"])
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"계정을 찾을 수 없음: {opts['owner']}"))
            return
        store = get_active_store(owner)
        if store is None:
            self.stderr.write(self.style.ERROR(f"{owner.username}의 매장이 없습니다."))
            return

        linked = 0
        for ing_id, cfg in COMMODITY_MAP.items():
            ing = Ingredient.objects.filter(store=store, ingredient_id=ing_id).first()
            if ing is None:
                continue
            item = MarketItem.objects.filter(code=cfg["code"]).exclude(source="manual").first()
            if item is None:
                self.stdout.write(self.style.WARNING(f"  실품목 {cfg['code']} 없음 — {ing.name} 건너뜀"))
                continue
            ing.market_item = item
            ing.commodity_unit_factor = cfg["unit_factor"]
            ing.save(update_fields=["market_item", "commodity_unit_factor"])
            linked += 1
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ {ing.name}({ing_id}) → {item.code}({item.name}) ×{cfg['unit_factor']}"
            ))

        self.stdout.write(self.style.SUCCESS(f"\n완료: {linked}개 재료를 실 commodity에 연결"))
