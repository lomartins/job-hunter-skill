---
description: Pipeline summary + next actions.
allowed-tools: Bash(job-hunter:*), Bash(job:*), Bash(uv run job-hunter:*)
---

Give a status of the job hunt.

Run in order:
1. `job-hunter report` — pipeline stage counts.
2. `job-hunter review` — things needing human review (paused adapters, inbox drafts).
3. `job-hunter list --stage applied` — show active applications waiting on responses.

Synthesize into a short status:
- Counts per active stage.
- Anything that needs human action (review + adapters_inbox drafts).
- Suggested next steps (queue more, follow up on stale `applied` rows, promote adapter drafts).

Keep the summary terse — one or two sentences per section.
