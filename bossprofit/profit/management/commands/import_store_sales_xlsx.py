from collections import defaultdict
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.models import OnboardingProgress, Store, StoreMember
from profit.models import DailyMenuSale, Menu, StoreSalesImport
from profit.sales_import import parse_pos_workbook, sha256_file, summarize_product_prices


class Command(BaseCommand):
    help = "POS 상품-일자별 Excel을 특정 사용자의 매장 판매 데이터로 가져옵니다."

    def add_arguments(self, parser):
        parser.add_argument("files", nargs="+")
        parser.add_argument("--username", required=True)
        parser.add_argument("--store-name", default="한신우동 수원세류점")
        parser.add_argument("--region", default="경기 수원시 권선구")
        parser.add_argument("--replace-sales", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        user = get_user_model().objects.filter(username=options["username"]).first()
        if user is None:
            raise CommandError(f"사용자를 찾을 수 없습니다: {options['username']}")

        membership = (
            StoreMember.objects.filter(user=user, is_active=True)
            .select_related("store")
            .first()
        )
        if membership:
            store = membership.store
            store.name = options["store_name"]
            store.region = options["region"]
            store.business_type = "JAPANESE"
            store.save(update_fields=["name", "region", "business_type", "updated_at"])
        else:
            store = Store.objects.create(
                name=options["store_name"],
                region=options["region"],
                business_type="JAPANESE",
            )
            StoreMember.objects.create(store=store, user=user, role="OWNER")

        if options["replace_sales"]:
            DailyMenuSale.objects.filter(store=store).delete()
            StoreSalesImport.objects.filter(store=store).delete()

        total_rows = 0
        imported_rows = 0
        all_rows = []
        imports = []
        for raw_path in options["files"]:
            path = Path(raw_path).resolve()
            if not path.is_file():
                raise CommandError(f"파일을 찾을 수 없습니다: {path}")
            digest = sha256_file(path)
            if StoreSalesImport.objects.filter(
                store=store,
                source_sha256=digest,
            ).exists():
                self.stdout.write(self.style.WARNING(f"이미 가져온 파일 건너뜀: {path.name}"))
                continue
            source_import = StoreSalesImport.objects.create(
                store=store,
                source_name=path.name,
                source_sha256=digest,
            )
            try:
                rows = parse_pos_workbook(path)
            except Exception as exc:
                source_import.status = "FAILED"
                source_import.error_message = str(exc)
                source_import.finished_at = timezone.now()
                source_import.save(
                    update_fields=["status", "error_message", "finished_at"]
                )
                raise CommandError(str(exc)) from exc
            source_import.row_count = len(rows)
            imports.append((source_import, rows))
            all_rows.extend(rows)
            total_rows += len(rows)

        product_prices = summarize_product_prices(all_rows)
        product_rows = {}
        for row in all_rows:
            product_rows[row.product_code] = row

        menu_map = {}
        Menu.objects.filter(store=store).update(is_active=False)
        for code, sample in product_rows.items():
            menu, _ = Menu.objects.update_or_create(
                store=store,
                menu_id=code,
                defaults={
                    "name": sample.product_name,
                    "category": sample.category,
                    "price": product_prices.get(code, 0),
                    "is_active": True,
                },
            )
            menu_map[code] = menu

        combined_daily = defaultdict(lambda: [0, 0, 0, 0])
        for source_import, rows in imports:
            daily = defaultdict(lambda: [0, 0, 0, 0])
            for row in rows:
                values = daily[(row.product_code, row.sale_date)]
                values[0] += row.quantity
                values[1] += row.gross_revenue
                values[2] += row.discount_amount
                values[3] += row.net_revenue
                combined = combined_daily[(row.product_code, row.sale_date)]
                combined[0] += row.quantity
                combined[1] += row.gross_revenue
                combined[2] += row.discount_amount
                combined[3] += row.net_revenue
            source_import.status = "SUCCEEDED"
            source_import.imported_count = len(daily)
            source_import.finished_at = timezone.now()
            source_import.save(
                update_fields=[
                    "status",
                    "row_count",
                    "imported_count",
                    "finished_at",
                ]
            )

        for (code, sale_date), values in combined_daily.items():
            DailyMenuSale.objects.update_or_create(
                store=store,
                menu=menu_map[code],
                sale_date=sale_date,
                channel="ALL",
                defaults={
                    "quantity": values[0],
                    "gross_revenue": values[1],
                    "discount_amount": values[2],
                    "net_revenue": values[3],
                    "source_import": None,
                },
            )
            imported_rows += 1

        recent_start = timezone.localdate() - timedelta(days=29)
        for menu in menu_map.values():
            recent_quantity = (
                DailyMenuSale.objects.filter(
                    store=store,
                    menu=menu,
                    sale_date__gte=recent_start,
                ).aggregate(total=Sum("quantity"))["total"]
                or 0
            )
            menu.monthly_orders = recent_quantity
            menu.save(update_fields=["monthly_orders"])

        OnboardingProgress.objects.update_or_create(
            store=store,
            defaults={
                "current_step": "COMPLETE",
                "store_completed": True,
                "menu_completed": bool(menu_map),
                "sales_completed": bool(imported_rows),
                "completed_at": timezone.now() if imported_rows else None,
            },
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"{store.name}: 원본 {total_rows}행, 일별 판매 {imported_rows}건, "
                f"메뉴 {len(menu_map)}개를 {options['username']} 계정에 연결했습니다."
            )
        )
