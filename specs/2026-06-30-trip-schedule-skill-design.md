# Trip Schedule Skill Design

Date: 2026-06-30
Status: Approved design

## 1. Objective

Create a portable `trip-schedule` Skill that plans trips within mainland China.
The Skill gathers live travel data, produces budget-constrained itinerary
alternatives, plans local transportation, renders an interactive AMap itinerary,
and records only lightweight reusable strategy memory.

The first release is read-only. It queries and recommends, but it does not book
tickets, place hotel orders, submit identity information, or process payments.

## 2. Approved Scope

### 2.1 Required user input

Before any data collection, ask for:

- Origin city
- Destination
- Total budget
- Departure date and time
- Total trip duration
- Number of travelers

Immediately before formal generation, ask the user to choose:

- One-shot generation
- Interactive generation

Do not require a long preference questionnaire. Ask optional follow-up questions
only when a missing preference materially changes the available plans.

### 2.2 Geographic scope

The first release supports mainland China as the complete, tested path. Provider
interfaces must remain replaceable so overseas providers can be added later,
but overseas travel is not an acceptance requirement for this release.

### 2.3 Cost boundary

Use only free or open-source data access for the first release. Do not depend on
a paid flight or hotel API for the main path. A provider that returns synthetic
test data cannot be presented as a live fare source.

### 2.4 Excluded features

- Ticket or hotel booking
- Automatic form submission
- Payment
- CAPTCHA bypass or anti-bot evasion
- User-account or passenger-profile storage
- Overseas provider coverage
- Weather-aware replanning
- Continuous price monitoring after the requested run ends

## 3. User Experience

### 3.1 One-shot generation

1. Validate required inputs and runtime dependencies.
2. Query attraction, intercity transport, hotel, and map providers.
3. Normalize all results into a per-trip snapshot.
4. Generate three alternatives:
   - Economy
   - Balanced
   - Time-saving
5. Select the highest-scoring valid plan as the primary recommendation.
6. Return the primary plan, two alternatives, the data-quality report, and the
   interactive itinerary.

### 3.2 Interactive generation

Use the same providers and planning core, but pause at three checkpoints:

1. Confirm the intercity transport option.
2. Confirm the hotel area and any multi-stage accommodation grouping.
3. Confirm attraction selection and daily pace.

After the final confirmation, produce the JSON artifacts and interactive map.

## 4. Architecture

Use a provider-adapter pipeline:

```text
Input and mode gate
  -> provider discovery and health checks
  -> provider queries
  -> normalized per-trip JSON
  -> budget and itinerary planning
  -> local transport routing
  -> alternatives and evidence report
  -> HTML/GeoJSON rendering
  -> lightweight Skill memory update
```

External data acquisition, normalization, planning, rendering, and memory must
remain separate. A provider implementation may change without changing the
planner or output contracts.

## 5. Skill Package

```text
trip-schedule/
├── SKILL.md
├── README.md
├── requirements.txt
├── agents/
│   └── openai.yaml
├── scripts/
│   ├── trip_schedule.py
│   ├── models.py
│   ├── serve_itinerary.py
│   ├── providers/
│   │   ├── base.py
│   │   ├── train_12306.py
│   │   ├── flight.py
│   │   ├── attractions.py
│   │   ├── hotels.py
│   │   └── amap.py
│   ├── planning/
│   │   ├── budget.py
│   │   ├── itinerary.py
│   │   └── routing.py
│   └── render_html.py
├── references/
│   ├── data-contracts.md
│   └── provider-policy.md
├── assets/
│   └── itinerary-template.html
└── memory/
    └── strategy.json
```

`SKILL.md` contains only the orchestration workflow, decision gates, and resource
routing. Detailed schemas and provider rules belong in `references/`. Repeated,
fragile operations belong in `scripts/`.

The installed copy under `~/.codex/skills/trip-schedule/` owns the mutable
`memory/strategy.json`. The Git repository is the editing source and contains
only the initial empty memory template.

## 6. Per-Trip Artifacts

Create an independent output directory for every run:

```text
trip-output/<timestamp>-<destination>/
├── request.json
├── attractions.json
├── transport.json
├── hotels.json
├── routes.geojson
├── plan.json
├── provider-report.json
└── itinerary.html
```

Do not read a previous trip directory as a live data cache. Within the current
run, providers may share their newly collected snapshot.

Every externally sourced record includes:

- `source`
- `source_url`
- `queried_at`
- `freshness`
- `confidence`

Live ticket and hotel offers also include `expires_at` when the provider exposes
an expiry. Otherwise, show the query time and state that availability is not
guaranteed.

## 7. Provider Contract

Each provider exposes the equivalent of:

```python
class Provider:
    provider_id: str

    def health_check(self) -> ProviderHealth:
        ...

    def query(self, request: ProviderRequest) -> ProviderResult:
        ...
```

