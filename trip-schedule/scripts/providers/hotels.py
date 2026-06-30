from __future__ import annotations

import json
import os
import subprocess
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from models import (
    HotelOption,
    ProviderHealth,
    ProviderResult,
    ProviderStatus,
    SourceEvidence,
)
from providers.base import Provider
from providers.command_provider import CommandRunner


def _load_command(raw: str | None) -> tuple[list[str] | None, str | None]:
    if not raw:
        return None, None
    try:
        command = json.loads(raw)
    except json.JSONDecodeError:
        return None, "TRIP_HOTEL_COMMAND_JSON must be valid JSON."
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(item, str) for item in command)
    ):
        return (
            None,
            "TRIP_HOTEL_COMMAND_JSON must be a non-empty JSON argv array of strings.",
        )
    return command, None


class HotelQuery(BaseModel):
    destination: str
    check_in: date
    check_out: date
    travelers: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_dates(self) -> "HotelQuery":
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        return self


def _normalize_hotel(
    row: object,
    query: HotelQuery,
    queried_at: datetime,
) -> tuple[HotelOption | None, str | None]:
    if not isinstance(row, dict):
        return None, "skipped hotel because row is not an object"

    source = row.get("source")
    if not isinstance(source, str) or not source.strip():
        return None, "skipped hotel because source is missing"

    source_url = row.get("source_url")
    if not isinstance(source_url, str) or not source_url.strip():
        return None, "skipped hotel because source_url is missing"

    try:
        hotel = HotelOption(
            name=row["name"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            address=row.get("address"),
            total_price_cny=row.get("total_price_cny"),
            nights=(query.check_out - query.check_in).days,
            rating=row.get("rating"),
            review_count=row.get("review_count"),
            transit_notes=row.get("transit_notes", []),
            evidence=[
                SourceEvidence(
                    source=source.strip(),
                    source_url=source_url.strip(),
                    queried_at=queried_at,
                    confidence=0.75,
                )
            ],
        )
    except (KeyError, TypeError, ValueError) as exc:
        return None, f"skipped hotel because row is invalid: {exc}"
    return hotel, None


class HotelProvider(Provider):
    provider_id = "hotels-external"

    def __init__(self) -> None:
        raw = os.getenv("TRIP_HOTEL_COMMAND_JSON")
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
                    "Set TRIP_HOTEL_COMMAND_JSON to an approved JSON argv array; "
                    "no crawler was installed automatically."
                ),
            )
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.OK,
            detail="external hotel wrapper configured",
        )

    def query(self, request: object) -> ProviderResult:
        query = HotelQuery.model_validate(request)
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
            rows = self.runner.run(query.model_dump(mode="json"))
        except RuntimeError:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.CHALLENGE_REQUIRED,
                queried_at=queried_at,
                records=[],
                warnings=["external hotel crawler failed"],
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
        except FileNotFoundError:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                queried_at=queried_at,
                records=[],
                warnings=["external hotel crawler executable was not found"],
                error_kind="external_crawler_not_found",
            )
        except subprocess.TimeoutExpired:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NETWORK_ERROR,
                queried_at=queried_at,
                records=[],
                warnings=["external hotel crawler timed out"],
                error_kind="external_crawler_timeout",
            )
        except OSError:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NETWORK_ERROR,
                queried_at=queried_at,
                records=[],
                warnings=["external hotel crawler OS error"],
                error_kind="external_crawler_os_error",
            )

        if not isinstance(rows, list):
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.SCHEMA_CHANGED,
                queried_at=queried_at,
                records=[],
                warnings=["crawler output must be a JSON array of objects"],
                error_kind="external_crawler_schema",
            )

        hotels = []
        warnings = []
        for row in rows:
            hotel, warning = _normalize_hotel(row, query, queried_at)
            if hotel is not None:
                hotels.append(hotel)
            if warning is not None:
                warnings.append(warning)

        status = ProviderStatus.OK if hotels else ProviderStatus.NO_RESULTS
        if rows and not hotels:
            status = ProviderStatus.SCHEMA_CHANGED
        return ProviderResult(
            provider_id=self.provider_id,
            status=status,
            queried_at=queried_at,
            records=[hotel.model_dump(mode="json") for hotel in hotels],
            warnings=warnings,
            error_kind="external_crawler_schema"
            if status is ProviderStatus.SCHEMA_CHANGED
            else None,
        )
