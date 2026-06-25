"""Residual Correction Model — Stage 3 (항목 12).

최종 예측:
    final_log_price(t,h) = log(stage2_pred(t,h)) + predicted_residual(t,h)
    final_price          = exp(final_log_price)

누수 방지 (핵심):
- 잔차 feature는 '예측 기준시점 O에서 이미 관측된 잔차'만 사용한다.
  잔차는 target_date 에 관측되므로, origin O 에서는 target_date <= O 인 잔차만 가용하다.
  (h스텝 관측 지연을 feature 빌더가 강제한다 → 미래 잔차 누수 차단)
- 잔차 모델은 OOF 잔차에서만 학습한다(항목 11 산출물).

Auto-disable guardrail:
- 별도 test fold에서 잔차 보정이 stage2를 개선하지 못하면 보정량을 0으로 비활성화한다.
  (기획서: 개선 없는 품목·horizon은 보정 자동 0 처리)
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

RESIDUAL_FEATURES = ["r_lag1", "r_bias_5", "r_bias_10", "r_std_10"]


def build_residual_training_table(
    residual_df: pd.DataFrame, min_history: int = 5
) -> pd.DataFrame:
    """단일 horizon 잔차에서 (origin별) feature+label 테이블을 만든다.

    각 origin O의 feature는 target_date <= O 인 잔차만으로 계산한다(누수 차단).
    residual_df 컬럼: origin_date, target_date, prediction, actual, residual.
    """
    if residual_df.empty:
        return pd.DataFrame()
    rdf = residual_df.copy()
    rdf["origin_date"] = pd.to_datetime(rdf["origin_date"])
    rdf["target_date"] = pd.to_datetime(rdf["target_date"])
    observed = pd.Series(
        rdf["residual"].astype(float).values, index=rdf["target_date"]
    ).sort_index()

    rows = []
    for _, r in rdf.sort_values("origin_date").iterrows():
        O = r["origin_date"]
        hist = observed[observed.index <= O]  # O 시점에 관측된 잔차만
        if len(hist) < min_history:
            continue
        rows.append({
            "origin_date": O,
            "target_date": r["target_date"],
            "prediction": float(r["prediction"]),
            "actual": float(r["actual"]) if pd.notna(r["actual"]) else np.nan,
            "r_lag1": float(hist.iloc[-1]),
            "r_bias_5": float(hist.tail(5).mean()),
            "r_bias_10": float(hist.tail(10).mean()),
            "r_std_10": float(hist.tail(10).std()) if len(hist) >= 2 else 0.0,
            "y": float(r["residual"]),
        })
    return pd.DataFrame(rows)


class ResidualCorrector:
    """관측된 잔차 통계로 다음 잔차를 예측하는 Ridge 모델."""

    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha

    def fit(self, table: pd.DataFrame) -> "ResidualCorrector":
        from sklearn.linear_model import Ridge
        X = table[RESIDUAL_FEATURES].fillna(0.0).values
        y = table["y"].values
        self.model_ = Ridge(alpha=self.alpha).fit(X, y)
        return self

    def predict_row(self, feat: dict) -> float:
        X = [[feat.get(f, 0.0) for f in RESIDUAL_FEATURES]]
        return float(self.model_.predict(X)[0])


def _wape(actual, pred):
    actual = np.asarray(actual, dtype="float64")
    pred = np.asarray(pred, dtype="float64")
    denom = np.sum(np.abs(actual))
    return float(np.sum(np.abs(actual - pred)) / denom) if denom else float("nan")


def evaluate_residual_correction(
    residual_df: pd.DataFrame,
    test_start,
    min_history: int = 5,
    min_train_rows: int = 8,
    min_improvement: float = 0.0,
) -> dict:
    """단일 horizon에서 stage2 vs stage2+residual 을 test fold로 비교하고 자동 비활성화 판단.

    각 test 행마다 그 origin까지 관측된 잔차만으로 corrector를 재학습한다(expanding, 누수 없음).
    min_improvement: 이 상대개선(예: 출시 게이트 0.03=3%) 미만이면 보정을 비활성화한다.
      유한 test fold의 우연한 미세 개선을 신뢰하지 않기 위함.
    """
    table = build_residual_training_table(residual_df, min_history=min_history)
    if table.empty:
        return {"applied": False, "reason": "insufficient_history"}

    test_ts = pd.Timestamp(test_start)
    test = table[table["target_date"] >= test_ts]
    test = test.dropna(subset=["actual"])
    if test.empty:
        return {"applied": False, "reason": "no_test_rows"}

    stage2_preds, corrected_preds, actuals = [], [], []
    for _, row in test.iterrows():
        O = row["origin_date"]
        # 누수 차단: target_date <= O 인 잔차로만 학습
        train = table[table["target_date"] <= O]
        stage2_pred = row["prediction"]
        if len(train) >= min_train_rows and stage2_pred > 0:
            corr = ResidualCorrector().fit(train)
            resid_hat = corr.predict_row(row)
            corrected = float(np.exp(np.log(stage2_pred) + resid_hat))
        else:
            corrected = stage2_pred  # 보정 보류
        stage2_preds.append(stage2_pred)
        corrected_preds.append(corrected)
        actuals.append(row["actual"])

    stage2_wape = _wape(actuals, stage2_preds)
    corrected_wape = _wape(actuals, corrected_preds)
    improvement = (stage2_wape - corrected_wape) / stage2_wape if stage2_wape else 0.0
    # 상대개선이 게이트 미만이면 비활성화(우연한 미세 개선 방어)
    disabled = improvement < min_improvement or improvement <= 0.0

    return {
        "applied": True,
        "n_test": len(test),
        "stage2_wape": stage2_wape,
        "corrected_wape": corrected_wape if not disabled else stage2_wape,
        "raw_corrected_wape": corrected_wape,
        "improvement": improvement,
        "disabled": disabled,
    }


def evaluate_item_residual(
    item, model_version: str, horizon: int, test_start,
    min_history: int = 5, min_train_rows: int = 8,
) -> dict:
    """저장된 OOF 잔차(항목 11)에서 해당 품목·horizon의 Stage 3 보정을 평가한다."""
    from .residuals import load_residuals

    rdf = load_residuals(item, model_version, horizon=horizon)
    result = evaluate_residual_correction(
        rdf, test_start, min_history=min_history, min_train_rows=min_train_rows
    )
    result["diagnostics"] = residual_diagnostics(rdf)
    result["item"] = item.code
    result["horizon"] = horizon
    return result


def residual_diagnostics(residual_df: pd.DataFrame) -> dict:
    """잔차 진단: 평균 편향, 1차 자기상관(보정 여지가 있는지)."""
    if residual_df.empty:
        return {"n": 0}
    r = pd.Series(residual_df["residual"].astype(float).values)
    r = r.dropna()
    if len(r) < 3:
        return {"n": int(len(r)), "mean_bias": float(r.mean()) if len(r) else None}
    acf1 = float(r.autocorr(lag=1)) if r.std() > 0 else 0.0
    return {
        "n": int(len(r)),
        "mean_bias": float(r.mean()),
        "std": float(r.std()),
        "acf_lag1": acf1,
    }
