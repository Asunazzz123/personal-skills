from pathlib import Path

from models import ProviderResult, ProviderStatus, TripRequest
from orchestrator import Orchestrator, OrchestratorDependencies
from planning.engine import PlanningEngine
from test_planning_engine import make_inputs


class StaticResearch:
    def __init__(self, *, failed_provider: str | None = None) -> None:
        self.inputs = make_inputs()
        self.failed_provider = failed_provider

    def collect(self, request: TripRequest) -> dict[str, ProviderResult]:
        groups = {
            "transport-fixture": [
                item.model_dump(mode="json") for item in self.inputs.transports
            ],
            "hotels-fixture": [
                item.model_dump(mode="json")
                for item in {
                    hotel.name: hotel
                    for option in self.inputs.hotel_stage_options
                    for hotel in option.hotels
                }.values()
            ],
            "attractions-fixture": [
                item.model_dump(mode="json") for item in self.inputs.attractions
            ],
        }
        results = {
            provider_id: ProviderResult(
                provider_id=provider_id,
                status=ProviderStatus.OK,
                queried_at="2026-07-01T10:00:00+08:00",
                records=records,
            )
            for provider_id, records in groups.items()
        }
        if self.failed_provider:
            results[self.failed_provider] = ProviderResult(
                provider_id=self.failed_provider,
                status=ProviderStatus.NETWORK_ERROR,
                queried_at="2026-07-01T10:00:00+08:00",
                records=[],
                error_kind="fixture_failure",
            )
        return results


class StaticRouteBuilder:
    def build(
        self,
        request: TripRequest,
        research: dict[str, ProviderResult],
    ) -> dict[str, list]:
        routes_by_hotel = {}
        for option in make_inputs().hotel_stage_options:
            for hotel in option.hotels:
                routes_by_hotel[hotel.name] = [
                    route
                    for route in option.routes
                    if route.origin_name == hotel.name
                ]
        return routes_by_hotel


def make_dependencies(
    *,
    failed_provider: str | None = None,
) -> OrchestratorDependencies:
    return OrchestratorDependencies(
        research=StaticResearch(failed_provider=failed_provider),
        route_builder=StaticRouteBuilder(),
        planner=PlanningEngine(),
    )


def test_one_shot_orchestrator_writes_required_artifacts(tmp_path) -> None:
    orchestrator = Orchestrator(make_dependencies())
    request = TripRequest.model_validate_json(
        (
            Path(__file__).parent / "fixtures" / "full-trip-input.json"
        ).read_text(encoding="utf-8")
    )

    result = orchestrator.run(request, output_root=tmp_path)

    assert result.primary_plan is not None
    assert {
        "request.json",
        "attractions.json",
        "transport.json",
        "hotels.json",
        "routes.geojson",
        "plan.json",
        "provider-report.json",
    } <= {path.name for path in result.workspace.root.iterdir()}


def test_partial_provider_failure_is_visible(tmp_path) -> None:
    dependencies = make_dependencies(
        failed_provider="attractions-xhs",
    )
    request = TripRequest.model_validate_json(
        (
            Path(__file__).parent / "fixtures" / "full-trip-input.json"
        ).read_text(encoding="utf-8")
    )

    result = Orchestrator(dependencies).run(request, output_root=tmp_path)

    report = (result.workspace.root / "provider-report.json").read_text(
        encoding="utf-8"
    )
    assert "attractions-xhs" in report
    assert "network_error" in report
