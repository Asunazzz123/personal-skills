import json
from pathlib import Path

from models import ProviderStatus, TransportOffer
from providers.train_12306 import Train12306Provider, TrainQuery
from providers.train_support.ticket_client import parse_query_response


FIXTURE = Path(__file__).parent / "fixtures" / "12306-query.json"


def test_parse_query_response_preserves_unknown_price() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    rows = parse_query_response(payload, query_date="2026-07-10")

    assert rows[0]["service_id"] == "G100"
    assert rows[0]["origin_name"] == "深圳北"
    assert rows[0]["destination_name"] == "广州南"
    assert rows[0]["total_price_cny"] is None


def test_train_provider_normalizes_one_shot_result(monkeypatch) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    provider = Train12306Provider()
    monkeypatch.setattr(provider.client, "query", lambda **_: payload)

    result = provider.query(
        TrainQuery(
            origin_station="深圳北",
            destination_station="广州南",
            travel_date="2026-07-10",
        )
    )

    assert result.status is ProviderStatus.OK
    offer = TransportOffer.model_validate(result.records[0])
    assert offer.provider_id == "train-12306"


def test_parse_query_response_rolls_overnight_arrival_to_next_day() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parts = payload["data"]["result"][0].split("|")
    parts[8] = "23:50"
    parts[9] = "00:30"
    parts[10] = "00:40"
    payload["data"]["result"][0] = "|".join(parts)

    row = parse_query_response(payload, query_date="2026-07-31")[0]

    assert row["arrival_at"].startswith("2026-08-01T00:30")


def test_parse_query_response_uses_duration_for_multi_day_trip() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parts = payload["data"]["result"][0].split("|")
    parts[8] = "08:00"
    parts[9] = "09:00"
    parts[10] = "25:00"
    payload["data"]["result"][0] = "|".join(parts)

    row = parse_query_response(payload, query_date="2026-07-10")[0]

    assert row["arrival_at"].startswith("2026-07-11T09:00")
    assert row["duration_minutes"] == 25 * 60


def test_malformed_non_empty_result_maps_to_schema_changed(monkeypatch) -> None:
    provider = Train12306Provider()
    monkeypatch.setattr(
        provider.client,
        "query",
        lambda **_: {"data": {"map": {}, "result": ["too|short"]}},
    )

    result = provider.query(
        TrainQuery(
            origin_station="深圳北",
            destination_station="广州南",
            travel_date="2026-07-10",
        )
    )

    assert result.status is ProviderStatus.SCHEMA_CHANGED
    assert result.records == []
    assert result.error_kind == "ValueError"
    assert result.warnings


def test_provider_maps_unknown_station_to_structured_result() -> None:
    provider = Train12306Provider()

    result = provider.query(
        TrainQuery(
            origin_station="不存在站",
            destination_station="广州南",
            travel_date="2026-07-10",
        )
    )

    assert result.status is ProviderStatus.SCHEMA_CHANGED
    assert result.records == []
    assert result.error_kind == "ValueError"
    assert result.warnings


def test_provider_maps_repeated_redirect_to_structured_result(monkeypatch) -> None:
    provider = Train12306Provider()
    monkeypatch.setattr(
        provider.client,
        "query",
        lambda **_: (_ for _ in ()).throw(
            RuntimeError("12306 returned repeated c_url redirects")
        ),
    )

    result = provider.query(
        TrainQuery(
            origin_station="深圳北",
            destination_station="广州南",
            travel_date="2026-07-10",
        )
    )

    assert result.status is ProviderStatus.SCHEMA_CHANGED
    assert result.records == []
    assert result.error_kind == "RuntimeError"
    assert result.warnings


def test_ticket_client_follows_at_most_one_dynamic_query_url(monkeypatch) -> None:
    responses = iter(
        [
            {"c_url": "leftTicket/queryA"},
            {"data": {"result": [], "map": {}}},
        ]
    )
    provider = Train12306Provider()

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return next(responses)

    calls = []
    monkeypatch.setattr(
        provider.client.session,
        "get",
        lambda url, **kwargs: calls.append(url) or Response(),
    )

    payload = provider.client.query(
        origin_station="深圳北",
        destination_station="广州南",
        travel_date="2026-07-10",
    )

    assert payload["data"]["result"] == []
    assert calls == [
        "https://kyfw.12306.cn/otn/leftTicket/queryG",
        "https://kyfw.12306.cn/otn/leftTicket/queryA",
    ]
