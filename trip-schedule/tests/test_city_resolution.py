import json
from subprocess import CompletedProcess

from providers.flight import FlightProvider
from providers.train_12306 import Train12306Provider


def test_train_provider_resolves_city_to_station_candidates() -> None:
    provider = Train12306Provider()

    stations = provider.stations_for_city("深圳")

    assert "深圳北" in stations
    assert len(stations) <= 5


def test_flight_provider_resolves_city_to_iata(monkeypatch) -> None:
    monkeypatch.setattr("providers.flight.shutil.which", lambda _: "/usr/bin/fli")
    monkeypatch.setattr(
        "providers.flight.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(
                [{"iata": "SZX", "name": "深圳宝安国际机场", "city": "深圳"}]
            ),
            stderr="",
        ),
    )

    assert FlightProvider().resolve_airports("深圳") == ["SZX"]
