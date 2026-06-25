import hashlib
import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


class ExternalApiError(RuntimeError):
    pass


def fetch_json(base_url, params, *, timeout=45, retries=2):
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "BOSSPROFIT/0.1 (+market-data-ingestion)",
        },
    )
    last_error = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
                return payload, url
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise ExternalApiError(str(last_error)) from last_error


def _xml_element_to_value(element):
    children = list(element)
    if not children:
        return element.text
    grouped = {}
    for child in children:
        value = _xml_element_to_value(child)
        if child.tag in grouped:
            if not isinstance(grouped[child.tag], list):
                grouped[child.tag] = [grouped[child.tag]]
            grouped[child.tag].append(value)
        else:
            grouped[child.tag] = value
    return grouped


def fetch_xml(base_url, params, *, timeout=60, retries=2):
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "BOSSPROFIT/0.1 (+agri-weather-ingestion)"},
    )
    last_error = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                root = ET.fromstring(response.read())
                payload = {root.tag: _xml_element_to_value(root)}
                return payload, url
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise ExternalApiError(str(last_error)) from last_error


def payload_sha256(payload):
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def redact_params(params):
    secret_keys = {"serviceKey", "p_cert_key", "p_cert_id", "apiKey"}
    return {
        key: ("***" if key in secret_keys else value)
        for key, value in params.items()
    }
