from models import RouteMode
from planning.routing import choose_local_mode


def test_public_transit_is_default() -> None:
    decision = choose_local_mode(
        distance_km=8,
        transit_minutes=45,
        taxi_minutes=30,
        taxi_cost_cny=45,
        travelers=2,
        late_night=False,
        has_luggage=False,
    )

    assert decision.mode is RouteMode.TRANSIT


def test_taxi_is_recommended_for_large_time_saving() -> None:
    decision = choose_local_mode(
        distance_km=10,
        transit_minutes=70,
        taxi_minutes=30,
        taxi_cost_cny=55,
        travelers=3,
        late_night=False,
        has_luggage=False,
    )

    assert decision.mode is RouteMode.TAXI
    assert "40 minutes" in decision.reason


def test_long_taxi_requires_exception_reason() -> None:
    decision = choose_local_mode(
        distance_km=20,
        transit_minutes=0,
        taxi_minutes=35,
        taxi_cost_cny=90,
        travelers=2,
        late_night=True,
        has_luggage=True,
    )

    assert decision.mode is RouteMode.TAXI
    assert "exception" in decision.reason.lower()
