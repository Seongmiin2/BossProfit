"""Global LightGBM quantile forecaster for market prices.

설계 의도(BOSSPROFIT_MASTER_REPORT의 "LightGBM Quantile **Global** Model")를
실제 코드로 구현한 모듈이다. 품목별로 관측치가 얇기 때문에(중앙값 ~13개) 품목별
모델 대신 **전 품목을 하나로 모은 글로벌 모델**을 학습하고, 품목 코드를 범주형
피처로 넣는다. 타깃은 가격 레벨이 아니라 **h일 로그수익률** ``log(p_{t+h}/p_t)``
이라서 품목 간 가격 스케일 차이에 영향받지 않는다.

분위(0.1 / 0.5 / 0.9) 회귀 3개를 학습해 중앙값 예측과 예측구간을 함께 산출한다.
LightGBM이 없으면 ``LightGBMUnavailable`` 을 던지고, 호출부가 기존 통계 모델로
폴백하도록 한다.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import date, timedelta

try:  # LightGBM은 선택적 의존성 — 없으면 폴백한다.
    import joblib
    import lightgbm as lgb
    import numpy as np

    LIGHTGBM_AVAILABLE = True
except Exception:  # pragma: no cover - 의존성 미설치 환경
    joblib = None
    lgb = None
    np = None
    LIGHTGBM_AVAILABLE = False


ARTIFACT_VERSION = "lightgbm-global-quantile-v1"
DEFAULT_ARTIFACT_PATH = os.path.join(
    os.path.dirname(__file__), "artifacts", "lightgbm_global.pkl"
)


class LightGBMUnavailable(RuntimeError):
    """lightgbm/numpy 미설치 시 발생."""


# 로그수익률 타깃을 만들 때 사용하는 lag/rolling 윈도우.
_LAG_DAYS = (1, 2, 3, 7, 14, 30)
_ROLL_WINDOWS = (7, 14, 30)

FEATURE_NAMES = [
    "log_price",
    "horizon",
    "dow_sin",
    "dow_cos",
    "doy_sin",
    "doy_cos",
    *[f"ret_lag_{lag}" for lag in _LAG_DAYS],
    *[f"roll_mean_ratio_{w}" for w in _ROLL_WINDOWS],
    *[f"roll_std_{w}" for w in _ROLL_WINDOWS],
    "item_code",
    "category",
]
_CATEGORICAL = ["item_code", "category"]


@dataclass
class Sample:
    item_id: int
    item_code: str
    category: str
    origin_date: date
    target_date: date
    horizon: int
    price_t: float
    actual: float  # p_{t+h}
    features: dict
    target: float  # log(actual / price_t)


def _series_features(prices_by_date, dates, idx):
    """관측 인덱스 ``idx`` 시점(origin)의 누설 없는 피처를 만든다."""
    origin = dates[idx]
    price_t = prices_by_date[origin]
    if price_t <= 0:
        return None
    feats = {"log_price": math.log(price_t)}

    # 달력 피처
    dow = origin.weekday()
    feats["dow_sin"] = math.sin(2 * math.pi * dow / 7)
    feats["dow_cos"] = math.cos(2 * math.pi * dow / 7)
    doy = origin.timetuple().tm_yday
    feats["doy_sin"] = math.sin(2 * math.pi * doy / 365)
    feats["doy_cos"] = math.cos(2 * math.pi * doy / 365)

    # lag 로그수익률 (없으면 NaN — LightGBM이 자체 처리)
    for lag in _LAG_DAYS:
        prev = origin - timedelta(days=lag)
        prev_price = prices_by_date.get(prev)
        if prev_price and prev_price > 0:
            feats[f"ret_lag_{lag}"] = math.log(price_t / prev_price)
        else:
            feats[f"ret_lag_{lag}"] = float("nan")

    # rolling 통계 (origin 이전 window일 가격, origin 포함)
    for w in _ROLL_WINDOWS:
        window_prices = [
            prices_by_date[origin - timedelta(days=d)]
            for d in range(0, w)
            if (origin - timedelta(days=d)) in prices_by_date
            and prices_by_date[origin - timedelta(days=d)] > 0
        ]
        if len(window_prices) >= 2:
            mean = sum(window_prices) / len(window_prices)
            var = sum((p - mean) ** 2 for p in window_prices) / len(window_prices)
            feats[f"roll_mean_ratio_{w}"] = price_t / mean if mean else float("nan")
            feats[f"roll_std_{w}"] = math.sqrt(var) / mean if mean else float("nan")
        else:
            feats[f"roll_mean_ratio_{w}"] = float("nan")
            feats[f"roll_std_{w}"] = float("nan")
    return feats


def build_samples(series, horizons):
    """품목 시계열들로부터 (피처, h일 로그수익률 타깃) 샘플을 만든다.

    ``series``: ``[{"item_id","item_code","category","rows":[(date, price)...]}...]``
    반환: ``list[Sample]`` (origin/target_date 메타 포함, 누설 없음)
    """
    samples = []
    for s in series:
        rows = sorted(s["rows"], key=lambda r: r[0])
        prices_by_date = {d: float(p) for d, p in rows if float(p) > 0}
        dates = [d for d, _ in rows if float(prices_by_date.get(d, 0)) > 0]
        date_set = set(dates)
        for idx, origin in enumerate(dates):
            feats = _series_features(prices_by_date, dates, idx)
            if feats is None:
                continue
            price_t = prices_by_date[origin]
            for h in horizons:
                target_date = origin + timedelta(days=h)
                if target_date not in date_set:
                    continue
                actual = prices_by_date[target_date]
                if actual <= 0:
                    continue
                row_feats = dict(feats)
                row_feats["horizon"] = float(h)
                row_feats["item_code"] = s["item_code"]
                row_feats["category"] = s["category"] or "UNKNOWN"
                samples.append(
                    Sample(
                        item_id=s["item_id"],
                        item_code=s["item_code"],
                        category=s["category"] or "UNKNOWN",
                        origin_date=origin,
                        target_date=target_date,
                        horizon=h,
                        price_t=price_t,
                        actual=actual,
                        features=row_feats,
                        target=math.log(actual / price_t),
                    )
                )
    return samples


def _to_matrix(samples, code_index, cat_index):
    rows = []
    for s in samples:
        f = s.features
        vec = [
            f["log_price"],
            f["horizon"],
            f["dow_sin"],
            f["dow_cos"],
            f["doy_sin"],
            f["doy_cos"],
            *[f[f"ret_lag_{lag}"] for lag in _LAG_DAYS],
            *[f[f"roll_mean_ratio_{w}"] for w in _ROLL_WINDOWS],
            *[f[f"roll_std_{w}"] for w in _ROLL_WINDOWS],
            float(code_index.get(s.features["item_code"], -1)),
            float(cat_index.get(s.features["category"], -1)),
        ]
        rows.append(vec)
    return np.asarray(rows, dtype="float64")


class LightGBMGlobalForecaster:
    """전 품목 글로벌 분위 회귀 모델."""

    QUANTILES = (0.1, 0.5, 0.9)

    def __init__(self, num_leaves=31, learning_rate=0.05, n_estimators=300,
                 min_child_samples=20, seed=42):
        if not LIGHTGBM_AVAILABLE:
            raise LightGBMUnavailable("pip install lightgbm 가 필요합니다.")
        self.params = dict(
            num_leaves=num_leaves,
            learning_rate=learning_rate,
            n_estimators=n_estimators,
            min_child_samples=min_child_samples,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.9,
            random_state=seed,
            verbosity=-1,
        )
        self.models = {}
        self.code_index = {}
        self.cat_index = {}
        self._cat_feature_idx = [
            FEATURE_NAMES.index("item_code"),
            FEATURE_NAMES.index("category"),
        ]

    def fit(self, samples):
        codes = sorted({s.features["item_code"] for s in samples})
        cats = sorted({s.features["category"] for s in samples})
        self.code_index = {c: i for i, c in enumerate(codes)}
        self.cat_index = {c: i for i, c in enumerate(cats)}
        x = _to_matrix(samples, self.code_index, self.cat_index)
        y = np.asarray([s.target for s in samples], dtype="float64")
        for q in self.QUANTILES:
            model = lgb.LGBMRegressor(
                objective="quantile", alpha=q, **self.params
            )
            model.fit(
                x, y,
                categorical_feature=self._cat_feature_idx,
            )
            self.models[q] = model
        return self

    def predict(self, samples):
        """샘플별 (lower, median, upper) 가격 레벨 예측을 반환."""
        x = _to_matrix(samples, self.code_index, self.cat_index)
        preds = {q: self.models[q].predict(x) for q in self.QUANTILES}
        out = []
        for i, s in enumerate(samples):
            q_lo = preds[0.1][i]
            q_mid = preds[0.5][i]
            q_hi = preds[0.9][i]
            # 분위 단조성 보정
            lo_r, mid_r, hi_r = sorted([q_lo, q_mid, q_hi])
            out.append(
                {
                    "lower": s.price_t * math.exp(lo_r),
                    "median": s.price_t * math.exp(mid_r),
                    "upper": s.price_t * math.exp(hi_r),
                }
            )
        return out


def build_inference_sample(rows, item_code, category, as_of_date, horizon):
    """``as_of_date`` 이하 최신 시점(origin)의 추론용 단일 샘플을 만든다.

    ``rows``: ``[(date, price), ...]``. 관측이 없거나 가격이 0이면 ``None``.
    """
    prices_by_date = {d: float(p) for d, p in rows if float(p) > 0}
    dates = sorted(prices_by_date)
    eligible = [d for d in dates if d <= as_of_date]
    if not eligible:
        return None
    origin = eligible[-1]
    idx = dates.index(origin)
    feats = _series_features(prices_by_date, dates, idx)
    if feats is None:
        return None
    feats = dict(feats)
    feats["horizon"] = float(horizon)
    feats["item_code"] = item_code
    feats["category"] = category or "UNKNOWN"
    price_t = prices_by_date[origin]
    return Sample(
        item_id=0,
        item_code=item_code,
        category=category or "UNKNOWN",
        origin_date=origin,
        target_date=origin + timedelta(days=horizon),
        horizon=horizon,
        price_t=price_t,
        actual=price_t,
        features=feats,
        target=0.0,
    )


class TrainedLightGBMArtifact:
    """학습된 글로벌 모델 + 분위구간 보정계수 + 메타데이터 번들."""

    version = ARTIFACT_VERSION

    def __init__(self, forecaster, interval_scale, metadata):
        self.forecaster = forecaster
        # {horizon(int): {"k": float, "coverage": float|None, "samples": int}}
        self.interval_scale = interval_scale
        self.metadata = metadata

    def save(self, path=DEFAULT_ARTIFACT_PATH):
        if joblib is None:
            raise LightGBMUnavailable("joblib 미설치")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self, path)
        return path

    @classmethod
    def load(cls, path=DEFAULT_ARTIFACT_PATH):
        if joblib is None or not os.path.exists(path):
            return None
        try:
            return joblib.load(path)
        except Exception:
            return None

    def predict_interval(self, rows, item_code, category, as_of_date, horizon):
        """엔진용 단일 예측: (median, lower, upper) + 보정 커버리지."""
        sample = build_inference_sample(
            rows, item_code, category, as_of_date, horizon
        )
        if sample is None:
            return None
        p = self.forecaster.predict([sample])[0]
        median, lower, upper = p["median"], p["lower"], p["upper"]
        scale = self.interval_scale.get(horizon) or self.interval_scale.get(str(horizon))
        k = float(scale["k"]) if scale else 1.0
        coverage = scale.get("coverage") if scale else None
        lower = median - k * (median - lower)
        upper = median + k * (upper - median)
        return {
            "median": median,
            "lower": max(lower, 0.0),
            "upper": upper,
            "coverage": coverage,
            "origin_date": sample.origin_date,
        }
