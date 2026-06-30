from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import product
from pathlib import Path
from typing import Protocol

from models import ProviderResult, ProviderStatus, TripRequest
from planning.attraction_resolver import AttractionCandidate, AttractionResolver
from providers.flight import FlightProvider, FlightQuery
from providers.hotels import HotelProvider, HotelQuery
from providers.train_12306 import Train12306Provider, TrainQuery
from providers.xhs import XhsEvidenceProvider, XhsQuery


class QueryProvider(Protocol):
    def query(self, request: object) -> ProviderResult:
        ...


@dataclass(frozen=True)
class ResearchDependencies:
    train: Train12306Provider
    flight: FlightProvider
    xhs: XhsEvidenceProvider
    hotels: HotelProvider
    attraction_resolver: AttractionResolver


def combine_results(
    provider_id: str,
    attempts: list[ProviderResult],
) -> ProviderResult:
    queried_at = datetime.now().astimezone()
    records = [record for attempt in attempts for record in attempt.records]
    warnings = [warning for attempt in attempts for warning in attempt.warnings]
    if records:
        status = ProviderStatus.OK
    elif attempts:
        status = attempts[-1].status
    else:
        status = ProviderStatus.NOT_CONFIGURED
    return ProviderResult(
        provider_id=provider_id,
        status=status,
        queried_at=queried_at,
        records=records,
        warnings=warnings,
        error_kind=attempts[-1].error_kind if attempts else None,
    )


class DefaultResearchPipeline:
    def __init__(
        self,
        dependencies: ResearchDependencies,
        *,
        attraction_candidates_path: Path,
    ) -> None:
        self.dependencies = dependencies
        self.attraction_candidates_path = attraction_candidates_path

    def collect(self, request: TripRequest) -> dict[str, ProviderResult]:
        departure_date = request.departure_at.date()
        results: dict[str, ProviderResult] = {}

        train_attempts: list[ProviderResult] = []
        origins = self.dependencies.train.stations_for_city(request.origin_city)[:3]
        destinations = self.dependencies.train.stations_for_city(
            request.destination
        )[:3]
        for origin, destination in product(origins, destinations):
            result = self.dependencies.train.query(
                TrainQuery(
                    origin_station=origin,
                    destination_station=destination,
                    travel_date=departure_date,
                )
            )
            train_attempts.append(result)
            if result.records:
                break
        results["transport-train"] = combine_results(
            "transport-train",
            train_attempts,
        )

        flight_attempts: list[ProviderResult] = []
        origin_airports = self.dependencies.flight.resolve_airports(
            request.origin_city
        )[:3]
        destination_airports = self.dependencies.flight.resolve_airports(
            request.destination
        )[:3]
        for origin, destination in product(origin_airports, destination_airports):
            flight_attempts.append(
                self.dependencies.flight.query(
                    FlightQuery(
                        origin_iata=origin,
                        destination_iata=destination,
                        departure_date=departure_date,
                        travelers=request.travelers,
                    )
                )
            )
        results["transport-flight"] = combine_results(
            "transport-flight",
            flight_attempts,
        )

        xhs_result = self.dependencies.xhs.query(
            XhsQuery(destination=request.destination)
        )
        results["evidence-xhs"] = xhs_result
        nights = max(1, request.duration_days - 1)
        results["hotels-external"] = self.dependencies.hotels.query(
            HotelQuery(
                destination=request.destination,
                check_in=departure_date,
                check_out=departure_date + timedelta(days=nights),
                travelers=request.travelers,
            )
        )
        results["attractions-resolved"] = self._resolve_attractions(
            request.destination,
            allowed_source_urls={
                str(record.get("source_url"))
                for record in xhs_result.records
                if record.get("source_url")
            },
        )
        return results

    def _resolve_attractions(
        self,
        city: str,
        *,
        allowed_source_urls: set[str],
    ) -> ProviderResult:
        queried_at = datetime.now().astimezone()
        if not self.attraction_candidates_path.is_file():
            return ProviderResult(
                provider_id="attractions-resolved",
                status=ProviderStatus.NOT_CONFIGURED,
                queried_at=queried_at,
                records=[],
                warnings=[
                    "Create attraction_candidates.json from sourced media evidence."
                ],
            )
        payload = json.loads(
            self.attraction_candidates_path.read_text(encoding="utf-8")
        )
        candidates = []
        rejected = []
        for item in payload:
            candidate = AttractionCandidate.model_validate(item)
            if candidate.source_url not in allowed_source_urls:
                rejected.append(candidate.source_url)
                continue
            candidates.append(candidate)
        attractions, warnings = self.dependencies.attraction_resolver.resolve(
            candidates,
            city=city,
        )
        if rejected:
            warnings.append(
                f"Rejected {len(rejected)} attraction candidates without "
                "matching source evidence."
            )
        return ProviderResult(
            provider_id="attractions-resolved",
            status=ProviderStatus.OK if attractions else ProviderStatus.NO_RESULTS,
            queried_at=queried_at,
            records=[attraction.model_dump(mode="json") for attraction in attractions],
            warnings=warnings,
        )
