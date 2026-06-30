from models import ProviderResult, ProviderStatus, TripRequest
from research_pipeline import DefaultResearchPipeline, ResearchDependencies


class FakeTrain:
    def __init__(self) -> None:
        self.calls = []

    def stations_for_city(self, city: str) -> list[str]:
        return [f"{city}一站", f"{city}二站", f"{city}三站"]

    def query(self, request: object) -> ProviderResult:
        self.calls.append(request)
        return ProviderResult(
            provider_id="train-12306",
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[{"service_id": "G100"}],
        )


class FakeFlight:
    def __init__(self) -> None:
        self.calls = []

    def resolve_airports(self, city: str) -> list[str]:
        return ["AAA", "AAB", "AAC"]

    def query(self, request: object) -> ProviderResult:
        self.calls.append(request)
        return ProviderResult(
            provider_id="flight-fli",
            status=ProviderStatus.NO_RESULTS,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[],
        )


class EmptyProvider:
    def query(self, request: object) -> ProviderResult:
        return ProviderResult(
            provider_id="empty",
            status=ProviderStatus.NO_RESULTS,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[],
        )


class EmptyResolver:
    def resolve(self, candidates: list, *, city: str):
        return [], ["no candidates"]


def make_request() -> TripRequest:
    return TripRequest(
        origin_city="深圳",
        destination="杭州",
        budget_cny=5000,
        departure_at="2026-07-10T08:00:00+08:00",
        duration_days=3,
        travelers=2,
        generation_mode="one_shot",
    )


def test_train_stops_after_first_usable_pair_and_flight_is_bounded(tmp_path) -> None:
    train = FakeTrain()
    flight = FakeFlight()
    candidate_path = tmp_path / "attraction_candidates.json"
    candidate_path.write_text("[]", encoding="utf-8")
    pipeline = DefaultResearchPipeline(
        ResearchDependencies(
            train=train,
            flight=flight,
            xhs=EmptyProvider(),
            hotels=EmptyProvider(),
            attraction_resolver=EmptyResolver(),
        ),
        attraction_candidates_path=candidate_path,
    )

    results = pipeline.collect(make_request())

    assert len(train.calls) == 1
    assert len(flight.calls) == 9
    assert "transport-train" in results
    assert "transport-flight" in results


def test_missing_candidate_file_is_reported(tmp_path) -> None:
    pipeline = DefaultResearchPipeline(
        ResearchDependencies(
            train=FakeTrain(),
            flight=FakeFlight(),
            xhs=EmptyProvider(),
            hotels=EmptyProvider(),
            attraction_resolver=EmptyResolver(),
        ),
        attraction_candidates_path=tmp_path / "missing.json",
    )

    result = pipeline.collect(make_request())["attractions-resolved"]

    assert result.status is ProviderStatus.NOT_CONFIGURED
    assert "attraction_candidates.json" in result.warnings[0]
