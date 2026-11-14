"""Production entrance checks using the existing server Playwright environment.

Start `pnpm start --port 3100` in web/, then run this from server/ with
`uv run python ../web/lib/verify-landing.py`. Set BROWSER_CHANNEL=chrome to use
installed Chrome. Artifacts go in ignored .next/landing-verification/.
No LLM calls, real agent runs, or external API writes.
"""
import json
import os
import sys
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = os.environ.get("LANDING_WEB_URL", "http://localhost:3100")
OUTPUT = Path(__file__).resolve().parents[1] / ".next/landing-verification"


class LandingChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUTPUT.mkdir(parents=True, exist_ok=True)
        cls.pw = sync_playwright().start()

    @classmethod
    def tearDownClass(cls):
        cls.pw.stop()

    def setUp(self):
        # Fresh browser per scenario isolates history and GPU state.
        self.browser = self.pw.chromium.launch(channel=os.environ.get("BROWSER_CHANNEL"))
        self.context = self.browser.new_context(viewport={"width": 1280, "height": 720})
        self.page = self.context.new_page()
        self.errors, self.posts, self.mocked_posts = [], [], []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("request", lambda request: self.posts.append(request.url) if request.method == "POST" else None)

    def tearDown(self):
        self.page.unroute_all(behavior="wait")
        self.browser.close()
        self.assertEqual(self.errors, [])
        self.assertEqual(self.posts, self.mocked_posts, "Every POST must be intercepted by the test")

    def visit(self):
        self.page.goto(BASE + "/")
        self.hint().wait_for()
        # Hydrated once the effect has measured the wordmark; scrolls before that have no listener.
        self.page.wait_for_function("document.querySelector('main > div').style.getPropertyValue('--inset-x') !== ''")

    def hint(self):
        return self.page.locator("main a[href='/console']")

    def scroll_to(self, *fractions):
        # Programmatic scrolls drive the same scroll/settle handlers as a wheel, but headless wheel
        # input is too uneven to time; two frames between steps give each its own scroll event.
        self.page.evaluate("""async fs => { const max = document.querySelector('main').offsetHeight - innerHeight;
          for (const f of fs) { scrollTo(0, f * max); await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); } }""", list(fractions))

    def at_console(self, timeout=8000):
        self.page.wait_for_url("**/console", timeout=timeout)
        self.page.locator(".app-theme").wait_for()

    def test_01_wordmark_and_hint(self):
        self.visit()
        self.assertTrue(self.page.get_by_role("img", name="AEGIS").is_visible())
        self.assertEqual(self.hint().inner_text().strip(), "Scroll to enter")
        self.assertEqual(self.page.title(), "Aegis")
        self.assertEqual(self.page.evaluate("scrollY"), 0)
        self.page.screenshot(path=str(OUTPUT / "hero.png"))

    def test_02_refresh_keeps_landing(self):
        self.visit()
        self.page.reload()
        self.hint().wait_for()
        self.assertTrue(self.page.url.rstrip("/").endswith(BASE.split("//")[1]) or self.page.url == BASE + "/")
        self.assertEqual(self.page.evaluate("scrollY"), 0)

    def test_03_scroll_past_commit_finishes_into_console(self):
        self.visit()
        self.scroll_to(0.1, 0.3)  # past COMMIT_AT (12%), then released
        self.at_console()
        self.page.screenshot(path=str(OUTPUT / "console-arrival.png"))

    def test_04_small_scroll_returns_to_top(self):
        self.visit()
        self.scroll_to(0.03, 0.06)  # below COMMIT_AT
        self.page.wait_for_function("scrollY === 0", timeout=4000)
        self.assertTrue(self.page.url.endswith("/"))

    def test_05_scrolling_back_up_cancels(self):
        self.visit()
        self.scroll_to(0.1, 0.3, 0.2)  # past the commit point, then back up
        self.page.wait_for_function("scrollY === 0", timeout=4000)
        self.page.wait_for_timeout(500)
        self.assertTrue(self.page.url.endswith("/"))

    def test_06_hint_click_and_keyboard(self):
        self.visit()
        self.hint().click()
        self.at_console()
        self.visit()
        self.page.keyboard.press("Tab")
        self.assertEqual(self.page.evaluate("document.activeElement.getAttribute('href')"), "/console")
        self.page.keyboard.press("Enter")
        self.at_console()

    def test_07_page_down_key(self):
        self.visit()
        self.page.keyboard.press("PageDown")
        self.at_console()

    def test_08_reduced_motion(self):
        self.page.emulate_media(reduced_motion="reduce")
        self.visit()
        self.page.get_by_role("link", name="Enter console").wait_for()  # label flips after hydration
        self.assertEqual(self.page.evaluate("document.documentElement.scrollHeight"), 720)
        self.hint().click()
        self.at_console(timeout=4000)

    def test_09_webgl_unavailable(self):
        self.page.add_init_script("""const get = HTMLCanvasElement.prototype.getContext;
          HTMLCanvasElement.prototype.getContext = function (kind, ...rest) {
            return String(kind).startsWith('webgl') || kind === 'experimental-webgl' ? null : get.call(this, kind, ...rest);
          };""")
        self.visit()
        self.assertTrue(self.page.get_by_role("img", name="AEGIS").is_visible())
        self.hint().click()
        self.at_console()

    def test_10_no_javascript(self):
        context = self.browser.new_context(java_script_enabled=False, viewport={"width": 1280, "height": 720})
        page = context.new_page()
        page.goto(BASE + "/")
        link = page.locator("main a[href='/console']")
        self.assertEqual(link.count(), 1)
        self.assertTrue(link.is_visible())
        context.close()

    def test_11_viewports_and_overflow(self):
        self.visit()
        for name, width, height in [("projector", 1280, 720), ("laptop", 1440, 900), ("tablet", 768, 1024),
                                    ("phone", 390, 844), ("short", 1280, 480), ("large", 1920, 1080)]:
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.wait_for_timeout(150)
            self.page.screenshot(path=str(OUTPUT / f"{name}.png"))
            self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
            for target in (self.page.get_by_role("img", name="AEGIS"), self.hint()):
                box = target.bounding_box()
                self.assertIsNotNone(box)
                self.assertGreaterEqual(box["x"], 0)
                self.assertLessEqual(box["x"] + box["width"], width + 1)
                self.assertLessEqual(box["y"] + box["height"], height + 1)
                self.assertAlmostEqual(box["x"] + box["width"] / 2, width / 2, delta=6)

    def test_12_deep_links_skip_entrance(self):
        for path in ["/console", "/runs", "/runs/sample?replay=1", "/lab", "/scan", "/stats", "/health"]:
            self.page.goto(BASE + path)
            self.page.locator(".app-theme").wait_for()
            self.assertEqual(self.page.get_by_role("img", name="AEGIS").count(), 0, path)
        self.page.goto(BASE + "/arena/index.html?traps=none")
        self.assertEqual(self.page.locator("main a[href='/console']").count(), 0)

    def test_13_frame_profile(self):
        self.visit()
        self.page.evaluate("""window.__frames=[];let last=performance.now();window.__rec=true;
          const tick=t=>{window.__frames.push(t-last);last=t;if(window.__rec)requestAnimationFrame(tick)};requestAnimationFrame(tick);""")
        self.page.wait_for_timeout(1500)
        self.scroll_to(0.1, 0.3)
        self.at_console()
        samples = self.page.evaluate("window.__frames || []")
        gpu = self.page.evaluate("""() => { const gl = document.createElement('canvas').getContext('webgl2');
          if (!gl) return 'no-webgl2'; const ext = gl.getExtension('WEBGL_debug_renderer_info');
          return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER); }""")
        # Informational only: headless GPU timing says little about the demo laptop.
        (OUTPUT / "profile.json").write_text(json.dumps({"browser": self.browser.version, "gpu": gpu, "landing_frame_intervals_ms": samples}, indent=2))

    def test_17_console_launch_approval_sample_and_replay(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
        from aegis.events import sample_run
        from aegis.presets import PRESETS

        summary_model, event_models = sample_run()
        summary = summary_model.model_dump(mode="json")
        events = [event.model_dump(mode="json") for event in event_models]
        preset = next(p for p in PRESETS if p.id == "clean").model_dump(mode="json")
        cors = {"access-control-allow-origin": "*"}
        self.page.route("**/presets", lambda route: route.fulfill(json=[preset], headers=cors))
        pending = next(e for e in events if e["kind"] == "ask" and e["payload"]["status"] == "pending")
        mock_id = "landing-verification"
        live = {**summary, "run_id": mock_id, "is_sample": False, "outcomes": {}, "status": "running"}
        ask = {**pending, "run_id": mock_id}

        stream_script = """(data=>{window.EventSource=class extends EventTarget {
          constructor(url){super();this.closed=false;const sample=url.includes('/sample/');
            setTimeout(()=>{if(this.closed)return;const summary=sample?data.summary:data.live;
              this.dispatchEvent(new MessageEvent('run',{data:JSON.stringify(summary)}));
              this.dispatchEvent(new MessageEvent('ask',{data:JSON.stringify(sample?data.pending:data.ask)}));},100);}
          close(){this.closed=true;}
        }})(__DATA__);"""
        self.page.add_init_script(stream_script.replace("__DATA__", json.dumps({"summary": summary, "live": live, "pending": pending, "ask": ask})))

        def create(route):
            if route.request.method == "OPTIONS":
                route.fulfill(headers={"access-control-allow-origin": "*", "access-control-allow-methods": "POST", "access-control-allow-headers": "content-type"})
                return
            self.assertEqual(route.request.post_data_json, {"preset_id": "clean"})
            self.mocked_posts.append(route.request.url)
            route.fulfill(json={"run_id": mock_id, "status": "running", "queue_position": 0}, headers=cors)

        def approve(route):
            if route.request.method == "OPTIONS":
                route.fulfill(headers={"access-control-allow-origin": "*", "access-control-allow-methods": "POST", "access-control-allow-headers": "content-type"})
                return
            self.assertEqual(route.request.post_data_json, {"decision": "approve"})
            self.mocked_posts.append(route.request.url)
            route.fulfill(json={**ask["payload"], "status": "approved"}, headers=cors)

        self.page.route("**/runs", create)
        self.page.route("**/runs/landing-verification/ask/*", approve)
        self.page.goto(BASE + "/console")
        self.page.get_by_role("button", name="Launch live run").click()
        self.page.wait_for_url("**/runs/landing-verification?queue=0")
        self.page.get_by_role("dialog").wait_for()
        self.page.get_by_role("button", name="Approve", exact=True).click()
        self.page.wait_for_function("!document.querySelector('dialog[open]')")
        self.assertEqual(len(self.posts), 2)
        self.page.goto(BASE + "/console")
        self.page.get_by_role("button", name="Play sample run").click()
        self.page.get_by_role("dialog").wait_for()
        self.assertTrue(self.page.get_by_role("button", name="Approve", exact=True).is_disabled())
        self.assertTrue(self.page.get_by_text("SAMPLE APPROVAL", exact=True).is_visible())
        self.assertEqual(len(self.posts), 2)
        self.page.route("**/runs/sample", lambda route: route.fulfill(json=summary, headers=cors))
        self.page.route("**/runs/sample/events", lambda route: route.fulfill(json=events, headers=cors))
        self.page.goto(BASE + "/runs/sample?replay=1")
        next_step = self.page.get_by_role("button", name="Next", exact=True)
        next_step.wait_for()
        self.page.wait_for_function("!document.querySelector('.replay-controls button:last-child').disabled")
        next_step.click()
        self.assertTrue(self.page.get_by_role("button", name="Previous").is_enabled())
        self.assertEqual(self.page.get_by_role("dialog").count(), 0)

    def test_18_own_key_launch_sends_llm_and_is_never_stored(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
        from aegis.presets import PRESETS

        cors = {"access-control-allow-origin": "*"}
        preset = next(p for p in PRESETS if p.id == "clean").model_dump(mode="json")
        self.page.route("**/presets", lambda route: route.fulfill(json=[preset], headers=cors))
        key = "sk-TEST-SENTINEL-123"
        bodies = []

        def create(route):
            if route.request.method == "OPTIONS":
                route.fulfill(headers={"access-control-allow-origin": "*", "access-control-allow-methods": "POST", "access-control-allow-headers": "content-type"})
                return
            bodies.append(route.request.post_data_json)
            self.mocked_posts.append(route.request.url)
            route.fulfill(status=503, json={"detail": "mocked: no run"}, headers=cors)

        self.page.route("**/runs", create)
        self.page.goto(BASE + "/console")
        self.page.get_by_text("Use your own API key").click()
        self.page.get_by_label("Provider").select_option("gemini")
        self.page.get_by_label("API key").fill(key)
        self.assertTrue(self.page.get_by_text("Your key · gemini:gemini-2.5-flash").is_visible())
        self.page.screenshot(path=str(OUTPUT / "own-key-panel.png"))
        self.page.get_by_role("button", name="Launch live run").click()
        self.page.get_by_text("mocked: no run").wait_for()
        self.assertEqual(bodies, [{"preset_id": "clean", "llm": {"provider": "gemini", "model": "gemini-2.5-flash", "api_key": key}}])
        storage = self.page.evaluate("JSON.stringify([{...localStorage}, {...sessionStorage}, document.cookie])")
        self.assertNotIn(key, storage)
        self.page.get_by_role("button", name="Clear").click()
        self.assertEqual(self.page.get_by_label("API key").input_value(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
