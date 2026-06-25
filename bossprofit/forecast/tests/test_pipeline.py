"""end-to-end 파이프라인 통합 테스트 (항목 13)."""
import math
from datetime import date, timedelta

from django.test import TestCase
from django.utils import timezone

from market.models import MarketItem, MarketPriceObservation
from forecast.baselines import LastValueForecaster
from forecast.data import load_price_series
from forecast.residuals import generate_oof_residuals
from forecast.pipeline import produce_forecast
from forecast.models import ForecastRun, ForecastPoint, ForecastComponent
from forecast.serving import forecast_response


class PipelineTests(TestCase):
    def setUp(self):
        self.item = MarketItem.objects.create(code="ONION", name="양파", source_item_code="245")
        start = date(2026, 1, 1)
        now = timezone.now()
        for i in range(140):
            d = start + timedelta(days=i)
            price = 2.0 + 0.01 * i + 0.3 * math.sin(2 * math.pi * i / 7)
            MarketPriceObservation.objects.create(
                item=self.item, observation_date=d, market_type="retail",
                region="", unit="g", price=round(price, 3), source="kamis",
                collected_at=now, quality_flag="ok",
            )
        # Stage 3용 OOF 잔차 사전 생성
        price = load_price_series(self.item)
        generate_oof_residuals(
            self.item, price, lambda: LastValueForecaster(), horizons=[7],
            min_train=30, model_version="last_value", persist=True,
        )

    def test_produce_persists_and_contract_consistent(self):
        out = produce_forecast(self.item, date(2026, 5, 1), horizons=[7], persist=True)
        self.assertTrue(out["ok"])
        self.assertEqual(ForecastRun.objects.count(), 1)
        self.assertEqual(ForecastPoint.objects.count(), 1)
        self.assertEqual(ForecastComponent.objects.count(), 1)

        run = ForecastRun.objects.get(id=out["run_id"])
        resp = forecast_response(run, 7)
        # 구간 순서
        self.assertLessEqual(float(resp["lower_80"]), float(resp["median"]))
        self.assertLessEqual(float(resp["median"]), float(resp["upper_80"]))
        # 단계 분해 합 = median
        from decimal import Decimal
        total = (Decimal(resp["base_prediction"]) + Decimal(resp["weather_adjustment"])
                 + Decimal(resp["residual_adjustment"]))
        self.assertEqual(total, Decimal(resp["median"]))
        self.assertIn(resp["confidence"], ["HIGH", "MEDIUM", "LOW"])

    def test_point_in_time_uses_only_past(self):
        # as_of 이후 가격을 추가해도 동일 as_of 예측의 base가 바뀌지 않아야 한다(과거만 사용)
        out1 = produce_forecast(self.item, date(2026, 4, 1), horizons=[7], persist=False)
        # 미래 데이터 추가
        now = timezone.now()
        for i in range(140, 170):
            d = date(2026, 1, 1) + timedelta(days=i)
            MarketPriceObservation.objects.create(
                item=self.item, observation_date=d, market_type="retail", region="",
                unit="g", price=99.0, source="kamis", collected_at=now, quality_flag="ok",
            )
        out2 = produce_forecast(self.item, date(2026, 4, 1), horizons=[7], persist=False)
        self.assertAlmostEqual(out1["points"][0]["base"], out2["points"][0]["base"], places=6)
