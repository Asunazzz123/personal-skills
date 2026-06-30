# Provider Policy

Providers are read-only. Run health checks before queries. Never install a
missing dependency automatically. Stop on CAPTCHA, login challenge, or platform
verification and report `challenge_required`. Bound retries and request rates.
Do not log credentials, cookies, tokens, authorization headers, or signed URLs.

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
