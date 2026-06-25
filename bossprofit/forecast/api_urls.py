"""예측 API URL 설정."""
from django.urls import path

from . import api_views

urlpatterns = [
    path("items/", api_views.api_forecast_items, name="api-forecast-items"),
    path("ingredients/", api_views.api_forecast_ingredients, name="api-forecast-ingredients"),
    path("<str:item_code>/", api_views.api_forecast_detail, name="api-forecast-detail"),
]
