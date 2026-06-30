# Trip Schedule Research, Planning, and Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable Xiaohongshu/Dianping/OTA crawler bridges, AMap Web Service data, deterministic itinerary planning, and redacted bounded Skill memory.

**Architecture:** Treat social-media and hotel crawlers as external read-only commands with a strict JSON contract, keeping fragile platform code outside the Skill core. Normalize their results, enrich locations through AMap, then run pure planning functions for budget allocation, clustering, transport policy, ranking, and memory updates.

**Tech Stack:** Python 3.10+, Pydantic 2, Requests, standard-library subprocess/JSON, Pytest

---

## File Map

Create or modify:

```text
trip-schedule/scripts/
├── models.py
├── memory_store.py
├── providers/
│   ├── command_provider.py
│   ├── xhs.py
│   ├── hotels.py
│   └── amap.py
└── planning/
    ├── __init__.py
    ├── attraction_resolver.py
    ├── budget.py
    ├── clustering.py
    ├── hotel_stages.py
    ├── routing.py
    ├── scheduling.py
    ├── scoring.py
    └── engine.py

trip-schedule/tests/
├── fixtures/
│   ├── xhs-notes.jsonl
│   ├── hotel-results.json
│   └── amap-routes.json
├── test_command_provider.py
├── test_xhs_provider.py
├── test_hotel_provider.py
├── test_amap_provider.py
├── test_attraction_resolver.py
├── test_budget.py
├── test_clustering.py
├── test_routing.py
├── test_scheduling.py
├── test_hotel_stages.py
├── test_scoring.py
├── test_planning_engine.py
├── test_memory_store.py
└── test_research_health.py
```

The Skill does not vendor MediaCrawler or an OTA crawler. Users may configure
compatible wrappers through environment variables. The Skill never invokes a
shell string and never installs a crawler automatically.

### Task 1: Add attraction, hotel, route, and plan models

**Files:**
- Modify: `trip-schedule/scripts/models.py`
- Modify: `trip-schedule/tests/test_models.py`

- [ ] **Step 1: Add failing model tests**

Append to `trip-schedule/tests/test_models.py`:

```python
from models import Attraction, HotelOption, RouteMode, RouteSegment


def test_attraction_requires_coordinates_after_amap_enrichment() -> None:
    with pytest.raises(ValidationError):
        Attraction(
            name="西湖",
            description="湖区景点",
            latitude=91,
            longitude=120.15,
            ticket_price_cny=0,
            suggested_visit_minutes=180,
            evidence=[],
        )


def test_hotel_price_is_total_for_the_requested_stay() -> None:
    hotel = HotelOption(
        name="示例酒店",
        latitude=30.25,
        longitude=120.16,
        total_price_cny=800,
        nights=2,
        transit_notes=["地铁 1 号线"],
        evidence=[],
    )

    assert hotel.total_price_cny == 800


def test_route_segment_has_explicit_mode_and_reason() -> None:
    segment = RouteSegment(
        origin_name="酒店",
        destination_name="西湖",
        mode=RouteMode.TRANSIT,
        distance_meters=5000,
        duration_minutes=35,
        estimated_cost_cny=6,
        reason="Public transport is the default.",
        path=[(120.16, 30.25), (120.15, 30.24)],
    )

    assert segment.mode is RouteMode.TRANSIT
```

- [ ] **Step 2: Run model tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_models.py -v
```

Expected: import failures for the new models.

- [ ] **Step 3: Add the models**

Append to `trip-schedule/scripts/models.py`:

```python
class RouteMode(StrEnum):
    WALK = "walk"
    TRANSIT = "transit"
    TAXI = "taxi"


class Attraction(StrictModel):
    name: str
    description: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str | None = None
    opening_hours: list[str] = Field(default_factory=list)
    ticket_price_cny: float | None = Field(default=None, ge=0)
    suggested_visit_minutes: int = Field(gt=0)
    evidence: list[SourceEvidence]


class HotelOption(StrictModel):
    name: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    address: str | None = None
    total_price_cny: float | None = Field(default=None, ge=0)
    nights: int = Field(gt=0)
    rating: float | None = Field(default=None, ge=0, le=5)
    review_count: int | None = Field(default=None, ge=0)
    transit_notes: list[str] = Field(default_factory=list)
    evidence: list[SourceEvidence]


class RouteSegment(StrictModel):
    origin_name: str
    destination_name: str
    mode: RouteMode
    distance_meters: int = Field(ge=0)
    duration_minutes: int = Field(gt=0)
    estimated_cost_cny: float = Field(ge=0)
    reason: str
    path: list[tuple[float, float]] = Field(min_length=2)


class DaySchedule(StrictModel):
    day_index: int = Field(gt=0)
    attractions: list[Attraction]
    hotel_name: str | None = None
    planned_visit_minutes: int = Field(ge=0)


class HotelStageOption(StrictModel):
    option_id: str
    hotels: list[HotelOption] = Field(min_length=1)
    days: list[DaySchedule] = Field(min_length=1)
    routes: list[RouteSegment]
    total_hotel_cost_cny: float = Field(ge=0)
    total_commute_minutes: int = Field(ge=0)


class CandidatePlan(StrictModel):
    plan_id: str
    label: str
    transport: TransportOffer
    hotels: list[HotelOption]
    attractions: list[Attraction]
    days: list[DaySchedule]
    routes: list[RouteSegment]
    total_cost_cny: float = Field(ge=0)
    contingency_cny: float = Field(ge=0)
    score: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Run model tests and verify GREEN**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_models.py -v
```

Expected: all model tests pass.

- [ ] **Step 5: Commit model expansion**

Run:

```bash
git add \
  trip-schedule/scripts/models.py \
  trip-schedule/tests/test_models.py
git commit -m "Add trip research and plan models" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 2: Implement a safe external crawler command contract

**Files:**
- Create: `trip-schedule/scripts/providers/command_provider.py`
- Create: `trip-schedule/tests/test_command_provider.py`

- [ ] **Step 1: Write failing command-runner tests**

Create `trip-schedule/tests/test_command_provider.py`:

```python
import json
from subprocess import CompletedProcess

import pytest

from providers.command_provider import CommandRunner


def test_command_runner_never_uses_a_shell(monkeypatch) -> None:
    observed = {}

    def fake_run(args, **kwargs):
        observed["args"] = args
        observed["shell"] = kwargs.get("shell")
        return CompletedProcess(args=args, returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr("providers.command_provider.subprocess.run", fake_run)

    result = CommandRunner(["crawler"]).run({"destination": "杭州"})

    assert result == []
    assert observed == {
        "args": ["crawler", "--request-json", '{"destination": "杭州"}'],
        "shell": False,
    }


def test_command_runner_rejects_non_json_stdout(monkeypatch) -> None:
    monkeypatch.setattr(
        "providers.command_provider.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args=args,
            returncode=0,
            stdout="login required",
            stderr="",
        ),
    )

    with pytest.raises(ValueError, match="valid JSON"):
        CommandRunner(["crawler"]).run({"destination": "杭州"})
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_command_provider.py -v
```

Expected: import failure for `providers.command_provider`.

- [ ] **Step 3: Implement the command runner**

Create `trip-schedule/scripts/providers/command_provider.py`:

```python
from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence
from typing import Any


class CommandRunner:
    """Run an explicitly configured crawler wrapper without a shell."""

    def __init__(self, command: Sequence[str], *, timeout_seconds: int = 120) -> None:
        if not command:
            raise ValueError("crawler command must not be empty")
        self.command = list(command)
        self.timeout_seconds = timeout_seconds

    def run(self, request: dict[str, Any]) -> list[dict[str, Any]]:
        request_json = json.dumps(request, ensure_ascii=False, separators=(",", ":"))
        completed = subprocess.run(
            [*self.command, "--request-json", request_json],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            shell=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr[-1000:]
            raise RuntimeError(
                f"crawler exited with {completed.returncode}: {stderr}"
            )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError("crawler stdout is not valid JSON") from exc
        if not isinstance(payload, list) or not all(
            isinstance(item, dict) for item in payload
        ):
            raise ValueError("crawler output must be a JSON array of objects")
        return payload
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_command_provider.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the command contract**

Run:

```bash
git add \
  trip-schedule/scripts/providers/command_provider.py \
  trip-schedule/tests/test_command_provider.py
