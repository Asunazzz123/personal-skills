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
        response = self.session.get(
            "https://restapi.amap.com/v3/geocode/geo",
            params={"key": self.key, "address": address, "city": city or ""},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "1":
            info = str(payload.get("info", "unknown AMap error"))
            status = (
                ProviderStatus.AUTHENTICATION_FAILED
                if "KEY" in info or "SCODE" in info
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
        for item in payload.get("geocodes", []):
            longitude, latitude = item["location"].split(",", maxsplit=1)
            records.append(
                {
                    "formatted_address": item.get("formatted_address"),
                    "longitude": float(longitude),
                    "latitude": float(latitude),
                }
            )
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

        response = self.session.get(
            url,
            params={
                "key": self.key,
                "origin": self._format_coordinate(origin),
                "destination": self._format_coordinate(destination),
                **extra,
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "1":
            info = str(payload.get("info", "unknown AMap error"))
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
            except ValueError:
                continue
        return points

    def _format_coordinate(self, coordinate: tuple[float, float]) -> str:
        return f"{coordinate[0]},{coordinate[1]}"
