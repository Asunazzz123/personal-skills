from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from models import (
    ProviderHealth,
    ProviderResult,
    ProviderStatus,
    SourceEvidence,
    TransportMode,
    TransportOffer,
)
from providers.base import Provider


class FlightQuery(BaseModel):
    origin_iata: str = Field(pattern=r"^[A-Z]{3}$")
    destination_iata: str = Field(pattern=r"^[A-Z]{3}$")
    departure_date: date
    travelers: int = Field(gt=0)


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("flights", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise ValueError("unsupported fli JSON schema")


class FlightProvider(Provider):
    provider_id = "flight-fli"

    def health_check(self) -> ProviderHealth:
        path = shutil.which("fli")
        if path is None:
            return ProviderHealth(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                detail="fli CLI is not installed; no installation was attempted",
            )
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.OK,
            detail=path,
        )

    def query(self, request: object) -> ProviderResult:
        query = FlightQuery.model_validate(request)
        queried_at = datetime.now().astimezone()
        if shutil.which("fli") is None:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                queried_at=queried_at,
                records=[],
                warnings=["Install requirements.txt after explicit user approval."],
            )

        try:
            completed = subprocess.run(
                [
                    "fli",
                    "flights",
                    query.origin_iata,
                    query.destination_iata,
                    query.departure_date.isoformat(),
                    "--currency",
                    "CNY",
                    "--language",
                    "zh-CN",
                    "--country",
                    "CN",
                    "--format",
                    "json",
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=45,
            )
        except subprocess.TimeoutExpired as exc:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NETWORK_ERROR,
                queried_at=queried_at,
                records=[],
                error_kind=type(exc).__name__,
                warnings=[str(exc)],
            )
        except FileNotFoundError as exc:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                queried_at=queried_at,
                records=[],
                error_kind=type(exc).__name__,
                warnings=[str(exc)],
            )
        except OSError as exc:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NETWORK_ERROR,
                queried_at=queried_at,
                records=[],
                error_kind=type(exc).__name__,
                warnings=[str(exc)],
            )
        if completed.returncode != 0:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NETWORK_ERROR,
                queried_at=queried_at,
                records=[],
                error_kind="fli_exit",
                warnings=[completed.stderr[-1000:]],
            )

        try:
            raw_records = _records(json.loads(completed.stdout))
            offers = [
                self._normalize(row, queried_at, query.travelers)
                for row in raw_records
            ]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.SCHEMA_CHANGED,
                queried_at=queried_at,
                records=[],
                error_kind=type(exc).__name__,
                warnings=[str(exc)],
            )

        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.OK if offers else ProviderStatus.NO_RESULTS,
            queried_at=queried_at,
            records=[offer.model_dump(mode="json") for offer in offers],
        )

    def _normalize(
        self,
        row: dict[str, Any],
        queried_at: datetime,
        travelers: int,
    ) -> TransportOffer:
        return TransportOffer(
            provider_id=self.provider_id,
            mode=TransportMode.FLIGHT,
            service_id=str(row["flight_number"]),
            origin_name=str(row["departure_airport"]),
            destination_name=str(row["arrival_airport"]),
            departure_at=row["departure_datetime"],
            arrival_at=row["arrival_datetime"],
            duration_minutes=int(row["duration"]),
            total_price_cny=float(row["price"]) * travelers,
            transfers=int(row.get("stops", 0)),
            booking_url=row.get("booking_url"),
            evidence=SourceEvidence(
                source="Google Flights via fli",
                source_url="https://www.google.com/travel/flights",
                queried_at=queried_at,
                confidence=0.75,
            ),
        )