git commit -m "Add external crawler command contract" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 3: Add the Xiaohongshu evidence provider

**Files:**
- Create: `trip-schedule/scripts/providers/xhs.py`
- Create: `trip-schedule/tests/fixtures/xhs-notes.jsonl`
- Create: `trip-schedule/tests/test_xhs_provider.py`

- [ ] **Step 1: Add a MediaCrawler-compatible sanitized fixture**

Create `trip-schedule/tests/fixtures/xhs-notes.jsonl`:

```jsonl
{"title":"杭州两日路线","desc":"西湖、灵隐寺适合安排在不同半天","liked_count":"1200","collected_count":"850","comment_count":"95","note_url":"https://www.xiaohongshu.com/explore/example1","source_keyword":"杭州 景点"}
{"title":"西湖步行建议","desc":"断桥到曲院风荷建议预留三小时","liked_count":"800","collected_count":"640","comment_count":"50","note_url":"https://www.xiaohongshu.com/explore/example2","source_keyword":"杭州 西湖"}
```

- [ ] **Step 2: Write failing provider tests**

Create `trip-schedule/tests/test_xhs_provider.py`:

```python
from models import ProviderStatus
from providers.xhs import XhsEvidenceProvider, XhsQuery


def test_xhs_provider_reports_missing_command(monkeypatch) -> None:
    monkeypatch.delenv("TRIP_XHS_COMMAND_JSON", raising=False)

    health = XhsEvidenceProvider().health_check()

    assert health.status is ProviderStatus.NOT_CONFIGURED


def test_xhs_provider_preserves_source_evidence(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_XHS_COMMAND_JSON", '["xhs-wrapper"]')
    provider = XhsEvidenceProvider()
    monkeypatch.setattr(
        provider.runner,
        "run",
        lambda _: [
            {
                "title": "杭州两日路线",
                "desc": "西湖适合安排半天",
                "liked_count": "1200",
                "collected_count": "850",
                "comment_count": "95",
                "note_url": "https://www.xiaohongshu.com/explore/example1",
                "source_keyword": "杭州 景点",
            }
        ],
    )

    result = provider.query(XhsQuery(destination="杭州", limit=10))

    assert result.status is ProviderStatus.OK
    assert result.records[0]["source_url"].endswith("example1")
    assert result.records[0]["engagement_score"] > 0
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_xhs_provider.py -v
```

Expected: import failure for `providers.xhs`.

- [ ] **Step 4: Implement the XHS provider**

Create `trip-schedule/scripts/providers/xhs.py`:

```python
from __future__ import annotations

import json
import os
from datetime import datetime

from pydantic import BaseModel, Field

from models import ProviderHealth, ProviderResult, ProviderStatus
from providers.base import Provider
from providers.command_provider import CommandRunner


class XhsQuery(BaseModel):
    destination: str
    limit: int = Field(default=20, ge=1, le=50)


def _count(value: object) -> int:
    try:
        return int(str(value or "0").replace(",", ""))
    except ValueError:
        return 0


class XhsEvidenceProvider(Provider):
    provider_id = "attractions-xhs"

    def __init__(self) -> None:
        raw = os.getenv("TRIP_XHS_COMMAND_JSON")
        self.command = json.loads(raw) if raw else None
        self.runner = CommandRunner(self.command) if self.command else None

    def health_check(self) -> ProviderHealth:
        if self.runner is None:
            return ProviderHealth(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                detail=(
                    "Set TRIP_XHS_COMMAND_JSON to an approved JSON argv array; "
                    "no crawler was installed automatically."
                ),
            )
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.OK,
            detail="external crawler wrapper configured",
        )

    def query(self, request: object) -> ProviderResult:
        query = XhsQuery.model_validate(request)
        queried_at = datetime.now().astimezone()
        if self.runner is None:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                queried_at=queried_at,
                records=[],
            )
        try:
            notes = self.runner.run(
                {
                    "destination": query.destination,
                    "keywords": [
                        f"{query.destination} 景点",
                        f"{query.destination} 旅游攻略",
                    ],
                    "limit": query.limit,
                }
            )
        except RuntimeError as exc:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.CHALLENGE_REQUIRED,
                queried_at=queried_at,
                records=[],
                warnings=[str(exc)],
                error_kind="external_crawler_failed",
            )

        records = []
        for note in notes[: query.limit]:
            likes = _count(note.get("liked_count"))
            collections = _count(note.get("collected_count"))
            comments = _count(note.get("comment_count"))
            records.append(
                {
                    "title": str(note.get("title", "")),
                    "description": str(note.get("desc", "")),
                    "source_keyword": str(note.get("source_keyword", "")),
                    "source_url": str(note["note_url"]),
                    "queried_at": queried_at.isoformat(),
                    "engagement_score": likes + 2 * collections + comments,
                }
            )
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.OK if records else ProviderStatus.NO_RESULTS,
            queried_at=queried_at,
            records=records,
        )
```

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_xhs_provider.py -v
```

Expected: `2 passed`.

- [ ] **Step 6: Document the wrapper boundary**

Add this exact contract to `trip-schedule/references/provider-policy.md`:

```markdown
## External crawler wrapper contract

Set `TRIP_XHS_COMMAND_JSON` to a JSON argv array, for example
`["python", "/approved/path/xhs_wrapper.py"]`. Trip Schedule appends
`--request-json <JSON>`. The wrapper must print one JSON array to stdout and all
diagnostics to stderr. It must return nonzero for login, CAPTCHA, rate-limit, or
schema failures. Trip Schedule never invokes a shell and never installs the
wrapper.

MediaCrawler may be used behind this boundary for personal research when its
license and platform terms permit it. Configure JSON/JSONL output and bounded
collection; do not enable comment or media collection unless the itinerary task
requires it.
```

- [ ] **Step 7: Commit the XHS provider**

Run:

```bash
git add \
  trip-schedule/scripts/providers/xhs.py \
  trip-schedule/tests/fixtures/xhs-notes.jsonl \
  trip-schedule/tests/test_xhs_provider.py \
  trip-schedule/references/provider-policy.md
git commit -m "Add Xiaohongshu evidence provider" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 4: Add the hotel crawler provider

**Files:**
- Create: `trip-schedule/scripts/providers/hotels.py`
- Create: `trip-schedule/tests/fixtures/hotel-results.json`
- Create: `trip-schedule/tests/test_hotel_provider.py`

- [ ] **Step 1: Add a normalized hotel crawler fixture**

Create `trip-schedule/tests/fixtures/hotel-results.json`:

```json
[
  {
    "name": "湖滨示例酒店",
    "latitude": 30.257,
    "longitude": 120.164,
    "address": "杭州湖滨区域",
    "total_price_cny": 920,
    "nights": 2,
    "rating": 4.6,
    "review_count": 1200,
    "transit_notes": ["步行 5 分钟到地铁站"],
    "source": "configured-hotel-crawler",
    "source_url": "https://example.invalid/hotel/1"
  }
]
```

- [ ] **Step 2: Write failing hotel-provider tests**

Create `trip-schedule/tests/test_hotel_provider.py`:

