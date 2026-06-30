from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class StrategyMemory:
    def __init__(self, path: Path, *, max_regions: int = 100) -> None:
        self.path = path
        self.max_regions = max_regions

    def _load(self) -> dict:
        if not self.path.exists():
            return {
                "version": 1,
                "updated_at": None,
                "regions": {},
                "providers": {},
            }
        return json.loads(self.path.read_text(encoding="utf-8"))

    def record_run(
        self,
        *,
        region: str,
        query_keywords: list[str],
        provider_events: list[tuple[str, str]],
        routing_notes: list[str],
    ) -> str:
        payload = self._load()
        now = datetime.now().astimezone().isoformat()
        regions = payload["regions"]
        regions.pop(region, None)
        regions[region] = {
            "query_keywords": list(dict.fromkeys(query_keywords))[:20],
            "routing_notes": list(dict.fromkeys(routing_notes))[:20],
            "updated_at": now,
        }
        while len(regions) > self.max_regions:
            regions.pop(next(iter(regions)))

        for provider_id, status in provider_events:
            provider = payload["providers"].setdefault(
                provider_id,
                {"success_count": 0, "failure_count": 0, "last_status": None},
            )
            key = "success_count" if status in {"ok", "partial"} else "failure_count"
            provider[key] += 1
            provider["last_status"] = status
            provider["updated_at"] = now

        payload["updated_at"] = now
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return "Updated Trip Schedule's de-identified strategy memory."
