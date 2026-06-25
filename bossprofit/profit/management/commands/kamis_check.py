"""
KAMIS Open API 연결 확인 및 품목/품종 코드 조회 명령.

사용 예:
    python manage.py kamis_check --category 200            # 채소류 오늘 시세
    python manage.py kamis_check --category 500 --date 2026-06-20
    python manage.py kamis_check --category 200 --cls 02   # 도매

부류코드: 100 식량작물 / 200 채소류 / 300 특용작물 / 400 과일류 / 500 축산물 / 600 수산물

출력된 item_code / kind_code 를 settings.KAMIS_ITEM_MAP 에 채워 넣으면
실제 시세 연동이 활성화된다.
"""
import json
from datetime import date
from urllib.parse import urlencode
from urllib.request import urlopen
from urllib.error import URLError

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

BASE_URL = "http://www.kamis.or.kr/service/price/xml.do"


class Command(BaseCommand):
    help = "KAMIS API 연결 확인 및 부류별 품목/품종 코드 조회"

    def add_arguments(self, parser):
        parser.add_argument("--category", default="200", help="부류코드 (기본 200 채소류)")
        parser.add_argument("--date", default=None, help="조회일 YYYY-MM-DD (기본: 오늘)")
        parser.add_argument("--cls", default="01", help="구분 01 소매(기본) / 02 도매")
        parser.add_argument("--country", default="1101", help="지역코드 (기본 1101 서울)")

    def handle(self, *args, **options):
        cert_key = getattr(settings, "KAMIS_CERT_KEY", "")
        cert_id = getattr(settings, "KAMIS_CERT_ID", "")
        if not (cert_key and cert_id):
            raise CommandError(
                "KAMIS_CERT_KEY / KAMIS_CERT_ID 환경변수가 설정되지 않았습니다.\n"
                "  예) set KAMIS_CERT_KEY=... && set KAMIS_CERT_ID=...  (Windows)\n"
                "      export KAMIS_CERT_KEY=... KAMIS_CERT_ID=...      (bash)"
            )

        regday = options["date"] or date.today().isoformat()
        params = {
            "action": "dailyPriceByCategoryList",
            "p_cert_key": cert_key,
            "p_cert_id": cert_id,
            "p_returntype": "json",
            "p_product_cls_code": options["cls"],
            "p_country_code": options["country"],
            "p_regday": regday,
            "p_convert_kg_yn": "Y",
            "p_item_category_code": options["category"],
        }
        url = f"{BASE_URL}?{urlencode(params)}"
        self.stdout.write(f"요청: 부류 {options['category']} / {regday} / 구분 {options['cls']}")

        try:
            with urlopen(url, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except URLError as e:
            raise CommandError(f"네트워크 오류: {e}")
        except ValueError as e:
            raise CommandError(f"응답 파싱 오류(JSON 아님): {e}")

        data = payload.get("data")
        if not isinstance(data, dict):
            raise CommandError(
                f"API 오류 응답: {payload!r}\n"
                "인증키/요청자ID가 올바른지, 해당 날짜 데이터가 있는지 확인하세요."
            )

        items = data.get("item")
        if isinstance(items, dict):
            items = [items]
        if not items:
            self.stdout.write(self.style.WARNING("해당 조건에 품목이 없습니다(휴장일 등)."))
            return

        self.stdout.write(self.style.SUCCESS(f"✓ 연결 성공 — {len(items)}개 품목"))
        self.stdout.write("-" * 72)
        self.stdout.write(f"{'item_code':>9}  {'kind_code':>9}  {'dpr1':>10}  품목/품종")
        self.stdout.write("-" * 72)
        for it in items:
            if not isinstance(it, dict):
                continue
            item_code = it.get("item_code", it.get("productno", ""))
            kind_code = it.get("kind_code", "")
            price = it.get("dpr1", "-")
            name = f"{it.get('item_name', '')} / {it.get('kind_name', '')}".strip(" /")
            self.stdout.write(f"{item_code:>9}  {kind_code:>9}  {str(price):>10}  {name}")
