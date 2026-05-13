"""Derive a 0..100 match score from a Job's validate_fit() concerns.

Base 100, minus severity-weighted penalties. Floored at 0. Stored on the
Application row so list views can sort cheaply without re-running heuristics
per request. Recomputed lazily on first list-render if missing.
"""

from __future__ import annotations

from ..models import Job
from ..validate import FitConcern, validate_fit

PENALTY = {"block": 40, "warn": 15, "note": 5}


def score_concerns(concerns: list[FitConcern]) -> int:
    deduction = 0
    for c in concerns:
        deduction += PENALTY.get(c.severity, 5)
    return max(0, min(100, 100 - deduction))


def score_job(job: Job, *, candidate_country: str = "Brazil") -> int:
    report = validate_fit(job, candidate_country=candidate_country)
    return score_concerns(report.concerns)
