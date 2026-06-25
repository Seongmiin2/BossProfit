import os

from .base import ExternalApiError, fetch_json, fetch_xml


ASOS_DAILY_URL = (
    "https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
)
SHORT_FORECAST_URL = (
    "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
)
MID_LAND_FORECAST_URL = (
    "https://apis.data.go.kr/1360000/MidFcstInfoService/getMidLandFcst"
)
WHOLESALE_AUCTION_URL = (
    "https://apis.data.go.kr/B552845/katRealTime2/trades2"
)
AGRI_PLPD_BASE_URL = (
    "https://apis.data.go.kr/1390802/AgriWeather/WeatherObsrInfo/frcPlpd"
)


def service_key():
    key = os.environ.get("DATA_GO_KR_SERVICE_KEY")
    if not key:
        raise ExternalApiError("DATA_GO_KR_SERVICE_KEY가 필요합니다.")
    return key


def fetch_asos_daily(*, station_id, start_date, end_date):
    params = {
        "serviceKey": service_key(),
        "pageNo": 1,
        "numOfRows": 999,
        "dataType": "JSON",
        "dataCd": "ASOS",
        "dateCd": "DAY",
        "startDt": start_date.strftime("%Y%m%d"),
        "endDt": end_date.strftime("%Y%m%d"),
        "stnIds": station_id,
    }
    payload, url = fetch_json(ASOS_DAILY_URL, params)
    return payload, url, params


def fetch_short_forecast(*, base_date, base_time, nx, ny):
    params = {
        "serviceKey": service_key(),
        "pageNo": 1,
        "numOfRows": 1000,
        "dataType": "JSON",
        "base_date": base_date.strftime("%Y%m%d"),
        "base_time": base_time,
        "nx": nx,
        "ny": ny,
    }
    payload, url = fetch_json(SHORT_FORECAST_URL, params)
    return payload, url, params


def fetch_mid_land_forecast(*, region_id, issued_at):
    params = {
        "serviceKey": service_key(),
        "pageNo": 1,
        "numOfRows": 100,
        "dataType": "JSON",
        "regId": region_id,
        "tmFc": issued_at.strftime("%Y%m%d%H%M"),
    }
    payload, url = fetch_json(MID_LAND_FORECAST_URL, params)
    return payload, url, params


def fetch_wholesale_auctions(
    *,
    trade_date,
    page=1,
    rows=1000,
    market_code=None,
    large_code=None,
    middle_code=None,
    small_code=None,
):
    params = {
        "serviceKey": service_key(),
        "pageNo": page,
        "numOfRows": rows,
        "returnType": "json",
        "cond[trd_clcln_ymd::EQ]": trade_date.isoformat(),
    }
    filters = {
        "cond[whsl_mrkt_cd::EQ]": market_code,
        "cond[gds_lclsf_cd::EQ]": large_code,
        "cond[gds_mclsf_cd::EQ]": middle_code,
        "cond[gds_sclsf_cd::EQ]": small_code,
    }
    params.update({key: value for key, value in filters.items() if value})
    payload, url = fetch_json(WHOLESALE_AUCTION_URL, params, timeout=60)
    return payload, url, params


def fetch_agri_crop_stations(*, crop_code, page=1, rows=100):
    params = {
        "serviceKey": service_key(),
        "Page_No": page,
        "Page_Size": rows,
        "frc_Code": crop_code,
    }
    payload, url = fetch_xml(
        f"{AGRI_PLPD_BASE_URL}/getWeatherPlpdObsrCodeList",
        params,
    )
    return payload, url, params


def fetch_agri_crop_daily(
    *,
    crop_code,
    station_code,
    start_date,
    end_date,
    page=1,
    rows=400,
):
    params = {
        "serviceKey": service_key(),
        "Page_No": page,
        "Page_Size": rows,
        "frc_Code": crop_code,
        "obsr_Spot_Code": station_code,
        "begin_Date": start_date.strftime("%Y%m%d"),
        "end_Date": end_date.strftime("%Y%m%d"),
    }
    payload, url = fetch_xml(
        f"{AGRI_PLPD_BASE_URL}/getWeatherPlpdDayList",
        params,
    )
    return payload, url, params


def xml_response_items(payload):
    response = payload.get("response", {})
    header = response.get("header", {})
    if str(header.get("result_Code")) != "200":
        raise ExternalApiError(
            f"농업기상 오류 {header.get('result_Code')}: "
            f"{header.get('result_Msg', '')}"
        )
    items = response.get("body", {}).get("items", {}).get("item", [])
    if isinstance(items, dict):
        return [items]
    return items or []


def response_items(payload):
    response = payload.get("response", {})
    header = response.get("header", {})
    if header.get("resultCode") not in (None, "0", "00"):
        raise ExternalApiError(
            f"공공데이터포털 오류 {header.get('resultCode')}: "
            f"{header.get('resultMsg', '')}"
        )
    items = response.get("body", {}).get("items", {}).get("item", [])
    if isinstance(items, dict):
        return [items]
    return items or []
