import random
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from profit.forecasting.engine import BasePriceModel, money
from profit.forecasting.evaluation import (
    conformal_error_quantile,
    metric_bundle,
    seasonal_naive,
)
from profit.models import (
    ForecastCalibration,
    ForecastModelComparison,
    MarketItem,
    MarketModelMetric,
    OutOfFoldForecast,
    ResidualObservation,
)


LAST_VALUE_VERSION = "baseline-last-value-v1"
SEASONAL_NAIVE_VERSION = "baseline-seasonal-naive-v1"


def seasonal_naive_prediction(eligible, horizon):
    return seasonal_naive(
        [row.price for row in eligible],
        horizon=horizon,
        season_length=7,
    )


def paired_bootstrap_ci(candidate_errors, baseline_errors, seed=42, samples=500):
    differences = [
        float(candidate - baseline)
        for candidate, baseline in zip(candidate_errors, baseline_errors)
    ]
    if not differences:
        return Decimal("0"), Decimal("0")
    rng = random.Random(seed)
    means = []
    for _ in range(samples):
        draw = [rng.choice(differences) for _ in differences]
        means.append(sum(draw) / len(draw))
    means.sort()
    lower = means[int((samples - 1) * 0.025)]
    upper = means[int((samples - 1) * 0.975)]
    return money(lower), money(upper)


def metric_values(samples, prediction_key, scale, interval_width=None):
    actual = [row["actual"] for row in samples]
    predicted = [row[prediction_key] for row in samples]
    metrics = metric_bundle(actual, predicted, scale=scale)
    errors = [
        abs(row["actual"] - row[prediction_key])
        for row in samples
    ]
    return {
        "wape": metrics["wape"],
        "mase": metrics["mase"],
        "mae": money(metrics["mae"]),
        "rmse": money(metrics["rmse"]),
        "bias": money(metrics["bias"]),
        "pinball_loss": money(metrics["pinball_loss"]),
        "interval_width": interval_width,
        "errors": errors,
    }


def save_metric(
    *,
    item,
    model_version,
    horizon,
    samples,
    prediction_key,
    scale,
    is_verified,
    coverage=None,
    interval_width=None,
):
    values = metric_values(samples, prediction_key, scale, interval_width)
    directions = [
        int(
            (row[prediction_key] - row["previous"])
            * (row["actual"] - row["previous"])
            >= 0
        )
        for row in samples
    ]
    metric, _ = MarketModelMetric.objects.update_or_create(
        item=item,
        model_version=model_version,
        horizon_days=horizon,
        defaults={
            "direction_accuracy": (
                Decimal(sum(directions)) / Decimal(len(directions))
            ),
            "wape": values["wape"],
            "mase": values["mase"],
            "mae": values["mae"],
            "rmse": values["rmse"],
            "bias": values["bias"],
            "pinball_loss": values["pinball_loss"],
            "interval_coverage": coverage,
            "interval_width": interval_width,
            "sample_count": len(samples),
            "evaluation_method": "ROLLING_ORIGIN_40PCT_HOLDOUT",
            "evaluation_start": samples[0]["target_date"],
            "evaluation_end": samples[-1]["target_date"],
            "is_verified": is_verified,
        },
    )
    return metric, values


