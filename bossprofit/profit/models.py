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

    store = models.ForeignKey(
        "accounts.Store",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="ingredients",
        verbose_name="매장",
    )
    ingredient_id = models.CharField(
        max_length=50, help_text="예: PORK_LOIN_G"
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
    is_hq_supplied = models.BooleanField(
        default=False,
        verbose_name="본사 납품",
        help_text="본사에서 납품가가 정해져 공급되는 재료(시장가격 변동 영향이 거의 없음)",
    )
    memo = models.TextField(blank=True, verbose_name="메모")

    class Meta:
        verbose_name = "식자재"
        verbose_name_plural = "식자재"
        ordering = ["category", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["store", "ingredient_id"],
                name="unique_store_ingredient_id",
            ),
        ]

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
        "accounts.Store",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="menus",
        verbose_name="매장",
    )
    menu_id = models.CharField(
        max_length=50, help_text="예: M001"
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
        constraints = [
            models.UniqueConstraint(
                fields=["store", "menu_id"],
                name="unique_store_menu_id",
            ),
        ]

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


class IngredientMarketMapping(models.Model):
    STATUS_CHOICES = [
        ("PENDING", "검토 필요"),
        ("CONFIRMED", "확정"),
        ("REJECTED", "제외"),
    ]

    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name="market_mappings",
    )
    market_item = models.ForeignKey(
        "MarketItem",
        on_delete=models.CASCADE,
        related_name="ingredient_mappings",
    )
    confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["ingredient", "market_item"],
                name="unique_ingredient_market_mapping",
            )
        ]


class PurchasePriceObservation(models.Model):
    store = models.ForeignKey(
        "accounts.Store",
        on_delete=models.CASCADE,
        related_name="purchase_prices",
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name="purchase_prices",
    )
    purchased_at = models.DateTimeField()
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit = models.CharField(max_length=20)
    total_price = models.DecimalField(max_digits=14, decimal_places=2)
    supplier = models.CharField(max_length=100, blank=True)
    memo = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-purchased_at"]


class StoreSalesImport(models.Model):
    """A traceable import of store-owned POS sales data."""

    STATUS_CHOICES = [
        ("STARTED", "진행 중"),
        ("SUCCEEDED", "성공"),
        ("FAILED", "실패"),
    ]

    store = models.ForeignKey(
        "accounts.Store",
        on_delete=models.CASCADE,
        related_name="sales_imports",
    )
    source_name = models.CharField(max_length=255)
    source_sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="STARTED")
    row_count = models.PositiveIntegerField(default=0)
    imported_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["store", "source_sha256"],
                name="unique_store_sales_import_file",
            )
        ]


class DailyMenuSale(models.Model):
    """매장별 일일 메뉴 판매량."""

    CHANNEL_CHOICES = [
        ("ALL", "전체"),
        ("DINE_IN", "홀"),
        ("DELIVERY", "배달"),
        ("TAKEOUT", "포장"),
    ]

    store = models.ForeignKey(
        "accounts.Store",
        on_delete=models.CASCADE,
        related_name="daily_sales",
        verbose_name="매장",
    )
    menu = models.ForeignKey(
        Menu,
        on_delete=models.CASCADE,
        related_name="daily_sales",
        verbose_name="메뉴",
    )
    sale_date = models.DateField(verbose_name="판매일")
    channel = models.CharField(
        max_length=20,
        choices=CHANNEL_CHOICES,
        default="ALL",
        verbose_name="판매 채널",
    )
    quantity = models.PositiveIntegerField(verbose_name="판매량")
    gross_revenue = models.PositiveBigIntegerField(default=0)
    discount_amount = models.PositiveBigIntegerField(default=0)
    net_revenue = models.PositiveBigIntegerField(default=0)
    source_import = models.ForeignKey(
        StoreSalesImport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-sale_date", "menu_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["store", "menu", "sale_date", "channel"],
                name="unique_daily_menu_sale",
            ),
        ]

    def __str__(self):
        return f"{self.sale_date} / {self.menu.name} / {self.quantity}"


