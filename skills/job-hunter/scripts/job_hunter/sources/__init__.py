"""Job source registry.

Each source module exposes a `SOURCE` instance implementing the Source protocol
(see `base.py`). The registry maps source name -> instance.
"""

from __future__ import annotations

from .base import (
    DiscoveryReport,
    JobPosting,
    RateLimitConfig,
    SearchQuery,
    Source,
    SourceError,
    new_run_dir,
    write_report,
)
from .gupy import SOURCE as GUPY
from .job_na_gringa import SOURCE as JOB_NA_GRINGA
from .linkedin import SOURCE as LINKEDIN
from .remoteok import SOURCE as REMOTEOK
from .stubs import SOURCES as STUB_SOURCES

REGISTRY: dict[str, Source] = {
    REMOTEOK.name: REMOTEOK,
    JOB_NA_GRINGA.name: JOB_NA_GRINGA,
    GUPY.name: GUPY,
    LINKEDIN.name: LINKEDIN,
    **STUB_SOURCES,
}


def get_source(name: str) -> Source:
    try:
        return REGISTRY[name]
    except KeyError as e:
        known = ", ".join(sorted(REGISTRY))
        raise SourceError(f"unknown source {name!r} — known: {known}") from e


__all__ = [
    "REGISTRY",
    "DiscoveryReport",
    "JobPosting",
    "RateLimitConfig",
    "SearchQuery",
    "Source",
    "SourceError",
    "get_source",
    "new_run_dir",
    "write_report",
]
