from django.contrib import admin

from .models import (
    WeatherStation, WeatherStationMapping,
    WeatherObservation, WeatherForecastSnapshot,
)


@admin.register(WeatherStation)
class WeatherStationAdmin(admin.ModelAdmin):
    list_display = ("station_id", "name", "source", "latitude", "longitude", "is_active")
    list_filter = ("source", "is_active")
    search_fields = ("station_id", "name")


@admin.register(WeatherStationMapping)
class WeatherStationMappingAdmin(admin.ModelAdmin):
    list_display = ("region", "station", "weight", "distance_km")
    list_filter = ("region",)


@admin.register(WeatherObservation)
class WeatherObservationAdmin(admin.ModelAdmin):
    list_display = ("station", "observed_date", "quality_flag", "collected_at")
    list_filter = ("source", "quality_flag", "station")
    date_hierarchy = "observed_date"


@admin.register(WeatherForecastSnapshot)
class WeatherForecastSnapshotAdmin(admin.ModelAdmin):
    list_display = ("provider", "issued_at", "valid_at", "station", "region", "collected_at")
    list_filter = ("provider", "station")
    date_hierarchy = "valid_at"
