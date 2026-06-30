# Trip Schedule Rendering and Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the providers and planner, render secure AMap itinerary artifacts, finalize the Skill workflow and README, and prove the complete package with offline and opt-in live tests.

**Architecture:** Keep conversational input and interactive checkpoints in `SKILL.md`, while deterministic scripts validate request JSON, query configured providers, write artifacts, render GeoJSON/HTML, and serve the itinerary through a loopback-only key-injecting proxy. End-to-end tests use fake providers; real network tests remain explicitly opt-in.

**Tech Stack:** Python 3.10+, Pydantic 2, Jinja2, Requests, AMap JS API 2.0 and Web Service APIs, Pytest, OpenAI Skill validator

---

## File Map

Create or modify:

```text
trip-schedule/
├── SKILL.md
├── README.md
├── agents/openai.yaml
├── assets/itinerary-template.html
├── scripts/
│   ├── trip_schedule.py
│   ├── checkpoints.py
│   ├── orchestrator.py
│   ├── research_pipeline.py
│   ├── route_builder.py
│   ├── render_html.py
│   ├── serve_itinerary.py
│   └── providers/
│       ├── flight.py
│       ├── train_12306.py
│       └── amap.py
├── references/
│   ├── data-contracts.md
│   └── provider-policy.md
└── tests/
    ├── fixtures/full-trip-input.json
    ├── test_city_resolution.py
    ├── test_orchestrator.py
    ├── test_research_pipeline.py
    ├── test_route_builder.py
    ├── test_render_html.py
    ├── test_serve_itinerary.py
    ├── test_generate_cli.py
    ├── test_checkpoints.py
    ├── test_secret_scan.py
    ├── test_skill_content.py
    └── test_live_smoke.py
```

### Task 1: Resolve user cities into stations and airports

**Files:**
- Modify: `trip-schedule/scripts/providers/train_support/station_index.py`
- Modify: `trip-schedule/scripts/providers/train_12306.py`
- Modify: `trip-schedule/scripts/providers/flight.py`
- Create: `trip-schedule/tests/test_city_resolution.py`

- [ ] **Step 1: Write failing city-resolution tests**

Create `trip-schedule/tests/test_city_resolution.py`:

```python
import json
from subprocess import CompletedProcess

from providers.flight import FlightProvider
from providers.train_12306 import Train12306Provider


def test_train_provider_resolves_city_to_station_candidates() -> None:
    provider = Train12306Provider()

    stations = provider.stations_for_city("深圳")

    assert "深圳北" in stations
    assert len(stations) <= 5


def test_flight_provider_resolves_city_to_iata(monkeypatch) -> None:
    monkeypatch.setattr("providers.flight.shutil.which", lambda _: "/usr/bin/fli")
    monkeypatch.setattr(
        "providers.flight.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(
                [{"iata": "SZX", "name": "深圳宝安国际机场", "city": "深圳"}]
            ),
            stderr="",
        ),
    )

    assert FlightProvider().resolve_airports("深圳") == ["SZX"]
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_city_resolution.py -v
```

Expected: missing `stations_for_city` and `resolve_airports`.

- [ ] **Step 3: Preserve city membership in the station index**

Update `StationIndex.__init__()` in
`trip-schedule/scripts/providers/train_support/station_index.py`:

```python
def __init__(self, path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    self.city_to_stations: dict[str, list[str]] = {}
    pairs: list[tuple[str, str]] = []
    for city in data:
        city_name = city.get("city")
        names: list[str] = []
        for station in city.get("stations", []):
            name = station.get("station")
            code = station.get("id")
            if name and code:
                pairs.append((name, code))
                names.append(name)
        if city_name and names:
            self.city_to_stations[city_name] = names
    self.name_to_code = dict(pairs)
    self.code_to_name = {code: name for name, code in pairs}

def stations_for_city(self, city: str, *, limit: int = 5) -> list[str]:
    direct = self.city_to_stations.get(city)
    if direct:
        return direct[:limit]
    matching = [
        name for name in self.name_to_code if name.startswith(city)
    ]
    return matching[:limit]
```

Add to `Train12306Provider`:

```python
def stations_for_city(self, city: str) -> list[str]:
    return self.index.stations_for_city(city)
```

- [ ] **Step 4: Implement airport resolution through the installed CLI**

Add to `FlightProvider`:

```python
def resolve_airports(self, city: str) -> list[str]:
    if shutil.which("fli") is None:
        return []
    completed = subprocess.run(
        ["fli", "airport-search", city, "--format", "json"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        return []
    payload = json.loads(completed.stdout)
    rows = payload if isinstance(payload, list) else payload.get("results", [])
    codes = [
        str(row["iata"]).upper()
        for row in rows
        if row.get("iata") and row.get("city") in {None, city}
    ]
    return list(dict.fromkeys(codes))[:5]
```

Catch JSON and schema errors and return an empty list; do not expose CLI output
that may contain signed URLs.

- [ ] **Step 5: Run city-resolution tests**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_city_resolution.py -v
```

Expected: `2 passed`.

- [ ] **Step 6: Commit city resolution**

Run:

```bash
git add \
  trip-schedule/scripts/providers/train_support/station_index.py \
  trip-schedule/scripts/providers/train_12306.py \
  trip-schedule/scripts/providers/flight.py \
  trip-schedule/tests/test_city_resolution.py
git commit -m "Resolve trip cities to transport hubs" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 2: Build the deterministic orchestration layer

**Files:**
- Create: `trip-schedule/scripts/orchestrator.py`
- Create: `trip-schedule/scripts/research_pipeline.py`
- Create: `trip-schedule/scripts/route_builder.py`
- Create: `trip-schedule/tests/fixtures/full-trip-input.json`
- Create: `trip-schedule/tests/test_orchestrator.py`
- Create: `trip-schedule/tests/test_research_pipeline.py`
- Create: `trip-schedule/tests/test_route_builder.py`

- [ ] **Step 1: Add a complete request fixture**

Create `trip-schedule/tests/fixtures/full-trip-input.json`:

```json
{
  "origin_city": "深圳",
  "destination": "杭州",
  "budget_cny": 5000,
  "departure_at": "2026-07-10T08:00:00+08:00",
  "duration_days": 3,
  "travelers": 2,
  "generation_mode": "one_shot"
}
```

- [ ] **Step 2: Write failing orchestration tests with fake providers**

