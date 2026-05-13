"""Tests for fit validation heuristics (handoff #7)."""

from __future__ import annotations

from datetime import datetime

from job_hunter.models import Job
from job_hunter.validate import validate_fit


def _job(
    title: str = "Senior Android Engineer",
    location: str | None = None,
    description: str | None = None,
) -> Job:
    return Job(
        source="indeed",
        external_id="t1",
        url="https://example.com/1",
        title=title,
        company="Acme",
        location=location,
        description=description,
        scraped_at=datetime(2026, 5, 13),
        fingerprint="fp",
    )


def test_clean_role_passes() -> None:
    r = validate_fit(_job(location="Brazil (Remote)", description="Build Android apps."))
    assert r.concerns == []
    assert r.summary() == "ok"
    assert not r.has_blocker()


def test_junior_blocks() -> None:
    r = validate_fit(_job(title="Junior Android Developer"))
    assert r.has_blocker()
    assert any(c.code == "seniority_mismatch" for c in r.concerns)


def test_senior_junior_in_title_passes() -> None:
    """'Senior Android Engineer' should NOT match 'junior' even if word boundaries don't help."""
    r = validate_fit(_job(title="Senior Mobile Engineer (no junior policies)"))
    # 'junior' substring exists in title but 'senior' also does → not blocked.
    assert not any(c.code == "seniority_mismatch" for c in r.concerns)


def test_us_citizenship_blocks() -> None:
    r = validate_fit(_job(description="This role requires US citizenship and a TS/SCI clearance."))
    assert r.has_blocker()
    assert any(c.code == "country_or_clearance_locked" for c in r.concerns)


def test_country_locked_blocks_when_not_candidate_country() -> None:
    r = validate_fit(
        _job(description="Only accepting candidates from United States."),
        candidate_country="Brazil",
    )
    assert r.has_blocker()
    assert any(c.code == "country_locked" for c in r.concerns)


def test_country_locked_allows_when_match() -> None:
    r = validate_fit(
        _job(description="Only accepting candidates from Brazil."),
        candidate_country="Brazil",
    )
    assert not any(c.code == "country_locked" for c in r.concerns)


def test_onsite_other_country_warns() -> None:
    r = validate_fit(
        _job(location="Mountain View, CA (On-site)", description="Onsite role."),
        candidate_country="Brazil",
    )
    assert any(c.code == "onsite_other_country" for c in r.concerns)
    assert not r.has_blocker()  # warn, not block


def test_onsite_same_country_no_warn() -> None:
    r = validate_fit(
        _job(location="São Paulo, Brazil (On-site)"),
        candidate_country="Brazil",
    )
    assert not any(c.code == "onsite_other_country" for c in r.concerns)


def test_onsite_remote_in_location_no_warn() -> None:
    r = validate_fit(_job(location="Remote (US-based on-site office)"))
    # 'remote' present so no onsite_other_country
    assert not any(c.code == "onsite_other_country" for c in r.concerns)


def test_hybrid_other_country_warns() -> None:
    r = validate_fit(
        _job(location="Bengaluru, India (Hybrid)"),
        candidate_country="Brazil",
    )
    assert any(c.code == "hybrid_other_country" for c in r.concerns)


def test_summary_format() -> None:
    r = validate_fit(_job(title="Junior Android"))
    assert "[block]" in r.summary()
    assert "seniority_mismatch" in r.summary()
