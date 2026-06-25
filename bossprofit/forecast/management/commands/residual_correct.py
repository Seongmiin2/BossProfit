"""Residual Correction(Stage 3) 평가 보고 (항목 12).

    python manage.py residual_correct --item ONION --model-version last_value --horizon 7 \
        --test-start 2026-04-01 --min-improvement 0.03

저장된 OOF 잔차(항목 11)를 학습해 stage2 vs stage2+residual 을 비교하고,
개선이 게이트 미만이면 보정을 자동 비활성화한다.
"""
from datetime import date

from django.core.management.base import BaseCommand

from market.models import MarketItem
from forecast.residual_model import evaluate_item_residual


class Command(BaseCommand):
    help = "OOF 잔차로 Stage 3 보정을 평가하고 자동 비활성화를 판정합니다."

    def add_arguments(self, parser):
        parser.add_argument("--item", required=True)
        parser.add_argument("--model-version", default="last_value")
        parser.add_argument("--horizon", type=int, default=7)
        parser.add_argument("--test-start", required=True, help="YYYY-MM-DD")
        parser.add_argument("--min-improvement", type=float, default=0.03)

    def handle(self, *args, **opts):
        item = MarketItem.objects.filter(code=opts["item"]).first()
        if not item:
            self.stdout.write(self.style.ERROR(f"품목 {opts['item']} 없음"))
            return

        out = evaluate_item_residual(
            item, opts["model_version"], opts["horizon"],
            test_start=date.fromisoformat(opts["test_start"]),
            min_history=5, min_train_rows=8,
        )
        d = out.get("diagnostics", {})
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n[{item.code}/{opts['model_version']}] h{opts['horizon']} Stage 3 잔차 보정"
        ))
        self.stdout.write(
            f"  진단: n={d.get('n')} 평균편향={d.get('mean_bias')} "
            f"자기상관(lag1)={d.get('acf_lag1')}"
        )
        if not out.get("applied"):
            self.stdout.write(self.style.WARNING(f"  보정 미적용: {out.get('reason')}"))
            return

        gate = opts["min_improvement"]
        disabled = out["improvement"] < gate or out["improvement"] <= 0
        verdict = self.style.WARNING("비활성화(게이트 미달)") if disabled else self.style.SUCCESS("채택")
        self.stdout.write(
            f"  test n={out['n_test']} | stage2 WAPE={out['stage2_wape']:.4f} "
            f"→ +residual WAPE={out['raw_corrected_wape']:.4f} "
            f"(개선 {out['improvement']*100:+.1f}%) | 게이트 {gate*100:.0f}% → "
        )
        self.stdout.write(f"  판정: {verdict}")
