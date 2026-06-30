from __future__ import annotations

import json
import os
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from models import (
    HotelOption,
    ProviderHealth,
    ProviderResult,
    ProviderStatus,
    SourceEvidence,
)
from providers.base import Provider
from providers.command_provider import CommandRunner


class HotelQuery(BaseModel):
    destination: str
    check_in: date
    check_out: date
    travelers: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_dates(self) -> "HotelQuery":
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self


class HotelProvider(Provider):
    provider_id = "hotels-external"

    def __init__(self) -> None:
        raw = os.getenv("TRIP_HOTEL_COMMAND_JSON")
        self.command = json.loads(raw) if raw else None
        self.runner = CommandRunner(self.command) if self.command else None

    def health_check(self) -> ProviderHealth:
        if self.runner is None:
            return ProviderHealth(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                detail="Set TRIP_HOTEL_COMMAND_JSON; no crawler was installed.",
            )
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.OK,
            detail="external hotel wrapper configured",
        )

    def query(self, request: object) -> ProviderResult:
        query = HotelQuery.model_validate(request)
        queried_at = datetime.now().astimezone()
        if self.runner is None:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                queried_at=queried_at,
                records=[],
            )
        try:
            rows = self.runner.run(query.model_dump(mode="json"))
            hotels = [
                HotelOption(
                    name=row["name"],
                    latitude=row["latitude"],
                    longitude=row["longitude"],
                    address=row.get("address"),
                    total_price_cny=row.get("total_price_cny"),
                    nights=(query.check_out - query.check_in).days,
                    rating=row.get("rating"),
                    review_count=row.get("review_count"),
                    transit_notes=row.get("transit_notes", []),
                    evidence=[
                        SourceEvidence(
                            source=row["source"],
                            source_url=row["source_url"],
                            queried_at=queried_at,
                            confidence=0.75,
                        )
                    ],
                )
                for row in rows
            ]
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.SCHEMA_CHANGED,
                queried_at=queried_at,
                records=[],
                warnings=[str(exc)],
                error_kind=type(exc).__name__,
            )
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.OK if hotels else ProviderStatus.NO_RESULTS,
            queried_at=queried_at,
            records=[hotel.model_dump(mode="json") for hotel in hotels],
        )
