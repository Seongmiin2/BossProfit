"""Model Registry + Forecast 영속화/계약 응답 테스트 (항목 13)."""
from datetime import date

from django.test import TestCase

from market.models import MarketItem
from forecast.models import ForecastRun, ForecastPoint, ForecastComponent, ModelRegistry
from forecast.serving import register_model, persist_forecast, forecast_response, forecast_response_all


class RegistryTests(TestCase):
    def test_register_is_idempotent(self):
        register_model("base-price-v1", "base", algorithm="lightgbm")
        register_model("base-price-v1", "base", algorithm="lightgbm_v2")
        self.assertEqual(ModelRegistry.objects.filter(model_version="base-price-v1").count(), 1)
        self.assertEqual(ModelRegistry.objects.get(model_version="base-price-v1").algorithm, "lightgbm_v2")


class ForecastPersistenceTests(TestCase):
    def setUp(self):
        self.item = MarketItem.objects.create(code="ONION", name="양파", source_item_code="245")
        self.points = [{
            "horizon": 30, "target_date": date(2026, 7, 24),
            "base": "1740.00", "weather_delta": "85.00", "residual_delta": "25.00",
            "median": "1850.00", "lower_80": "1650.00", "upper_80": "2050.00",
            "lower_95": "1500.00", "upper_95": "2250.00",
            "confidence": "MEDIUM", "weather_disabled": False, "residual_disabled": False,
        }]
        self.versions = {
            "base": "base-price-v1", "weather": "weather-impact-v1",
            "residual": "residual-correction-v1", "calibration": "interval-calibration-v1",
        }

    def test_persist_creates_run_point_component(self):
        run = persist_forecast(self.item, date(2026, 6, 24), self.points, self.versions)
        self.assertEqual(ForecastRun.objects.count(), 1)
        self.assertEqual(ForecastPoint.objects.count(), 1)
        self.assertEqual(ForecastComponent.objects.count(), 1)

    def test_idempotent_replaces_points(self):
        persist_forecast(self.item, date(2026, 6, 24), self.points, self.versions)
        persist_forecast(self.item, date(2026, 6, 24), self.points, self.versions)
        self.assertEqual(ForecastRun.objects.count(), 1)
        self.assertEqual(ForecastPoint.objects.count(), 1)  # 중복 안 쌓임

    def test_contract_response_matches_spec(self):
        run = persist_forecast(self.item, date(2026, 6, 24), self.points, self.versions)
        resp = forecast_response(run, 30)
        # 통합 보고서 11.4 필수 키
        for key in ["target_type", "target_id", "as_of", "horizon_days",
                    "base_prediction", "weather_adjustment", "residual_adjustment",
                    "median", "lower_80", "upper_80", "confidence",
                    "model_version", "data_quality"]:
            self.assertIn(key, resp)
        self.assertEqual(resp["target_id"], "ONION")
        self.assertEqual(resp["base_prediction"], "1740.00")
        self.assertEqual(resp["median"], "1850.00")
        self.assertEqual(resp["model_version"]["base"], "base-price-v1")

    def test_components_sum_to_median(self):
        run = persist_forecast(self.item, date(2026, 6, 24), self.points, self.versions)
        resp = forecast_response(run, 30)
        from decimal import Decimal
        total = (Decimal(resp["base_prediction"]) + Decimal(resp["weather_adjustment"])
                 + Decimal(resp["residual_adjustment"]))
        self.assertEqual(total, Decimal(resp["median"]))

    def test_response_all_returns_each_horizon(self):
        multi = self.points + [dict(self.points[0], horizon=7, target_date=date(2026, 7, 1))]
        run = persist_forecast(self.item, date(2026, 6, 24), multi, self.versions)
        self.assertEqual(len(forecast_response_all(run)), 2)