```python
from models import HotelOption, ProviderStatus
from providers.hotels import HotelProvider, HotelQuery


def test_hotel_provider_requires_configured_wrapper(monkeypatch) -> None:
    monkeypatch.delenv("TRIP_HOTEL_COMMAND_JSON", raising=False)

    assert HotelProvider().health_check().status is ProviderStatus.NOT_CONFIGURED


def test_hotel_provider_validates_total_stay_price(monkeypatch) -> None:
    monkeypatch.setenv("TRIP_HOTEL_COMMAND_JSON", '["hotel-wrapper"]')
    provider = HotelProvider()
    monkeypatch.setattr(
        provider.runner,
        "run",
        lambda _: [
            {
                "name": "湖滨示例酒店",
                "latitude": 30.257,
                "longitude": 120.164,
                "total_price_cny": 920,
                "nights": 2,
                "source": "configured-hotel-crawler",
                "source_url": "https://example.invalid/hotel/1",
            }
        ],
    )

    result = provider.query(
        HotelQuery(
            destination="杭州",
            check_in="2026-07-10",
            check_out="2026-07-12",
            travelers=2,
        )
    )

    hotel = HotelOption.model_validate(result.records[0])
    assert hotel.total_price_cny == 920
    assert hotel.nights == 2
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_hotel_provider.py -v
```

Expected: import failure for `providers.hotels`.

- [ ] **Step 4: Implement the hotel provider**

Create `trip-schedule/scripts/providers/hotels.py`:

```python
from __future__ import annotations

import json
import os
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from models import (
    HotelOption,
    HotelStageOption,
    ProviderHealth,
    ProviderResult,
    ProviderStatus,
    SourceEvidence,
)
from providers.base import Provider
from providers.command_provider import CommandRunner


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


class HotelProvider(Provider):
    provider_id = "hotels-external"

    def __init__(self) -> None:
        raw = os.getenv("TRIP_HOTEL_COMMAND_JSON")
        self.command = json.loads(raw) if raw else None
        self.runner = CommandRunner(self.command) if self.command else None

    def health_check(self) -> ProviderHealth:
        if self.runner is None:
            return ProviderHealth(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                detail="Set TRIP_HOTEL_COMMAND_JSON; no crawler was installed.",
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
            )
        try:
            rows = self.runner.run(query.model_dump(mode="json"))
            hotels = [
                HotelOption(
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
                            source=row["source"],
                            source_url=row["source_url"],
                            queried_at=queried_at,
                            confidence=0.75,
                        )
                    ],
                )
                for row in rows
            ]
        except (KeyError, TypeError, ValueError, RuntimeError) as exc:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.SCHEMA_CHANGED,
                queried_at=queried_at,
                records=[],
                warnings=[str(exc)],
                error_kind=type(exc).__name__,
            )
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.OK if hotels else ProviderStatus.NO_RESULTS,
            queried_at=queried_at,
            records=[hotel.model_dump(mode="json") for hotel in hotels],
        )
```

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_hotel_provider.py -v
```

Expected: `2 passed`.

- [ ] **Step 6: Commit the hotel provider**

Run:

```bash
git add \
  trip-schedule/scripts/providers/hotels.py \
  trip-schedule/tests/fixtures/hotel-results.json \
  trip-schedule/tests/test_hotel_provider.py
git commit -m "Add external hotel provider" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 5: Add AMap Web Service enrichment

**Files:**
- Create: `trip-schedule/scripts/providers/amap.py`
- Create: `trip-schedule/tests/fixtures/amap-routes.json`
- Create: `trip-schedule/tests/test_amap_provider.py`

- [ ] **Step 1: Write failing key and redaction tests**

Create `trip-schedule/tests/test_amap_provider.py`:

```python
from models import ProviderStatus
from providers.amap import AMapProvider


def test_amap_health_requires_webservice_key(monkeypatch) -> None:
    monkeypatch.delenv("AMAP_WEBSERVICE_KEY", raising=False)

    assert AMapProvider().health_check().status is ProviderStatus.NOT_CONFIGURED


def test_amap_error_does_not_expose_key(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")
    provider = AMapProvider()

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "0", "info": "INVALID_USER_KEY"}

    monkeypatch.setattr(provider.session, "get", lambda *args, **kwargs: Response())

    result = provider.geocode("杭州西湖")

    assert result.status is ProviderStatus.AUTHENTICATION_FAILED
    assert "secret-value" not in result.model_dump_json()
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_amap_provider.py -v
```

Expected: import failure for `providers.amap`.

- [ ] **Step 3: Implement AMap health and geocoding**

Create `trip-schedule/scripts/providers/amap.py`:

```python
from __future__ import annotations

import os
from datetime import datetime

import requests

from models import ProviderHealth, ProviderResult, ProviderStatus
from providers.base import Provider


class AMapProvider(Provider):
    provider_id = "amap-webservice"

    def __init__(self) -> None:
        self.key = os.getenv("AMAP_WEBSERVICE_KEY")
        self.session = requests.Session()

    def health_check(self) -> ProviderHealth:
        if not self.key:
            return ProviderHealth(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                detail="AMAP_WEBSERVICE_KEY is not set",
            )
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.OK,
            detail="Web Service key configured",
        )

    def query(self, request: object) -> ProviderResult:
        if not isinstance(request, str):
            raise TypeError("AMapProvider.query expects an address string")
        return self.geocode(request)

    def geocode(self, address: str, *, city: str | None = None) -> ProviderResult:
        queried_at = datetime.now().astimezone()
        if not self.key:
            return ProviderResult(
                provider_id=self.provider_id,
                status=ProviderStatus.NOT_CONFIGURED,
                queried_at=queried_at,
                records=[],
            )
        response = self.session.get(
            "https://restapi.amap.com/v3/geocode/geo",
            params={"key": self.key, "address": address, "city": city or ""},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "1":
            info = str(payload.get("info", "unknown AMap error"))
            status = (
                ProviderStatus.AUTHENTICATION_FAILED
                if "KEY" in info or "SCODE" in info
                else ProviderStatus.NETWORK_ERROR
            )
            return ProviderResult(
                provider_id=self.provider_id,
                status=status,
                queried_at=queried_at,
                records=[],
                warnings=[info],
                error_kind="amap_error",
            )
        records = []
        for item in payload.get("geocodes", []):
            longitude, latitude = item["location"].split(",", maxsplit=1)
            records.append(
                {
                    "formatted_address": item.get("formatted_address"),
                    "longitude": float(longitude),
                    "latitude": float(latitude),
                }
            )
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.OK if records else ProviderStatus.NO_RESULTS,
            queried_at=queried_at,
            records=records,
        )
```

- [ ] **Step 4: Add route fixtures and failing route tests**

Create `trip-schedule/tests/fixtures/amap-routes.json`:

```json
{
  "driving": {
    "status": "1",
    "route": {
      "paths": [
        {
          "distance": "8200",
          "duration": "1500",
          "steps": [
            {"polyline": "120.100,30.200;120.150,30.250"}
          ]
        }
      ]
    }
  },
  "transit": {
    "status": "1",
    "route": {
      "transits": [
        {
          "distance": "9000",
          "duration": "2700",
          "cost": "6"
        }
      ]
    }
  }
}
```

Append to `trip-schedule/tests/test_amap_provider.py`:

```python
import json
from pathlib import Path


ROUTE_FIXTURE = Path(__file__).parent / "fixtures" / "amap-routes.json"


class RouteResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


def test_amap_driving_route_extracts_distance_duration_and_path(
    monkeypatch,
) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")
    payload = json.loads(ROUTE_FIXTURE.read_text(encoding="utf-8"))["driving"]
    provider = AMapProvider()
    monkeypatch.setattr(
        provider.session,
        "get",
        lambda *args, **kwargs: RouteResponse(payload),
    )

    result = provider.route_driving((120.1, 30.2), (120.15, 30.25))

    assert result.records[0]["distance_meters"] == 8200
    assert result.records[0]["duration_minutes"] == 25
    assert result.records[0]["path"] == [
        [120.1, 30.2],
        [120.15, 30.25],
    ]


def test_amap_transit_route_extracts_cost(monkeypatch) -> None:
    monkeypatch.setenv("AMAP_WEBSERVICE_KEY", "secret-value")
    payload = json.loads(ROUTE_FIXTURE.read_text(encoding="utf-8"))["transit"]
    provider = AMapProvider()
    monkeypatch.setattr(
        provider.session,
        "get",
        lambda *args, **kwargs: RouteResponse(payload),
    )

    result = provider.route_transit(
        (120.1, 30.2),
        (120.15, 30.25),
        city="杭州",
    )

    assert result.records[0]["estimated_cost_cny"] == 6
    assert result.records[0]["duration_minutes"] == 45
```

