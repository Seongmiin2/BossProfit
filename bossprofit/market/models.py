"""시장 데이터 모델 (담당 B).

설계 원칙 (핵심 완료 기준 직결):
- 재현성: 모든 관측은 IngestionRun에 연결되고, 자연키 upsert로 같은 원본을 다시 넣어도 중복이 없다.
- 원본 보존: 관측마다 source와 raw_ref(원본 응답/식별자 참조)를 남긴다.
- 시간 구분: observation_date(valid_at, 가격이 유효한 날) / collected_at(수집 시각)을
  분리 저장한다. 예보·수정 데이터의 issued_at은 향후 ForecastSnapshot 단계에서 추가한다.
- 누수 방지: 관측은 '그 날 실제 공개된 값'이며, 미래 정보를 끌어오지 않는다.
  point-in-time 재구성을 위해 collected_at을 보존한다.
- 품질: 이상치는 자동 삭제하지 않고 quality_flag로 표시한다(실제 사건일 수 있음).
"""
from django.db import models


class MarketItem(models.Model):
    """표준 시장 품목 카탈로그. KAMIS 등 외부 소스 코드를 표준 코드로 정규화한다."""

    SOURCE_CHOICES = [
        ("kamis", "KAMIS"),
        ("wholesale", "도매시장 경락"),
        ("manual", "수동 등록"),
    ]
    MARKET_LEVEL_CHOICES = [
        ("retail", "소매"),
        ("wholesale", "도매"),
    ]

    code = models.CharField(
        max_length=64, unique=True,
        help_text="표준 품목 코드 (예: ONION, NAPA_CABBAGE)",
    )
    name = models.CharField(max_length=100, verbose_name="품목명")
    category = models.CharField(max_length=50, blank=True, verbose_name="부류")
    variety = models.CharField(max_length=50, blank=True, verbose_name="품종")
    standard_unit = models.CharField(
        max_length=10, default="g",
        help_text="표준단위: g / ml / ea",
    )

    # 외부 소스 매핑 (KAMIS 코드 등)
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default="kamis", verbose_name="출처"
    )
    source_category_code = models.CharField(max_length=20, blank=True)
    source_item_code = models.CharField(max_length=20, blank=True)
    source_kind_code = models.CharField(max_length=20, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "시장 품목"
        verbose_name_plural = "시장 품목"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["source", "source_item_code", "source_kind_code"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class IngestionRun(models.Model):
    """수집 실행 추적. 실패·부분성공·재현성의 단일 진실 공급원."""

    STATUS_CHOICES = [
        ("running", "실행 중"),
        ("success", "성공"),
        ("partial", "부분 성공"),
        ("failed", "실패"),
    ]

    source = models.CharField(
        max_length=40, verbose_name="수집 소스",
        help_text="예: kamis_daily, wholesale_auction, asos",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="running"
    )
    # 재현성: 어떤 파라미터로 어느 코드 버전이 수집했는가
    params = models.JSONField(default=dict, blank=True, verbose_name="수집 파라미터")
    code_version = models.CharField(
        max_length=64, blank=True, help_text="git sha 또는 릴리스 라벨"
    )

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    # 집계 카운트
    fetched_count = models.PositiveIntegerField(default=0)
    created_count = models.PositiveIntegerField(default=0)
    updated_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    quality_issue_count = models.PositiveIntegerField(default=0)

    error = models.TextField(blank=True)

    class Meta:
        verbose_name = "수집 실행"
        verbose_name_plural = "수집 실행"
        ordering = ["-started_at"]

    def __str__(self):
        return f"[{self.source}] {self.status} ({self.started_at:%Y-%m-%d %H:%M})"

    def mark(self, status, error=""):
        from django.utils import timezone
        self.status = status
        self.error = error
        self.finished_at = timezone.now()
        self.save(update_fields=[
            "status", "error", "finished_at",
            "fetched_count", "created_count", "updated_count",
            "skipped_count", "quality_issue_count",
        ])


class MarketPriceObservation(models.Model):
    """시장 가격 관측 1건. 자연키 upsert로 멱등하게 적재된다."""

    MARKET_TYPE_CHOICES = [
        ("retail", "소매"),
        ("wholesale", "도매"),
    ]
    QUALITY_CHOICES = [
        ("ok", "정상"),
        ("anomaly_jump", "급등락 의심"),
        ("nonpositive", "0/음수"),
        ("imputed", "대체값"),
        ("stale", "장기 동일값"),
    ]

    item = models.ForeignKey(
        MarketItem, on_delete=models.CASCADE, related_name="observations"
    )
    observation_date = models.DateField(
        verbose_name="관측일(valid_at)", help_text="가격이 유효한 날짜"
    )
    region = models.CharField(max_length=40, blank=True, verbose_name="지역")
    market_type = models.CharField(
        max_length=12, choices=MARKET_TYPE_CHOICES, default="retail"
    )
    grade = models.CharField(max_length=20, blank=True, verbose_name="등급")
    unit = models.CharField(max_length=10, default="g", verbose_name="표준단위")

    price = models.DecimalField(
        max_digits=14, decimal_places=4, verbose_name="표준단위당 가격(KRW)"
    )

    source = models.CharField(max_length=20, default="kamis", verbose_name="출처")
    # 원본 보존: 원본 응답 객체키 또는 소스 식별자
    raw_ref = models.CharField(max_length=255, blank=True, verbose_name="원본 참조")

    # 시간 구분 (누수 방지/point-in-time)
    collected_at = models.DateTimeField(verbose_name="수집 시각")
    first_collected_at = models.DateTimeField(
        null=True, blank=True, verbose_name="최초 수집 시각"
    )

    quality_flag = models.CharField(
        max_length=20, choices=QUALITY_CHOICES, default="ok"
    )
    ingestion_run = models.ForeignKey(
        IngestionRun, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="observations",
    )

    class Meta:
        verbose_name = "시장 가격 관측"
        verbose_name_plural = "시장 가격 관측"
        ordering = ["item", "-observation_date"]
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "source", "item", "observation_date",
                    "region", "market_type", "grade", "unit",
                ],
                name="uq_market_price_natural_key",
            )
        ]
        indexes = [
            models.Index(fields=["item", "observation_date"]),
            models.Index(fields=["observation_date"]),
        ]

    def __str__(self):
        return f"{self.item.name} {self.observation_date} {self.price}원/{self.unit}"


