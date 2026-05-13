# Markdown sync

The SQLite DB at `$XDG_DATA_HOME/job-hunter/jobs.db` is the source of truth. The skill regenerates two Markdown views from it after every state-mutating CLI call, so a human can `cat`, `vimdiff`, or symlink them into an Obsidian vault.

## Files

| Path | What |
|------|------|
| `$XDG_DATA_HOME/job-hunter/tracking.md` | Single-file index. Active pipeline table at top, then sections by stage, then weekly summary. |
| `$XDG_DATA_HOME/job-hunter/tracking/<job-slug>.md` | Per-job detail page. Full history, raw description (cached), adapter used, fill artifact paths, free-form notes block. |

## Atomic writes

Both files are written via write-temp-fsync-rename. We never partially overwrite. Concurrent `job apply` calls from different terminals serialize via a `flock` on `jobs.db`.

## Determinism

Spec requires: for the same DB state, regenerated output must be byte-identical. This is asserted by `test_tracking_md_determinism.py`.

Sources of non-determinism we control for:

1. **Timestamps**: a `_Last updated: <ts>_` line is part of the output. To keep determinism testable, the timestamp comes from an injected `time_provider()` callable. Production = `datetime.now(tz)`. Tests = a fixed value via `freezegun` or `JOB_HUNTER_FREEZE_NOW` env var.
2. **Dict iteration order**: SQL queries `ORDER BY` explicitly on stable keys. No reliance on insertion order.
3. **Floating point**: salary rendering uses formatted strings, never repr.

## Per-job notes block

Per-job files have a user-editable region that survives regenerations:

```markdown
<!-- notes:start -->
Things I'm researching:
- Their CI setup (looked like Bitrise from the JD)
- Compose Multiplatform readiness
<!-- notes:end -->
```

`tracking_md.py` reads the existing file (if present) before regenerating. It extracts the block between markers verbatim, generates the rest fresh from the DB, and splices the preserved block back in. Tests cover: markers preserved, content preserved, missing markers added, malformed markers (missing end) regenerated with the malformed content quoted in a `<!-- recovered: -->` comment.

## --no-md-sync

State-mutating CLI commands call `sync()` implicitly at the end. For batch ops (`job apply --batch`, `job discover` over many sources), pass `--no-md-sync` to skip per-call regen and run `job sync` once at the end. Saves ~50ms per call but mostly relevant on slow disks.

## Symlinking into Obsidian (or any notes vault)

The skill does NOT touch your vault. If you want the files to live there:

```bash
ln -s ~/.local/share/job-hunter/tracking.md ~/Obsidian/job-tracking/index.md
ln -s ~/.local/share/job-hunter/tracking/  ~/Obsidian/job-tracking/by-job
```

The vault gets git-tracked by you, not by the skill. Avoids accidentally committing artifacts from `runs/`.
