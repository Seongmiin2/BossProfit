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

    ingredient_id = models.CharField(
        max_length=50, unique=True, help_text="예: PORK_LOIN_G"
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
    memo = models.TextField(blank=True, verbose_name="메모")

    class Meta:
        verbose_name = "식자재"
        verbose_name_plural = "식자재"
        ordering = ["category", "name"]

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

    menu_id = models.CharField(
        max_length=50, unique=True, help_text="예: M001"
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

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name="assumptions",
        verbose_name="소유자"
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
    def get_active(cls, user=None):
        """활성화된 가정 1개를 반환. 없으면 기본값으로 생성."""
        if user and user.is_authenticated:
            obj = cls.objects.filter(owner=user, is_active=True).first()
            if obj:
                return obj
            default = cls.objects.filter(owner__isnull=True, is_active=True).first()
            defaults = {
                "label": default.label if default else "기본 가정",
                "dine_in_share": default.dine_in_share if default else 0.50,
                "delivery_share": default.delivery_share if default else 0.30,
                "takeout_share": default.takeout_share if default else 0.20,
                "delivery_commission_rate": (
                    default.delivery_commission_rate if default else 0.12
                ),
                "rider_fee": default.rider_fee if default else 4600,
                "rider_fee_store_share": (
                    default.rider_fee_store_share if default else 1.0
                ),
                "target_food_cost_rate": (
                    default.target_food_cost_rate if default else 0.35
                ),
                "is_active": True,
            }
            return cls.objects.create(owner=user, **defaults)

        obj = cls.objects.filter(owner__isnull=True, is_active=True).first()
        return obj or cls.objects.create()


class MenuProfitSnapshot(models.Model):
    """계산 결과 스냅샷 (재료/가격/가정이 바뀌면 재생성)"""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="profit_snapshots",
        verbose_name="소유자",
    )
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
