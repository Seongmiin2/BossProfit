import math
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.utils import timezone

from profit.forecasting.lightgbm_model import TrainedLightGBMArtifact
from profit.models import (
    ForecastCalibration,
    ForecastComponent,
    ForecastModelComparison,
    ForecastPoint,
    ForecastRun,
    MarketForecast,
    MarketItem,
    ResidualObservation,
    WeatherExposureFeature,
)


MONEY = Decimal("0.01")

# 백테스트 근거: LightGBM은 장기(>=14일) horizon에서 통계 모델을 이기고, 단기는
# LastValue/통계 모델이 더 낫다. 따라서 이 임계값 이상에서만 LightGBM을 쓴다.
LIGHTGBM_MIN_HORIZON = 14
LIGHTGBM_VERSION = "lightgbm-global-quantile-v1"


def money(value):
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class StagePrediction:
    value: Decimal
    details: dict


class BasePriceModel:
    """Deterministic damped log-trend model using point-in-time price history only."""

    minimum_observations = 30

    def predict(self, observations, horizon_days):
        if len(observations) < self.minimum_observations:
            raise ValueError(
                f"최소 {self.minimum_observations}일의 가격 관측이 필요합니다."
            )
        recent = observations[-min(90, len(observations)) :]
        values = [max(float(row.price), 0.01) for row in recent]
        logs = [math.log(value) for value in values]
        xs = list(range(len(logs)))
        x_mean = sum(xs) / len(xs)
        y_mean = sum(logs) / len(logs)
        denominator = sum((x - x_mean) ** 2 for x in xs)
        slope = (
            sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, logs))
            / denominator
            if denominator
            else 0
        )
        daily_slope_cap = math.log(1.03)
        slope = max(-daily_slope_cap, min(daily_slope_cap, slope))
        damping = 1 - math.exp(-horizon_days / 30)
        effective_horizon = horizon_days * (1 - 0.65 * damping)
        trend_prediction = math.exp(logs[-1] + slope * effective_horizon)

        weekday_values = [
            float(row.price)
            for row in recent
            if row.observed_date.weekday()
            == (recent[-1].observed_date + timedelta(days=horizon_days)).weekday()
        ]
        seasonal_anchor = (
            sum(weekday_values[-8:]) / len(weekday_values[-8:])
            if weekday_values
            else values[-1]
        )
        prediction = 0.75 * trend_prediction + 0.25 * seasonal_anchor
        return StagePrediction(
            value=money(max(prediction, 0)),
            details={
                "model": "damped-log-trend-v1",
                "observation_count": len(recent),
                "last_observed_date": recent[-1].observed_date.isoformat(),
                "daily_log_slope": round(slope, 8),
                "effective_horizon": round(effective_horizon, 3),
            },
        )


class WeatherSupplyImpactModel:
    """Consumes versioned exposure output; returns zero until a trained adjustment exists."""

    def predict(self, item, as_of_date, base_prediction, horizon_days):
        exposure = (
            WeatherExposureFeature.objects.filter(
                item=item,
                as_of_date__lte=as_of_date,
            )
            .order_by("-as_of_date", "-id")
            .first()
        )
        if exposure is None:
            return StagePrediction(
                value=Decimal("0"),
                details={"enabled": False, "reason": "NO_WEATHER_EXPOSURE"},
            )
        rate_key = f"learned_adjustment_rate_h{horizon_days}"
        rate = exposure.anomalies.get(rate_key)
        if rate is None:
            return StagePrediction(
                value=Decimal("0"),
                details={
                    "enabled": False,
                    "reason": "NO_TRAINED_WEATHER_ADJUSTMENT",
                    "feature_version": exposure.feature_version,
                },
            )
        adjustment = money(base_prediction * Decimal(str(rate)))
        return StagePrediction(
            value=adjustment,
            details={
                "enabled": True,
                "feature_version": exposure.feature_version,
                "rate": str(rate),
                "production_region_id": exposure.production_region_id,
            },
        )


class ResidualCorrectionModel:
    """Uses rolling-origin out-of-fold residuals only."""

    def predict(self, item, horizon_days):
        residuals = list(
            ResidualObservation.objects.filter(
                oof_forecast__item=item,
                oof_forecast__horizon_days=horizon_days,
            )
            .order_by("-oof_forecast__target_date")
            .values_list("residual", flat=True)[:60]
        )
        if len(residuals) < 8:
            return StagePrediction(
                value=Decimal("0"),
                details={"enabled": False, "reason": "INSUFFICIENT_OOF_RESIDUALS"},
            )
        raw_mean = sum(residuals, Decimal("0")) / Decimal(len(residuals))
        shrinkage = Decimal(len(residuals)) / Decimal(len(residuals) + 20)
        correction = money(raw_mean * shrinkage)
        return StagePrediction(
            value=correction,
            details={
                "enabled": True,
                "oof_residual_count": len(residuals),
                "shrinkage": str(shrinkage.quantize(Decimal("0.0001"))),
            },
        )


