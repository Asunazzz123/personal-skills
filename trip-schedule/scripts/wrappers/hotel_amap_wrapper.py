from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

import requests


AMAP_SOURCE_URL = "https://lbs.amap.com/"


def _redact(message: str) -> str:
    key = os.getenv("AMAP_WEBSERVICE_KEY")
    if key:
        message = message.replace(key, "[redacted]")
    return message[-1000:]


def _fail(message: str, *, code: int = 2) -> None:
    print(_redact(message), file=sys.stderr)
    raise SystemExit(code)


def _require_key() -> str:
    key = os.getenv("AMAP_WEBSERVICE_KEY")
    if not key:
        _fail("AMAP_WEBSERVICE_KEY is required for hotel AMap wrapper.")
    return key


def _limit() -> int:
    try:
        return max(1, min(25, int(os.getenv("TRIP_HOTEL_LIMIT", "10"))))
    except ValueError:
        return 10


def _price_overrides() -> dict[str, float]:
    raw = os.getenv("TRIP_HOTEL_PRICE_OVERRIDES")
    if not raw:
        return {}
    path = Path(raw).expanduser()
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    prices = {}
    for name, value in payload.items():
        try:
            prices[str(name)] = float(value)
        except (TypeError, ValueError):
            continue
    return prices


def _rating(poi: dict[str, Any]) -> float | None:
    raw = None
    biz_ext = poi.get("biz_ext")
    if isinstance(biz_ext, dict):
        raw = biz_ext.get("rating")
    if raw in (None, "", []):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _review_count(poi: dict[str, Any]) -> int | None:
    for key in ("review_count", "comment_count"):
        raw = poi.get(key)
        if raw in (None, "", []):
            continue
        try:
            return int(str(raw).replace(",", ""))
        except ValueError:
            continue
    return None


def _coordinates(poi: dict[str, Any]) -> tuple[float, float] | None:
    location = poi.get("location")
    if not isinstance(location, str):
        return None
    try:
        longitude, latitude = location.split(",", maxsplit=1)
        return float(longitude), float(latitude)
    except (TypeError, ValueError):
        return None


def _normalize_poi(
    poi: dict[str, Any],
    *,
    prices: dict[str, float],
) -> dict[str, Any] | None:
    name = poi.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    coordinates = _coordinates(poi)
    if coordinates is None:
        return None
    longitude, latitude = coordinates
    return {
        "name": name.strip(),
        "latitude": latitude,
        "longitude": longitude,
        "address": poi.get("address") or None,
        "total_price_cny": prices.get(name.strip()),
        "rating": _rating(poi),
        "review_count": _review_count(poi),
        "transit_notes": [
            "AMap hotel POI candidate; verify live room price separately."
        ],
        "source": "AMap",
        "source_url": AMAP_SOURCE_URL,
    }


def fetch_hotels(*, request: dict[str, Any]) -> list[dict[str, Any]]:
    key = _require_key()
    destination = str(request.get("destination", "")).strip()
    if not destination:
        _fail("request.destination is required for hotel AMap wrapper.")
    keywords = f"{destination} 酒店"
    response = requests.get(
        "https://restapi.amap.com/v3/place/text",
        params={
            "key": key,
            "keywords": keywords,
            "city": destination,
            "citylimit": "true",
            "offset": _limit(),
            "types": "100000",
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        _fail("AMap hotel response JSON schema changed.")
    if payload.get("status") != "1":
        _fail(f"AMap hotel query failed: {payload.get('info', 'unknown error')}")
    pois = payload.get("pois", [])
    if not isinstance(pois, list):
        _fail("AMap hotel response pois must be a list.")
    prices = _price_overrides()
    rows = []
    for poi in pois:
        if not isinstance(poi, dict):
            continue
        row = _normalize_poi(poi, prices=prices)
        if row is not None:
            rows.append(row)
    return rows[: _limit()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", required=True)
    args = parser.parse_args(argv)
    request = json.loads(args.request_json)
    rows = fetch_hotels(request=request)
    print(json.dumps(rows, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
