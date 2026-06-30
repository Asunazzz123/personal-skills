from models import (
    Attraction,
    HotelOption,
    ProviderResult,
    ProviderStatus,
    SourceEvidence,
    TripRequest,
)
from route_builder import DefaultRouteBuilder


class FakeAMap:
    def route_transit(self, origin, destination, *, city):
        return ProviderResult(
            provider_id="amap-webservice",
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[
                {
                    "distance_meters": 8000,
                    "duration_minutes": 60,
                    "estimated_cost_cny": 6,
                    "path": [list(origin), list(destination)],
                }
            ],
        )

    def route_driving(self, origin, destination):
        return ProviderResult(
            provider_id="amap-webservice",
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[
                {
                    "distance_meters": 8000,
                    "duration_minutes": 25,
                    "estimated_cost_cny": 0,
                    "path": [list(origin), list(destination)],
                }
            ],
        )


def test_route_builder_creates_routes_per_hotel() -> None:
    evidence = SourceEvidence(
        source="fixture",
        source_url="https://example.invalid/source",
        queried_at="2026-07-01T10:00:00+08:00",
        confidence=0.8,
    )
    hotel = HotelOption(
        name="湖滨酒店",
        latitude=30.26,
        longitude=120.16,
        total_price_cny=900,
        nights=2,
        evidence=[evidence],
    )
    attraction = Attraction(
        name="西湖",
        description="湖区",
        latitude=30.25,
        longitude=120.15,
        ticket_price_cny=0,
        suggested_visit_minutes=180,
        evidence=[evidence],
    )
    research = {
        "hotels-fixture": ProviderResult(
            provider_id="hotels-fixture",
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[hotel.model_dump(mode="json")],
        ),
        "attractions-fixture": ProviderResult(
            provider_id="attractions-fixture",
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[attraction.model_dump(mode="json")],
        ),
    }
    request = TripRequest(
        origin_city="深圳",
        destination="杭州",
        budget_cny=5000,
        departure_at="2026-07-10T08:00:00+08:00",
        duration_days=3,
        travelers=2,
        generation_mode="one_shot",
    )

    routes = DefaultRouteBuilder(FakeAMap()).build(request, research)

    assert list(routes) == ["湖滨酒店"]
    assert routes["湖滨酒店"][0].path[0] == (120.16, 30.26)
