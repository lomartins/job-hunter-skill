# Firecrawl integration

Opt-in scraping backend for **Indeed** and **Glassdoor** only. Solves the captcha + JS-rendering problem those two sources fight us on without adding new dependencies to the rest of the pipeline.

## Why

| Source | Plain HTTP success rate | With Firecrawl |
|--------|------------------------|----------------|
| Glassdoor | <10% (login wall + Cloudflare + JS) | ~70-80% |
| Indeed | ~40-60% (intermittent captcha) | ~85-95% |
| Others (RemoteOK / Gupy / Job na Gringa / LinkedIn) | Already work — **NOT routed through Firecrawl** |

## Privacy boundary

**Firecrawl is read-only.** It scrapes public job pages. It is **never** used by `apply.py` — that path touches PII (CPF, phone, address) and routing those fills through any third-party would leak them. `firecrawl_client.assert_apply_path_safe()` raises if `apply` runs with `FIRECRAWL_ENDPOINT` set; unset the env var first.

Self-hosting (recommended) keeps every URL and HTML response on your machine. Hosted SaaS transits your search activity through their backend — fine for job listings, not for anything else.

## Self-host setup (~2 minutes once Docker is installed)

```bash
git clone https://github.com/firecrawl/firecrawl.git ~/src/firecrawl
cd ~/src/firecrawl
cp apps/api/.env.example apps/api/.env       # defaults are fine for self-host
docker compose up -d
```

Default endpoint: `http://localhost:3002`. Verify:

```bash
curl -s http://localhost:3002/v1/scrape \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://example.com","formats":["html"]}' | jq '.data.html[:200]'
```

If you see HTML, you're good.

## Enable in `job-hunter`

Edit `~/.config/job-hunter/secrets/personal.env`:

```
FIRECRAWL_ENDPOINT=http://localhost:3002
# FIRECRAWL_API_KEY=                  # leave empty for self-host
```

That's the opt-in signal. Indeed + Glassdoor will now route through Firecrawl. Other sources are untouched. No additional config.yaml flag.

## Disable temporarily

```bash
unset FIRECRAWL_ENDPOINT      # in your current shell only
job-hunter discover --source indeed
```

Or remove the line from `personal.env`.

## Hosted SaaS (alternative)

```
FIRECRAWL_ENDPOINT=https://api.firecrawl.dev
FIRECRAWL_API_KEY=fc-...
```

Per-scrape cost. Faster to set up; queries transit their backend. Pick self-host unless you have a strong reason.

## Failure modes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `Firecrawl unreachable at http://...` | Docker container down | `docker compose ps` from the firecrawl repo; restart |
| `Firecrawl returned 4xx: ...` | API key missing / wrong endpoint | Check `FIRECRAWL_ENDPOINT` ends with no `/v1`; we append it |
| `Firecrawl response missing html field` | Backend version mismatch | Pull latest firecrawl image; restart |
| `apply.py refuses to run with Firecrawl configured` | Defense in depth — apply touches PII | Unset `FIRECRAWL_ENDPOINT` for that terminal, or use `--dry-run` (still hard-blocks; intentional) |

## What it does NOT solve

- **LinkedIn** — they fingerprint Firecrawl's IP ranges and serve captcha anyway. LinkedIn cookie auth remains the only path. Skill keeps direct HTTP for LinkedIn even when Firecrawl is set.
- **Apply forms** — needs interactive Playwright (clicks, file uploads, multi-step). Firecrawl scrapes pages; it doesn't fill forms.
- **Rate limits** — Firecrawl bypasses anti-bot, not throttling. If you blast Glassdoor through Firecrawl at 1 req/s, you'll still be flagged.
