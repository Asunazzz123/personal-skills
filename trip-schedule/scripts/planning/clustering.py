from __future__ import annotations

from math import asin, cos, radians, sin, sqrt


Point = tuple[str, float, float]


def haversine_km(left: Point, right: Point) -> float:
    _, lat1, lon1 = left
    _, lat2, lon2 = right
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    value = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 6371 * 2 * asin(sqrt(value))


def cluster_points(points: list[Point], *, radius_km: float) -> list[list[Point]]:
    clusters: list[list[Point]] = []
    for point in points:
        for cluster in clusters:
            if any(haversine_km(point, member) <= radius_km for member in cluster):
                cluster.append(point)
                break
        else:
            clusters.append([point])
    return clusters