class IntervalCalibration:
    def interval(self, item, model_version, horizon_days, prediction):
        calibration = ForecastCalibration.objects.filter(
            item=item,
            model_version=model_version,
            horizon_days=horizon_days,
        ).first()
        if calibration:
            width = calibration.absolute_error_quantile
            details = {
                "calibrated": True,
                "target_coverage": str(calibration.target_coverage),
                "measured_coverage": (
                    str(calibration.measured_coverage)
                    if calibration.measured_coverage is not None
                    else None
                ),
            }
        else:
            width = money(
                prediction
                * Decimal("0.08")
                * Decimal(str(max(1, math.sqrt(horizon_days / 7))))
            )
            details = {
                "calibrated": False,
                "reason": "NO_OOF_CALIBRATION",
            }
        return (
            money(max(Decimal("0"), prediction - width)),
            money(prediction + width),
            details,
        )


class ForecastEngine:
    model_version = "bossprofit-statistical-v1"
    feature_version = "market-weather-supply-v1"

    def __init__(self, use_lightgbm=True):
        self.base_model = BasePriceModel()
        self.weather_model = WeatherSupplyImpactModel()
        self.residual_model = ResidualCorrectionModel()
        self.calibration = IntervalCalibration()
        self.use_lightgbm = use_lightgbm
        self._lightgbm_loaded = False
        self._lightgbm = None

    def _lightgbm_artifact(self):
        if not self.use_lightgbm:
            return None
        if not self._lightgbm_loaded:
            self._lightgbm = TrainedLightGBMArtifact.load()
            self._lightgbm_loaded = True
        return self._lightgbm

    def _lightgbm_prediction(self, item, observations, as_of_date, horizon):
        """장기 horizon에 한해 학습된 글로벌 LightGBM 예측을 반환(없으면 None)."""
        if horizon < LIGHTGBM_MIN_HORIZON:
            return None
        artifact = self._lightgbm_artifact()
        if artifact is None:
            return None
        rows = [(o.observed_date, o.price) for o in observations]
        try:
            return artifact.predict_interval(
                rows, item.code, item.category, as_of_date, horizon
            )
        except Exception:
            return None

    def run(self, item: MarketItem, as_of_date, horizons=(1, 7, 30, 60, 90)):
        observation_query = item.observations.filter(
            observed_date__lte=as_of_date,
            is_demo=False,
        )
        period_query = observation_query.filter(
            source="KAMIS_PERIOD",
            region_code="AVERAGE",
        )
        if period_query.exists():
            observation_query = period_query
        observations = list(observation_query.order_by("observed_date", "id"))
        if not observations:
            raise ValueError("실제 시장 가격 관측이 없습니다.")
        run, _ = ForecastRun.objects.update_or_create(
            item=item,
            as_of_date=as_of_date,
            model_version=self.model_version,
            defaults={
                "feature_version": self.feature_version,
                "observation_cutoff": timezone.now(),
                "random_seed": 0,
                "status": "RUNNING",
                "error_message": "",
            },
        )
        run.points.all().delete()
        last_price = observations[-1].price
        published = []
        try:
            for horizon in horizons:
                lgbm = self._lightgbm_prediction(
                    item, observations, as_of_date, horizon
                )
                if lgbm is not None:
                    # 장기 horizon: 학습된 글로벌 LightGBM 분위 모델을 사용.
                    final_prediction = money(lgbm["median"])
                    lower = money(max(Decimal("0"), Decimal(str(lgbm["lower"]))))
                    upper = money(lgbm["upper"])
                    base = StagePrediction(
                        value=final_prediction,
                        details={
                            "model": LIGHTGBM_VERSION,
                            "selected_model": LIGHTGBM_VERSION,
                            "origin_date": lgbm["origin_date"].isoformat(),
                        },
                    )
                    weather = StagePrediction(
                        value=Decimal("0"),
                        details={"enabled": False, "reason": "LIGHTGBM_PATH"},
                    )
                    residual = StagePrediction(
                        value=Decimal("0"),
                        details={"enabled": False, "reason": "LIGHTGBM_PATH"},
                    )
                    calibration_details = {
                        "calibrated": lgbm["coverage"] is not None,
                        "method": "CONFORMAL_QUANTILE_SCALE",
                        "model": LIGHTGBM_VERSION,
                        "measured_coverage": (
                            str(lgbm["coverage"])
                            if lgbm["coverage"] is not None
                            else None
                        ),
                    }
                else:
                    try:
                        base = self.base_model.predict(observations, horizon)
                        statistical_ok = True
                    except ValueError as exc:
                        # 관측이 통계모델 최소치 미만 — last-value로 폴백(품목 전체
                        # 실패 대신 정직한 베이스라인 예측을 제공).
                        base = StagePrediction(
                            value=money(observations[-1].price),
                            details={
                                "model": "baseline-last-value-v1",
                                "insufficient_history": str(exc),
                            },
                        )
                        statistical_ok = False
                    comparison = (
                        ForecastModelComparison.objects.filter(
                            item=item,
                            horizon_days=horizon,
                            candidate_version=self.model_version,
                            baseline_version="baseline-last-value-v1",
                            metric="MAE",
                            is_significant=True,
                            difference__gt=0,
                        ).first()
                        if statistical_ok
                        else None
                    )
                    if not statistical_ok:
                        base = StagePrediction(
                            value=base.value,
                            details={
                                **base.details,
                                "selected_model": "baseline-last-value-v1",
                                "fallback_reason": "INSUFFICIENT_HISTORY",
                            },
                        )
                    elif comparison:
                        base = StagePrediction(
                            value=money(observations[-1].price),
                            details={
                                **base.details,
                                "selected_model": "baseline-last-value-v1",
                                "fallback_reason": "CANDIDATE_SIGNIFICANTLY_WORSE",
                                "paired_bootstrap_ci": [
                                    str(comparison.ci_lower),
                                    str(comparison.ci_upper),
                                ],
                            },
                        )
                    else:
                        base = StagePrediction(
                            value=base.value,
                            details={
                                **base.details,
                                "selected_model": self.model_version,
                            },
                        )
                    weather = self.weather_model.predict(
                        item,
                        as_of_date,
                        base.value,
                        horizon,
                    )
                    residual = self.residual_model.predict(item, horizon)
                    final_prediction = money(
                        base.value + weather.value + residual.value
                    )
                    lower, upper, calibration_details = self.calibration.interval(
                        item,
                        self.model_version,
                        horizon,
                        final_prediction,
                    )
                point = ForecastPoint.objects.create(
                    run=run,
                    target_date=as_of_date + timedelta(days=horizon),
                    horizon_days=horizon,
                    median=final_prediction,
                    lower=lower,
                    upper=upper,
                )
                ForecastComponent.objects.create(
                    point=point,
                    base_prediction=base.value,
                    weather_adjustment=weather.value,
                    residual_adjustment=residual.value,
                    details={
                        "base": base.details,
                        "weather_supply": weather.details,
                        "residual": residual.details,
                        "interval": calibration_details,
                    },
                )
                change_rate = (
                    (final_prediction - last_price) / last_price
                    if last_price
                    else Decimal("0")
                )
                forecast, _ = MarketForecast.objects.update_or_create(
                    item=item,
                    as_of_date=as_of_date,
                    horizon_days=horizon,
                    model_version=self.model_version,
                    defaults={
                        "run": run,
                        "target_date": point.target_date,
                        "predicted_price": final_prediction,
                        "lower_price": lower,
                        "upper_price": upper,
                        "expected_change_rate": change_rate,
                        "confidence_grade": self._confidence_grade(
                            calibration_details
                        ),
                        "is_demo": False,
                    },
                )
                published.append(forecast)
            run.status = "SUCCEEDED"
        except Exception as exc:
            run.status = "FAILED"
            run.error_message = str(exc)
            run.finished_at = timezone.now()
            run.save(
                update_fields=["status", "error_message", "finished_at"]
            )
            raise
        run.finished_at = timezone.now()
        run.save(update_fields=["status", "finished_at"])
        return published

    @staticmethod
    def _confidence_grade(calibration_details):
        if not calibration_details.get("calibrated"):
            return "검증 필요"
        measured = calibration_details.get("measured_coverage")
        if measured is None:
            return "검증 필요"
        coverage = Decimal(str(measured))
        if Decimal("0.70") <= coverage <= Decimal("0.90"):
            return "검증됨"
        return "구간 재보정 필요"
