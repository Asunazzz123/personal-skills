from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from checkpoints import InteractiveSession, InteractiveStage
from memory_store import StrategyMemory
from models import GenerationMode, TripRequest
from orchestrator import Orchestrator, OrchestratorDependencies
from planning.attraction_resolver import AttractionResolver
from planning.engine import PlanningEngine
from providers.amap import AMapProvider
from providers.flight import FlightProvider
from providers.hotels import HotelProvider
from providers.registry import ProviderRegistry
from providers.train_12306 import Train12306Provider
from providers.xhs import XhsEvidenceProvider
from render_html import render_itinerary
from research_pipeline import DefaultResearchPipeline, ResearchDependencies
from route_builder import DefaultRouteBuilder
from serve_itinerary import create_server


def build_registry() -> ProviderRegistry:
    return ProviderRegistry(
        [
            Train12306Provider(),
            FlightProvider(),
            XhsEvidenceProvider(),
            HotelProvider(),
            AMapProvider(),
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trip-schedule")
    subparsers = parser.add_subparsers(dest="command", required=True)

    health_parser = subparsers.add_parser("health")
    health_parser.add_argument("--json", action="store_true")

    generate = subparsers.add_parser("generate")
    generate.add_argument("--request", required=True, type=Path)
    generate.add_argument("--output-root", required=True, type=Path)
    generate.add_argument("--attraction-candidates", required=True, type=Path)

    serve = subparsers.add_parser("serve")
    serve.add_argument("directory", type=Path)
    serve.add_argument("--port", type=int, default=8765)

    resume = subparsers.add_parser("resume")
    resume.add_argument("--workspace", required=True, type=Path)
    resume.add_argument("--selection", required=True, type=Path)

    return parser


def build_default_dependencies(
    attraction_candidates_path: Path,
) -> OrchestratorDependencies:
    amap = AMapProvider()
    research = DefaultResearchPipeline(
        ResearchDependencies(
            train=Train12306Provider(),
            flight=FlightProvider(),
            xhs=XhsEvidenceProvider(),
            hotels=HotelProvider(),
            attraction_resolver=AttractionResolver(amap),
        ),
        attraction_candidates_path=attraction_candidates_path,
    )
    return OrchestratorDependencies(
        research=research,
        route_builder=DefaultRouteBuilder(amap),
        planner=PlanningEngine(),
    )


def options_after_selection(
    stage: InteractiveStage,
    selection_ids: list[str],
    plans: list[dict],
) -> list[str]:
    selected = set(selection_ids)
    if stage is InteractiveStage.INTERCITY:
        return sorted(
            {
                f"hotel:{plan['hotels'][0]['name']}"
                for plan in plans
                if (
                    f"{plan['transport']['mode']}:{plan['transport']['service_id']}"
                    in selected
                )
            }
        )
    if stage is InteractiveStage.HOTEL:
        return sorted(
            {
                f"attraction:{item['name']}"
                for plan in plans
                if f"hotel:{plan['hotels'][0]['name']}" in selected
                for item in plan["attractions"]
            }
        )
    return []


def _transport_option_ids(plans: list[dict]) -> list[str]:
    return sorted(
        {
            f"{plan['transport']['mode']}:{plan['transport']['service_id']}"
            for plan in plans
        }
    )


def _load_plan(workspace: Path) -> dict:
    return json.loads((workspace / "plan.json").read_text(encoding="utf-8"))


def _render_workspace(workspace: Path) -> None:
    plan = _load_plan(workspace)
    geojson = json.loads((workspace / "routes.geojson").read_text(encoding="utf-8"))
    render_itinerary(
        output_path=workspace / "itinerary.html",
        plan=plan,
        geojson=geojson,
    )


def _record_memory(request: TripRequest, report: dict) -> str:
    return StrategyMemory(
        Path(__file__).resolve().parents[1] / "memory" / "strategy.json"
    ).record_run(
        region=request.destination,
        query_keywords=[
            f"{request.destination} 景点",
            f"{request.destination} 旅游攻略",
        ],
        provider_events=[
            (provider_id, item["status"]) for provider_id, item in report.items()
        ],
        routing_notes=[],
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "health":
        health = build_registry().health()
        if args.json:
            payload = {
                provider_id: provider_health.model_dump(mode="json")
                for provider_id, provider_health in health.items()
            }
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        else:
            for provider_id, provider_health in health.items():
                print(
                    f"{provider_id}: "
                    f"{provider_health.status} - {provider_health.detail}"
                )
        return 0

    if args.command == "generate":
        request = TripRequest.model_validate_json(
            args.request.read_text(encoding="utf-8")
        )
        dependencies = build_default_dependencies(args.attraction_candidates)
        result = Orchestrator(dependencies).run(
            request,
            output_root=args.output_root,
        )
        plan = _load_plan(result.workspace.root)
        if request.generation_mode is GenerationMode.INTERACTIVE:
            InteractiveSession.create(
                result.workspace.root,
                option_ids=_transport_option_ids(plan["plans"]),
            )
        else:
            _render_workspace(result.workspace.root)
        report = json.loads(
            (result.workspace.root / "provider-report.json").read_text(
                encoding="utf-8"
            )
        )
        memory_message = _record_memory(request, report)
        print(result.workspace.root)
        print(memory_message)
        return 0

    if args.command == "resume":
        selection = json.loads(args.selection.read_text(encoding="utf-8"))
        selection_ids = selection["selection_ids"]
        session = InteractiveSession.load(args.workspace)
        previous_stage = session.state.stage
        plan = _load_plan(args.workspace)
        next_option_ids = options_after_selection(
            previous_stage,
            selection_ids,
            plan["plans"],
        )
        session.resume(
            selection_ids=selection_ids,
            next_option_ids=next_option_ids,
        )
        if session.state.stage is InteractiveStage.COMPLETE:
            _render_workspace(args.workspace)
        print(session.path)
        return 0

    if args.command == "serve":
        server = create_server(args.directory.resolve(), port=args.port)
        print(f"http://127.0.0.1:{server.server_port}/itinerary.html")
        server.serve_forever()
        return 0

    parser.error(f"unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
