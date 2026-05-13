# Apply modes: shadow and auto

Two modes, one Playwright runner. The difference is what happens between "form filled" and "submit clicked".

## Shadow (default)

Why it exists: catch hallucinations and adapter drift before the application is irreversible. Most failure modes are visually obvious — wrong file uploaded, wrong locale of resume, salary in the wrong currency, a "Are you a citizen of X?" radio that needs your judgment.

Flow:

1. Open a headed browser (or connect to Browserless).
2. Walk every field in the adapter, fill values from the resolver. Mask PII fields' on-screen rendering before the screenshot.
3. Run `pre_submit_checks`:
   - `screenshot`: capture to `runs/<iso>/before_submit.png` (with DOM masking applied to PII inputs)
   - `assert_no_pii_in_logs`: grep the log file for the patterns from `lint_secret_leaks`
   - `assert_all_required_filled`: every adapter field marked `required: true` is non-empty on the page
   - `assert_resume_matches_locale`: if posting language is pt-BR, the resume file path should match `file.resume_pt`; if en, `file.resume_en`
4. Block on stdin with: `[<id> <company>] Form ready. Review browser window. Submit? (y/N/edit)`
5. Branches:
   - `y` -> click submit, wait for confirmation page, screenshot post-submit, record `outcome=confirmed` (or `submitted` if confirmation unclear)
   - `edit` -> open devtools, keep waiting until you re-press `y` or `N`
   - `N` / EOF -> `outcome=aborted_for_review`, browser stays open for inspection until Ctrl+C

TTY requirement: in headless invocations (`claude -p`, CI), shadow auto-aborts to `aborted_for_review` with `reason=no_tty`. Documented so Claude doesn't waste tokens trying to interact.

## Auto

Why it exists: bulk-apply to known-good ATSes (Greenhouse, Lever, Workday — once adapters mature) without typing `y` 30 times.

Five gates must all hold or auto degrades to shadow:

1. Adapter has `auto_eligible: true` (toggle manually after observing 3+ clean shadow submits)
2. `success_count / (success_count + failure_count) >= 0.9` for this adapter
3. CLI flag `--mode auto` is set (config can't enable it implicitly)
4. `--i-understand` was passed at least once this session (per-PID env var bookkeeping)
5. No required field has `source: generate.*` unless `cover_letter_approvals` has an entry for this job_id

Flow:

1. Fill fields like shadow.
2. Run `pre_submit_checks`. Any failure -> degrade to shadow, never submit.
3. Cooldown: `Submitting in 30s... Ctrl+C to abort and review.` 30s configurable per adapter via `submit.cooldown_seconds`.
4. Click submit, wait for confirmation, record artifacts.

## Artifacts

Every fill attempt — shadow or auto — writes to `$XDG_DATA_HOME/job-hunter/runs/<iso-timestamp>/`:

```
report.json          # outcome, fields_filled, fields_total, error trace if any
before_submit.png    # with PII DOM-masked
after_submit.png     # confirmation page
session.har          # browser HAR (PII redacted via Playwright's storage_state filtering)
adapter_snapshot.yaml  # exact adapter used, for repro
```

The skill never copies values from `personal.env` into any artifact. The HAR is filtered server-side by Playwright: request bodies for PII fields are replaced with `[REDACTED]`.

## Failure modes -> outcome enum

| Symptom | Outcome value |
|---------|---------------|
| Form opened, no field filled | `failed` (with stack trace in report.json) |
| All fields filled, user pressed N | `aborted_for_review` |
| All fields filled, user pressed y, confirmation page reached | `confirmed` |
| All fields filled, submit clicked, no confirmation reachable in 30s | `submitted` (manually upgrade via `job approve <fill_id>`) |
| Auto refused due to gate | `aborted_for_review` with reason in report.json |
| Adapter mismatch detected mid-fill (field missing on page) | `failed` (signature drifted; surface in `job review`) |
| User manually applied after shadow N, wants credit | `approved_post_hoc` (set via `job approve <fill_id>`) |
