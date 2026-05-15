from django.contrib import admin

from .models import (
    Ingredient,
    Menu,
    RecipeItem,
    ProfitAssumption,
    MenuProfitSnapshot,
)


class RecipeItemInline(admin.TabularInline):
    model = RecipeItem
    extra = 1
    autocomplete_fields = ["ingredient"]


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = (
        "name", "category", "purchase_quantity", "unit",
        "purchase_price", "unit_cost_display",
    )
    list_filter = ("category",)
    search_fields = ("name", "ingredient_id")
    ordering = ("category", "name")

    @admin.display(description="단가(원)")
    def unit_cost_display(self, obj):
        return f"{obj.unit_cost:.2f}"


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = (
        "menu_id", "name", "category", "price",
        "monthly_orders", "food_cost_display", "is_active",
    )
    list_filter = ("category", "is_active")
    search_fields = ("name", "menu_id")
    inlines = [RecipeItemInline]

    @admin.display(description="원가율(%)")
    def food_cost_display(self, obj):
        return f"{obj.food_cost_rate() * 100:.1f}"


@admin.register(ProfitAssumption)
class ProfitAssumptionAdmin(admin.ModelAdmin):
    list_display = (
        "label", "dine_in_share", "delivery_share", "takeout_share",
        "delivery_commission_rate", "rider_fee", "is_active",
    )


@admin.register(MenuProfitSnapshot)
class MenuProfitSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "menu", "monthly_profit", "weighted_margin",
        "food_cost_rate", "signal", "created_at",
    )
    list_filter = ("signal", "menu__category")
    readonly_fields = (
        "menu", "base_cost", "food_cost_rate",
        "dine_in_margin", "takeout_margin", "delivery_margin",
        "weighted_margin", "monthly_profit", "monthly_revenue",
        "signal", "created_at",
    )
