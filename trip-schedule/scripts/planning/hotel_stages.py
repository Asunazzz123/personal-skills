from __future__ import annotations

from models import DaySchedule, HotelOption, HotelStageOption, RouteSegment


def _route_index(
    routes_by_hotel: dict[str, list[RouteSegment]],
) -> dict[tuple[str, str], RouteSegment]:
    return {
        (hotel_name, route.destination_name): route
        for hotel_name, routes in routes_by_hotel.items()
        for route in routes
    }


def _commute_for_day(
    hotel_name: str,
    day: DaySchedule,
    index: dict[tuple[str, str], RouteSegment],
) -> int:
    return sum(
        index[(hotel_name, attraction.name)].duration_minutes
        for attraction in day.attractions
        if (hotel_name, attraction.name) in index
    )


def build_hotel_stage_options(
    days: list[DaySchedule],
    hotels: list[HotelOption],
    routes_by_hotel: dict[str, list[RouteSegment]],
) -> list[HotelStageOption]:
    index = _route_index(routes_by_hotel)
    options: list[HotelStageOption] = []
    for hotel in hotels:
        selected_routes = routes_by_hotel.get(hotel.name, [])
        commute = sum(
            _commute_for_day(hotel.name, day, index) for day in days
        )
        options.append(
            HotelStageOption(
                option_id=f"single:{hotel.name}",
                hotels=[hotel],
                days=[
                    day.model_copy(update={"hotel_name": hotel.name})
                    for day in days
                ],
                routes=selected_routes,
                total_hotel_cost_cny=hotel.total_price_cny or 0,
                total_commute_minutes=commute,
            )
        )
    if not options:
        return []

    best_single = min(options, key=lambda item: item.total_commute_minutes)
    selected_by_day = [
        min(
            hotels,
            key=lambda hotel: _commute_for_day(hotel.name, day, index),
        )
        for day in days
    ]
    unique_hotels = list({hotel.name: hotel for hotel in selected_by_day}.values())
    multi_commute = sum(
        _commute_for_day(hotel.name, day, index)
        for hotel, day in zip(selected_by_day, days, strict=True)
    )
    saving = best_single.total_commute_minutes - multi_commute
    if len(unique_hotels) > 1 and saving >= 60:
        day_counts = {
            hotel.name: sum(
                selected.name == hotel.name for selected in selected_by_day
            )
            for hotel in unique_hotels
        }
        stage_hotels = []
        for hotel in unique_hotels:
            stage_nights = max(1, min(day_counts[hotel.name], hotel.nights))
            nightly = (hotel.total_price_cny or 0) / hotel.nights
            stage_hotels.append(
                hotel.model_copy(
                    update={
                        "nights": stage_nights,
                        "total_price_cny": round(nightly * stage_nights, 2),
                    }
                )
            )
        options.append(
            HotelStageOption(
                option_id="multi:" + "+".join(
                    hotel.name for hotel in stage_hotels
                ),
                hotels=stage_hotels,
                days=[
                    day.model_copy(update={"hotel_name": hotel.name})
                    for day, hotel in zip(days, selected_by_day, strict=True)
                ],
                routes=[
                    index[(hotel.name, attraction.name)]
                    for day, hotel in zip(days, selected_by_day, strict=True)
                    for attraction in day.attractions
                    if (hotel.name, attraction.name) in index
                ],
                total_hotel_cost_cny=sum(
                    hotel.total_price_cny or 0 for hotel in stage_hotels
                ),
                total_commute_minutes=multi_commute,
            )
        )
    return options
