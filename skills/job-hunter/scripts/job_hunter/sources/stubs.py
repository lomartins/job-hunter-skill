"""Stub sources for items 5–11. Each raises NotImplementedError at discover().

Documented in references/sources/*.md. Phase 3 only ships sources 1–4 as
working; the stubs are there so `job discover --source <name>` produces a
clear "not yet" message instead of a `unknown source` error.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from .base import JobPosting, RateLimitConfig, SearchQuery, SourceError


@dataclass
class StubSource:
    name: str
    base_url: str
    rate_limit: RateLimitConfig | None = None

    async def discover(
        self, query: SearchQuery, client: httpx.AsyncClient
    ) -> AsyncIterator[JobPosting]:
        raise SourceError(
            f"source {self.name!r} is not yet implemented — "
            f"see references/sources/{self.name}.md for the spec."
        )
        # Make the type checker happy:
        if False:
            yield JobPosting(source=self.name, external_id="", url="", title="", company="")

    async def fetch_detail(self, posting: JobPosting, client: httpx.AsyncClient) -> JobPosting:
        return posting


def _stub(name: str, base_url: str) -> StubSource:
    return StubSource(name=name, base_url=base_url)


SOURCES: dict[str, StubSource] = {
    "remotive": _stub("remotive", "https://remotive.com"),
    "wwr": _stub("wwr", "https://weworkremotely.com"),
    "himalayas": _stub("himalayas", "https://himalayas.app"),
    "programathor": _stub("programathor", "https://programathor.com.br"),
    "coodesh": _stub("coodesh", "https://coodesh.com"),
    "trampos": _stub("trampos", "https://trampos.co"),
    "arcdev": _stub("arcdev", "https://arc.dev"),
}
