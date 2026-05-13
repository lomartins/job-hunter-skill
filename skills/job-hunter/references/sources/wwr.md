# Source: We Work Remotely

RSS feed. Use `feedparser`.

## Endpoint

- `https://weworkremotely.com/categories/remote-programming-jobs.rss`
- Items have title, link, summary, pubDate.

## Parser

Title format: "<Company>: <Position>". Split on first `:`.
Description is HTML; strip via selectolax.

## Phase 1 scope

Stub. **Phase 3** (lower priority).
