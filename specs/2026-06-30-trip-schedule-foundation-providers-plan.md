# Trip Schedule Foundation and Transport Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the portable Skill package, shared typed contracts, isolated run workspace, migrated 12306 provider, and free flight CLI provider.

**Architecture:** Build a small Python package inside `trip-schedule/scripts/` with typed Pydantic boundary models and provider adapters. Keep the 12306 and flight implementations behind the same provider contract, emit one-shot JSON only, and never install dependencies or tools at runtime.

**Tech Stack:** Python 3.10+, Pydantic 2, Requests, `flights` 0.9.0 (`fli` CLI), Pytest, OpenAI Skill metadata

---

## File Map

Create:

```text
trip-schedule/
├── SKILL.md
├── README.md
├── requirements.txt
├── requirements-dev.txt
├── agents/openai.yaml
├── scripts/
│   ├── __init__.py
│   ├── models.py
│   ├── trip_schedule.py
│   ├── workspace.py
│   └── providers/
│       ├── __init__.py
│       ├── base.py
│       ├── registry.py
│       ├── train_12306.py
│       ├── flight.py
│       └── train_support/
│           ├── __init__.py
│           ├── station_index.py
│           ├── ticket_client.py
│           └── station.json
├── references/
│   ├── data-contracts.md
│   └── provider-policy.md
├── assets/
└── memory/
    └── strategy.json
```

Create tests:

```text
trip-schedule/tests/
├── conftest.py
├── fixtures/12306-query.json
├── test_models.py
├── test_provider_registry.py
├── test_workspace.py
├── test_train_provider.py
├── test_flight_provider.py
└── test_transport_cli.py
```

The copied `station.json` is a data resource from the user's existing
`train_crawler` repository. Do not hand-retype it.

### Task 1: Scaffold the Skill package

**Files:**
- Create: `trip-schedule/SKILL.md`
- Create: `trip-schedule/agents/openai.yaml`
- Create: `trip-schedule/scripts/`
- Create: `trip-schedule/references/`
- Create: `trip-schedule/assets/`

- [ ] **Step 1: Verify the package does not already exist**

Run:

```bash
test ! -e trip-schedule
```

Expected: exit code `0`. If the directory exists, stop and inspect it instead of
overwriting it.

- [ ] **Step 2: Initialize with the official Skill scaffold**

Run:

```bash
conda run -n agent python \
  /Users/asuna/.codex/skills/.system/skill-creator/scripts/init_skill.py \
  trip-schedule \
  --path . \
  --resources scripts,references,assets \
  --interface 'display_name=Trip Schedule' \
  --interface 'short_description=Plan sourced, budget-aware trips in China' \
  --interface 'default_prompt=Use $trip-schedule to plan a sourced, budget-aware trip in mainland China.'
```

Expected: `trip-schedule/SKILL.md` and `trip-schedule/agents/openai.yaml` are
created.

- [ ] **Step 3: Add Python package markers and the initial memory template**

Create `trip-schedule/scripts/__init__.py`:

```python
"""Trip Schedule runtime package."""
```

Create `trip-schedule/scripts/providers/__init__.py`:

```python
"""External data providers used by Trip Schedule."""
```

Create `trip-schedule/memory/strategy.json`:

```json
{
  "version": 1,
  "updated_at": null,
  "regions": {},
  "providers": {}
}
```

- [ ] **Step 4: Add pinned runtime and test dependencies**

Create `trip-schedule/requirements.txt`:

```text
flights==0.9.0
jinja2>=3.1,<4
pydantic>=2.8,<3
requests>=2.32,<3
```

Create `trip-schedule/requirements-dev.txt`:

```text
-r requirements.txt
pytest>=8.2,<9
```

The README will instruct users to install `requirements.txt` in their chosen
environment. It must not require Conda.

- [ ] **Step 5: Replace scaffold placeholders with a temporary valid Skill shell**

Replace `trip-schedule/SKILL.md` with:

```markdown
---
name: trip-schedule
description: Use when planning a sourced, budget-constrained trip in mainland China, including attractions, train or flight comparisons, hotel alternatives, local transportation, route maps, and itinerary HTML.
---

# Trip Schedule

## Status

The provider and planning workflow is implemented incrementally. Use the
bundled scripts only after their health checks pass.

## Safety

Query and recommend only. Do not book, submit identity information, pay, bypass
CAPTCHAs, or hide provider failures.
```

