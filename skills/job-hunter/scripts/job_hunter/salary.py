"""Salary aggregator.

Pulls `salary_min` / `salary_max` from rows already in the DB (Indeed,
RemoteOK, Job na Gringa, Glassdoor) and returns percentile distributions
per currency. Optional `--source glassdoor` augments with Glassdoor's
salary tool (fragile; see references/sources/glassdoor.md).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlmodel import Session, select

from .models import Job


@dataclass
class SalaryBucket:
    currency: str
    samples: list[int] = field(default_factory=list)

    def add(self, low: int | None, high: int | None) -> None:
        # Use midpoint when both available; else whichever is present.
        if low is not None and high is not None:
            self.samples.append((low + high) // 2)
        elif low is not None:
            self.samples.append(low)
        elif high is not None:
            self.samples.append(high)

    @property
    def count(self) -> int:
        return len(self.samples)

    def percentile(self, p: float) -> int | None:
        if not self.samples:
            return None
        ordered = sorted(self.samples)
        n = len(ordered)
        k = max(0, min(n - 1, int(round((p / 100) * (n - 1)))))
        return ordered[k]

    @property
    def median(self) -> int | None:
        if not self.samples:
            return None
        return int(statistics.median(self.samples))


@dataclass
class SalaryReport:
    role_query: str
    location_query: str | None
    source_filter: str | None
    since: datetime | None
    buckets: dict[str, SalaryBucket] = field(default_factory=dict)

    def add(self, currency: str | None, low: int | None, high: int | None) -> None:
        if currency is None:
            currency = "UNKNOWN"
        bucket = self.buckets.setdefault(currency, SalaryBucket(currency=currency))
        bucket.add(low, high)

    def total_samples(self) -> int:
        return sum(b.count for b in self.buckets.values())


def aggregate(
    sess: Session,
    *,
    role: str,
    location: str | None = None,
    source: str | None = None,
    since_days: int | None = None,
) -> SalaryReport:
    """Build a salary distribution across rows matching role + filters.

    Role matching is case-insensitive substring against `title` AND `description`
    (so "android" hits "Senior Android" / "Mobile Android Engineer"). Filters
    AND together.
    """
    role_lower = role.lower()
    stmt = select(Job)
    if source:
        stmt = stmt.where(Job.source == source)
    if since_days:
        since = datetime.utcnow() - timedelta(days=since_days)  # noqa: DTZ003
        stmt = stmt.where(Job.scraped_at >= since)

    report = SalaryReport(
        role_query=role,
        location_query=location,
        source_filter=source,
        since=datetime.utcnow() - timedelta(days=since_days) if since_days else None,  # noqa: DTZ003
    )

    for job in sess.exec(stmt).all():
        if (
            role_lower not in (job.title or "").lower()
            and role_lower not in (job.description or "").lower()
        ):
            continue
        if location and location.lower() not in (job.location or "").lower():
            continue
        if job.salary_min is None and job.salary_max is None:
            continue
        report.add(job.currency, job.salary_min, job.salary_max)

    return report


def suggest_expectation(
    report: SalaryReport, currency: str, *, padding: float = 0.10
) -> int | None:
    """Suggest a salary expectation: p75 + padding (10%) by default."""
    bucket = report.buckets.get(currency)
    if bucket is None:
        return None
    p75 = bucket.percentile(75)
    if p75 is None:
        return None
    return int(p75 * (1 + padding))
