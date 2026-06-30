from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel
from requests import RequestException

from models import (
    ProviderHealth,
    ProviderResult,
    ProviderStatus,
    SourceEvidence,
    TransportMode,
    TransportOffer,
)
from providers.base import Provider
from providers.train_support.station_index import StationIndex
from providers.train_support.ticket_client import TicketClient, parse_query_response


class TrainQuery(BaseModel):
    origin_station: str
    destination_station: str
    travel_date: date


class Train12306Provider(Provider):
    provider_id = "train-12306"

    def __init__(self) -> None:
        support_dir = Path(__file__).with_name("train_support")
        self.index = StationIndex(support_dir / "station.json")
        self.client = TicketClient(self.index)

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.OK,
            detail=f"{len(self.index.name_to_code)} stations loaded",
        )

    def query(self, request: object) -> ProviderResult:
        query = TrainQuery.model_validate(request)
        queried_at = datetime.now().astimezone()
        try:
            payload = self.client.query(
                origin_station=query.origin_station,
                destination_station=query.destination_station,
                travel_date=query.travel_date.isoformat(),
            )
            rows = parse_query_response(
                payload,
                query_date=query.travel_date.isoformat(),
            )
        except RequestException as exc:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NETWORK_ERROR,
                queried_at=queried_at,
                records=[],
                error_kind=type(exc).__name__,
                warnings=[str(exc)],
            )

        offers = [
            TransportOffer(
                provider_id=self.provider_id,
                mode=TransportMode.TRAIN,
                evidence=SourceEvidence(
                    source="12306",
                    source_url="https://kyfw.12306.cn/",
                    queried_at=queried_at,
                    confidence=0.9,
                ),
                **row,
            ).model_dump(mode="json")
            for row in rows
        ]
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.OK if offers else ProviderStatus.NO_RESULTS,
            queried_at=queried_at,
            records=offers,
        )
