# Trip Schedule XHS and Hotel Wrapper Design

## Goal

Replace the current fixture-only XHS and hotel debug wrappers with real, local,
read-only data-source wrappers while keeping Trip Schedule's provider boundary
unchanged:

- `TRIP_XHS_COMMAND_JSON` invokes an external command that receives
  `--request-json` and prints a JSON array of XHS evidence rows.
- `TRIP_HOTEL_COMMAND_JSON` invokes an external command that receives
  `--request-json` and prints a JSON array of hotel candidate rows.

The wrappers must support local debugging, avoid committing credentials, and
stop rather than bypass CAPTCHA, login, rate-limit, or platform verification.

## Current context

The core Skill already has a safe external-command boundary:

- `CommandRunner` never invokes a shell.
- Provider stderr is redacted before surfacing wrapper failures.
- XHS rows are normalized from `note_url`, `title`, `desc`, counts, and keyword.
- Hotel rows are normalized from name, coordinates, address, total-stay price,
  rating/review fields, source, and source URL.

Local debug currently uses fixture wrappers under ignored `tmp/`.

## Recommended architecture

### XHS: MediaCrawler wrapper

Use `NanmiCoder/MediaCrawler` as the default real XHS integration target because
it is active, popular, and explicitly supports Xiaohongshu search/note crawling.

Do not vendor MediaCrawler into this Skill. The wrapper reads:

- `MEDIACRAWLER_ROOT`: absolute path to a locally cloned MediaCrawler checkout.
- Optional `TRIP_XHS_LOGIN_MODE`: MediaCrawler login mode, defaulting to a
  user-visible mode such as QR/manual login.
- Optional `TRIP_XHS_OUTPUT_DIR`: ignored local output directory.

The wrapper:

1. Parses `--request-json`.
2. Builds bounded keywords from the request, such as `<destination> 景点` and
   `<destination> 旅游攻略`.
3. Runs MediaCrawler in search mode with a small limit.
4. Reads MediaCrawler's configured JSON/JSONL output.
5. Prints only normalized JSON rows to stdout:
   `title`, `desc`, `note_url`, `source_keyword`, `liked_count`,
   `collected_count`, `comment_count`.

If MediaCrawler is missing, login is required, CAPTCHA appears, or the output
schema cannot be read, the wrapper exits nonzero and writes a short diagnostic
to stderr. It must not print cookies, tokens, local profile paths, or request
signatures.

### Hotel: AMap hotel POI wrapper first

No stable, public, personal-use hotel price API for major domestic OTA
platforms was found during research. Open-source Ctrip/Qunar/Dianping hotel
crawlers found through GitHub search were old, sparse, or not suitable as a
default dependency.

Use AMap WebService as the first real hotel source because the Skill already
uses AMap, the API is configured locally, and it can provide stable hotel POI
names, addresses, coordinates, and source evidence.

The wrapper reads:

- `AMAP_WEBSERVICE_KEY`
- Optional `TRIP_HOTEL_PRICE_OVERRIDES`: path to an ignored JSON file for manual
  total-stay prices by hotel name.
- Optional `TRIP_HOTEL_LIMIT`: result cap, default 10.

The wrapper:

1. Parses `--request-json`.
2. Calls AMap place text search with hotel-oriented keywords in the destination
   city.
3. Normalizes POIs into Trip Schedule hotel rows:
   `name`, `latitude`, `longitude`, `address`, `total_price_cny`,
   `rating`, `review_count`, `transit_notes`, `source`, `source_url`.
4. Leaves `total_price_cny` as `null` unless a local override supplies a
   value. Unknown prices must not be invented.

### Optional OTA crawler extension

If a specific OTA crawler is later approved, add it behind the same
`TRIP_HOTEL_COMMAND_JSON` boundary rather than changing the Skill provider. The
OTA wrapper may merge prices into the AMap POI candidates by name/address, but
it must still stop on CAPTCHA, login challenge, or rate limiting.

## Configuration

Local debug config remains ignored under `tmp/`:

```bash
export TRIP_XHS_COMMAND_JSON='["conda","run","-n","agent","python","trip-schedule/scripts/wrappers/xhs_mediacrawler_wrapper.py"]'
export TRIP_HOTEL_COMMAND_JSON='["conda","run","-n","agent","python","trip-schedule/scripts/wrappers/hotel_amap_wrapper.py"]'
export MEDIACRAWLER_ROOT="/absolute/path/to/MediaCrawler"
export TRIP_HOTEL_PRICE_OVERRIDES="/absolute/path/to/hotel_prices.json"
```

AMap keys stay in local env files only and are never committed.

## Error handling and safety

- Never install MediaCrawler automatically.
- Never run shell strings; use JSON argv arrays only.
- Do not bypass login, CAPTCHA, challenge, or rate-limit controls.
- Bound result counts and request timeouts.
- Print machine-readable JSON arrays only to stdout.
- Print short diagnostics only to stderr.
- Do not persist or log credentials, cookies, tokens, authorization headers, or
  signed URLs.

## Testing

Add tests for:

- XHS wrapper command construction and normalization using a fake MediaCrawler
  output directory.
- XHS wrapper nonzero exit when `MEDIACRAWLER_ROOT` is missing.
- Hotel AMap wrapper normalization from mocked AMap responses.
- Hotel price override application without inventing unknown prices.
- Secret scan remains clean.
- Existing provider tests continue passing.

## Acceptance criteria

- Health can be configured to report XHS and hotel wrappers as available.
- Hotel wrapper can return real AMap hotel POIs with coordinates.
- XHS wrapper can run against a local MediaCrawler checkout when the user has
  prepared it and completed any required interactive login.
- Missing crawler/login/challenge states fail safely and visibly.
- No committed file contains API keys, cookies, tokens, or local private data.
