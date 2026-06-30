import json

from models import GenerationMode, TripRequest
from workspace import TripWorkspace


def test_workspace_writes_request_without_reusing_previous_trip(tmp_path) -> None:
    request = TripRequest(
        origin_city="深圳",
        destination="广州",
        budget_cny=2000,
        departure_at="2026-07-10T08:00:00+08:00",
        duration_days=2,
        travelers=2,
        generation_mode=GenerationMode.ONE_SHOT,
    )

    first = TripWorkspace.create(tmp_path, request, timestamp="20260701T100000")
    second = TripWorkspace.create(tmp_path, request, timestamp="20260701T100001")

    assert first.root != second.root
    assert json.loads(first.request_path.read_text(encoding="utf-8"))[
        "destination"
    ] == "广州"
