"""end-to-end 예측 파이프라인 (항목 8~13 통합).

as_of 시점까지의 데이터만으로 (point-in-time):
  base → +weather → +residual → conformal 구간보정 → 신뢰등급
을 조립해 ForecastRun/Point/Component 로 저장하고 백엔드 계약 응답을 만든다.

각 단계는 개별 검증된 모듈을 재사용한다. 보정 단계가 비활성화면 delta=0으로 둔다.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from .data import load_price_series, load_volume_series
from .base_models import LightGBMQuantileForecaster
from .baselines import LastValueForecaster
from .weather_features import (
    load_item_weather, load_item_forecast_weather,
    build_weather_exposure, sensitive_growth_doys,
)
from .weather_model import detect_weather_shocks
from .residuals import load_residuals
from .residual_model import build_residual_training_table, ResidualCorrector
from .calibration import (
    ConformalIntervalCalibrator, confidence_grade, widen_for_low_confidence,
)
from .evaluation import rolling_origin_backtest
from .serving import persist_forecast


def _calibration_set(price, model_factory, horizon, tail=60, step=3):
    """history 꼬리 구간 rolling-origin으로 (qlo, qhi, actual) 보정셋 생성."""
    s = price.dropna().astype(float)
    if len(s) < tail + horizon:
        return None
    cal_start = s.index[-tail].date()
    preds = rolling_origin_backtest(
        s, {"m": model_factory}, [horizon],
        min_train=len(s) - tail - horizon, step=step, test_start=cal_start,
    )
    return preds if not preds.empty else None


def produce_forecast(
    item,
    as_of: date,
    horizons=(7, 30),
    residual_version: str = "last_value",
    persist: bool = True,
) -> dict:
    """단일 품목의 최종 예측을 단계별 분해와 함께 생성한다."""
    horizons = list(horizons)
    price = load_price_series(item, end=as_of)
    if price.empty:
        return {"ok": False, "reason": "no_price"}
    volume = load_volume_series(item, end=as_of)
    growth_doy = sensitive_growth_doys(item)
    wdf = load_item_weather(item, end=as_of)
    # 가격 모델용 노출은 과거 관측만 사용한다(미래 예보를 feature로 넣지 않음 = 누수 방지).
    exposure = build_weather_exposure(wdf, growth_doy=growth_doy) if not wdf.empty else pd.DataFrame()

    # 미래 기상 예보(단기예보)는 충격 감지·신뢰등급에만 결합한다(point-in-time: issued<=as_of).
    fc_wdf, fc_issued = load_item_forecast_weather(item, as_of, max(horizons))
    if not fc_wdf.empty and not wdf.empty:
        combined = pd.concat([wdf, fc_wdf])
        combined = combined[~combined.index.duplicated(keep="last")].sort_index()
        shock_exposure = build_weather_exposure(combined, growth_doy=growth_doy)
    elif not fc_wdf.empty:
        shock_exposure = build_weather_exposure(fc_wdf, growth_doy=growth_doy)
    else:
        shock_exposure = exposure
    shocks = detect_weather_shocks(shock_exposure) if not shock_exposure.empty else set()
    past_extreme = as_of in shocks
    n_hist = len(price)

    base_model = LightGBMQuantileForecaster(horizons=tuple(horizons), volume=volume).fit(price)
    weather_model = None
    if not exposure.empty:
        weather_model = LightGBMQuantileForecaster(
            horizons=tuple(horizons), volume=volume, weather=exposure
        ).fit(price)

    points = []
    for h in horizons:
        bq = base_model.predict_quantiles(h)
        base_pred = bq[0.5]
        if weather_model is not None:
            wq = weather_model.predict_quantiles(h)
            stage2 = wq[0.5]
            qlo, qhi = wq[0.1], wq[0.9]
        else:
            stage2 = base_pred
            qlo, qhi = bq[0.1], bq[0.9]
        weather_delta = stage2 - base_pred

        # --- Stage 3 잔차 보정 ---
        residual_delta = 0.0
        residual_disabled = True
        rdf = load_residuals(item, residual_version, horizon=h, as_of=as_of)
        table = build_residual_training_table(rdf) if not rdf.empty else pd.DataFrame()
        if len(table) >= 8 and stage2 > 0:
            corr = ResidualCorrector().fit(table)
            last = table.sort_values("origin_date").iloc[-1]
            resid_hat = corr.predict_row(last.to_dict())
            final = float(np.exp(np.log(stage2) + resid_hat))
            residual_delta = final - stage2
            residual_disabled = False

        median = base_pred + weather_delta + residual_delta

        # --- 구간: conformal 보정 + 신뢰등급 ---
        factory = (lambda hh=h: LightGBMQuantileForecaster(horizons=(hh,), volume=volume)) \
            if weather_model is None else \
            (lambda hh=h: LightGBMQuantileForecaster(horizons=(hh,), volume=volume, weather=exposure))
        # 구간 폭을 median 기준으로 평행이동
        lo, hi = qlo + (median - stage2), qhi + (median - stage2)
        cal = _calibration_set(price, factory, h)
        if cal is not None and len(cal) >= 10:
            # 보정셋의 (qlo,qhi)는 별도 분위수 예측이 없으므로 점예측 대비 잔차로 근사 보정
            err = (cal["y_true"] - cal["y_pred"]).abs()
            d = float(np.quantile(err, 0.8, method="higher"))
            lo, hi = median - d, median + d

        # 극한기상: as_of 당일 충격 + (as_of, as_of+h] 구간의 예보 충격
        h_end = as_of + timedelta(days=h)
        extreme = past_extreme or any(as_of < d <= h_end for d in shocks)

        width = hi - lo
        grade = confidence_grade(n_hist, width, median, extreme=extreme)
        lo, hi = widen_for_low_confidence(lo, hi, median, grade)

        points.append({
            "horizon": h,
            "target_date": (as_of + pd.Timedelta(days=h)).date() if isinstance(as_of, pd.Timestamp) else (pd.Timestamp(as_of) + pd.Timedelta(days=h)).date(),
            "base": round(base_pred, 4),
            "weather_delta": round(weather_delta, 4),
            "residual_delta": round(residual_delta, 4),
            "median": round(median, 4),
            "lower_80": round(lo, 4),
            "upper_80": round(hi, 4),
            "confidence": grade,
            "weather_disabled": weather_model is None,
            "residual_disabled": residual_disabled,
        })

    versions = {
        "base": "base-price-lgbm-v1",
        "weather": "weather-impact-lgbm-v1" if weather_model is not None else None,
        "residual": f"residual-{residual_version}-v1",
        "calibration": "conformal-v1",
    }
    result = {"ok": True, "item": item.code, "as_of": as_of.isoformat(), "points": points,
              "model_versions": versions}
    if persist:
        run = persist_forecast(item, as_of, points, versions,
                               weather_forecast_issued_at=fc_issued)
        result["run_id"] = run.id
    return result
