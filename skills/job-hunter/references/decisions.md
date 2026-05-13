# Decisions, plan, divergences

Living doc. Records every place we deliberately deviated from the build spec, every ambiguity we resolved with a default, and the phased plan we execute. Update on every commit that changes scope.

## Plan: phased build

Each phase ends in a runnable state with green tests. Commit per phase. Bump `marketplace.json` version per commit touching `skills/job-hunter/**` (CI enforces).

| Phase | Output | Runnable demo |
|------|--------|---------------|
| 1 | Repo scaffold, `marketplace.json`, SKILL.md (frontmatter + body skeleton), `pyproject.toml` (uv), licenses, CHANGELOG, CI workflow stubs | `uv sync` succeeds; CI runs (no tests yet, lint only) |
| 2 | XDG `paths.py`, SQLModel models, numbered migrations, `tracking_md.py` (deterministic), `install_hook.sh`, `healthcheck.py`; CLI `init`/`sync`/`doctor`/`lint` | `job-hunter init && job-hunter doctor` clean on Arch + a temp XDG override |
| 3 | Sources 1–4 (Job na Gringa, LinkedIn cookie auth, Gupy, RemoteOK). Stubs + reference docs for 5–11 | `job-hunter discover --source remoteok` populates DB, `tracking.md` updates |
| 4 | YAML adapter format, resolver, bundled adapters (Gupy, Greenhouse, Lever, Workday, Ashby), `field_labels.yaml`, secret/profile/file/generate dispatcher | `job-hunter adapter list` shows 5 entries, all `auto_eligible=false` |
| 5 | `apply.py` (shadow blocks for y/N/edit; auto with all 5 gates), `learn.py` inspection + signature, `lint_secret_leaks.py` | `job-hunter apply <id> --mode shadow --dry-run` walks form, prints diff, never submits |
| 6 | Remaining CLI: `apply` (live), `stage`, `review`, `queue`, `show`, `list`, `report`, all `adapter` subcommands, `--batch`, `--i-understand`, `--no-md-sync` | Every CLI verb in spec has an integration test |
| 7 | Full pytest suite (8 categories), CI green (ruff + mypy + pytest + lint_secret_leaks + marketplace schema + version-bump check), README polished, `template/` stub, clean-install E2E | Fresh `~/.claude` + `~/.config/job-hunter` → `/plugin install` → all CLI verbs work |

After each phase: paste `uv run pytest`, `job-hunter lint`, `job-hunter doctor` outputs in the chat before moving on.

## Resolved ambiguities (defaults chosen)

These are spec gaps where we made a call rather than ask. Override later if any is wrong.

### 1. The `claude job …` CLI prefix is convention, not a real `claude` subcommand

Claude Code's `claude` binary has no `job` subcommand and we can't add one. We ship a single console script `job-hunter` (with shorter alias `job`) via `[project.scripts]` in `pyproject.toml`. After `uv tool install` or shell PATH wiring, users type `job ...` in any terminal.

Docs/SKILL.md use `job ...` for examples. The spec's `claude job ...` is interpreted as shell-prompt shorthand, not a Claude Code subcommand.

### 2. Shadow-mode TTY requirement

Shadow mode blocks for `y/N/edit`. In a headless `claude -p` session there is no TTY, so the block would hang or eat stdin. Resolution: shadow mode detects `sys.stdin.isatty()`; if false, it auto-records the run as `aborted_for_review` (artifacts written, DB updated) and exits non-zero with a clear message. The user runs `job apply <id>` from an interactive shell to actually submit.

### 3. Markdown determinism vs timestamps

`tracking.md` carries a `_Last updated: <iso>_` line, which would break byte-identity. Resolution: timestamp source is `time_provider()` injected at the boundary. Tests freeze it to a constant; the determinism test asserts byte-identity across two regenerations under the same frozen clock. Real runs use `datetime.now(tz)`.

### 4. Fill-attempt outcome enum

Spec doesn't enumerate `fill_attempts.outcome`. We use: `pending | filled | submitted | confirmed | aborted_for_review | failed | approved_post_hoc`. `confirmed` = post-submit success page reached; `approved_post_hoc` = user ran `job approve <id>` for a shadow run they later submitted manually.

### 5. `--smart-fill` (Skyvern/Stagehand) scope

Phase-1 ships the flag and its `config.yaml` opt-in gate but no integration. Calling `--smart-fill` without `config.yaml: smart_fill.enabled: true` errors out. With the opt-in flag set, it errors with `"smart-fill backend not wired in this version; see references/decisions.md"`. This preserves the user's promise that smart-fill is opt-in and PII-aware without us shipping a half-built integration.

### 6. Generator for `generate.cover_letter`

Phase-1 ships a placeholder generator that returns a deterministic templated paragraph using only `{job_title, company, role_summary, public_profile_blurb}` from `profile.yaml`. A `pluggy` hook point lets users register a real LLM call. PII never enters the generator's arguments — enforced by the resolver, asserted in tests.

### 7. CI version-bump check

Implemented as `.github/workflows/ci.yml` step that runs a Python helper: diff `skills/job-hunter/**` between PR base and head; if non-empty, assert that `.claude-plugin/marketplace.json`'s `plugins[0].version` increased per SemVer. Local pre-commit ships the same check (optional opt-in via `assets/pre-commit-config.yaml`).