- [ ] **Step 5: Implement route methods and schema validation**

Append to `AMapProvider`:

```python
def route_transit(
    self,
    origin: tuple[float, float],
    destination: tuple[float, float],
    *,
    city: str,
) -> ProviderResult:
    return self._route(
        "https://restapi.amap.com/v3/direction/transit/integrated",
        origin,
        destination,
        extra={"city": city, "strategy": 0},
    )


def route_driving(
    self,
    origin: tuple[float, float],
    destination: tuple[float, float],
) -> ProviderResult:
    return self._route(
        "https://restapi.amap.com/v3/direction/driving",
        origin,
        destination,
        extra={"strategy": 0},
    )


def _route(
    self,
    url: str,
    origin: tuple[float, float],
    destination: tuple[float, float],
    *,
    extra: dict[str, object],
) -> ProviderResult:
    queried_at = datetime.now().astimezone()
    if not self.key:
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.NOT_CONFIGURED,
            queried_at=queried_at,
            records=[],
        )
    response = self.session.get(
        url,
        params={
            "key": self.key,
            "origin": f"{origin[0]},{origin[1]}",
            "destination": f"{destination[0]},{destination[1]}",
            **extra,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "1":
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.NETWORK_ERROR,
            queried_at=queried_at,
            records=[],
            warnings=[str(payload.get("info", "AMap route error"))],
            error_kind="amap_error",
        )
    route = payload.get("route", {})
    candidates = route.get("transits") or route.get("paths") or []
    if not candidates:
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.SCHEMA_CHANGED,
            queried_at=queried_at,
            records=[],
            warnings=["AMap route response has no paths or transits"],
            error_kind="missing_route_candidates",
        )
    candidate = candidates[0]
    try:
        distance = int(float(candidate["distance"]))
        duration_minutes = max(1, round(float(candidate["duration"]) / 60))
    except (KeyError, TypeError, ValueError) as exc:
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.SCHEMA_CHANGED,
            queried_at=queried_at,
            records=[],
            warnings=[type(exc).__name__],
            error_kind="invalid_route_fields",
        )
    path = []
    for step in candidate.get("steps", []):
        for point in str(step.get("polyline", "")).split(";"):
            if "," not in point:
                continue
            longitude, latitude = point.split(",", maxsplit=1)
            path.append([float(longitude), float(latitude)])
    return ProviderResult(
        provider_id=self.provider_id,
        status=ProviderStatus.OK,
        queried_at=queried_at,
        records=[
            {
                "distance_meters": distance,
                "duration_minutes": duration_minutes,
                "estimated_cost_cny": float(candidate.get("cost") or 0),
                "path": path or [list(origin), list(destination)],
            }
        ],
    )
```

Never include request parameters in an error string because they contain the
key.

- [ ] **Step 6: Run AMap tests and verify GREEN**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_amap_provider.py -v
```

Expected: health, redaction, geocode, transit, and driving tests pass.

- [ ] **Step 7: Commit AMap enrichment**

Run:

```bash
git add \
  trip-schedule/scripts/providers/amap.py \
  trip-schedule/tests/fixtures/amap-routes.json \
  trip-schedule/tests/test_amap_provider.py
git commit -m "Add AMap route provider" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 6: Resolve sourced attraction candidates through AMap

**Files:**
- Modify: `trip-schedule/scripts/providers/amap.py`
- Create: `trip-schedule/scripts/planning/attraction_resolver.py`
- Create: `trip-schedule/tests/test_attraction_resolver.py`

- [ ] **Step 1: Write a failing sourced-candidate test**

Create `trip-schedule/tests/test_attraction_resolver.py`:

```python
from models import ProviderResult, ProviderStatus
from planning.attraction_resolver import AttractionCandidate, AttractionResolver


class FakeAMap:
    def search_poi(self, keyword: str, *, city: str) -> ProviderResult:
        return ProviderResult(
            provider_id="amap-webservice",
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[
                {
                    "name": "西湖风景名胜区",
                    "address": "杭州市西湖区",
                    "longitude": 120.150,
                    "latitude": 30.250,
                }
            ],
        )


def test_resolver_combines_media_evidence_with_amap_coordinates() -> None:
    candidate = AttractionCandidate(
        name="西湖",
        description="建议预留三小时",
        source_url="https://www.xiaohongshu.com/explore/example",
        queried_at="2026-07-01T09:00:00+08:00",
        suggested_visit_minutes=180,
        ticket_price_cny=0,
    )

    attractions, warnings = AttractionResolver(FakeAMap()).resolve(
        [candidate],
        city="杭州",
    )

    assert warnings == []
    assert attractions[0].name == "西湖风景名胜区"
    assert attractions[0].longitude == 120.150
    assert attractions[0].evidence[0].source == "Xiaohongshu"
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_attraction_resolver.py -v
```

Expected: import failure for `planning.attraction_resolver`.

- [ ] **Step 3: Add AMap POI text search**

Append to `AMapProvider`:

```python
def search_poi(self, keyword: str, *, city: str) -> ProviderResult:
    queried_at = datetime.now().astimezone()
    if not self.key:
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.NOT_CONFIGURED,
            queried_at=queried_at,
            records=[],
        )
    response = self.session.get(
        "https://restapi.amap.com/v3/place/text",
        params={
            "key": self.key,
            "keywords": keyword,
            "city": city,
            "citylimit": "true",
            "offset": 5,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") != "1":
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.NETWORK_ERROR,
            queried_at=queried_at,
            records=[],
            warnings=[str(payload.get("info", "AMap POI error"))],
            error_kind="amap_error",
        )
    records = []
    for item in payload.get("pois", []):
        location = item.get("location")
        if not location or "," not in location:
            continue
        longitude, latitude = location.split(",", maxsplit=1)
        records.append(
            {
                "name": item.get("name") or keyword,
                "address": item.get("address") or None,
                "longitude": float(longitude),
                "latitude": float(latitude),
            }
        )
    return ProviderResult(
        provider_id=self.provider_id,
        status=ProviderStatus.OK if records else ProviderStatus.NO_RESULTS,
        queried_at=queried_at,
        records=records,
    )
```

- [ ] **Step 4: Implement the attraction resolver**

Create `trip-schedule/scripts/planning/attraction_resolver.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, Field

from models import Attraction, ProviderResult, ProviderStatus, SourceEvidence


class POISearch(Protocol):
    def search_poi(self, keyword: str, *, city: str) -> ProviderResult:
        ...


class AttractionCandidate(BaseModel):
    name: str
    description: str
    source_url: str
    queried_at: datetime
    suggested_visit_minutes: int = Field(gt=0)
    ticket_price_cny: float | None = Field(default=None, ge=0)


class AttractionResolver:
    def __init__(self, amap: POISearch) -> None:
        self.amap = amap

    def resolve(
        self,
        candidates: list[AttractionCandidate],
        *,
        city: str,
    ) -> tuple[list[Attraction], list[str]]:
        attractions: list[Attraction] = []
        warnings: list[str] = []
        for candidate in candidates:
            result = self.amap.search_poi(candidate.name, city=city)
            if result.status is not ProviderStatus.OK or not result.records:
                warnings.append(f"AMap could not resolve: {candidate.name}")
                continue
            poi = result.records[0]
            attractions.append(
                Attraction(
                    name=poi["name"],
                    description=candidate.description,
                    latitude=poi["latitude"],
                    longitude=poi["longitude"],
                    address=poi.get("address"),
                    ticket_price_cny=candidate.ticket_price_cny,
                    suggested_visit_minutes=candidate.suggested_visit_minutes,
                    evidence=[
                        SourceEvidence(
                            source="Xiaohongshu",
                            source_url=candidate.source_url,
                            queried_at=candidate.queried_at,
                            confidence=0.65,
                        ),
                        SourceEvidence(
                            source="AMap",
                            source_url="https://lbs.amap.com/",
                            queried_at=result.queried_at,
                            confidence=0.9,
                        ),
                    ],
                )
            )
        return attractions, warnings
```

