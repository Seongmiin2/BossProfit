from django.contrib import admin

from .models import (
    MarketItem, IngestionRun, MarketPriceObservation,
    WholesaleAuctionObservation, ProductionRegion,
    CropProductionRegion, CropGrowthStage,
)


@admin.register(MarketItem)
class MarketItemAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "standard_unit", "source",
                    "source_item_code", "is_active")
    list_filter = ("source", "category", "is_active")
    search_fields = ("code", "name", "source_item_code")


@admin.register(IngestionRun)
class IngestionRunAdmin(admin.ModelAdmin):
    list_display = ("source", "status", "started_at", "finished_at",
                    "fetched_count", "created_count", "updated_count",
                    "skipped_count", "quality_issue_count")
    list_filter = ("source", "status")
    readonly_fields = [f.name for f in IngestionRun._meta.fields]


@admin.register(MarketPriceObservation)
class MarketPriceObservationAdmin(admin.ModelAdmin):
    list_display = ("item", "observation_date", "region", "market_type",
                    "grade", "unit", "price", "quality_flag", "collected_at")
    list_filter = ("source", "market_type", "quality_flag", "item")
    search_fields = ("item__name", "item__code")
    date_hierarchy = "observation_date"


@admin.register(WholesaleAuctionObservation)
class WholesaleAuctionObservationAdmin(admin.ModelAdmin):
    list_display = ("item", "observation_date", "market", "origin", "grade",
                    "price", "volume", "quality_flag", "collected_at")
    list_filter = ("source", "market", "quality_flag", "item")
    search_fields = ("item__name", "item__code", "market")
    date_hierarchy = "observation_date"


@admin.register(ProductionRegion)
class ProductionRegionAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(CropProductionRegion)
class CropProductionRegionAdmin(admin.ModelAdmin):
    list_display = ("item", "region", "weight", "valid_from")
    list_filter = ("item", "region")


@admin.register(CropGrowthStage)
class CropGrowthStageAdmin(admin.ModelAdmin):
    list_display = ("item", "region", "stage", "start_day", "end_day")
    list_filter = ("item", "stage")