### 8. `job adapter contribute <signature>`

Wraps `git`/`gh` to produce a branch + PR in this repo with the user-edited adapter copied from `$XDG_DATA_HOME/job-hunter/adapters_user/<sig>.yaml` into `skills/job-hunter/assets/adapters/`. Best-effort: requires `gh auth status` clean; if not, prints the manual diff and the suggested `gh pr create` command and exits.

### 9. LinkedIn rate limit

Spec: 1 req per 12–25s jittered. We implement a global token-bucket per `domain` keyed in `$XDG_STATE_HOME/job-hunter/logs/ratelimit.json`, so concurrent runs across terminals share the budget. Default for `linkedin.com` is `(min=12, max=25)`. Configurable via `config.yaml`.

### 10. Browserless detection

`apply.py` checks `BROWSER_WS_ENDPOINT` env var. If set, Playwright connects via `connect_over_cdp`. Else local Chromium. `doctor` reports which is active.

### 11. Profile YAML schema and `secret.*` keyspace

`profile.yaml` keyspace is documented in `assets/profile.yaml.example`. `secret.*` keyspace is exactly what `assets/personal.env.example` defines — `secret.cpf`, `secret.rg`, `secret.phone`, `secret.address`, `secret.birth_date`, `secret.salary_expectation_brl`, `secret.bank_account`, `LINKEDIN_LI_AT` (this last is access, not identity, but lives in the same file because it's session credentials). Any adapter referencing a `secret.X` not present in the env errors at fill-plan time, never at submit time.

### 12a. Migrations live inside the python package

Spec puts `migrations/` at `scripts/migrations/` (sibling of `scripts/job_hunter/`). We moved them to `scripts/job_hunter/migrations/` so they ride along in the installed wheel (`hatchling` only packages files under `packages =`). `db.py` resolves them via `importlib.resources`. Visible in source layout via the package path; functionally equivalent to the spec.

### 12. Test DB strategy

Tests get a fresh temp dir via `tmp_path` fixture, with `JOB_HUNTER_HOME_OVERRIDE` env var pointing into it. `paths.py` honors that override before consulting `XDG_*` for tests' benefit; it's documented in SKILL.md as a test hook and in `references/decisions.md`. No prod path uses it.

### 13. `lint_secret_leaks.py` scope

Scans `$XDG_DATA_HOME/job-hunter/runs/`, `$XDG_STATE_HOME/job-hunter/logs/`, `$XDG_DATA_HOME/job-hunter/tracking.md`, and per-job markdowns. Regexes for CPF (`\d{3}\.?\d{3}\.?\d{3}-?\d{2}`), CNPJ (`\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}`), RG (varies by state; we use a generous `[A-Z]{0,3}\d{6,10}[A-Z\d]?`), phone (BR `\(?\d{2}\)?\s?9?\d{4}-?\d{4}`), and BR IBAN. Excludes `personal.env` and the example template by path so the example values don't false-positive.

### 14. Auto-mode "no required field sourced from `generate.*` unless cached pre-approved" gate

We add a `cover_letter_approvals` table (job_id, generated_text_hash, approved_at). Auto mode checks this table before allowing submit. CLI verb: `job approve --letter <id>` previews and approves; without it auto refuses.

### 15. Adapter `platform_signature` hash inputs

Lowercased form-tag class list + framework hint (presence of `data-react-helmet`, `data-ember-action`, etc.) + the sorted list of input `name` attributes + the URL path template (host preserved, integer IDs replaced with `:id`). SHA-256, truncated to 16 hex chars. Documented in `references/self_improvement.md`.

## Out of scope (phase 1)

- ATS-side OAuth (we use cookie/session capture only).
- Resume/cover-letter generation from scratch (we ship templated placeholder; user wires their LLM).
- Email/Slack notifications for stage transitions.
- Multi-profile (one user, one profile.yaml).
- Encrypted secrets at rest (we rely on filesystem permissions and the user's disk encryption). A KeePassXC integration is a likely Phase 2.

## Risks & mitigations

| Risk | Mitigation |
|------|------------|
| LinkedIn detects scraping → cookie banned | Hard rate limit, jitter, single-session, user owns the cookie. Document recovery. |
| PII leaks into a log we forgot about | `lint_secret_leaks.py` runs in CI on test fixture; also `job lint` runs it on real runtime dirs. |
| Adapter drift breaks auto-mode silently | After 3 consecutive failures we pause auto for that signature and surface in `job review`. |
| Markdown sync corrupts user notes | Per-job `<!-- notes:start --> ... <!-- notes:end -->` block is preserved verbatim across regenerations; determinism test covers it. |
| Plugin marketplace schema changes | `marketplace.json` validated in CI against a vendored schema; failing PR blocks. |

## Resolved with user (2026-05-13)

1. Console scripts: ship both `job-hunter` and short alias `job`.
2. `job adapter contribute` PRs to `lomartins/job-hunter-skill` by default, override via `$JOB_HUNTER_UPSTREAM_REPO`.
3. Bundled adapters: Apache-2.0 (same as repo).
4. `discover --watch` default interval: 6h.
