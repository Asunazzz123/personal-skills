from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


TravelModeToNextAnchor = Literal["transit", "taxi", "walk"]


class RestaurantCandidate(BaseModel):
    """Structured dining candidate produced from sourced evidence."""

    name: str = Field(min_length=1)
    area: str = Field(min_length=1)
    cuisine_tags: list[str] = Field(default_factory=list)
    average_cost_cny: float | None = Field(default=None, ge=0)
    reputation_score: float = Field(ge=0, le=1)
    detour_minutes: int = Field(default=0, ge=0)
    distance_to_nearest_metro_meters: int | None = Field(default=None, ge=0)
    transit_minutes_to_next_anchor: int | None = Field(default=None, ge=0)
    taxi_minutes_to_next_anchor: int | None = Field(default=None, ge=0)
    arrival_buffer_minutes: int | None = Field(default=None)
    evidence_urls: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("cuisine_tags", "evidence_urls", "notes")
    @classmethod
    def strip_blank_strings(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class RestaurantRankingContext(BaseModel):
    """Trip-stage context used by the pure restaurant scorer."""

    preferred_cuisine_tags: list[str] = Field(default_factory=list)
    budget_min_cny: float | None = Field(default=None, ge=0)
    budget_max_cny: float | None = Field(default=None, ge=0)
    travel_mode_to_next_anchor: TravelModeToNextAnchor = "transit"
    minimum_arrival_buffer_minutes: int = Field(default=20, ge=0)

    @field_validator("preferred_cuisine_tags")
    @classmethod
    def strip_preferred_tags(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class RestaurantRankingResult(BaseModel):
    candidate: RestaurantCandidate
    final_score: float = Field(ge=0, le=1)
    component_scores: dict[str, float]
    penalties: list[str] = Field(default_factory=list)
    is_viable: bool = True


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _budget_score(
    candidate: RestaurantCandidate,
    context: RestaurantRankingContext,
) -> tuple[float, list[str]]:
    penalties: list[str] = []
    if candidate.average_cost_cny is None:
        return 0.5, ["missing average cost"]
    lower = context.budget_min_cny
    upper = context.budget_max_cny
    cost = candidate.average_cost_cny
    if lower is not None and cost < lower:
        ratio = (lower - cost) / max(lower, 1)
        penalties.append("below budget band")
        return _clamp(0.85 - ratio), penalties
    if upper is not None and cost > upper:
        ratio = (cost - upper) / max(upper, 1)
        penalties.append("above budget band")
        return _clamp(1 - 2 * ratio), penalties
    if lower is None or upper is None or upper <= lower:
        return 1.0, penalties
    midpoint = (lower + upper) / 2
    half_width = max((upper - lower) / 2, 1)
    return _clamp(1 - 0.25 * abs(cost - midpoint) / half_width), penalties


def _cuisine_score(
    candidate: RestaurantCandidate,
    context: RestaurantRankingContext,
) -> float:
    preferred = {tag.lower() for tag in context.preferred_cuisine_tags}
    if not preferred:
        return 1.0
    candidate_tags = {tag.lower() for tag in candidate.cuisine_tags}
    if preferred & candidate_tags:
        return 1.0
    return 0.35


def _route_score(candidate: RestaurantCandidate) -> float:
    return _clamp(1 - candidate.detour_minutes / 60)


def _convenience_score(
    candidate: RestaurantCandidate,
    context: RestaurantRankingContext,
) -> tuple[float, list[str]]:
    penalties: list[str] = []
    mode = context.travel_mode_to_next_anchor
    if mode == "transit":
        metro_distance = candidate.distance_to_nearest_metro_meters
        if metro_distance is None:
            penalties.append("missing metro distance")
            metro_score = 0.45
        elif metro_distance <= 400:
            metro_score = 1.0
        elif metro_distance <= 800:
            metro_score = 0.75
        elif metro_distance <= 1200:
            metro_score = 0.45
            penalties.append("metro distance is inconvenient")
        else:
            metro_score = 0.2
            penalties.append("metro distance is far")
        transit_minutes = candidate.transit_minutes_to_next_anchor
        if transit_minutes is None:
            penalties.append("missing transit time")
            time_score = 0.45
        else:
            time_score = _clamp(1 - transit_minutes / 90)
        return _clamp(0.65 * metro_score + 0.35 * time_score), penalties
    if mode == "taxi":
        taxi_minutes = candidate.taxi_minutes_to_next_anchor
        if taxi_minutes is None:
            penalties.append("missing taxi time")
            return 0.45, penalties
        if taxi_minutes > 40:
            penalties.append("taxi route is slow")
        return _clamp(1 - taxi_minutes / 70), penalties
    return _route_score(candidate), penalties


def _arrival_buffer_viability(
    candidate: RestaurantCandidate,
    context: RestaurantRankingContext,
) -> tuple[bool, list[str]]:
    if candidate.arrival_buffer_minutes is None:
        return True, ["missing arrival buffer"]
    if candidate.arrival_buffer_minutes < context.minimum_arrival_buffer_minutes:
        return False, [
            "arrival buffer below required minimum "
            f"({candidate.arrival_buffer_minutes}m < "
            f"{context.minimum_arrival_buffer_minutes}m)"
        ]
    return True, []


def score_restaurant(
    candidate: RestaurantCandidate,
    context: RestaurantRankingContext,
) -> RestaurantRankingResult:
    budget_score, budget_penalties = _budget_score(candidate, context)
    cuisine_score = _cuisine_score(candidate, context)
    route_score = _route_score(candidate)
    convenience_score, convenience_penalties = _convenience_score(candidate, context)
    is_viable, viability_penalties = _arrival_buffer_viability(candidate, context)
    components = {
        "reputation": round(candidate.reputation_score, 4),
        "route_fit": round(route_score, 4),
        "budget": round(budget_score, 4),
        "cuisine": round(cuisine_score, 4),
        "convenience": round(convenience_score, 4),
    }
    penalties = budget_penalties + convenience_penalties + viability_penalties
    penalty_discount = _penalty_discount(penalties)
    if not is_viable:
        final_score = 0.0
    else:
        final_score = (
            0.30 * candidate.reputation_score
            + 0.25 * route_score
            + 0.20 * budget_score
            + 0.15 * cuisine_score
            + 0.10 * convenience_score
            - penalty_discount
        )
    return RestaurantRankingResult(
        candidate=candidate,
        final_score=round(_clamp(final_score), 4),
        component_scores=components,
        penalties=penalties,
        is_viable=is_viable,
    )


def _penalty_discount(penalties: list[str]) -> float:
    discount = 0.0
    for penalty in penalties:
        normalized = penalty.lower()
        if "metro distance is far" in normalized:
            discount += 0.12
        elif "metro distance is inconvenient" in normalized:
            discount += 0.05
        elif "taxi route is slow" in normalized:
            discount += 0.06
        elif "above budget band" in normalized:
            discount += 0.08
        elif normalized.startswith("missing"):
            discount += 0.03
    return discount


def rank_restaurants(
    candidates: list[RestaurantCandidate],
    context: RestaurantRankingContext,
) -> list[RestaurantRankingResult]:
    scored = [score_restaurant(candidate, context) for candidate in candidates]
    return sorted(
        scored,
        key=lambda item: (item.is_viable, item.final_score, item.candidate.reputation_score),
        reverse=True,
    )
