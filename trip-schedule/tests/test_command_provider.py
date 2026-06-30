import json
from subprocess import CompletedProcess

import pytest

from providers.command_provider import CommandRunner


def test_command_runner_never_uses_a_shell(monkeypatch) -> None:
    observed = {}

    def fake_run(args, **kwargs):
        observed["args"] = args
        observed["shell"] = kwargs.get("shell")
        return CompletedProcess(args=args, returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr("providers.command_provider.subprocess.run", fake_run)

    result = CommandRunner(["crawler"]).run({"destination": "杭州"})

    assert result == []
    assert observed == {
        "args": ["crawler", "--request-json", '{"destination": "杭州"}'],
        "shell": False,
    }


def test_command_runner_rejects_non_json_stdout(monkeypatch) -> None:
    monkeypatch.setattr(
        "providers.command_provider.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args=args,
            returncode=0,
            stdout="login required",
            stderr="",
        ),
    )

    with pytest.raises(ValueError, match="valid JSON"):
        CommandRunner(["crawler"]).run({"destination": "杭州"})
