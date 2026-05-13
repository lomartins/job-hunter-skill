---
description: Pre-flag obvious non-fits (junior, US-only, country-locked, onsite-wrong-country).
argument-hint: "[application-id]   (omit to scan all queued)"
allowed-tools: Bash(job-hunter:*), Bash(job:*), Bash(uv run job-hunter:*)
---

Run `job-hunter validate $ARGUMENTS` and present the table of concerns.

For each flagged application explain the concern in one sentence. Recommend:
- **block** severity → withdraw via `job-hunter stage <id> --to withdrawn`
- **warn** severity → user confirms whether they're willing to relocate / handle the friction
- empty result → applications look fine for the user's profile

If many applications are flagged, sort by severity (blocks first) and limit
the output to the top 10. If `description` is empty on most jobs, suggest the
user re-discover the source to fetch JD details (LinkedIn descriptions are
populated by a future enrich pass).
