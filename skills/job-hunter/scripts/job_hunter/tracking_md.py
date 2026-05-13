"""Deterministic Markdown sync from the SQLite DB.

The DB is the source of truth. This module regenerates two views:
- `$XDG_DATA_HOME/job-hunter/tracking.md` (single-file index)
- `$XDG_DATA_HOME/job-hunter/tracking/<slug>.md` per application past `discovered`

Determinism contract: for the same DB state + same `now`, two consecutive
`regenerate()` calls produce byte-identical files. Test in
`tests/test_tracking_md.py` asserts this.

Atomic writes: temp file in the same dir, fsync, rename. Avoids partial reads.

Notes-block preservation: per-job files carry a user-editable region between
`<!-- notes:start -->` and `<!-- notes:end -->`. The regenerator reads any
existing file, extracts the block verbatim, and splices it back into the new
content. A malformed (start without end) block is recovered into a
`<!-- recovered: -->` comment for the human to fix.
"""

from __future__ import annotations

import io
import os
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlmodel import col, select

from .models import (
    ACTIVE_STAGES,
    Application,
    Job,
    Stage,
    StageHistory,
)
from .paths import Paths

if TYPE_CHECKING:
    from sqlmodel import Session

DEFAULT_TZ = ZoneInfo("America/Sao_Paulo")

NOTES_START = "<!-- notes:start -->"
NOTES_END = "<!-- notes:end -->"

_SLUG_BAD = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """ASCII-only kebab slug. Stable across Python versions."""
    norm = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    norm = norm.lower()
    norm = _SLUG_BAD.sub("-", norm).strip("-")
    return norm or "untitled"


@dataclass(frozen=True)
class IndexRow:
    job_id: int
    company: str
    role: str
    stage: str
    next_action: str
    due: str
    source: str


@dataclass(frozen=True)
class WeeklyStats:
    new_discoveries: int
    submissions: int
    advancements: int
    rejections: int


def regenerate(
    paths: Paths,
    sess: Session,
    *,
    now: datetime | None = None,
) -> None:
    """Write `tracking.md` and per-job files atomically. Idempotent."""
    now = now or datetime.now(DEFAULT_TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=DEFAULT_TZ)

    rows = _collect_index_rows(sess)
    stats = _collect_weekly_stats(sess, now=now)
    index_text = _render_index(rows, stats, now)
    _atomic_write(paths.tracking_index, index_text)

    paths.tracking_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        job_text = _render_job(sess, row.job_id, now)
        slug = slugify(f"{row.company}-{row.role}")
        target = paths.tracking_dir / f"{row.job_id:03d}-{slug}.md"
        existing_notes = _extract_notes(target)
        spliced = _splice_notes(job_text, existing_notes)
        _atomic_write(target, spliced)


# ─── data collection ─────────────────────────────────────────────────────────


def _collect_index_rows(sess: Session) -> list[IndexRow]:
    """All applications, ordered by application.id asc, joined to job."""
    stmt = select(Application, Job).join(Job, col(Application.job_id) == col(Job.id))
    stmt = stmt.order_by(col(Application.id).asc())
    rows: list[IndexRow] = []
    for app, job in sess.exec(stmt).all():
        rows.append(
            IndexRow(
                job_id=app.id or 0,
                company=job.company,
                role=job.title,
                stage=app.current_stage,
                next_action=app.next_action or "",
                due=app.next_action_due.date().isoformat() if app.next_action_due else "",
                source=job.source,
            )
        )
    return rows


def _collect_weekly_stats(sess: Session, *, now: datetime) -> WeeklyStats:
    since = now - timedelta(days=7)
    since_utc = since.astimezone(UTC).replace(tzinfo=None)
    new_disc = sess.exec(select(Job).where(col(Job.scraped_at) >= since_utc)).all()
    history = sess.exec(
        select(StageHistory).where(col(StageHistory.transitioned_at) >= since_utc)
    ).all()
    submissions = sum(1 for h in history if h.to_stage == Stage.APPLIED.value)
    rejections = sum(1 for h in history if h.to_stage == Stage.REJECTED.value)
    advancements = sum(1 for h in history if h.to_stage != Stage.DISCOVERED.value)
    return WeeklyStats(
        new_discoveries=len(new_disc),
        submissions=submissions,
        advancements=advancements,
        rejections=rejections,
    )


# ─── rendering ───────────────────────────────────────────────────────────────


