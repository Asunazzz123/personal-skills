from __future__ import annotations

from models import Attraction, DaySchedule
from planning.clustering import cluster_points


def schedule_attractions(
    attractions: list[Attraction],
    *,
    duration_days: int,
    daily_visit_minutes: int = 480,
) -> list[DaySchedule]:
    if duration_days <= 0:
        raise ValueError("duration_days must be positive")
    points = [
        (item.name, item.latitude, item.longitude) for item in attractions
    ]
    clusters = cluster_points(points, radius_km=2)
    by_name = {item.name: item for item in attractions}
    ordered = [
        by_name[name]
        for cluster in clusters
        for name, _, _ in cluster
    ]
    days: list[list[Attraction]] = [[]]
    minutes = 0
    for item in ordered:
        would_overflow = (
            days[-1]
            and minutes + item.suggested_visit_minutes > daily_visit_minutes
        )
        if would_overflow and len(days) < duration_days:
            days.append([])
            minutes = 0
        days[-1].append(item)
        minutes += item.suggested_visit_minutes
    return [
        DaySchedule(
            day_index=index,
            attractions=items,
            planned_visit_minutes=sum(
                item.suggested_visit_minutes for item in items
            ),
        )
        for index, items in enumerate(days, start=1)
    ]
