from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Sequence
from typing import Any


_SENSITIVE_KEYS = "authorization|api_key|password|cookie|token|key"


def _redact_sensitive_stderr(stderr: str) -> str:
    redacted = re.sub(
        r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+",
        "Bearer [REDACTED]",
        stderr,
    )
    redacted = re.sub(
        rf'(?i)(["\']?(?:{_SENSITIVE_KEYS})["\']?\s*:\s*["\'])([^"\']+)(["\'])',
        r"\1[REDACTED]\3",
        redacted,
    )
    redacted = re.sub(
        rf"(?i)\b({_SENSITIVE_KEYS})\b(\s*[=:]\s*)([^;\s,}}]+)",
        r"\1\2[REDACTED]",
        redacted,
    )
    return redacted[-1000:]


class CommandRunner:
    """Run an explicitly configured crawler wrapper without a shell."""

    def __init__(self, command: Sequence[str], *, timeout_seconds: int = 120) -> None:
        if isinstance(command, (str, bytes)):
            raise ValueError("crawler argv must be a non-empty sequence of strings")
        if not command:
            raise ValueError("crawler command must not be empty")
        if not all(isinstance(item, str) for item in command):
            raise ValueError("crawler argv must contain only strings")
        self.command = list(command)
        self.timeout_seconds = timeout_seconds

    def run(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        request_json = json.dumps(request, ensure_ascii=False)
        completed = subprocess.run(
            [*self.command, "--request-json", request_json],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            shell=False,
        )
        if completed.returncode != 0:
            stderr = _redact_sensitive_stderr(completed.stderr)
            raise RuntimeError(
                f"crawler exited with {completed.returncode}: {stderr}"
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("crawler stdout is not valid JSON") from exc
        if not isinstance(payload, list) or not all(
            isinstance(item, dict) for item in payload
        ):
            raise ValueError("crawler output must be a JSON array of objects")
        return payload