def _render_index(rows: list[IndexRow], stats: WeeklyStats, now: datetime) -> str:
    buf = io.StringIO()
    buf.write("# Job tracking\n\n")
    buf.write(f"_Last updated: {now.isoformat(timespec='seconds')}_\n\n")

    active = [r for r in rows if r.stage in {s.value for s in ACTIVE_STAGES}]
    buf.write("## Active pipeline\n\n")
    if not active:
        buf.write("_No active applications yet. Run `job discover` then `job queue <id>`._\n\n")
    else:
        buf.write(
            "| ID  | Company | Role | Stage | Next action | Due | Source |\n"
            "|-----|---------|------|-------|-------------|-----|--------|\n"
        )
        for r in active:
            buf.write(
                f"| {r.job_id:03d} | {r.company} | {r.role} | {r.stage} | "
                f"{r.next_action} | {r.due} | {r.source} |\n"
            )
        buf.write("\n")

    buf.write("## By stage\n\n")
    for stage in Stage:
        bucket = [r for r in rows if r.stage == stage.value]
        if not bucket:
            continue
        buf.write(f"### {stage.value.capitalize()} ({len(bucket)})\n\n")
        for r in bucket:
            buf.write(f"- {r.job_id:03d} {r.company} — {r.role} ({r.source})\n")
        buf.write("\n")

    buf.write("## Weekly summary\n\n")
    buf.write(f"- New discoveries: {stats.new_discoveries}\n")
    buf.write(f"- Applications submitted: {stats.submissions}\n")
    buf.write(f"- Stage advancements: {stats.advancements}\n")
    buf.write(f"- Rejections: {stats.rejections}\n")
    return buf.getvalue()


def _render_job(sess: Session, application_id: int, now: datetime) -> str:
    app = sess.get(Application, application_id)
    if app is None:
        return ""
    job = sess.get(Job, app.job_id)
    if job is None:
        return ""

    history = sess.exec(
        select(StageHistory)
        .where(col(StageHistory.application_id) == application_id)
        .order_by(col(StageHistory.transitioned_at).asc(), col(StageHistory.id).asc())
    ).all()

    buf = io.StringIO()
    buf.write(f"# {app.id:03d} — {job.company}: {job.title}\n\n")
    buf.write(f"_Last updated: {now.isoformat(timespec='seconds')}_\n\n")
    buf.write("## Job\n\n")
    buf.write(f"- **Company**: {job.company}\n")
    buf.write(f"- **Role**: {job.title}\n")
    buf.write(f"- **Source**: {job.source}\n")
    buf.write(f"- **URL**: <{job.url}>\n")
    if job.location:
        buf.write(f"- **Location**: {job.location}\n")
    if job.salary_min or job.salary_max:
        cur = job.currency or ""
        lo = job.salary_min or ""
        hi = job.salary_max or ""
        buf.write(f"- **Salary range**: {cur} {lo} — {cur} {hi}\n")
    buf.write(f"- **Current stage**: `{app.current_stage}`\n")
    if app.next_action:
        due = app.next_action_due.date().isoformat() if app.next_action_due else ""
        buf.write(f"- **Next action**: {app.next_action} (due {due})\n")
    if app.adapter_used:
        buf.write(f"- **Adapter used**: `{app.adapter_used}`\n")
    buf.write("\n")

    buf.write("## Stage history\n\n")
    if not history:
        buf.write("_(no transitions yet — created at discovery)_\n\n")
    else:
        for h in history:
            ts = h.transitioned_at.isoformat(timespec="seconds")
            from_s = h.from_stage or "—"
            note = f" — {h.note}" if h.note else ""
            buf.write(f"- {ts}: `{from_s}` → `{h.to_stage}`{note}\n")
        buf.write("\n")

    if job.description:
        buf.write("## Description (cached)\n\n")
        buf.write(job.description.strip())
        buf.write("\n\n")

    buf.write("## Notes\n\n")
    buf.write(f"{NOTES_START}\n")
    buf.write("\n")
    buf.write(f"{NOTES_END}\n")
    return buf.getvalue()


# ─── notes block preservation ────────────────────────────────────────────────


_NOTES_RE = re.compile(
    re.escape(NOTES_START) + r"(.*?)" + re.escape(NOTES_END),
    re.DOTALL,
)


def _extract_notes(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = _NOTES_RE.search(text)
    if not m:
        # Malformed: start but no end? recover.
        if NOTES_START in text and NOTES_END not in text:
            tail = text.split(NOTES_START, 1)[1]
            recovered = "<!-- recovered: malformed notes block from previous file -->"
            return f"\n{recovered}\n{tail.strip()}\n"
        return None
    return m.group(1)


def _splice_notes(new_text: str, preserved: str | None) -> str:
    if preserved is None:
        return new_text
    return _NOTES_RE.sub(NOTES_START + preserved + NOTES_END, new_text, count=1)


# ─── atomic write ────────────────────────────────────────────────────────────


def _atomic_write(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)
        fh.flush()
        os.fsync(fh.fileno())
    tmp.replace(target)


def fixed_now_from_env() -> datetime | None:
    """Read `JOB_HUNTER_FREEZE_NOW` env var. Used by tests for determinism."""
    val = os.environ.get("JOB_HUNTER_FREEZE_NOW")
    if not val:
        return None
    dt = datetime.fromisoformat(val)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=DEFAULT_TZ)
    return dt


__all__ = [
    "DEFAULT_TZ",
    "NOTES_START",
    "NOTES_END",
    "fixed_now_from_env",
    "regenerate",
    "slugify",
]


def _unused_iter_check(_: Iterable[object]) -> None:
    """No-op; kept to silence unused-import warnings under strict configs."""
    return None
