# Trip Schedule Implementation Roadmap

Execute the plans in this order:

1. [Foundation and transport providers](2026-06-30-trip-schedule-foundation-providers-plan.md)
2. [Research, planning, and memory](2026-06-30-trip-schedule-research-planning-memory-plan.md)
3. [Rendering and packaging](2026-06-30-trip-schedule-rendering-packaging-plan.md)

Each plan ends in a working, testable milestone. Do not start a later plan while
the preceding milestone tests are failing.

## Design Coverage

| Approved requirement | Implementation location |
|---|---|
| Six required inputs | Rendering plan, Tasks 2, 5, and 6 |
| One-shot or interactive choice before generation | Rendering plan, Tasks 5 and 6 |
| Independent per-trip JSON artifacts | Foundation plan, Task 4; Rendering plan, Task 2 |
| Provider adapter architecture | Foundation plan, Tasks 2 and 3 |
| Existing 12306 crawler migration | Foundation plan, Task 5 |
| Free CLI/Skill/MCP discovery before flight fallback | Foundation plan, Tasks 6 and 7; final Skill workflow |
| Xiaohongshu open-source crawler integration | Research plan, Tasks 2 and 3 |
| Hotel/OTA crawler integration | Research plan, Tasks 2 and 4 |
| Sourced attraction resolution | Research plan, Tasks 5 and 6 |
| AMap geocoding and routes | Research plan, Tasks 5 and 6 |
| Hard budget and 10% contingency | Research plan, Task 7 |
| Geographic attraction clusters | Research plan, Tasks 8 and 9 |
| Public transport default and conditional taxi | Research plan, Task 8 |
| Multi-stage hotel alternatives | Research plan, Task 9 |
| Economy, balanced, and time-saving plans | Research plan, Task 10 |
| Lightweight redacted Skill memory | Research plan, Task 11 |
| Daily route GeoJSON and interactive HTML | Rendering plan, Tasks 2 and 3 |
| Security code kept server-side | Rendering plan, Task 4 |
| README dependency and AMap setup | Rendering plan, Task 6 |
| Provider error disclosure and data freshness | Foundation plan, Task 7; Rendering plan, Tasks 2 and 6 |
| Offline tests, secret scan, opt-in live smoke tests | Rendering plan, Task 7 |

## Execution Gates

- Ask before installing `requirements.txt`, a crawler, a CLI, a Skill, or an MCP
  server.
- Use `conda run -n agent ...` for development commands in this repository.
  Do not impose that environment on installed Skill users.
- Keep crawler logins and CAPTCHA handling user-mediated. Do not bypass platform
  controls.
- Do not place the AMap values shared in chat into repository files, fixtures,
  command lines, or logs.
- Run live provider tests only after the user approves the exact providers and
  credentials in use.
