"""Leakage-safe forecast evaluation primitives.

This module selectively incorporates the useful evaluation design from the
remote ``master`` branch without introducing its duplicate market/weather
database apps. All functions are dependency-free and Decimal-safe.
"""

from __future__ import annotations

import math
from decimal import Decimal


def _pairs(actual, predicted):
    pairs = []
    for y_true, y_pred in zip(actual, predicted):
        if y_true is None or y_pred is None:
            continue
        pairs.append((Decimal(str(y_true)), Decimal(str(y_pred))))
    return pairs


def mae(actual, predicted):
    pairs = _pairs(actual, predicted)
    if not pairs:
        return None
    return sum((abs(y_true - y_pred) for y_true, y_pred in pairs), Decimal("0")) / Decimal(
        len(pairs)
    )


def rmse(actual, predicted):
    pairs = _pairs(actual, predicted)
    if not pairs:
        return None
    mean_squared_error = sum(
        (float(y_true - y_pred) ** 2 for y_true, y_pred in pairs),
        0.0,
    ) / len(pairs)
    return Decimal(str(math.sqrt(mean_squared_error)))


def wape(actual, predicted):
    pairs = _pairs(actual, predicted)
    if not pairs:
        return None
    denominator = sum((abs(y_true) for y_true, _ in pairs), Decimal("0"))
    if denominator == 0:
        return None
    numerator = sum((abs(y_true - y_pred) for y_true, y_pred in pairs), Decimal("0"))
    return numerator / denominator


def bias(actual, predicted):
    pairs = _pairs(actual, predicted)
    if not pairs:
        return None
    return sum((y_pred - y_true for y_true, y_pred in pairs), Decimal("0")) / Decimal(
        len(pairs)
    )


def pinball_loss(actual, predicted, quantile=Decimal("0.5")):
    pairs = _pairs(actual, predicted)
    if not pairs:
        return None
    q = Decimal(str(quantile))
    losses = []
    for y_true, y_pred in pairs:
        error = y_true - y_pred
        losses.append(max(q * error, (q - Decimal("1")) * error))
    return sum(losses, Decimal("0")) / Decimal(len(losses))


def naive_scale(training_values, season_length=1):
    values = [Decimal(str(value)) for value in training_values if value is not None]
    if len(values) <= season_length:
        return None
    differences = [
        abs(values[index] - values[index - season_length])
        for index in range(season_length, len(values))
    ]
    scale = sum(differences, Decimal("0")) / Decimal(len(differences))
    return scale if scale > 0 else None


def mase(actual, predicted, scale):
    absolute_error = mae(actual, predicted)
    if absolute_error is None or scale in (None, 0):
        return None
    return absolute_error / Decimal(str(scale))


def empirical_coverage(lower, upper, actual):
    triples = [
        (Decimal(str(lo)), Decimal(str(up)), Decimal(str(y_true)))
        for lo, up, y_true in zip(lower, upper, actual)
        if lo is not None and up is not None and y_true is not None
    ]
    if not triples:
        return None
    covered = sum(lo <= y_true <= up for lo, up, y_true in triples)
    return Decimal(covered) / Decimal(len(triples))


def mean_interval_width(lower, upper):
    widths = [
        Decimal(str(up)) - Decimal(str(lo))
        for lo, up in zip(lower, upper)
        if lo is not None and up is not None
    ]
    if not widths:
        return None
    return sum(widths, Decimal("0")) / Decimal(len(widths))


def conformal_error_quantile(errors, target_coverage=Decimal("0.8")):
    """Finite-sample conformal absolute-error quantile using ``higher``."""

    ordered = sorted(Decimal(str(value)) for value in errors if value is not None)
    if not ordered:
        return Decimal("0")
    coverage = Decimal(str(target_coverage))
    rank = math.ceil((len(ordered) + 1) * float(coverage))
    index = min(len(ordered) - 1, max(0, rank - 1))
    return ordered[index]


def last_value(history):
    return history[-1] if history else None


def seasonal_naive(history, horizon, season_length=7):
    if not history:
        return None
    if len(history) < season_length:
        return history[-1]
    index = -season_length + ((horizon - 1) % season_length)
    return history[index]


def metric_bundle(actual, predicted, scale=None, lower=None, upper=None):
    result = {
        "mae": mae(actual, predicted),
        "rmse": rmse(actual, predicted),
        "wape": wape(actual, predicted),
        "bias": bias(actual, predicted),
        "pinball_loss": pinball_loss(actual, predicted),
        "sample_count": len(_pairs(actual, predicted)),
    }
    result["mase"] = mase(actual, predicted, scale) if scale is not None else None
    if lower is not None and upper is not None:
        result["interval_coverage"] = empirical_coverage(lower, upper, actual)
        result["interval_width"] = mean_interval_width(lower, upper)
    return result