class ProfitAssumption(models.Model):
    """매장 단위 손익 가정 (MVP에서는 1행만 사용)"""

    store = models.ForeignKey(
        "accounts.Store",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="profit_assumptions",
        verbose_name="매장",
    )
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
    def get_active(cls, user=None, store=None):
        """활성화된 가정 1개를 반환. 없으면 기본값으로 생성."""
        if store is not None:
            obj = cls.objects.filter(store=store, is_active=True).first()
            if obj:
                return obj
            default = cls.objects.filter(
                store__isnull=True,
                owner__isnull=True,
                is_active=True,
            ).first()
            defaults = {
                "owner": user if user and user.is_authenticated else None,
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
            return cls.objects.create(store=store, **defaults)

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

        obj = cls.objects.filter(
            store__isnull=True,
            owner__isnull=True,
            is_active=True,
        ).first()
        return obj or cls.objects.create()


class MenuProfitSnapshot(models.Model):
    """계산 결과 스냅샷 (재료/가격/가정이 바뀌면 재생성)"""

    store = models.ForeignKey(
        "accounts.Store",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="profit_snapshots",
        verbose_name="매장",
    )
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


class MarketItem(models.Model):
    """시장 가격·거래량·예측의 기준 품목."""

    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50)
    variety = models.CharField(max_length=100, blank=True)
    grade = models.CharField(max_length=50, blank=True)
    region = models.CharField(max_length=100, default="전국")
    unit = models.CharField(max_length=30)
    standard_unit = models.CharField(max_length=30, default="kg")
    image_key = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class MarketPriceObservation(models.Model):
    """수집 시점과 출처를 보존하는 시장 관측값."""

    item = models.ForeignKey(
        MarketItem,
        on_delete=models.CASCADE,
        related_name="observations",
    )
    observed_date = models.DateField()
    region_code = models.CharField(max_length=30, blank=True)
    region_name = models.CharField(max_length=100, blank=True)
    market_type = models.CharField(max_length=30, default="RETAIL")
    unit = models.CharField(max_length=50, blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    volume = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    source = models.CharField(max_length=100)
    source_item_code = models.CharField(max_length=100, blank=True)
    source_unique_key = models.CharField(max_length=255, blank=True)
    raw_payload = models.ForeignKey(
        "RawSourcePayload",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="market_prices",
    )
    collected_at = models.DateTimeField()
    is_demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["-observed_date", "-collected_at"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "item",
                    "observed_date",
                    "source",
                    "region_code",
                    "market_type",
                    "unit",
                ],
                name="unique_market_observation",
            )
        ]


class IngestionRun(models.Model):
    """One observable, reproducible execution of an external data collector."""

    STATUS_CHOICES = [
        ("RUNNING", "진행 중"),
        ("SUCCEEDED", "성공"),
        ("PARTIAL", "일부 성공"),
        ("FAILED", "실패"),
    ]

    source = models.CharField(max_length=100)
    dataset = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="RUNNING")
    observation_cutoff = models.DateTimeField(null=True, blank=True)
    requested_params = models.JSONField(default=dict)
    source_version = models.CharField(max_length=100, blank=True)
    code_revision = models.CharField(max_length=64, blank=True)
    fetched_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    rejected_count = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]


class RawSourcePayload(models.Model):
    """Immutable raw API response with lineage back to its ingestion run."""

    ingestion_run = models.ForeignKey(
        IngestionRun,
        on_delete=models.CASCADE,
        related_name="raw_payloads",
    )
    source_url = models.URLField(max_length=1000)
    request_params = models.JSONField(default=dict)
    payload = models.JSONField()
    payload_sha256 = models.CharField(max_length=64)
    collected_at = models.DateTimeField()

    class Meta:
        ordering = ["-collected_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["ingestion_run", "payload_sha256"],
                name="unique_raw_payload_per_run",
            )
        ]


class CropProductionRegion(models.Model):
    item = models.ForeignKey(
        MarketItem,
        on_delete=models.CASCADE,
        related_name="production_regions",
    )
    region_code = models.CharField(max_length=30)
    region_name = models.CharField(max_length=100)
    weight = models.DecimalField(max_digits=7, decimal_places=6)
    mapping_confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    review_status = models.CharField(max_length=20, default="PENDING")
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    source = models.CharField(max_length=100, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item", "region_code", "valid_from"],
                name="unique_item_production_region_version",
            )
        ]


class WeatherStationMapping(models.Model):
    production_region = models.ForeignKey(
        CropProductionRegion,
        on_delete=models.CASCADE,
        related_name="station_mappings",
    )
    provider = models.CharField(max_length=50)
    station_id = models.CharField(max_length=50)
    station_name = models.CharField(max_length=100, blank=True)
    grid_x = models.IntegerField(null=True, blank=True)
    grid_y = models.IntegerField(null=True, blank=True)
    distance_km = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    weight = models.DecimalField(max_digits=7, decimal_places=6, default=1)
    mapping_confidence = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    review_status = models.CharField(max_length=20, default="PENDING")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["production_region", "provider", "station_id"],
                name="unique_region_weather_station",
            )
        ]


