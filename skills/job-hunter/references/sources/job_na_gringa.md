# Source: Job na Gringa

Curated job board (https://jobnagringa.com.br) targeted at BR devs hunting international remote roles. Lower volume than LinkedIn but very high signal — every role is vetted for "accepts BR-based remote".

## Endpoint

- Listing: `https://jobnagringa.com.br/jobs?role=mobile&seniority=senior` (HTML)
- Filtering: URL query params support `role`, `seniority`, `salary_min_usd`, `posted_within`
- Detail pages link out to the company's ATS directly (Greenhouse, Lever, Workday, Ashby...)

## Parser

`selectolax` on the listing:
- Card: `article.job-card`
- Title: `.job-card__title`
- Company: `.job-card__company`
- Salary range: `.job-card__salary` (optional, USD)
- External link: `.job-card__apply-link[href]`

## Linkthrough

Job na Gringa is a discovery surface. The actual application form is on the company's ATS, so:
1. We record the JNG listing as the canonical `Job` row (source="job_na_gringa", url=jng_url).
2. `apply` follows the external link; `learn.py` detects the ATS signature.
3. The matched adapter (Greenhouse/Lever/etc.) handles the fill.

## Rate limit

Polite: 1 request per 1-3s. The site is small; don't be obnoxious.

## Phase 1 scope

Stub. Implementation in **Phase 3**.
