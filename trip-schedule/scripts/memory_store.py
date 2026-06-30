from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path


MAX_STORED_STRING_LENGTH = 160

_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_SECRET_RE_LIST = [
    re.compile(
        r"\bauthorization\s*=\s*(?:Bearer\s+)?[^\s&;,]+(?:\s+[^\s&;,]+)?",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:token|api_key|password|cookie)\s*=\s*[^\s&;,]+", re.IGNORECASE),
]
_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def _default_payload() -> dict:
    return {
        "version": 1,
        "updated_at": None,
        "regions": {},
        "providers": {},
    }


def _is_valid_payload(payload: object) -> bool:
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("regions"), dict)
        and isinstance(payload.get("providers"), dict)
    )


def _sanitize_memory_string(value: str) -> str:
    sanitized = value.strip()
    sanitized = _URL_RE.sub("[url]", sanitized)
    for secret_re in _SECRET_RE_LIST:
        sanitized = secret_re.sub("[redacted]", sanitized)
    sanitized = _DATE_RE.sub("[date]", sanitized)
    sanitized = " ".join(sanitized.split())
    return sanitized[:MAX_STORED_STRING_LENGTH].rstrip()


def _sanitize_memory_strings(values: list[str]) -> list[str]:
    return list(dict.fromkeys(_sanitize_memory_string(value) for value in values))[:20]


class StrategyMemory:
    def __init__(
        self,
        path: Path,
        *,
        max_regions: int = 100,
        max_providers: int = 100,
    ) -> None:
        if max_regions <= 0:
            raise ValueError("max_regions must be positive")
        if max_providers <= 0:
            raise ValueError("max_providers must be positive")
        self.path = path
        self.max_regions = max_regions
        self.max_providers = max_providers

    def _load(self) -> dict:
        if not self.path.exists():
            return _default_payload()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return _default_payload()
        if not _is_valid_payload(payload):
            return _default_payload()
        payload.setdefault("version", 1)
        payload.setdefault("updated_at", None)
        return payload

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
            "query_keywords": _sanitize_memory_strings(query_keywords),
            "routing_notes": _sanitize_memory_strings(routing_notes),
            "updated_at": now,
        }
        while len(regions) > self.max_regions:
            regions.pop(next(iter(regions)))

        providers = payload["providers"]
        for provider_id, status in provider_events:
            provider = providers.pop(provider_id, None)
            if not isinstance(provider, dict):
                provider = {
                    "success_count": 0,
                    "failure_count": 0,
                    "last_status": None,
                }
            provider.setdefault("success_count", 0)
            provider.setdefault("failure_count", 0)
            provider.setdefault("last_status", None)
            status_counts = provider.setdefault("status_counts", {})
            if not isinstance(status_counts, dict):
                status_counts = {}
                provider["status_counts"] = status_counts

            key = "success_count" if status in {"ok", "partial"} else "failure_count"
            provider[key] += 1
            provider["last_status"] = status
            status_counts[status] = status_counts.get(status, 0) + 1
            provider["updated_at"] = now
            providers[provider_id] = provider
            while len(providers) > self.max_providers:
                providers.pop(next(iter(providers)))

        payload["updated_at"] = now
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return "Updated Trip Schedule's de-identified strategy memory."