`ProviderResult` contains normalized records, collection timestamps, source
evidence, warnings, and a typed status. Provider-specific raw fields must not
leak into the planning layer.

Supported status values:

- `ok`
- `partial`
- `not_configured`
- `authentication_failed`
- `rate_limited`
- `challenge_required`
- `network_error`
- `schema_changed`
- `no_results`
- `stale`

## 8. Provider Strategy

### 8.1 Attractions

Use destination-appropriate mainland platforms, initially Xiaohongshu and
Dianping, through maintainable open-source crawlers or a small local adapter.

Normalize:

- Name and aliases
- Description
- Coordinates and address
- Opening hours
- Ticket price
- Suggested visit duration
- Public transport notes
- Source URL and collection time

Deduplicate by normalized name, coordinates, and address. Preserve conflicting
prices or hours as separate evidence instead of silently choosing one.

Use bounded request rates. If login, CAPTCHA, or a platform challenge is
required, stop the provider and report `challenge_required`. Do not bypass it.

### 8.2 Train

Migrate the smallest useful core from:

```text
/Users/asuna/Asuna/study&work/git/train_crawler/Train_crawler/
  backend/crawler/ticket_crawler.py
  backend/station_id_normalization/
  resource/json/station.json
```

Retain the one-shot `TicketCrawler.query()` behavior and station-name
normalization. Do not migrate the React frontend, Flask/SSE service, CSV polling
loop, or indefinite monitoring behavior.

Wrap the migrated logic in a one-shot JSON CLI and normalize its Chinese field
names into the shared transport schema.

The current crawler provides schedules, duration, seat classes, and
availability, but not confirmed prices. Keep price fields `null` until a
reliable price source is implemented. Never invent a fare to satisfy the budget
planner.

### 8.3 Flight

Use this discovery order:

1. Check whether a compatible flight CLI, Skill, or MCP tool is already
   available in the current runtime.
2. Prefer a free, open-source provider that returns live structured results.
3. Evaluate community Google Flights adapters such as `fast-flights` behind the
   common provider interface.
4. Implement a read-only crawler only when no usable provider exists.

Discovery must not install a CLI, Skill, MCP server, or Python package
automatically. Report the selected candidate and request user approval before
installing any missing component.

Any candidate must pass live mainland-China route tests before it becomes the
default. A provider requiring paid production access may be documented as an
optional future adapter, but it is not the first-release main path.

Normalize total fare, currency, operating carrier, departure and arrival
airports, departure and arrival times, duration, stop count, baggage information
when available, booking link, and query time.

### 8.4 Hotels

Use free public sources or maintainable open-source OTA crawlers. Generate hotel
candidates by geographic cluster and price tier.

Normalize:

- Property name
- Coordinates and address
- Price and price unit
- Rating and review count
- Cancellation or refund information when available
- Nearby transit
- Travel time to the selected attraction cluster
- Source and query time

For a multi-stage trip, group candidates by city or attraction cluster. Change
hotels only for a cross-city stage or when the move saves at least 60 minutes of
total planned local travel without breaking the budget.

### 8.5 AMap

Use AMap Web Service APIs for geocoding, POI normalization, and route matrices.
Use AMap JS API 2.0 to render the itinerary.

Read credentials only from:

- `AMAP_WEBSERVICE_KEY`
- `AMAP_JSAPI_KEY`
- `AMAP_SECURITY_KEY`

Do not store real credential values in Git, logs, fixtures, static HTML, or
Skill memory.

Serve `itinerary.html` through `serve_itinerary.py`. The static template contains
no secrets. The local server injects the JS key at response time and proxies
requests that require the security key, so `AMAP_SECURITY_KEY` remains
server-side. Document AMap domain and referrer restrictions in the README.

## 9. Planning Rules

### 9.1 Budget

Treat the total user budget as a hard constraint. Reserve 10% as contingency by
default. Allocate the remainder across:

- Intercity transport
- Accommodation
- Attraction tickets
- Local transport
- Required fixed costs

If no plan fits, show the smallest budget deficit and the main cost drivers.
Do not silently remove required travel segments or mark an incomplete plan as
valid.

### 9.2 Train versus flight

Compare door-to-door cost and time, not ticket face value alone. Include:

- Origin-to-station or airport transfer
- Recommended arrival buffer
- Waiting time
- Transfer time
- Destination transfer
- Known baggage or service fees

Score cost, total time, number of transfers, convenience, and data confidence.
Do not recommend a flight solely because its airborne time is shorter.

### 9.3 Hotel selection

Cluster attractions geographically, then score hotels by:

- Total stay cost
- Total planned commuting time
- Transit access
- Data confidence
- Number of hotel changes

Produce economy, balanced, and time-saving groups when enough valid candidates
exist.

