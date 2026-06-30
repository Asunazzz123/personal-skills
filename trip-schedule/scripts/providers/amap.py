from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import requests

from models import ProviderHealth, ProviderResult, ProviderStatus
from providers.base import Provider


class AMapProvider(Provider):
    provider_id = "amap-webservice"

    def __init__(self) -> None:
        self.key = os.getenv("AMAP_WEBSERVICE_KEY")
        self.session = requests.Session()

    def health_check(self) -> ProviderHealth:
        if not self.key:
            return ProviderHealth(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                detail="AMAP_WEBSERVICE_KEY is not set",
            )
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.OK,
            detail="Web Service key configured",
        )

    def query(self, request: object) -> ProviderResult:
        if not isinstance(request, str):
            raise TypeError("AMapProvider.query expects an address string")
        return self.geocode(request)

    def geocode(self, address: str, *, city: str | None = None) -> ProviderResult:
        queried_at = datetime.now().astimezone()
        if not self.key:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                queried_at=queried_at,
                records=[],
            )
        payload, error = self._request_json(
            "https://restapi.amap.com/v3/geocode/geo",
            params={"key": self.key, "address": address, "city": city or ""},
            queried_at=queried_at,
        )
        if error is not None:
            return error
        if payload.get("status") != "1":
            raw_info = str(payload.get("info", "unknown AMap error"))
            info = self._sanitize_message(raw_info)
            status = (
                ProviderStatus.AUTHENTICATION_FAILED
                if "KEY" in raw_info or "SCODE" in raw_info
                else ProviderStatus.NETWORK_ERROR
            )
            return ProviderResult(
                provider_id=self.provider_id,
                status=status,
                queried_at=queried_at,
                records=[],
                warnings=[info],
                error_kind="amap_error",
            )
        records = []
        warnings = []
        geocodes = payload.get("geocodes", [])
        if not isinstance(geocodes, list):
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.SCHEMA_CHANGED,
                queried_at=queried_at,
                records=[],
                warnings=["AMap geocode response contained invalid geocode rows"],
                error_kind="invalid_geocode_fields",
            )
        for item in geocodes:
            record = self._normalize_geocode(item)
            if record is None:
                warnings.append("Skipped AMap geocode row with invalid location")
            else:
                records.append(record)
        status = ProviderStatus.OK if records else ProviderStatus.NO_RESULTS
        error_kind = None
        if geocodes and not records:
            status = ProviderStatus.SCHEMA_CHANGED
            error_kind = "invalid_geocode_fields"
        return ProviderResult(
            provider_id=self.provider_id,
            status=status,
            queried_at=queried_at,
            records=records,
            warnings=warnings,
            error_kind=error_kind,
        )

    def search_poi(self, keyword: str, *, city: str) -> ProviderResult:
        queried_at = datetime.now().astimezone()
        if not self.key:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                queried_at=queried_at,
                records=[],
            )

        payload, error = self._request_json(
            "https://restapi.amap.com/v3/place/text",
            params={
                "key": self.key,
                "keywords": keyword,
                "city": city,
                "citylimit": "true",
                "offset": 5,
            },
            queried_at=queried_at,
        )
        if error is not None:
            return error
        if payload.get("status") != "1":
            info = self._sanitize_message(str(payload.get("info", "unknown AMap error")))
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NETWORK_ERROR,
                queried_at=queried_at,
                records=[],
                warnings=[info],
                error_kind="amap_error",
            )

        records = []
        pois = payload.get("pois", [])
        if not isinstance(pois, list):
            pois = []
        for item in pois:
            record = self._normalize_poi(item, keyword)
            if record is not None:
                records.append(record)
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.OK if records else ProviderStatus.NO_RESULTS,
            queried_at=queried_at,
            records=records,
        )

    def route_transit(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        *,
        city: str,
    ) -> ProviderResult:
        return self._route(
            "https://restapi.amap.com/v3/direction/transit/integrated",
            origin,
            destination,
            candidate_keys=("transits", "paths"),
            extra={"city": city, "strategy": 0},
        )

    def route_driving(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> ProviderResult:
        return self._route(
            "https://restapi.amap.com/v3/direction/driving",
            origin,
            destination,
            candidate_keys=("paths", "transits"),
            extra={"strategy": 0},
        )

    def _route(
        self,
        url: str,
        origin: tuple[float, float],
        destination: tuple[float, float],
        *,
        candidate_keys: tuple[str, ...],
        extra: dict[str, object],
    ) -> ProviderResult:
        queried_at = datetime.now().astimezone()
        if not self.key:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                queried_at=queried_at,
                records=[],
            )

        payload, error = self._request_json(
            url,
            params={
                "key": self.key,
                "origin": self._format_coordinate(origin),
                "destination": self._format_coordinate(destination),
                **extra,
            },
            queried_at=queried_at,
        )
        if error is not None:
            return error
        if payload.get("status") != "1":
            info = self._sanitize_message(str(payload.get("info", "unknown AMap error")))
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NETWORK_ERROR,
                queried_at=queried_at,
                records=[],
                warnings=[info],
                error_kind="amap_error",
            )

        candidates = self._route_candidates(payload, candidate_keys)
        if not candidates:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.SCHEMA_CHANGED,
                queried_at=queried_at,
                records=[],
                warnings=["AMap route response did not contain route candidates"],
                error_kind="missing_route_candidates",
            )

        candidate = candidates[0]
        if not isinstance(candidate, dict):
            return self._invalid_route_fields(queried_at)

        try:
            distance_meters = int(candidate["distance"])
            duration_seconds = int(candidate["duration"])
            estimated_cost_cny = float(candidate.get("cost") or 0)
        except (KeyError, TypeError, ValueError):
            return self._invalid_route_fields(queried_at)

        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.OK,
            queried_at=queried_at,
            records=[
                {
                    "distance_meters": distance_meters,
                    "duration_minutes": max(1, round(duration_seconds / 60)),
                    "estimated_cost_cny": estimated_cost_cny,
                    "path": self._route_path(candidate, origin, destination),
                }
            ],
        )

    def _invalid_route_fields(self, queried_at: datetime) -> ProviderResult:
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.SCHEMA_CHANGED,
            queried_at=queried_at,
            records=[],
            warnings=["AMap route response contained invalid route fields"],
            error_kind="invalid_route_fields",
        )

    def _request_json(
        self,
        url: str,
        *,
        params: dict[str, object],
        queried_at: datetime,
    ) -> tuple[dict[str, Any], ProviderResult | None]:
        try:
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
        except requests.Timeout:
            return (
                {},
                ProviderResult(
                    provider_id=self.provider_id,
                    status=ProviderStatus.NETWORK_ERROR,
                    queried_at=queried_at,
                    records=[],
                    warnings=["AMap request timed out"],
                    error_kind="amap_timeout",
                ),
            )
        except requests.RequestException:
            return (
                {},
                ProviderResult(
                    provider_id=self.provider_id,
                    status=ProviderStatus.NETWORK_ERROR,
                    queried_at=queried_at,
                    records=[],
                    warnings=["AMap request failed"],
                    error_kind="amap_request_error",
                ),
            )

        try:
            payload = response.json()
        except ValueError:
            return (
                {},
                ProviderResult(
                    provider_id=self.provider_id,
                    status=ProviderStatus.SCHEMA_CHANGED,
                    queried_at=queried_at,
                    records=[],
                    warnings=["AMap response was not valid JSON"],
                    error_kind="amap_invalid_json",
                ),
            )

        if not isinstance(payload, dict):
            return (
                {},
                ProviderResult(
                    provider_id=self.provider_id,
                    status=ProviderStatus.SCHEMA_CHANGED,
                    queried_at=queried_at,
                    records=[],
                    warnings=["AMap response JSON schema changed"],
                    error_kind="amap_schema_changed",
                ),
            )
        return payload, None

    def _normalize_geocode(self, item: object) -> dict[str, object] | None:
        if not isinstance(item, dict):
            return None
        location = item.get("location")
        if not isinstance(location, str):
            return None
        try:
            longitude, latitude = location.split(",", maxsplit=1)
            return {
                "formatted_address": item.get("formatted_address"),
                "longitude": float(longitude),
                "latitude": float(latitude),
            }
        except (TypeError, ValueError):
            return None

    def _normalize_poi(self, item: object, keyword: str) -> dict[str, object] | None:
        if not isinstance(item, dict):
            return None
        location = item.get("location")
        if not isinstance(location, str):
            return None
        try:
            longitude, latitude = location.split(",", maxsplit=1)
            return {
                "name": item.get("name") or keyword,
                "address": item.get("address") or None,
                "longitude": float(longitude),
                "latitude": float(latitude),
            }
        except (TypeError, ValueError):
            return None

    def _sanitize_message(self, message: str) -> str:
        if self.key:
            return message.replace(self.key, "[redacted]")
        return message

    def _route_candidates(
        self,
        payload: dict[str, Any],
        candidate_keys: tuple[str, ...],
    ) -> list[Any]:
        route = payload.get("route")
        if not isinstance(route, dict):
            return []
        for key in candidate_keys:
            candidates = route.get(key)
            if isinstance(candidates, list) and candidates:
                return candidates
        return []

    def _route_path(
        self,
        candidate: dict[str, Any],
        origin: tuple[float, float],
        destination: tuple[float, float],
    ) -> list[list[float]]:
        points: list[list[float]] = []
        steps = candidate.get("steps")
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                polyline = step.get("polyline")
                if not isinstance(polyline, str):
                    continue
                points.extend(self._parse_polyline(polyline))
        if len(points) >= 2:
            return points
        return [list(origin), list(destination)]

    def _parse_polyline(self, polyline: str) -> list[list[float]]:
        points = []
        for raw_point in polyline.split(";"):
            if not raw_point:
                continue
            try:
                longitude, latitude = raw_point.split(",", maxsplit=1)
                points.append([float(longitude), float(latitude)])
            except (TypeError, ValueError):
                continue
        return points

    def _format_coordinate(self, coordinate: tuple[float, float]) -> str:
        return f"{coordinate[0]},{coordinate[1]}"
