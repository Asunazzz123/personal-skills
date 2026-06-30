from models import (
    Attraction,
    HotelOption,
    RouteMode,
    RouteSegment,
    SourceEvidence,
    TransportMode,
    TransportOffer,
)
from planning.engine import PlanningEngine, PlanningInputs
from planning.hotel_stages import build_hotel_stage_options
from planning.scheduling import schedule_attractions


def make_evidence(source: str) -> SourceEvidence:
    return SourceEvidence(
        source=source,
        source_url="https://example.invalid/source",
        queried_at="2026-07-01T10:00:00+08:00",
        confidence=0.8,
    )


def make_inputs() -> PlanningInputs:
    transports = [
        TransportOffer(
            provider_id="transport-test",
            mode=TransportMode.FLIGHT,
            service_id="F100",
            origin_name="SZX",
            destination_name="HGH",
            departure_at="2026-07-10T08:00:00+08:00",
            arrival_at="2026-07-10T10:00:00+08:00",
            duration_minutes=120,
            total_price_cny=600,
            evidence=make_evidence("flight"),
        ),
        TransportOffer(
            provider_id="transport-test",
            mode=TransportMode.TRAIN,
            service_id="G100",
            origin_name="深圳北",
            destination_name="杭州东",
            departure_at="2026-07-10T08:00:00+08:00",
            arrival_at="2026-07-10T14:00:00+08:00",
            duration_minutes=360,
            total_price_cny=450,
            evidence=make_evidence("train"),
        ),
    ]
    hotels = [
        HotelOption(
            name=f"Hotel {index}",
            latitude=30.25 + index / 1000,
            longitude=120.16,
            total_price_cny=price,
            nights=2,
            evidence=[make_evidence("hotel")],
        )
        for index, price in enumerate((700, 900, 1200), start=1)
    ]
    attractions = [
        Attraction(
            name="西湖",
            description="湖区",
            latitude=30.25,
            longitude=120.15,
            ticket_price_cny=0,
            suggested_visit_minutes=180,
            evidence=[make_evidence("xhs")],
        )
    ]
    route_template = [
        RouteSegment(
            origin_name="Hotel 1",
            destination_name="西湖",
            mode=RouteMode.TRANSIT,
            distance_meters=5000,
            duration_minutes=35,
            estimated_cost_cny=6,
            reason="Public transport is the default.",
            path=[(120.16, 30.25), (120.15, 30.25)],
        )
    ]
    routes_by_hotel = {
        hotel.name: [
            route.model_copy(update={"origin_name": hotel.name})
            for route in route_template
        ]
        for hotel in hotels
    }
    days = schedule_attractions(attractions, duration_days=3)
    hotel_stage_options = build_hotel_stage_options(
        days,
        hotels,
        routes_by_hotel,
    )
    return PlanningInputs(
        budget_cny=5000,
        travelers=2,
        transports=transports,
        attractions=attractions,
        hotel_stage_options=hotel_stage_options,
    )


def test_engine_rejects_over_budget_candidates() -> None:
    inputs = make_inputs().model_copy(update={"budget_cny": 500})

    result = PlanningEngine().build(inputs)

    assert result.plans == []
    assert result.minimum_deficit_cny > 0


def test_engine_labels_three_distinct_strategies() -> None:
    result = PlanningEngine().build(make_inputs())

    assert [plan.label for plan in result.plans] == [
        "balanced",
        "economy",
        "time-saving",
    ]
    underlying_ids = {
        plan.plan_id.removeprefix(f"{plan.label}-") for plan in result.plans
    }
    assert len(underlying_ids) == 3
