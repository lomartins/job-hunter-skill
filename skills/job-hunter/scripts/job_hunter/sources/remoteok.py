"""RemoteOK: public JSON API at https://remoteok.com/api."""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from .base import (
    JobPosting,
    RateLimitConfig,
    SearchQuery,
)


@dataclass
class RemoteOKSource:
    name: str = "remoteok"
    base_url: str = "https://remoteok.com"
    rate_limit: RateLimitConfig | None = None

    def __post_init__(self) -> None:
        if self.rate_limit is None:
            self.rate_limit = RateLimitConfig("remoteok.com", 5.0, 10.0)

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=1, max=10),
        reraise=True,
    )
    async def _fetch(self, client: httpx.AsyncClient) -> list[dict[str, object]]:
        resp = await client.get(
            f"{self.base_url}/api",
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError(f"unexpected payload type: {type(data).__name__}")
        # Index 0 is metadata/disclaimer; skip it.
        return [item for item in data[1:] if isinstance(item, dict) and item.get("id")]

    async def discover(
        self, query: SearchQuery, client: httpx.AsyncClient
    ) -> AsyncIterator[JobPosting]:
        items = await self._fetch(client)
        for item in items:
            posting = _to_posting(item)
            tags = posting.raw_payload.get("tags", [])
            tag_str = (
                " ".join(t for t in tags if isinstance(t, str)) if isinstance(tags, list) else ""
            )
            if not query.matches_role(f"{posting.title} {tag_str}"):
                continue
            yield posting

    async def fetch_detail(self, posting: JobPosting, client: httpx.AsyncClient) -> JobPosting:
        return posting  # description already in the listing payload


def _to_posting(item: dict[str, object]) -> JobPosting:
    posted_at: datetime | None = None
    raw_date = item.get("date")
    if isinstance(raw_date, str):
        with contextlib.suppress(ValueError):
            posted_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))

    salary_min = _safe_int(item.get("salary_min"))
    salary_max = _safe_int(item.get("salary_max"))
    location = _opt_str(item.get("location"))
    remote_val = item.get("remote", True)
    remote = bool(remote_val) if isinstance(remote_val, bool | int) else True

    ext_id = str(item["id"])
    url = _opt_str(item.get("url")) or f"https://remoteok.com/remote-jobs/{ext_id}"
    title = _opt_str(item.get("position")) or _opt_str(item.get("title")) or "Unknown"
    company = _opt_str(item.get("company")) or "Unknown"
    description = _opt_str(item.get("description"))
    raw_tags = item.get("tags", [])
    if not isinstance(raw_tags, list):
        raw_tags = []
    tags = [t.strip().lower() for t in raw_tags if isinstance(t, str) and t.strip()]

    return JobPosting(
        source="remoteok",
        external_id=ext_id,
        url=url,
        title=title,
        company=company,
        location=location,
        remote=remote,
        salary_min=salary_min,
        salary_max=salary_max,
        currency="USD" if (salary_min or salary_max) else None,
        posted_at=posted_at,
        description=description,
        raw_payload={"tags": tags, "id": item.get("id")},
        tags=tags,
        # RemoteOK's salary_min/max fields are always annual figures.
        salary_period="year" if (salary_min or salary_max) else None,
    )


def _opt_str(v: object) -> str | None:
    return v if isinstance(v, str) else None


def _safe_int(v: object) -> int | None:
    if v in (None, "", 0):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str | float):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    return None


SOURCE: RemoteOKSource = RemoteOKSource()