class WeatherObservation(models.Model):
    provider = models.CharField(max_length=50)
    station_id = models.CharField(max_length=50)
    observed_at = models.DateTimeField()
    variables = models.JSONField(default=dict)
    quality = models.JSONField(default=dict)
    collected_at = models.DateTimeField()
    raw_payload = models.ForeignKey(
        RawSourcePayload,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weather_observations",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "station_id", "observed_at"],
                name="unique_weather_observation",
            )
        ]


class WeatherForecastSnapshot(models.Model):
    provider = models.CharField(max_length=50)
    forecast_type = models.CharField(max_length=30)
    location_key = models.CharField(max_length=100)
    issued_at = models.DateTimeField()
    valid_at = models.DateTimeField()
    variables = models.JSONField(default=dict)
    collected_at = models.DateTimeField()
    raw_payload = models.ForeignKey(
        RawSourcePayload,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="weather_forecasts",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "provider",
                    "forecast_type",
                    "location_key",
                    "issued_at",
                    "valid_at",
                ],
                name="unique_weather_forecast_snapshot",
            )
        ]


class WeatherExposureFeature(models.Model):
    item = models.ForeignKey(
        MarketItem,
        on_delete=models.CASCADE,
        related_name="weather_exposures",
    )
    production_region = models.ForeignKey(
        CropProductionRegion,
        on_delete=models.CASCADE,
        related_name="weather_exposures",
    )
    as_of_date = models.DateField()
    windows = models.JSONField(default=dict)
    anomalies = models.JSONField(default=dict)
    feature_version = models.CharField(max_length=100)
    observation_cutoff = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "item",
                    "production_region",
                    "as_of_date",
                    "feature_version",
                ],
                name="unique_weather_exposure_feature",
            )
        ]


class WholesaleAuctionObservation(models.Model):
    source = models.CharField(max_length=100)
    source_record_id = models.CharField(max_length=150, default="", blank=True)
    auctioned_at = models.DateTimeField()
    market_code = models.CharField(max_length=50)
    market_name = models.CharField(max_length=100, blank=True)
    item = models.ForeignKey(
        MarketItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auction_observations",
    )
    source_item_code = models.CharField(max_length=100)
    source_item_name = models.CharField(max_length=100)
    origin_name = models.CharField(max_length=100, blank=True)
    grade = models.CharField(max_length=50, blank=True)
    unit = models.CharField(max_length=50, blank=True)
    volume = models.DecimalField(max_digits=16, decimal_places=3)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    collected_at = models.DateTimeField()
    raw_payload = models.ForeignKey(
        RawSourcePayload,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auction_observations",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["source", "source_record_id"],
                name="unique_wholesale_auction_observation",
            )
        ]


class ProductionStatistic(models.Model):
    item = models.ForeignKey(
        MarketItem,
        on_delete=models.CASCADE,
        related_name="production_statistics",
    )
    region_code = models.CharField(max_length=30)
    region_name = models.CharField(max_length=100)
    period_start = models.DateField()
    period_end = models.DateField()
    acreage = models.DecimalField(max_digits=16, decimal_places=3, null=True, blank=True)
    yield_amount = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        null=True,
        blank=True,
    )
    production_amount = models.DecimalField(
        max_digits=16,
        decimal_places=3,
        null=True,
        blank=True,
    )
    unit = models.CharField(max_length=30)
    source = models.CharField(max_length=100)
    issued_at = models.DateTimeField(null=True, blank=True)
    collected_at = models.DateTimeField()
    raw_payload = models.ForeignKey(
        RawSourcePayload,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="production_statistics",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "item",
                    "region_code",
                    "period_start",
                    "period_end",
                    "source",
                ],
                name="unique_production_statistic",
            )
        ]


