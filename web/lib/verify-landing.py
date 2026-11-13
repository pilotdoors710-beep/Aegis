"""Production entrance checks using the existing server Playwright environment.

Start `corepack pnpm start --port 3100` in web/, then run this with the
server's Python. Artifacts go in ignored .next/landing-verification/.
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
        # Fresh browser context isolates history and GPU state between scenarios.
        self.browser = self.pw.chromium.launch(channel="chrome")
        self.context = self.browser.new_context(viewport={"width": 1280, "height": 720})
        self.context.add_init_script("""window.__pendingFrames = new Set();
          const raf = window.requestAnimationFrame.bind(window), caf = window.cancelAnimationFrame.bind(window);
          window.requestAnimationFrame = fn => { let id = raf(t => { window.__pendingFrames.delete(id); fn(t); }); window.__pendingFrames.add(id); return id; };
          window.cancelAnimationFrame = id => { window.__pendingFrames.delete(id); caf(id); };
          window.__longFrames = [];
          if (PerformanceObserver.supportedEntryTypes.includes('long-animation-frame'))
            new PerformanceObserver(l => window.__longFrames.push(...l.getEntries().map(e => ({start:e.startTime,duration:e.duration}))))
              .observe({type:'long-animation-frame',buffered:true});
        """)
        self.page = self.context.new_page()
        self.errors, self.posts, self.mocked_posts = [], [], []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.on("request", lambda request: self.posts.append(request.url) if request.method == "POST" else None)

    def tearDown(self):
        self.page.unroute_all(behavior="wait")
        self.browser.close()
        self.assertEqual(self.errors, [])
        self.assertEqual(self.posts, self.mocked_posts, "Every POST must be intercepted by the test")

    def visit(self, query="?intro=play"):
        self.page.goto(BASE + "/" + query)

    def ready(self):
        self.page.wait_for_selector('main[data-phase="ready"]', timeout=10000)

    def enter(self):
        # Keyboard completion on the slider commits the entrance.
        slider = self.page.get_by_role("slider")
        slider.focus()
        self.page.keyboard.press("End")
        self.page.wait_for_url("**/console", timeout=12000)
        self.page.wait_for_function("document.activeElement.id === 'console-heading'")

    def drag_slider_commit(self):
        thumb = self.page.locator("[class*='sliderThumb']")
        thumb.scroll_into_view_if_needed()
        box = thumb.bounding_box()
        self.assertIsNotNone(box)
        # Drag right by 260px (>= 90% of travel)
        self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        self.page.mouse.down()
        self.page.mouse.move(box["x"] + box["width"] / 2 + 260, box["y"] + box["height"] / 2, steps=10)
        self.page.mouse.up()

    def test_01_hero_and_typography(self):
        self.page.mouse.move(10, 10)
        self.visit()
        self.ready()
        self.page.screenshot(path=str(OUTPUT / "desktop.png"))
        self.assertEqual(self.page.evaluate("window.__pendingFrames.size"), 0)

        # 1. Exact h1 title
        h1 = self.page.locator("h1")
        self.assertEqual(h1.count(), 1)
        self.assertEqual(h1.inner_text(), "AEGIS")

        # 2. Quote and orange rule
        self.assertIn("COMMIT BEFORE CODE", self.page.locator("main").inner_text())
        self.assertTrue(self.page.locator("[class*='orangeRule']").is_visible())

        # 3. Verbatim description
        self.assertIn(
            "A runtime shield between autonomous agents and the live web—stopping deception before it becomes a commitment.",
            self.page.locator("main").inner_text(),
        )

        # 4. Visible slider label and slider control
        self.assertIn("SLIDE TO ENTER", self.page.locator("main").inner_text())
        slider = self.page.get_by_role("slider")
        self.assertTrue(slider.is_visible())
        self.assertEqual(slider.get_attribute("aria-label"), "Slide to enter Aegis console")

        # In-viewport composition: no page scroll
        self.assertEqual(self.page.evaluate("window.scrollY"), 0)

        # Enter console via keyboard completion
        self.enter()
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "console-heading")
        self.assertIsNone(self.page.evaluate("sessionStorage.getItem('aegis:intro-seen:v1')"))
        self.page.wait_for_function("window.__pendingFrames.size === 0")
        self.assertEqual(self.page.evaluate("window.__pendingFrames.size"), 0)

    def test_02_refresh_and_revisit_preserves_landing(self):
        self.visit("")
        self.ready()
        self.assertEqual(self.page.locator("h1").inner_text(), "AEGIS")
        self.assertTrue(self.page.get_by_role("slider").is_visible())
        self.page.reload()
        self.ready()
        self.assertEqual(self.page.locator("h1").inner_text(), "AEGIS")
        self.assertTrue(self.page.get_by_role("slider").is_visible())
        self.enter()
        self.assertTrue(self.page.url.endswith("/console"))
        # Reloading while on /console redirects to landing page
        self.page.reload()
        self.ready()
        self.assertEqual(self.page.locator("h1").inner_text(), "AEGIS")
        self.assertTrue(self.page.get_by_role("slider").is_visible())
        self.assertTrue(self.page.url.endswith("/") or self.page.url.rstrip("/").endswith(":3100"))
        self.enter()
        self.assertTrue(self.page.url.endswith("/console"))
        self.visit("")
        self.ready()
        self.assertEqual(self.page.locator("h1").inner_text(), "AEGIS")
        self.assertTrue(self.page.get_by_role("slider").is_visible())
        self.page.reload()
        self.ready()
        self.assertTrue(self.page.get_by_role("slider").is_visible())

    def test_03_entrance_order_and_progressive_dimming(self):
        self.visit()
        # Stage 1: Title begins immediately, slider is disabled
        self.page.wait_for_selector('main[data-stage="title"]')
        self.assertEqual(self.page.locator("h1").inner_text(), "AEGIS")
        slider = self.page.locator("[role='slider']")
        self.assertEqual(slider.get_attribute("aria-disabled"), "true")

        # Stage 2: Quote arrives at 700ms+
        self.page.wait_for_selector('main[data-stage="quote"]')
        self.assertIn("COMMIT BEFORE CODE", self.page.locator("main").inner_text())
        self.assertEqual(slider.get_attribute("aria-disabled"), "true")

        # Stage 3: Description arrives at 1300ms+
        self.page.wait_for_selector('main[data-stage="description"]')
        self.assertIn("A runtime shield", self.page.locator("main").inner_text())

        # Stage 4: Control reveal at 2050ms+
        self.ready()
        self.assertEqual(self.page.locator("main").get_attribute("data-stage"), "ready")
        self.assertEqual(slider.get_attribute("aria-disabled"), "false")
        self.assertIn("SLIDE TO ENTER", self.page.locator("main").inner_text())

        # In-viewport verification: entire composition stays inside viewport
        self.assertEqual(self.page.evaluate("window.scrollY"), 0)
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), 1280)

    def test_04_drag_interactions_incomplete_and_complete(self):
        self.visit()
        self.ready()
        thumb = self.page.locator("[class*='sliderThumb']")
        thumb.scroll_into_view_if_needed()
        box = thumb.bounding_box()
        self.assertIsNotNone(box)
        # Incomplete drag: drag right 40px (< 90%), release mouse
        self.page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        self.page.mouse.down()
        self.page.mouse.move(box["x"] + box["width"] / 2 + 40, box["y"] + box["height"] / 2, steps=5)
        self.page.mouse.up()
        self.page.wait_for_timeout(300)
        # Thumb snaps back to start (aria-valuenow is 0, phase is still ready)
        self.assertEqual(self.page.locator("[role='slider']").get_attribute("aria-valuenow"), "0")
        self.assertEqual(self.page.locator("main").get_attribute("data-phase"), "ready")
        self.assertTrue(not self.page.url.endswith("/console"))
        # Completed drag: drag right 260px (>= 90%)
        self.drag_slider_commit()
        # Slider commits, phase changes to exiting
        self.assertEqual(self.page.locator("main").get_attribute("data-phase"), "exiting")
        self.page.wait_for_url("**/console", timeout=12000)

    def test_05_touch_cancellation(self):
        self.visit()
        self.ready()
        thumb = self.page.locator("[class*='sliderThumb']")
        thumb.scroll_into_view_if_needed()
        box = thumb.bounding_box()
        # Dispatch pointerdown, move, then pointercancel
        thumb.dispatch_event("pointerdown", {"pointerId": 1, "clientX": box["x"] + 10, "clientY": box["y"] + 10, "button": 0})
        thumb.dispatch_event("pointermove", {"pointerId": 1, "clientX": box["x"] + 80, "clientY": box["y"] + 10})
        thumb.dispatch_event("pointercancel", {"pointerId": 1})
        self.assertEqual(self.page.locator("[role='slider']").get_attribute("aria-valuenow"), "0")
        self.assertEqual(self.page.locator("main").get_attribute("data-phase"), "ready")

    def test_06_keyboard_navigation(self):
        self.visit()
        self.ready()
        slider = self.page.get_by_role("slider")
        slider.focus()
        # ArrowRight advances thumb
        self.page.keyboard.press("ArrowRight")
        val = int(slider.get_attribute("aria-valuenow") or "0")
        self.assertGreater(val, 0)
        # End key completes
        self.page.keyboard.press("End")
        self.page.wait_for_url("**/console", timeout=12000)

    def test_07_repeated_and_early_input(self):
        self.visit()
        self.ready()
        # Repeated triggers commit only once
        slider = self.page.get_by_role("slider")
        slider.evaluate("""el => {
          el.dispatchEvent(new KeyboardEvent('keydown', { key: 'End', repeat: true, bubbles: true }));
          el.dispatchEvent(new KeyboardEvent('keydown', { key: 'End', repeat: true, bubbles: true }));
        }""")
        self.page.wait_for_url("**/console", timeout=12000)
        self.assertEqual(self.page.locator("#console-heading").count(), 1)

    def test_08_no_full_page_click_target(self):
        self.visit()
        self.ready()
        # Clicking title does NOT enter console
        self.page.locator("h1").click()
        self.assertEqual(self.page.locator("main").get_attribute("data-phase"), "ready")
        # Clicking background does NOT enter console
        self.page.mouse.click(50, 50)
        self.assertEqual(self.page.locator("main").get_attribute("data-phase"), "ready")
        # Clicking slider track outside thumb does NOT enter console
        track = self.page.locator("[class*='sliderTrack']")
        box = track.bounding_box()
        self.page.mouse.click(box["x"] + box["width"] - 20, box["y"] + box["height"] / 2)
        self.assertEqual(self.page.locator("main").get_attribute("data-phase"), "ready")
        self.assertFalse(self.page.url.endswith("/console"))

    def test_09_reduced_motion(self):
        self.page.emulate_media(reduced_motion="reduce")
        self.visit()
        self.ready()
        self.assertEqual(self.page.locator("h1").inner_text(), "AEGIS")
        self.assertTrue(self.page.get_by_role("slider").is_visible())
        self.assertEqual(self.page.evaluate("window.__pendingFrames.size"), 0)
        self.assertEqual(self.page.evaluate("window.scrollY"), 0)
        self.enter()

    def test_10_webgl_failure(self):
        self.context.add_init_script("""const get=HTMLCanvasElement.prototype.getContext;
          HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:get.call(this,type,...args)};""")
        self.visit()
        self.ready()
        self.assertEqual(self.page.locator("h1").inner_text(), "AEGIS")
        self.assertTrue(self.page.get_by_role("slider").is_visible())
        self.enter()

    def test_11_context_loss_during_exit(self):
        self.visit()
        self.ready()
        self.page.get_by_role("slider").focus()
        self.page.keyboard.press("End")
        tunnel = self.page.locator("[class*='tunnel'] canvas")
        if tunnel.count() > 0:
            tunnel.evaluate("""el=>el.getContext('webgl2')?.getExtension('WEBGL_lose_context')?.loseContext()""")
        self.page.wait_for_url("**/console", timeout=12000)

    def test_12_no_javascript(self):
        with self.browser.new_context(java_script_enabled=False) as context:
            page = context.new_page()
            page.goto(BASE)
            # Renders all hero copy
            self.assertEqual(page.locator("h1").inner_text(), "AEGIS")
            self.assertIn("COMMIT BEFORE CODE", page.locator("main").inner_text())
            self.assertIn("A runtime shield between autonomous agents", page.locator("main").inner_text())
            # Renders visible "Open console" link
            link = page.get_by_role("link", name="Open console")
            self.assertTrue(link.is_visible())
            link.click()
            self.assertTrue(page.url.endswith("/console"))

    def test_13_viewports_centering_and_overflow(self):
        self.visit()
        self.ready()
        # Test desktop, tablet, mobile, short-height, and 200% zoom viewports
        scenarios = [
            ("desktop", 1280, 720),
            ("tablet", 768, 1024),
            ("mobile", 360, 640),
            ("short-laptop", 1366, 600),
            ("short-height", 1024, 500),
            ("zoom-200", 640, 360),
            ("large", 1920, 1080),
        ]
        for name, width, height in scenarios:
            self.page.set_viewport_size({"width": width, "height": height})
            self.page.wait_for_timeout(100)
            self.page.screenshot(path=str(OUTPUT / f"{name}.png"))
            # No horizontal overflow
            self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
            # Slider visible
            slider = self.page.get_by_role("slider")
            self.assertTrue(slider.is_visible())
            # Centered slider track
            box = self.page.locator("[class*='sliderTrack']").bounding_box()
            self.assertIsNotNone(box)
            track_center = box["x"] + box["width"] / 2
            self.assertAlmostEqual(track_center, width / 2, delta=4)
            # Centered title
            h1_box = self.page.locator("h1").bounding_box()
            self.assertIsNotNone(h1_box)
            h1_center = h1_box["x"] + h1_box["width"] / 2
            self.assertAlmostEqual(h1_center, width / 2, delta=4)

        self.enter()

    def test_14_record_profile_and_exit_transition(self):
        with self.browser.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(OUTPUT)) as context:
            page = context.new_page()
            cdp = context.new_cdp_session(page)
            cdp.send("Performance.enable")
            trace = []
            cdp.on("Tracing.dataCollected", lambda event: trace.extend(event["value"]))
            cdp.send("Tracing.start", {"categories": "devtools.timeline,blink.user_timing,gpu", "transferMode": "ReportEvents"})
            page.goto(BASE + "/?intro=play")
            page.wait_for_selector('main[data-phase="ready"]', timeout=10000)
            gpu = page.evaluate("""() => {
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl2');
                if (!gl) return 'no-webgl2';
                const ext = gl.getExtension('WEBGL_debug_renderer_info');
                return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER);
            }""")
            page.evaluate("""window.__frameTimes=[];window.__last=performance.now();window.__record=true;
              const record=t=>{window.__frameTimes.push(t-window.__last);window.__last=t;if(window.__record)requestAnimationFrame(record)};requestAnimationFrame(record);""")
            # Commit slider
            slider = page.get_by_role("slider")
            slider.focus()
            page.keyboard.press("End")
            page.wait_for_selector('main[data-phase="exiting"]')
            # During overlap (t = 500ms into exiting), tunnel frames are active
            page.wait_for_timeout(500)
            page.screenshot(path=str(OUTPUT / "exit-transition.png"))
            page.wait_for_url("**/console", timeout=12000)
            samples = page.evaluate("window.__record=false;window.__frameTimes")
            (OUTPUT / "profile.json").write_text(json.dumps({"browser": self.browser.version, "gpu": gpu, "frame_intervals_ms": samples, "over_33_ms": sum(t > 33 for t in samples), "cdp_metrics": cdp.send("Performance.getMetrics")}, indent=2))
            cdp.send("Tracing.end")
            page.wait_for_timeout(500)
            (OUTPUT / "trace.json").write_text(json.dumps({"traceEvents": trace}))
            page.wait_for_timeout(250)

    def test_15_slow_route_recovery_link(self):
        # Simulate route slow navigation
        self.page.add_init_script("""const originalFetch=window.fetch.bind(window);
          window.fetch=(input,options)=>{
            const url=new URL(typeof input==='string'?input:(input instanceof URL?input.href:input.url),location.href);
            return url.pathname==='/console'?new Promise(()=>{}):originalFetch(input,options);
          };""")
        self.visit()
        self.ready()
        self.page.get_by_role("slider").focus()
        self.page.keyboard.press("End")
        # Recovery control appears after 2s if route hasn't loaded
        recovery = self.page.get_by_role("link", name="Open console")
        recovery.wait_for(timeout=8000)
        self.assertEqual(recovery.get_attribute("href"), "/console")
        self.assertEqual(recovery.locator("svg").count(), 1)

    def test_16_deep_links(self):
        for path in ["/console", "/runs", "/runs/sample?replay=1", "/stats", "/health", "/arena/index.html?traps=none"]:
            self.page.goto(BASE + path)
            self.assertEqual(self.page.locator("[role='slider']").count(), 0)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
