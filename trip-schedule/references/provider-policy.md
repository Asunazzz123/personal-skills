# Provider Policy

Providers are read-only. Run health checks before queries. Never install a
missing dependency automatically. Stop on CAPTCHA, login challenge, or platform
verification and report `challenge_required`. Bound retries and request rates.
Do not log credentials, cookies, tokens, authorization headers, or signed URLs.