- [ ] **Step 6: Validate the initial scaffold**

Run:

```bash
conda run -n agent python \
  /Users/asuna/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  trip-schedule
```

Expected: the validator reports the Skill is valid.

- [ ] **Step 7: Commit the scaffold**

Run:

```bash
git add \
  trip-schedule/SKILL.md \
  trip-schedule/agents/openai.yaml \
  trip-schedule/scripts/__init__.py \
  trip-schedule/scripts/providers/__init__.py \
  trip-schedule/memory/strategy.json \
  trip-schedule/requirements.txt \
  trip-schedule/requirements-dev.txt
git commit -m "Scaffold trip schedule skill" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

Expected: one commit containing only the initial package.

### Task 2: Define typed boundary models

**Files:**
- Create: `trip-schedule/scripts/models.py`
- Create: `trip-schedule/tests/conftest.py`
- Create: `trip-schedule/tests/test_models.py`

- [ ] **Step 1: Make the scripts package importable in tests**

Create `trip-schedule/tests/conftest.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
```

- [ ] **Step 2: Write failing model validation tests**

Create `trip-schedule/tests/test_models.py`:

```python
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
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_models.py -v
```

Expected: collection fails because `models` does not exist.

- [ ] **Step 4: Implement the typed models**

Create `trip-schedule/scripts/models.py`:

```python
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    """Base model that rejects unknown fields at system boundaries."""

    model_config = ConfigDict(extra="forbid")


class GenerationMode(StrEnum):
    ONE_SHOT = "one_shot"
    INTERACTIVE = "interactive"


class ProviderStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    NOT_CONFIGURED = "not_configured"
    AUTHENTICATION_FAILED = "authentication_failed"
    RATE_LIMITED = "rate_limited"
    CHALLENGE_REQUIRED = "challenge_required"
    NETWORK_ERROR = "network_error"
    SCHEMA_CHANGED = "schema_changed"
    NO_RESULTS = "no_results"
    STALE = "stale"


class TransportMode(StrEnum):
    TRAIN = "train"
    FLIGHT = "flight"


class TripRequest(StrictModel):
    origin_city: str = Field(min_length=1)
    destination: str = Field(min_length=1)
    budget_cny: float = Field(gt=0)
    departure_at: datetime
    duration_days: int = Field(gt=0)
    travelers: int = Field(gt=0)
    generation_mode: GenerationMode

    @field_validator("departure_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("departure_at must include a timezone")
        return value


class SourceEvidence(StrictModel):
    source: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    queried_at: datetime
    expires_at: datetime | None = None
    freshness: str = "live"
    confidence: float = Field(ge=0, le=1)

    @field_validator("queried_at")
    @classmethod
    def require_query_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("queried_at must include a timezone")
        return value


class TransportOffer(StrictModel):
    provider_id: str
    mode: TransportMode
    service_id: str
    origin_name: str
    destination_name: str
    departure_at: datetime
    arrival_at: datetime
    duration_minutes: int = Field(gt=0)
    total_price_cny: float | None = Field(default=None, ge=0)
    transfers: int = Field(default=0, ge=0)
    availability: dict[str, str] = Field(default_factory=dict)
    booking_url: str | None = None
    evidence: SourceEvidence


class ProviderHealth(StrictModel):
    provider_id: str
    status: ProviderStatus
    detail: str


class ProviderResult(StrictModel):
    provider_id: str
    status: ProviderStatus
    queried_at: datetime
    records: list[dict[str, Any]]
    warnings: list[str] = Field(default_factory=list)
    error_kind: str | None = None

    @field_validator("queried_at")
    @classmethod
    def require_result_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("queried_at must include a timezone")
        return value
```

- [ ] **Step 5: Run model tests and verify GREEN**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_models.py -v
```

Expected: `3 passed`.

- [ ] **Step 6: Commit the models**

Run:

```bash
git add \
  trip-schedule/scripts/models.py \
  trip-schedule/tests/conftest.py \
  trip-schedule/tests/test_models.py
git commit -m "Add trip schedule data contracts" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 3: Add the provider base class and registry

**Files:**
- Create: `trip-schedule/scripts/providers/base.py`
- Create: `trip-schedule/scripts/providers/registry.py`
- Create: `trip-schedule/tests/test_provider_registry.py`

- [ ] **Step 1: Write failing registry tests**

Create `trip-schedule/tests/test_provider_registry.py`:

```python
from models import ProviderHealth, ProviderResult, ProviderStatus
from providers.base import Provider
from providers.registry import ProviderRegistry


class StubProvider(Provider):
    provider_id = "stub"

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider_id=self.provider_id,
            status=ProviderStatus.OK,
            detail="ready",
        )

    def query(self, request: object) -> ProviderResult:
        return ProviderResult(
            provider_id=self.provider_id,
            status=ProviderStatus.OK,
            queried_at="2026-07-01T10:00:00+08:00",
            records=[],
        )


