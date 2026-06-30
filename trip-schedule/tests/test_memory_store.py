import json

import pytest

from memory_store import StrategyMemory


def test_memory_api_rejects_trip_specific_fields(tmp_path) -> None:
    path = tmp_path / "strategy.json"
    memory = StrategyMemory(path)

    with pytest.raises(TypeError):
        memory.record_run(
            region="杭州",
            query_keywords=["杭州 景点"],
            provider_events=[("attractions-xhs", "ok")],
            routing_notes=["West Lake attractions cluster well."],
            budget_cny=5000,
        )


def test_memory_caps_region_entries(tmp_path) -> None:
    path = tmp_path / "strategy.json"
    memory = StrategyMemory(path, max_regions=2)
    for region in ("杭州", "苏州", "南京"):
        memory.record_run(
            region=region,
            query_keywords=[f"{region} 景点"],
            provider_events=[],
            routing_notes=[],
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert list(payload["regions"]) == ["苏州", "南京"]


def test_memory_rejects_non_positive_caps(tmp_path) -> None:
    path = tmp_path / "strategy.json"

    with pytest.raises(ValueError):
        StrategyMemory(path, max_regions=0)

    with pytest.raises(ValueError):
        StrategyMemory(path, max_providers=0)


def test_memory_caps_provider_entries(tmp_path) -> None:
    path = tmp_path / "strategy.json"
    memory = StrategyMemory(path, max_providers=2)
    for provider_id in ("provider-a", "provider-b", "provider-c"):
        memory.record_run(
            region="杭州",
            query_keywords=[],
            provider_events=[(provider_id, "ok")],
            routing_notes=[],
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert list(payload["providers"]) == ["provider-b", "provider-c"]


def test_memory_moves_updated_provider_to_end_before_capping(tmp_path) -> None:
    path = tmp_path / "strategy.json"
    memory = StrategyMemory(path, max_providers=2)
    memory.record_run(
        region="杭州",
        query_keywords=[],
        provider_events=[("provider-a", "ok"), ("provider-b", "ok")],
        routing_notes=[],
    )

    memory.record_run(
        region="杭州",
        query_keywords=[],
        provider_events=[("provider-a", "partial"), ("provider-c", "ok")],
        routing_notes=[],
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert list(payload["providers"]) == ["provider-a", "provider-c"]


def test_memory_tracks_exact_provider_status_counts(tmp_path) -> None:
    path = tmp_path / "strategy.json"
    memory = StrategyMemory(path)

    memory.record_run(
        region="杭州",
        query_keywords=[],
        provider_events=[
            ("provider-a", "ok"),
            ("provider-a", "partial"),
            ("provider-a", "no_results"),
            ("provider-a", "not_configured"),
            ("provider-a", "no_results"),
        ],
        routing_notes=[],
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    provider = payload["providers"]["provider-a"]
    assert provider["success_count"] == 2
    assert provider["failure_count"] == 3
    assert provider["status_counts"] == {
        "ok": 1,
        "partial": 1,
        "no_results": 2,
        "not_configured": 1,
    }
    assert provider["last_status"] == "no_results"


def test_memory_sanitizes_stored_query_and_routing_strings(tmp_path) -> None:
    path = tmp_path / "strategy.json"
    memory = StrategyMemory(path)

    long_secret = "token=secret " + ("x" * 240)
    memory.record_run(
        region="杭州",
        query_keywords=[
            "  Visit https://example.invalid/x on 2026-07-10 token=secret  ",
            "api_key=secret-key nearby hotels",
            long_secret,
        ],
        provider_events=[],
        routing_notes=[
            "cookie=session password=hunter2 authorization=Bearer abc 2026-07-10",
            "https://example.invalid/x",
        ],
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    stored_strings = (
        payload["regions"]["杭州"]["query_keywords"]
        + payload["regions"]["杭州"]["routing_notes"]
    )
    joined = "\n".join(stored_strings)
    assert "https://example.invalid/x" not in joined
    assert "2026-07-10" not in joined
    assert "token=secret" not in joined
    assert "api_key=secret-key" not in joined
    assert "session" not in joined
    assert "hunter2" not in joined
    assert "Bearer abc" not in joined
    assert "[url]" in joined
    assert "[date]" in joined
    assert "[redacted]" in joined
    assert all(value == value.strip() for value in stored_strings)
    assert all(len(value) <= 160 for value in stored_strings)


def test_memory_recovers_from_corrupt_existing_json(tmp_path) -> None:
    path = tmp_path / "strategy.json"
    path.write_text("{bad json", encoding="utf-8")
    memory = StrategyMemory(path)

    memory.record_run(
        region="杭州",
        query_keywords=["杭州 景点"],
        provider_events=[("provider-a", "ok")],
        routing_notes=["cluster nearby attractions"],
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert isinstance(payload["regions"], dict)
    assert isinstance(payload["providers"], dict)
    assert list(payload["regions"]) == ["杭州"]
    assert payload["providers"]["provider-a"]["success_count"] == 1


def test_memory_recovers_from_malformed_existing_shape(tmp_path) -> None:
    path = tmp_path / "strategy.json"
    path.write_text(
        json.dumps({"version": 1, "regions": [], "providers": None}),
        encoding="utf-8",
    )
    memory = StrategyMemory(path)

    memory.record_run(
        region="杭州",
        query_keywords=[],
        provider_events=[],
        routing_notes=[],
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert isinstance(payload["regions"], dict)
    assert isinstance(payload["providers"], dict)
    assert list(payload["regions"]) == ["杭州"]