class ActionPlan(models.Model):
    STATUS_CHOICES = [
        ("SAVED", "저장"),
        ("IN_PROGRESS", "진행 중"),
        ("COMPLETED", "완료"),
        ("CANCELLED", "중단"),
    ]

    store = models.ForeignKey(
        "accounts.Store",
        on_delete=models.CASCADE,
        related_name="action_plans",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bossprofit_action_plans",
    )
    title = models.CharField(max_length=200)
    period_label = models.CharField(max_length=50)
    reason = models.TextField()
    data_used = models.JSONField(default=list)
    source_documents = models.JSONField(default=list)
    expected_effect = models.TextField(blank=True)
    success_criteria = models.TextField(blank=True)
    stop_criteria = models.TextField(blank=True)
    review_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="SAVED")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class ForecastRun(models.Model):
    STATUS_CHOICES = [
        ("RUNNING", "진행 중"),
        ("SUCCEEDED", "성공"),
        ("FAILED", "실패"),
    ]

    item = models.ForeignKey(
        MarketItem,
        on_delete=models.CASCADE,
        related_name="forecast_runs",
    )
    as_of_date = models.DateField()
    model_version = models.CharField(max_length=100)
    feature_version = models.CharField(max_length=100)
    observation_cutoff = models.DateTimeField()
    code_revision = models.CharField(max_length=64, blank=True)
    random_seed = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="RUNNING")
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-as_of_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "as_of_date", "model_version"],
                name="unique_forecast_run",
            )
        ]


class ForecastPoint(models.Model):
    run = models.ForeignKey(
        ForecastRun,
        on_delete=models.CASCADE,
        related_name="points",
    )
    target_date = models.DateField()
    horizon_days = models.PositiveSmallIntegerField()
    median = models.DecimalField(max_digits=14, decimal_places=2)
    lower = models.DecimalField(max_digits=14, decimal_places=2)
    upper = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "horizon_days"],
                name="unique_forecast_point",
            ),
            models.CheckConstraint(
                condition=models.Q(lower__lte=models.F("median")),
                name="forecast_lower_lte_median",
            ),
            models.CheckConstraint(
                condition=models.Q(median__lte=models.F("upper")),
                name="forecast_median_lte_upper",
            ),
        ]


class ForecastComponent(models.Model):
    point = models.OneToOneField(
        ForecastPoint,
        on_delete=models.CASCADE,
        related_name="components",
    )
    base_prediction = models.DecimalField(max_digits=14, decimal_places=2)
    weather_adjustment = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    residual_adjustment = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    weather_forecast_issued_at = models.DateTimeField(null=True, blank=True)
    details = models.JSONField(default=dict)


class OutOfFoldForecast(models.Model):
    item = models.ForeignKey(
        MarketItem,
        on_delete=models.CASCADE,
        related_name="oof_forecasts",
    )
    fold_id = models.CharField(max_length=100)
    train_cutoff = models.DateField()
    target_date = models.DateField()
    horizon_days = models.PositiveSmallIntegerField()
    prediction = models.DecimalField(max_digits=14, decimal_places=2)
    actual = models.DecimalField(max_digits=14, decimal_places=2)
    model_version = models.CharField(max_length=100)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "item",
                    "fold_id",
                    "target_date",
                    "horizon_days",
                    "model_version",
                ],
                name="unique_oof_forecast",
            )
        ]


class ResidualObservation(models.Model):
    oof_forecast = models.OneToOneField(
        OutOfFoldForecast,
        on_delete=models.CASCADE,
        related_name="residual_observation",
    )
    residual = models.DecimalField(max_digits=14, decimal_places=2)
    residual_type = models.CharField(max_length=30, default="ACTUAL_MINUS_PREDICTION")


class ForecastCalibration(models.Model):
    item = models.ForeignKey(
        MarketItem,
        on_delete=models.CASCADE,
        related_name="calibrations",
        null=True,
        blank=True,
    )
    model_version = models.CharField(max_length=100)
    horizon_days = models.PositiveSmallIntegerField()
    target_coverage = models.DecimalField(max_digits=5, decimal_places=4)
    measured_coverage = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
    )
    absolute_error_quantile = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )
    fitted_from = models.DateField()
    fitted_to = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item", "model_version", "horizon_days"],
                name="unique_forecast_calibration",
            )
        ]


class MarketForecast(models.Model):
    """품목·horizon별 가격 예측과 예측구간."""

    item = models.ForeignKey(
        MarketItem,
        on_delete=models.CASCADE,
        related_name="forecasts",
    )
    run = models.ForeignKey(
        ForecastRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_forecasts",
    )
    as_of_date = models.DateField()
    target_date = models.DateField()
    horizon_days = models.PositiveSmallIntegerField()
    predicted_price = models.DecimalField(max_digits=14, decimal_places=2)
    lower_price = models.DecimalField(max_digits=14, decimal_places=2)
    upper_price = models.DecimalField(max_digits=14, decimal_places=2)
    expected_change_rate = models.DecimalField(max_digits=8, decimal_places=4)
    confidence_grade = models.CharField(max_length=20, default="검증 전")
    model_version = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["horizon_days", "-as_of_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "as_of_date", "horizon_days", "model_version"],
                name="unique_market_forecast",
            )
        ]