Create `trip-schedule/tests/test_orchestrator.py`:

```python
import json
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
```

- [ ] **Step 3: Run orchestration tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_orchestrator.py -v
```

Expected: import failure for `orchestrator`.

- [ ] **Step 4: Implement injectable orchestration**

Create `trip-schedule/scripts/orchestrator.py`:

```python
from __future__ import annotations

import json
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
        workspace.write_json(
            "plan.json",
            planning_result.model_dump(mode="json"),
        )
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
        primary_routes = (
            planning_result.plans[0].routes if planning_result.plans else []
        )
        self._write_geojson(workspace, primary_routes)
        return OrchestratorResult(
            workspace=workspace,
            plans=planning_result.plans,
        )

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
        attractions = [
            Attraction.model_validate(row) for row in records("attractions")
        ]
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
```

- [ ] **Step 5: Write failing bounded-research tests**

Create `trip-schedule/tests/test_research_pipeline.py`:

```python
import json
from pathlib import Path

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
```

- [ ] **Step 6: Implement the production research pipeline**

Create `trip-schedule/scripts/research_pipeline.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import product
from pathlib import Path
from typing import Protocol

from models import ProviderResult, ProviderStatus, TripRequest
from planning.attraction_resolver import AttractionCandidate, AttractionResolver
from providers.flight import FlightProvider, FlightQuery
from providers.hotels import HotelProvider, HotelQuery
from providers.train_12306 import Train12306Provider, TrainQuery
from providers.xhs import XhsEvidenceProvider, XhsQuery


class QueryProvider(Protocol):
    def query(self, request: object) -> ProviderResult:
        ...


@dataclass(frozen=True)
class ResearchDependencies:
    train: Train12306Provider
    flight: FlightProvider
    xhs: XhsEvidenceProvider
    hotels: HotelProvider
    attraction_resolver: AttractionResolver


def combine_results(
    provider_id: str,
    attempts: list[ProviderResult],
) -> ProviderResult:
    queried_at = datetime.now().astimezone()
    records = [record for attempt in attempts for record in attempt.records]
    warnings = [
        warning
        for attempt in attempts
        for warning in attempt.warnings
    ]
    if records:
        status = ProviderStatus.OK
    elif attempts:
        status = attempts[-1].status
    else:
        status = ProviderStatus.NOT_CONFIGURED
    return ProviderResult(
        provider_id=provider_id,
        status=status,
        queried_at=queried_at,
        records=records,
        warnings=warnings,
        error_kind=attempts[-1].error_kind if attempts else None,
    )


class DefaultResearchPipeline:
    def __init__(
        self,
        dependencies: ResearchDependencies,
        *,
        attraction_candidates_path: Path,
    ) -> None:
        self.dependencies = dependencies
        self.attraction_candidates_path = attraction_candidates_path

    def collect(self, request: TripRequest) -> dict[str, ProviderResult]:
        departure_date = request.departure_at.date()
        results: dict[str, ProviderResult] = {}

        train_attempts: list[ProviderResult] = []
        origins = self.dependencies.train.stations_for_city(request.origin_city)[:3]
        destinations = self.dependencies.train.stations_for_city(
            request.destination
        )[:3]
        for origin, destination in product(origins, destinations):
            result = self.dependencies.train.query(
                TrainQuery(
                    origin_station=origin,
                    destination_station=destination,
                    travel_date=departure_date,
                )
            )
            train_attempts.append(result)
            if result.records:
                break
        results["transport-train"] = combine_results(
            "transport-train",
            train_attempts,
        )

        flight_attempts: list[ProviderResult] = []
        origin_airports = self.dependencies.flight.resolve_airports(
            request.origin_city
        )[:3]
        destination_airports = self.dependencies.flight.resolve_airports(
            request.destination
        )[:3]
        for origin, destination in product(origin_airports, destination_airports):
            flight_attempts.append(
                self.dependencies.flight.query(
                    FlightQuery(
                        origin_iata=origin,
                        destination_iata=destination,
                        departure_date=departure_date,
                        travelers=request.travelers,
                    )
                )
            )
        results["transport-flight"] = combine_results(
            "transport-flight",
            flight_attempts,
        )

        xhs_result = self.dependencies.xhs.query(
            XhsQuery(destination=request.destination)
        )
        results["evidence-xhs"] = xhs_result
        nights = max(1, request.duration_days - 1)
        results["hotels-external"] = self.dependencies.hotels.query(
            HotelQuery(
                destination=request.destination,
                check_in=departure_date,
                check_out=departure_date + timedelta(days=nights),
                travelers=request.travelers,
            )
        )
        results["attractions-resolved"] = self._resolve_attractions(
            request.destination,
            allowed_source_urls={
                str(record.get("source_url"))
                for record in xhs_result.records
                if record.get("source_url")
            },
        )
        return results

    def _resolve_attractions(
        self,
        city: str,
        *,
        allowed_source_urls: set[str],
    ) -> ProviderResult:
        queried_at = datetime.now().astimezone()
        if not self.attraction_candidates_path.is_file():
            return ProviderResult(
                provider_id="attractions-resolved",
                status=ProviderStatus.NOT_CONFIGURED,
                queried_at=queried_at,
                records=[],
                warnings=[
                    "Create attraction_candidates.json from sourced media evidence."
                ],
            )
        payload = json.loads(
            self.attraction_candidates_path.read_text(encoding="utf-8")
        )
        candidates = []
        rejected = []
        for item in payload:
            candidate = AttractionCandidate.model_validate(item)
            if candidate.source_url not in allowed_source_urls:
                rejected.append(candidate.source_url)
                continue
            candidates.append(candidate)
        attractions, warnings = self.dependencies.attraction_resolver.resolve(
            candidates,
            city=city,
        )
        if rejected:
            warnings.append(
                f"Rejected {len(rejected)} attraction candidates without "
                "matching source evidence."
            )
        return ProviderResult(
            provider_id="attractions-resolved",
            status=(
                ProviderStatus.OK
                if attractions
                else ProviderStatus.NO_RESULTS
            ),
            queried_at=queried_at,
            records=[
                attraction.model_dump(mode="json")
                for attraction in attractions
            ],
            warnings=warnings,
        )
