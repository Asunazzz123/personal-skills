# Trip Schedule XHS and Hotel Wrappers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local wrapper scripts for XHS MediaCrawler evidence and AMap hotel POI candidates while preserving Trip Schedule's external command boundary.

**Architecture:** Wrapper scripts live under `trip-schedule/scripts/wrappers/` and are invoked through existing `TRIP_XHS_COMMAND_JSON` and `TRIP_HOTEL_COMMAND_JSON`. XHS wrapper delegates to a user-managed MediaCrawler checkout and normalizes its output; hotel wrapper calls AMap WebService and optionally applies local price overrides.

**Tech Stack:** Python stdlib, requests, pytest, existing Trip Schedule provider contracts.

---

## File Map

Create:

- `trip-schedule/scripts/wrappers/__init__.py`
- `trip-schedule/scripts/wrappers/xhs_mediacrawler_wrapper.py`
- `trip-schedule/scripts/wrappers/hotel_amap_wrapper.py`
- `trip-schedule/tests/test_xhs_mediacrawler_wrapper.py`
- `trip-schedule/tests/test_hotel_amap_wrapper.py`

Modify:

- `trip-schedule/README.md`

## Task 1: XHS MediaCrawler wrapper

- [ ] Write tests for missing `MEDIACRAWLER_ROOT`, output normalization from JSON/JSONL, and safe command construction.
- [ ] Run wrapper tests and verify RED.
- [ ] Implement `xhs_mediacrawler_wrapper.py` with helper functions for request parsing, keyword selection, MediaCrawler command construction, output discovery, and row normalization.
- [ ] Run wrapper tests and verify GREEN.
- [ ] Commit XHS wrapper.

## Task 2: AMap hotel wrapper

- [ ] Write tests for missing key, AMap POI normalization, and price override application.
- [ ] Run wrapper tests and verify RED.
- [ ] Implement `hotel_amap_wrapper.py` with request parsing, place-text API call, POI normalization, and optional price overrides.
- [ ] Run wrapper tests and verify GREEN.
- [ ] Commit hotel wrapper.

## Task 3: Local config docs and final validation

- [ ] Update README with real wrapper configuration examples and safety notes.
- [ ] Run focused wrapper tests.
- [ ] Run full offline suite.
- [ ] Run `git diff --check`.
- [ ] Run Skill validator.
- [ ] Commit docs/final changes.
