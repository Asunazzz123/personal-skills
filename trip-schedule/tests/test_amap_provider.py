import json
from pathlib import Path

import requests

from models import ProviderStatus
from providers.amap import AMapProvider


ROUTE_FIXTURE = Path(__file__).parent / "fixtures" / "amap-routes.json"


def test_amap_health_requires_webservice_key(monkeypatch) -> None:
    monkeypatch.delenv("AMAP_WEBSERVICE_KEY", raising=False)

    assert AMapProvider().health_check().status is ProviderStatus.NOT_CONFIGURED


def test_amap_error_does_not_expose_key(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")
    provider = AMapProvider()

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "0", "info": "INVALID_USER_KEY"}

    monkeypatch.setattr(provider.session, "get", lambda *args, **kwargs: Response())

    result = provider.geocode("杭州西湖")

    assert result.status is ProviderStatus.AUTHENTICATION_FAILED
    assert "secret-value" not in result.model_dump_json()


def test_amap_error_info_sanitizes_configured_key(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")
    provider = AMapProvider()

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "0", "info": "INVALID_USER_KEY secret-value"}

    monkeypatch.setattr(provider.session, "get", lambda *args, **kwargs: Response())

    result = provider.geocode("杭州西湖")

    assert result.status is ProviderStatus.AUTHENTICATION_FAILED
    assert "secret-value" not in result.model_dump_json()


def test_amap_request_exception_does_not_expose_key(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")
    provider = AMapProvider()

    def fail(*args, **kwargs):
        raise requests.RequestException(
            "boom https://restapi.amap.com/v3/geocode/geo?key=secret-value"
        )

    monkeypatch.setattr(provider.session, "get", fail)

    result = provider.geocode("杭州西湖")
    payload = result.model_dump_json()

    assert result.status is ProviderStatus.NETWORK_ERROR
    assert result.error_kind == "amap_request_error"
    assert "secret-value" not in payload
    assert "key=secret-value" not in payload


def test_amap_timeout_maps_to_network_error(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")
    provider = AMapProvider()

    def fail(*args, **kwargs):
        raise requests.Timeout("timeout key=secret-value")

    monkeypatch.setattr(provider.session, "get", fail)

    result = provider.geocode("杭州西湖")
    payload = result.model_dump_json()

    assert result.status is ProviderStatus.NETWORK_ERROR
    assert result.error_kind == "amap_timeout"
    assert "secret-value" not in payload


def test_amap_invalid_json_maps_to_schema_changed(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")
    provider = AMapProvider()

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            raise ValueError("invalid json key=secret-value")

    monkeypatch.setattr(provider.session, "get", lambda *args, **kwargs: Response())

    result = provider.geocode("杭州西湖")
    payload = result.model_dump_json()

    assert result.status is ProviderStatus.SCHEMA_CHANGED
    assert result.error_kind == "amap_invalid_json"
    assert "secret-value" not in payload


def test_amap_geocode_invalid_location_schema_changed(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")
    provider = AMapProvider()

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "1",
                "geocodes": [
                    {"formatted_address": "bad", "location": "not-a-coordinate"}
                ],
            }

    monkeypatch.setattr(provider.session, "get", lambda *args, **kwargs: Response())

    result = provider.geocode("杭州西湖")

    assert result.status is ProviderStatus.SCHEMA_CHANGED
    assert result.records == []


class RouteResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_amap_driving_route_extracts_distance_duration_and_path(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")
    payload = json.loads(ROUTE_FIXTURE.read_text(encoding="utf-8"))["driving"]
    provider = AMapProvider()
    monkeypatch.setattr(
        provider.session,
        "get",
        lambda *args, **kwargs: RouteResponse(payload),
    )

    result = provider.route_driving((120.1, 30.2), (120.15, 30.25))

    assert result.records[0]["distance_meters"] == 8200
    assert result.records[0]["duration_minutes"] == 25
    assert result.records[0]["path"] == [
        [120.1, 30.2],
        [120.15, 30.25],
    ]


def test_amap_transit_route_extracts_cost(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")
    payload = json.loads(ROUTE_FIXTURE.read_text(encoding="utf-8"))["transit"]
    provider = AMapProvider()
    monkeypatch.setattr(
        provider.session,
        "get",
        lambda *args, **kwargs: RouteResponse(payload),
    )

    result = provider.route_transit(
        (120.1, 30.2),
        (120.15, 30.25),
        city="杭州",
    )

    assert result.records[0]["estimated_cost_cny"] == 6
    assert result.records[0]["duration_minutes"] == 45


def test_amap_route_request_exception_does_not_expose_key(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")
    provider = AMapProvider()

    def fail(*args, **kwargs):
        raise requests.RequestException("route failed key=secret-value")

    monkeypatch.setattr(provider.session, "get", fail)

    result = provider.route_driving((120.1, 30.2), (120.15, 30.25))
    payload = result.model_dump_json()

    assert result.status is ProviderStatus.NETWORK_ERROR
    assert result.error_kind == "amap_request_error"
    assert "secret-value" not in payload
    assert "key=secret-value" not in payload
