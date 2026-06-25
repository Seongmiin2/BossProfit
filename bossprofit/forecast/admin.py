from django.contrib import admin

from .models import (
    OutOfFoldForecast, ResidualObservation,
    ModelRegistry, ForecastRun, ForecastPoint, ForecastComponent,
)


@admin.register(ModelRegistry)
class ModelRegistryAdmin(admin.ModelAdmin):
    list_display = ("model_version", "stage", "algorithm", "trained_from",
                    "trained_to", "is_active", "created_at")
    list_filter = ("stage", "is_active")
    search_fields = ("model_version",)


class ForecastComponentInline(admin.StackedInline):
    model = ForecastComponent
    extra = 0


class ForecastPointInline(admin.TabularInline):
    model = ForecastPoint
    extra = 0


@admin.register(ForecastRun)
class ForecastRunAdmin(admin.ModelAdmin):
    list_display = ("item", "as_of", "status", "created_at")
    list_filter = ("status", "item")
    date_hierarchy = "as_of"
    inlines = [ForecastPointInline]


@admin.register(ForecastPoint)
class ForecastPointAdmin(admin.ModelAdmin):
    list_display = ("run", "horizon", "median", "lower_80", "upper_80", "confidence")
    list_filter = ("confidence", "horizon")
    inlines = [ForecastComponentInline]


@admin.register(OutOfFoldForecast)
class OutOfFoldForecastAdmin(admin.ModelAdmin):
    list_display = ("item", "model_version", "horizon", "origin_date",
                    "target_date", "prediction", "actual")
    list_filter = ("model_version", "horizon", "item")
    date_hierarchy = "target_date"


@admin.register(ResidualObservation)
class ResidualObservationAdmin(admin.ModelAdmin):
    list_display = ("oof", "residual", "residual_type", "created_at")
    list_filter = ("residual_type",)
