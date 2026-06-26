"""
BOSSPROFIT REST API Serializers
"""
from rest_framework import serializers
from .models import (
    Ingredient,
    Menu,
    RecipeItem,
    DailyMenuSale,
    ProfitAssumption,
    MenuProfitSnapshot,
)


class IngredientSerializer(serializers.ModelSerializer):
    """식자재 마스터"""
    unit_cost = serializers.SerializerMethodField()

    class Meta:
        model = Ingredient
        fields = [
            'ingredient_id', 'name', 'category',
            'purchase_quantity', 'purchase_price', 'unit',
            'is_hq_supplied', 'memo', 'unit_cost'
        ]

    def get_unit_cost(self, obj):
        return obj.unit_cost


class RecipeItemInlineSerializer(serializers.ModelSerializer):
    """레시피 항목 (인라인, 메뉴 상세에서 사용)"""
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    ingredient_id = serializers.CharField(source='ingredient.ingredient_id', read_only=True)
    unit = serializers.CharField(source='ingredient.unit', read_only=True)
    unit_cost = serializers.SerializerMethodField()
    cost = serializers.SerializerMethodField()

    class Meta:
        model = RecipeItem
        fields = ['ingredient_id', 'ingredient_name', 'quantity', 'unit', 'unit_cost', 'cost', 'memo']

    def get_unit_cost(self, obj):
        return obj.ingredient.unit_cost

    def get_cost(self, obj):
        return obj.cost


class MenuListSerializer(serializers.ModelSerializer):
    """메뉴 목록용 (가벼운 버전)"""
    food_cost = serializers.SerializerMethodField()
    food_cost_rate = serializers.SerializerMethodField()

    class Meta:
        model = Menu
        fields = [
            'menu_id', 'name', 'category', 'price',
            'monthly_orders', 'packaging_cost', 'is_active',
            'food_cost', 'food_cost_rate'
        ]

    def get_food_cost(self, obj):
        return obj.food_cost()

    def get_food_cost_rate(self, obj):
        return round(obj.food_cost_rate(), 4)


class MenuDetailSerializer(serializers.ModelSerializer):
    """메뉴 상세용"""
    food_cost = serializers.SerializerMethodField()
    food_cost_rate = serializers.SerializerMethodField()
    recipe_items = RecipeItemInlineSerializer(many=True, read_only=True)

    class Meta:
        model = Menu
        fields = [
            'menu_id', 'name', 'category', 'price',
            'monthly_orders', 'packaging_cost', 'is_active',
            'food_cost', 'food_cost_rate', 'recipe_items'
        ]

    def get_food_cost(self, obj):
        return obj.food_cost()

    def get_food_cost_rate(self, obj):
        return round(obj.food_cost_rate(), 4)


class ProfitAssumptionSerializer(serializers.ModelSerializer):
    """손익 가정"""

    class Meta:
        model = ProfitAssumption
        fields = [
            'label',
            'dine_in_share', 'delivery_share', 'takeout_share',
            'delivery_commission_rate', 'rider_fee', 'rider_fee_store_share',
            'target_food_cost_rate'
        ]


class MenuProfitSnapshotSerializer(serializers.ModelSerializer):
    """수익성 스냅샷"""
    signal_color = serializers.SerializerMethodField()
    menu = MenuListSerializer(read_only=True)

    class Meta:
        model = MenuProfitSnapshot
        fields = [
            'menu',
            'base_cost', 'food_cost_rate',
            'dine_in_margin', 'takeout_margin', 'delivery_margin',
            'weighted_margin', 'monthly_profit', 'monthly_revenue',
            'signal', 'signal_color', 'created_at'
        ]

    def get_signal_color(self, obj):
        return obj.signal_color


# ===== Write Serializers (CRUD) =====

class RecipeItemWriteSerializer(serializers.Serializer):
    """레시피 항목 작성용"""
    ingredient_id = serializers.CharField(max_length=50)
    quantity = serializers.FloatField()
    memo = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_ingredient_id(self, value):
        store = self.context.get("store")
        if not Ingredient.objects.filter(store=store, ingredient_id=value).exists():
            raise serializers.ValidationError(f"재료 '{value}'가 존재하지 않습니다.")
        return value

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("사용량은 0보다 커야 합니다.")
        return value


