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
