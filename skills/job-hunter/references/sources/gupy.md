# Source: Gupy

Brazilian ATS used by most mid-to-large BR tech companies. Hostname pattern: `<company>.gupy.io`. No central index — you discover by knowing the companies.

## Target company list

Stored at `$XDG_CONFIG_HOME/job-hunter/gupy_companies.yaml`:

```yaml
companies:
  - nubank
  - stark
  - inter
  - itau
  - bradesco
  - rappi
  - ifood
  # ... add as you find them
```

`job discover --source gupy` iterates these. To add: visit any Gupy form, grab the subdomain, append.

## Endpoints

- Listing: `https://<company>.gupy.io/jobs` (HTML, server-rendered)
- Detail: `https://<company>.gupy.io/jobs/<job_id>` (HTML)
- Some companies also expose `https://api.gupy.io/api/v1/jobs?companyId=...` (JSON; check per-company)

## Parser

`selectolax` on the HTML listing:
- Job card: `[data-testid="job-card"]`
- Title: `h3` inside the card
- Location/remote: `[data-testid="job-card-location"]`
- Link: `a[href]` to detail page

## Fingerprint

`external_id` = the job's path segment (e.g. `4392838` from `/jobs/4392838`). Combined with `source="gupy"` + the company subdomain stored in `raw_payload.company_subdomain` for uniqueness.

## Rate limit

Soft: 1 request per 2-4s per host. Gupy is forgiving but we don't push it.

## Phase 1 scope

Stub. Implementation in **Phase 3**. The reference adapter for the Gupy form (separate from this source scraper) is in `references/adapters/gupy.md`.
