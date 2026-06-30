from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from typing import Any


class CommandRunner:
    """Run an explicitly configured crawler wrapper without a shell."""

    def __init__(self, command: Sequence[str], *, timeout_seconds: int = 120) -> None:
        if not command:
            raise ValueError("crawler command must not be empty")
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
            stderr = completed.stderr[-1000:]
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
