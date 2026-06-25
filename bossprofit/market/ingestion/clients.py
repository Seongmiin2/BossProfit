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
from typing import Iterable

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


class KamisApiDailyClient(BaseKamisDailyClient):
    """실제 KAMIS Open API 클라이언트.

    settings.KAMIS_CERT_KEY/ID 가 설정돼야 동작한다. 응답 파싱은 기존
    profit.market_price 의 검증된 헬퍼를 재사용한다. (MVP: 일자별 단일 조회를
    범위만큼 반복; 호출량은 상위 run의 파라미터로 제어)
    """

    BASE_URL = "https://www.kamis.or.kr/service/price/xml.do?action=dailyPriceByCategoryList"

    def __init__(self, cert_key: str | None = None, cert_id: str | None = None):
        self.cert_key = cert_key or getattr(settings, "KAMIS_CERT_KEY", "")
        self.cert_id = cert_id or getattr(settings, "KAMIS_CERT_ID", "")

    def fetch_daily(self, item, start: date, end: date) -> list[dict]:
        if not (self.cert_key and self.cert_id):
            return []
        # 실제 호출 로직은 별도 티켓(B-02 확장)에서 구현. 여기서는 인터페이스만 고정.
        # 데모/테스트는 FixtureKamisDailyClient를 사용한다.
        return []


def get_daily_client() -> BaseKamisDailyClient:
    """설정에 따라 클라이언트 선택. 키가 있으면 실 API, 없으면 fixture."""
    cert_key = getattr(settings, "KAMIS_CERT_KEY", "")
    cert_id = getattr(settings, "KAMIS_CERT_ID", "")
    if cert_key and cert_id:
        return KamisApiDailyClient(cert_key, cert_id)
    return FixtureKamisDailyClient()
