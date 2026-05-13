"""SQLModel definitions. Mirror the schema in migrations/001_initial.sql.

SQLAlchemy is the source-of-truth for query construction; the migration SQL
is the source-of-truth for table layout. We assert agreement in a test.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class Stage(StrEnum):
    DISCOVERED = "discovered"
    QUEUED = "queued"
    APPLYING = "applying"
    APPLIED = "applied"
    SCREENING = "screening"
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


ACTIVE_STAGES: frozenset[Stage] = frozenset(
    {
        Stage.QUEUED,
        Stage.APPLYING,
        Stage.APPLIED,
        Stage.SCREENING,
        Stage.TECHNICAL,
        Stage.BEHAVIORAL,
        Stage.OFFER,
    }
)

TERMINAL_STAGES: frozenset[Stage] = frozenset({Stage.REJECTED, Stage.WITHDRAWN})


class FillOutcome(StrEnum):
    PENDING = "pending"
    FILLED = "filled"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    ABORTED_FOR_REVIEW = "aborted_for_review"
    FAILED = "failed"
    APPROVED_POST_HOC = "approved_post_hoc"


class FillMode(StrEnum):
    SHADOW = "shadow"
    AUTO = "auto"
    DRY_RUN = "dry_run"


class Job(SQLModel, table=True):
    __tablename__ = "jobs"
    __table_args__ = ({"sqlite_autoincrement": True},)

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(index=True)
    external_id: str = Field(index=True)
    url: str = Field(unique=True)
    title: str
    company: str = Field(index=True)
    location: str | None = None
    remote: bool | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    currency: str | None = None
    posted_at: datetime | None = None
    description: str | None = None
    raw_payload: str | None = None  # JSON-encoded
    scraped_at: datetime
    fingerprint: str = Field(index=True)


class Application(SQLModel, table=True):
    __tablename__ = "applications"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", index=True)
    current_stage: str = Field(default=Stage.DISCOVERED.value, index=True)
    applied_at: datetime | None = None
    next_action: str | None = None
    next_action_due: datetime | None = None
    notes: str | None = None
    adapter_used: str | None = None
    updated_at: datetime


class StageHistory(SQLModel, table=True):
    __tablename__ = "stage_history"

    id: int | None = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="applications.id", index=True)
    from_stage: str | None = None
    to_stage: str
    transitioned_at: datetime
    note: str | None = None


class SiteAdapter(SQLModel, table=True):
    __tablename__ = "site_adapters"

    id: int | None = Field(default=None, primary_key=True)
    platform_signature: str = Field(unique=True, index=True)
    adapter_path: str
    version: int = Field(default=1)
    success_count: int = Field(default=0)
    failure_count: int = Field(default=0)
    consecutive_failures: int = Field(default=0)
    last_used_at: datetime | None = None
    auto_eligible: bool = Field(default=False)
    paused_for_review: bool = Field(default=False)


class FillAttempt(SQLModel, table=True):
    __tablename__ = "fill_attempts"

    id: int | None = Field(default=None, primary_key=True)
    application_id: int = Field(foreign_key="applications.id", index=True)
    adapter_id: int | None = Field(default=None, foreign_key="site_adapters.id")
    started_at: datetime
    finished_at: datetime | None = None
    outcome: str | None = None
    artifacts_path: str | None = None
    fields_filled: int | None = None
    fields_total: int | None = None
    mode: str


class CoverLetterApproval(SQLModel, table=True):
    """Auto-mode requires pre-approval of generated cover letters for a job."""

    __tablename__ = "cover_letter_approvals"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="jobs.id", unique=True, index=True)
    generated_text_hash: str
    approved_at: datetime
