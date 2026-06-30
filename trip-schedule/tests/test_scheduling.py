from models import Attraction, SourceEvidence
from planning.scheduling import schedule_attractions


def make_evidence(source: str) -> SourceEvidence:
    return SourceEvidence(
        source=source,
        source_url="https://example.invalid/source",
        queried_at="2026-07-01T10:00:00+08:00",
        confidence=0.8,
    )


def attraction(name: str, latitude: float, longitude: float, minutes: int):
    return Attraction(
        name=name,
        description=name,
        latitude=latitude,
        longitude=longitude,
        ticket_price_cny=0,
        suggested_visit_minutes=minutes,
        evidence=[make_evidence("fixture")],
    )


def test_scheduler_keeps_nearby_attractions_on_the_same_day() -> None:
    schedules = schedule_attractions(
        [
            attraction("A", 30.250, 120.160, 180),
            attraction("B", 30.255, 120.165, 180),
            attraction("C", 30.320, 120.230, 240),
        ],
        duration_days=2,
        daily_visit_minutes=480,
    )

    assert [item.name for item in schedules[0].attractions] == ["A", "B"]
    assert [item.name for item in schedules[1].attractions] == ["C"]
