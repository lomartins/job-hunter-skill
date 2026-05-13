# Changelog

All notable changes to the `job-hunter` plugin follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The plugin's version is the source of truth and is mirrored in `.claude-plugin/marketplace.json` and `skills/job-hunter/SKILL.md` frontmatter. CI fails any PR that modifies `skills/job-hunter/**` without bumping it.

## [Unreleased]

## [0.9.1] - 2026-05-13

### Fixed
- **LinkedIn parser** now handles the authenticated SPA layout. LinkedIn
  serves two different HTML structures by auth state:
  - Logged-out: `.base-card` under `ul.jobs-search__results-list` (old
    layout the skill was written against).
  - Logged-in (with valid `li_at`): `[data-occludable-job-id]` cards
    using `.artdeco-entity-lockup__title` / `__subtitle` / `__caption`.
    **This is what real users see.**

  Old parser returned 0 results for authenticated users because none of
  its selectors matched. Now tries authenticated layout first, falls
  back to anonymous. `external_id` comes from `data-occludable-job-id`
  (more reliable than scraping the URL).
- Diagnosed via claude-in-chrome against a real logged-in session
  showing 1,115 results.

### Added
- `tests/fixtures/linkedin_authenticated.html` for the SPA layout.
- Test `test_linkedin_parser_authenticated_layout`.
- `tools/` (one-off harvest scripts) excluded from ruff + mypy.

## [0.9.0] - 2026-05-13

### Added — sources
- **Indeed** source: HTML scrape of `br.indeed.com`. Captcha-aware
  (`SourceError` with recovery hint). BR + US currency parsing.
- **Glassdoor** source: HTML scrape + cookie auth (`GLASSDOOR_GD_ID` +
  `GLASSDOOR_UAC`). Salary-tool page parser
  (`GlassdoorSource.fetch_salary_estimate()`).
- Both wired into `REGISTRY`. `personal.env.example` adds slots for new
  cookies. References at `references/sources/indeed.md` + `glassdoor.md`.

### Added — Firecrawl integration
- Self-hosted opt-in scraping backend for **Indeed + Glassdoor only**.
- Setting `FIRECRAWL_ENDPOINT=http://localhost:3002` in `personal.env`
  routes those two sources' `_fetch` through `/v1/scrape`.
- Other sources (RemoteOK, Gupy, Job na Gringa, LinkedIn) bypass Firecrawl
  intentionally.
- `firecrawl_client.assert_apply_path_safe()` raises if `apply.py` runs
  with Firecrawl configured. PII never transits Firecrawl.
- Full setup + privacy boundary in `references/firecrawl.md`.

### Added — salary aggregator
- `job_hunter.salary.aggregate()` walks the DB, filters by role substring
  + optional location/source/recency, returns per-currency percentile
  buckets (p25 / median / p75).
- `suggest_expectation()` returns p75 + configurable padding.
- `job-hunter salary --role <r> [--location L] [--source S] [--since-days N]`
  CLI verb + `/job-hunter:salary` slash command.

### Test coverage (+22, 116 total)
- Indeed parser: 3-card fixture, BRL/USD/k-suffix salaries, captcha
  detection.
- Glassdoor listing parser (2-card) + salary-tool page parser.
- Salary aggregator: role substring match, location filter, currency
  buckets, percentile correctness, no-match, suggest_expectation.
- FirecrawlClient: `from_env`, success scrape, 4xx + non-success responses.
- Routing: Indeed/Glassdoor route through Firecrawl when env set; direct
  otherwise. Apply path hard-blocks when Firecrawl is configured.

### Fixed
- Salary parser handles BR thousands separator (`R$ 12.000`) and US
  (`12,000`) without confusing them with decimals.
- `_is_remote()` recognizes `remoto` / `worldwide` / `anywhere` in
  addition to `remote`.

## [0.8.0] - 2026-05-13

### Added
- 8 plugin slash commands wired into `skills/job-hunter/commands/`:
  `/job-hunter:discover`, `/job-hunter:list`, `/job-hunter:track`,
  `/job-hunter:apply`, `/job-hunter:status`, `/job-hunter:review`,
  `/job-hunter:sync`, `/job-hunter:doctor`. Each declares the
  `Bash(job-hunter:*) / Bash(job:*) / Bash(uv run job-hunter:*)`
  allow-list so the user isn't prompted for every CLI invocation.
- SKILL.md documents the slash-command surface so Claude knows to
  suggest them.

### Fixed
- `test_draft_adapter_with_bundled_labels` no longer leaks `_tmp_home`
  next to the bundled assets; uses a proper `tmp_path` fixture.
- `.gitignore` adds `_tmp_home/` as a belt-and-suspenders guard.

## [0.7.0] - 2026-05-13

