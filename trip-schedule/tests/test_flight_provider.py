import json
from subprocess import CompletedProcess, TimeoutExpired

from models import ProviderStatus, TransportOffer
from providers.flight import FlightProvider, FlightQuery


FLIGHT_JSON = {
    "flights": [
        {
            "price": 580,
            "duration": 155,
            "stops": 0,
            "airline": "Example Air",
            "flight_number": "EA100",
            "departure_airport": "SZX",
            "arrival_airport": "SHA",
            "departure_datetime": "2026-07-10T08:00:00+08:00",
            "arrival_datetime": "2026-07-10T10:35:00+08:00",
        }
    ]
}


def test_flight_health_reports_missing_cli(monkeypatch) -> None:
    monkeypatch.setattr("providers.flight.shutil.which", lambda _: None)

    health = FlightProvider().health_check()

    assert health.status is ProviderStatus.NOT_CONFIGURED


def test_flight_provider_normalizes_cli_json(monkeypatch) -> None:
    calls = []

    def fake_run(*args, **kwargs) -> CompletedProcess:
        calls.append((args, kwargs))
        return CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(FLIGHT_JSON),
            stderr="",
        )

    monkeypatch.setattr("providers.flight.shutil.which", lambda _: "/usr/bin/fli")
    monkeypatch.setattr("providers.flight.subprocess.run", fake_run)

    result = FlightProvider().query(
        FlightQuery(
            origin_iata="SZX",
            destination_iata="SHA",
            departure_date="2026-07-10",
            travelers=1,
        )
    )

    offer = TransportOffer.model_validate(result.records[0])
    assert offer.total_price_cny == 580
    assert offer.provider_id == "flight-fli"
    assert calls[0][1]["timeout"] == 45
    assert calls[0][1].get("shell") is None


def test_flight_provider_multiplies_per_traveler_price(monkeypatch) -> None:
    monkeypatch.setattr("providers.flight.shutil.which", lambda _: "/usr/bin/fli")
    monkeypatch.setattr(
        "providers.flight.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(FLIGHT_JSON),
            stderr="",
        ),
    )

    result = FlightProvider().query(
        FlightQuery(
            origin_iata="SZX",
            destination_iata="SHA",
            departure_date="2026-07-10",
            travelers=2,
        )
    )

    offer = TransportOffer.model_validate(result.records[0])
    assert offer.total_price_cny == 1160


def test_flight_provider_reports_timeout_as_network_error(monkeypatch) -> None:
    monkeypatch.setattr("providers.flight.shutil.which", lambda _: "/usr/bin/fli")

    def raise_timeout(*args, **kwargs) -> CompletedProcess:
        raise TimeoutExpired(cmd=args[0], timeout=kwargs["timeout"])

    monkeypatch.setattr("providers.flight.subprocess.run", raise_timeout)

    result = FlightProvider().query(
        FlightQuery(
            origin_iata="SZX",
            destination_iata="SHA",
            departure_date="2026-07-10",
            travelers=1,
        )
    )

    assert result.status is ProviderStatus.NETWORK_ERROR
    assert result.records == []
    assert result.error_kind == "TimeoutExpired"
    assert result.warnings


def test_flight_provider_reports_file_not_found_as_not_configured(
    monkeypatch,
) -> None:
    monkeypatch.setattr("providers.flight.shutil.which", lambda _: "/usr/bin/fli")

    def raise_file_not_found(*args, **kwargs) -> CompletedProcess:
        raise FileNotFoundError("fli")

    monkeypatch.setattr("providers.flight.subprocess.run", raise_file_not_found)

    result = FlightProvider().query(
        FlightQuery(
            origin_iata="SZX",
            destination_iata="SHA",
            departure_date="2026-07-10",
            travelers=1,
        )
    )

    assert result.status is ProviderStatus.NOT_CONFIGURED
    assert result.records == []
    assert result.error_kind == "FileNotFoundError"
    assert result.warnings


def test_flight_provider_reports_schema_change(monkeypatch) -> None:
    monkeypatch.setattr("providers.flight.shutil.which", lambda _: "/usr/bin/fli")
    monkeypatch.setattr(
        "providers.flight.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args=args,
            returncode=0,
            stdout='{"unexpected": true}',
            stderr="",
        ),
    )

    result = FlightProvider().query(
        FlightQuery(
            origin_iata="SZX",
            destination_iata="SHA",
            departure_date="2026-07-10",
            travelers=1,
        )
    )

    assert result.status is ProviderStatus.SCHEMA_CHANGED


def test_flight_provider_resolves_airports_with_installed_fli_cli(
    monkeypatch,
) -> None:
    calls = []

    def fake_run(*args, **kwargs) -> CompletedProcess:
        calls.append(args[0])
        return CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(
                [
                    {
                        "code": "SZX",
                        "name": "Shenzhen Bao'an International Airport",
                        "match_type": "name",
                    }
                ]
            ),
            stderr="",
        )

    monkeypatch.setattr("providers.flight.shutil.which", lambda _: "/usr/bin/fli")
    monkeypatch.setattr("providers.flight.subprocess.run", fake_run)

    assert FlightProvider().resolve_airports("Shenzhen") == ["SZX"]
    assert calls[0] == ["fli", "airports", "Shenzhen", "--json"]


def test_flight_provider_resolves_common_chinese_city_aliases(
    monkeypatch,
) -> None:
    monkeypatch.setattr("providers.flight.shutil.which", lambda _: "/usr/bin/fli")

    assert FlightProvider().resolve_airports("深圳") == ["SZX"]
    assert FlightProvider().resolve_airports("张家界") == ["DYG"]