class MenuWriteSerializer(serializers.ModelSerializer):
    """메뉴 작성용 (인라인 레시피)"""
    recipe_items = RecipeItemWriteSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Menu
        fields = ['menu_id', 'name', 'category', 'price', 'monthly_orders', 'packaging_cost', 'is_active', 'recipe_items']

    def validate_recipe_items(self, value):
        ingredient_ids = [item["ingredient_id"] for item in value]
        if len(ingredient_ids) != len(set(ingredient_ids)):
            raise serializers.ValidationError("같은 재료를 중복해서 추가할 수 없습니다.")
        return value

    def validate_menu_id(self, value):
        store = self.context.get("store")
        query = Menu.objects.filter(store=store, menu_id=value)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError("이미 사용 중인 메뉴 ID입니다.")
        return value

    def create(self, validated_data):
        recipe_items_data = validated_data.pop('recipe_items', [])
        store = self.context["store"]
        menu = Menu.objects.create(store=store, **validated_data)
        for item_data in recipe_items_data:
            ingredient = Ingredient.objects.get(
                store=store,
                ingredient_id=item_data['ingredient_id'],
            )
            RecipeItem.objects.create(
                menu=menu,
                ingredient=ingredient,
                quantity=item_data['quantity'],
                memo=item_data.get('memo', '')
            )
        return menu

    def update(self, instance, validated_data):
        recipe_items_data = validated_data.pop('recipe_items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if recipe_items_data is not None:
            instance.recipe_items.all().delete()
            for item_data in recipe_items_data:
                ingredient = Ingredient.objects.get(
                    store=instance.store,
                    ingredient_id=item_data['ingredient_id'],
                )
                RecipeItem.objects.create(
                    menu=instance,
                    ingredient=ingredient,
                    quantity=item_data['quantity'],
                    memo=item_data.get('memo', '')
                )
        return instance


class IngredientWriteSerializer(serializers.ModelSerializer):
    """재료 작성용"""
    class Meta:
        model = Ingredient
        fields = ['ingredient_id', 'name', 'category', 'purchase_quantity', 'purchase_price', 'unit', 'is_hq_supplied', 'memo']

    def validate_purchase_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("구매 수량은 0보다 커야 합니다.")
        return value

    def validate_ingredient_id(self, value):
        store = self.context.get("store")
        query = Ingredient.objects.filter(store=store, ingredient_id=value)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError("이미 사용 중인 재료 ID입니다.")
        return value

    def create(self, validated_data):
        return Ingredient.objects.create(
            store=self.context["store"],
            **validated_data,
        )


class DailyMenuSaleWriteSerializer(serializers.Serializer):
    menu_id = serializers.CharField(max_length=50)
    sale_date = serializers.DateField()
    quantity = serializers.IntegerField(min_value=0)
    channel = serializers.ChoiceField(
        choices=DailyMenuSale.CHANNEL_CHOICES,
        default="ALL",
    )

    def validate_menu_id(self, value):
        store = self.context["store"]
        if not Menu.objects.filter(store=store, menu_id=value).exists():
            raise serializers.ValidationError("해당 매장의 메뉴가 아닙니다.")
        return value


class ProfitAssumptionWriteSerializer(serializers.ModelSerializer):
    """가정 작성용"""
    class Meta:
        model = ProfitAssumption
        fields = [
            'label', 'dine_in_share', 'delivery_share', 'takeout_share',
            'delivery_commission_rate', 'rider_fee', 'rider_fee_store_share',
            'target_food_cost_rate'
        ]

    def validate(self, attrs):
        instance = self.instance
        shares = [
            attrs.get("dine_in_share", getattr(instance, "dine_in_share", 0.50)),
            attrs.get("delivery_share", getattr(instance, "delivery_share", 0.30)),
            attrs.get("takeout_share", getattr(instance, "takeout_share", 0.20)),
        ]
        if any(share < 0 or share > 1 for share in shares):
            raise serializers.ValidationError("판매 비중은 0과 1 사이여야 합니다.")
        if abs(sum(shares) - 1.0) > 0.001:
            raise serializers.ValidationError("홀·배달·포장 판매 비중의 합은 1이어야 합니다.")

        rate_fields = ("delivery_commission_rate", "rider_fee_store_share", "target_food_cost_rate")
        for field in rate_fields:
            value = attrs.get(field, getattr(instance, field, None))
            if value is not None and not 0 <= value <= 1:
                raise serializers.ValidationError({field: "0과 1 사이의 값을 입력하세요."})
        return attrs
