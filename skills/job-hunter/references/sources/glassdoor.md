# Source: Glassdoor

Hostile-to-scraping. Cloudflare + JS rendering + login wall + per-region IP fingerprinting. Expect direct-HTTP success rates <10%. Use Firecrawl (see `references/firecrawl.md`) for usable Glassdoor coverage.

## Endpoint

- Job search: `https://www.glassdoor.com/Job/jobs.htm?sc.keyword=<role>&locT=C&locName=<location>`
- Salary tool: `https://www.glassdoor.com/Salaries/<location-slug>-<role-slug>-salary-SRCH_IL.0,N_KON+1,M.htm` (the index params are positional; we compute them from string lengths)

## Auth

Two cookies, both required:

```
GLASSDOOR_GD_ID=<value from `gdId` cookie>
GLASSDOOR_UAC=<value from `_uac` cookie>
```

Capture after login at glassdoor.com via devtools → Application → Cookies → `https://www.glassdoor.com`.

Cookies expire on:
- Password change
- "Sign out everywhere"
- ~30 days of inactivity

When discovery returns 0 or hits the login redirect, refresh both cookies.

## Selectors (volatile)

| Field | Selector |
|-------|---------|
| Card | `li[data-test='jobListing']`, `li.react-job-listing` |
| Title | `[data-test='job-title']` |
| Company | `[data-test='employer-name']` |
| Location | `[data-test='job-location']` |
| Salary | `[data-test='detailSalary']`, `.salaryEstimate` |
| Listing link | `a[data-test='job-link']` |

Salary-tool page:

| Field | Selector |
|-------|---------|
| p25 | `[data-test='p25-salary']`, `[data-test='salary-p25']` |
| Median | `[data-test='median-salary']`, `[data-test='base-pay-median']` |
| p75 | `[data-test='p75-salary']`, `[data-test='salary-p75']` |
| Sample size | `[data-test='sample-size']` |

Glassdoor changes selectors more often than other ATS sites — be ready to update.

## Captcha + login-wall detection

- 403 / 429 → `SourceError` with cookie-refresh hint.
- 301/302 to a URL containing `login` → `SourceError`.
- Body contains "Sign In" in first 5KB but no `salary_main_card` anywhere → login wall.
- Generic captcha hints (same set as Indeed) → `SourceError`.

## When to skip Glassdoor

If you have Firecrawl set up, leave Glassdoor on — it'll mostly work. Otherwise consider skipping it: `job-hunter discover --source remoteok` / `--source indeed` / `--source linkedin` cover most of the same listings without the auth ceremony.

## Salary aggregation

**Prefer `job-hunter salary --role X`** for distribution data. It aggregates `salary_min`/`salary_max` across all source rows in your DB — much more reliable than Glassdoor's salary tool which is JS-rendered and frequently behind their auth wall.

If you want a Glassdoor salary-tool number specifically, call `GlassdoorSource.fetch_salary_estimate()` from Python — but expect it to often return `None`.

## Phase

Implemented in 0.9.0 (HTML + cookie auth + salary-tool parsing).