- [ ] **Step 5: Document the agent-to-script candidate file**

Append to `trip-schedule/references/data-contracts.md`:

```markdown
## Attraction candidate handoff

After reviewing XHS/Dianping evidence, the agent writes
`attraction_candidates.json`. Each item contains `name`, `description`,
`source_url`, `queried_at`, `suggested_visit_minutes`, and nullable
`ticket_price_cny`. The resolver accepts only these fields and verifies every
location through AMap before creating an `Attraction`.
```

- [ ] **Step 6: Run resolver and AMap tests**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_attraction_resolver.py \
  trip-schedule/tests/test_amap_provider.py -v
```

Expected: all POI search and attraction resolution tests pass.

- [ ] **Step 7: Commit attraction resolution**

Run:

```bash
git add \
  trip-schedule/scripts/providers/amap.py \
  trip-schedule/scripts/planning/attraction_resolver.py \
  trip-schedule/tests/test_attraction_resolver.py \
  trip-schedule/references/data-contracts.md
git commit -m "Resolve sourced attraction candidates" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 7: Implement budget allocation and plan scoring

**Files:**
- Create: `trip-schedule/scripts/planning/__init__.py`
- Create: `trip-schedule/scripts/planning/budget.py`
- Create: `trip-schedule/scripts/planning/scoring.py`
- Create: `trip-schedule/tests/test_budget.py`
- Create: `trip-schedule/tests/test_scoring.py`

- [ ] **Step 1: Write failing budget tests**

Create `trip-schedule/tests/test_budget.py`:

```python
from planning.budget import BudgetPolicy


def test_budget_reserves_ten_percent_contingency() -> None:
    allocation = BudgetPolicy().allocate(5000)

    assert allocation.contingency_cny == 500
    assert sum(allocation.categories.values()) == 4500


def test_budget_reports_deficit_instead_of_hiding_it() -> None:
    deficit = BudgetPolicy().deficit(budget_cny=5000, planned_cost_cny=5600)

    assert deficit == 1100
```

- [ ] **Step 2: Run budget tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_budget.py -v
```

Expected: import failure for `planning.budget`.

- [ ] **Step 3: Implement the budget policy**

Create `trip-schedule/scripts/planning/__init__.py`:

```python
"""Pure itinerary planning functions."""
```

Create `trip-schedule/scripts/planning/budget.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BudgetAllocation:
    contingency_cny: float
    categories: dict[str, float]


class BudgetPolicy:
    def __init__(self, contingency_ratio: float = 0.10) -> None:
        self.contingency_ratio = contingency_ratio

    def allocate(self, budget_cny: float) -> BudgetAllocation:
        contingency = round(budget_cny * self.contingency_ratio, 2)
        usable = round(budget_cny - contingency, 2)
        ratios = {
            "intercity": 0.30,
            "accommodation": 0.35,
            "attractions": 0.15,
            "local_transport": 0.10,
            "fixed_costs": 0.10,
        }
        categories = {
            name: round(usable * ratio, 2) for name, ratio in ratios.items()
        }
        rounding_delta = round(usable - sum(categories.values()), 2)
        categories["fixed_costs"] += rounding_delta
        return BudgetAllocation(
            contingency_cny=contingency,
            categories=categories,
        )

    def deficit(self, *, budget_cny: float, planned_cost_cny: float) -> float:
        usable = budget_cny * (1 - self.contingency_ratio)
        return round(max(0, planned_cost_cny - usable), 2)
```

- [ ] **Step 4: Write failing scoring tests**

Create `trip-schedule/tests/test_scoring.py`:

```python
from planning.scoring import score_plan


def test_scoring_uses_approved_weights() -> None:
    score = score_plan(
        affordability=1,
        door_to_door_time=0.5,
        convenience=0.5,
        data_confidence=1,
    )

    assert score == 0.8
```

- [ ] **Step 5: Implement exact approved weights**

Create `trip-schedule/scripts/planning/scoring.py`:

```python
def score_plan(
    *,
    affordability: float,
    door_to_door_time: float,
    convenience: float,
    data_confidence: float,
) -> float:
    values = (
        affordability,
        door_to_door_time,
        convenience,
        data_confidence,
    )
    if any(value < 0 or value > 1 for value in values):
        raise ValueError("component scores must be between 0 and 1")
    return round(
        0.40 * affordability
        + 0.25 * door_to_door_time
        + 0.15 * convenience
        + 0.20 * data_confidence,
        4,
    )
```

- [ ] **Step 6: Run budget and scoring tests**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_budget.py \
  trip-schedule/tests/test_scoring.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit budget and scoring**

Run:

```bash
git add \
  trip-schedule/scripts/planning \
  trip-schedule/tests/test_budget.py \
  trip-schedule/tests/test_scoring.py
git commit -m "Add trip budget and scoring rules" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 8: Implement clustering and local transport policy

**Files:**
- Create: `trip-schedule/scripts/planning/clustering.py`
- Create: `trip-schedule/scripts/planning/routing.py`
- Create: `trip-schedule/tests/test_clustering.py`
- Create: `trip-schedule/tests/test_routing.py`

- [ ] **Step 1: Write failing clustering tests**

Create `trip-schedule/tests/test_clustering.py`:

```python
from planning.clustering import cluster_points


def test_cluster_points_groups_nearby_attractions() -> None:
    points = [
        ("A", 30.2500, 120.1600),
        ("B", 30.2550, 120.1650),
        ("C", 30.3100, 120.2200),
    ]

    clusters = cluster_points(points, radius_km=2)

    assert [[item[0] for item in cluster] for cluster in clusters] == [
        ["A", "B"],
        ["C"],
    ]
```

- [ ] **Step 2: Implement deterministic geographic clustering**

Create `trip-schedule/scripts/planning/clustering.py`:

```python
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt


Point = tuple[str, float, float]


def haversine_km(left: Point, right: Point) -> float:
    _, lat1, lon1 = left
    _, lat2, lon2 = right
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    value = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return 6371 * 2 * asin(sqrt(value))


def cluster_points(points: list[Point], *, radius_km: float) -> list[list[Point]]:
    clusters: list[list[Point]] = []
    for point in points:
        for cluster in clusters:
            if any(haversine_km(point, member) <= radius_km for member in cluster):
                cluster.append(point)
                break
        else:
            clusters.append([point])
    return clusters
```

- [ ] **Step 3: Write failing taxi-policy tests**

Create `trip-schedule/tests/test_routing.py`:

```python
from models import RouteMode
from planning.routing import choose_local_mode


def test_public_transit_is_default() -> None:
    decision = choose_local_mode(
        distance_km=8,
        transit_minutes=45,
        taxi_minutes=30,
        taxi_cost_cny=45,
        travelers=2,
        late_night=False,
        has_luggage=False,
    )

    assert decision.mode is RouteMode.TRANSIT


def test_taxi_is_recommended_for_large_time_saving() -> None:
    decision = choose_local_mode(
        distance_km=10,
        transit_minutes=70,
        taxi_minutes=30,
        taxi_cost_cny=55,
        travelers=3,
        late_night=False,
        has_luggage=False,
    )

    assert decision.mode is RouteMode.TAXI
    assert "40 minutes" in decision.reason


def test_long_taxi_requires_exception_reason() -> None:
    decision = choose_local_mode(
        distance_km=20,
        transit_minutes=0,
        taxi_minutes=35,
        taxi_cost_cny=90,
        travelers=2,
        late_night=True,
        has_luggage=True,
    )

    assert decision.mode is RouteMode.TAXI
    assert "exception" in decision.reason.lower()
```

