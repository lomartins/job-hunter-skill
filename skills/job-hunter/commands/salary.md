---
description: Salary distribution for a role from data already in the DB.
argument-hint: "<role> [--location LOC] [--source SRC] [--since-days N]"
allowed-tools: Bash(job-hunter:*), Bash(job:*), Bash(uv run job-hunter:*)
---

Aggregate the salary distribution for $ARGUMENTS from postings already in the database.

Run `job-hunter salary --role <role-and-flags-from-args>` and present the per-currency table (count, p25, median, p75, suggested expectation).

If no data: suggest running `job-hunter discover --source indeed` (or `remoteok`, `job_na_gringa`, `glassdoor`) first to gather samples, then re-run.

When recommending a salary expectation to use on application forms, pick the **p75 + 10–20% padding** value in the user's target currency. Explain that this number comes from postings YOU'VE seen (not Glassdoor's broader market data) and therefore reflects the segment you're actually applying to.
