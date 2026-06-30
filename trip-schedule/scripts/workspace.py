from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from models import TripRequest


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value.strip())
    return slug.strip("-") or "trip"


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
        root = output_root / f"{stamp}-{_safe_slug(request.destination)}"
        root.mkdir(parents=True, exist_ok=False)
        workspace = cls(root=root)
        workspace.request_path.write_text(
            request.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return workspace

    def write_json(self, filename: str, payload: object) -> Path:
        from pydantic import TypeAdapter

        path = self.root / filename
        data = TypeAdapter(object).dump_json(payload, indent=2)
        path.write_bytes(data)
        return path
