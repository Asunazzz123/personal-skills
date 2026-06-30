from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from models import CandidatePlan, ProviderResult, TripRequest
from planning.engine import PlanningEngine, PlanningInputs, PlanningResult
from workspace import TripWorkspace


class ResearchPipeline(Protocol):
    def collect(self, request: TripRequest) -> dict[str, ProviderResult]:
        ...


class RouteBuilder(Protocol):
    def build(
        self,
        request: TripRequest,
        research: dict[str, ProviderResult],
    ) -> dict[str, list]:
        ...


@dataclass(frozen=True)
class OrchestratorDependencies:
    research: ResearchPipeline
    route_builder: RouteBuilder
    planner: PlanningEngine


@dataclass(frozen=True)
class OrchestratorResult:
    workspace: TripWorkspace
    plans: list[CandidatePlan]

    @property
    def primary_plan(self) -> CandidatePlan | None:
        return self.plans[0] if self.plans else None


class Orchestrator:
    def __init__(self, dependencies: OrchestratorDependencies) -> None:
        self.dependencies = dependencies

    def run(self, request: TripRequest, *, output_root: Path) -> OrchestratorResult:
        workspace = TripWorkspace.create(output_root, request)
        research = self.dependencies.research.collect(request)
        routes_by_hotel = self.dependencies.route_builder.build(request, research)
        inputs = self._planning_inputs(request, research, routes_by_hotel)
        planning_result: PlanningResult = self.dependencies.planner.build(inputs)

        self._write_records(workspace, "attractions.json", research, "attractions")
        self._write_records(workspace, "transport.json", research, "transport")
        self._write_records(workspace, "hotels.json", research, "hotels")
        workspace.write_json("plan.json", planning_result.model_dump(mode="json"))
        workspace.write_json(
            "provider-report.json",
            {
                provider_id: {
                    "status": result.status,
                    "warnings": result.warnings,
                    "error_kind": result.error_kind,
                    "queried_at": result.queried_at,
                }
                for provider_id, result in research.items()
            },
        )
        primary_routes = planning_result.plans[0].routes if planning_result.plans else []
        self._write_geojson(workspace, primary_routes)
        return OrchestratorResult(workspace=workspace, plans=planning_result.plans)

    def _write_records(
        self,
        workspace: TripWorkspace,
        filename: str,
        research: dict[str, ProviderResult],
        category: str,
    ) -> None:
        records = [
            record
            for provider_id, result in research.items()
            if provider_id.startswith(category)
            for record in result.records
        ]
        workspace.write_json(filename, records)

    def _planning_inputs(
        self,
        request: TripRequest,
        research: dict[str, ProviderResult],
        routes_by_hotel: dict[str, list],
    ) -> PlanningInputs:
        from models import Attraction, HotelOption, TransportOffer
        from planning.hotel_stages import build_hotel_stage_options
        from planning.scheduling import schedule_attractions

        def records(prefix: str) -> list[dict]:
            return [
                record
                for provider_id, result in research.items()
                if provider_id.startswith(prefix)
                for record in result.records
            ]

        hotels = [HotelOption.model_validate(row) for row in records("hotels")]
        attractions = [Attraction.model_validate(row) for row in records("attractions")]
        days = schedule_attractions(
            attractions,
            duration_days=request.duration_days,
        )
        hotel_stage_options = build_hotel_stage_options(
            days,
            hotels,
            routes_by_hotel,
        )
        return PlanningInputs(
            budget_cny=request.budget_cny,
            travelers=request.travelers,
            transports=[
                TransportOffer.model_validate(row) for row in records("transport")
            ],
            attractions=attractions,
            hotel_stage_options=hotel_stage_options,
        )

    def _write_geojson(self, workspace: TripWorkspace, routes: list) -> None:
        features = [
            {
                "type": "Feature",
                "properties": route.model_dump(mode="json", exclude={"path"}),
                "geometry": {
                    "type": "LineString",
                    "coordinates": [list(point) for point in route.path],
                },
            }
            for route in routes
        ]
        workspace.write_json(
            "routes.geojson",
            {"type": "FeatureCollection", "features": features},
        )
