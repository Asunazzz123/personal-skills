from __future__ import annotations

import json
import os
from datetime import datetime

from pydantic import BaseModel, Field

from models import ProviderHealth, ProviderResult, ProviderStatus
from providers.base import Provider
from providers.command_provider import CommandRunner


class XhsQuery(BaseModel):
    destination: str
    limit: int = Field(default=20, ge=1, le=50)


def _count(value: object) -> int:
    try:
        return int(str(value or "0").replace(",", ""))
    except ValueError:
        return 0


class XhsEvidenceProvider(Provider):
    provider_id = "attractions-xhs"

    def __init__(self) -> None:
        raw = os.getenv("TRIP_XHS_COMMAND_JSON")
        self.command = json.loads(raw) if raw else None
        self.runner = CommandRunner(self.command) if self.command else None

    def health_check(self) -> ProviderHealth:
        if self.runner is None:
            return ProviderHealth(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                detail=(
                    "Set TRIP_XHS_COMMAND_JSON to an approved JSON argv array; "
                    "no crawler was installed automatically."
                ),
            )
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.OK,
            detail="external crawler wrapper configured",
        )

    def query(self, request: object) -> ProviderResult:
        query = XhsQuery.model_validate(request)
        queried_at = datetime.now().astimezone()
        if self.runner is None:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                queried_at=queried_at,
                records=[],
            )
        try:
            notes = self.runner.run(
                {
                    "destination": query.destination,
                    "keywords": [
                        f"{query.destination} 景点",
                        f"{query.destination} 旅游攻略",
                    ],
                    "limit": query.limit,
                }
            )
        except RuntimeError as exc:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.CHALLENGE_REQUIRED,
                queried_at=queried_at,
                records=[],
                warnings=[str(exc)],
                error_kind="external_crawler_failed",
            )

        records = []
        for note in notes[: query.limit]:
            likes = _count(note.get("liked_count"))
            collections = _count(note.get("collected_count"))
            comments = _count(note.get("comment_count"))
            records.append(
                {
                    "title": str(note.get("title", "")),
                    "description": str(note.get("desc", "")),
                    "source_keyword": str(note.get("source_keyword", "")),
                    "source_url": str(note["note_url"]),
                    "queried_at": queried_at.isoformat(),
                    "engagement_score": likes + 2 * collections + comments,
                }
            )
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.OK if records else ProviderStatus.NO_RESULTS,
            queried_at=queried_at,
            records=records,
        )