class MarketModelMetric(models.Model):
    """검증이 완료된 모델 성능만 화면에 노출하기 위한 지표."""

    item = models.ForeignKey(
        MarketItem,
        on_delete=models.CASCADE,
        related_name="model_metrics",
        null=True,
        blank=True,
    )
    model_version = models.CharField(max_length=100)
    horizon_days = models.PositiveSmallIntegerField()
    direction_accuracy = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        null=True,
        blank=True,
    )
    wape = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    mase = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    mae = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    rmse = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    bias = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    pinball_loss = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    interval_coverage = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        null=True,
        blank=True,
    )
    interval_width = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
    )
    sample_count = models.PositiveIntegerField(default=0)
    evaluation_method = models.CharField(
        max_length=100,
        default="ROLLING_ORIGIN_HOLDOUT",
    )
    evaluation_start = models.DateField(null=True, blank=True)
    evaluation_end = models.DateField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["item", "model_version", "horizon_days"],
                name="unique_market_model_metric",
            )
        ]


class ForecastModelComparison(models.Model):
    item = models.ForeignKey(
        MarketItem,
        on_delete=models.CASCADE,
        related_name="model_comparisons",
    )
    horizon_days = models.PositiveSmallIntegerField()
    candidate_version = models.CharField(max_length=100)
    baseline_version = models.CharField(max_length=100)
    metric = models.CharField(max_length=30, default="MAE")
    candidate_value = models.DecimalField(max_digits=14, decimal_places=4)
    baseline_value = models.DecimalField(max_digits=14, decimal_places=4)
    difference = models.DecimalField(max_digits=14, decimal_places=4)
    ci_lower = models.DecimalField(max_digits=14, decimal_places=4)
    ci_upper = models.DecimalField(max_digits=14, decimal_places=4)
    sample_count = models.PositiveIntegerField()
    method = models.CharField(max_length=50, default="PAIRED_BOOTSTRAP")
    is_significant = models.BooleanField(default=False)
    random_seed = models.PositiveIntegerField(default=42)
    evaluation_start = models.DateField()
    evaluation_end = models.DateField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "item",
                    "horizon_days",
                    "candidate_version",
                    "baseline_version",
                    "metric",
                ],
                name="unique_forecast_model_comparison",
            )
        ]


class MarketRecommendation(models.Model):
    """예측 결과를 구매 행동 언어로 변환한 검증 가능한 권고."""

    DECISION_CHOICES = [
        ("BUY", "미리 구매 검토"),
        ("WATCH", "관망"),
        ("AVOID", "구매 보류"),
    ]

    item = models.ForeignKey(
        MarketItem,
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    as_of_date = models.DateField()
    decision = models.CharField(max_length=20, choices=DECISION_CHOICES)
    summary = models.TextField()
    action = models.TextField()
    evidence = models.JSONField(default=list)
    is_demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["-as_of_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "as_of_date"],
                name="unique_market_recommendation",
            )
        ]


class MarketRankingSnapshot(models.Model):
    """현재 순위와 이전 순위 이동을 보존하는 랭킹 스냅샷."""

    TYPE_CHOICES = [
        ("VOLUME", "거래량"),
        ("TODAY", "오늘 가격 변동"),
        ("TOMORROW", "내일 예상 변동"),
    ]

    ranking_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    as_of_date = models.DateField()
    item = models.ForeignKey(
        MarketItem,
        on_delete=models.CASCADE,
        related_name="ranking_snapshots",
    )
    rank = models.PositiveSmallIntegerField()
    previous_rank = models.PositiveSmallIntegerField(null=True, blank=True)
    score = models.DecimalField(max_digits=14, decimal_places=4)
    display_change_rate = models.DecimalField(max_digits=8, decimal_places=4)
    generated_at = models.DateTimeField(auto_now_add=True)
    is_demo = models.BooleanField(default=False)

    class Meta:
        ordering = ["ranking_type", "as_of_date", "rank"]
        constraints = [
            models.UniqueConstraint(
                fields=["ranking_type", "as_of_date", "rank"],
                name="unique_market_ranking_position",
            ),
            models.UniqueConstraint(
                fields=["ranking_type", "as_of_date", "item"],
                name="unique_market_ranking_item",
            ),
        ]