class WholesaleAuctionObservation(models.Model):
    """전국 공영도매시장 경락 관측 (가격 + 거래량). 수급 선행변수.

    가격만 보는 KAMIS와 달리 거래량/반입량을 함께 보존해, 기상 충격이
    가격에 반영되기 전 출하·거래량 변화로 먼저 드러나는 신호를 학습에 쓴다.
    """

    item = models.ForeignKey(
        MarketItem, on_delete=models.CASCADE, related_name="auction_observations"
    )
    observation_date = models.DateField(verbose_name="경락일(valid_at)")
    market = models.CharField(max_length=40, verbose_name="도매시장")
    origin = models.CharField(max_length=40, blank=True, verbose_name="산지")
    grade = models.CharField(max_length=20, blank=True, verbose_name="등급")
    unit = models.CharField(max_length=10, default="g", verbose_name="표준단위")

    price = models.DecimalField(
        max_digits=14, decimal_places=4, verbose_name="표준단위당 낙찰가(KRW)"
    )
    volume = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True,
        verbose_name="거래량(표준단위)",
    )

    source = models.CharField(max_length=20, default="wholesale")
    raw_ref = models.CharField(max_length=255, blank=True)
    collected_at = models.DateTimeField(verbose_name="수집 시각")
    first_collected_at = models.DateTimeField(null=True, blank=True)
    quality_flag = models.CharField(
        max_length=20,
        choices=MarketPriceObservation.QUALITY_CHOICES,
        default="ok",
    )
    ingestion_run = models.ForeignKey(
        IngestionRun, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="auction_observations",
    )

    class Meta:
        verbose_name = "도매 경락 관측"
        verbose_name_plural = "도매 경락 관측"
        ordering = ["item", "-observation_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "item", "observation_date", "market", "origin", "grade", "unit"],
                name="uq_wholesale_natural_key",
            )
        ]
        indexes = [
            models.Index(fields=["item", "observation_date"]),
            models.Index(fields=["market", "observation_date"]),
        ]

    def __str__(self):
        return f"{self.item.name} {self.observation_date} {self.market} {self.price}원"


class ProductionRegion(models.Model):
    """주산지/행정 지역 앵커. 품목 주산지 비중과 기상 관측소 매핑을 연결한다."""

    code = models.CharField(max_length=20, unique=True, help_text="행정코드 또는 표준 지역코드")
    name = models.CharField(max_length=50, verbose_name="지역명")

    class Meta:
        verbose_name = "생산 지역"
        verbose_name_plural = "생산 지역"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class CropProductionRegion(models.Model):
    """품목별 주산지 비중. 같은 강수·기온이라도 주산지별 가중으로 노출을 집계한다."""

    item = models.ForeignKey(
        MarketItem, on_delete=models.CASCADE, related_name="production_regions"
    )
    region = models.ForeignKey(
        ProductionRegion, on_delete=models.CASCADE, related_name="crop_shares"
    )
    weight = models.FloatField(default=0.0, verbose_name="주산지 비중(0~1)")
    valid_from = models.DateField(null=True, blank=True, verbose_name="적용 시작일")

    class Meta:
        verbose_name = "품목 주산지 비중"
        verbose_name_plural = "품목 주산지 비중"
        unique_together = [("item", "region", "valid_from")]
        ordering = ["item", "-weight"]

    def __str__(self):
        return f"{self.item.name} ← {self.region.name} {self.weight:.0%}"


class CropGrowthStage(models.Model):
    """품목·지역별 생육단계. 같은 기상도 생육단계에 따라 영향이 다르다."""

    item = models.ForeignKey(
        MarketItem, on_delete=models.CASCADE, related_name="growth_stages"
    )
    region = models.ForeignKey(
        ProductionRegion, on_delete=models.CASCADE, null=True, blank=True,
        related_name="growth_stages",
    )
    stage = models.CharField(max_length=30, verbose_name="생육단계")
    start_day = models.PositiveSmallIntegerField(verbose_name="시작 일자(1~366)")
    end_day = models.PositiveSmallIntegerField(verbose_name="종료 일자(1~366)")

    class Meta:
        verbose_name = "생육단계"
        verbose_name_plural = "생육단계"
        ordering = ["item", "start_day"]

    def __str__(self):
        return f"{self.item.name} {self.stage} ({self.start_day}~{self.end_day})"
