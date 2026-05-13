# Source: Indeed

HTML scraping of `br.indeed.com` (or `*.indeed.com` for other locales). Listings work without auth; full descriptions sometimes need a session.

## Endpoint

- Listing: `https://br.indeed.com/jobs?q=<keyword>&l=<location>&fromage=7`
- Detail: `https://br.indeed.com/viewjob?jk=<external_id>`
- `external_id` is the `data-jk` attribute on each card.

## Selectors

| Field | Selector |
|-------|---------|
| Card | `div[data-jk]` (preferred) or `td.resultContent` or `a.tapItem` |
| Title | `h2.jobTitle span[title]`, `h2 a span[title]` |
| Company | `[data-testid='company-name']`, `span.companyName` |
| Location | `[data-testid='text-location']`, `div.companyLocation` |
| Salary | `[data-testid='attribute_snippet_testid']`, `.salary-snippet` |
| Description (detail page) | `#jobDescriptionText`, `[data-testid='job-description']` |

CSS-overlap dedup via `id(node)` — multiple selectors may match the same card.

## Rate limit

Default: 6-12s jittered (`indeed.com` domain in `ratelimit.json`). Polite enough that Indeed mostly leaves us alone; still expect occasional captcha.

## Captcha detection

`_looks_like_captcha()` scans the first 5KB of the response for: `captcha`, `cf-browser-verification`, `verify you are a human`, `checking your browser`. Hit any → raise `SourceError` with the recovery hint.

## Recovery from captcha

1. Open `https://br.indeed.com` in your browser, solve the challenge.
2. Wait 10-15 minutes before re-running discover.
3. Or enable Firecrawl — handles JS + anti-bot automatically. See `references/firecrawl.md`.

## Salary parsing

`_parse_salary()` handles:
- `R$ 12.000 - R$ 18.000` (BR thousands separator)
- `USD 90,000 - 130,000` (US thousands separator)
- `$95k - $135k` (k suffix)
- `120 mil` (Portuguese "mil")

Returns `(currency, salary_min, salary_max)`. Currency one of: `BRL`, `USD`, `EUR`, `GBP` or `None` if unrecognized.

## Remote detection

`_is_remote()` matches: `remote`, `remoto` (PT), `worldwide`, `anywhere`.

## Phase

Implemented in 0.9.0.
