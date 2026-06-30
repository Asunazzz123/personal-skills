import json
from subprocess import CompletedProcess

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
            travelers=1,
        )
    )

    offer = TransportOffer.model_validate(result.records[0])
    assert offer.total_price_cny == 580
    assert offer.provider_id == "flight-fli"


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
