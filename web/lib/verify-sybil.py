"""Browser checks for unavailable and editable Sybil playground states."""

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
            headers = {"Access-Control-Allow-Origin": BASE, "Cache-Control": "no-store"}
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
            await page.get_by_text("Formula sybil-v2 · restart 0.15.", exact=True).wait_for(
                state="visible"
            )
            await page.screenshot(path=str(OUTPUT / f"{width}.png"), full_page=True)
        unavailable = True
        await page.goto(BASE + "/sybil?retry=1")
        await page.get_by_role("button", name="Retry the dataset check").wait_for()
        unavailable = False
        await page.get_by_role("button", name="Retry the dataset check").click()
        await page.get_by_text("Real graph unavailable", exact=True).wait_for()

        await page.unroute("**/sybil/datasets", respond)
        edits = {
            "dataset_id": "test",
            "mode": "challenge",
            "injected_nodes": ["sim:one"],
            "added_links": [],
            "removed_links": [],
            "recommendations": [{"website": "sim:one", "shop": "B"}],
            "removed_recommendations": [],
            "compromised": [],
            "cooperating_links": [],
            "anchors": None,
            "restart": 0.15,
            "weights": {"base": 0.4, "breadth": 0.2, "withdrawal": 0.2, "connection": 0.2},
        }
        budget = {
            "injected_websites": 1,
            "internal_links": 0,
            "external_credits": 0,
            "website_limit": 1000,
            "internal_link_limit": 100000,
            "credit_limit": 25,
        }
        revisions = {
            "generate": {
                "id": "a" * 64,
                "dataset_id": "test",
                "dataset_hash": "d" * 64,
                "edits": edits,
                "budget": budget,
                "policy_version": "sybil-challenge-v1",
            },
            "edit": {
                "id": "b" * 64,
                "dataset_id": "test",
                "dataset_hash": "d" * 64,
                "edits": edits,
                "budget": budget,
                "policy_version": "sybil-challenge-v1",
            },
        }
        score = {
            "recommendation_count": 1,
            "trust_weighted_support": 0.2,
            "structural_support": 0.66,
            "effective_anchors": 2,
            "anchor_breadth": 0.14,
            "anchor_withdrawal_resilience": 0.8,
            "tested_connection_resilience": 0.7,
            "total_robustness": 62.1,
            "tested_edges": [],
        }

        async def respond_available(route):
            url = route.request.url
            headers = {
                "Access-Control-Allow-Origin": BASE,
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Cache-Control": "no-store",
            }
            if route.request.method == "OPTIONS":
                await route.fulfill(status=204, headers=headers)
                return
            if url.endswith("/sybil/datasets"):
                body = [
                    {
                        "release": "cc-main-2026-aug-sep-oct",
                        "dataset_id": "test",
                        "status": "available",
                        "source_nodes": 134979706,
                        "source_edges": 1817202146,
                        "imported_nodes": 50000,
                        "imported_edges": 1000000,
                        "observation_date": "2026-11-15",
                        "reason": "Validated",
                        "source_url": "https://example.invalid",
                    }
                ]
            elif "/generate" in url:
                body = revisions["generate"]
            elif url.endswith("/sybil/scenarios"):
                body = revisions["edit"]
            elif "/view?" in url or url.endswith("/view"):
                body = {
                    "revision_id": "a" * 64,
                    "total_nodes": 2,
                    "total_edges": 0,
                    "displayed_nodes": 2,
                    "displayed_edges": 0,
                    "nodes": [
                        {
                            "id": "anchor",
                            "label": "anchor.invalid",
                            "provenance": "observed",
                            "anchor": True,
                            "original_outdegree": 0,
                            "retained_outdegree": 0,
                            "x": 0,
                            "y": 0,
                        },
                        {
                            "id": "sim:one",
                            "label": "sim:one",
                            "provenance": "simulated",
                            "anchor": False,
                            "original_outdegree": 0,
                            "retained_outdegree": 0,
                            "x": 1,
                            "y": 1,
                        },
                    ],
                    "edges": [],
                    "recommendations": edits["recommendations"],
                    "subset": False,
                }
            elif url.endswith("/assessments"):
                body = {
                    "id": "e" * 64,
                    "revision_id": "a" * 64,
                    "status": "complete",
                    "formula_version": "sybil-v2",
                    "converged": True,
                    "residual": 0,
                    "iterations": 8,
                    "elapsed_ms": 120,
                    "scores": {
                        "A": {**score, "recommendation_count": 0, "total_robustness": 0},
                        "B": score,
                    },
                    "reason": None,
                }
            elif url.endswith("/counterfactuals"):
                delta = {
                    "trust_weighted_support": 0,
                    "structural_support": 0,
                    "anchor_breadth": 0,
                    "anchor_withdrawal_resilience": 0,
                    "tested_connection_resilience": 0,
                    "total_robustness": 0,
                    "rank": 0,
                }
                body = {
                    "baseline_revision_id": "a" * 64,
                    "counterfactual_revision_id": "b" * 64,
                    "status": "complete",
                    "elapsed_ms": 42,
                    "deltas": {"A": delta, "B": delta},
                    "reason": None,
                }
            else:
                await route.abort()
                return
            await route.fulfill(json=body, headers=headers)

        await page.route("**/sybil/**", respond_available)
        await page.goto(BASE + "/sybil")
        await page.get_by_label("Connection pattern").select_option(label="Dense cluster")
        await page.get_by_role("button", name="Create revision").click()
        await page.get_by_role("heading", name="Revision editor").wait_for()
        await page.get_by_role("button", name="Preview score delta").click()
        await page.get_by_text("Counterfactual: complete in 42 ms", exact=True).wait_for()
        await page.get_by_role("button", name="Create immutable revision").click()
        await page.get_by_role("button", name="Undo").click()
        await page.get_by_text("Revision: aaaaaaaaaaaa", exact=True).wait_for()
        async with page.expect_download() as download_info:
            await page.get_by_role("button", name="Export score CSV").click()
        assert (await download_info.value).suggested_filename.endswith("-scores.csv")
        assert not errors, errors
        await browser.close()
    print("Sybil readiness: unavailable, responsive, editing, deltas, history and export passed.")


if __name__ == "__main__":
    asyncio.run(main())