- [ ] **Step 4: Implement the local mode decision**

Create `trip-schedule/scripts/planning/routing.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from models import RouteMode


@dataclass(frozen=True)
class RouteDecision:
    mode: RouteMode
    reason: str


def choose_local_mode(
    *,
    distance_km: float,
    transit_minutes: int,
    taxi_minutes: int,
    taxi_cost_cny: float,
    travelers: int,
    late_night: bool,
    has_luggage: bool,
) -> RouteDecision:
    transit_unavailable = transit_minutes <= 0
    time_saved = max(0, transit_minutes - taxi_minutes)
    practical_need = late_night or has_luggage or transit_unavailable
    if distance_km > 15 and practical_need:
        return RouteDecision(
            mode=RouteMode.TAXI,
            reason=(
                "Taxi exception beyond 15 km because transit is impractical "
                "for this segment."
            ),
        )
    if distance_km <= 15 and (time_saved >= 25 or practical_need):
        return RouteDecision(
            mode=RouteMode.TAXI,
            reason=(
                f"Taxi saves {time_saved} minutes or satisfies a practical "
                f"need; estimated per-person cost is "
                f"{taxi_cost_cny / travelers:.2f} CNY."
            ),
        )
    return RouteDecision(
        mode=RouteMode.TRANSIT,
        reason="Public transport is the default for this segment.",
    )
```

- [ ] **Step 5: Run clustering and routing tests**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_clustering.py \
  trip-schedule/tests/test_routing.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit geographic planning rules**

Run:

```bash
git add \
  trip-schedule/scripts/planning/clustering.py \
  trip-schedule/scripts/planning/routing.py \
  trip-schedule/tests/test_clustering.py \
  trip-schedule/tests/test_routing.py
git commit -m "Add trip clustering and routing policy" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 9: Schedule days and multi-stage hotel alternatives

**Files:**
- Create: `trip-schedule/scripts/planning/scheduling.py`
- Create: `trip-schedule/scripts/planning/hotel_stages.py`
- Create: `trip-schedule/tests/test_scheduling.py`
- Create: `trip-schedule/tests/test_hotel_stages.py`

- [ ] **Step 1: Write failing day-scheduling tests**

Create `trip-schedule/tests/test_scheduling.py`:

```python
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
```

- [ ] **Step 2: Implement geographic day scheduling**

Create `trip-schedule/scripts/planning/scheduling.py`:

```python
from __future__ import annotations

from models import Attraction, DaySchedule
from planning.clustering import cluster_points


def schedule_attractions(
    attractions: list[Attraction],
    *,
    duration_days: int,
    daily_visit_minutes: int = 480,
) -> list[DaySchedule]:
    if duration_days <= 0:
        raise ValueError("duration_days must be positive")
    points = [
        (item.name, item.latitude, item.longitude) for item in attractions
    ]
    clusters = cluster_points(points, radius_km=2)
    by_name = {item.name: item for item in attractions}
    ordered = [
        by_name[name]
        for cluster in clusters
        for name, _, _ in cluster
    ]
    days: list[list[Attraction]] = [[]]
    minutes = 0
    for item in ordered:
        would_overflow = (
            days[-1]
            and minutes + item.suggested_visit_minutes > daily_visit_minutes
        )
        if would_overflow and len(days) < duration_days:
            days.append([])
            minutes = 0
        days[-1].append(item)
        minutes += item.suggested_visit_minutes
    return [
        DaySchedule(
            day_index=index,
            attractions=items,
            planned_visit_minutes=sum(
                item.suggested_visit_minutes for item in items
            ),
        )
        for index, items in enumerate(days, start=1)
    ]
```

- [ ] **Step 3: Write failing hotel-stage tests**

Create `trip-schedule/tests/test_hotel_stages.py`:

```python
from models import DaySchedule, HotelOption, RouteMode, RouteSegment
from planning.hotel_stages import build_hotel_stage_options
from test_scheduling import attraction, make_evidence


def route(hotel: str, destination: str, minutes: int) -> RouteSegment:
    return RouteSegment(
        origin_name=hotel,
        destination_name=destination,
        mode=RouteMode.TRANSIT,
        distance_meters=5000,
        duration_minutes=minutes,
        estimated_cost_cny=6,
        reason="Public transport is the default.",
        path=[(120.16, 30.25), (120.15, 30.25)],
    )


def test_multi_hotel_option_requires_sixty_minute_saving() -> None:
    hotels = [
        HotelOption(
            name="Hotel A",
            latitude=30.25,
            longitude=120.16,
            total_price_cny=800,
            nights=2,
            evidence=[make_evidence("hotel")],
        ),
        HotelOption(
            name="Hotel B",
            latitude=30.32,
            longitude=120.23,
            total_price_cny=900,
            nights=2,
            evidence=[make_evidence("hotel")],
        ),
    ]
    days = [
        DaySchedule(
            day_index=1,
            attractions=[attraction("A", 30.25, 120.16, 180)],
            planned_visit_minutes=180,
        ),
        DaySchedule(
            day_index=2,
            attractions=[attraction("B", 30.32, 120.23, 180)],
            planned_visit_minutes=180,
        ),
    ]
    routes = {
        "Hotel A": [route("Hotel A", "A", 10), route("Hotel A", "B", 100)],
        "Hotel B": [route("Hotel B", "A", 100), route("Hotel B", "B", 10)],
    }

    options = build_hotel_stage_options(days, hotels, routes)

    assert any(len(option.hotels) == 2 for option in options)
```

- [ ] **Step 4: Implement single- and multi-hotel stage options**

Create `trip-schedule/scripts/planning/hotel_stages.py`:

```python
from __future__ import annotations

from models import DaySchedule, HotelOption, HotelStageOption, RouteSegment


def _route_index(
    routes_by_hotel: dict[str, list[RouteSegment]],
) -> dict[tuple[str, str], RouteSegment]:
    return {
        (hotel_name, route.destination_name): route
        for hotel_name, routes in routes_by_hotel.items()
        for route in routes
    }


def _commute_for_day(
    hotel_name: str,
    day: DaySchedule,
    index: dict[tuple[str, str], RouteSegment],
) -> int:
    return sum(
        index[(hotel_name, attraction.name)].duration_minutes
        for attraction in day.attractions
        if (hotel_name, attraction.name) in index
    )