```

- [ ] **Step 7: Write and implement hotel-specific route building**

Create `trip-schedule/tests/test_route_builder.py`:

```python
from models import (
    Attraction,
    HotelOption,
    ProviderResult,
    ProviderStatus,
    SourceEvidence,
    TripRequest,
)
from route_builder import DefaultRouteBuilder


class FakeAMap:
    def route_transit(self, origin, destination, *, city):
        return ProviderResult(
            provider_id="amap-webservice",
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[{
                "distance_meters": 8000,
                "duration_minutes": 60,
                "estimated_cost_cny": 6,
                "path": [list(origin), list(destination)],
            }],
        )

    def route_driving(self, origin, destination):
        return ProviderResult(
            provider_id="amap-webservice",
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[{
                "distance_meters": 8000,
                "duration_minutes": 25,
                "estimated_cost_cny": 0,
                "path": [list(origin), list(destination)],
            }],
        )


def test_route_builder_creates_routes_per_hotel() -> None:
    evidence = SourceEvidence(
        source="fixture",
        source_url="https://example.invalid/source",
        queried_at="2026-07-01T10:00:00+08:00",
        confidence=0.8,
    )
    hotel = HotelOption(
        name="湖滨酒店",
        latitude=30.26,
        longitude=120.16,
        total_price_cny=900,
        nights=2,
        evidence=[evidence],
    )
    attraction = Attraction(
        name="西湖",
        description="湖区",
        latitude=30.25,
        longitude=120.15,
        ticket_price_cny=0,
        suggested_visit_minutes=180,
        evidence=[evidence],
    )
    research = {
        "hotels-fixture": ProviderResult(
            provider_id="hotels-fixture",
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[hotel.model_dump(mode="json")],
        ),
        "attractions-fixture": ProviderResult(
            provider_id="attractions-fixture",
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[attraction.model_dump(mode="json")],
        ),
    }
    request = TripRequest(
        origin_city="深圳",
        destination="杭州",
        budget_cny=5000,
        departure_at="2026-07-10T08:00:00+08:00",
        duration_days=3,
        travelers=2,
        generation_mode="one_shot",
    )

    routes = DefaultRouteBuilder(FakeAMap()).build(request, research)

    assert list(routes) == ["湖滨酒店"]
    assert routes["湖滨酒店"][0].path[0] == (120.16, 30.26)
```

Create `trip-schedule/scripts/route_builder.py`:

```python
from __future__ import annotations

from models import (
    Attraction,
    HotelOption,
    ProviderResult,
    ProviderStatus,
    RouteMode,
    RouteSegment,
    TripRequest,
)
from planning.routing import choose_local_mode


class DefaultRouteBuilder:
    def __init__(self, amap) -> None:
        self.amap = amap

    def build(
        self,
        request: TripRequest,
        research: dict[str, ProviderResult],
    ) -> dict[str, list[RouteSegment]]:
        hotels = [
            HotelOption.model_validate(record)
            for provider_id, result in research.items()
            if provider_id.startswith("hotels")
            for record in result.records
        ]
        attractions = [
            Attraction.model_validate(record)
            for provider_id, result in research.items()
            if provider_id.startswith("attractions")
            for record in result.records
        ]
        routes_by_hotel: dict[str, list[RouteSegment]] = {}
        for hotel in hotels:
            hotel_routes = []
            origin = (hotel.longitude, hotel.latitude)
            for attraction in attractions:
                destination = (attraction.longitude, attraction.latitude)
                transit = self.amap.route_transit(
                    origin,
                    destination,
                    city=request.destination,
                )
                driving = self.amap.route_driving(origin, destination)
                if (
                    transit.status is not ProviderStatus.OK
                    or driving.status is not ProviderStatus.OK
                ):
                    continue
                transit_row = transit.records[0]
                driving_row = driving.records[0]
                distance_km = driving_row["distance_meters"] / 1000
                taxi_cost = round(
                    13 + max(0, distance_km - 3) * 2.5,
                    2,
                )
                decision = choose_local_mode(
                    distance_km=distance_km,
                    transit_minutes=transit_row["duration_minutes"],
                    taxi_minutes=driving_row["duration_minutes"],
                    taxi_cost_cny=taxi_cost,
                    travelers=request.travelers,
                    late_night=False,
                    has_luggage=False,
                )
                selected = (
                    driving_row
                    if decision.mode is RouteMode.TAXI
                    else transit_row
                )
                hotel_routes.append(
                    RouteSegment(
                        origin_name=hotel.name,
                        destination_name=attraction.name,
                        mode=decision.mode,
                        distance_meters=selected["distance_meters"],
                        duration_minutes=selected["duration_minutes"],
                        estimated_cost_cny=(
                            taxi_cost
                            if decision.mode is RouteMode.TAXI
                            else selected["estimated_cost_cny"]
                        ),
                        reason=decision.reason,
                        path=[
                            tuple(point) for point in selected["path"]
                        ],
                    )
                )
            routes_by_hotel[hotel.name] = hotel_routes
        return routes_by_hotel
```

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_route_builder.py -v
```

Expected: `1 passed`.

- [ ] **Step 8: Run orchestration and research tests**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_orchestrator.py \
  trip-schedule/tests/test_research_pipeline.py \
  trip-schedule/tests/test_route_builder.py -v
```

Expected: artifact and failure-report tests pass.

- [ ] **Step 9: Commit orchestration**

Run:

```bash
git add \
  trip-schedule/scripts/orchestrator.py \
  trip-schedule/scripts/research_pipeline.py \
  trip-schedule/scripts/route_builder.py \
  trip-schedule/tests/fixtures/full-trip-input.json \
  trip-schedule/tests/test_orchestrator.py \
  trip-schedule/tests/test_research_pipeline.py \
  trip-schedule/tests/test_route_builder.py
git commit -m "Add trip planning orchestrator" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 3: Render GeoJSON and itinerary HTML

**Files:**
- Create: `trip-schedule/assets/itinerary-template.html`
- Create: `trip-schedule/scripts/render_html.py`
- Create: `trip-schedule/tests/test_render_html.py`

- [ ] **Step 1: Write failing rendering tests**

Create `trip-schedule/tests/test_render_html.py`:

