import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import OnboardingProgress, Store, StoreMember
from profit.calculator import recalculate_all
from profit.models import (
    DailyMenuSale,
    Ingredient,
    Menu,
    MenuProfitSnapshot,
    ProfitAssumption,
    RecipeItem,
)


class Command(BaseCommand):
    help = "기존 샘플 데이터를 지정한 사장님 계정의 개인 매장으로 구성합니다."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--password", required=True)
        parser.add_argument(
            "--store-name",
            default="우동·돈까스 매장",
        )
        parser.add_argument(
            "--file",
            default=str(Path(settings.BASE_DIR) / "seed_data.json"),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        source_path = Path(options["file"]).resolve()
        if not source_path.is_file():
            raise CommandError(f"샘플 데이터 파일을 찾을 수 없습니다: {source_path}")

        with source_path.open(encoding="utf-8") as source:
            data = json.load(source)

        user_model = get_user_model()
        user, user_created = user_model.objects.get_or_create(
            username=options["username"]
        )
        user.set_password(options["password"])
        user.save(update_fields=["password"])

        membership = (
            StoreMember.objects.filter(user=user, is_active=True)
            .select_related("store")
            .first()
        )
        if membership:
            store = membership.store
            store.name = options["store_name"]
            store.business_type = "JAPANESE"
            store.save(update_fields=["name", "business_type", "updated_at"])
        else:
            store = Store.objects.create(
                name=options["store_name"],
                business_type="JAPANESE",
            )
            StoreMember.objects.create(store=store, user=user, role="OWNER")

        assumption, _ = ProfitAssumption.objects.update_or_create(
            store=store,
            defaults={
                **data["assumptions"],
                "owner": user,
                "label": "기본 운영 가정",
                "is_active": True,
            },
        )

        ingredient_map = {}
        for item in data["ingredients"]:
            ingredient, _ = Ingredient.objects.update_or_create(
                store=store,
                ingredient_id=item["ingredient_id"],
                defaults={
                    "name": item["name"],
                    "category": item.get("category", "기타"),
                    "purchase_quantity": item["purchase_quantity"],
                    "purchase_price": item["purchase_price"],
                    "unit": item.get("unit", "g"),
                    "memo": item.get("memo", ""),
                },
            )
            ingredient_map[ingredient.ingredient_id] = ingredient

        menu_map = {}
        for item in data["menus"]:
            menu, _ = Menu.objects.update_or_create(
                store=store,
                menu_id=item["menu_id"],
                defaults={
                    "name": item["menu_name"],
                    "category": item["category"],
                    "price": item["price"],
                    "monthly_orders": item["monthly_orders"],
                    "packaging_cost": item.get("packaging_cost", 0),
                    "is_active": True,
                },
            )
            menu_map[menu.menu_id] = menu

        RecipeItem.objects.filter(menu__in=menu_map.values()).delete()
        recipes = []
        for item in data["recipes"]:
            menu = menu_map.get(item["menu_id"])
            ingredient = ingredient_map.get(item["ingredient_id"])
            if menu is None or ingredient is None:
                raise CommandError(
                    "레시피 연결에 필요한 메뉴 또는 재료가 없습니다: "
                    f"{item['menu_id']} / {item['ingredient_id']}"
                )
            recipes.append(
                RecipeItem(
                    menu=menu,
                    ingredient=ingredient,
                    quantity=item["qty"],
                )
            )
        RecipeItem.objects.bulk_create(recipes)

        today = timezone.localdate()
        for menu in menu_map.values():
            DailyMenuSale.objects.update_or_create(
                store=store,
                menu=menu,
                sale_date=today,
                channel="ALL",
                defaults={"quantity": menu.monthly_orders},
            )

        OnboardingProgress.objects.update_or_create(
            store=store,
            defaults={
                "current_step": "COMPLETE",
                "store_completed": True,
                "ingredient_completed": True,
                "menu_completed": True,
                "recipe_completed": True,
                "sales_completed": True,
                "completed_at": timezone.now(),
            },
        )

        MenuProfitSnapshot.objects.filter(store=store).delete()
        snapshots = recalculate_all(assumption=assumption, store=store)

        account_status = "생성" if user_created else "갱신"
        self.stdout.write(
            self.style.SUCCESS(
                f"{options['username']} 계정 {account_status} 완료: "
                f"재료 {len(ingredient_map)}개, 메뉴 {len(menu_map)}개, "
                f"레시피 {len(recipes)}개, 분석 {len(snapshots)}개"
            )
        )
