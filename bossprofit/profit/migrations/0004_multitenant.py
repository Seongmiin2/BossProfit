"""멀티테넌트 도입: Store/StoreMember 추가 및 매장 데이터의 store 귀속.

기존 데모 데이터(재료·메뉴·손익가정)는 데모 유저 소유의 데모 매장으로 이관해
한 줄도 유실하지 않는다. 적용 순서:
  1) Store/StoreMember 생성
  2) Ingredient/Menu에 store(nullable) 추가, ProfitAssumption.owner → store 교체
  3) 데모 매장 생성 후 기존 행 backfill
  4) store NOT NULL + (store, *_id) unique 제약 적용
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


DEMO_OWNER_USERNAME = "demo_owner"
DEMO_STORE_NAME = "우동·돈까스 매장"


def backfill_demo_store(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL.split(".")[0], settings.AUTH_USER_MODEL.split(".")[1])
    Store = apps.get_model("profit", "Store")
    StoreMember = apps.get_model("profit", "StoreMember")
    Ingredient = apps.get_model("profit", "Ingredient")
    Menu = apps.get_model("profit", "Menu")
    ProfitAssumption = apps.get_model("profit", "ProfitAssumption")

    has_legacy = (
        Ingredient.objects.exists()
        or Menu.objects.exists()
        or ProfitAssumption.objects.exists()
    )
    if not has_legacy:
        return

    owner = User.objects.filter(username=DEMO_OWNER_USERNAME).first()
    if owner is None:
        # 기존 슈퍼유저가 있으면 그 사람을 데모 매장 소유자로, 없으면 데모 유저 생성
        owner = User.objects.filter(is_superuser=True).order_by("id").first()
    if owner is None:
        owner = User.objects.create(
            username=DEMO_OWNER_USERNAME,
            is_active=True,
        )

    store = Store.objects.create(
        owner=owner,
        name=DEMO_STORE_NAME,
        business_type="외식업",
        region="",
    )
    StoreMember.objects.get_or_create(
        store=store, user=owner, defaults={"role": "OWNER"}
    )

    Ingredient.objects.filter(store__isnull=True).update(store=store)
    Menu.objects.filter(store__isnull=True).update(store=store)
    ProfitAssumption.objects.filter(store__isnull=True).update(store=store)


def noop_reverse(apps, schema_editor):
    # 되돌릴 때는 store 컬럼 자체가 제거되므로 별도 데이터 작업 불필요
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("profit", "0003_ingredientpricehistory"),
    ]

    operations = [
        # 1) Store / StoreMember
        migrations.CreateModel(
            name="Store",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, verbose_name="매장명")),
                ("business_type", models.CharField(blank=True, max_length=50, verbose_name="업종")),
                ("region", models.CharField(blank=True, max_length=50, verbose_name="지역")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="owned_stores", to=settings.AUTH_USER_MODEL, verbose_name="소유자")),
            ],
            options={
                "verbose_name": "매장",
                "verbose_name_plural": "매장",
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="StoreMember",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("OWNER", "사장"), ("MANAGER", "매니저"), ("STAFF", "직원")], default="OWNER", max_length=20, verbose_name="역할")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("store", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="members", to="profit.store")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="store_memberships", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "매장 구성원",
                "verbose_name_plural": "매장 구성원",
                "unique_together": {("store", "user")},
            },
        ),
        # 2) store(nullable) 컬럼 추가 + unique 해제
        migrations.AddField(
            model_name="ingredient",
            name="store",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name="ingredients", to="profit.store", verbose_name="매장"),
        ),
        migrations.AddField(
            model_name="menu",
            name="store",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name="menus", to="profit.store", verbose_name="매장"),
        ),
        migrations.AlterField(
            model_name="ingredient",
            name="ingredient_id",
            field=models.CharField(help_text="예: PORK_LOIN_G (매장 내 고유)", max_length=50),
        ),
        migrations.AlterField(
            model_name="menu",
            name="menu_id",
            field=models.CharField(help_text="예: M001 (매장 내 고유)", max_length=50),
        ),
        # ProfitAssumption.owner → store
        migrations.RemoveField(
            model_name="profitassumption",
            name="owner",
        ),
        migrations.AddField(
            model_name="profitassumption",
            name="store",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="assumptions", to="profit.store", verbose_name="매장"),
        ),
        # 3) 데모 매장 backfill
        migrations.RunPython(backfill_demo_store, noop_reverse),
        # 4) NOT NULL + 매장 스코프 unique
        migrations.AlterField(
            model_name="ingredient",
            name="store",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ingredients", to="profit.store", verbose_name="매장"),
        ),
        migrations.AlterField(
            model_name="menu",
            name="store",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="menus", to="profit.store", verbose_name="매장"),
        ),
        migrations.AlterUniqueTogether(
            name="ingredient",
            unique_together={("store", "ingredient_id")},
        ),
        migrations.AlterUniqueTogether(
            name="menu",
            unique_together={("store", "menu_id")},
        ),
    ]
