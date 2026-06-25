"""
BOSSPROFIT 데이터 모델

설계 원칙:
- Ingredient: 구매 단위(예: 1kg)와 가격을 그대로 저장하고 unit_cost는 property로 자동 계산
  → 사장님이 "1kg 12,300원에 샀어요" 라고 입력한 그대로 저장하는 게 직관적
- RecipeItem: 메뉴 × 재료 + 사용량(g, 개 등)
- ProfitAssumption: 매장 단위 가정. 1매장 1행이 기본 (MVP는 단일 매장)
- MenuProfitSnapshot: 계산 결과 캐싱용. 가격/원가가 바뀔 때마다 재계산
"""
from django.db import models
from django.conf import settings


class Store(models.Model):
    """매장. 모든 매장 데이터(재료·메뉴·손익가정)의 소유 단위.

    MVP는 사용자당 1매장을 기본으로 하되, StoreMember로 추후 직원 초대를 확장한다.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_stores",
        verbose_name="소유자",
    )
    name = models.CharField(max_length=100, verbose_name="매장명")
    business_type = models.CharField(
        max_length=50, blank=True, verbose_name="업종"
    )
    region = models.CharField(max_length=50, blank=True, verbose_name="지역")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "매장"
        verbose_name_plural = "매장"
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} (owner={self.owner_id})"


class StoreMember(models.Model):
    """매장 구성원과 권한. MVP에서는 OWNER 1명이 기본."""

    ROLE_CHOICES = [
        ("OWNER", "사장"),
        ("MANAGER", "매니저"),
        ("STAFF", "직원"),
    ]

    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="store_memberships",
    )
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default="OWNER", verbose_name="역할"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "매장 구성원"
        verbose_name_plural = "매장 구성원"
        unique_together = [("store", "user")]

    def __str__(self):
        return f"{self.store.name} · {self.user} ({self.role})"


class Ingredient(models.Model):
    """식자재 마스터"""

    CATEGORY_CHOICES = [
        ("돈까스", "돈까스"),
        ("우동", "우동"),
        ("만두", "만두"),
        ("공통", "공통"),
        ("안주", "안주"),
        ("포장", "포장"),
        ("기타", "기타"),
    ]

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="ingredients",
        verbose_name="매장",
    )
    ingredient_id = models.CharField(
        max_length=50, help_text="예: PORK_LOIN_G (매장 내 고유)"
    )
    name = models.CharField(max_length=100, verbose_name="재료명")
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, blank=True, verbose_name="카테고리"
    )
    purchase_quantity = models.FloatField(
        verbose_name="구매 수량", help_text="예: 1kg을 그램으로 환산한 1000"
    )
    purchase_price = models.PositiveIntegerField(verbose_name="구매 가격(원)")
    unit = models.CharField(max_length=20, default="g", verbose_name="단위")
    is_supplied = models.BooleanField(
        default=False,
        verbose_name="본사 발주 재료(고정가)",
        help_text="본사에서 고정가로 발주받는 재료. 시세 변동이 없으므로 가격 예측에서 제외한다.",
    )
    market_item = models.ForeignKey(
        "market.MarketItem",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingredients",
        verbose_name="연동 시장품목",
        help_text="가격 예측 대상으로 연동된 시장품목(재료별 1:1). "
                  "실 commodity(양파 등) 연결 시 KAMIS·기상 실데이터 예측을 사용한다.",
    )
    commodity_unit_factor = models.FloatField(
        default=1.0,
        verbose_name="시장품목 단가 환산계수",
        help_text="시장품목 가격(예: 원/kg)을 재료 단위(예: 원/g)로 환산하는 계수. "
                  "실 commodity 연결 시 사용(예: 원/kg→원/g = 0.001).",
    )
    memo = models.TextField(blank=True, verbose_name="메모")

    class Meta:
        verbose_name = "식자재"
        verbose_name_plural = "식자재"
        ordering = ["category", "name"]
        unique_together = [("store", "ingredient_id")]

    @property
    def unit_cost(self) -> float:
        """단위당 원가 (예: 1g당 12.3원)"""
        if not self.purchase_quantity:
            return 0.0
        return self.purchase_price / self.purchase_quantity

    def __str__(self):
        return f"{self.name} ({self.purchase_price:,}원 / {self.purchase_quantity}{self.unit})"


class Menu(models.Model):
    """판매 메뉴"""

    CATEGORY_CHOICES = [
        ("돈까스", "돈까스"),
        ("우동", "우동"),
        ("만두", "만두"),
        ("세트", "세트"),
        ("안주", "안주"),
        ("기타", "기타"),
    ]

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="menus",
        verbose_name="매장",
    )
    menu_id = models.CharField(
        max_length=50, help_text="예: M001 (매장 내 고유)"
    )
    name = models.CharField(max_length=100, verbose_name="메뉴명")
    category = models.CharField(
        max_length=20, choices=CATEGORY_CHOICES, verbose_name="카테고리"
    )
    price = models.PositiveIntegerField(verbose_name="판매가(원)")
    monthly_orders = models.PositiveIntegerField(
        default=0, verbose_name="월 판매량"
    )
    packaging_cost = models.PositiveIntegerField(
        default=0, verbose_name="포장 비용(원)"
    )
    is_active = models.BooleanField(default=True, verbose_name="판매중")

    class Meta:
        verbose_name = "메뉴"
        verbose_name_plural = "메뉴"
        ordering = ["menu_id"]
        unique_together = [("store", "menu_id")]

    def food_cost(self) -> float:
        return sum(item.cost for item in self.recipe_items.all())

    def food_cost_rate(self) -> float:
        if not self.price:
            return 0.0
        return self.food_cost() / self.price

    def __str__(self):
        return f"{self.name} ({self.price:,}원)"


class RecipeItem(models.Model):
    """메뉴 × 재료 사용량"""

    menu = models.ForeignKey(
        Menu, on_delete=models.CASCADE, related_name="recipe_items"
    )
    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.PROTECT, related_name="used_in"
    )
    quantity = models.FloatField(verbose_name="사용량")
    memo = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "레시피 항목"
        verbose_name_plural = "레시피 항목"
        unique_together = [("menu", "ingredient")]
        ordering = ["menu", "ingredient"]

    @property
    def cost(self) -> float:
        return self.ingredient.unit_cost * self.quantity

    def __str__(self):
        return f"{self.menu.name} ← {self.ingredient.name} {self.quantity}{self.ingredient.unit}"


class ProfitAssumption(models.Model):
    """매장 단위 손익 가정 (MVP에서는 1행만 사용)"""

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="assumptions",
        verbose_name="매장",
    )
    label = models.CharField(
        max_length=50, default="기본 가정", verbose_name="가정 이름"
    )
    dine_in_share = models.FloatField(default=0.50, verbose_name="홀 비중")
    delivery_share = models.FloatField(default=0.30, verbose_name="배달 비중")
    takeout_share = models.FloatField(default=0.20, verbose_name="포장 비중")
    delivery_commission_rate = models.FloatField(
        default=0.12, verbose_name="배달앱 수수료율"
    )
    rider_fee = models.PositiveIntegerField(
        default=4600, verbose_name="배달 기사 수수료(원)"
    )
    rider_fee_store_share = models.FloatField(
        default=1.0, verbose_name="기사료 가게 부담률"
    )
    target_food_cost_rate = models.FloatField(
        default=0.35, verbose_name="목표 원가율"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "손익 가정"
        verbose_name_plural = "손익 가정"

    def __str__(self):
        return f"{self.label} (홀{int(self.dine_in_share*100)}/배{int(self.delivery_share*100)}/포{int(self.takeout_share*100)})"

    @classmethod
    def get_active(cls, store=None):
        """매장의 활성 가정 1개를 반환. 없으면 기본값으로 생성."""
        if store is not None:
            obj = cls.objects.filter(store=store, is_active=True).first()
            if obj is None:
                obj = cls.objects.create(store=store)
            return obj
        # store 미지정(레거시/공개 컨텍스트): store 없는 기본 가정
        obj = cls.objects.filter(store__isnull=True, is_active=True).first()
        if obj is None:
            obj = cls.objects.create()
        return obj


class IngredientPriceHistory(models.Model):
    """식자재 단가 변경 이력 (외부 시세 연동/수동 변경 시 기록)"""

    SOURCE_CHOICES = [
        ("mock", "모의 시세"),
        ("kamis", "KAMIS 시세"),
        ("manual", "수동 입력"),
    ]

    ingredient = models.ForeignKey(
        Ingredient, on_delete=models.CASCADE, related_name="price_history"
    )
    old_price = models.PositiveIntegerField(verbose_name="이전 구매가(원)")
    new_price = models.PositiveIntegerField(verbose_name="변경 구매가(원)")
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default="manual", verbose_name="출처"
    )
    note = models.CharField(max_length=255, blank=True, verbose_name="비고")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "단가 변경 이력"
        verbose_name_plural = "단가 변경 이력"
        ordering = ["-created_at"]

    @property
    def delta(self) -> int:
        return self.new_price - self.old_price

    @property
    def delta_rate(self) -> float:
        """변동률(%) — 이전가 대비"""
        if not self.old_price:
            return 0.0
        return (self.new_price - self.old_price) / self.old_price * 100

    def __str__(self):
        sign = "+" if self.delta >= 0 else ""
        return f"{self.ingredient.name}: {self.old_price:,} → {self.new_price:,} ({sign}{self.delta_rate:.1f}%)"


class MenuProfitSnapshot(models.Model):
    """계산 결과 스냅샷 (재료/가격/가정이 바뀌면 재생성)"""

    menu = models.ForeignKey(
        Menu, on_delete=models.CASCADE, related_name="snapshots"
    )
    base_cost = models.FloatField(verbose_name="재료 원가")
    food_cost_rate = models.FloatField(verbose_name="원가율")
    dine_in_margin = models.FloatField(verbose_name="홀 마진")
    takeout_margin = models.FloatField(verbose_name="포장 마진")
    delivery_margin = models.FloatField(verbose_name="배달 마진")
    weighted_margin = models.FloatField(verbose_name="가중 마진")
    monthly_profit = models.FloatField(verbose_name="월 예상 이익")
    monthly_revenue = models.FloatField(verbose_name="월 매출")
    signal = models.CharField(max_length=50, verbose_name="신호등")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "수익성 스냅샷"
        verbose_name_plural = "수익성 스냅샷"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d}] {self.menu.name} → {self.signal}"

    @property
    def signal_color(self) -> str:
        if "🟢" in self.signal:
            return "green"
        if "🟡" in self.signal:
            return "yellow"
        return "red"
