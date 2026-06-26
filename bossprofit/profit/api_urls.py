"""
BOSSPROFIT API URL Configuration
"""
from django.urls import path
from . import api_views

urlpatterns = [
    path("dashboard/", api_views.api_dashboard, name="api-dashboard"),
    path(
        "public/product-preview/",
        api_views.api_public_product_preview,
        name="api-public-product-preview",
    ),
    path(
        "analysis/store/",
        api_views.api_store_analysis,
        name="api-store-analysis",
    ),
    path(
        "analysis/report/",
        api_views.api_analysis_report,
        name="api-analysis-report",
    ),
    path(
        "analysis/calendar/",
        api_views.api_sales_calendar,
        name="api-sales-calendar",
    ),
    path(
        "analysis/calendar/day/",
        api_views.api_sales_day_detail,
        name="api-sales-day-detail",
    ),
    path(
        "analysis/follow-up/",
        api_views.api_analysis_follow_up,
        name="api-analysis-follow-up",
    ),
    path(
        "action-plans/",
        api_views.api_action_plan_create,
        name="api-action-plan-create",
    ),
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

    # Daily Sales
    path("sales/daily/", api_views.api_daily_sales_upsert, name="api-daily-sales"),

    # Public market intelligence
    path(
        "market/rankings/<str:ranking_type>/",
        api_views.api_market_ranking,
        name="api-market-ranking",
    ),
]
