"""Salary aggregator: percentile distribution from DB rows."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlmodel import Session

from job_hunter import paths as paths_mod
from job_hunter.db import get_engine, run_migrations
from job_hunter.models import Job
from job_hunter.salary import aggregate, suggest_expectation


@pytest.fixture
def populated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[paths_mod.Paths, Engine]:
    paths_mod.clear_cache()
    monkeypatch.setenv("JOB_HUNTER_HOME_OVERRIDE", str(tmp_path))
    p = paths_mod.resolve()
    p.ensure()
    run_migrations(p)
    eng = get_engine(p)
    seed = [
        # role,            company,    location,   currency, min,    max
        ("Senior Android Engineer", "Nubank", "Brazil — Remote", "BRL", 12000, 18000),
        ("Senior Android Engineer", "Stark", "Brazil", "BRL", 14000, 20000),
        ("Senior Android Engineer", "Inter", "Brazil", "BRL", 16000, 22000),
        ("Senior Android Engineer", "Acme USA", "Worldwide", "USD", 90000, 130000),
        ("Kotlin Multiplatform Engineer", "GlobalCo", "Worldwide", "USD", 110000, 150000),
        ("Junior Android", "Trainee", "Brazil", "BRL", 4000, 6000),
        ("Data Scientist", "Other", "Brazil", "BRL", 10000, 14000),
    ]
    with Session(eng) as sess:
        for i, (title, company, location, currency, lo, hi) in enumerate(seed):
            sess.add(
                Job(
                    source="indeed",
                    external_id=f"seed-{i}",
                    url=f"https://example.com/jobs/{i}",
                    title=title,
                    company=company,
                    location=location,
                    salary_min=lo,
                    salary_max=hi,
                    currency=currency,
                    scraped_at=datetime(2026, 5, 10),
                    fingerprint=f"fp{i}",
                )
            )
        sess.commit()
    return p, eng


def test_aggregates_brl_android_roles(populated: tuple[paths_mod.Paths, Engine]) -> None:
    _, eng = populated
    with Session(eng) as sess:
        report = aggregate(sess, role="android")
    # 3 BRL senior + 1 USD senior + 1 BRL junior = 5 rows match "android"
    assert report.total_samples() == 5
    brl = report.buckets["BRL"]
    assert brl.count == 4  # 3 senior + 1 junior, all BRL
    # p25, median, p75 should be plausible
    assert brl.median is not None
    usd = report.buckets["USD"]
    assert usd.count == 1


def test_aggregate_filters_by_location_substring(populated: tuple[paths_mod.Paths, Engine]) -> None:
    _, eng = populated
    with Session(eng) as sess:
        report = aggregate(sess, role="android", location="brazil")
    # Excludes the Worldwide one
    total = sum(b.count for b in report.buckets.values())
    assert total == 4  # 3 BRL senior + 1 BRL junior


def test_aggregate_role_keyword_specific(populated: tuple[paths_mod.Paths, Engine]) -> None:
    _, eng = populated
    with Session(eng) as sess:
        report = aggregate(sess, role="multiplatform")
    assert report.total_samples() == 1
    assert "USD" in report.buckets


def test_suggest_expectation_uses_p75_plus_padding(
    populated: tuple[paths_mod.Paths, Engine],
) -> None:
    _, eng = populated
    with Session(eng) as sess:
        report = aggregate(sess, role="senior android", location="brazil")
    suggested = suggest_expectation(report, "BRL", padding=0.10)
    assert suggested is not None
    # p75 of 3 BRL Senior rows (midpoints 15000, 17000, 19000) is ~19000;
    # +10% padding -> ~20900. Allow a wide window because of percentile rounding.
    assert 18000 < suggested < 24000


def test_suggest_expectation_missing_currency_returns_none(
    populated: tuple[paths_mod.Paths, Engine],
) -> None:
    _, eng = populated
    with Session(eng) as sess:
        report = aggregate(sess, role="android")
    assert suggest_expectation(report, "EUR") is None


def test_aggregate_handles_no_matches(populated: tuple[paths_mod.Paths, Engine]) -> None:
    _, eng = populated
    with Session(eng) as sess:
        report = aggregate(sess, role="nonexistent role")
    assert report.total_samples() == 0
    assert report.buckets == {}
