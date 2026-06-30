from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import Field, ValidationError

from models import Attraction, ProviderResult, ProviderStatus, SourceEvidence, StrictModel


class POISearch(Protocol):
    def search_poi(self, keyword: str, *, city: str) -> ProviderResult:
        ...


class AttractionCandidate(StrictModel):
    name: str
    description: str
    source_url: str
    queried_at: datetime
    suggested_visit_minutes: int = Field(gt=0)
    ticket_price_cny: float | None = Field(default=None, ge=0)


class AttractionResolver:
    def __init__(self, amap: POISearch) -> None:
        self.amap = amap

    def resolve(
        self,
        candidates: list[AttractionCandidate],
        *,
        city: str,
    ) -> tuple[list[Attraction], list[str]]:
        attractions: list[Attraction] = []
        warnings: list[str] = []
        for candidate in candidates:
            result = self.amap.search_poi(candidate.name, city=city)
            if result.status is not ProviderStatus.OK or not result.records:
                warnings.append(f"AMap could not resolve: {candidate.name}")
                continue

            attraction = self._first_valid_attraction(candidate, result)
            if attraction is None:
                warnings.append(f"AMap returned invalid POI: {candidate.name}")
                continue
            attractions.append(attraction)
        return attractions, warnings

    def _first_valid_attraction(
        self,
        candidate: AttractionCandidate,
        result: ProviderResult,
    ) -> Attraction | None:
        for poi in result.records:
            try:
                return Attraction(
                    name=poi["name"],
                    description=candidate.description,
                    latitude=poi["latitude"],
                    longitude=poi["longitude"],
                    address=poi.get("address"),
                    ticket_price_cny=candidate.ticket_price_cny,
                    suggested_visit_minutes=candidate.suggested_visit_minutes,
                    evidence=self._evidence(candidate, result),
                )
            except (KeyError, ValidationError):
                continue
        return None

    def _evidence(
        self,
        candidate: AttractionCandidate,
        result: ProviderResult,
    ) -> list[SourceEvidence]:
        return [
            SourceEvidence(
                source="Xiaohongshu",
                source_url=candidate.source_url,
                queried_at=candidate.queried_at,
                confidence=0.65,
            ),
            SourceEvidence(
                source="AMap",
                source_url="https://lbs.amap.com/",
                queried_at=result.queried_at,
                confidence=0.9,
            ),
        ]
