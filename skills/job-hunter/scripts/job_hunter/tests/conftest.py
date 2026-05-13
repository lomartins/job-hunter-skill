"""Shared pytest fixtures.

The `job_hunter_home` fixture builds a clean XDG tree under tmp_path and
sets the JOB_HUNTER_HOME_OVERRIDE env var so `paths.py` honors it.
Real `paths.py` lands in phase 2; the fixture is here so phase-1 tests can
already use it.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def job_hunter_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    root = tmp_path / "job-hunter-home"
    (root / "config" / "job-hunter" / "secrets").mkdir(parents=True)
    (root / "data" / "job-hunter" / "tracking").mkdir(parents=True)
    (root / "data" / "job-hunter" / "adapters_inbox").mkdir(parents=True)
    (root / "data" / "job-hunter" / "adapters_user").mkdir(parents=True)
    (root / "data" / "job-hunter" / "files").mkdir(parents=True)
    (root / "data" / "job-hunter" / "runs").mkdir(parents=True)
    (root / "state" / "job-hunter" / "logs").mkdir(parents=True)

    monkeypatch.setenv("JOB_HUNTER_HOME_OVERRIDE", str(root))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(root / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(root / "data"))
    monkeypatch.setenv("XDG_STATE_HOME", str(root / "state"))

    yield root

    # Belt-and-suspenders: scrub any env carry-over.
    for var in ("JOB_HUNTER_HOME_OVERRIDE",):
        os.environ.pop(var, None)
