"""Rolling-origin OOF 잔차 생성 (항목 11).

핵심 규칙(누수 방지):
- 잔차 라벨은 in-sample이 아니라 rolling-origin OOF 예측에서만 만든다.
- 각 OOF 예측은 origin_date 까지의 과거만으로 생성된다(rolling_origin_backtest가 보장).
- residual(t,h) = log(actual(t+h)) - log(stage2_oof_pred(t,h)).
- 0/음수 가격은 log 불가이므로 제외한다.

생성된 잔차는 OutOfFoldForecast/ResidualObservation 으로 멱등 저장한다.
"""
from __future__ import annotations

from typing import Callable, Optional

import numpy as np
import pandas as pd
from django.db import transaction

from .evaluation import rolling_origin_backtest
from .models import OutOfFoldForecast, ResidualObservation


def compute_oof_residuals(
    price: pd.Series,
    model_factory: Callable,
    horizons: list[int],
    min_train: int,
    model_version: str,
    step: int = 1,
    test_start=None,
) -> pd.DataFrame:
    """OOF 예측을 생성하고 로그 잔차를 계산해 DataFrame으로 반환(저장 안 함)."""
    preds = rolling_origin_backtest(
        price, {model_version: model_factory}, horizons,
        min_train=min_train, step=step, test_start=test_start,
    )
    if preds.empty:
        return preds.assign(residual=[])

    # log 잔차: 가격 양수만
    valid = (preds["y_true"] > 0) & (preds["y_pred"] > 0)
    preds = preds[valid].copy()
    preds["residual"] = np.log(preds["y_true"].astype(float)) - np.log(preds["y_pred"].astype(float))
    preds["model_version"] = model_version
    return preds.reset_index(drop=True)


@transaction.atomic
def persist_oof_residuals(item, residual_df: pd.DataFrame) -> dict:
    """잔차 DataFrame을 OutOfFoldForecast/ResidualObservation으로 멱등 저장."""
    created = 0
    updated = 0
    for _, r in residual_df.iterrows():
        oof, was_created = OutOfFoldForecast.objects.update_or_create(
            item=item,
            model_version=r["model_version"],
            horizon=int(r["horizon"]),
            origin_date=pd.Timestamp(r["origin_date"]).date(),
            target_date=pd.Timestamp(r["target_date"]).date(),
            defaults={
                "prediction": float(r["y_pred"]),
                "actual": float(r["y_true"]),
            },
        )
        ResidualObservation.objects.update_or_create(
            oof=oof,
            defaults={"residual": float(r["residual"]), "residual_type": "log"},
        )
        created += 1 if was_created else 0
        updated += 0 if was_created else 1
    return {"created": created, "updated": updated, "total": len(residual_df)}


def generate_oof_residuals(
    item,
    price: pd.Series,
    model_factory: Callable,
    horizons: list[int],
    min_train: int,
    model_version: str,
    step: int = 1,
    test_start=None,
    persist: bool = True,
) -> pd.DataFrame:
    """OOF 잔차 생성(+선택 저장)의 단일 진입점."""
    df = compute_oof_residuals(
        price, model_factory, horizons, min_train, model_version,
        step=step, test_start=test_start,
    )
    if persist and not df.empty:
        persist_oof_residuals(item, df)
    return df


def load_residuals(
    item, model_version: str, horizon: Optional[int] = None, as_of=None
) -> pd.DataFrame:
    """저장된 잔차를 DataFrame으로 로드.

    as_of 가 주어지면 target_date <= as_of 인 잔차만 반환한다(누수 방지:
    잔차 모델을 as_of 시점에 학습할 때 '이미 관측된' 잔차만 쓰기 위함).
    """
    qs = ResidualObservation.objects.filter(
        oof__item=item, oof__model_version=model_version
    ).select_related("oof")
    if horizon is not None:
        qs = qs.filter(oof__horizon=horizon)
    if as_of is not None:
        qs = qs.filter(oof__target_date__lte=as_of)
    rows = [
        {
            "horizon": r.oof.horizon,
            "origin_date": r.oof.origin_date,
            "target_date": r.oof.target_date,
            "prediction": r.oof.prediction,
            "actual": r.oof.actual,
            "residual": r.residual,
        }
        for r in qs
    ]
    return pd.DataFrame(rows)