def test_registry_rejects_duplicate_provider_ids() -> None:
    registry = ProviderRegistry()
    registry.register(StubProvider())

    try:
        registry.register(StubProvider())
    except ValueError as exc:
        assert "stub" in str(exc)
    else:
        raise AssertionError("duplicate provider id was accepted")


def test_registry_reports_health_by_provider_id() -> None:
    registry = ProviderRegistry([StubProvider()])

    assert registry.health()["stub"].status is ProviderStatus.OK
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_provider_registry.py -v
```

Expected: import failure for `providers.base`.

- [ ] **Step 3: Implement the provider interface**

Create `trip-schedule/scripts/providers/base.py`:

```python
from __future__ import annotations

from abc import ABC, abstractmethod

from models import ProviderHealth, ProviderResult


class Provider(ABC):
    """Read-only external data provider."""

    provider_id: str

    @abstractmethod
    def health_check(self) -> ProviderHealth:
        """Return readiness without mutating external state."""

    @abstractmethod
    def query(self, request: object) -> ProviderResult:
        """Return a normalized one-shot result."""
```

Create `trip-schedule/scripts/providers/registry.py`:

```python
from __future__ import annotations

from collections.abc import Iterable

from models import ProviderHealth
from providers.base import Provider


class ProviderRegistry:
    """Own providers and enforce stable unique identifiers."""

    def __init__(self, providers: Iterable[Provider] = ()) -> None:
        self._providers: dict[str, Provider] = {}
        for provider in providers:
            self.register(provider)

    def register(self, provider: Provider) -> None:
        if provider.provider_id in self._providers:
            raise ValueError(f"duplicate provider id: {provider.provider_id}")
        self._providers[provider.provider_id] = provider

    def get(self, provider_id: str) -> Provider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"provider not registered: {provider_id}") from exc

    def health(self) -> dict[str, ProviderHealth]:
        return {
            provider_id: provider.health_check()
            for provider_id, provider in self._providers.items()
        }
```

- [ ] **Step 4: Run registry tests and verify GREEN**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_provider_registry.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the registry**

Run:

```bash
git add \
  trip-schedule/scripts/providers/base.py \
  trip-schedule/scripts/providers/registry.py \
  trip-schedule/tests/test_provider_registry.py
git commit -m "Add trip provider registry" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 4: Create isolated per-trip workspaces

**Files:**
- Create: `trip-schedule/scripts/workspace.py`
- Create: `trip-schedule/tests/test_workspace.py`

- [ ] **Step 1: Write failing workspace tests**

Create `trip-schedule/tests/test_workspace.py`:

```python
import json

from models import GenerationMode, TripRequest
from workspace import TripWorkspace


def test_workspace_writes_request_without_reusing_previous_trip(tmp_path) -> None:
    request = TripRequest(
        origin_city="深圳",
        destination="广州",
        budget_cny=2000,
        departure_at="2026-07-10T08:00:00+08:00",
        duration_days=2,
        travelers=2,
        generation_mode=GenerationMode.ONE_SHOT,
    )

    first = TripWorkspace.create(tmp_path, request, timestamp="20260701T100000")
    second = TripWorkspace.create(tmp_path, request, timestamp="20260701T100001")

    assert first.root != second.root
    assert json.loads(first.request_path.read_text(encoding="utf-8"))[
        "destination"
    ] == "广州"
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_workspace.py -v
```

Expected: import failure for `workspace`.

- [ ] **Step 3: Implement deterministic workspace creation**

