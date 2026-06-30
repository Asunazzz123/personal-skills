from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import requests

from providers.train_support.station_index import StationIndex


SEAT_INDEXES = {
    "business_class": 32,
    "special_class": 25,
    "first_class": 31,
    "second_class": 30,
    "soft_sleeper": 23,
    "hard_sleeper": 28,
    "hard_seat": 29,
    "no_seat": 26,
}


def _seat_value(parts: list[str], index: int) -> str | None:
    if index >= len(parts) or parts[index] in {"", "无", "--"}:
        return None
    return parts[index]


def parse_query_response(
    payload: dict[str, Any],
    *,
    query_date: str,
) -> list[dict[str, Any]]:
    data = payload.get("data", {})
    if not isinstance(data, dict):
        raise ValueError("12306 response data must be an object")
    station_map = data.get("map", {})
    if not isinstance(station_map, dict):
        raise ValueError("12306 response data.map must be an object")
    raw_results = data.get("result", [])
    if not isinstance(raw_results, list):
        raise ValueError("12306 response data.result must be a list")
    rows: list[dict[str, Any]] = []
    for raw in raw_results:
        if not isinstance(raw, str):
            raise ValueError("12306 response result rows must be strings")
        parts = raw.split("|")
        if len(parts) < 33:
            continue
        departure = datetime.fromisoformat(f"{query_date}T{parts[8]}:00+08:00")
        hours, minutes = (int(value) for value in parts[10].split(":"))
        duration_minutes = hours * 60 + minutes
        arrival = departure + timedelta(minutes=duration_minutes)
        rows.append(
            {
                "service_id": parts[3],
                "origin_name": station_map.get(parts[6], parts[6]),
                "destination_name": station_map.get(parts[7], parts[7]),
                "departure_at": departure.isoformat(),
                "arrival_at": arrival.isoformat(),
                "duration_minutes": duration_minutes,
                "total_price_cny": None,
                "availability": {
                    name: value
                    for name, index in SEAT_INDEXES.items()
                    if (value := _seat_value(parts, index)) is not None
                },
            }
        )
    if raw_results and not rows:
        raise ValueError("12306 response contained no parseable result rows")
    return rows


class TicketClient:
    """Small read-only client for one 12306 availability query."""

    def __init__(self, station_index: StationIndex) -> None:
        self.station_index = station_index
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Referer": "https://kyfw.12306.cn/otn/leftTicket/init",
                "Host": "kyfw.12306.cn",
            }
        )
        self._cookies_initialized = False

    def _ensure_cookies(self) -> None:
        if self._cookies_initialized:
            return
        response = self.session.get(
            "https://kyfw.12306.cn/otn/leftTicket/init",
            timeout=15,
        )
        response.raise_for_status()
        self._cookies_initialized = True

    def query(
        self,
        *,
        origin_station: str,
        destination_station: str,
        travel_date: str,
    ) -> dict[str, Any]:
        params = {
            "leftTicketDTO.train_date": travel_date,
            "leftTicketDTO.from_station": self.station_index.code_for(
                origin_station
            ),
            "leftTicketDTO.to_station": self.station_index.code_for(
                destination_station
            ),
            "purpose_codes": "ADULT",
        }
        self._ensure_cookies()
        query_url = "https://kyfw.12306.cn/otn/leftTicket/queryG"
        for attempt in range(2):
            response = self.session.get(query_url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
            redirect_path = payload.get("c_url")
            if not redirect_path:
                return payload
            if attempt == 1:
                raise RuntimeError("12306 returned repeated c_url redirects")
            query_url = f"https://kyfw.12306.cn/otn/{redirect_path}"
        raise RuntimeError("12306 query did not return a result")
