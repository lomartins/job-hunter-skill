"""Migration runner + schema agreement with SQLModel definitions."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from job_hunter import paths as paths_mod
from job_hunter.db import get_engine, run_migrations


def test_migrations_apply_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    paths_mod.clear_cache()
    monkeypatch.setenv("JOB_HUNTER_HOME_OVERRIDE", str(tmp_path))
    p = paths_mod.resolve()
    p.ensure()

    applied = run_migrations(p)
    assert applied, "expected at least one migration on a fresh DB"

    again = run_migrations(p)
    assert again == [], "re-running migrations should be a no-op"


def test_migration_creates_expected_tables(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    paths_mod.clear_cache()
    monkeypatch.setenv("JOB_HUNTER_HOME_OVERRIDE", str(tmp_path))
    p = paths_mod.resolve()
    p.ensure()
    run_migrations(p)

    eng = get_engine(p)
    insp = inspect(eng)
    table_names = set(insp.get_table_names())
    expected = {
        "jobs",
        "applications",
        "stage_history",
        "site_adapters",
        "fill_attempts",
        "cover_letter_approvals",
        "_migrations",
    }
    missing = expected - table_names
    assert not missing, f"missing tables: {missing}"


def test_foreign_keys_on(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    paths_mod.clear_cache()
    monkeypatch.setenv("JOB_HUNTER_HOME_OVERRIDE", str(tmp_path))
    p = paths_mod.resolve()
    p.ensure()
    run_migrations(p)

    eng = get_engine(p)
    with eng.begin() as conn:
        result = conn.execute(text("PRAGMA foreign_keys")).scalar()
    assert result == 1, "foreign_keys pragma should be ON"
