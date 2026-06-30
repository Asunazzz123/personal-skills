from __future__ import annotations

from dataclasses import dataclass

from models import RouteMode


@dataclass(frozen=True)
class RouteDecision:
    mode: RouteMode
    reason: str


def choose_local_mode(
    *,
    distance_km: float,
    transit_minutes: int,
    taxi_minutes: int,
    taxi_cost_cny: float,
    travelers: int,
    late_night: bool,
    has_luggage: bool,
) -> RouteDecision:
    transit_unavailable = transit_minutes <= 0
    time_saved = max(0, transit_minutes - taxi_minutes)
    practical_need = late_night or has_luggage or transit_unavailable
    if distance_km > 15 and practical_need:
        return RouteDecision(
            mode=RouteMode.TAXI,
            reason=(
                "Taxi exception beyond 15 km because transit is impractical "
                "for this segment."
            ),
        )
    if distance_km <= 15 and (time_saved >= 25 or practical_need):
        return RouteDecision(
            mode=RouteMode.TAXI,
            reason=(
                f"Taxi saves {time_saved} minutes or satisfies a practical "
                f"need; estimated per-person cost is "
                f"{taxi_cost_cny / travelers:.2f} CNY."
            ),
        )
    return RouteDecision(
        mode=RouteMode.TRANSIT,
        reason="Public transport is the default for this segment.",
    )
