from django.utils import timezone

from .models import OnboardingProgress


def refresh_onboarding_progress(store):
    """매장 데이터 상태를 기준으로 온보딩 진행도를 갱신한다."""
    progress, _ = OnboardingProgress.objects.get_or_create(store=store)
    ingredient_exists = store.ingredients.exists()
    menu_exists = store.menus.exists()
    recipe_exists = store.menus.filter(recipe_items__isnull=False).exists()

    progress.ingredient_completed = ingredient_exists
    progress.menu_completed = menu_exists
    progress.recipe_completed = recipe_exists
    progress.sales_completed = store.daily_sales.exists()

    if not ingredient_exists:
        progress.current_step = "INGREDIENT"
    elif not menu_exists:
        progress.current_step = "MENU"
    elif not recipe_exists:
        progress.current_step = "RECIPE"
    elif not progress.sales_completed:
        progress.current_step = "SALES"
    else:
        progress.current_step = "COMPLETE"
        progress.completed_at = progress.completed_at or timezone.now()

    progress.save()
    return progress
