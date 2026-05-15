"""
seed_data.json을 읽어서 DB에 한 번에 적재하고 즉시 재계산까지 실행.

사용법:
    python manage.py seed_data
    python manage.py seed_data --file=/path/to/other.json
    python manage.py seed_data --flush   # 기존 데이터 삭제 후 적재
"""
import json
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from profit.models import (
    Ingredient,
    Menu,
    RecipeItem,
    ProfitAssumption,
    MenuProfitSnapshot,
)
from profit.calculator import recalculate_all


class Command(BaseCommand):
    help = "seed_data.json을 읽어 모델에 적재하고 수익성을 재계산합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="seed_data.json",
            help="시드 파일 경로 (기본: 프로젝트 루트의 seed_data.json)",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="기존 Ingredient/Menu/RecipeItem/Snapshot을 모두 삭제하고 적재",
        )

    def handle(self, *args, **opts):
        path = Path(opts["file"])
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"파일을 찾을 수 없음: {path}"))
            return

        with path.open(encoding="utf-8") as f:
            data = json.load(f)

        with transaction.atomic():
            if opts["flush"]:
                self.stdout.write("기존 데이터 삭제 중...")
                MenuProfitSnapshot.objects.all().delete()
                RecipeItem.objects.all().delete()
                Menu.objects.all().delete()
                Ingredient.objects.all().delete()

            # 1. Assumptions (1개만 유지)
            ProfitAssumption.objects.update_or_create(
                label="기본 가정",
                defaults={**data["assumptions"], "is_active": True},
            )
            self.stdout.write(self.style.SUCCESS("✓ 손익 가정 적재"))

            # 2. Ingredients
            for item in data["ingredients"]:
                Ingredient.objects.update_or_create(
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
            self.stdout.write(
                self.style.SUCCESS(f"✓ 식자재 {len(data['ingredients'])}개 적재")
            )

            # 3. Menus
            for m in data["menus"]:
                Menu.objects.update_or_create(
                    menu_id=m["menu_id"],
                    defaults={
                        "name": m["menu_name"],
                        "category": m["category"],
                        "price": m["price"],
                        "monthly_orders": m["monthly_orders"],
                        "packaging_cost": m.get("packaging_cost", 0),
                        "is_active": True,
                    },
                )
            self.stdout.write(
                self.style.SUCCESS(f"✓ 메뉴 {len(data['menus'])}개 적재")
            )

            # 4. Recipes
            # 매핑 캐시
            ing_map = {i.ingredient_id: i for i in Ingredient.objects.all()}
            menu_map = {m.menu_id: m for m in Menu.objects.all()}

            # 같은 메뉴-재료 페어는 한 번만 등록 (unique_together)
            created_count = 0
            for r in data["recipes"]:
                menu = menu_map.get(r["menu_id"])
                ing = ing_map.get(r["ingredient_id"])
                if not menu or not ing:
                    self.stderr.write(
                        f"  경고: {r['menu_id']} / {r['ingredient_id']} 매핑 실패"
                    )
                    continue
                _, created = RecipeItem.objects.update_or_create(
                    menu=menu,
                    ingredient=ing,
                    defaults={"quantity": r["qty"]},
                )
                if created:
                    created_count += 1
            self.stdout.write(
                self.style.SUCCESS(f"✓ 레시피 {created_count}건 신규 등록")
            )

        # 5. 재계산 (외부 트랜잭션)
        self.stdout.write("\n수익성 재계산 중...")
        snaps = recalculate_all()
        self.stdout.write(
            self.style.SUCCESS(f"✓ 스냅샷 {len(snaps)}개 생성 완료")
        )
        self.stdout.write(
            self.style.SUCCESS("\n🎉 시드 완료. python manage.py runserver 로 확인하세요.")
        )
