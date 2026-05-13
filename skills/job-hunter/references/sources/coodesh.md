# Source: Coodesh

BR + LATAM dev job board. Public listing; full detail requires auth.

## Endpoint

- Listing: `https://coodesh.com/vagas?stack=kotlin`
- Detail: same URL pattern; if not logged in, returns a redacted body.

## Auth

Optional. If you want full descriptions, log in via browser and capture the session cookie into `personal.env` as `COODESH_SESSION=...`. Otherwise we work from listing-only data.

## Phase 1 scope

Stub. **Phase 3** (lower priority).
