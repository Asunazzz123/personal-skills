from planning.clustering import cluster_points


def test_cluster_points_groups_nearby_attractions() -> None:
    points = [
        ("A", 30.2500, 120.1600),
        ("B", 30.2550, 120.1650),
        ("C", 30.3100, 120.2200),
    ]

    clusters = cluster_points(points, radius_km=2)

    assert [[item[0] for item in cluster] for cluster in clusters] == [
        ["A", "B"],
        ["C"],
    ]
