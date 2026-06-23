"""
BOSSPROFIT REST API Serializers
"""
from rest_framework import serializers
from .models import Ingredient, Menu, RecipeItem, ProfitAssumption, MenuProfitSnapshot


class IngredientSerializer(serializers.ModelSerializer):
    """식자재 마스터"""
    unit_cost = serializers.SerializerMethodField()

    class Meta:
        model = Ingredient
        fields = [
            'ingredient_id', 'name', 'category',
            'purchase_quantity', 'purchase_price', 'unit',
            'memo', 'unit_cost'
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
        if not Ingredient.objects.filter(ingredient_id=value).exists():
            raise serializers.ValidationError(f"재료 '{value}'가 존재하지 않습니다.")
        return value


class MenuWriteSerializer(serializers.ModelSerializer):
    """메뉴 작성용 (인라인 레시피)"""
    recipe_items = RecipeItemWriteSerializer(many=True, required=False, write_only=True)

    class Meta:
        model = Menu
        fields = ['menu_id', 'name', 'category', 'price', 'monthly_orders', 'packaging_cost', 'is_active', 'recipe_items']

    def create(self, validated_data):
        recipe_items_data = validated_data.pop('recipe_items', [])
        menu = Menu.objects.create(**validated_data)
        for item_data in recipe_items_data:
            ingredient = Ingredient.objects.get(ingredient_id=item_data['ingredient_id'])
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
                ingredient = Ingredient.objects.get(ingredient_id=item_data['ingredient_id'])
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
        fields = ['ingredient_id', 'name', 'category', 'purchase_quantity', 'purchase_price', 'unit', 'memo']


class ProfitAssumptionWriteSerializer(serializers.ModelSerializer):
    """가정 작성용"""
    class Meta:
        model = ProfitAssumption
        fields = [
            'label', 'dine_in_share', 'delivery_share', 'takeout_share',
            'delivery_commission_rate', 'rider_fee', 'rider_fee_store_share',
            'target_food_cost_rate'
        ]
