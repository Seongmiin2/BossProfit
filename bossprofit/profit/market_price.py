"""
BOSSPROFIT 외부 식재료 시세 연동 (Phase 4)

설계:
- MarketPriceProvider: 식자재 1건의 "현재 시세 구매가"를 돌려주는 추상 인터페이스.
  반환값은 해당 식자재의 purchase_quantity 기준 가격(원)이라, 기존 unit_cost 계산과 단위가 호환됨.
- MockMarketPriceProvider: 키/인터넷 없이도 동작하는 기본 provider.
  (ingredient_id + 날짜) 해시 기반으로 ±12% 내에서 결정적으로 변동하는 시세를 시뮬레이션.
- KamisMarketPriceProvider: settings.KAMIS_CERT_KEY 가 설정되면 실제 KAMIS(농수산물유통정보)
  Open API를 호출. 매핑/네트워크 실패 시 해당 식자재는 건너뜀(None).

흐름:
- preview_price_changes(): 쓰기 없이 제안된 변경 목록만 계산해 반환.
- apply_price_changes(): 실제 purchase_price 업데이트 + IngredientPriceHistory 기록 + 스냅샷 재계산.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from typing import Optional
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import URLError

from django.conf import settings
from django.db import transaction

from .models import Ingredient, IngredientPriceHistory
from .calculator import recalculate_all


# ===== Provider 인터페이스 =====

class MarketPriceProvider:
    """식자재 → 현재 시세 구매가(purchase_quantity 기준, 원) 변환."""

    source = "manual"

    def fetch_price(self, ingredient: Ingredient, as_of: date) -> Optional[int]:
        raise NotImplementedError


class MockMarketPriceProvider(MarketPriceProvider):
    """결정적 모의 시세. 같은 날짜·재료면 항상 같은 값을 반환한다."""

    source = "mock"
    MAX_SWING = 0.12  # ±12%

    def _factor(self, seed: str) -> float:
        digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
        # 0..1999 → -1000..999 → -1.0..0.999 → ±MAX_SWING
        bucket = int(digest, 16) % 2000
        normalized = (bucket - 1000) / 1000.0
        return 1.0 + normalized * self.MAX_SWING

    def fetch_price(self, ingredient: Ingredient, as_of: date) -> Optional[int]:
        if not ingredient.purchase_price:
            return None
        seed = f"{ingredient.ingredient_id}:{as_of.isoformat()}"
        factor = self._factor(seed)
        new_price = round(ingredient.purchase_price * factor)
        # 10원 단위로 반올림(현실감)
        new_price = int(round(new_price / 10.0) * 10)
        return max(new_price, 0)


class KamisMarketPriceProvider(MarketPriceProvider):
    """KAMIS(한국농수산식품유통공사) 일별 부류별 도소매가격 API.

    settings.KAMIS_CERT_KEY / KAMIS_CERT_ID 필요.
    식자재명 → KAMIS 품목코드 매핑은 KAMIS_ITEM_MAP(설정)에 의존하며,
    매핑이 없거나 호출 실패 시 None(건너뜀)을 반환한다.
    """

    source = "kamis"
    # KAMIS는 https만 응답한다(http는 타임아웃). 또한 기본 urllib UA는 차단되므로
    # 브라우저 UA를 함께 보낸다.
    BASE_URL = "https://www.kamis.or.kr/service/price/xml.do"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )

    DEFAULT_COUNTRY = "1101"  # 서울

    def __init__(self, cert_key: str, cert_id: str, item_map: dict):
        self.cert_key = cert_key
        self.cert_id = cert_id
        self.item_map = item_map or {}

    def build_params(self, mapping: dict, as_of: date) -> dict:
        """dailyPriceByCategoryList 요청 파라미터 구성."""
        params = {
            "action": "dailyPriceByCategoryList",
            "p_cert_key": self.cert_key,
            "p_cert_id": self.cert_id,
            "p_returntype": "json",
            "p_product_cls_code": mapping.get("product_cls_code", "01"),  # 01 소매 / 02 도매
            "p_country_code": mapping.get("country_code", self.DEFAULT_COUNTRY),
            "p_regday": as_of.strftime("%Y-%m-%d"),
            "p_convert_kg_yn": mapping.get("convert_kg_yn", "Y"),  # Y: 1kg 환산가
            "p_item_category_code": mapping["category_code"],
        }
        if mapping.get("item_code"):
            params["p_item_code"] = mapping["item_code"]
        if mapping.get("kind_code"):
            params["p_kind_code"] = mapping["kind_code"]
        return params

    # KAMIS 일별 가격은 1~2일 지연·휴장이 있어 조회일에 데이터가 없을 수 있다.
    # 요청일부터 최대 LOOKBACK_DAYS 일 되짚어 가장 최근 가용 가격을 사용한다.
    LOOKBACK_DAYS = 7

    def _fetch_one(self, mapping: dict, as_of: date) -> Optional[float]:
        url = f"{self.BASE_URL}?{urlencode(self.build_params(mapping, as_of))}"
        req = Request(url, headers={"User-Agent": self.USER_AGENT})
        try:
            with urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (URLError, ValueError, TimeoutError, OSError):
            return None
        return _extract_kamis_price(
            payload,
            item_code=mapping.get("item_code"),
            kind_code=mapping.get("kind_code"),
        )

    def fetch_price(self, ingredient: Ingredient, as_of: date) -> Optional[int]:
        mapping = self.item_map.get(ingredient.ingredient_id) or self.item_map.get(ingredient.name)
        if not mapping or not mapping.get("category_code"):
            return None

        price = None
        for back in range(self.LOOKBACK_DAYS + 1):
            price = self._fetch_one(mapping, as_of - timedelta(days=back))
            if price is not None:
                break
        if price is None:
            return None
        # KAMIS 가격 단위(예: 1kg)를 식자재 purchase_quantity 기준으로 환산하는 계수.
        # 예) 1kg 단가를 1g 단위 마스터(구매수량 1000g)에 맞추면 그대로 1kg=1000g 이므로 1.0,
        #     "100g당 가격"으로 저장하려면 0.1 등. 매핑에서 지정.
        unit_factor = mapping.get("unit_factor", 1.0)
        return max(int(round(price * unit_factor)), 0)


def _parse_price(raw) -> Optional[float]:
    """KAMIS 가격 필드(dpr1)를 숫자로 변환. '-', 빈값, 리스트는 None."""
    if raw is None or isinstance(raw, (list, dict)):
        return None
    s = str(raw).replace(",", "").strip()
    if not s or s in ("-", "0"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _extract_kamis_price(payload, item_code=None, kind_code=None) -> Optional[float]:
    """KAMIS 응답에서 해당 품목/품종의 최근 조사가(dpr1)를 추출.

    dailyPriceByCategoryList는 한 부류 내 여러 품목을 반환하므로
    item_code(품목코드)·kind_code(품종코드)로 우선 필터링한 뒤 가격을 읽는다.
    """
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):  # 오류 시 data가 리스트(["001"])로 오는 경우 포함
        return None
    items = data.get("item")
    if isinstance(items, dict):
        items = [items]
    if not items:
        return None

    def matches(it: dict) -> bool:
        if item_code and str(item_code) not in (
            str(it.get("item_code", "")), str(it.get("productno", ""))
        ):
            return False
        if kind_code and str(it.get("kind_code", "")) != str(kind_code):
            return False
        return True

    # 1순위: 매핑 코드와 일치하는 품목
    for it in items:
        if isinstance(it, dict) and matches(it):
            price = _parse_price(it.get("dpr1"))
            if price is not None:
                return price
    # 2순위: 코드 필터가 없거나 못 찾은 경우 첫 유효 가격
    if not item_code and not kind_code:
        for it in items:
            if isinstance(it, dict):
                price = _parse_price(it.get("dpr1"))
                if price is not None:
                    return price
    return None


def get_provider() -> MarketPriceProvider:
    """설정에 따라 provider를 선택. KAMIS 키가 있으면 KAMIS, 없으면 Mock."""
    cert_key = getattr(settings, "KAMIS_CERT_KEY", "")
    cert_id = getattr(settings, "KAMIS_CERT_ID", "")
    if cert_key and cert_id:
        item_map = getattr(settings, "KAMIS_ITEM_MAP", {})
        return KamisMarketPriceProvider(cert_key, cert_id, item_map)
    return MockMarketPriceProvider()


# ===== 미리보기 / 반영 =====

def _build_change(ingredient: Ingredient, market_price: int) -> dict:
    current = ingredient.purchase_price
    qty = ingredient.purchase_quantity or 0
    delta = market_price - current
    delta_rate = (delta / current * 100) if current else 0.0
    return {
        "ingredient_id": ingredient.ingredient_id,
        "name": ingredient.name,
        "category": ingredient.category,
        "unit": ingredient.unit,
        "purchase_quantity": qty,
        "current_price": current,
        "current_unit_cost": round(ingredient.unit_cost, 4),
        "market_price": market_price,
        "market_unit_cost": round(market_price / qty, 4) if qty else 0.0,
        "delta": delta,
        "delta_rate": round(delta_rate, 2),
        "changed": delta != 0,
    }


def preview_price_changes(as_of: Optional[date] = None, store=None) -> dict:
    """제안된 시세 변경 목록을 (쓰기 없이) 계산해 반환. store가 주어지면 해당 매장 재료만."""
    as_of = as_of or date.today()
    provider = get_provider()

    ing_qs = Ingredient.objects.all()
    if store is not None:
        ing_qs = ing_qs.filter(store=store)

    changes = []
    skipped = []
    for ingredient in ing_qs:
        market_price = provider.fetch_price(ingredient, as_of)
        if market_price is None:
            skipped.append(ingredient.ingredient_id)
            continue
        changes.append(_build_change(ingredient, market_price))

    changes.sort(key=lambda c: abs(c["delta_rate"]), reverse=True)
    return {
        "source": provider.source,
        "as_of": as_of.isoformat(),
        "summary": {
            "total": len(changes),
            "up": sum(1 for c in changes if c["delta"] > 0),
            "down": sum(1 for c in changes if c["delta"] < 0),
            "unchanged": sum(1 for c in changes if c["delta"] == 0),
            "skipped": len(skipped),
        },
        "changes": changes,
    }


@transaction.atomic
def apply_price_changes(
    ingredient_ids: Optional[list[str]] = None,
    as_of: Optional[date] = None,
    store=None,
) -> dict:
    """시세를 실제 purchase_price에 반영하고 이력 기록 + 스냅샷 재계산.

    store가 주어지면 해당 매장 재료만 대상으로 한다.
    ingredient_ids 가 주어지면 해당 재료만, 없으면 변동이 있는 전체를 반영한다.
    """
    as_of = as_of or date.today()
    provider = get_provider()

    qs = Ingredient.objects.all()
    if store is not None:
        qs = qs.filter(store=store)
    if ingredient_ids:
        qs = qs.filter(ingredient_id__in=ingredient_ids)

    applied = []
    for ingredient in qs:
        market_price = provider.fetch_price(ingredient, as_of)
        if market_price is None or market_price == ingredient.purchase_price:
            continue

        old_price = ingredient.purchase_price
        IngredientPriceHistory.objects.create(
            ingredient=ingredient,
            old_price=old_price,
            new_price=market_price,
            source=provider.source,
            note=f"{as_of.isoformat()} 시세 연동",
        )
        ingredient.purchase_price = market_price
        ingredient.save(update_fields=["purchase_price"])
        applied.append({
            "ingredient_id": ingredient.ingredient_id,
            "name": ingredient.name,
            "old_price": old_price,
            "new_price": market_price,
            "delta": market_price - old_price,
        })

    # 원가가 바뀌었으니 수익성 스냅샷 재계산 (해당 매장만)
    snapshots = recalculate_all(store=store) if applied else []

    return {
        "source": provider.source,
        "as_of": as_of.isoformat(),
        "applied_count": len(applied),
        "recalculated": len(snapshots),
        "applied": applied,
    }
