# Changelog

All notable changes to the `job-hunter` plugin follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and adhere to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The plugin's version is the source of truth and is mirrored in `.claude-plugin/marketplace.json` and `skills/job-hunter/SKILL.md` frontmatter. CI fails any PR that modifies `skills/job-hunter/**` without bumping it.

## [Unreleased]

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
