import subprocess

from models import HotelOption, ProviderStatus
from providers.hotels import HotelProvider, HotelQuery


def test_hotel_provider_requires_configured_wrapper(monkeypatch) -> None:
    monkeypatch.delenv("TRIP_HOTEL_COMMAND_JSON", raising=False)

    assert HotelProvider().health_check().status is ProviderStatus.NOT_CONFIGURED


def test_hotel_provider_validates_total_stay_price(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_HOTEL_COMMAND_JSON", '["hotel-wrapper"]')
    provider = HotelProvider()
    monkeypatch.setattr(
        provider.runner,
        "run",
        lambda _: [
            {
                "name": "湖滨示例酒店",
                "latitude": 30.257,
                "longitude": 120.164,
                "total_price_cny": 920,
                "nights": 99,
                "source": "configured-hotel-crawler",
                "source_url": "https://example.invalid/hotel/1",
            }
        ],
    )

    result = provider.query(
        HotelQuery(
            destination="杭州",
            check_in="2026-07-10",
            check_out="2026-07-12",
            travelers=2,
        )
    )

    hotel = HotelOption.model_validate(result.records[0])
    assert hotel.total_price_cny == 920
    assert hotel.nights == 2


def test_hotel_provider_reports_invalid_command_json_without_leaking_config(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIP_HOTEL_COMMAND_JSON", "not-json-secret-token")

    health = HotelProvider().health_check()

    assert health.status is ProviderStatus.NOT_CONFIGURED
    assert "not-json-secret-token" not in health.detail


def test_hotel_provider_reports_non_list_command_json(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_HOTEL_COMMAND_JSON", '{"cmd":"hotel"}')

    health = HotelProvider().health_check()

    assert health.status is ProviderStatus.NOT_CONFIGURED


def test_hotel_provider_maps_schema_error_to_schema_changed(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_HOTEL_COMMAND_JSON", '["hotel-wrapper"]')
    provider = HotelProvider()

    def fail(_):
        raise ValueError("crawler output must be a JSON array of objects")

    monkeypatch.setattr(provider.runner, "run", fail)

    result = provider.query(
        HotelQuery(
            destination="杭州",
            check_in="2026-07-10",
            check_out="2026-07-12",
            travelers=2,
        )
    )

    assert result.status is ProviderStatus.SCHEMA_CHANGED
    assert result.error_kind == "external_crawler_schema"


def test_hotel_provider_maps_wrapper_failure_to_challenge_required(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIP_HOTEL_COMMAND_JSON", '["hotel-wrapper"]')
    provider = HotelProvider()

    def fail(_):
        raise RuntimeError("crawler exited with 1: login required")

    monkeypatch.setattr(provider.runner, "run", fail)

    result = provider.query(
        HotelQuery(
            destination="杭州",
            check_in="2026-07-10",
            check_out="2026-07-12",
            travelers=2,
        )
    )

    assert result.status is ProviderStatus.CHALLENGE_REQUIRED
    assert result.error_kind == "external_crawler_failed"


def test_hotel_provider_maps_missing_executable_to_not_configured(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIP_HOTEL_COMMAND_JSON", '["hotel-wrapper"]')
    provider = HotelProvider()

    def fail(_):
        raise FileNotFoundError("hotel-wrapper")

    monkeypatch.setattr(provider.runner, "run", fail)

    result = provider.query(
        HotelQuery(
            destination="杭州",
            check_in="2026-07-10",
            check_out="2026-07-12",
            travelers=2,
        )
    )

    assert result.status is ProviderStatus.NOT_CONFIGURED
    assert result.error_kind == "external_crawler_not_found"


def test_hotel_provider_redacts_timeout_command_arguments(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_HOTEL_COMMAND_JSON", '["hotel-wrapper"]')
    provider = HotelProvider()

    def fail(_):
        raise subprocess.TimeoutExpired(
            ["hotel-wrapper", "--request-json", '{"token":"secret"}'],
            120,
        )

    monkeypatch.setattr(provider.runner, "run", fail)

    result = provider.query(
        HotelQuery(
            destination="杭州",
            check_in="2026-07-10",
            check_out="2026-07-12",
            travelers=2,
        )
    )
    payload = result.model_dump_json()

    assert result.status is ProviderStatus.NETWORK_ERROR
    assert result.error_kind == "external_crawler_timeout"
    assert "--request-json" not in payload
    assert "secret" not in payload


def test_hotel_provider_skips_invalid_rows(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_HOTEL_COMMAND_JSON", '["hotel-wrapper"]')
    provider = HotelProvider()
    monkeypatch.setattr(
        provider.runner,
        "run",
        lambda _: [
            "not a row",
            {
                "name": "缺少来源链接酒店",
                "latitude": 30.257,
                "longitude": 120.164,
                "source": "configured-hotel-crawler",
            },
        ],
    )

    result = provider.query(
        HotelQuery(
            destination="杭州",
            check_in="2026-07-10",
            check_out="2026-07-12",
            travelers=2,
        )
    )

    assert result.status is ProviderStatus.SCHEMA_CHANGED
    assert result.records == []
    assert result.warnings


def test_hotel_provider_skips_invalid_rows_but_keeps_valid_rows(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRIP_HOTEL_COMMAND_JSON", '["hotel-wrapper"]')
    provider = HotelProvider()
    monkeypatch.setattr(
        provider.runner,
        "run",
        lambda _: [
            "not a row",
            {
                "name": "湖滨示例酒店",
                "latitude": 30.257,
                "longitude": 120.164,
                "total_price_cny": 920,
                "source": "configured-hotel-crawler",
                "source_url": "https://example.invalid/hotel/1",
            },
        ],
    )

    result = provider.query(
        HotelQuery(
            destination="杭州",
            check_in="2026-07-10",
            check_out="2026-07-12",
            travelers=2,
        )
    )

    hotel = HotelOption.model_validate(result.records[0])
    assert result.status is ProviderStatus.OK
    assert hotel.name == "湖滨示例酒店"
    assert result.warnings


def test_hotel_provider_rejects_blank_source_url(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_HOTEL_COMMAND_JSON", '["hotel-wrapper"]')
    provider = HotelProvider()
    monkeypatch.setattr(
        provider.runner,
        "run",
        lambda _: [
            {
                "name": "湖滨示例酒店",
                "latitude": 30.257,
                "longitude": 120.164,
                "source": "configured-hotel-crawler",
                "source_url": "   ",
            }
        ],
    )

    result = provider.query(
        HotelQuery(
            destination="杭州",
            check_in="2026-07-10",
            check_out="2026-07-12",
            travelers=2,
        )
    )

    assert result.status is ProviderStatus.SCHEMA_CHANGED
    assert result.records == []
    assert result.warnings