Create `trip-schedule/scripts/workspace.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from models import TripRequest


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value.strip())
    return slug.strip("-") or "trip"


@dataclass(frozen=True)
class TripWorkspace:
    root: Path

    @property
    def request_path(self) -> Path:
        return self.root / "request.json"

    @classmethod
    def create(
        cls,
        output_root: Path,
        request: TripRequest,
        *,
        timestamp: str | None = None,
    ) -> "TripWorkspace":
        stamp = timestamp or datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
        root = output_root / f"{stamp}-{_safe_slug(request.destination)}"
        root.mkdir(parents=True, exist_ok=False)
        workspace = cls(root=root)
        workspace.request_path.write_text(
            request.model_dump_json(indent=2),
            encoding="utf-8",
        )
        return workspace

    def write_json(self, filename: str, payload: object) -> Path:
        from pydantic import TypeAdapter

        path = self.root / filename
        data = TypeAdapter(object).dump_json(payload, indent=2)
        path.write_bytes(data)
        return path
```

- [ ] **Step 4: Run the workspace test and verify GREEN**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_workspace.py -v
```

Expected: `1 passed`.

- [ ] **Step 5: Commit the workspace**

Run:

```bash
git add \
  trip-schedule/scripts/workspace.py \
  trip-schedule/tests/test_workspace.py
git commit -m "Add isolated trip workspaces" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 5: Migrate the one-shot 12306 core

**Files:**
- Create: `trip-schedule/scripts/providers/train_support/__init__.py`
- Create: `trip-schedule/scripts/providers/train_support/station_index.py`
- Create: `trip-schedule/scripts/providers/train_support/ticket_client.py`
- Copy: `trip-schedule/scripts/providers/train_support/station.json`
- Create: `trip-schedule/scripts/providers/train_12306.py`
- Create: `trip-schedule/tests/fixtures/12306-query.json`
- Create: `trip-schedule/tests/test_train_provider.py`

- [ ] **Step 1: Copy the station resource from the existing crawler**

Run:

```bash
mkdir -p trip-schedule/scripts/providers/train_support
cp \
  '/Users/asuna/Asuna/study&work/git/train_crawler/Train_crawler/resource/json/station.json' \
  trip-schedule/scripts/providers/train_support/station.json
```

Expected: the copied JSON contains city groups and station IDs.

- [ ] **Step 2: Add a sanitized 12306 parser fixture**

Create `trip-schedule/tests/fixtures/12306-query.json` with a single sanitized
result whose pipe-separated fields include:

```json
{
  "data": {
    "map": {
      "IOQ": "深圳北",
      "IZQ": "广州南"
    },
    "result": [
      "secret|预订|240000G1000A|G100|IOQ|IZQ|IOQ|IZQ|08:00|08:35|00:35|Y|||||||||||||||||||有|3|无"
    ]
  }
}
```

The fixture contains no cookie, token, passenger, or account data.

- [ ] **Step 3: Write failing station and train-provider tests**

Create `trip-schedule/tests/test_train_provider.py`:

```python
import json
from pathlib import Path

from models import ProviderStatus, TransportOffer
from providers.train_12306 import Train12306Provider, TrainQuery
from providers.train_support.ticket_client import parse_query_response


FIXTURE = Path(__file__).parent / "fixtures" / "12306-query.json"


def test_parse_query_response_preserves_unknown_price() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    rows = parse_query_response(payload, query_date="2026-07-10")

    assert rows[0]["service_id"] == "G100"
    assert rows[0]["origin_name"] == "深圳北"
    assert rows[0]["destination_name"] == "广州南"
    assert rows[0]["total_price_cny"] is None


def test_train_provider_normalizes_one_shot_result(monkeypatch) -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    provider = Train12306Provider()
    monkeypatch.setattr(provider.client, "query", lambda **_: payload)

    result = provider.query(
        TrainQuery(
            origin_station="深圳北",
            destination_station="广州南",
            travel_date="2026-07-10",
        )
    )

    assert result.status is ProviderStatus.OK
    offer = TransportOffer.model_validate(result.records[0])
    assert offer.provider_id == "train-12306"
```

- [ ] **Step 4: Run train tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_train_provider.py -v
```

Expected: import failure for `providers.train_12306`.

- [ ] **Step 5: Implement station lookup without global mutable state**

Create `trip-schedule/scripts/providers/train_support/__init__.py`:

```python
"""Minimal 12306 support migrated from the user's train crawler."""
```

Create `trip-schedule/scripts/providers/train_support/station_index.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