class Command(BaseCommand):
    help = "시간 순서를 보존한 rolling-origin OOF 예측·기준선·보정값을 생성합니다."

    def add_arguments(self, parser):
        parser.add_argument("--item-code")
        parser.add_argument("--horizons", default="1,7,30")
        parser.add_argument("--model-version", default="bossprofit-statistical-v1")

    @transaction.atomic
    def handle(self, *args, **options):
        horizons = tuple(
            sorted(
                {
                    int(value.strip())
                    for value in options["horizons"].split(",")
                    if value.strip()
                }
            )
        )
        items = MarketItem.objects.filter(is_active=True)
        if options["item_code"]:
            items = items.filter(code=options["item_code"])
        if not items.exists():
            raise CommandError("백테스트할 품목이 없습니다.")

        base_model = BasePriceModel()
        total = 0
        for item in items:
            observation_query = item.observations.filter(is_demo=False)
            period_query = observation_query.filter(
                source="KAMIS_PERIOD",
                region_code="AVERAGE",
            )
            if period_query.exists():
                observation_query = period_query
            observations = list(observation_query.order_by("observed_date", "id"))
            item_count = 0
            for horizon in horizons:
                samples = []
                for target_index in range(
                    base_model.minimum_observations + horizon,
                    len(observations),
                ):
                    target = observations[target_index]
                    eligible = [
                        row
                        for row in observations[:target_index]
                        if row.observed_date
                        <= target.observed_date - timedelta(days=horizon)
                    ]
                    if len(eligible) < base_model.minimum_observations:
                        continue
                    prediction = base_model.predict(eligible, horizon).value
                    actual = target.price
                    oof, _ = OutOfFoldForecast.objects.update_or_create(
                        item=item,
                        fold_id=f"{eligible[-1].observed_date}:{horizon}",
                        target_date=target.observed_date,
                        horizon_days=horizon,
                        model_version=options["model_version"],
                        defaults={
                            "train_cutoff": eligible[-1].observed_date,
                            "prediction": prediction,
                            "actual": actual,
                        },
                    )
                    ResidualObservation.objects.update_or_create(
                        oof_forecast=oof,
                        defaults={"residual": money(actual - prediction)},
                    )
                    samples.append(
                        {
                            "target_date": target.observed_date,
                            "actual": actual,
                            "candidate": prediction,
                            "last_value": eligible[-1].price,
                            "seasonal_naive": seasonal_naive_prediction(
                                eligible,
                                horizon,
                            ),
                            "previous": eligible[-1].price,
                        }
                    )
                    item_count += 1
                if len(samples) < 2:
                    MarketModelMetric.objects.filter(
                        item=item,
                        horizon_days=horizon,
                        model_version__in=[
                            options["model_version"],
                            LAST_VALUE_VERSION,
                            SEASONAL_NAIVE_VERSION,
                        ],
                    ).update(is_verified=False, sample_count=len(samples))
                    ForecastCalibration.objects.filter(
                        item=item,
                        model_version=options["model_version"],
                        horizon_days=horizon,
                    ).delete()
                    continue

                split_index = max(1, int(len(samples) * 0.60))
                calibration_samples = samples[:split_index]
                evaluation_samples = samples[split_index:]
                if not evaluation_samples:
                    continue
                calibration_errors = [
                    abs(row["actual"] - row["candidate"])
                    for row in calibration_samples
                ]
                interval_half_width = conformal_error_quantile(
                    calibration_errors,
                    Decimal("0.8"),
                )
                covered = sum(
                    abs(row["actual"] - row["candidate"]) <= interval_half_width
                    for row in evaluation_samples
                )
                coverage = Decimal(covered) / Decimal(len(evaluation_samples))
                enough_for_verification = len(evaluation_samples) >= 20

                if enough_for_verification:
                    ForecastCalibration.objects.update_or_create(
                        item=item,
                        model_version=options["model_version"],
                        horizon_days=horizon,
                        defaults={
                            "target_coverage": Decimal("0.8000"),
                            "measured_coverage": coverage,
                            "absolute_error_quantile": interval_half_width,
                            "fitted_from": calibration_samples[0]["target_date"],
                            "fitted_to": calibration_samples[-1]["target_date"],
                        },
                    )
                else:
                    ForecastCalibration.objects.filter(
                        item=item,
                        model_version=options["model_version"],
                        horizon_days=horizon,
                    ).delete()

                scale_values = [
                    abs(current.price - previous.price)
                    for previous, current in zip(observations, observations[1:])
                    if current.observed_date < evaluation_samples[0]["target_date"]
                ]
                scale = (
                    sum(scale_values, Decimal("0")) / Decimal(len(scale_values))
                    if scale_values
                    else None
                )
                candidate_metric, candidate_values = save_metric(
                    item=item,
                    model_version=options["model_version"],
                    horizon=horizon,
                    samples=evaluation_samples,
                    prediction_key="candidate",
                    scale=scale,
                    is_verified=enough_for_verification,
                    coverage=coverage,
                    interval_width=interval_half_width * 2,
                )
                for baseline_version, prediction_key in (
                    (LAST_VALUE_VERSION, "last_value"),
                    (SEASONAL_NAIVE_VERSION, "seasonal_naive"),
                ):
                    baseline_metric, baseline_values = save_metric(
                        item=item,
                        model_version=baseline_version,
                        horizon=horizon,
                        samples=evaluation_samples,
                        prediction_key=prediction_key,
                        scale=scale,
                        is_verified=enough_for_verification,
                    )
                    ci_lower, ci_upper = paired_bootstrap_ci(
                        candidate_values["errors"],
                        baseline_values["errors"],
                    )
                    difference = candidate_metric.mae - baseline_metric.mae
                    ForecastModelComparison.objects.update_or_create(
                        item=item,
                        horizon_days=horizon,
                        candidate_version=options["model_version"],
                        baseline_version=baseline_version,
                        metric="MAE",
                        defaults={
                            "candidate_value": candidate_metric.mae,
                            "baseline_value": baseline_metric.mae,
                            "difference": difference,
                            "ci_lower": ci_lower,
                            "ci_upper": ci_upper,
                            "sample_count": len(evaluation_samples),
                            "method": "PAIRED_BOOTSTRAP",
                            "is_significant": (
                                enough_for_verification
                                and (ci_upper < 0 or ci_lower > 0)
                            ),
                            "random_seed": 42,
                            "evaluation_start": evaluation_samples[0]["target_date"],
                            "evaluation_end": evaluation_samples[-1]["target_date"],
                        },
                    )
            total += item_count
            self.stdout.write(f"{item.name}: OOF {item_count}건")
        self.stdout.write(self.style.SUCCESS(f"rolling-origin OOF 총 {total}건 생성"))
