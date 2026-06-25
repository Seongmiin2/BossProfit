from django.contrib import admin

from .models import (
    Store,
    StoreMember,
    Ingredient,
    Menu,
    RecipeItem,
    ProfitAssumption,
    MenuProfitSnapshot,
    IngredientPriceHistory,
)


class StoreMemberInline(admin.TabularInline):
    model = StoreMember
    extra = 0
    autocomplete_fields = ["user"]


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "owner", "business_type", "region", "created_at")
    search_fields = ("name", "owner__username")
    inlines = [StoreMemberInline]


@admin.register(StoreMember)
class StoreMemberAdmin(admin.ModelAdmin):
    list_display = ("store", "user", "role", "created_at")
    list_filter = ("role",)
    search_fields = ("store__name", "user__username")


class RecipeItemInline(admin.TabularInline):
    model = RecipeItem
    extra = 1
    autocomplete_fields = ["ingredient"]


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = (
        "name", "store", "category", "purchase_quantity", "unit",
        "purchase_price", "unit_cost_display",
    )
    list_filter = ("store", "category")
    search_fields = ("name", "ingredient_id")
    ordering = ("category", "name")

    @admin.display(description="단가(원)")
    def unit_cost_display(self, obj):
        return f"{obj.unit_cost:.2f}"


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = (
        "menu_id", "name", "store", "category", "price",
        "monthly_orders", "food_cost_display", "is_active",
    )
    list_filter = ("store", "category", "is_active")
    search_fields = ("name", "menu_id")
    inlines = [RecipeItemInline]

    @admin.display(description="원가율(%)")
    def food_cost_display(self, obj):
        return f"{obj.food_cost_rate() * 100:.1f}"


@admin.register(ProfitAssumption)
class ProfitAssumptionAdmin(admin.ModelAdmin):
    list_display = (
        "label", "store", "dine_in_share", "delivery_share", "takeout_share",
        "delivery_commission_rate", "rider_fee", "is_active",
    )
    list_filter = ("store",)


@admin.register(IngredientPriceHistory)
class IngredientPriceHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "ingredient", "old_price", "new_price",
        "delta", "source", "created_at",
    )
    list_filter = ("source", "ingredient__category")
    search_fields = ("ingredient__name", "ingredient__ingredient_id")
    readonly_fields = ("ingredient", "old_price", "new_price", "source", "note", "created_at")

    @admin.display(description="증감(원)")
    def delta(self, obj):
        return f"{obj.delta:+,}"


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
