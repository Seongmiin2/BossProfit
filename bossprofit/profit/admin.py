from django.contrib import admin

from .models import (
    Ingredient,
    Menu,
    RecipeItem,
    DailyMenuSale,
    ProfitAssumption,
    MenuProfitSnapshot,
    MarketForecast,
    MarketItem,
    MarketModelMetric,
    MarketPriceObservation,
    MarketRankingSnapshot,
    MarketRecommendation,
    CropProductionRegion,
    ForecastCalibration,
    ForecastComponent,
    ForecastModelComparison,
    ForecastPoint,
    ForecastRun,
    IngredientMarketMapping,
    IngestionRun,
    OutOfFoldForecast,
    ProductionStatistic,
    PurchasePriceObservation,
    RawSourcePayload,
    ResidualObservation,
    StoreSalesImport,
    WeatherExposureFeature,
    WeatherForecastSnapshot,
    WeatherObservation,
    WeatherStationMapping,
    WholesaleAuctionObservation,
    ActionPlan,
)


class RecipeItemInline(admin.TabularInline):
    model = RecipeItem
    extra = 1
    autocomplete_fields = ["ingredient"]


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = (
        "store", "name", "category", "purchase_quantity", "unit",
        "purchase_price", "unit_cost_display",
    )
    list_filter = ("store", "category")
    search_fields = ("store__name", "name", "ingredient_id")
    ordering = ("category", "name")

    @admin.display(description="단가(원)")
    def unit_cost_display(self, obj):
        return f"{obj.unit_cost:.2f}"


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = (
        "store", "menu_id", "name", "category", "price",
        "monthly_orders", "food_cost_display", "is_active",
    )
    list_filter = ("store", "category", "is_active")
    search_fields = ("store__name", "name", "menu_id")
    inlines = [RecipeItemInline]

    @admin.display(description="원가율(%)")
    def food_cost_display(self, obj):
        return f"{obj.food_cost_rate() * 100:.1f}"


@admin.register(ProfitAssumption)
class ProfitAssumptionAdmin(admin.ModelAdmin):
    list_display = (
        "store", "label", "dine_in_share", "delivery_share", "takeout_share",
        "delivery_commission_rate", "rider_fee", "is_active",
    )


@admin.register(MenuProfitSnapshot)
class MenuProfitSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "store", "menu", "monthly_profit", "weighted_margin",
        "food_cost_rate", "signal", "created_at",
    )
    list_filter = ("store", "signal", "menu__category")
    readonly_fields = (
        "store", "owner", "menu", "base_cost", "food_cost_rate",
        "dine_in_margin", "takeout_margin", "delivery_margin",
        "weighted_margin", "monthly_profit", "monthly_revenue",
        "signal", "created_at",
    )


@admin.register(DailyMenuSale)
class DailyMenuSaleAdmin(admin.ModelAdmin):
    list_display = ("sale_date", "store", "menu", "channel", "quantity")
    list_filter = ("store", "channel", "sale_date")
    search_fields = ("store__name", "menu__name")


@admin.register(MarketItem)
class MarketItemAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "region", "unit", "is_active")
    list_filter = ("category", "region", "is_active")
    search_fields = ("code", "name")


admin.site.register(MarketPriceObservation)
admin.site.register(MarketForecast)
admin.site.register(MarketModelMetric)
admin.site.register(MarketRecommendation)
admin.site.register(MarketRankingSnapshot)
admin.site.register(CropProductionRegion)
admin.site.register(ForecastCalibration)
admin.site.register(ForecastComponent)
admin.site.register(ForecastModelComparison)
admin.site.register(ForecastPoint)
admin.site.register(ForecastRun)
admin.site.register(IngredientMarketMapping)
admin.site.register(IngestionRun)
admin.site.register(OutOfFoldForecast)
admin.site.register(ProductionStatistic)
admin.site.register(PurchasePriceObservation)
admin.site.register(RawSourcePayload)
admin.site.register(ResidualObservation)
admin.site.register(StoreSalesImport)
admin.site.register(WeatherExposureFeature)
admin.site.register(WeatherForecastSnapshot)
admin.site.register(WeatherObservation)
admin.site.register(WeatherStationMapping)
admin.site.register(WholesaleAuctionObservation)
admin.site.register(ActionPlan)
