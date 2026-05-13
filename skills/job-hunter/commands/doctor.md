---
description: Validate the job-hunter install (XDG dirs, perms, Playwright, gh, version).
allowed-tools: Bash(job-hunter:*), Bash(job:*), Bash(uv run job-hunter:*)
---

Run `job-hunter doctor` and report the result.

If any check fails:
- Quote the failing row(s).
- Give the exact fix from `skills/job-hunter/references/troubleshooting.md` (e.g. `chmod 600 ~/.config/job-hunter/secrets/personal.env`, `playwright install chromium`).
- Do NOT print the contents of `~/.config/job-hunter/secrets/personal.env`.
