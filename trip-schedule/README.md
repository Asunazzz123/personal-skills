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

### XHS via MediaCrawler

Trip Schedule ships a wrapper for a user-managed
[MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) checkout. Clone and
configure MediaCrawler separately, complete any required user-visible login, and
then point the wrapper at that checkout:

```bash
export MEDIACRAWLER_ROOT="/absolute/path/to/MediaCrawler"
export TRIP_XHS_COMMAND_JSON='["conda","run","-n","agent","python","trip-schedule/scripts/wrappers/xhs_mediacrawler_wrapper.py"]'
```

The wrapper is bounded to XHS search output and does not collect comments or
media files. If login, CAPTCHA, platform verification, or schema changes block
collection, it exits nonzero so the Skill reports the provider failure.

### Hotels via AMap POI

Trip Schedule ships an AMap hotel POI wrapper for stable hotel names,
addresses, and coordinates:

```bash
export AMAP_WEBSERVICE_KEY="<your-web-service-key>"
export TRIP_HOTEL_COMMAND_JSON='["conda","run","-n","agent","python","trip-schedule/scripts/wrappers/hotel_amap_wrapper.py"]'
```

AMap POI does not provide reliable live room prices. To add manually verified
total-stay prices for local debugging, create an ignored JSON file such as:

```json
{
  "武陵源标志门酒店": 1288
}
```

Then set:

```bash
export TRIP_HOTEL_PRICE_OVERRIDES="/absolute/path/to/hotel_prices.json"
```

Unknown hotel prices remain `null`; the Skill never invents them.

## Verify

```bash
python scripts/trip_schedule.py health --json
```

## Open an itinerary

```bash
python scripts/trip_schedule.py serve trip-output/<trip-directory>
```