class StationIndex:
    """Bidirectional station-name index loaded once per provider instance."""

    def __init__(self, path: Path) -> None:
        data = json.loads(path.read_text(encoding="utf-8"))
        pairs = [
            (station["station"], station["id"])
            for city in data
            for station in city.get("stations", [])
            if station.get("station") and station.get("id")
        ]
        self.name_to_code = dict(pairs)
        self.code_to_name = {code: name for name, code in pairs}

    def code_for(self, name: str) -> str:
        try:
            return self.name_to_code[name]
        except KeyError as exc:
            raise ValueError(f"unknown station: {name}") from exc

    def name_for(self, code: str) -> str:
        return self.code_to_name.get(code, code)
```

- [ ] **Step 6: Implement the one-shot 12306 client and parser**

Create `trip-schedule/scripts/providers/train_support/ticket_client.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from providers.train_support.station_index import StationIndex


SEAT_INDEXES = {
    "business_class": 32,
    "special_class": 25,
    "first_class": 31,
    "second_class": 30,
    "soft_sleeper": 23,
    "hard_sleeper": 28,
    "hard_seat": 29,
    "no_seat": 26,
}


def _seat_value(parts: list[str], index: int) -> str | None:
    if index >= len(parts) or parts[index] in {"", "无", "--"}:
        return None
    return parts[index]


def parse_query_response(
    payload: dict[str, Any],
    *,
    query_date: str,
) -> list[dict[str, Any]]:
    data = payload.get("data", {})
    station_map = data.get("map", {})
    rows: list[dict[str, Any]] = []
    for raw in data.get("result", []):
        parts = raw.split("|")
        if len(parts) < 33:
            continue
        departure = datetime.fromisoformat(f"{query_date}T{parts[8]}:00+08:00")
        arrival = datetime.fromisoformat(f"{query_date}T{parts[9]}:00+08:00")
        if arrival < departure:
            arrival += timedelta(days=1)
        hours, minutes = (int(value) for value in parts[10].split(":"))
        rows.append(
            {
                "service_id": parts[3],
                "origin_name": station_map.get(parts[6], parts[6]),
                "destination_name": station_map.get(parts[7], parts[7]),
                "departure_at": departure.isoformat(),
                "arrival_at": arrival.isoformat(),
                "duration_minutes": hours * 60 + minutes,
                "total_price_cny": None,
                "availability": {
                    name: value
                    for name, index in SEAT_INDEXES.items()
                    if (value := _seat_value(parts, index)) is not None
                },
            }
        )
    return rows


