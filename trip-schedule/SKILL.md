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

Query and recommend only. Do not book, submit identity information, do not pay,
or do not bypass security controls.

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
