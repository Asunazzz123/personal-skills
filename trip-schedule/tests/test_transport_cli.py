import json

from trip_schedule import main


def test_health_command_emits_provider_json(capsys) -> None:
    exit_code = main(["health", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert "train-12306" in payload
    assert "flight-fli" in payload