class TicketClient:
    """Small read-only client for one 12306 availability query."""

    def __init__(self, station_index: StationIndex) -> None:
        self.station_index = station_index
        self.session = requests.Session()
        self.session.trust_env = False
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0",
                "Referer": "https://kyfw.12306.cn/otn/leftTicket/init",
            }
        )

    def query(
        self,
        *,
        origin_station: str,
        destination_station: str,
        travel_date: str,
    ) -> dict[str, Any]:
        params = {
            "leftTicketDTO.train_date": travel_date,
            "leftTicketDTO.from_station": self.station_index.code_for(
                origin_station
            ),
            "leftTicketDTO.to_station": self.station_index.code_for(
                destination_station
            ),
            "purpose_codes": "ADULT",
        }
        query_url = "https://kyfw.12306.cn/otn/leftTicket/queryG"
        for attempt in range(2):
            response = self.session.get(query_url, params=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
            redirect_path = payload.get("c_url")
            if not redirect_path:
                return payload
            if attempt == 1:
                raise RuntimeError("12306 returned repeated c_url redirects")
            query_url = f"https://kyfw.12306.cn/otn/{redirect_path}"
        raise RuntimeError("12306 query did not return a result")
```

- [ ] **Step 7: Add overnight and bounded-redirect regression tests**

Append to `trip-schedule/tests/test_train_provider.py`:

```python
def test_parse_query_response_rolls_overnight_arrival_to_next_day() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parts = payload["data"]["result"][0].split("|")
    parts[8] = "23:50"
    parts[9] = "00:30"
    parts[10] = "00:40"
    payload["data"]["result"][0] = "|".join(parts)

    row = parse_query_response(payload, query_date="2026-07-31")[0]

    assert row["arrival_at"].startswith("2026-08-01T00:30")


def test_ticket_client_follows_at_most_one_dynamic_query_url(monkeypatch) -> None:
    responses = iter(
        [
            {"c_url": "leftTicket/queryA"},
            {"data": {"result": [], "map": {}}},
        ]
    )
    provider = Train12306Provider()

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return next(responses)

    calls = []
    monkeypatch.setattr(
        provider.client.session,
        "get",
        lambda url, **kwargs: calls.append(url) or Response(),
    )

    payload = provider.client.query(
        origin_station="深圳北",
        destination_station="广州南",
        travel_date="2026-07-10",
    )

    assert payload["data"]["result"] == []
    assert calls == [
        "https://kyfw.12306.cn/otn/leftTicket/queryG",
        "https://kyfw.12306.cn/otn/leftTicket/queryA",
    ]
```

- [ ] **Step 8: Implement the normalized train provider**

Create `trip-schedule/scripts/providers/train_12306.py`:

```python
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
```

- [ ] **Step 9: Run train tests and verify GREEN**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_train_provider.py -v
```

Expected: parser, overnight, bounded redirect, and provider normalization tests
all pass.

- [ ] **Step 10: Commit the migrated train provider**

Run:

```bash
git add \
  trip-schedule/scripts/providers/train_12306.py \
  trip-schedule/scripts/providers/train_support \
  trip-schedule/tests/fixtures/12306-query.json \
  trip-schedule/tests/test_train_provider.py
git commit -m "Add one-shot 12306 provider" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 6: Add the free `fli` flight provider

**Files:**
- Create: `trip-schedule/scripts/providers/flight.py`
- Create: `trip-schedule/tests/test_flight_provider.py`

- [ ] **Step 1: Write failing tests for discovery and normalization**

Create `trip-schedule/tests/test_flight_provider.py`:

```python
import json
from subprocess import CompletedProcess

from models import ProviderStatus, TransportOffer
from providers.flight import FlightProvider, FlightQuery


FLIGHT_JSON = {
    "flights": [
        {
            "price": 580,
            "duration": 155,
            "stops": 0,
            "airline": "Example Air",
            "flight_number": "EA100",
            "departure_airport": "SZX",
            "arrival_airport": "SHA",
            "departure_datetime": "2026-07-10T08:00:00+08:00",
            "arrival_datetime": "2026-07-10T10:35:00+08:00"
        }
    ]
}


def test_flight_health_reports_missing_cli(monkeypatch) -> None:
    monkeypatch.setattr("providers.flight.shutil.which", lambda _: None)

    health = FlightProvider().health_check()

    assert health.status is ProviderStatus.NOT_CONFIGURED


def test_flight_provider_normalizes_cli_json(monkeypatch) -> None:
    monkeypatch.setattr("providers.flight.shutil.which", lambda _: "/usr/bin/fli")
    monkeypatch.setattr(
        "providers.flight.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args=args,
            returncode=0,
            stdout=json.dumps(FLIGHT_JSON),
            stderr="",
        ),
    )

    result = FlightProvider().query(
        FlightQuery(
            origin_iata="SZX",
            destination_iata="SHA",
            departure_date="2026-07-10",
            travelers=1,
        )
    )

    offer = TransportOffer.model_validate(result.records[0])
    assert offer.total_price_cny == 580
    assert offer.provider_id == "flight-fli"
```

- [ ] **Step 2: Run flight tests and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_flight_provider.py -v
```

Expected: import failure for `providers.flight`.

- [ ] **Step 3: Implement CLI discovery and bounded execution**

Create `trip-schedule/scripts/providers/flight.py`:

```python
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
            offers = [self._normalize(row, queried_at) for row in raw_records]
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
            total_price_cny=float(row["price"]),
            transfers=int(row.get("stops", 0)),
            booking_url=row.get("booking_url"),
            evidence=SourceEvidence(
                source="Google Flights via fli",
                source_url="https://www.google.com/travel/flights",
                queried_at=queried_at,
                confidence=0.75,
            ),
        )
```

- [ ] **Step 4: Run flight tests and verify GREEN**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_flight_provider.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Add an explicit schema-drift fixture**

Add to `trip-schedule/tests/test_flight_provider.py`:

```python
def test_flight_provider_reports_schema_change(monkeypatch) -> None:
    monkeypatch.setattr("providers.flight.shutil.which", lambda _: "/usr/bin/fli")
    monkeypatch.setattr(
        "providers.flight.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(
            args=args,
            returncode=0,
            stdout='{"unexpected": true}',
            stderr="",
        ),
    )

    result = FlightProvider().query(
        FlightQuery(
            origin_iata="SZX",
            destination_iata="SHA",
            departure_date="2026-07-10",
            travelers=1,
        )
    )

    assert result.status is ProviderStatus.SCHEMA_CHANGED
```

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_flight_provider.py -v
```

Expected: `3 passed`.

- [ ] **Step 6: Commit the flight provider**

Run:

```bash
git add \
  trip-schedule/scripts/providers/flight.py \
  trip-schedule/tests/test_flight_provider.py
git commit -m "Add free flight CLI provider" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

### Task 7: Add the transport CLI and provider references

**Files:**
- Create: `trip-schedule/scripts/trip_schedule.py`
- Create: `trip-schedule/tests/test_transport_cli.py`
- Create: `trip-schedule/references/data-contracts.md`
- Create: `trip-schedule/references/provider-policy.md`

- [ ] **Step 1: Write a failing CLI test**

Create `trip-schedule/tests/test_transport_cli.py`:

```python
import json

from trip_schedule import main


def test_health_command_emits_provider_json(capsys) -> None:
    exit_code = main(["health", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert "train-12306" in payload
    assert "flight-fli" in payload
```

- [ ] **Step 2: Run the CLI test and verify RED**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_transport_cli.py -v
```

Expected: import failure for `trip_schedule`.

- [ ] **Step 3: Implement the first CLI surface**

Create `trip-schedule/scripts/trip_schedule.py`:

```python
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from providers.flight import FlightProvider
from providers.registry import ProviderRegistry
from providers.train_12306 import Train12306Provider


def build_registry() -> ProviderRegistry:
    return ProviderRegistry([Train12306Provider(), FlightProvider()])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trip-schedule")
    subparsers = parser.add_subparsers(dest="command", required=True)
    health = subparsers.add_parser("health")
    health.add_argument("--json", action="store_true", dest="as_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "health":
        payload = {
            provider_id: health.model_dump(mode="json")
            for provider_id, health in build_registry().health().items()
        }
        if args.as_json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            for provider_id, health in payload.items():
                print(f"{provider_id}: {health['status']} - {health['detail']}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the CLI test and verify GREEN**

Run:

```bash
conda run -n agent python -m pytest \
  trip-schedule/tests/test_transport_cli.py -v
```

Expected: `1 passed`.

- [ ] **Step 5: Document exact contracts and safety policy**

Create `trip-schedule/references/data-contracts.md` with:

```markdown
# Data Contracts

All timestamps are ISO 8601 values with timezone offsets. Monetary values use
numeric CNY amounts. Unknown prices are `null`; they are never inferred.

Every provider returns `provider_id`, `status`, `queried_at`, `records`,
`warnings`, and optional `error_kind`. Every external record contains source
evidence with URL, query time, freshness, and confidence.
```

Create `trip-schedule/references/provider-policy.md` with:

```markdown
# Provider Policy

Providers are read-only. Run health checks before queries. Never install a
missing dependency automatically. Stop on CAPTCHA, login challenge, or platform
verification and report `challenge_required`. Bound retries and request rates.
Do not log credentials, cookies, tokens, authorization headers, or signed URLs.
```

- [ ] **Step 6: Run the complete milestone suite**

Run:

```bash
conda run -n agent python -m pytest trip-schedule/tests -v
```

Expected: all foundation and transport tests pass.

- [ ] **Step 7: Re-run official Skill validation**

Run:

```bash
conda run -n agent python \
  /Users/asuna/.codex/skills/.system/skill-creator/scripts/quick_validate.py \
  trip-schedule
```

Expected: valid Skill.

- [ ] **Step 8: Commit the milestone**

Run:

```bash
git add \
  trip-schedule/scripts/trip_schedule.py \
  trip-schedule/tests/test_transport_cli.py \
  trip-schedule/references/data-contracts.md \
  trip-schedule/references/provider-policy.md
git commit -m "Add trip transport health CLI" \
  -m "Co-authored-by: Codex <codex@openai.com>"
```

## Milestone Exit Criteria

- The package validates as a Skill.
- Transport models reject invalid inputs and naive timestamps.
- Every run directory is independent.
- The migrated 12306 provider performs one query and never polls indefinitely.
- Unknown train prices remain `null`.
- The `fli` provider reports missing CLI state without installing anything.
- `trip_schedule.py health --json` emits provider readiness.
- All offline tests pass.
