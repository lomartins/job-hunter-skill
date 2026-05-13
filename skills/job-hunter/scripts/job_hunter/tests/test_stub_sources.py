"""Stub sources must raise SourceError with a clear message on discover()."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from job_hunter.sources import REGISTRY, SourceError
from job_hunter.sources.base import SearchQuery
from job_hunter.sources.stubs import SOURCES as STUB_SOURCES


@pytest.mark.parametrize("name", list(STUB_SOURCES))
def test_stub_raises_source_error(name: str) -> None:
    src = REGISTRY[name]

    async def go() -> None:
        async with httpx.AsyncClient() as client:
            with pytest.raises(SourceError) as exc:
                async for _ in src.discover(SearchQuery(), client):
                    pass
        assert "not yet implemented" in str(exc.value)
        assert name in str(exc.value)

    asyncio.run(go())


def test_registry_contains_expected_sources() -> None:
    expected = {
        "remoteok",
        "job_na_gringa",
        "gupy",
        "linkedin",
        "remotive",
        "wwr",
        "himalayas",
        "programathor",
        "coodesh",
        "trampos",
        "arcdev",
    }
    assert expected <= set(REGISTRY)