def build_hotel_stage_options(
    days: list[DaySchedule],
    hotels: list[HotelOption],
    routes_by_hotel: dict[str, list[RouteSegment]],
) -> list[HotelStageOption]:
    index = _route_index(routes_by_hotel)
    options: list[HotelStageOption] = []
    for hotel in hotels:
        selected_routes = routes_by_hotel.get(hotel.name, [])
        commute = sum(
            _commute_for_day(hotel.name, day, index) for day in days
        )
        options.append(
            HotelStageOption(
                option_id=f"single:{hotel.name}",
                hotels=[hotel],
                days=[
                    day.model_copy(update={"hotel_name": hotel.name})
                    for day in days
                ],
                routes=selected_routes,
                total_hotel_cost_cny=hotel.total_price_cny or 0,
                total_commute_minutes=commute,
            )
        )
    if not options:
        return []

    best_single = min(options, key=lambda item: item.total_commute_minutes)
    selected_by_day = [
        min(
            hotels,
            key=lambda hotel: _commute_for_day(hotel.name, day, index),
        )
        for day in days
    ]
    unique_hotels = list({hotel.name: hotel for hotel in selected_by_day}.values())
    multi_commute = sum(
        _commute_for_day(hotel.name, day, index)
        for hotel, day in zip(selected_by_day, days, strict=True)
    )
    saving = best_single.total_commute_minutes - multi_commute
    if len(unique_hotels) > 1 and saving >= 60:
        day_counts = {
            hotel.name: sum(
                selected.name == hotel.name for selected in selected_by_day
            )
            for hotel in unique_hotels
        }
        stage_hotels = []
        for hotel in unique_hotels:
            stage_nights = max(1, min(day_counts[hotel.name], hotel.nights))
            nightly = (hotel.total_price_cny or 0) / hotel.nights
            stage_hotels.append(
                hotel.model_copy(
                    update={
                        "nights": stage_nights,
                        "total_price_cny": round(nightly * stage_nights, 2),
                    }
                )
            )
        options.append(
            HotelStageOption(
                option_id="multi:" + "+".join(
                    hotel.name for hotel in stage_hotels
                ),
                hotels=stage_hotels,
                days=[
                    day.model_copy(update={"hotel_name": hotel.name})
                    for day, hotel in zip(days, selected_by_day, strict=True)
                ],
                routes=[
                    index[(hotel.name, attraction.name)]
                    for day, hotel in zip(days, selected_by_day, strict=True)
                    for attraction in day.attractions
                    if (hotel.name, attraction.name) in index
                ],
                total_hotel_cost_cny=sum(
                    hotel.total_price_cny or 0 for hotel in stage_hotels
                ),
                total_commute_minutes=multi_commute,
            )
        )
    return options
```

- [ ] **Step 5: Run scheduling and hotel-stage tests**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_scheduling.py \
  trip-schedule/tests/test_hotel_stages.py -v
```

Expected: both geographic scheduling and the 60-minute switch rule pass.

- [ ] **Step 6: Commit scheduling and hotel stages**

Run:

```bash
git add \
  trip-schedule/scripts/planning/scheduling.py \
  trip-schedule/scripts/planning/hotel_stages.py \
  trip-schedule/tests/test_scheduling.py \
  trip-schedule/tests/test_hotel_stages.py
git commit -m "Schedule trip days and hotel stages" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 10: Implement candidate-plan generation

**Files:**
- Create: `trip-schedule/scripts/planning/engine.py`
- Create: `trip-schedule/tests/test_planning_engine.py`

- [ ] **Step 1: Write failing hard-budget and alternative tests**

Create `trip-schedule/tests/test_planning_engine.py`:

```python
from models import (
    Attraction,
    HotelOption,
    RouteMode,
    RouteSegment,
    SourceEvidence,
    TransportMode,
    TransportOffer,
)
from planning.engine import PlanningEngine, PlanningInputs
from planning.hotel_stages import build_hotel_stage_options
from planning.scheduling import schedule_attractions


def make_evidence(source: str) -> SourceEvidence:
    return SourceEvidence(
        source=source,
        source_url="https://example.invalid/source",
        queried_at="2026-07-01T10:00:00+08:00",
        confidence=0.8,
    )


def make_inputs() -> PlanningInputs:
    transports = [
        TransportOffer(
            provider_id="transport-test",
            mode=TransportMode.FLIGHT,
            service_id="F100",
            origin_name="SZX",
            destination_name="HGH",
            departure_at="2026-07-10T08:00:00+08:00",
            arrival_at="2026-07-10T10:00:00+08:00",
            duration_minutes=120,
            total_price_cny=600,
            evidence=make_evidence("flight"),
        ),
        TransportOffer(
            provider_id="transport-test",
            mode=TransportMode.TRAIN,
            service_id="G100",
            origin_name="深圳北",
            destination_name="杭州东",
            departure_at="2026-07-10T08:00:00+08:00",
            arrival_at="2026-07-10T14:00:00+08:00",
            duration_minutes=360,
            total_price_cny=450,
            evidence=make_evidence("train"),
        ),
    ]
    hotels = [
        HotelOption(
            name=f"Hotel {index}",
            latitude=30.25 + index / 1000,
            longitude=120.16,
            total_price_cny=price,
            nights=2,
            evidence=[make_evidence("hotel")],
        )
        for index, price in enumerate((700, 900, 1200), start=1)
    ]
    attractions = [
        Attraction(
            name="西湖",
            description="湖区",
            latitude=30.25,
            longitude=120.15,
            ticket_price_cny=0,
            suggested_visit_minutes=180,
            evidence=[make_evidence("xhs")],
        )
    ]
    route_template = [
        RouteSegment(
            origin_name="Hotel 1",
            destination_name="西湖",
            mode=RouteMode.TRANSIT,
            distance_meters=5000,
            duration_minutes=35,
            estimated_cost_cny=6,
            reason="Public transport is the default.",
            path=[(120.16, 30.25), (120.15, 30.25)],
        )
    ]
    routes_by_hotel = {
        hotel.name: [
            route.model_copy(update={"origin_name": hotel.name})
            for route in route_template
        ]
        for hotel in hotels
    }
    days = schedule_attractions(attractions, duration_days=3)
    hotel_stage_options = build_hotel_stage_options(
        days,
        hotels,
        routes_by_hotel,
    )
    return PlanningInputs(
        budget_cny=5000,
        travelers=2,
        transports=transports,
        attractions=attractions,
        hotel_stage_options=hotel_stage_options,
    )


def test_engine_rejects_over_budget_candidates() -> None:
    inputs = make_inputs().model_copy(update={"budget_cny": 500})

    result = PlanningEngine().build(inputs)

    assert result.plans == []
    assert result.minimum_deficit_cny > 0


def test_engine_labels_three_distinct_strategies() -> None:
    result = PlanningEngine().build(make_inputs())

    assert [plan.label for plan in result.plans] == [
        "balanced",
        "economy",
        "time-saving",
    ]
    underlying_ids = {
        plan.plan_id.removeprefix(f"{plan.label}-") for plan in result.plans
    }
    assert len(underlying_ids) == 3
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_planning_engine.py -v
```

Expected: import failure for `planning.engine`.

- [ ] **Step 3: Implement the planning engine**

Create `trip-schedule/scripts/planning/engine.py`:

```python
from __future__ import annotations

from itertools import product

from pydantic import BaseModel

from models import Attraction, CandidatePlan, HotelStageOption, TransportOffer
from planning.budget import BudgetPolicy
from planning.scoring import score_plan


class PlanningInputs(BaseModel):
    budget_cny: float
    travelers: int
    transports: list[TransportOffer]
    attractions: list[Attraction]
    hotel_stage_options: list[HotelStageOption]


class PlanningResult(BaseModel):
    plans: list[CandidatePlan]
    minimum_deficit_cny: float = 0


