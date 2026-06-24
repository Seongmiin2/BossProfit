from django.db import models
from django.conf import settings


class Store(models.Model):
    """사용자가 운영하는 매장."""

    BUSINESS_TYPE_CHOICES = [
        ("KOREAN", "한식"),
        ("WESTERN", "양식"),
        ("JAPANESE", "일식"),
        ("CHINESE", "중식"),
        ("CAFE", "카페·디저트"),
        ("SNACK", "분식"),
        ("OTHER", "기타"),
    ]

    name = models.CharField(max_length=100, verbose_name="매장명")
    business_type = models.CharField(
        max_length=20,
        choices=BUSINESS_TYPE_CHOICES,
        default="OTHER",
        verbose_name="업종",
    )
    region = models.CharField(max_length=100, blank=True, verbose_name="지역")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class StoreMember(models.Model):
    """매장 구성원과 권한."""

    ROLE_CHOICES = [
        ("OWNER", "소유자"),
        ("MANAGER", "관리자"),
        ("STAFF", "직원"),
    ]

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="store_memberships",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="OWNER")
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["store", "user"],
                name="unique_store_member",
            ),
        ]

    def __str__(self):
        return f"{self.store.name} / {self.user.username} / {self.role}"


class OnboardingProgress(models.Model):
    """최초 매장 설정의 단계별 진행 상태."""

    STEP_CHOICES = [
        ("STORE", "매장 등록"),
        ("INGREDIENT", "첫 재료 등록"),
        ("MENU", "첫 메뉴 등록"),
        ("RECIPE", "레시피 구성"),
        ("SALES", "판매 데이터 입력"),
        ("COMPLETE", "첫 분석 완료"),
    ]

    store = models.OneToOneField(
        Store,
        on_delete=models.CASCADE,
        related_name="onboarding",
    )
    current_step = models.CharField(
        max_length=20,
        choices=STEP_CHOICES,
        default="INGREDIENT",
    )
    store_completed = models.BooleanField(default=True)
    ingredient_completed = models.BooleanField(default=False)
    menu_completed = models.BooleanField(default=False)
    recipe_completed = models.BooleanField(default=False)
    sales_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.store.name} / {self.current_step}"
