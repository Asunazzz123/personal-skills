from __future__ import annotations

from pathlib import Path

from planning.restaurant_scoring import (
    RestaurantCandidate,
    RestaurantRankingContext,
    rank_restaurants,
)


def make_candidate(
    name: str,
    *,
    average_cost_cny: float,
    reputation_score: float,
    cuisine_tags: list[str],
    detour_minutes: int,
    distance_to_nearest_metro_meters: int,
    transit_minutes_to_next_anchor: int,
    taxi_minutes_to_next_anchor: int = 20,
    arrival_buffer_minutes: int = 45,
) -> RestaurantCandidate:
    return RestaurantCandidate(
        name=name,
        area="广州",
        cuisine_tags=cuisine_tags,
        average_cost_cny=average_cost_cny,
        reputation_score=reputation_score,
        detour_minutes=detour_minutes,
        distance_to_nearest_metro_meters=distance_to_nearest_metro_meters,
        transit_minutes_to_next_anchor=transit_minutes_to_next_anchor,
        taxi_minutes_to_next_anchor=taxi_minutes_to_next_anchor,
        arrival_buffer_minutes=arrival_buffer_minutes,
        evidence_urls=["https://www.xiaohongshu.com/explore/demo"],
    )


def test_transit_ranking_penalizes_restaurants_far_from_metro() -> None:
    context = RestaurantRankingContext(
        preferred_cuisine_tags=["西餐", "高端粤菜", "日料"],
        budget_min_cny=200,
        budget_max_cny=400,
        travel_mode_to_next_anchor="transit",
        minimum_arrival_buffer_minutes=25,
    )
    close_match = make_candidate(
        "近地铁西餐",
        average_cost_cny=310,
        reputation_score=0.82,
        cuisine_tags=["西餐"],
        detour_minutes=12,
        distance_to_nearest_metro_meters=240,
        transit_minutes_to_next_anchor=32,
    )
    far_but_popular = make_candidate(
        "远地铁热门西餐",
        average_cost_cny=300,
        reputation_score=0.98,
        cuisine_tags=["西餐"],
        detour_minutes=8,
        distance_to_nearest_metro_meters=1600,
        transit_minutes_to_next_anchor=48,
    )

    ranked = rank_restaurants([far_but_popular, close_match], context)

    assert [item.candidate.name for item in ranked] == ["近地铁西餐", "远地铁热门西餐"]
    assert ranked[0].component_scores["convenience"] > ranked[1].component_scores[
        "convenience"
    ]
    assert any("metro" in reason.lower() for reason in ranked[1].penalties)


def test_restaurant_missing_train_buffer_is_disqualified() -> None:
    context = RestaurantRankingContext(
        preferred_cuisine_tags=["日料"],
        budget_min_cny=200,
        budget_max_cny=400,
        travel_mode_to_next_anchor="transit",
        minimum_arrival_buffer_minutes=25,
    )
    too_late = make_candidate(
        "赶不上车的日料",
        average_cost_cny=300,
        reputation_score=0.99,
        cuisine_tags=["日料"],
        detour_minutes=0,
        distance_to_nearest_metro_meters=100,
        transit_minutes_to_next_anchor=20,
        arrival_buffer_minutes=10,
    )
    safe = make_candidate(
        "可安全赶车的日料",
        average_cost_cny=330,
        reputation_score=0.72,
        cuisine_tags=["日料"],
        detour_minutes=15,
        distance_to_nearest_metro_meters=400,
        transit_minutes_to_next_anchor=35,
        arrival_buffer_minutes=35,
    )

    ranked = rank_restaurants([too_late, safe], context)

    assert ranked[0].candidate.name == "可安全赶车的日料"
    assert ranked[0].is_viable is True
    assert ranked[1].candidate.name == "赶不上车的日料"
    assert ranked[1].is_viable is False
    assert ranked[1].final_score == 0


def test_taxi_mode_uses_taxi_time_instead_of_metro_distance() -> None:
    context = RestaurantRankingContext(
        preferred_cuisine_tags=["高端粤菜"],
        budget_min_cny=250,
        budget_max_cny=450,
        travel_mode_to_next_anchor="taxi",
        minimum_arrival_buffer_minutes=25,
    )
    far_from_metro_fast_taxi = make_candidate(
        "打车顺路粤菜",
        average_cost_cny=360,
        reputation_score=0.80,
        cuisine_tags=["高端粤菜"],
        detour_minutes=5,
        distance_to_nearest_metro_meters=1800,
        transit_minutes_to_next_anchor=70,
        taxi_minutes_to_next_anchor=16,
    )
    close_to_metro_slow_taxi = make_candidate(
        "近地铁但打车绕路粤菜",
        average_cost_cny=360,
        reputation_score=0.80,
        cuisine_tags=["高端粤菜"],
        detour_minutes=5,
        distance_to_nearest_metro_meters=120,
        transit_minutes_to_next_anchor=30,
        taxi_minutes_to_next_anchor=48,
    )

    ranked = rank_restaurants([close_to_metro_slow_taxi, far_from_metro_fast_taxi], context)

    assert ranked[0].candidate.name == "打车顺路粤菜"
    assert ranked[0].component_scores["convenience"] > ranked[1].component_scores[
        "convenience"
    ]


def test_restaurant_scoring_module_does_not_import_provider_integrations() -> None:
    source = Path("scripts/planning/restaurant_scoring.py").read_text(encoding="utf-8")

    assert "providers." not in source
    assert "xhs" not in source.lower()
    assert "train_12306" not in source
    assert "amap" not in source.lower()
