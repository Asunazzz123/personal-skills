import json

from trip_schedule import main


def test_health_lists_all_first_release_providers(capsys) -> None:
    assert main(["health", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert set(payload) == {
        "train-12306",
        "flight-fli",
        "attractions-xhs",
        "hotels-external",
        "amap-webservice",
    }
