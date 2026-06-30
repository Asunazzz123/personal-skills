import json

import pytest

from models import GenerationMode, TripRequest
from workspace import TripWorkspace


def _trip_request(destination: str = "广州") -> TripRequest:
    return TripRequest(
        origin_city="深圳",
        destination=destination,
        budget_cny=2000,
        departure_at="2026-07-10T08:00:00+08:00",
        duration_days=2,
        travelers=2,
        generation_mode=GenerationMode.ONE_SHOT,
    )


def test_workspace_writes_request_without_reusing_previous_trip(tmp_path) -> None:
    request = _trip_request()

    first = TripWorkspace.create(tmp_path, request, timestamp="20260701T100000")
    second = TripWorkspace.create(tmp_path, request, timestamp="20260701T100001")

    assert first.root != second.root
    assert json.loads(first.request_path.read_text(encoding="utf-8"))[
        "destination"
    ] == "广州"


def test_workspace_allocates_suffix_for_same_timestamp_and_destination(tmp_path) -> None:
    request = _trip_request()

    first = TripWorkspace.create(tmp_path, request, timestamp="20260701T100000")
    second = TripWorkspace.create(tmp_path, request, timestamp="20260701T100000")

    assert first.root != second.root
    assert first.request_path.exists()
    assert second.request_path.exists()
    assert second.root.name == "20260701T100000-广州-2"


def test_workspace_rejects_unsafe_timestamp(tmp_path) -> None:
    with pytest.raises(ValueError, match="timestamp"):
        TripWorkspace.create(tmp_path, _trip_request(), timestamp="../escape")


def test_write_json_rejects_paths_outside_workspace(tmp_path) -> None:
    workspace = TripWorkspace.create(tmp_path, _trip_request(), timestamp="20260701T100000")

    with pytest.raises(ValueError, match="filename"):
        workspace.write_json("../escape.json", {"ok": True})

    with pytest.raises(ValueError, match="filename"):
        workspace.write_json(str(tmp_path / "escape.json"), {"ok": True})


def test_write_json_writes_inside_workspace(tmp_path) -> None:
    workspace = TripWorkspace.create(tmp_path, _trip_request(), timestamp="20260701T100000")

    path = workspace.write_json("provider-report.json", {"ok": True})

    assert path == workspace.root / "provider-report.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {"ok": True}
