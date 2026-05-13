# Source: LinkedIn

Authenticated via the `li_at` session cookie. Highest-value source; also highest-rate-limit risk.

## Recommended setup: persistent Chrome profile

LinkedIn aggressively invalidates `li_at` cookies that arrive with a fresh fingerprint each run (different User-Agent, different TLS hash, no JSESSIONID). The skill bypasses this by reusing a **persistent Chromium profile** at `$XDG_DATA_HOME/job-hunter/chrome-profiles/linkedin/` — same fingerprint, accumulated session cookies, looks like a returning real user.

One-time setup:

```bash
job-hunter linkedin-login         # opens a headed browser; you sign in once
```

After that, `job-hunter discover --source linkedin` reuses the profile. The cookie env var becomes a fallback, only consulted on the first run before the profile exists.

If LinkedIn ever logs you out (security alert, password change), re-run `job-hunter linkedin-login`.

## Cookie capture (fallback / first run)

1. Log in to linkedin.com in Firefox/Chrome.
2. Devtools -> Storage/Application -> Cookies -> `https://www.linkedin.com`.
3. Copy the `li_at` value (alphanumeric, no quoting).
4. Put it in `~/.config/job-hunter/secrets/personal.env`:
   ```
   LINKEDIN_LI_AT=AQEDA...zz
   ```
5. `chmod 600` if not already.

The model never reads this file. The scraper does `os.environ["LINKEDIN_LI_AT"]` in its own process.

## Rate limit

Hard: 1 request per `random.uniform(12, 25)` seconds. Tracked in `$XDG_STATE_HOME/job-hunter/logs/ratelimit.json` so concurrent terminals share the budget. Tenacity retries with exponential backoff on 429/503.

User-Agent rotation: 5 fixed UAs (current Chrome/Firefox on Linux+Mac), random per session.

## Endpoints

- Search: `https://www.linkedin.com/jobs/search/?keywords=<roles>&location=<loc>&f_TPR=r604800` (past week)
- Job detail: `https://www.linkedin.com/jobs/view/<job_id>`
- Description body lives in `.show-more-less-html__markup`. Sometimes in a separate XHR to `/jobs/api/jobPostings/<id>`.

## Query construction from profile.yaml

```yaml
roles: [Android Engineer, Senior Android, ...]
locations: [Brazil, Remote, LATAM, Worldwide]
```

Becomes one request per (role, location) tuple. Pagination via `&start=25`. Cap at 5 pages per tuple per discover run (configurable).

## Detection / recovery

- If 30% of requests in a discover run hit 999 or 403, abort and surface "LinkedIn likely flagged session; refresh cookie".
- If the HTML response lacks the expected DOM markers, the page may be a captcha — log to `runs/<iso>/report.json` with `reason=captcha`, abort.

## Phase 1 scope

This file documents the source. Implementation lands in **Phase 3**. Until then, `job discover --source linkedin` errors with "not yet implemented; see references/sources/linkedin.md".
