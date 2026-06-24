from django.contrib import admin

from .models import Store, StoreMember, OnboardingProgress


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("name", "business_type", "region", "created_at")
    list_filter = ("business_type",)
    search_fields = ("name", "region")


@admin.register(StoreMember)
class StoreMemberAdmin(admin.ModelAdmin):
    list_display = ("store", "user", "role", "is_active", "joined_at")
    list_filter = ("role", "is_active")
    search_fields = ("store__name", "user__username")


@admin.register(OnboardingProgress)
class OnboardingProgressAdmin(admin.ModelAdmin):
    list_display = (
        "store",
        "current_step",
        "ingredient_completed",
        "menu_completed",
        "recipe_completed",
        "sales_completed",
        "updated_at",
    )
    list_filter = ("current_step",)
