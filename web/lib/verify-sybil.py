"""Unavailable-state browser check for the gated Sybil playground."""

import asyncio
import os
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from aegis.schemas import SybilDatasetStatus  # noqa: E402

BASE = os.environ.get("SYBIL_WEB_URL", "http://localhost:3103")
OUTPUT = Path(__file__).resolve().parents[1] / ".next" / "sybil-verification"


async def main():
    dataset = SybilDatasetStatus(
        release="cc-main-2026-aug-sep-oct",
        source_nodes=134979706,
        source_edges=1817202146,
        reason="Real graph extraction is pending.",
        source_url="https://index.commoncrawl.org/graphinfo.json",
    )
    OUTPUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel="chrome")
        page = await browser.new_page(reduced_motion="reduce")
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        unavailable = False

        async def respond(route):
            headers = {"Access-Control-Allow-Origin": BASE}
            if unavailable:
                await route.fulfill(
                    status=404,
                    json={"detail": "Sybil Playground is disabled"},
                    headers=headers,
                )
            else:
                await route.fulfill(json=[dataset.model_dump()], headers=headers)

        await page.route("**/sybil/datasets", respond)
        for width, height in [(1280, 720), (390, 844)]:
            await page.set_viewport_size({"width": width, "height": height})
            await page.goto(BASE + "/sybil")
            await page.get_by_text("Real graph unavailable", exact=True).wait_for()
            assert await page.get_by_role("button", name="Create revision").is_disabled()
            assert await page.get_by_role("button", name="Run agent comparison").is_disabled()
            assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            await page.get_by_text("Inspect the score formula", exact=True).click()
            await page.get_by_text("Formula sybil-v1 · restart 0.15.", exact=True).wait_for(
                state="visible"
            )
            await page.screenshot(path=str(OUTPUT / f"{width}.png"), full_page=True)
        unavailable = True
        await page.goto(BASE + "/sybil?retry=1")
        await page.get_by_role("button", name="Retry dataset check").wait_for()
        unavailable = False
        await page.get_by_role("button", name="Retry dataset check").click()
        await page.get_by_text("Real graph unavailable", exact=True).wait_for()
        assert not errors, errors
        await browser.close()
    print("Sybil readiness: desktop, phone, unavailable state, formula and retry passed.")


if __name__ == "__main__":
    asyncio.run(main())
