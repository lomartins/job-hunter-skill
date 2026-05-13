#!/usr/bin/env python3
"""Thin shim so the linter is runnable directly from the repo without `uv run`.

Real implementation lives in `job_hunter.lint_secret_leaks`. We add the package
to sys.path so this script works from a fresh clone before `uv sync`.
"""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from job_hunter.lint_secret_leaks import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
