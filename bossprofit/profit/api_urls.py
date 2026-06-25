"""
BOSSPROFIT API URL Configuration
"""
from django.urls import path
from . import api_views

urlpatterns = [
    path("dashboard/", api_views.api_dashboard, name="api-dashboard"),
    path("recalculate/", api_views.api_recalculate, name="api-recalculate"),

    # Menu CRUD (create/update/delete 먼저, 그 다음 상세/목록)
    path("menus/create/", api_views.api_menu_create, name="api-menu-create"),
    path("menus/<str:menu_id>/update/", api_views.api_menu_update, name="api-menu-update"),
    path("menus/<str:menu_id>/delete/", api_views.api_menu_delete, name="api-menu-delete"),
    path("menus/", api_views.api_menu_list, name="api-menu-list"),
    path("menus/<str:menu_id>/", api_views.api_menu_detail, name="api-menu-detail"),

    # Ingredient CRUD
    path("ingredients/", api_views.api_ingredient_list, name="api-ingredient-list"),
    path("ingredients/create/", api_views.api_ingredient_create, name="api-ingredient-create"),
    path("ingredients/<str:ingredient_id>/update/", api_views.api_ingredient_update, name="api-ingredient-update"),
    path("ingredients/<str:ingredient_id>/delete/", api_views.api_ingredient_delete, name="api-ingredient-delete"),

    # Assumption
    path("assumption/", api_views.api_assumption_update, name="api-assumption-update"),

    # History
    path("history/", api_views.api_history, name="api-history"),

    # Market price (외부 시세 연동)
    path("market/preview/", api_views.api_market_preview, name="api-market-preview"),
    path("market/sync/", api_views.api_market_sync, name="api-market-sync"),
    path(
        "ingredients/<str:ingredient_id>/price-history/",
        api_views.api_ingredient_price_history,
        name="api-ingredient-price-history",
    ),
]
