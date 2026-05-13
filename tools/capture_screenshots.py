"""Capture README screenshots from the local webapp using Playwright.

Run while `job-hunter web` is up on the default port (127.0.0.1:8765).
Writes PNGs into docs/screenshots/. One-shot helper; not part of the
package install.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
SHOTS = [
    ("jobs",       "/jobs?sort=salary",      (1440, 900)),
    ("tracker",    "/tracker",               (1600, 900)),
    ("metrics",    "/metrics",               (1440, 900)),
    ("detail",     "/jobs/1",                (1440, 1100)),
]


async def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        for name, path, (w, h) in SHOTS:
            ctx = await browser.new_context(
                viewport={"width": w, "height": h},
                device_scale_factor=2,  # crisp on README
            )
            page = await ctx.new_page()
            url = f"http://127.0.0.1:8765{path}"
            print(f"  → {name}: {url}")
            await page.goto(url, wait_until="networkidle")
            # Let charts settle.
            await page.wait_for_timeout(1500)
            out_path = OUT / f"{name}.png"
            await page.screenshot(path=str(out_path), full_page=False)
            await ctx.close()
            print(f"    wrote {out_path.relative_to(OUT.parent.parent)}")
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
