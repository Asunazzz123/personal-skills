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
