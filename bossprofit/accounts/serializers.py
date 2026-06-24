from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Store, StoreMember, OnboardingProgress


class RegisterSerializer(serializers.Serializer):
    """회원가입"""
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=6)
    password2 = serializers.CharField(write_only=True, min_length=6)

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError("비밀번호가 일치하지 않습니다.")
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError("이미 존재하는 사용자명입니다.")
        return data

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password']
        )
        return user


class UserSerializer(serializers.ModelSerializer):
    """사용자 정보"""
    store = serializers.SerializerMethodField()
    onboarding = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'store', 'onboarding']

    def get_store(self, obj):
        membership = (
            obj.store_memberships.filter(is_active=True)
            .select_related("store")
            .first()
        )
        if not membership:
            return None
        store = membership.store
        return {
            "id": store.id,
            "name": store.name,
            "business_type": store.business_type,
            "business_type_label": store.get_business_type_display(),
            "region": store.region,
            "role": membership.role,
        }

    def get_onboarding(self, obj):
        membership = (
            obj.store_memberships.filter(is_active=True)
            .select_related("store")
            .first()
        )
        if not membership:
            return {
                "has_store": False,
                "current_step": "STORE",
                "is_complete": False,
            }
        progress, _ = OnboardingProgress.objects.get_or_create(
            store=membership.store
        )
        return OnboardingProgressSerializer(progress).data


class StoreCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["name", "business_type", "region"]

    def create(self, validated_data):
        user = self.context["request"].user
        if user.store_memberships.filter(is_active=True).exists():
            raise serializers.ValidationError("이미 연결된 매장이 있습니다.")
        store = Store.objects.create(**validated_data)
        StoreMember.objects.create(store=store, user=user, role="OWNER")
        OnboardingProgress.objects.create(store=store)
        return store


class StoreSerializer(serializers.ModelSerializer):
    business_type_label = serializers.CharField(
        source="get_business_type_display",
        read_only=True,
    )

    class Meta:
        model = Store
        fields = [
            "id",
            "name",
            "business_type",
            "business_type_label",
            "region",
        ]


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["username", "email"]

    def validate_username(self, value):
        queryset = User.objects.filter(username=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("이미 사용 중인 사용자명입니다.")
        return value


class StoreUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Store
        fields = ["name", "business_type", "region"]


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=6)
    new_password2 = serializers.CharField(write_only=True, min_length=6)

    def validate_current_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("현재 비밀번호가 올바르지 않습니다.")
        return value

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password2"]:
            raise serializers.ValidationError(
                {"new_password2": "새 비밀번호가 일치하지 않습니다."}
            )
        return attrs

    def save(self, **kwargs):
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


class OnboardingProgressSerializer(serializers.ModelSerializer):
    has_store = serializers.SerializerMethodField()
    is_complete = serializers.SerializerMethodField()
    completed_steps = serializers.SerializerMethodField()
    total_steps = serializers.IntegerField(default=5, read_only=True)

    class Meta:
        model = OnboardingProgress
        fields = [
            "has_store",
            "current_step",
            "is_complete",
            "completed_steps",
            "total_steps",
            "store_completed",
            "ingredient_completed",
            "menu_completed",
            "recipe_completed",
            "sales_completed",
        ]

    def get_has_store(self, obj):
        return True

    def get_is_complete(self, obj):
        return obj.current_step == "COMPLETE"

    def get_completed_steps(self, obj):
        return sum([
            obj.store_completed,
            obj.ingredient_completed,
            obj.menu_completed,
            obj.recipe_completed,
            obj.sales_completed,
        ])
