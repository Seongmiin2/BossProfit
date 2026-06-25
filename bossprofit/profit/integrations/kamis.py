import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from .base import ExternalApiError, fetch_json


KAMIS_PRICE_URL = "https://www.kamis.or.kr/service/price/xml.do"


def fetch_daily_price_by_category(
    *,
    regday,
    category_code="200",
    country_code="1101",
    product_class_code="01",
):
    cert_key = os.environ.get("KAMIS_CERT_KEY")
    cert_id = os.environ.get("KAMIS_CERT_ID")
    if not cert_key or not cert_id:
        raise ExternalApiError("KAMIS_CERT_KEY와 KAMIS_CERT_ID가 필요합니다.")
    params = {
        "action": "dailyPriceByCategoryList",
        "p_cert_key": cert_key,
        "p_cert_id": cert_id,
        "p_returntype": "json",
        "p_product_cls_code": product_class_code,
        "p_item_category_code": category_code,
        "p_country_code": country_code,
        "p_regday": regday.isoformat(),
        "p_convert_kg_yn": "N",
    }
    payload, url = fetch_json(KAMIS_PRICE_URL, params)
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("error_code") not in (None, "000"):
        raise ExternalApiError(
            f"KAMIS 오류: {data.get('error_code') if isinstance(data, dict) else 'INVALID'}"
        )
    return payload, url, params


def fetch_period_product(
    *,
    start_date,
    end_date,
    category_code,
    item_code,
    kind_code,
    rank_code,
    country_code="1101",
    product_class_code="01",
):
    cert_key = os.environ.get("KAMIS_CERT_KEY")
    cert_id = os.environ.get("KAMIS_CERT_ID")
    if not cert_key or not cert_id:
        raise ExternalApiError("KAMIS_CERT_KEY와 KAMIS_CERT_ID가 필요합니다.")
    params = {
        "action": "periodProductList",
        "p_cert_key": cert_key,
        "p_cert_id": cert_id,
        "p_returntype": "json",
        "p_startday": start_date.isoformat(),
        "p_endday": end_date.isoformat(),
        "p_productclscode": product_class_code,
        "p_itemcategorycode": category_code,
        "p_itemcode": item_code,
        "p_kindcode": kind_code,
        "p_productrankcode": rank_code,
        "p_countrycode": country_code,
        "p_convert_kg_yn": "N",
    }
    payload, url = fetch_json(KAMIS_PRICE_URL, params, timeout=60)
    data = payload.get("data")
    if not isinstance(data, dict) or data.get("error_code") not in (None, "000"):
        raise ExternalApiError(
            f"KAMIS 오류: {data.get('error_code') if isinstance(data, dict) else 'INVALID'}"
        )
    return payload, url, params


def parse_price(value):
    if value in (None, "", "-", "0"):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except InvalidOperation:
        return None


def parse_month_day(value, as_of_date):
    if not value:
        return None
    normalized = str(value).replace(".", "/").replace("-", "/")
    match = re.search(r"(?:(\d{4})/)?(\d{1,2})/(\d{1,2})", normalized)
    if not match:
        return None
    explicit_year, month, day = match.groups()
    month, day = int(month), int(day)
    if explicit_year:
        return date(int(explicit_year), month, day)
    year = as_of_date.year - 1 if month > as_of_date.month + 1 else as_of_date.year
    return date(year, month, day)


def iter_daily_prices(payload, as_of_date):
    items = payload.get("data", {}).get("item", [])
    if isinstance(items, dict):
        items = [items]
    for item in items:
        for index in range(1, 8):
            observed_date = parse_month_day(item.get(f"day{index}"), as_of_date)
            price = parse_price(item.get(f"dpr{index}"))
            if observed_date and price is not None:
                yield item, observed_date, price


def iter_period_prices(payload):
    items = payload.get("data", {}).get("item", [])
    if isinstance(items, dict):
        items = [items]
    for item in items:
        if item.get("countyname") != "평균":
            continue
        year = item.get("yyyy")
        regday = item.get("regday")
        price = parse_price(item.get("price"))
        if not year or not regday or price is None:
            continue
        month, day = map(int, str(regday).split("/"))
        yield item, date(int(year), month, day), price
