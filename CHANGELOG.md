# Changelog

All notable changes to the `job-hunter` plugin follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The plugin's version is the source of truth and is mirrored in `.claude-plugin/marketplace.json` and `skills/job-hunter/SKILL.md` frontmatter. CI fails any PR that modifies `skills/job-hunter/**` without bumping it.

## [Unreleased]

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
