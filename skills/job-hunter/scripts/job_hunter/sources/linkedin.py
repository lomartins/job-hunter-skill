"""LinkedIn: authenticated via the `li_at` session cookie.

The cookie is read from `os.environ["LINKEDIN_LI_AT"]` after the user's
`personal.env` has been loaded into the process. NEVER LOGGED.

Hard rate limit: 12-25s jittered between requests (enforced via the shared
RateLimiter, so concurrent terminals share the budget).
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import quote_plus

import httpx
from selectolax.parser import HTMLParser
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

from .base import (
    JobPosting,
    RateLimitConfig,
    SearchQuery,
    SourceError,
)


@dataclass
class LinkedInSource:
    name: str = "linkedin"
    base_url: str = "https://www.linkedin.com"
    rate_limit: RateLimitConfig | None = None

    def __post_init__(self) -> None:
        if self.rate_limit is None:
            self.rate_limit = RateLimitConfig("linkedin.com", 12.0, 25.0)

    def _cookie(self) -> str:
        v = os.environ.get("LINKEDIN_LI_AT")
        if not v:
            raise SourceError(
                "LINKEDIN_LI_AT not set. Add it to ~/.config/job-hunter/secrets/personal.env "
                "(see references/sources/linkedin.md for how to capture)."
            )
        return v

    @retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        stop=stop_after_attempt(3),
        wait=wait_exponential_jitter(initial=2, max=30),
        reraise=True,
    )
    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str:
        # Cookie injected per-request; never written to disk or logs.
        cookies = {"li_at": self._cookie()}
        resp = await client.get(url, cookies=cookies)
        if resp.status_code in (403, 429, 999):
            raise SourceError(
                f"LinkedIn returned {resp.status_code} — likely flagged/limited. "
                "Refresh cookie or pause runs."
            )
        resp.raise_for_status()
        return resp.text

    async def discover(
        self, query: SearchQuery, client: httpx.AsyncClient
    ) -> AsyncIterator[JobPosting]:
        if not query.roles:
            return
        for role in query.roles:
            for location in query.locations or ["Brazil"]:
                kw = quote_plus(role)
                loc = quote_plus(location)
                url = f"{self.base_url}/jobs/search/?keywords={kw}" f"&location={loc}&f_TPR=r604800"
                try:
                    html = await self._fetch(client, url)
                except SourceError:
                    raise
                except httpx.HTTPError:
                    continue
                for posting in parse_search_results(html, self.base_url):
                    if not query.matches_role(posting.title):
                        continue
                    yield posting

    async def fetch_detail(self, posting: JobPosting, client: httpx.AsyncClient) -> JobPosting:
        if posting.description:
            return posting
        try:
            html = await self._fetch(client, posting.url)
        except (SourceError, httpx.HTTPError):
            return posting
        tree = HTMLParser(html)
        body = tree.css_first(".show-more-less-html__markup, .description__text")
        if body is not None:
            posting.description = body.text(separator="\n").strip()
        return posting


def parse_search_results(html: str, base_url: str) -> list[JobPosting]:
    """Parse a LinkedIn jobs search result list.

    LinkedIn serves TWO different layouts:

    1. **Authenticated** (when `li_at` is valid): SPA-style. Cards are
       `[data-occludable-job-id]` containing `.artdeco-entity-lockup__title` /
       `__subtitle` / `__caption`. The `data-occludable-job-id` attribute is
       the authoritative external_id.

    2. **Anonymous** (no cookie / cookie rejected): server-rendered. Cards are
       `.base-card` under `ul.jobs-search__results-list`. External_id comes
       from `/jobs/view/<id>` in the link href.

    We try the authenticated layout first; fall back to the anonymous one.
    """
    tree = HTMLParser(html)
    out: list[JobPosting] = []
    from selectolax.parser import Node

    # ── authenticated layout ────────────────────────────────────────────────
    auth_cards = tree.css("[data-occludable-job-id]")
    seen_ids: set[str] = set()
    for card in auth_cards:
        ext_id = card.attributes.get("data-occludable-job-id") or card.attributes.get("data-job-id")
        if not ext_id or ext_id in seen_ids:
            continue
        seen_ids.add(ext_id)
        title_el = card.css_first(".artdeco-entity-lockup__title")
        company_el = card.css_first(".artdeco-entity-lockup__subtitle")
        location_el = card.css_first(".artdeco-entity-lockup__caption")
        link_el = card.css_first("a.job-card-container__link, a[href*='/jobs/view/']")
        if not title_el:
            continue
        href = link_el.attributes.get("href") if link_el else None
        url = (
            (href if href and href.startswith("http") else f"{base_url}{href}")
            if href
            else f"{base_url}/jobs/view/{ext_id}/"
        )
        out.append(
            JobPosting(
                source="linkedin",
                external_id=ext_id,
                url=url.split("?")[0],
                title=title_el.text(strip=True),
                company=company_el.text(strip=True) if company_el else "Unknown",
                location=location_el.text(strip=True) if location_el else None,
                raw_payload={"layout": "authenticated"},
            )
        )

    if out:
        return out

    # ── anonymous layout (fallback) ─────────────────────────────────────────
    seen_nodes: set[int] = set()
    cards: list[Node] = []
    for sel in ("ul.jobs-search__results-list li", ".jobs-search-results__list-item"):
        for node in tree.css(sel):
            key = id(node)
            if key in seen_nodes:
                continue
            seen_nodes.add(key)
            cards.append(node)
    for card in cards:
        title_el = card.css_first("h3.base-search-card__title, .base-search-card__title")
        company_el = card.css_first(
            "h4.base-search-card__subtitle, .base-search-card__subtitle, .hidden-nested-link"
        )
        location_el = card.css_first(".job-search-card__location, .base-search-card__metadata")
        link_el = card.css_first("a.base-card__full-link[href], a[href*='/jobs/view/']")
        if not (title_el and company_el and link_el):
            continue
        href = link_el.attributes.get("href") or ""
        url = href if href.startswith("http") else f"{base_url}{href}"
        external_id = ""
        if "/jobs/view/" in url:
            tail = url.split("/jobs/view/", 1)[1]
            external_id = tail.split("?", 1)[0].rstrip("/").split("/")[-1]
        external_id = external_id or url
        out.append(
            JobPosting(
                source="linkedin",
                external_id=external_id,
                url=url.split("?")[0],
                title=title_el.text(strip=True),
                company=company_el.text(strip=True),
                location=location_el.text(strip=True) if location_el else None,
                raw_payload={"layout": "anonymous", "href": href},
            )
        )
    return out


SOURCE: LinkedInSource = LinkedInSource()
