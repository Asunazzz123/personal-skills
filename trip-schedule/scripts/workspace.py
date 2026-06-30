from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from models import TripRequest


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value.strip())
    return slug.strip("-") or "trip"


def _safe_component(value: str, field_name: str) -> str:
    path = Path(value)
    if (
        not value
        or path.is_absolute()
        or path.name != value
        or any(part == ".." for part in path.parts)
    ):
        raise ValueError(f"{field_name} must be a safe path component")
    return value


@dataclass(frozen=True)
class TripWorkspace:
    root: Path

    @property
    def request_path(self) -> Path:
        return self.root / "request.json"

    @classmethod
    def create(
        cls,
        output_root: Path,
        request: TripRequest,
        *,
        timestamp: str | None = None,
    ) -> "TripWorkspace":
        stamp = timestamp or datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
        stamp = _safe_component(stamp, "timestamp")
        base_name = f"{stamp}-{_safe_slug(request.destination)}"
        root = output_root / base_name
        suffix = 2
        while root.exists():
            root = output_root / f"{base_name}-{suffix}"
            suffix += 1
        root.mkdir(parents=True, exist_ok=False)
        workspace = cls(root=root)
        workspace.request_path.write_text(
            request.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return workspace

    def write_json(self, filename: str, payload: object) -> Path:
        from pydantic import TypeAdapter

        output_path = Path(filename)
        if output_path.is_absolute() or any(part == ".." for part in output_path.parts):
            raise ValueError("filename must stay inside the workspace")

        path = self.root / output_path
        data = TypeAdapter(object).dump_json(payload, indent=2)
        path.write_bytes(data)
        return path