class PlanningEngine:
    def __init__(self) -> None:
        self.budget_policy = BudgetPolicy()

    def build(self, inputs: PlanningInputs) -> PlanningResult:
        attraction_cost = sum(
            (item.ticket_price_cny or 0) * inputs.travelers
            for item in inputs.attractions
        )
        candidates: list[CandidatePlan] = []
        deficits: list[float] = []

        combinations = list(product(inputs.transports, inputs.hotel_stage_options))
        if not combinations:
            return PlanningResult(plans=[], minimum_deficit_cny=0)

        max_duration = max(item[0].duration_minutes for item in combinations)
        for transport, hotel_stage in combinations:
            if transport.total_price_cny is None:
                continue
            route_cost = sum(
                item.estimated_cost_cny for item in hotel_stage.routes
            )
            total_cost = (
                transport.total_price_cny * inputs.travelers
                + hotel_stage.total_hotel_cost_cny
                + attraction_cost
                + route_cost
            )
            deficit = self.budget_policy.deficit(
                budget_cny=inputs.budget_cny,
                planned_cost_cny=total_cost,
            )
            deficits.append(deficit)
            if deficit > 0:
                continue
            affordability = max(0, 1 - total_cost / inputs.budget_cny)
            time_score = 1 - transport.duration_minutes / max_duration
            confidence = (
                transport.evidence.confidence
                + sum(
                    evidence.confidence
                    for hotel in hotel_stage.hotels
                    for evidence in hotel.evidence
                )
                / max(
                    1,
                    sum(len(hotel.evidence) for hotel in hotel_stage.hotels),
                )
            ) / 2
            candidates.append(
                CandidatePlan(
                    plan_id=f"{transport.service_id}-{hotel_stage.option_id}",
                    label="unassigned",
                    transport=transport,
                    hotels=hotel_stage.hotels,
                    attractions=inputs.attractions,
                    days=hotel_stage.days,
                    routes=hotel_stage.routes,
                    total_cost_cny=round(total_cost, 2),
                    contingency_cny=round(inputs.budget_cny * 0.10, 2),
                    score=score_plan(
                        affordability=affordability,
                        door_to_door_time=max(0, time_score),
                        convenience=0.5,
                        data_confidence=confidence,
                    ),
                )
            )

        if not candidates:
            positive = [value for value in deficits if value > 0]
            return PlanningResult(
                plans=[],
                minimum_deficit_cny=min(positive) if positive else 0,
            )

        def pick_distinct(
            ordered: list[CandidatePlan],
            used_ids: set[str],
        ) -> CandidatePlan:
            for candidate in ordered:
                if candidate.plan_id not in used_ids:
                    used_ids.add(candidate.plan_id)
                    return candidate
            return ordered[0]

        used_ids: set[str] = set()
        balanced = pick_distinct(
            sorted(candidates, key=lambda item: item.score, reverse=True),
            used_ids,
        )
        economy = pick_distinct(
            sorted(candidates, key=lambda item: item.total_cost_cny),
            used_ids,
        )
        time_saving = pick_distinct(
            sorted(candidates, key=lambda item: item.transport.duration_minutes),
            used_ids,
        )
        selected: list[CandidatePlan] = []
        for label, candidate in (
            ("balanced", balanced),
            ("economy", economy),
            ("time-saving", time_saving),
        ):
            item = candidate.model_copy(
                update={"label": label, "plan_id": f"{label}-{candidate.plan_id}"}
            )
            selected.append(item)
        return PlanningResult(plans=selected)
```

- [ ] **Step 4: Run planning-engine tests**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_planning_engine.py -v
```

Expected: hard-budget, labels, and distinct-choice tests pass.

- [ ] **Step 5: Commit the planning engine**

Run:

```bash
git add \
  trip-schedule/scripts/planning/engine.py \
  trip-schedule/tests/test_planning_engine.py
git commit -m "Add trip alternative planner" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 11: Add redacted bounded Skill memory

**Files:**
- Create: `trip-schedule/scripts/memory_store.py`
- Create: `trip-schedule/tests/test_memory_store.py`

- [ ] **Step 1: Write failing redaction and bounded-growth tests**

Create `trip-schedule/tests/test_memory_store.py`:

```python
import json

import pytest

from memory_store import StrategyMemory


def test_memory_api_rejects_trip_specific_fields(tmp_path) -> None:
    path = tmp_path / "strategy.json"
    memory = StrategyMemory(path)

    with pytest.raises(TypeError):
        memory.record_run(
            region="杭州",
            query_keywords=["杭州 景点"],
            provider_events=[("attractions-xhs", "ok")],
            routing_notes=["West Lake attractions cluster well."],
            budget_cny=5000,
        )


def test_memory_caps_region_entries(tmp_path) -> None:
    path = tmp_path / "strategy.json"
    memory = StrategyMemory(path, max_regions=2)
    for region in ("杭州", "苏州", "南京"):
        memory.record_run(
            region=region,
            query_keywords=[f"{region} 景点"],
            provider_events=[],
            routing_notes=[],
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert list(payload["regions"]) == ["苏州", "南京"]
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_memory_store.py -v
```

Expected: import failure for `memory_store`.

- [ ] **Step 3: Implement atomic memory updates**

Create `trip-schedule/scripts/memory_store.py`:

```python
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


class StrategyMemory:
    def __init__(self, path: Path, *, max_regions: int = 100) -> None:
        self.path = path
        self.max_regions = max_regions

    def _load(self) -> dict:
        if not self.path.exists():
            return {
                "version": 1,
                "updated_at": None,
                "regions": {},
                "providers": {},
            }
        return json.loads(self.path.read_text(encoding="utf-8"))

    def record_run(
        self,
        *,
        region: str,
        query_keywords: list[str],
        provider_events: list[tuple[str, str]],
        routing_notes: list[str],
    ) -> str:
        payload = self._load()
        now = datetime.now().astimezone().isoformat()
        regions = payload["regions"]
        regions.pop(region, None)
        regions[region] = {
            "query_keywords": list(dict.fromkeys(query_keywords))[:20],
            "routing_notes": list(dict.fromkeys(routing_notes))[:20],
            "updated_at": now,
        }
        while len(regions) > self.max_regions:
            regions.pop(next(iter(regions)))

        for provider_id, status in provider_events:
            provider = payload["providers"].setdefault(
                provider_id,
                {"success_count": 0, "failure_count": 0, "last_status": None},
            )
            key = "success_count" if status in {"ok", "partial"} else "failure_count"
            provider[key] += 1
            provider["last_status"] = status
            provider["updated_at"] = now

        payload["updated_at"] = now
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return "Updated Trip Schedule's de-identified strategy memory."
```

- [ ] **Step 4: Run memory tests and verify GREEN**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_memory_store.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Commit Skill memory**

Run:

```bash
git add \
  trip-schedule/scripts/memory_store.py \
  trip-schedule/tests/test_memory_store.py
git commit -m "Add redacted trip strategy memory" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 12: Run the research and planning milestone checks

**Files:**
- Modify: `trip-schedule/scripts/providers/registry.py`
- Modify: `trip-schedule/scripts/trip_schedule.py`
- Create: `trip-schedule/tests/test_research_health.py`

- [ ] **Step 1: Register the new providers**

Update `build_registry()` in `trip-schedule/scripts/trip_schedule.py`:

```python
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
```

Add imports for `AMapProvider`, `HotelProvider`, and `XhsEvidenceProvider`.

- [ ] **Step 2: Add a health-output test**

Create `trip-schedule/tests/test_research_health.py`:

```python
import json

from trip_schedule import main


def test_health_lists_all_first_release_providers(capsys) -> None:
    assert main(["health", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert set(payload) == {
        "train-12306",
        "flight-fli",
        "attractions-xhs",
        "hotels-external",
        "amap-webservice",
    }
```

- [ ] **Step 3: Run the complete offline suite**

Run:

```bash
conda run -n agent python -m pytest trip-schedule/tests -v
```

Expected: all foundation, transport, research, planning, and memory tests pass.

- [ ] **Step 4: Scan memory, fixtures, and source for credential-shaped values**

Run:

```bash
rg -n \
  'AMAP_(WEBSERVICE_KEY|JSAPI_KEY|SECURITY_KEY)\\s*=\\s*["'\"'][^$]' \
  trip-schedule
```

Expected: no matches containing real values. Placeholder variable names are
allowed.

- [ ] **Step 5: Commit milestone integration**

Run:

```bash
git add \
  trip-schedule/scripts/trip_schedule.py \
  trip-schedule/tests/test_research_health.py
git commit -m "Integrate trip research providers" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

## Milestone Exit Criteria

- XHS and hotel wrappers use JSON argv arrays and `shell=False`.
- Missing crawlers are reported without installation.
- AMap Web Service errors never expose the configured key.
- Budget keeps a 10% contingency and reports deficits.
- Plan scoring uses the approved 40/25/15/20 weights.
- Public transit is the default; taxi recommendations include reasons.
- Three strategy labels are produced when valid candidates exist.
- Memory updates atomically, remains bounded, and excludes trip-specific data.
- All offline tests pass.
