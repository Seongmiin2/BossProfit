"""
추이(시계열) 차트용 과거 스냅샷을 백데이트로 생성한다.

seed_data는 재계산을 한 번만 호출해 모든 스냅샷이 '오늘' 한 시점에 몰린다.
그러면 /history 차트에 점이 하나뿐이라 선이 그려지지 않는다.
이 명령은 지난 N일간의 일별 스냅샷을 메뉴별 완만한 변동과 함께 만들어
추이 차트·대시보드 시계열을 의미 있게 만든다.

사용법:
    python manage.py seed_history                 # 최근 90일(데모 매장)
    python manage.py seed_history --days 30
    python manage.py seed_history --append         # 기존 스냅샷 유지(기본은 삭제 후 생성)
    python manage.py seed_history --owner=조윤     # 특정 계정 매장에만 생성

스냅샷은 계산식으로 재생성 가능한 파생 데이터라 기본적으로 기존 것을 비우고 다시 만든다.
"""
import math
import random
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from profit.models import Menu, ProfitAssumption, MenuProfitSnapshot
from profit.calculator import calculate_menu


def _classify(food_cost_rate, delivery_margin, weighted_margin, orders, avg_orders, target):
    """calculator.classify와 동일한 규칙(일별 주문량 기준)."""
    if delivery_margin < 0 and weighted_margin < 0:
        return "🔴 배달 손실"
    high_sales = orders >= avg_orders
    low_cost = food_cost_rate <= target
    if high_sales and low_cost:
        return "🟢 간판 메뉴"
    if high_sales and not low_cost:
        return "🟡 손해 보는 베스트셀러"
    if not high_sales and low_cost:
        return "🟡 숨은 효자"
    return "🔴 정리 검토"


class Command(BaseCommand):
    help = "추이 차트용 과거 일별 스냅샷을 백데이트로 생성합니다."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90, help="생성할 일수 (기본 90)")
        parser.add_argument("--append", action="store_true", help="기존 스냅샷을 지우지 않고 추가")
        parser.add_argument("--seed", type=int, default=42, help="난수 시드(재현용)")
        parser.add_argument("--owner", default=None, help="대상 계정(username). 미지정 시 매장 전체")

    def handle(self, *args, **opts):
        days = max(opts["days"], 1)
        rng = random.Random(opts["seed"])

        # 대상 매장 한정(멀티테넌트): --owner 지정 시 그 계정의 매장에만 적용
        store = None
        if opts["owner"]:
            User = get_user_model()
            try:
                owner = User.objects.get(username=opts["owner"])
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"계정을 찾을 수 없음: {opts['owner']}"))
                return
            store = owner.owned_stores.order_by("id").first()
            if store is None:
                self.stderr.write(self.style.ERROR(f"{owner.username}의 매장이 없습니다. 먼저 seed_data를 실행하세요."))
                return

        menu_qs = Menu.objects.filter(is_active=True)
        if store is not None:
            menu_qs = menu_qs.filter(store=store)
        menus = list(menu_qs.prefetch_related("recipe_items__ingredient"))
        if not menus:
            self.stderr.write(self.style.ERROR("활성 메뉴가 없습니다. 먼저 seed_data를 실행하세요."))
            return

        assumption = ProfitAssumption.get_active(store=store)
        target = assumption.target_food_cost_rate

        # 메뉴별 기준 계산값 + 고정 위상(파형이 메뉴마다 다르게)
        base = {}
        for m in menus:
            res = calculate_menu(m, assumption)
            base[m.pk] = {
                "base_cost": res["base_cost"],
                "orders": m.monthly_orders,
                "cost_phase": (hash(m.menu_id) % 360) * math.pi / 180,
                "order_phase": (hash(m.menu_id + "o") % 360) * math.pi / 180,
            }

        commission_unit = assumption.delivery_commission_rate
        rider = assumption.rider_fee * assumption.rider_fee_store_share
        ds, dvs, ts = assumption.dine_in_share, assumption.delivery_share, assumption.takeout_share

        today = timezone.localdate()

        with transaction.atomic():
            if not opts["append"]:
                snap_qs = MenuProfitSnapshot.objects.all()
                if store is not None:
                    snap_qs = snap_qs.filter(menu__store=store)
                deleted = snap_qs.count()
                snap_qs.delete()
                self.stdout.write(f"기존 스냅샷 {deleted}개 삭제")

            total = 0
            # 오래된 날짜부터 생성
            for offset in range(days - 1, -1, -1):
                day = today - timedelta(days=offset)
                t = (days - 1 - offset) / max(days - 1, 1)  # 0(과거) → 1(오늘)

                day_rows = []
                for m in menus:
                    b = base[m.pk]
                    # 완만한 파형(계절성) + 소량 노이즈
                    cost_mult = 1 + 0.06 * math.sin(2 * math.pi * 1.5 * t + b["cost_phase"]) + rng.uniform(-0.02, 0.02)
                    order_mult = 1 + 0.12 * math.sin(2 * math.pi * t + b["order_phase"]) + rng.uniform(-0.05, 0.05)

                    base_cost_d = max(b["base_cost"] * cost_mult, 0)
                    orders_d = max(int(round(b["orders"] * order_mult)), 0)
                    price = m.price

                    dine_in = price - base_cost_d
                    takeout = price - base_cost_d - m.packaging_cost
                    delivery = price - base_cost_d - m.packaging_cost - price * commission_unit - rider
                    weighted = dine_in * ds + delivery * dvs + takeout * ts
                    fcr = (base_cost_d / price) if price else 0.0

                    day_rows.append({
                        "menu": m,
                        "orders": orders_d,
                        "base_cost": round(base_cost_d, 2),
                        "food_cost_rate": round(fcr, 4),
                        "dine_in_margin": round(dine_in, 2),
                        "takeout_margin": round(takeout, 2),
                        "delivery_margin": round(delivery, 2),
                        "weighted_margin": round(weighted, 2),
                        "monthly_profit": round(weighted * orders_d, 2),
                        "monthly_revenue": round(price * orders_d, 2),
                    })

                avg_orders = sum(r["orders"] for r in day_rows) / len(day_rows)
                pks = []
                for r in day_rows:
                    signal = _classify(
                        r["food_cost_rate"], r["delivery_margin"], r["weighted_margin"],
                        r["orders"], avg_orders, target,
                    )
                    snap = MenuProfitSnapshot.objects.create(
                        menu=r["menu"],
                        base_cost=r["base_cost"],
                        food_cost_rate=r["food_cost_rate"],
                        dine_in_margin=r["dine_in_margin"],
                        takeout_margin=r["takeout_margin"],
                        delivery_margin=r["delivery_margin"],
                        weighted_margin=r["weighted_margin"],
                        monthly_profit=r["monthly_profit"],
                        monthly_revenue=r["monthly_revenue"],
                        signal=signal,
                    )
                    pks.append(snap.pk)

                # auto_now_add 우회: 생성 후 created_at을 해당 일자(09:00)로 소급
                dt = timezone.make_aware(datetime.combine(day, time(9, 0)))
                MenuProfitSnapshot.objects.filter(pk__in=pks).update(created_at=dt)
                total += len(pks)

        self.stdout.write(self.style.SUCCESS(
            f"✓ {days}일 × 메뉴 {len(menus)}개 = 스냅샷 {total}개 생성 완료 ({today - timedelta(days=days-1)} ~ {today})"
        ))
