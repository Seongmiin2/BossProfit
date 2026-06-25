"""KAMIS 일별 가격 수집 클라이언트.

클라이언트 책임:
- 외부 소스에서 raw 행을 가져와 '표준단위당 가격'으로 정규화한 dict 리스트를 반환한다.
- 네트워크/파싱 실패는 예외 대신 빈 결과 또는 명시적 신호로 다룬다(상위 run이 부분성공 판정).

반환 행 스키마(정규화 완료):
    {
        "observation_date": "2026-06-20",   # ISO date
        "region": "서울",                    # 선택
        "market_type": "retail",             # retail | wholesale
        "grade": "상",                       # 선택
        "unit": "g",                         # 표준단위
        "price": "12.3400",                  # 표준단위당 가격(문자열 Decimal 권장)
        "raw_ref": "kamis:daily:...",        # 원본 참조
    }
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Iterable, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError

from django.conf import settings


class BaseKamisDailyClient:
    source = "kamis"

    def fetch_daily(self, item, start: date, end: date) -> list[dict]:  # pragma: no cover
        raise NotImplementedError


class FixtureKamisDailyClient(BaseKamisDailyClient):
    """API 키 없이 동작하는 fixture 기반 클라이언트.

    fixture 파일은 다음 형태의 JSON:
        { "<source_item_code>": [ {정규화 행}, ... ], ... }
    또는 item.code 키도 허용한다. 날짜 범위 [start, end]로 필터링한다.
    """

    def __init__(self, fixture_path: str | Path | None = None, data: dict | None = None):
        if data is not None:
            self._data = data
        else:
            path = Path(fixture_path) if fixture_path else self._default_path()
            with open(path, encoding="utf-8") as f:
                self._data = json.load(f)

    @staticmethod
    def _default_path() -> Path:
        return Path(__file__).resolve().parent.parent / "fixtures" / "kamis_daily_sample.json"

    def _rows_for(self, item) -> Iterable[dict]:
        # source_item_code 우선, 없으면 표준 code로 조회
        return self._data.get(item.source_item_code) or self._data.get(item.code) or []

    def fetch_daily(self, item, start: date, end: date) -> list[dict]:
        out = []
        for row in self._rows_for(item):
            d = date.fromisoformat(row["observation_date"])
            if start <= d <= end:
                out.append(row)
        return out


def _kamis_price(raw) -> Optional[str]:
    """KAMIS 가격 문자열('2,311')을 Decimal 문자열로. '-'/빈값/0은 None."""
    if raw is None or isinstance(raw, (list, dict)):
        return None
    s = str(raw).replace(",", "").strip()
    if not s or s in ("-", "0"):
        return None
    try:
        return str(float(s))
    except ValueError:
        return None


class KamisApiDailyClient(BaseKamisDailyClient):
    """실제 KAMIS Open API 클라이언트 (periodProductList).

    settings.KAMIS_CERT_KEY/ID 가 설정돼야 동작한다. periodProductList 로
    기간 일별 가격 시계열을 한 번에 받아 표준 정규화 행으로 반환한다.
    KAMIS는 https + 브라우저 UA만 응답한다(http/기본 UA는 차단).
    """

    BASE_URL = "https://www.kamis.or.kr/service/price/xml.do"
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
    )

    def __init__(self, cert_key: str | None = None, cert_id: str | None = None):
        self.cert_key = cert_key or getattr(settings, "KAMIS_CERT_KEY", "")
        self.cert_id = cert_id or getattr(settings, "KAMIS_CERT_ID", "")

    def fetch_daily(self, item, start: date, end: date) -> list[dict]:
        if not (self.cert_key and self.cert_id):
            return []
        if not (item.source_category_code and item.source_item_code):
            return []

        params = {
            "action": "periodProductList",
            "p_cert_key": self.cert_key,
            "p_cert_id": self.cert_id,
            "p_returntype": "json",
            "p_startday": start.strftime("%Y-%m-%d"),
            "p_endday": end.strftime("%Y-%m-%d"),
            "p_itemcategorycode": item.source_category_code,
            "p_itemcode": item.source_item_code,
            "p_productrankcode": "04",        # 상품
            "p_countrycode": "1101",          # 서울(평균)
            "p_convert_kg_yn": "Y",           # 1kg 환산가
            "p_productclscode": "01",         # 01 소매
        }
        if item.source_kind_code:
            params["p_kindcode"] = item.source_kind_code

        url = f"{self.BASE_URL}?{urlencode(params)}"
        req = Request(url, headers={"User-Agent": self.USER_AGENT})
        try:
            with urlopen(req, timeout=15) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (URLError, ValueError, TimeoutError, OSError):
            return []

        data = payload.get("data")
        if not isinstance(data, dict) or data.get("error_code") not in ("000", 0):
            return []
        items = data.get("item")
        if isinstance(items, dict):
            items = [items]
        if not items:
            return []

        out = []
        for it in items:
            yyyy, regday = it.get("yyyy"), it.get("regday")
            price = _kamis_price(it.get("price"))
            if not yyyy or not regday or price is None or "/" not in str(regday):
                continue
            mm, dd = str(regday).split("/")
            out.append({
                "observation_date": f"{yyyy}-{int(mm):02d}-{int(dd):02d}",
                "region": "",
                "market_type": "retail",
                "grade": "",
                "unit": item.standard_unit,
                "price": price,
                "raw_ref": f"kamis:period:{item.source_item_code}:{yyyy}-{mm}-{dd}",
            })
        return out


def get_daily_client() -> BaseKamisDailyClient:
    """설정에 따라 클라이언트 선택. 키가 있으면 실 API, 없으면 fixture."""
    cert_key = getattr(settings, "KAMIS_CERT_KEY", "")
    cert_id = getattr(settings, "KAMIS_CERT_ID", "")
    if cert_key and cert_id:
        return KamisApiDailyClient(cert_key, cert_id)
    return FixtureKamisDailyClient()
