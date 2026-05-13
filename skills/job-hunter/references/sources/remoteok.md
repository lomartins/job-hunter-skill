# Source: RemoteOK

Public JSON API. Easiest source to implement; good first integration.

## Endpoint

- `https://remoteok.com/api`
- Returns a JSON array. Element 0 is metadata (legal/disclaimer); skip it.
- Each subsequent element:
  ```json
  {
    "id": "...",
    "slug": "company-role-slug",
    "company": "Company name",
    "position": "Senior Mobile Engineer",
    "tags": ["android", "kotlin", ...],
    "location": "Worldwide",
    "salary_min": 80000, "salary_max": 120000,
    "date": "2026-05-10T...",
    "url": "https://remoteok.com/remote-jobs/...",
    "description": "<html>..."
  }
  ```

## Filtering against profile.yaml

After fetch, filter:
- Tags intersect with profile roles (case-insensitive token match against "android", "kotlin", "mobile", "kmp")
- Position contains any role keyword
- Exclude if position matches any `exclude_keywords`

## Fingerprint

`external_id = id`. `fingerprint = sha256(company || position || description[:500])`.

## Rate limit

Public API, no auth. We use 1 request per 30s to be polite; full snapshot per call so we don't need pagination.

## Phase 1 scope

Stub. **Phase 3** ships the working scraper.
