"""기상 데이터 모델 (담당 B, 항목 5).

설계 원칙:
- 누수 방지의 핵심: 예보는 issued_at(발행시각)과 valid_at(예측 대상시각)을 반드시 분리한다.
  학습/평가 시 "그 예측 시점에 실제로 발행돼 있던 예보"만 사용해야 하므로
  issued_at 을 보존하지 않으면 미래 정보가 새어든다.
- 관측(ASOS/농업기상)은 observed_date(valid_at)과 collected_at(수집시각)을 분리한다.
- variables 는 JSON으로 유연하게 저장하되, 자주 쓰는 키는 문서화한다.
- 모든 적재는 market.IngestionRun 에 연결해 재현성과 실패추적을 공유한다.
"""
from django.db import models

from market.models import IngestionRun, ProductionRegion


class WeatherStation(models.Model):
    """기상 관측소 (ASOS / 농업기상)."""

    SOURCE_CHOICES = [
        ("asos", "기상청 ASOS"),
        ("aws_agri", "농촌진흥청 농업기상"),
    ]

    station_id = models.CharField(max_length=20, unique=True, verbose_name="지점번호")
    name = models.CharField(max_length=50, verbose_name="지점명")
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, default="asos")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "기상 관측소"
        verbose_name_plural = "기상 관측소"
        ordering = ["station_id"]

    def __str__(self):
        return f"{self.name} ({self.station_id})"


class WeatherStationMapping(models.Model):
    """주산지 ↔ 관측소 가중 매핑. 한 지역에 여러 관측소를 거리 가중으로 묶는다."""

    region = models.ForeignKey(
        ProductionRegion, on_delete=models.CASCADE, related_name="station_mappings"
    )
    station = models.ForeignKey(
        WeatherStation, on_delete=models.CASCADE, related_name="region_mappings"
    )
    weight = models.FloatField(default=1.0, verbose_name="가중치")
    distance_km = models.FloatField(null=True, blank=True, verbose_name="거리(km)")

    class Meta:
        verbose_name = "지역-관측소 매핑"
        verbose_name_plural = "지역-관측소 매핑"
        unique_together = [("region", "station")]
        ordering = ["region", "-weight"]

    def __str__(self):
        return f"{self.region.name} ← {self.station.name} (w={self.weight})"


class WeatherObservation(models.Model):
    """일별 기상 관측. variables 예: tavg/tmin/tmax/rain/humidity/sunshine/soil_moisture."""

    station = models.ForeignKey(
        WeatherStation, on_delete=models.CASCADE, related_name="observations"
    )
    observed_date = models.DateField(verbose_name="관측일(valid_at)")
    variables = models.JSONField(default=dict, verbose_name="기상 변수")
    quality_flag = models.CharField(max_length=20, default="ok")

    source = models.CharField(max_length=20, default="asos")
    raw_ref = models.CharField(max_length=255, blank=True)
    collected_at = models.DateTimeField(verbose_name="수집 시각")
    first_collected_at = models.DateTimeField(null=True, blank=True)
    ingestion_run = models.ForeignKey(
        IngestionRun, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="weather_observations",
    )

    class Meta:
        verbose_name = "기상 관측"
        verbose_name_plural = "기상 관측"
        ordering = ["station", "-observed_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "station", "observed_date"],
                name="uq_weather_obs_natural_key",
            )
        ]
        indexes = [
            models.Index(fields=["station", "observed_date"]),
            models.Index(fields=["observed_date"]),
        ]

    def __str__(self):
        return f"{self.station.name} {self.observed_date}"


class WeatherForecastSnapshot(models.Model):
    """기상 예보 스냅샷. issued_at != valid_at 분리가 누수 방지의 핵심.

    같은 valid_at(예측 대상일)이라도 발행시각(issued_at)이 다른 여러 예보가 존재한다.
    학습/평가 시 예측 기준시점(as_of) 이전에 발행된 스냅샷만 사용한다.
    """

    PROVIDER_CHOICES = [
        ("kma_short", "기상청 단기예보(1~3일)"),
        ("kma_mid", "기상청 중기예보(4~11일)"),
        ("kma_month", "기상청 1개월 전망(12~30일)"),
    ]

    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    issued_at = models.DateTimeField(verbose_name="발행시각(issued_at)")
    valid_at = models.DateField(verbose_name="예측 대상일(valid_at)")

    # 지역 또는 관측소 단위 예보 (둘 중 하나 이상)
    region = models.ForeignKey(
        ProductionRegion, on_delete=models.CASCADE, null=True, blank=True,
        related_name="forecast_snapshots",
    )
    station = models.ForeignKey(
        WeatherStation, on_delete=models.CASCADE, null=True, blank=True,
        related_name="forecast_snapshots",
    )
    variables = models.JSONField(default=dict, verbose_name="예보 변수")

    source = models.CharField(max_length=20, default="kma")
    raw_ref = models.CharField(max_length=255, blank=True)
    collected_at = models.DateTimeField(verbose_name="수집 시각")
    ingestion_run = models.ForeignKey(
        IngestionRun, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="forecast_snapshots",
    )

    class Meta:
        verbose_name = "기상 예보 스냅샷"
        verbose_name_plural = "기상 예보 스냅샷"
        ordering = ["-issued_at", "valid_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "issued_at", "valid_at", "region", "station"],
                name="uq_forecast_snapshot_natural_key",
            )
        ]
        indexes = [
            models.Index(fields=["provider", "valid_at"]),
            models.Index(fields=["issued_at"]),
        ]

    def __str__(self):
        return f"{self.provider} issued={self.issued_at:%Y-%m-%d %H:%M} valid={self.valid_at}"
