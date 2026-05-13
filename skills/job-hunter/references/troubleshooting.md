# Troubleshooting

Read when something is broken. Organized by symptom.

## Install

### `uv tool install` fails with "no Python 3.12"
Run `uv python install 3.12`, then retry.

### `playwright install chromium` fails
Wayland/Hyprland: install `xdg-utils` and `libnss3` via your package manager. On Arch:
```
sudo pacman -S nss xdg-utils libxkbcommon
```
If still failing, set `BROWSER_WS_ENDPOINT` to a Browserless container instead — see Apply / Browserless below.

### Plugin marketplace can't find the skill
Confirm `.claude-plugin/marketplace.json` exists at the **root** of the repo (not under `skills/`). Check `gh repo view lomartins/job-hunter-skill` resolves.

## XDG paths and perms

### `job doctor` reports "secrets file world-readable"
```
chmod 600 ~/.config/job-hunter/secrets/personal.env
```
Re-run `job doctor`.

### `tracking.md` writes to the wrong dir
Check `$XDG_DATA_HOME` — if unset, default is `~/.local/share`. The skill prints the resolved path on every `job sync`. If you want to redirect, set the env var in your shell rc.

## LinkedIn

### Discover returns 0 jobs unexpectedly
1. Cookie expired. Open Firefox/Chrome -> linkedin.com -> devtools -> Application -> Cookies -> `li_at`. Copy value into `personal.env` as `LINKEDIN_LI_AT=<value>` (the model never sees it). Run `job discover --source linkedin` again.
2. LinkedIn flagged the session. Visit linkedin.com in a real browser, solve any captchas, then refresh the cookie.
3. Rate limit was hit. `job-hunter` enforces 12-25s jitter; if you bypassed via a fork, restore that.

### "Too many redirects" on LinkedIn
Cookie is malformed. The `li_at` value should NOT include `li_at=` prefix or quoting — just the alphanumeric token.

## Adapter mismatches

### `apply` reports `aborted_for_review` immediately
A new ATS or a layout change. `learn.py` drafted `adapters_inbox/<sig>.yaml`. Edit it, then:
```
job adapter test <sig> --url <one-job-url>
job adapter promote <sig>
```

### Adapter fills fields but submit button fails
1. The submit selector drifted. Inspect in browser devtools, update the adapter's `submit.selector`.
2. There's a captcha. We don't auto-solve. Use shadow mode and click through manually.
3. A required field was missed. Check `runs/<latest>/report.json` — `fields_filled` < `fields_total`. Add the missing field to the adapter.

## Apply / Playwright / Browserless

### Browser launches but pages are blank in headed mode
Wayland-specific: try `WAYLAND_DISPLAY=` (unset) before running, to force Xwayland. Or set `BROWSER_WS_ENDPOINT=ws://localhost:3000` after starting a Browserless container:
```
docker run -p 3000:3000 ghcr.io/browserless/chromium
```

### `apply` hangs in `claude -p`
Shadow mode needs a TTY for the y/N/edit prompt. Headless invocations auto-abort with `aborted_for_review`. Either:
- Run `job apply <id>` from an interactive shell, or
- Use `--mode auto` after pre-approving via shadow at least once.

## Markdown sync

### Diff churn between regenerations
The determinism test should have caught this. Re-run:
```
uv run pytest skills/job-hunter/scripts/job_hunter/tests/test_tracking_md_determinism.py -v
```
Bug — open an issue. Workaround: pin `JOB_HUNTER_FREEZE_NOW=2026-05-13T00:00:00-03:00` to force a stable timestamp.

## CI

### Version-bump check fails
You changed something under `skills/job-hunter/**` but didn't bump the version in `.claude-plugin/marketplace.json`. Bump the patch. Update SKILL.md frontmatter `version` to match. Update CHANGELOG.

### Secret-leak lint fails on a test fixture
Add `# job-hunter:allow-pii` at the end of the offending line, or move the fixture out of scanned paths.

## Where to file issues

`gh issue create -R lomartins/job-hunter-skill -t "..." -b "...$(cat runs/<latest>/report.json)..."`
Attach `runs/<iso>/report.json` whenever possible. Never paste `personal.env`.
