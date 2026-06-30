from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    """Base model that rejects unknown fields at system boundaries."""

    model_config = ConfigDict(extra="forbid")


class GenerationMode(StrEnum):
    ONE_SHOT = "one_shot"
    INTERACTIVE = "interactive"


class ProviderStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    NOT_CONFIGURED = "not_configured"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"
    CHALLENGE_REQUIRED = "challenge_required"
    NETWORK_ERROR = "network_error"
    SCHEMA_CHANGED = "schema_changed"
    NO_RESULTS = "no_results"
    STALE = "stale"


class TransportMode(StrEnum):
    TRAIN = "train"
    FLIGHT = "flight"


class TripRequest(StrictModel):
    origin_city: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    budget_cny: float = Field(gt=0)
    departure_at: datetime
    duration_days: int = Field(gt=0)
    travelers: int = Field(gt=0)
    generation_mode: GenerationMode

    @field_validator("departure_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("departure_at must include a timezone")
        return value


class SourceEvidence(StrictModel):
    source: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    queried_at: datetime
    expires_at: datetime | None = None
    freshness: str = "live"
    confidence: float = Field(ge=0, le=1)

    @field_validator("queried_at")
    @classmethod
    def require_query_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("queried_at must include a timezone")
        return value


class TransportOffer(StrictModel):
    provider_id: str
    mode: TransportMode
    service_id: str
    origin_name: str
    destination_name: str
    departure_at: datetime
    arrival_at: datetime
    duration_minutes: int = Field(gt=0)
    total_price_cny: float | None = Field(default=None, ge=0)
    transfers: int = Field(default=0, ge=0)
    availability: dict[str, str] = Field(default_factory=dict)
    booking_url: str | None = None
    evidence: SourceEvidence


class ProviderHealth(StrictModel):
    provider_id: str
    status: ProviderStatus
    detail: str


class ProviderResult(StrictModel):
    provider_id: str
    status: ProviderStatus
    queried_at: datetime
    records: list[dict[str, Any]]
    warnings: list[str] = Field(default_factory=list)
    error_kind: str | None = None

    @field_validator("queried_at")
    @classmethod
    def require_result_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("queried_at must include a timezone")
        return value


class RouteMode(StrEnum):
    WALK = "walk"
    TRANSIT = "transit"
    TAXI = "taxi"


class Attraction(StrictModel):
    name: str
    description: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str | None = None
    opening_hours: list[str] = Field(default_factory=list)
    ticket_price_cny: float | None = Field(default=None, ge=0)
    suggested_visit_minutes: int = Field(gt=0)
    evidence: list[SourceEvidence]


class HotelOption(StrictModel):
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str | None = None
    total_price_cny: float | None = Field(default=None, ge=0)
    nights: int = Field(gt=0)
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    transit_notes: list[str] = Field(default_factory=list)
    evidence: list[SourceEvidence]


class RouteSegment(StrictModel):
    origin_name: str
    destination_name: str
    mode: RouteMode
    distance_meters: int = Field(ge=0)
    duration_minutes: int = Field(gt=0)
    estimated_cost_cny: float = Field(ge=0)
    reason: str
    path: list[tuple[float, float]] = Field(min_length=2)


class DaySchedule(StrictModel):
    day_index: int = Field(gt=0)
    attractions: list[Attraction]
    hotel_name: str | None = None
    planned_visit_minutes: int = Field(ge=0)


class HotelStageOption(StrictModel):
    option_id: str
    hotels: list[HotelOption] = Field(min_length=1)
    days: list[DaySchedule] = Field(min_length=1)
    routes: list[RouteSegment]
    total_hotel_cost_cny: float = Field(ge=0)
    total_commute_minutes: int = Field(ge=0)


class CandidatePlan(StrictModel):
    plan_id: str
    label: str
    transport: TransportOffer
    hotels: list[HotelOption]
    attractions: list[Attraction]
    days: list[DaySchedule]
    routes: list[RouteSegment]
    total_cost_cny: float = Field(ge=0)
    contingency_cny: float = Field(ge=0)
    score: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
