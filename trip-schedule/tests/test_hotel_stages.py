from models import DaySchedule, HotelOption, RouteMode, RouteSegment
from planning.hotel_stages import build_hotel_stage_options
from test_scheduling import attraction, make_evidence


def route(hotel: str, destination: str, minutes: int) -> RouteSegment:
    return RouteSegment(
        origin_name=hotel,
        destination_name=destination,
        mode=RouteMode.TRANSIT,
        distance_meters=5000,
        duration_minutes=minutes,
        estimated_cost_cny=6,
        reason="Public transport is the default.",
        path=[(120.16, 30.25), (120.15, 30.25)],
    )


def test_multi_hotel_option_requires_sixty_minute_saving() -> None:
    hotels = [
        HotelOption(
            name="Hotel A",
            latitude=30.25,
            longitude=120.16,
            total_price_cny=800,
            nights=2,
            evidence=[make_evidence("hotel")],
        ),
        HotelOption(
            name="Hotel B",
            latitude=30.32,
            longitude=120.23,
            total_price_cny=900,
            nights=2,
            evidence=[make_evidence("hotel")],
        ),
    ]
    days = [
        DaySchedule(
            day_index=1,
            attractions=[attraction("A", 30.25, 120.16, 180)],
            planned_visit_minutes=180,
        ),
        DaySchedule(
            day_index=2,
            attractions=[attraction("B", 30.32, 120.23, 180)],
            planned_visit_minutes=180,
        ),
    ]
    routes = {
        "Hotel A": [route("Hotel A", "A", 10), route("Hotel A", "B", 100)],
        "Hotel B": [route("Hotel B", "A", 100), route("Hotel B", "B", 10)],
    }

    options = build_hotel_stage_options(days, hotels, routes)

    assert any(len(option.hotels) == 2 for option in options)
