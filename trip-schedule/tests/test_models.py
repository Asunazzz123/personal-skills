from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from models import (
    GenerationMode,
    ProviderResult,
    ProviderStatus,
    SourceEvidence,
    TransportMode,
    TransportOffer,
    TripRequest,
)


def test_trip_request_requires_positive_budget_duration_and_travelers() -> None:
    with pytest.raises(ValidationError):
        TripRequest(
            origin_city="深圳",
            destination="广州",
            budget_cny=0,
            departure_at="2026-07-10T08:00:00+08:00",
            duration_days=0,
            travelers=0,
            generation_mode=GenerationMode.ONE_SHOT,
        )


def test_transport_offer_preserves_unknown_price() -> None:
    offer = TransportOffer(
        provider_id="train-12306",
        mode=TransportMode.TRAIN,
        service_id="G100",
        origin_name="深圳北",
        destination_name="广州南",
        departure_at="2026-07-10T08:00:00+08:00",
        arrival_at="2026-07-10T08:35:00+08:00",
        duration_minutes=35,
        total_price_cny=None,
        availability={"second_class": "有"},
        evidence=SourceEvidence(
            source="12306",
            source_url="https://kyfw.12306.cn/",
            queried_at="2026-07-01T10:00:00+08:00",
            confidence=0.9,
        ),
    )

    assert offer.total_price_cny is None
    assert offer.mode is TransportMode.TRAIN


def test_provider_result_rejects_naive_query_time() -> None:
    with pytest.raises(ValidationError):
        ProviderResult(
            provider_id="train-12306",
            status=ProviderStatus.OK,
            queried_at=datetime(2026, 7, 1, 10, 0),
            records=[],
        )