```python
from pathlib import Path

from render_html import render_itinerary


def test_rendered_html_contains_no_amap_credentials(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AMAP_JSAPI_KEY", "js-secret")
    monkeypatch.setenv("AMAP_SECURITY_KEY", "security-secret")
    output = tmp_path / "itinerary.html"

    render_itinerary(
        output_path=output,
        plan={"plans": []},
        geojson={"type": "FeatureCollection", "features": []},
    )

    html = output.read_text(encoding="utf-8")
    assert "js-secret" not in html
    assert "security-secret" not in html
    assert "/runtime-config" in html
    assert "routes.geojson" in html


def test_template_has_daily_route_and_budget_panels(tmp_path) -> None:
    output = tmp_path / "itinerary.html"
    render_itinerary(
        output_path=output,
        plan={"plans": [{"label": "balanced", "total_cost_cny": 3000}]},
        geojson={"type": "FeatureCollection", "features": []},
    )

    html = output.read_text(encoding="utf-8")
    assert 'id="map"' in html
    assert 'id="timeline"' in html
    assert 'id="budget"' in html
    assert 'id="evidence"' in html
```

- [ ] **Step 2: Run rendering tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_render_html.py -v
```

Expected: import failure for `render_html`.

- [ ] **Step 3: Create the key-free HTML template**

Create `trip-schedule/assets/itinerary-template.html` as a complete HTML
document with:

```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }}</title>
    <style>
      html, body { margin: 0; min-height: 100%; font-family: system-ui, sans-serif; }
      main { display: grid; grid-template-columns: minmax(320px, 38%) 1fr; min-height: 100vh; }
      aside { padding: 20px; overflow: auto; background: #f7f4ed; }
      #map { min-height: 100vh; }
      .panel { background: white; border-radius: 12px; padding: 14px; margin-bottom: 12px; }
      @media (max-width: 800px) {
        main { grid-template-columns: 1fr; }
        #map { min-height: 60vh; }
      }
    </style>
  </head>
  <body>
    <main>
      <aside>
        <section id="timeline" class="panel"></section>
        <section id="budget" class="panel"></section>
        <section id="evidence" class="panel"></section>
      </aside>
      <div id="map" aria-label="行程地图"></div>
    </main>
    <script id="trip-plan" type="application/json">{{ plan_json | safe }}</script>
    <script>
      async function boot() {
        const config = await fetch("/runtime-config").then((response) => response.json());
        window._AMapSecurityConfig = {
          serviceHost: `${window.location.origin}/_AMapService`
        };
        const loader = document.createElement("script");
        loader.src = `https://webapi.amap.com/loader.js`;
        loader.onload = async () => {
          const AMap = await AMapLoader.load({
            key: config.amapJsApiKey,
            version: "2.0"
          });
          const map = new AMap.Map("map", { zoom: 11 });
          const geojson = await fetch("routes.geojson").then((response) => response.json());
          window.renderTrip(map, geojson, JSON.parse(
            document.getElementById("trip-plan").textContent
          ));
        };
        document.head.appendChild(loader);
      }

      window.renderTrip = function renderTrip(map, geojson, plan) {
        const colors = ["#d35400", "#2874a6", "#239b56", "#7d3c98"];
        const overlays = [];
        geojson.features.forEach((feature, index) => {
          if (feature.geometry?.type !== "LineString") return;
          const path = feature.geometry.coordinates;
          if (path.length < 2) return;
          const polyline = new AMap.Polyline({
            path,
            strokeColor: colors[index % colors.length],
            strokeWeight: 6,
            showDir: true
          });
          const start = new AMap.Marker({
            position: path[0],
            title: feature.properties.origin_name
          });
          const end = new AMap.Marker({
            position: path[path.length - 1],
            title: feature.properties.destination_name
          });
          map.add([polyline, start, end]);
          overlays.push(polyline, start, end);
        });
        if (overlays.length) map.setFitView(overlays);

        const timeline = document.getElementById("timeline");
        timeline.replaceChildren();
        (plan.plans?.[0]?.routes || []).forEach((route) => {
          const row = document.createElement("p");
          row.textContent =
            `${route.origin_name} → ${route.destination_name}: ` +
            `${route.mode}, ${route.duration_minutes} min`;
          timeline.appendChild(row);
        });
        document.getElementById("budget").textContent =
          plan.plans?.[0] ? `Budget: CNY ${plan.plans[0].total_cost_cny}` : "No valid plan";
        document.getElementById("evidence").textContent =
          "See provider-report.json for source timestamps and warnings.";
      };

      boot().catch((error) => {
        document.getElementById("evidence").textContent =
          `Map failed to load: ${error.message}`;
      });
    </script>
  </body>
</html>
```

Append to `test_template_has_daily_route_and_budget_panels()`:

```python
assert "new AMap.Polyline" in html
assert "new AMap.Marker" in html
assert "map.setFitView" in html
```

- [ ] **Step 4: Implement deterministic rendering**

Create `trip-schedule/scripts/render_html.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def render_itinerary(
    *,
    output_path: Path,
    plan: dict,
    geojson: dict,
) -> None:
    assets_dir = Path(__file__).resolve().parents[1] / "assets"
    environment = Environment(
        loader=FileSystemLoader(assets_dir),
        autoescape=select_autoescape(("html", "xml")),
    )
    template = environment.get_template("itinerary-template.html")
    output_path.write_text(
        template.render(
            title="Trip Schedule",
            plan_json=json.dumps(plan, ensure_ascii=False).replace("</", "<\\/"),
        ),
        encoding="utf-8",
    )
    (output_path.parent / "routes.geojson").write_text(
        json.dumps(geojson, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
```

- [ ] **Step 5: Run rendering tests and verify GREEN**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_render_html.py -v
```

Expected: no keys appear in static output and required panels exist.

- [ ] **Step 6: Commit the renderer**

Run:

```bash
git add \
  trip-schedule/assets/itinerary-template.html \
  trip-schedule/scripts/render_html.py \
  trip-schedule/tests/test_render_html.py
git commit -m "Render trip itinerary HTML" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 4: Serve the itinerary with a loopback-only AMap proxy

**Files:**
- Create: `trip-schedule/scripts/serve_itinerary.py`
- Create: `trip-schedule/tests/test_serve_itinerary.py`

- [ ] **Step 1: Write failing configuration and binding tests**

Create `trip-schedule/tests/test_serve_itinerary.py`:

```python
import json

import pytest

from serve_itinerary import RuntimeConfig, create_server


def test_runtime_config_requires_all_map_credentials(monkeypatch) -> None:
    monkeypatch.delenv("AMAP_SECURITY_KEY", raising=False)

    with pytest.raises(RuntimeError, match="AMAP_SECURITY_KEY"):
        RuntimeConfig.from_environment()


def test_server_binds_loopback_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("AMAP_JSAPI_KEY", "js-key")
    monkeypatch.setenv("AMAP_SECURITY_KEY", "security-key")
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "web-key")

    server = create_server(tmp_path, port=0)

    try:
        assert server.server_address[0] == "127.0.0.1"
    finally:
        server.server_close()
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_serve_itinerary.py -v
```

Expected: import failure for `serve_itinerary`.

- [ ] **Step 3: Implement runtime config and loopback server**

Create `trip-schedule/scripts/serve_itinerary.py`:

```python
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests


@dataclass(frozen=True)
class RuntimeConfig:
    js_api_key: str
    security_key: str
    webservice_key: str

    @classmethod
    def from_environment(cls) -> "RuntimeConfig":
        values = {
            "AMAP_JSAPI_KEY": os.getenv("AMAP_JSAPI_KEY"),
            "AMAP_SECURITY_KEY": os.getenv("AMAP_SECURITY_KEY"),
            "AMAP_WEBSERVICE_KEY": os.getenv("AMAP_WEBSERVICE_KEY"),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")
        return cls(
            js_api_key=values["AMAP_JSAPI_KEY"],
            security_key=values["AMAP_SECURITY_KEY"],
            webservice_key=values["AMAP_WEBSERVICE_KEY"],
        )


class ItineraryHandler(SimpleHTTPRequestHandler):
    runtime_config: RuntimeConfig

    def do_GET(self) -> None:
        if self.path == "/runtime-config":
            body = json.dumps(
                {"amapJsApiKey": self.runtime_config.js_api_key}
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/_AMapService/"):
            self._proxy_amap()
            return
        super().do_GET()

    def _proxy_amap(self) -> None:
        split = urlsplit(self.path)
        upstream_path = split.path.removeprefix("/_AMapService")
        query = dict(parse_qsl(split.query, keep_blank_values=True))
        query["jscode"] = self.runtime_config.security_key
        upstream = urlunsplit(
            ("https", "restapi.amap.com", upstream_path, urlencode(query), "")
        )
        response = requests.get(upstream, timeout=20)
        body = response.content
        self.send_response(response.status_code)
        self.send_header(
            "Content-Type",
            response.headers.get("Content-Type", "application/json"),
        )
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(directory: Path, *, port: int) -> ThreadingHTTPServer:
    config = RuntimeConfig.from_environment()

    class BoundItineraryHandler(ItineraryHandler):
        runtime_config = config

    def handler(*args, **kwargs):
        return BoundItineraryHandler(
            *args,
            directory=str(directory.resolve()),
            **kwargs,
        )

    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = create_server(args.directory.resolve(), port=args.port)
    print(f"http://127.0.0.1:{server.server_port}/itinerary.html")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add proxy redaction and traversal tests**

Append to `trip-schedule/tests/test_serve_itinerary.py`:

```python
import threading
from urllib.error import HTTPError
from urllib.request import urlopen


def start_server(server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return thread


def configure_keys(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_JSAPI_KEY", "js-key")
    monkeypatch.setenv("AMAP_SECURITY_KEY", "security-key")
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "web-key")


def test_runtime_config_endpoint_exposes_only_js_key(tmp_path, monkeypatch) -> None:
    configure_keys(monkeypatch)
    server = create_server(tmp_path, port=0)
    start_server(server)
    try:
        body = urlopen(
            f"http://127.0.0.1:{server.server_port}/runtime-config"
        ).read().decode("utf-8")
        assert json.loads(body) == {"amapJsApiKey": "js-key"}
        assert "security-key" not in body
        assert "web-key" not in body
    finally:
        server.shutdown()
        server.server_close()


def test_proxy_keeps_security_key_upstream_only(
    tmp_path,
    monkeypatch,
) -> None:
    configure_keys(monkeypatch)
    observed = {}

    class Response:
        status_code = 200
        content = b'{"ok":true}'
        headers = {"Content-Type": "application/json"}

    def fake_get(url, *, timeout):
        observed["url"] = url
        return Response()

    monkeypatch.setattr("serve_itinerary.requests.get", fake_get)
    server = create_server(tmp_path, port=0)
    start_server(server)
    try:
        body = urlopen(
            f"http://127.0.0.1:{server.server_port}"
            "/_AMapService/v3/test?value=1"
        ).read().decode("utf-8")
        assert "security-key" in observed["url"]
        assert "security-key" not in body
    finally:
        server.shutdown()
        server.server_close()


def test_static_handler_cannot_escape_itinerary_directory(
    tmp_path,
    monkeypatch,
) -> None:
    configure_keys(monkeypatch)
    root = tmp_path / "trip"
    root.mkdir()
    (tmp_path / "secret.txt").write_text("secret", encoding="utf-8")
    server = create_server(root, port=0)
    start_server(server)
    try:
        with pytest.raises(HTTPError) as exc_info:
            urlopen(
                f"http://127.0.0.1:{server.server_port}/../secret.txt"
            )
        assert exc_info.value.code == 404
    finally:
        server.shutdown()
        server.server_close()
```

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_serve_itinerary.py -v
```

Expected: all server tests pass and the server binds only to `127.0.0.1`.

- [ ] **Step 5: Commit the local server**

Run:

```bash
git add \
  trip-schedule/scripts/serve_itinerary.py \
  trip-schedule/tests/test_serve_itinerary.py
git commit -m "Serve trip maps through local AMap proxy" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 5: Finalize the CLI generation commands

**Files:**
- Modify: `trip-schedule/scripts/trip_schedule.py`
- Create: `trip-schedule/scripts/checkpoints.py`
- Create: `trip-schedule/tests/test_generate_cli.py`
- Create: `trip-schedule/tests/test_checkpoints.py`

- [ ] **Step 1: Write failing CLI argument tests**

Create `trip-schedule/tests/test_generate_cli.py`:

```python
from trip_schedule import build_parser


def test_generate_command_requires_request_and_output() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "generate",
            "--request",
            "request.json",
            "--output-root",
            "trip-output",
            "--attraction-candidates",
            "attraction_candidates.json",
        ]
    )

    assert args.command == "generate"
    assert str(args.request) == "request.json"
    assert str(args.output_root) == "trip-output"


def test_serve_command_accepts_itinerary_directory() -> None:
    parser = build_parser()
    args = parser.parse_args(["serve", "trip-output/example"])

    assert args.command == "serve"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_generate_cli.py -v
```

Expected: parser rejects `generate` and `serve`.

- [ ] **Step 3: Add `generate` and `serve` subcommands**

Extend `build_parser()`:

```python
generate = subparsers.add_parser("generate")
generate.add_argument("--request", required=True, type=Path)
generate.add_argument("--output-root", required=True, type=Path)
generate.add_argument("--attraction-candidates", required=True, type=Path)

serve = subparsers.add_parser("serve")
serve.add_argument("directory", type=Path)
serve.add_argument("--port", type=int, default=8765)
```

Add the dependency factory:

```python
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
```

Extend `main()`:

```python
if args.command == "generate":
    request = TripRequest.model_validate_json(
        args.request.read_text(encoding="utf-8")
    )
    dependencies = build_default_dependencies(args.attraction_candidates)
    result = Orchestrator(dependencies).run(
        request,
        output_root=args.output_root,
    )
    plan = json.loads(
        (result.workspace.root / "plan.json").read_text(encoding="utf-8")
    )
    geojson = json.loads(
        (result.workspace.root / "routes.geojson").read_text(encoding="utf-8")
    )
    render_itinerary(
        output_path=result.workspace.root / "itinerary.html",
        plan=plan,
        geojson=geojson,
    )
    report = json.loads(
        (result.workspace.root / "provider-report.json").read_text(
            encoding="utf-8"
        )
    )
    memory_message = StrategyMemory(
        Path(__file__).resolve().parents[1] / "memory" / "strategy.json"
    ).record_run(
        region=request.destination,
        query_keywords=[
            f"{request.destination} 景点",
            f"{request.destination} 旅游攻略",
        ],
        provider_events=[
            (provider_id, item["status"])
            for provider_id, item in report.items()
        ],
        routing_notes=[],
    )
    print(result.workspace.root)
    print(memory_message)
    return 0

if args.command == "serve":
    server = create_server(args.directory.resolve(), port=args.port)
    print(f"http://127.0.0.1:{server.server_port}/itinerary.html")
    server.serve_forever()
    return 0
```

Import `Path`, `TripRequest`, `Orchestrator`, `build_default_dependencies`,
`render_itinerary`, `create_server`, `StrategyMemory`, `AMapProvider`,
`AttractionResolver`, `DefaultResearchPipeline`, `ResearchDependencies`,
`DefaultRouteBuilder`, `PlanningEngine`, and every concrete provider.

- [ ] **Step 4: Write failing checkpoint-state tests**

Create `trip-schedule/tests/test_checkpoints.py`:

```python
import pytest

from checkpoints import InteractiveSession, InteractiveStage


def test_interactive_session_advances_three_validated_stages(tmp_path) -> None:
    session = InteractiveSession.create(
        tmp_path,
        option_ids=["train:G100", "flight:EA100"],
    )
    assert session.state.stage is InteractiveStage.INTERCITY

    session.resume(
        selection_ids=["train:G100"],
        next_option_ids=["hotel:湖滨", "hotel:城站"],
    )
    assert session.state.stage is InteractiveStage.HOTEL

    session.resume(
        selection_ids=["hotel:湖滨"],
        next_option_ids=["attraction:西湖", "attraction:灵隐寺"],
    )
    assert session.state.stage is InteractiveStage.ATTRACTIONS

    session.resume(
        selection_ids=["attraction:西湖", "attraction:灵隐寺"],
        next_option_ids=[],
    )
    assert session.state.stage is InteractiveStage.COMPLETE


def test_interactive_session_rejects_unknown_option(tmp_path) -> None:
    session = InteractiveSession.create(tmp_path, option_ids=["train:G100"])

    with pytest.raises(ValueError, match="not offered"):
        session.resume(
            selection_ids=["flight:forged"],
            next_option_ids=[],
        )
```

- [ ] **Step 5: Implement the checkpoint state machine**

Create `trip-schedule/scripts/checkpoints.py`:

```python
from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class InteractiveStage(StrEnum):
    INTERCITY = "awaiting_intercity_selection"
    HOTEL = "awaiting_hotel_selection"
    ATTRACTIONS = "awaiting_attraction_selection"
    COMPLETE = "complete"


class InteractiveState(BaseModel):
    stage: InteractiveStage
    valid_option_ids: list[str]
    selections: dict[str, list[str]] = Field(default_factory=dict)


class InteractiveSession:
    def __init__(self, workspace: Path, state: InteractiveState) -> None:
        self.workspace = workspace
        self.state = state

    @property
    def path(self) -> Path:
        return self.workspace / "interactive-state.json"

    @classmethod
    def create(
        cls,
        workspace: Path,
        *,
        option_ids: list[str],
    ) -> "InteractiveSession":
        session = cls(
            workspace,
            InteractiveState(
                stage=InteractiveStage.INTERCITY,
                valid_option_ids=option_ids,
            ),
        )
        session._save()
        return session

    @classmethod
    def load(cls, workspace: Path) -> "InteractiveSession":
        state = InteractiveState.model_validate_json(
            (workspace / "interactive-state.json").read_text(encoding="utf-8")
        )
        return cls(workspace, state)

    def resume(
        self,
        *,
        selection_ids: list[str],
        next_option_ids: list[str],
    ) -> None:
        invalid = set(selection_ids) - set(self.state.valid_option_ids)
        if invalid:
            raise ValueError(f"selection was not offered: {sorted(invalid)}")
        self.state.selections[self.state.stage.value] = selection_ids
        next_stage = {
            InteractiveStage.INTERCITY: InteractiveStage.HOTEL,
            InteractiveStage.HOTEL: InteractiveStage.ATTRACTIONS,
            InteractiveStage.ATTRACTIONS: InteractiveStage.COMPLETE,
        }.get(self.state.stage, InteractiveStage.COMPLETE)
        self.state.stage = next_stage
        self.state.valid_option_ids = next_option_ids
        self._save()

    def _save(self) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            self.state.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
```

- [ ] **Step 6: Add `resume` CLI parsing and trusted-option derivation**

Add:

```json
{
  "selection_ids": ["train:G100"]
}
```

Extend `build_parser()`:

```python
resume = subparsers.add_parser("resume")
resume.add_argument("--workspace", required=True, type=Path)
resume.add_argument("--selection", required=True, type=Path)
```

Add:

```python
def options_after_selection(
    stage: InteractiveStage,
    selection_ids: list[str],
    plans: list[dict],
) -> list[str]:
    selected = set(selection_ids)
    if stage is InteractiveStage.INTERCITY:
        return sorted({
            f"hotel:{plan['hotels'][0]['name']}"
            for plan in plans
            if f"{plan['transport']['mode']}:{plan['transport']['service_id']}"
            in selected
        })
    if stage is InteractiveStage.HOTEL:
        return sorted({
            f"attraction:{item['name']}"
            for plan in plans
            if f"hotel:{plan['hotels'][0]['name']}" in selected
            for item in plan["attractions"]
        })
    return []
```

For interactive `generate`, run research and planning, write the candidate
`plan.json`, then create `InteractiveSession` with option IDs derived from
`plan["plans"][*]["transport"]`. Do not render HTML until the session reaches
`complete`.

For `resume`, load `selection_ids`, call `session.resume()` with option IDs
derived from the existing `plan.json`, and render only after the final stage.
The selection file never supplies provider records.

- [ ] **Step 7: Run CLI and checkpoint tests**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_generate_cli.py \
  trip-schedule/tests/test_checkpoints.py -v
```

Expected: health, one-shot generate, serve, and interactive checkpoint tests
pass.

- [ ] **Step 8: Commit the final CLI**

Run:

```bash
git add \
  trip-schedule/scripts/trip_schedule.py \
  trip-schedule/scripts/checkpoints.py \
  trip-schedule/tests/test_generate_cli.py \
  trip-schedule/tests/test_checkpoints.py
git commit -m "Add trip generation CLI" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 6: Write the final Skill workflow and README

**Files:**
- Modify: `trip-schedule/SKILL.md`
- Create: `trip-schedule/README.md`
- Modify: `trip-schedule/agents/openai.yaml`
- Create: `trip-schedule/tests/test_skill_content.py`

- [ ] **Step 1: Write failing content tests**

Create `trip-schedule/tests/test_skill_content.py`:

```python
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


def test_skill_requires_generation_mode_and_six_inputs() -> None:
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    for phrase in (
        "origin city",
        "destination",
        "budget",
        "departure",
        "trip duration",
        "number of travelers",
        "one-shot",
        "interactive",
    ):
        assert phrase in text.lower()


def test_readme_has_placeholder_only_amap_setup() -> None:
    text = (SKILL_ROOT / "README.md").read_text(encoding="utf-8")
    for variable in (
        "AMAP_WEBSERVICE_KEY",
        "AMAP_JSAPI_KEY",
        "AMAP_SECURITY_KEY",
    ):
        assert variable in text
    assert "conda activate agent" not in text
    assert "pip install -r requirements.txt" in text


def test_skill_states_read_only_boundary() -> None:
    text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8").lower()
    assert "do not book" in text
    assert "do not pay" in text
    assert "do not bypass" in text
```

- [ ] **Step 2: Run content tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_skill_content.py -v
```

Expected: current temporary Skill shell and missing README fail.

- [ ] **Step 3: Replace `SKILL.md` with the approved workflow**

Replace `trip-schedule/SKILL.md` with:

````markdown
---
name: trip-schedule
description: Use when planning a sourced, budget-constrained trip in mainland China, including attractions, train or flight comparisons, hotel alternatives, local transportation, route maps, and itinerary HTML.
---

# Trip Schedule

## Start every trip

Before collecting data, obtain all six required values:

1. Origin city
2. Destination
3. Total budget in CNY
4. Departure date and time
5. Total trip duration
6. Number of travelers

Immediately before formal generation, ask whether the user wants one-shot or
interactive generation. Do not infer this choice.

Create a new per-trip output directory. Do not use an older trip directory as
a live data cache.

## Check dependencies

Run:

```bash
python scripts/trip_schedule.py health --json
```

Explain every provider that is unavailable. Never install a CLI, Skill, MCP
server, browser component, or Python package without explicit user approval.
Read [provider-policy.md](references/provider-policy.md) before configuring or
changing a provider.

## Collect mainland-China sources

1. Query the migrated 12306 provider for train schedules and availability.
2. Discover an installed flight tool first; use the configured `fli` provider
   when available. Keep train prices `null` unless a reliable price source
   returned them.
3. Query the configured Xiaohongshu wrapper for destination recommendations.
4. Query the configured hotel wrapper for total-stay prices and locations.
5. Preserve source URLs, query times, freshness, confidence, warnings, and
   failure categories.
6. Stop a provider on CAPTCHA, login challenge, or platform verification. Do
   not bypass it.

Review the sourced media evidence and write `attraction_candidates.json` using
the contract in [data-contracts.md](references/data-contracts.md). Do not invent
an attraction, ticket price, opening hour, or source. Let AMap resolve each
candidate to a real POI.

## Generate

Write the six inputs and selected mode to `request.json`, then run:

```bash
python scripts/trip_schedule.py generate \
  --request request.json \
  --attraction-candidates attraction_candidates.json \
  --output-root trip-output
```

For one-shot mode, return the balanced primary plan plus economy and
time-saving alternatives when valid candidates exist.

For interactive mode, present only option IDs from
`interactive-state.json`. Collect the user's choice, write:

```json
{"selection_ids": ["an-option-id-that-was-offered"]}
```

Then resume:

```bash
python scripts/trip_schedule.py resume \
  --workspace trip-output/<trip-directory> \
  --selection selection.json
```

Repeat for intercity transport, hotel area, and attractions. Never accept a
record supplied by the selection file; accept only IDs already present in the
workspace.

## Report quality and cost

Treat the budget as a hard constraint with a 10% contingency. If no plan fits,
show the smallest deficit and the main cost drivers.

State which values are live, estimated, missing, or stale. Show provider
failures and fallbacks from `provider-report.json`. Do not describe a partial
plan as complete.

Query and recommend only. Do not book, submit identity information, pay, or
bypass security controls.

## Present the itinerary

Start the loopback-only itinerary server:

```bash
python scripts/trip_schedule.py serve trip-output/<trip-directory>
```

Return the local URL and the artifact paths. Do not copy AMap credentials into
HTML, JSON, logs, or chat.

## Update memory

After a completed or useful partial run, update only the installed Skill's
de-identified region strategies and provider reliability counters. Do not store
trip dates, origin city, budget, traveler count, selected hotel, ticket results,
cookies, or credentials.

Disclose the update in one localized sentence equivalent to:

> Updated Trip Schedule's de-identified strategy memory.
````

- [ ] **Step 4: Write the portable README**

Create `trip-schedule/README.md` with these exact installation commands:

````markdown
# Trip Schedule

## Install

Copy or symlink this directory to:

```text
~/.codex/skills/trip-schedule/
```

Install dependencies in your chosen Python environment:

```bash
python -m pip install -r requirements.txt
```

Trip Schedule does not require a particular Conda environment and never
installs missing packages automatically.

## AMap configuration

```bash
export AMAP_WEBSERVICE_KEY="<your-web-service-key>"
export AMAP_JSAPI_KEY="<your-js-api-key>"
export AMAP_SECURITY_KEY="<your-js-security-code>"
```

Restrict the JS key to the local host/domain you use. Never commit these values.

## Crawler wrappers

Configure `TRIP_XHS_COMMAND_JSON` and `TRIP_HOTEL_COMMAND_JSON` as JSON argv
arrays only after reviewing and installing the selected open-source crawlers.
Wrappers receive `--request-json` and must print a JSON array to stdout.

## Verify

```bash
python scripts/trip_schedule.py health --json
```

## Open an itinerary

```bash
python scripts/trip_schedule.py serve trip-output/<trip-directory>
```
````

- [ ] **Step 5: Regenerate `agents/openai.yaml`**

Run:

```bash
conda run -n agent python \
  /Users/asuna/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py \
  trip-schedule \
  --interface 'display_name=Trip Schedule' \
  --interface 'short_description=Plan sourced, budget-aware trips in China' \
  --interface 'default_prompt=Use $trip-schedule to plan a sourced, budget-aware trip in mainland China.'
```

Then confirm:

```yaml
policy:
  allow_implicit_invocation: true
```

- [ ] **Step 6: Run content tests and official validation**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_skill_content.py -v
```

Expected: all content tests pass.

Run:

```bash
conda run -n agent python \
  /Users/asuna/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  trip-schedule
```

Expected: valid Skill.

- [ ] **Step 7: Commit Skill instructions and installation**

Run:

```bash
git add \
  trip-schedule/SKILL.md \
  trip-schedule/README.md \
  trip-schedule/agents/openai.yaml \
  trip-schedule/tests/test_skill_content.py
git commit -m "Document trip schedule workflow" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 7: Add secret scanning and end-to-end verification

**Files:**
- Create: `trip-schedule/tests/test_secret_scan.py`
- Create: `trip-schedule/tests/test_live_smoke.py`

- [ ] **Step 1: Add a repository secret-shape test**

Create `trip-schedule/tests/test_secret_scan.py`:

```python
import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
HEX_32 = re.compile(r"(?<![A-Za-z0-9])[0-9a-fA-F]{32}(?![A-Za-z0-9])")
ENV_ASSIGNMENT = re.compile(
    r"AMAP_(?:WEBSERVICE_KEY|JSAPI_KEY|SECURITY_KEY)"
    r"\s*=\s*[\"'](?!<)[^\"']{8,}[\"']"
)


def test_repository_contains_no_credential_values() -> None:
    offenders = []
    for path in SKILL_ROOT.rglob("*"):
        if not path.is_file() or path.suffix in {".pyc", ".png", ".jpg"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in HEX_32.finditer(text):
            offenders.append(f"{path}:{match.start()}")
        for match in ENV_ASSIGNMENT.finditer(text):
            offenders.append(f"{path}:{match.start()}")
    assert offenders == []
```

- [ ] **Step 2: Add opt-in live smoke tests**

Create `trip-schedule/tests/test_live_smoke.py`:

```python
import os

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("TRIP_SCHEDULE_LIVE_TESTS") != "1",
    reason="set TRIP_SCHEDULE_LIVE_TESTS=1 for bounded live checks",
)


def test_live_amap_geocode() -> None:
    from providers.amap import AMapProvider

    result = AMapProvider().geocode("杭州西湖", city="杭州")
    assert result.records


def test_live_train_query() -> None:
    from providers.train_12306 import Train12306Provider, TrainQuery

    result = Train12306Provider().query(
        TrainQuery(
            origin_station="深圳北",
            destination_station="广州南",
            travel_date=os.environ["TRIP_SCHEDULE_TEST_DATE"],
        )
    )
    assert result.status.value in {"ok", "no_results"}
```

Do not add a default live XHS, hotel, or flight test until the user has approved
the exact external crawler commands.

- [ ] **Step 3: Run the complete offline suite**

Run:

```bash
conda run -n agent python -m pytest trip-schedule/tests -v
```

Expected: all offline tests pass; live tests are skipped.

- [ ] **Step 4: Run source-level quality checks**

Run:

```bash
conda run -n agent python -m compileall -q trip-schedule/scripts
```

Expected: exit code `0`.

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: Run opt-in live checks only with configured credentials**

Run after explicit approval:

```bash
TRIP_SCHEDULE_LIVE_TESTS=1 \
TRIP_SCHEDULE_TEST_DATE=<future-YYYY-MM-DD> \
conda run -n agent python -m pytest \
  trip-schedule/tests/test_live_smoke.py -v
```

Expected: AMap returns a geocode and 12306 returns either results or a valid
empty result. Do not log environment-variable values.

- [ ] **Step 6: Run final Skill validation**

Run:

```bash
conda run -n agent python \
  /Users/asuna/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  trip-schedule
```

Expected: valid Skill.

- [ ] **Step 7: Commit final verification**

Run:

```bash
git add \
  trip-schedule/tests/test_secret_scan.py \
  trip-schedule/tests/test_live_smoke.py
git commit -m "Verify trip schedule skill package" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

## Milestone Exit Criteria

- Origin and destination cities resolve to bounded station and airport options.
- One-shot generation writes every required artifact.
- Interactive mode has three validated checkpoints and a complete terminal state.
- Static HTML and repository files contain no AMap credentials.
- The itinerary server binds only to loopback and keeps the AMap security code
  server-side.
- `SKILL.md` asks for all six required inputs and generation mode.
- README uses generic `python -m pip` installation and no Conda requirement.
- All offline tests and official Skill validation pass.
- Live tests run only after explicit approval.
