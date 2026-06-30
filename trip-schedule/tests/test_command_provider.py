import json
from subprocess import CompletedProcess

import pytest

from providers.command_provider import CommandRunner


@pytest.mark.parametrize("command", ["crawler", b"crawler"])
def test_command_runner_rejects_bare_string_commands(command) -> None:
    with pytest.raises(ValueError, match="argv"):
        CommandRunner(command)


def test_command_runner_rejects_non_string_argv_items() -> None:
    with pytest.raises(ValueError, match="argv"):
        CommandRunner(["crawler", 123])


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


def test_command_runner_redacts_sensitive_stderr(monkeypatch) -> None:
    stderr = (
        "cookie=secret; Authorization: Bearer abc.def; token=hidden; "
        "api_key=secret-key; password=pw; "
        '{"key": "json-secret", "authorization": "Bearer xyz.123"}'
    )

    monkeypatch.setattr(
        "providers.command_provider.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args=args,
            returncode=7,
            stdout="",
            stderr=stderr,
        ),
    )

    with pytest.raises(RuntimeError) as exc_info:
        CommandRunner(["crawler"]).run({"destination": "杭州"})

    message = str(exc_info.value)
    assert "crawler exited with 7" in message
    assert "[REDACTED]" in message
    for secret in (
        "secret",
        "abc.def",
        "hidden",
        "secret-key",
        "pw",
        "json-secret",
        "xyz.123",
    ):
        assert secret not in message


def test_command_runner_redacts_full_cookie_header(monkeypatch) -> None:
    monkeypatch.setattr(
        "providers.command_provider.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args=args,
            returncode=7,
            stdout="",
            stderr="Cookie: session=abc; csrf=def",
        ),
    )

    with pytest.raises(RuntimeError) as exc_info:
        CommandRunner(["crawler"]).run({"destination": "杭州"})

    message = str(exc_info.value)
    assert "crawler exited with 7" in message
    assert "[REDACTED]" in message
    assert "session=abc" not in message
    assert "csrf=def" not in message


def test_command_runner_redacts_non_bearer_authorization_header(monkeypatch) -> None:
    monkeypatch.setattr(
        "providers.command_provider.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args=args,
            returncode=7,
            stdout="",
            stderr="Authorization: Basic dXNlcjpwYXNz",
        ),
    )

    with pytest.raises(RuntimeError) as exc_info:
        CommandRunner(["crawler"]).run({"destination": "杭州"})

    message = str(exc_info.value)
    assert "crawler exited with 7" in message
    assert "[REDACTED]" in message
    assert "Basic dXNlcjpwYXNz" not in message
    assert "dXNlcjpwYXNz" not in message
