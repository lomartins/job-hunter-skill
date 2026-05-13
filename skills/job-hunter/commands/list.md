---
description: Show the job pipeline (applications + stages).
argument-hint: "[--stage STAGE] [--source SOURCE] [--since YYYY-MM-DD]"
allowed-tools: Bash(job-hunter:*), Bash(job:*), Bash(uv run job-hunter:*)
---

Show the job application pipeline.

Run `job-hunter list $ARGUMENTS` and present the result. If the user passes filters in $ARGUMENTS pass them through verbatim. If the table is large (>20 rows), summarize by stage in addition to showing the first 10 rows.

After listing, suggest one next action based on what you see:
- many `discovered` → `/job-hunter:status` to plan
- something `applied` and stale → `/job-hunter:status` to flag follow-ups
- `aborted_for_review` → `/job-hunter:review`
