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
export MEDIACRAWLER_PYTHON="/absolute/path/to/MediaCrawler/.venv/bin/python"
export TRIP_XHS_BROWSER_MODE="standard"
export TRIP_XHS_LOGIN_MODE="qrcode"
export TRIP_XHS_COMMAND_JSON='["conda","run","-n","agent","python","trip-schedule/scripts/wrappers/xhs_mediacrawler_wrapper.py"]'
```

The wrapper is bounded to XHS search output and does not collect comments or
media files. If login, CAPTCHA, platform verification, or schema changes block
collection, it exits nonzero so the Skill reports the provider failure.
By default the wrapper starts MediaCrawler in visible standard Playwright mode,
which avoids MediaCrawler's default wait for an existing Chrome CDP debug port
(`9222`). If you prefer attaching to your own remote-debugging browser, set
`TRIP_XHS_BROWSER_MODE=cdp-existing`; if you want MediaCrawler to launch a CDP
browser itself, set `TRIP_XHS_BROWSER_MODE=cdp-new`.

#### Browser, login, and platform notes

The default `TRIP_XHS_BROWSER_MODE=standard` path requires Playwright's
Chromium browser dependency inside the MediaCrawler environment:

```bash
cd /absolute/path/to/MediaCrawler
.venv/bin/python -m playwright install chromium
```

On Windows, use the MediaCrawler virtual environment's Python executable, for
example:

```powershell
cd C:\path\to\MediaCrawler
.\.venv\Scripts\python.exe -m playwright install chromium
```

The first XHS run uses `TRIP_XHS_LOGIN_MODE=qrcode` by default. A visible
browser window opens; scan the QR code with the Xiaohongshu app and complete any
manual platform verification, such as CAPTCHA or slider checks. MediaCrawler
saves the browser login state under its local `browser_data/` directory when
`SAVE_LOGIN_STATE=True`, so later runs can usually reuse the session for a
while. Xiaohongshu may still require a fresh login when the session expires,
risk controls trigger, the browser profile changes, or you switch machines.

This wrapper is not macOS-only. It delegates browser control to MediaCrawler and
Playwright, so the expected compatibility is:

- macOS: tested locally with standard Playwright mode.
- Windows: expected to work with MediaCrawler's Windows support; use Windows
  paths and PowerShell/CMD environment syntax.
- Linux: expected to work when the host can run a visible Chromium/Chrome
  session. Headless servers may need extra system packages, fonts, sandbox
  support, or a display such as Xvfb.

CDP browser modes have a different dependency profile:

- `standard`: uses Playwright-managed Chromium, so install Chromium with
  `python -m playwright install chromium`.
- `cdp-existing`: connects to an already running Chrome/Edge browser with
  remote debugging enabled; this can reduce platform verification but requires
  user confirmation in Chrome and a reachable debug port.
- `cdp-new`: lets MediaCrawler detect and start Chrome/Edge through CDP. This
  depends on MediaCrawler's local browser detection for the operating system.

For local debugging, install MediaCrawler outside the Skill package, preferably
under an ignored directory:

```bash
git clone --depth 1 git@github-asunazzz123:NanmiCoder/MediaCrawler.git tmp/trip-schedule-debug/MediaCrawler
cd tmp/trip-schedule-debug/MediaCrawler
uv sync --python 3.12
.venv/bin/python -m playwright install chromium
```

Then set `MEDIACRAWLER_ROOT` to that checkout and `MEDIACRAWLER_PYTHON` to its
`.venv/bin/python`. MediaCrawler's pinned dependencies are known to be awkward
with Python 3.14, so keep them in this isolated `uv` environment instead of
installing them into the shared `agent` Conda environment. MediaCrawler also
requires Node.js and a user-visible browser/login flow; use Chrome/CDP or QR
login according to MediaCrawler's README. First runs may block until the user
accepts browser remote debugging, scans a QR code, or completes platform
verification; Trip Schedule reports that as a provider failure and never bypasses
it. Do not commit MediaCrawler's checkout, browser profile, cookies, or generated
data.

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
