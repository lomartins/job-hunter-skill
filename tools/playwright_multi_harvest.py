"""Multi-source Playwright harvest: Indeed (BR + Remote) + select Greenhouse
boards of remote-friendly companies. Renders client-side JS, filters by
Senior Mobile / Android / KMP relevance, upserts into the job-hunter DB.

Single one-shot tool; not part of the package install.
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import UTC, datetime

sys.path.insert(0, "/home/lomartins/projects/job-hunter-skill/skills/job-hunter/scripts")

from job_hunter.db import run_migrations
from job_hunter.discover import upsert_posting
from job_hunter.paths import resolve
from job_hunter.sources.base import JobPosting
from playwright.async_api import Browser, Playwright, async_playwright
from sqlalchemy import create_engine
from sqlmodel import Session

# Title-only keyword match — title is the first line of the card text.
TITLE_KEYWORDS = (
    "android",
    "kotlin",
    "mobile",
    "kmp",
    "multiplatform",
    "ios",
    "engenheiro mobile",
    "desenvolvedor mobile",
    "developer mobile",
    "mobile engineer",
    "mobile developer",
    "mobile software",
)
EXCLUDE = ("estagio", "estagiário", "estagiario", "intern", "junior", "trainee")
SENIOR_HINTS = (
    "senior",
    "sênior",
    "sr.",
    "sr ",
    "staff",
    "lead",
    "principal",
    "tech lead",
    "specialist",
    "iv",
    "pleno",
)  # pleno = mid-level (OK)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"


def is_relevant_title(title: str) -> bool:
    t = title.lower()
    if any(b in t for b in EXCLUDE):
        return False
    if not any(k in t for k in TITLE_KEYWORDS):
        return False
    # Default to True; surfacing some mid-level too since profile lists `pleno`
    return True


async def harvest_indeed(browser: Browser, base_query: str, location: str) -> list[JobPosting]:
    page = await browser.new_page(user_agent=UA, locale="pt-BR")
    url = f"https://br.indeed.com/jobs?q={base_query.replace(' ', '+')}&l={location.replace(' ', '+')}&fromage=14"
    out: list[JobPosting] = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=25000)
    except Exception as e:
        print(f"  [indeed/{base_query}] nav failed: {type(e).__name__}", file=sys.stderr)
        await page.close()
        return out

    # Wait for cards
    try:
        await page.wait_for_selector("div[data-jk], a[data-jk], h2.jobTitle a", timeout=12000)
    except Exception:
        # Likely captcha or empty result. Indeed is finicky.
        await page.close()
        return out

    cards = await page.evaluate(
        """() => {
            const items = [];
            const cardEls = document.querySelectorAll('div[data-jk], a[data-jk]');
            cardEls.forEach(el => {
                const jk = el.getAttribute('data-jk');
                if (!jk) return;
                const titleEl = el.querySelector('h2.jobTitle span[title], h2.jobTitle a span') ||
                                el.querySelector('span[title]');
                const title = titleEl ? (titleEl.getAttribute('title') || titleEl.textContent || '').trim() : '';
                const companyEl = el.querySelector('[data-testid=\"company-name\"], span.companyName');
                const company = companyEl ? companyEl.textContent.trim() : '';
                const locEl = el.querySelector('[data-testid=\"text-location\"], div.companyLocation');
                const location = locEl ? locEl.textContent.trim() : '';
                const salEl = el.querySelector('[data-testid=\"attribute_snippet_testid\"], .salary-snippet');
                const salary = salEl ? salEl.textContent.trim() : '';
                items.push({ jk, title, company, location, salary });
            });
            return items;
        }"""
    )
    seen: set[str] = set()
    for c in cards:
        if c["jk"] in seen:
            continue
        seen.add(c["jk"])
        title = c["title"]
        if not is_relevant_title(title):
            continue
        out.append(
            JobPosting(
                source="indeed",
                external_id=c["jk"],
                url=f"https://br.indeed.com/viewjob?jk={c['jk']}",
                title=title,
                company=c["company"] or "Unknown",
                location=c["location"] or location,
                remote=(
                    "remoto" in (c["location"] or "").lower()
                    or "remote" in (c["location"] or "").lower()
                ),
                raw_payload={"data_jk": c["jk"], "salary_raw": c["salary"]},
            )
        )

    await page.close()
    return out


async def harvest_greenhouse(browser: Browser, company: str) -> list[JobPosting]:
    """Pull from boards.greenhouse.io/<company>. Server-rendered, fast."""
    page = await browser.new_page(user_agent=UA)
    url = f"https://boards.greenhouse.io/{company}"
    out: list[JobPosting] = []
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=15000)
    except Exception:
        await page.close()
        return out

    cards = await page.evaluate(
        """() => {
            const items = [];
            // Greenhouse boards: each job is an <a class="..."> inside an <opening> or .opening row
            document.querySelectorAll('a[href*="/jobs/"]').forEach(a => {
                const href = a.getAttribute('href') || '';
                const title = (a.textContent || '').trim();
                const row = a.closest('.opening') || a.closest('li');
                const locEl = row ? row.querySelector('.location') : null;
                const location = locEl ? locEl.textContent.trim() : '';
                items.push({ href, title, location });
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
        title = c["title"]
        if not is_relevant_title(title):
            continue
        full_url = href if href.startswith("http") else f"https://boards.greenhouse.io{href}"
        # external_id: numeric ID at end of /jobs/<id>
        m = re.search(r"/jobs/(\d+)", href)
        ext = m.group(1) if m else href
        out.append(
            JobPosting(
                source="greenhouse",
                external_id=f"{company}-{ext}",
                url=full_url.split("?")[0],
                title=title,
                company=company.replace("-", " ").title(),
                location=c["location"] or None,
                remote=(
                    "remote" in (c["location"] or "").lower()
                    or "worldwide" in (c["location"] or "").lower()
                ),
                raw_payload={"board": company, "href": href},
            )
        )

    await page.close()
    return out


async def main() -> None:
    paths = resolve()
    run_migrations(paths)
    eng = create_engine(f"sqlite:///{paths.db_path}", connect_args={"check_same_thread": False})

    all_postings: list[JobPosting] = []

    indeed_queries = [
        ("android engineer", "Brasil"),
        ("kotlin developer", "Brasil"),
        ("mobile engineer", "Brasil"),
        ("android", "Remote"),
        ("kotlin multiplatform", "Worldwide"),
    ]
    greenhouse_boards = [
        # Remote-friendly companies that use Greenhouse + hire Brazilians
        "stone",
        "nubank",
        "olist",
        "vtex",
        "loft",
        "quintoandar",
        "stripe",
        "gitlab",
        "datadog",
        "doximity",
        "buffer",
        "shopify",
        "ramp",
        "duolingo",
        "elastic",
        "automattic",
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        print("=== Indeed (Playwright-rendered) ===", file=sys.stderr)
        for q, loc in indeed_queries:
            print(f"  [{q} | {loc}]", file=sys.stderr)
            posts = await harvest_indeed(browser, q, loc)
            print(f"    -> {len(posts)} relevant", file=sys.stderr)
            all_postings.extend(posts)
            await asyncio.sleep(8)  # be polite

        print("\n=== Greenhouse boards ===", file=sys.stderr)
        for c in greenhouse_boards:
            posts = await harvest_greenhouse(browser, c)
            print(f"  [{c}] -> {len(posts)} relevant", file=sys.stderr)
            all_postings.extend(posts)
            await asyncio.sleep(2)

        await browser.close()

    # Dedup by URL (multiple queries may hit same posting)
    by_url: dict[str, JobPosting] = {}
    for p in all_postings:
        by_url.setdefault(p.url, p)
    deduped = list(by_url.values())

    print(f"\nTotal harvested (deduped): {len(deduped)}", file=sys.stderr)

    new_count = 0
    with Session(eng) as sess:
        for posting in deduped:
            try:
                _, was_new = upsert_posting(sess, posting)
                if was_new:
                    new_count += 1
            except Exception as e:
                print(f"  upsert failed for {posting.url}: {e}", file=sys.stderr)
    print(f"New rows added to DB: {new_count}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
