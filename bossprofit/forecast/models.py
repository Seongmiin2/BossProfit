"""예측 영속화 모델 (항목 11~13).

OutOfFoldForecast / ResidualObservation:
- 잔차 보정(Stage 3)의 학습 라벨은 반드시 OOF(out-of-fold) 예측에서만 생성한다.
  in-sample 예측에 잔차를 맞추면 미래 정보가 새어들기 때문이다.
- 각 OOF 예측은 origin_date(예측 기준시점)까지의 과거만으로 만들어졌음을 origin_date로 보존한다.
- 재현성·누수검사를 위해 예측·실제·잔차를 모두 남긴다.
"""
from django.db import models

from market.models import MarketItem


class ModelRegistry(models.Model):
    """모델 버전 카탈로그. 재현성: 학습 구간·데이터 snapshot·성능을 보존한다."""

    STAGE_CHOICES = [
        ("base", "Base Price"),
        ("weather", "Weather & Supply"),
        ("residual", "Residual Correction"),
        ("calibration", "Interval Calibration"),
        ("ensemble", "Ensemble"),
    ]

    model_version = models.CharField(max_length=64, unique=True)
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES)
    algorithm = models.CharField(max_length=50, blank=True)
    trained_from = models.DateField(null=True, blank=True)
    trained_to = models.DateField(null=True, blank=True)
    train_snapshot_ref = models.CharField(
        max_length=128, blank=True, help_text="학습 데이터 snapshot 식별자(재현성)"
    )
    code_version = models.CharField(max_length=64, blank=True)
    metrics = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "모델 레지스트리"
        verbose_name_plural = "모델 레지스트리"
        ordering = ["stage", "-created_at"]

    def __str__(self):
        return f"{self.model_version} ({self.stage})"


class ForecastRun(models.Model):
    """예측 생성 1회. as_of 시점에 어떤 모델 조합으로 만들었는지 기록한다."""

    STATUS_CHOICES = [
        ("success", "성공"), ("failed", "실패"), ("stale", "stale"),
    ]

    item = models.ForeignKey(
        MarketItem, on_delete=models.CASCADE, related_name="forecast_runs"
    )
    target_type = models.CharField(max_length=20, default="market_price")
    as_of = models.DateField(verbose_name="예측 기준일")
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="success")
    model_versions = models.JSONField(
        default=dict, blank=True, help_text="{base, weather, residual, calibration}"
    )
    data_quality = models.JSONField(default=list, blank=True)
    weather_forecast_issued_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "예측 실행"
        verbose_name_plural = "예측 실행"
        ordering = ["-as_of", "-created_at"]
        indexes = [models.Index(fields=["item", "as_of"])]

    def __str__(self):
        return f"{self.item.code} @ {self.as_of}"


class ForecastPoint(models.Model):
    """horizon별 최종 예측 점·구간·신뢰등급."""

    CONFIDENCE_CHOICES = [("HIGH", "높음"), ("MEDIUM", "보통"), ("LOW", "낮음")]

    run = models.ForeignKey(
        ForecastRun, on_delete=models.CASCADE, related_name="points"
    )
    horizon = models.PositiveSmallIntegerField()
    target_date = models.DateField()
    median = models.DecimalField(max_digits=14, decimal_places=4)
    lower_80 = models.DecimalField(max_digits=14, decimal_places=4)
    upper_80 = models.DecimalField(max_digits=14, decimal_places=4)
    lower_95 = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    upper_95 = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    confidence = models.CharField(max_length=8, choices=CONFIDENCE_CHOICES, default="MEDIUM")

    class Meta:
        verbose_name = "예측 점"
        verbose_name_plural = "예측 점"
        ordering = ["run", "horizon"]
        constraints = [
            models.UniqueConstraint(fields=["run", "horizon"], name="uq_forecast_point")
        ]

    def __str__(self):
        return f"{self.run.item.code} h{self.horizon} {self.median}"


class ForecastComponent(models.Model):
    """단계별 보정량 분해: base + weather_delta + residual_delta (백엔드 계약)."""

    point = models.OneToOneField(
        ForecastPoint, on_delete=models.CASCADE, related_name="component"
    )
    base = models.DecimalField(max_digits=14, decimal_places=4)
    weather_delta = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    residual_delta = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    weather_disabled = models.BooleanField(default=False)
    residual_disabled = models.BooleanField(default=False)

    class Meta:
        verbose_name = "예측 보정량 분해"
        verbose_name_plural = "예측 보정량 분해"

    def __str__(self):
        return f"{self.point} base={self.base} w={self.weather_delta} r={self.residual_delta}"


class OutOfFoldForecast(models.Model):
    """rolling-origin으로 생성된 단일 OOF 예측 1건 (잔차 학습 전용)."""

    item = models.ForeignKey(
        MarketItem, on_delete=models.CASCADE, related_name="oof_forecasts"
    )
    model_version = models.CharField(
        max_length=64, verbose_name="기반 모델 버전",
        help_text="이 OOF 예측을 만든 Stage1/2 모델 식별자",
    )
    horizon = models.PositiveSmallIntegerField()
    origin_date = models.DateField(
        verbose_name="예측 기준시점(as_of)",
        help_text="이 시점까지의 과거만으로 예측했다",
    )
    target_date = models.DateField(verbose_name="예측 대상일")
    prediction = models.FloatField(verbose_name="OOF 예측값")
    actual = models.FloatField(null=True, blank=True, verbose_name="실제값")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "OOF 예측"
        verbose_name_plural = "OOF 예측"
        ordering = ["item", "model_version", "horizon", "origin_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["item", "model_version", "horizon", "origin_date", "target_date"],
                name="uq_oof_natural_key",
            )
        ]
        indexes = [
            models.Index(fields=["item", "model_version", "horizon", "target_date"]),
        ]

    def __str__(self):
        return f"{self.item.code} h{self.horizon} {self.origin_date}->{self.target_date}"


class ResidualObservation(models.Model):
    """OOF 예측에서만 생성되는 잔차 라벨. residual = log(actual) - log(prediction)."""

    RESIDUAL_TYPES = [("log", "로그 잔차"), ("raw", "원시 잔차")]

    oof = models.OneToOneField(
        OutOfFoldForecast, on_delete=models.CASCADE, related_name="residual"
    )
    residual = models.FloatField(verbose_name="잔차값")
    residual_type = models.CharField(max_length=10, choices=RESIDUAL_TYPES, default="log")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "잔차 관측"
        verbose_name_plural = "잔차 관측"
        ordering = ["oof"]

    def __str__(self):
        return f"{self.oof} resid={self.residual:+.4f}"