### Polished (Phase 7: shipping cut)
- Clean-install E2E verified end-to-end against a fresh `JOB_HUNTER_HOME_OVERRIDE`
  root: `init` runs install-hook + migrations + doctor; all checks green
  (Python 3.12, uv, Playwright Chromium, XDG dirs, secrets 0600 + not
  world-readable, profile.yaml present, gh auth, package version).
- CI workflow YAML validated.
- Final tally: 90 passing tests, ruff/ruff-format/mypy clean across 39
  source files, 74-file PII lint clean, marketplace.json valid.

### Known follow-ups (post-0.7)
- Live Playwright form-fill path (currently `--dry-run` only).
- Real cooldown + Ctrl+C handling for auto mode (logic exists, browser hook
  pending).
- `--smart-fill` Skyvern/Stagehand integration (gated flag wired, backend
  not).
- Per-source scrapers 5–11 (Remotive, WWR, Himalayas, Programathor,
  Coodesh, Trampos, Arc.dev) — currently raise SourceError with a clear
  "see references/sources/<name>.md" message.
- `adapter contribute` PR push via gh.

## [0.6.0] - 2026-05-13

### Added (Phase 6: remaining CLI verbs)
- `job list [--stage] [--source] [--since]` — Rich table of applications.
- `job show <id>` — full detail + stage history for one application.
- `job queue <id>` — DISCOVERED → QUEUED transition; idempotent.
- `job stage <id> --to STAGE [--note]` — generic transition with history record.
- `job apply <id> [--mode] [--dry-run] [--i-understand]` — full plan
  resolution + Field-plan rendering; `--dry-run` walks the entire plan
  without a browser (live Playwright fill returns a clear "wired in
  Phase 6+" message to keep the command shape complete).
- `job approve <id>` — reserved for the live-fill path.
- `job review` — surfaces paused adapters + adapters_inbox drafts.
- `job report [--weekly]` — pipeline stage counts.
- `job adapter list` — bundled + user adapters, origin marker, auto-eligible.
- `job adapter promote <sig>` — validates inbox draft + moves to user dir +
  registers in `site_adapters`.
- `job adapter test <sig> --url URL` — dry-run match.
- `job adapter mark-auto-eligible <sig>` — flips the YAML flag on a user
  adapter (bundled stays conservative).
- `job adapter contribute <sig>` — gh-based PR helper (skeleton).

### Test coverage (+16, 90 total)
- list, show (found + missing), queue idempotent, stage (valid + invalid),
  adapter list (5 bundled), adapter test (match + non-match), adapter
  promote (inbox → user dir + DB row), mark-auto-eligible flips flag,
  review empty + with inbox drafts, report stage counts, apply --dry-run
  matches Gupy URL with field plan rendered + reports missing required.

## [0.5.0] - 2026-05-13

### Added (Phase 5: apply + learn logic)
- `job_hunter.apply` — pure-Python core of the form runner, testable
  without a browser:
  - `evaluate_auto_gates()` enforces the 5 conditions for auto mode.
  - `check_no_pii_in_paths()`, `check_all_required_filled()`,
    `check_resume_matches_locale()` pre-submit checks.
  - `plan_for_url()` matches adapter + builds FieldPlan from URL.
  - `is_tty_available()` policy: shadow needs a TTY, headless aborts to
    `aborted_for_review`.
  - `confirm_submit_blocking()` y/N/edit prompt; `cooldown()` countdown.
- `job_hunter.learn` — adapter learner:
  - `compute_signature()` deterministic 16-hex platform signature from
    form class list + framework hint + sorted input names + URL path
    template (digits→`:id`, UUIDs→`:uuid`).
  - `match_known_ats()` host-pattern + DOM-hint match against the 10
    known ATSes.
  - `infer_source_for_input()` label-dictionary match (BR + EN) with
    token-overlap score.
  - `draft_adapter_from_dom()` produces a YAML-serializable draft;
    unknown inputs marked `source: TODO`.
  - `save_inbox_draft()` writes to `$XDG_DATA_HOME/job-hunter/adapters_inbox/`.

The actual Playwright runner (browser navigate / fill / screenshot / HAR)
is referenced from apply.py and will be wired in Phase 6 alongside the
CLI verbs. All of the substantive logic above is unit-tested.

### Test coverage (+20, 74 total)
- Auto-gate evaluator: all-pass case + each blocker isolated.
- Pre-submit checks: required-fill ok/missing, PII scan clean/leaky,
  resume locale (pt/en/no-resume).
- `plan_for_url`: gupy match + unknown-URL no-match path.
- Signature: stable across calls, differs for different inputs.
- `match_known_ats` for all 5 bundled + miss.
- `infer_source_for_input` matches CPF via "cpf"/"documento", email via
  Portuguese placeholder, returns None on unknown.
- `draft_adapter_from_dom` against synthetic BR-labeled form correctly
  infers CPF source via field_labels.yaml.
- `save_inbox_draft` writes YAML to adapters_inbox/.

## [0.4.0] - 2026-05-13

### Added (Phase 4: adapters + resolver)
- YAML adapter format (`platform_signature`, `match`, `fields`, `submit`)
  with strict parse + helpful errors.
- 5 bundled adapters under `skills/job-hunter/assets/adapters/`: Gupy,
  Greenhouse, Lever, Workday, Ashby. All `auto_eligible: false`.
- `field_labels.yaml`: BR + EN label dictionary for `learn.py` (Phase 5).
- `adapters.loader`: bundled + user override resolution by signature.
  `match_url()` for URL-pattern selection.
- `adapters.resolver.SecretResolver`: dispatcher for `profile.*`,
  `secret.*`, `file.*`, `generate.*`. Values fetched lazily; FieldPlan
  exposes only presence flags + selectors (no values) — model-safe.
- `adapters.generators.cover_letter`: deterministic templated default,
  receives PUBLIC context only (job_title, company, role_summary,
  public_profile_blurb). Pluggy hook reserved for user LLM override.

### Test coverage (+9 tests, 54 total)
- All 5 bundled adapters load cleanly; all `auto_eligible=False`.
- User override beats bundled by platform_signature.
- URL matching for Gupy, Greenhouse; non-match returns None.
- Invalid YAML raises AdapterError with file path.
- Resolver: profile + secret + file + generate dispatch.
- Missing secret → `has_value=False`, never a value field on PlanEntry.
- Generator function signature accepts only `ctx` dict (structural check
  that PII can't be smuggled in).
- File resolution finds `.pdf`/`.docx` variants.

## [0.3.0] - 2026-05-13

### Added (Phase 3: sources)
- `job_hunter.sources` package with Source protocol, RateLimiter
  (file-backed token bucket, concurrent-terminal safe), DiscoveryReport.
- Working scrapers for RemoteOK (JSON API), Job na Gringa (HTML), Gupy
  (per-company HTML iteration), LinkedIn (cookie auth, hard rate limit
  12-25s, 999/403/429 detection).
- Stub sources for Remotive, We Work Remotely, Himalayas, Programathor,
  Coodesh, Trampos.co, Arc.dev — raise SourceError with a helpful message.
- `job_hunter.discover` orchestrator: profile.yaml → SearchQuery → source
  → DB upsert → run report.
- `job discover --source <name>` CLI verb. Loads PII env (LINKEDIN_LI_AT)
  via python-dotenv into the child process; never logs cookie values.
- Synthetic HTML/JSON fixtures for parser tests (no real PII shipped).

### Test coverage (20 new tests)
- Per-source parsers against fixtures (3 cards each, deduped).
- Stub sources raise SourceError on discover().
- Registry contains all expected names.
- Salary parser parametrize.
- End-to-end discover with mocked _fetch: insert new, update existing,
  run dir + report.json written.
- SearchQuery role-filter + exclude-keyword logic.

## [0.2.0] - 2026-05-13

### Added (Phase 2: data layer + first CLI verbs)
- `job_hunter.paths` with XDG resolution honoring `JOB_HUNTER_HOME_OVERRIDE`.
- SQLModel definitions for `Job`, `Application`, `StageHistory`, `SiteAdapter`,
  `FillAttempt`, `CoverLetterApproval` in `job_hunter.models`.
- `job_hunter.db` with migration runner (`_migrations` table, idempotent).
- Migration `001_initial.sql` (full schema per spec).
- `job_hunter.tracking_md`: deterministic markdown generator, atomic write,
  notes-block preservation, ASCII slug.
- `install_hook.sh` real implementation (idempotent, never clobbers).
- `healthcheck.py` real checks (Python version, uv, Playwright, XDG dirs,
  secrets perms, gh auth).
- CLI verbs: `init`, `sync`, `doctor`, `lint`, `info`.

### Test coverage
- XDG path resolution across env-set / unset matrix.
- Migration idempotency + table presence + FK pragma.
- Markdown determinism (byte-identity), notes preservation.
- install_hook idempotency, no-clobber, perm hardening.
- CLI verbs smoke tests.

## [0.1.0] - 2026-05-13

### Added
- Initial repo scaffold (Phase 1 of the build plan in `skills/job-hunter/references/decisions.md`).
- `.claude-plugin/marketplace.json` describing the `job-hunter` plugin.
- `skills/job-hunter/SKILL.md` with PII-isolation forbidden-actions section, CLI surface, XDG runtime layout, and reference index.
- `pyproject.toml` (uv-managed) pinning Python 3.12 and direct dependencies.
- Apache-2.0 license, third-party notices stub, Keep-a-Changelog.
- CI workflow stubs (ruff + mypy + pytest + secret-leak lint + marketplace schema + version-bump check).

Subsequent phases will land DB models, sources 1–4, adapter system, apply/learn, and full test coverage. See `skills/job-hunter/references/decisions.md` for the phase plan.
