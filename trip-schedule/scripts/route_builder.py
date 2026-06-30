from __future__ import annotations

from models import (
    Attraction,
    HotelOption,
    ProviderResult,
    ProviderStatus,
    RouteMode,
    RouteSegment,
    TripRequest,
)
from planning.routing import choose_local_mode


class DefaultRouteBuilder:
    def __init__(self, amap) -> None:
        self.amap = amap

    def build(
        self,
        request: TripRequest,
        research: dict[str, ProviderResult],
    ) -> dict[str, list[RouteSegment]]:
        hotels = [
            HotelOption.model_validate(record)
            for provider_id, result in research.items()
            if provider_id.startswith("hotels")
            for record in result.records
        ]
        attractions = [
            Attraction.model_validate(record)
            for provider_id, result in research.items()
            if provider_id.startswith("attractions")
            for record in result.records
        ]
        routes_by_hotel: dict[str, list[RouteSegment]] = {}
        for hotel in hotels:
            hotel_routes = []
            origin = (hotel.longitude, hotel.latitude)
            for attraction in attractions:
                destination = (attraction.longitude, attraction.latitude)
                transit = self.amap.route_transit(
                    origin,
                    destination,
                    city=request.destination,
                )
                driving = self.amap.route_driving(origin, destination)
                if (
                    transit.status is not ProviderStatus.OK
                    or driving.status is not ProviderStatus.OK
                    or not transit.records
                    or not driving.records
                ):
                    continue
                transit_row = transit.records[0]
                driving_row = driving.records[0]
                distance_km = driving_row["distance_meters"] / 1000
                taxi_cost = round(13 + max(0, distance_km - 3) * 2.5, 2)
                decision = choose_local_mode(
                    distance_km=distance_km,
                    transit_minutes=transit_row["duration_minutes"],
                    taxi_minutes=driving_row["duration_minutes"],
                    taxi_cost_cny=taxi_cost,
                    travelers=request.travelers,
                    late_night=False,
                    has_luggage=False,
                )
                selected = (
                    driving_row if decision.mode is RouteMode.TAXI else transit_row
                )
                hotel_routes.append(
                    RouteSegment(
                        origin_name=hotel.name,
                        destination_name=attraction.name,
                        mode=decision.mode,
                        distance_meters=selected["distance_meters"],
                        duration_minutes=selected["duration_minutes"],
                        estimated_cost_cny=(
                            taxi_cost
                            if decision.mode is RouteMode.TAXI
                            else selected["estimated_cost_cny"]
                        ),
                        reason=decision.reason,
                        path=[tuple(point) for point in selected["path"]],
                    )
                )
            routes_by_hotel[hotel.name] = hotel_routes
        return routes_by_hotel
