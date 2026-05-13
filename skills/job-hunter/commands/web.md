---
description: Launch the local triage webapp (FastAPI + HTMX) for browsing and updating jobs.
argument-hint: "[--port 8765] [--no-open]"
allowed-tools: Bash(job-hunter:*), Bash(job:*), Bash(uv run job-hunter:*)
---

Run `job-hunter web $ARGUMENTS` to start the local webapp.

The app binds `127.0.0.1` by default. It exposes:

- **Joblist** — filter by stage/source/flag/search, sort by match/date/salary/company.
- **Per-job page** — open posting, mark applied, edit stage/notes, edit salary/location/remote, flag as broken / suspicious / spam / not-a-fit.
- **Tracker** — kanban-style view grouped by pipeline stage.
- **Metrics** — applications-per-day, applications-per-week, by-stage doughnut, by-source bar, totals.
- **Language toggle** — PT-BR / EN, persists in a cookie.

If the user is already running the webapp, tell them it's at `http://127.0.0.1:8765/jobs` instead of starting a second instance. If the port is busy, suggest `--port 8766`.

Never recommend `--host 0.0.0.0` without warning the user that the app has no auth.
