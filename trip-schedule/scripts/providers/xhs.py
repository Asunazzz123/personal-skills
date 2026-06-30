from __future__ import annotations

import json
import os
import subprocess
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


def _load_command(raw: str | None) -> tuple[list[str] | None, str | None]:
    if not raw:
        return None, None
    try:
        command = json.loads(raw)
    except json.JSONDecodeError:
        return None, "TRIP_XHS_COMMAND_JSON must be valid JSON."
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(item, str) for item in command)
    ):
        return None, "TRIP_XHS_COMMAND_JSON must be a non-empty JSON argv array of strings."
    return command, None


def _normalize_note(
    note: object,
    queried_at: datetime,
) -> tuple[dict[str, object] | None, str | None]:
    if not isinstance(note, dict):
        return None, "skipped XHS note because row is not an object"

    source_url = note.get("note_url")
    if not isinstance(source_url, str) or not source_url.strip():
        return None, "skipped XHS note because note_url is missing"

    likes = _count(note.get("liked_count"))
    collections = _count(note.get("collected_count"))
    comments = _count(note.get("comment_count"))
    return (
        {
            "title": str(note.get("title", "")),
            "description": str(note.get("desc", "")),
            "source_keyword": str(note.get("source_keyword", "")),
            "source_url": source_url,
            "queried_at": queried_at.isoformat(),
            "engagement_score": likes + 2 * collections + comments,
        },
        None,
    )


class XhsEvidenceProvider(Provider):
    provider_id = "attractions-xhs"

    def __init__(self) -> None:
        raw = os.getenv("TRIP_XHS_COMMAND_JSON")
        self.command, self.configuration_error = _load_command(raw)
        self.runner = None
        if self.command is not None:
            try:
                self.runner = CommandRunner(self.command)
            except ValueError as exc:
                self.command = None
                self.configuration_error = str(exc)

    def health_check(self) -> ProviderHealth:
        if self.runner is None:
            return ProviderHealth(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                detail=self.configuration_error
                or (
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
                warnings=[self.configuration_error] if self.configuration_error else [],
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
        except ValueError as exc:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.SCHEMA_CHANGED,
                queried_at=queried_at,
                records=[],
                warnings=[str(exc)],
                error_kind="external_crawler_schema",
            )
        except FileNotFoundError as exc:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                queried_at=queried_at,
                records=[],
                warnings=[str(exc)],
                error_kind="external_crawler_not_found",
            )
        except subprocess.TimeoutExpired:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NETWORK_ERROR,
                queried_at=queried_at,
                records=[],
                warnings=["external crawler timed out"],
                error_kind="external_crawler_timeout",
            )
        except OSError as exc:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NETWORK_ERROR,
                queried_at=queried_at,
                records=[],
                warnings=[str(exc)],
                error_kind="external_crawler_os_error",
            )

        if not isinstance(notes, list):
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.SCHEMA_CHANGED,
                queried_at=queried_at,
                records=[],
                warnings=["crawler output must be a JSON array of objects"],
                error_kind="external_crawler_schema",
            )

        records = []
        warnings = []
        for note in notes[: query.limit]:
            record, warning = _normalize_note(note, queried_at)
            if record is not None:
                records.append(record)
            if warning is not None:
                warnings.append(warning)

        status = ProviderStatus.OK if records else ProviderStatus.NO_RESULTS
        if notes and not records:
            status = ProviderStatus.SCHEMA_CHANGED
        return ProviderResult(
            provider_id=self.provider_id,
            status=status,
            queried_at=queried_at,
            records=records,
            warnings=warnings,
            error_kind="external_crawler_schema"
            if status is ProviderStatus.SCHEMA_CHANGED
            else None,
        )