### 9.4 Local transport

Use public transport as the default for routable mainland-city segments.
Recommend a taxi when at least one of these is true:

- It saves at least 25 minutes.
- Public transport is unavailable or misses the last service.
- Luggage, late-night arrival, or mobility needs make transit impractical.
- The per-person incremental taxi cost remains reasonable within the selected
  budget plan.

Use 15 km as the default normal taxi consideration limit. Longer taxi segments
require an explicit reason in the plan.

### 9.5 Plan scoring

Use normalized component scores:

```text
40% affordability
25% door-to-door time
15% convenience
20% data confidence
```

Reject any plan that violates a hard budget, date, or routing constraint before
ranking. Keep the weights in one configuration surface so later revisions do not
require provider changes.

## 10. Error Handling and Degradation

Use bounded retries with jitter for transient network and rate-limit failures.
Do not retry authentication failures, CAPTCHA challenges, or detected schema
changes as if they were transient.

Continue with a partial plan only when the missing provider does not invalidate
the selected transport, lodging, or route. Always record:

- Failed provider
- Failure category
- Retry count
- Fallback used
- Missing fields
- Conclusions affected

Stop and ask for user action when a missing credential, login challenge, or
critical provider prevents a complete result.

Never log cookies, tokens, API keys, full authentication headers, or raw
credential-bearing URLs.

## 11. Skill Memory

Update `memory/strategy.json` after every completed run, including a partial run
that produced useful provider evidence.

Store only:

- Region-level query strategies and useful keywords
- Provider success and failure counters
- Common provider failure categories
- Routing and hotel-grouping heuristics
- Update time

Do not store:

- Travel dates
- User budget
- Number of travelers
- Origin city tied to a trip
- Chosen hotel
- Ticket results
- Authentication data
- Cookies or API keys

After writing memory, disclose one localized sentence equivalent to:

> Updated Trip Schedule's de-identified strategy memory.

Cap detailed regional entries and aggregate old provider events so memory does
not grow without bound.

## 12. README Installation Requirements

The README must:

1. Explain how to copy or symlink the Skill to
   `~/.codex/skills/trip-schedule/`.
2. Require installation of dependencies from `requirements.txt` in the user's
   chosen Python environment.
3. Avoid requiring a particular Conda environment.
4. Show placeholder-only environment-variable examples for AMap.
5. Explain optional crawler setup and login limitations.
6. Explain how to run the dependency and provider health check.
7. Explain how to start the local itinerary server.

The Skill may report missing dependencies, but it must not install, upgrade, or
remove packages automatically.

## 13. Testing

### 13.1 Unit tests

- Input and JSON model validation
- Provider normalization
- Budget allocation
- Plan rejection and scoring
- Attraction clustering
- Hotel-stage grouping
- Taxi recommendation rules
- Memory redaction and bounded growth

### 13.2 Fixture-based parser tests

Store sanitized provider response fixtures and test parsers without network
access. Include schema-change and missing-field cases.

### 13.3 Train migration regression tests

For representative station pairs, verify that the migrated station
normalization and one-shot query parser preserve the original crawler's
schedule, station, duration, and seat-availability semantics.

### 13.4 Provider contract tests

Every provider must return the shared status and result schema for success,
partial success, empty results, and failures.

### 13.5 Opt-in live smoke tests

Keep live crawler and AMap tests opt-in. Use a small number of representative
mainland routes and enforce rate limits. Do not make live provider access a
default offline test requirement.

### 13.6 Artifact and secret checks

- Validate every JSON artifact.
- Validate generated GeoJSON.
- Confirm the HTML can be served locally.
- Scan repository files, fixtures, logs, and static HTML for credentials.
- Verify that runtime credentials are absent from Skill memory.
- Run the official Skill validator.

During development in this repository, project-related Python commands follow
the repository's global instruction to use `conda run -n agent ...`. This is a
development rule, not an installation requirement for Skill users.

## 14. Acceptance Criteria

The first release is complete when:

1. The Skill asks for the six required inputs and generation mode.
2. One-shot and interactive flows use the same planning core.
3. The 12306 core works through the normalized one-shot provider.
4. At least one live, free flight provider passes representative mainland route
   tests, with a documented crawler fallback.
5. Attraction and hotel providers produce sourced, timestamped JSON.
6. The planner returns valid economy, balanced, and time-saving alternatives
   when source data allows.
7. No selected plan exceeds the hard budget without an explicit deficit report.
8. Local transport segments include route mode, duration, distance, and reason.
9. The local itinerary page renders daily tracks without storing AMap security
   credentials in static files.
10. Provider failures and stale data are visible to the user.
11. Skill memory updates after a run without storing trip-specific or secret
    data.
12. The package, tests, secret scans, and official Skill validation pass.
