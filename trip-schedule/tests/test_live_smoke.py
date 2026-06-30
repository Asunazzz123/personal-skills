import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("TRIP_SCHEDULE_LIVE_TESTS") != "1",
    reason="set TRIP_SCHEDULE_LIVE_TESTS=1 for bounded live checks",
)


def test_live_amap_geocode() -> None:
    from providers.amap import AMapProvider

    result = AMapProvider().geocode("杭州西湖", city="杭州")
    assert result.records


def test_live_train_query() -> None:
    from providers.train_12306 import Train12306Provider, TrainQuery

    result = Train12306Provider().query(
        TrainQuery(
            origin_station="深圳北",
            destination_station="广州南",
            travel_date=os.environ["TRIP_SCHEDULE_TEST_DATE"],
        )
    )
    assert result.status.value in {"ok", "no_results"}
