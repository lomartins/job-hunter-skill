"""Fit validation: pre-flag obvious non-matches before the user wastes time.

Heuristics over `Job.title` + `Job.location` + `Job.description` (when present).
Returns a `FitReport` listing concerns. Empty list = looks OK.

This is a triage helper, not a final gate — user always overrides. The intent
is to surface "you're a Senior Android based in Brazil, this role wants US
citizenship + on-site Mountain View" before you spend Connects or a half-hour
filling Workday forms.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import Job

# Phrases that almost always mean "you must be a US national / clearance-holder".
US_RESTRICTED_PHRASES = (
    "u.s. citizen",
    "us citizen",
    "us citizenship",
    "u.s. citizenship",
    "must be authorized to work in the u.s.",
    "must be authorized to work in the us",
    "must be a us citizen",
    "must be a u.s. citizen",
    "secret clearance",
    "top secret clearance",
    "ts/sci",
    "us residents only",
)
COUNTRY_LOCKED_PATTERNS = (
    re.compile(r"must reside in ([\w\s]{2,40})", re.IGNORECASE),
    re.compile(r"only accepting candidates? (?:from|in) ([\w\s]{2,40})", re.IGNORECASE),
    re.compile(r"remote within (?:your )?(?:own )?country, ([\w\s]{2,40})", re.IGNORECASE),
    re.compile(r"this role is open to candidates? (?:in|from) ([\w\s]{2,40})", re.IGNORECASE),
)

JUNIOR_TITLE_TOKENS = ("junior", "intern", "entry level", "estagiário", "estagiario", "trainee")
ONSITE_HINTS = ("on-site", "onsite", "presencial", "in-office", "in office")
HYBRID_HINTS = ("hybrid", "híbrido", "hibrido")


@dataclass
class FitConcern:
    severity: str  # "block" | "warn" | "note"
    code: str
    message: str


@dataclass
class FitReport:
    job_id: int | None
    concerns: list[FitConcern] = field(default_factory=list)

    def has_blocker(self) -> bool:
        return any(c.severity == "block" for c in self.concerns)

    def summary(self) -> str:
        if not self.concerns:
            return "ok"
        return ", ".join(f"[{c.severity}] {c.code}" for c in self.concerns)


def validate_fit(
    job: Job,
    *,
    candidate_country: str = "Brazil",
    seniority: tuple[str, ...] = ("senior", "staff", "lead", "principal", "pleno"),
) -> FitReport:
    """Return a FitReport listing concerns. Empty .concerns ⇒ looks OK."""
    report = FitReport(job_id=job.id)
    title_lower = (job.title or "").lower()
    loc_lower = (job.location or "").lower()
    desc_lower = (job.description or "").lower()

    # 1. Seniority mismatch — title says junior/intern but profile is senior
    for tok in JUNIOR_TITLE_TOKENS:
        if tok in title_lower and not any(s in title_lower for s in seniority):
            report.concerns.append(
                FitConcern("block", "seniority_mismatch", f"title contains '{tok}'")
            )
            break

    # 2. US-only / clearance restrictions in description
    for phrase in US_RESTRICTED_PHRASES:
        if phrase in desc_lower:
            report.concerns.append(
                FitConcern(
                    "block",
                    "country_or_clearance_locked",
                    f"description requires '{phrase}'",
                )
            )
            break

    # 3. Country-locked phrases. Extract the matched country and compare.
    for pat in COUNTRY_LOCKED_PATTERNS:
        m = pat.search(job.description or "")
        if m:
            named_country = m.group(1).strip()
            if candidate_country.lower() not in named_country.lower():
                report.concerns.append(
                    FitConcern(
                        "block",
                        "country_locked",
                        f"description: 'only candidates in {named_country}'",
                    )
                )
            break

    # 4. Workplace-type vs location: on-site role in a country that isn't ours.
    onsite = any(h in loc_lower for h in ONSITE_HINTS) or any(h in desc_lower for h in ONSITE_HINTS)
    hybrid = any(h in loc_lower for h in HYBRID_HINTS) or any(h in desc_lower for h in HYBRID_HINTS)
    if onsite and candidate_country.lower() not in loc_lower and loc_lower:
        if not any(tok in loc_lower for tok in ("remote", "remoto", "worldwide", "anywhere")):
            report.concerns.append(
                FitConcern(
                    "warn",
                    "onsite_other_country",
                    f"on-site role in '{job.location}' (you're in {candidate_country})",
                )
            )
    elif hybrid and candidate_country.lower() not in loc_lower and loc_lower:
        report.concerns.append(
            FitConcern(
                "warn",
                "hybrid_other_country",
                f"hybrid role in '{job.location}' — partial relocation likely",
            )
        )

    return report
