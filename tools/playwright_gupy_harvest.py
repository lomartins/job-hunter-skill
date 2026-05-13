"""One-shot Gupy harvest using Playwright (renders client-side JS).

Visits a list of BR companies known to use Gupy and extracts senior mobile /
Android / KMP roles. Writes via the job-hunter DB layer so results show up
in `job-hunter list`.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, "/home/lomartins/projects/job-hunter-skill/skills/job-hunter/scripts")

from job_hunter.db import run_migrations
from job_hunter.discover import upsert_posting
from job_hunter.models import Application, Job  # noqa: F401
from job_hunter.paths import resolve
from job_hunter.sources.base import JobPosting
from sqlmodel import Session
from playwright.async_api import async_playwright


COMPANIES = [
    "nubank",
    "stark",
    "inter",
    "itau",
    "bradesco",
    "mercadolivre",
    "ifood",
    "rappi",
    "99",
    "picpay",
    "xp",
    "magalu",
    "americanas",
    "creditas",
    "vtex",
    "loft",
    "quintoandar",
    "recargapay",
    "pagseguro",
    "cloudwalk",
    "localiza",
    "ambev",
    "gerdau",
    "gympass",
    "wildlife",
    "olist",
    "movile",
    "movilepay",
    "neon",
    "warren",
    "btg",
    "stone",
    "ame",
    "linx",
    "trybe",
]

KEYWORDS = ("android", "kotlin", "mobile", "ios", "kmp", "multiplatform")
EXCLUDE = ("estagio", "estagiário", "estagiario", "intern", "junior", "trainee")


async def harvest_company(playwright_ctx, browser, company: str) -> list[JobPosting]:
    """Render https://<company>.gupy.io/jobs and extract relevant cards."""
    url = f"https://{company}.gupy.io/jobs"
    page = await browser.new_page(
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
    )
    out: list[JobPosting] = []
    try:
        await page.goto(url, wait_until="networkidle", timeout=20000)
    except Exception as e:
        print(f"  [skip {company}] navigation failed: {type(e).__name__}", file=sys.stderr)
        await page.close()
        return out

    # Wait briefly for client-side render
    try:
        await page.wait_for_selector("a[href*='/job/'], a[href*='/jobs/']", timeout=8000)
    except Exception:
        await page.close()
        return out

    # Extract job links + titles
    cards = await page.evaluate(
        """() => {
            const items = [];
            const anchors = document.querySelectorAll("a[href*='/job/'], a[href*='/jobs/']");
            anchors.forEach(a => {
                const href = a.getAttribute('href');
                if (!href || !href.includes('/job')) return;
                const card = a.closest('article, li, div[class*=card]') || a;
                const text = card.innerText || '';
                items.push({ href, text });
            });
            return items;
        }"""
    )
    seen: set[str] = set()
    for c in cards:
        href = c["href"]
        if href in seen:
            continue
        seen.add(href)
        text = c["text"]
        text_lower = text.lower()
        if not any(k in text_lower for k in KEYWORDS):
            continue
        if any(b in text_lower for b in EXCLUDE):
            continue
        # First line of card text = title (usually)
        title = text.strip().split("\n", 1)[0].strip()[:120]
        if not title:
            continue
        full_url = href if href.startswith("http") else f"https://{company}.gupy.io{href}"
        external_id = href.rstrip("/").rsplit("/", 1)[-1]
        out.append(
            JobPosting(
                source="gupy",
                external_id=f"{company}-{external_id}",
                url=full_url.split("?")[0],
                title=title,
                company=company.capitalize(),
                location="Brasil",
                remote=("remoto" in text_lower or "remote" in text_lower),
                raw_payload={"company_subdomain": company, "href": href},
            )
        )

    await page.close()
    return out


async def main() -> None:
    paths = resolve()
    run_migrations(paths)

    from sqlalchemy import create_engine

    eng = create_engine(f"sqlite:///{paths.db_path}", connect_args={"check_same_thread": False})

    all_postings: list[JobPosting] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        for company in COMPANIES:
            print(f"[{company}] rendering...", file=sys.stderr)
            postings = await harvest_company(p, browser, company)
            print(f"  -> {len(postings)} relevant", file=sys.stderr)
            all_postings.extend(postings)
        await browser.close()

    print(f"\nTotal harvested: {len(all_postings)}", file=sys.stderr)

    new_count = 0
    with Session(eng) as sess:
        for posting in all_postings:
            try:
                _, was_new = upsert_posting(sess, posting)
                if was_new:
                    new_count += 1
            except Exception as e:
                print(f"  upsert failed for {posting.url}: {e}", file=sys.stderr)
    print(f"\nNew rows: {new_count}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
