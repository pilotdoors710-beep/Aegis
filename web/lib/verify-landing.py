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
        # A fresh browser also isolates history and GPU state between scenarios.
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
        self.page.wait_for_selector('main[data-phase="ready"]')

    def enter(self):
        # The full viewport button sits behind the selectable copy.
        self.page.get_by_role("button", name="Enter Aegis console").focus()
        self.page.keyboard.press("Enter")
        self.page.wait_for_url("**/console")
        self.page.wait_for_function("document.activeElement.id === 'console-heading'")

    def test_01_motion_and_focus(self):
        self.visit()
        self.ready()
        self.assertEqual(self.page.locator("[data-artwork]").get_attribute("data-artwork"), "pixels")
        self.page.screenshot(path=str(OUTPUT / "desktop.png"))
        self.assertEqual(self.page.evaluate("window.__pendingFrames.size"), 0)
        self.assertEqual(self.page.get_by_role("link", name="Skip intro").count(), 0)
        self.assertEqual(self.page.get_by_role("link", name="Enter console").count(), 0)
        self.enter()
        self.assertEqual(self.page.evaluate("document.activeElement.id"), "console-heading")
        self.assertIsNone(self.page.evaluate("sessionStorage.getItem('aegis:intro-seen:v1')"))
        self.assertEqual(self.page.evaluate("window.__pendingFrames.size"), 0)

    def test_02_refresh_and_revisit_preserves_landing(self):
        self.visit("")
        self.ready()
        self.page.reload()
        self.ready()
        self.assertTrue(self.page.get_by_role("button", name="Enter Aegis console").is_visible())
        self.assertEqual(self.page.get_by_role("link", name="Skip intro").count(), 0)
        self.assertEqual(self.page.get_by_role("link", name="Enter console").count(), 0)
        self.enter()
        self.assertTrue(self.page.url.endswith("/console"))
        self.visit("")
        self.ready()
        self.assertTrue(self.page.get_by_role("button", name="Enter Aegis console").is_visible())
        self.page.reload()
        self.ready()
        self.assertTrue(self.page.get_by_role("button", name="Enter Aegis console").is_visible())

    def test_03_early_and_duplicate_input(self):
        self.visit()
        self.page.get_by_role("button", name="Enter Aegis console").evaluate("""button => {
          button.click(); button.click(); button.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',repeat:true,bubbles:true}));
        }""")
        self.page.wait_for_url("**/console")
        self.assertEqual(self.page.locator("#console-heading").count(), 1)

    def test_04_keyboard_space(self):
        self.visit()
        self.ready()
        self.page.get_by_role("button", name="Enter Aegis console").focus()
        self.page.keyboard.press("Space")
        self.page.wait_for_url("**/console")

    def test_05_reduced_motion_and_change(self):
        self.page.emulate_media(reduced_motion="reduce")
        self.visit()
        self.ready()
        self.assertEqual(self.page.locator("[data-artwork]").get_attribute("data-artwork"), "poster")
        self.assertEqual(self.page.evaluate("window.__pendingFrames.size"), 0)
        self.enter()
        self.page.emulate_media(reduced_motion="no-preference")
        self.visit()
        self.ready()
        self.page.get_by_role("button", name="Enter Aegis console").evaluate("el=>el.click()")
        self.page.emulate_media(reduced_motion="reduce")
        self.page.wait_for_url("**/console")

    def test_06_webgl_and_context_loss(self):
        self.context.add_init_script("""const get=HTMLCanvasElement.prototype.getContext;
          HTMLCanvasElement.prototype.getContext=function(type,...args){return type==='webgl2'?null:get.call(this,type,...args)};""")
        self.visit()
        self.ready()
        self.assertEqual(self.page.locator("[data-artwork]").get_attribute("data-artwork"), "poster")
        self.enter()

    def test_07_missing_assets_and_storage(self):
        self.context.add_init_script("""Object.defineProperty(window,'sessionStorage',{get(){throw new Error('Storage disabled')}});""")
        self.page.route("**/landing/*.png", lambda route: route.abort())
        self.visit()
        self.ready()
        self.assertTrue(self.page.get_by_role("heading", level=1).is_visible())
        self.enter()

    def test_08_context_loss_during_exit(self):
        self.visit()
        self.ready()
        self.page.get_by_role("button", name="Enter Aegis console").evaluate("el=>el.click()")
        self.page.locator("[data-artwork] canvas").evaluate("""el=>el.getContext('webgl2').getExtension('WEBGL_lose_context').loseContext()""")
        self.page.wait_for_url("**/console")

    def test_09_no_javascript(self):
        with self.browser.new_context(java_script_enabled=False) as context:
            page = context.new_page()
            page.goto(BASE)
            self.assertTrue(page.get_by_alt_text("Dithered Aegis shield with a Medusa relief.").is_visible())
            self.assertEqual(page.get_by_role("link", name="Skip intro").count(), 0)
            self.assertEqual(page.get_by_role("link", name="Enter console").count(), 0)
            page.get_by_role("link", name="Open console").click()
            self.assertTrue(page.url.endswith("/console"))

    def test_10_viewports_resize_and_zoom(self):
        self.visit()
        self.ready()
        for width, height in [(360,640),(390,844),(768,1024),(1280,720),(1920,1080)]:
            self.page.set_viewport_size({"width":width,"height":height})
            self.page.wait_for_timeout(100)
            self.page.screenshot(path=str(OUTPUT / f"viewport-{width}.png"))
            self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"), width)
            self.assertEqual(self.page.get_by_role("link", name="Skip intro").count(), 0)
            self.assertEqual(self.page.get_by_role("link", name="Enter console").count(), 0)
            btn = self.page.get_by_role("button", name="Enter Aegis console")
            self.assertTrue(btn.is_visible())
        self.page.set_viewport_size({"width":1280,"height":720})
        self.page.evaluate("document.documentElement.style.zoom='2'")
        self.page.screenshot(path=str(OUTPUT / "zoom-200.png"), full_page=True)
        self.assertLessEqual(self.page.evaluate("document.documentElement.scrollWidth"),1280)
        self.enter()

    def test_11_selectable_copy(self):
        self.visit()
        self.ready()
        self.page.locator("h1").evaluate("""el=>{const range=document.createRange();range.selectNodeContents(el);const s=getSelection();s.removeAllRanges();s.addRange(range);el.click()}""")
        self.assertEqual(self.page.locator("main").get_attribute("data-phase"),"ready")

    def test_12_deep_links(self):
        for path in ["/console","/runs","/runs/sample?replay=1","/stats","/health","/arena/index.html?traps=none"]:
            self.page.goto(BASE+path)
            self.assertEqual(self.page.locator("button[aria-label='Enter Aegis console']").count(),0)

    def test_13_record_and_profile(self):
        with self.browser.new_context(viewport={"width":1280,"height":720},record_video_dir=str(OUTPUT)) as context:
            page = context.new_page()
            cdp = context.new_cdp_session(page)
            cdp.send("Performance.enable")
            trace = []
            cdp.on("Tracing.dataCollected", lambda event: trace.extend(event["value"]))
            cdp.send("Tracing.start", {"categories":"devtools.timeline,blink.user_timing,gpu","transferMode":"ReportEvents"})
            page.goto(BASE+"/?intro=play")
            page.wait_for_selector('main[data-phase="ready"]')
            gpu = page.locator("[data-artwork] canvas").evaluate("""el=>{const gl=el.getContext('webgl2'),ext=gl.getExtension('WEBGL_debug_renderer_info');return ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER)}""")
            page.evaluate("""window.__frameTimes=[];window.__last=performance.now();window.__record=true;
              const record=t=>{window.__frameTimes.push(t-window.__last);window.__last=t;if(window.__record)requestAnimationFrame(record)};requestAnimationFrame(record);""")
            page.get_by_role("button",name="Enter Aegis console").evaluate("el=>el.click()")
            page.wait_for_selector('main[data-phase="tunnel"]')
            page.wait_for_timeout(420)
            page.screenshot(path=str(OUTPUT / "tunnel.png"))
            # Preserve samples before the component unmounts (shared root layout).
            page.wait_for_url("**/console")
            samples = page.evaluate("window.__record=false;window.__frameTimes")
            (OUTPUT/"profile.json").write_text(json.dumps({"browser":self.browser.version,"gpu":gpu,"frame_intervals_ms":samples,"over_33_ms":sum(t>33 for t in samples),"cdp_metrics":cdp.send("Performance.getMetrics")},indent=2))
            cdp.send("Tracing.end")
            page.wait_for_timeout(500)
            (OUTPUT/"trace.json").write_text(json.dumps({"traceEvents":trace}))
            page.wait_for_timeout(250)

    def test_14_hidden_tab_resumes_active_time(self):
        self.context.add_init_script("""window.__testHidden=false;
          Object.defineProperty(document,'hidden',{get:()=>window.__testHidden,configurable:true});""")
        self.visit()
        self.page.wait_for_selector('main[data-phase="assembling"]')
        self.page.evaluate("window.__testHidden=true;document.dispatchEvent(new Event('visibilitychange'))")
        self.page.wait_for_timeout(1350)
        self.assertEqual(self.page.locator("main").get_attribute("data-phase"), "assembling")
        self.assertEqual(self.page.evaluate("window.__pendingFrames.size"),0)
        self.page.evaluate("window.__testHidden=false;document.dispatchEvent(new Event('visibilitychange'))")
        self.ready()
        self.enter()

    def test_15_touch_and_recovery_link(self):
        with self.browser.new_context(has_touch=True,viewport={"width":390,"height":844}) as context:
            page = context.new_page()
            page.goto(BASE+"/?intro=play")
            page.wait_for_selector('main[data-phase="ready"]')
            page.touchscreen.tap(15,400)
            page.wait_for_url("**/console")
        self.page.emulate_media(reduced_motion="reduce")
        self.page.add_init_script("""const originalFetch=window.fetch.bind(window);
          window.fetch=(input,options)=>{
            const url=new URL(typeof input==='string'?input:(input instanceof URL?input.href:input.url),location.href);
            return url.pathname==='/console'?new Promise(()=>{}):originalFetch(input,options);
          };""")
        self.visit()
        self.ready()
        self.page.get_by_role("button",name="Enter Aegis console").evaluate("el=>el.click()")
        self.page.wait_for_selector('main[data-phase="entering"]',state="attached")
        recovery = self.page.get_by_role("link",name="Open console")
        recovery.wait_for()
        self.assertEqual(recovery.get_attribute("href"),"/console")
        self.assertEqual(recovery.evaluate("el=>{let opacity=1;while(el){opacity*=Number(getComputedStyle(el).opacity);el=el.parentElement;}return opacity}"),1)

    def test_16_console_launch_approval_sample_and_replay(self):
        # Reuse the server's schema-built fixtures; never maintain another contract.
        sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"server"))
        from aegis.events import sample_run
        from aegis.presets import PRESETS

        summary_model, event_models = sample_run()
        summary = summary_model.model_dump(mode="json")
        events = [event.model_dump(mode="json") for event in event_models]
        preset = next(p for p in PRESETS if p.id == "clean").model_dump(mode="json")
        cors = {"access-control-allow-origin":"*"}
        self.page.route("**/presets", lambda route: route.fulfill(json=[preset],headers=cors))
        pending = next(e for e in events if e["kind"] == "ask" and e["payload"]["status"] == "pending")
        mock_id = "landing-verification"
        live = {**summary,"run_id":mock_id,"is_sample":False,"outcomes":{},"status":"running"}
        ask = {**pending,"run_id":mock_id}
        # A controllable stream keeps the action pending while testing the real dialog.
        stream_script = """(data=>{window.EventSource=class extends EventTarget {
          constructor(url){super();this.closed=false;const sample=url.includes('/sample/');
            setTimeout(()=>{if(this.closed)return;const summary=sample?data.summary:data.live;
              this.dispatchEvent(new MessageEvent('run',{data:JSON.stringify(summary)}));
              this.dispatchEvent(new MessageEvent('ask',{data:JSON.stringify(sample?data.pending:data.ask)}));},100);}
          close(){this.closed=true;}
        }})(__DATA__);"""
        self.page.add_init_script(stream_script.replace("__DATA__",json.dumps({"summary":summary,"live":live,"pending":pending,"ask":ask})))

        def create(route):
            if route.request.method == "OPTIONS":
                route.fulfill(headers={"access-control-allow-origin":"*","access-control-allow-methods":"POST","access-control-allow-headers":"content-type"})
                return
            self.assertEqual(route.request.post_data_json,{"preset_id":"clean"})
            self.mocked_posts.append(route.request.url)
            route.fulfill(json={"run_id":mock_id,"status":"running","queue_position":0},headers=cors)

        def approve(route):
            if route.request.method == "OPTIONS":
                route.fulfill(headers={"access-control-allow-origin":"*","access-control-allow-methods":"POST","access-control-allow-headers":"content-type"})
                return
            self.assertEqual(route.request.post_data_json,{"decision":"approve"})
            self.mocked_posts.append(route.request.url)
            route.fulfill(json={**ask["payload"],"status":"approved"},headers=cors)

        self.page.route("**/runs",create)
        self.page.route("**/runs/landing-verification/ask/*",approve)
        self.page.goto(BASE+"/console")
        self.page.get_by_role("button",name="Launch live run").click()
        self.page.wait_for_url("**/runs/landing-verification?queue=0")
        self.page.get_by_role("dialog").wait_for()
        self.page.get_by_role("button",name="Approve",exact=True).click()
        self.page.wait_for_function("!document.querySelector('dialog[open]')")
        self.assertEqual(len(self.posts),2)
        self.page.goto(BASE+"/console")
        self.page.get_by_role("button",name="Play sample run").click()
        self.page.get_by_role("dialog").wait_for()
        self.assertTrue(self.page.get_by_role("button",name="Approve",exact=True).is_disabled())
        self.assertTrue(self.page.get_by_text("SAMPLE APPROVAL",exact=True).is_visible())
        self.assertEqual(len(self.posts),2)
        self.page.route("**/runs/sample",lambda route: route.fulfill(json=summary,headers=cors))
        self.page.route("**/runs/sample/events",lambda route: route.fulfill(json=events,headers=cors))
        self.page.goto(BASE+"/runs/sample?replay=1")
        next_step=self.page.get_by_role("button",name="Next",exact=True)
        next_step.wait_for()
        self.page.wait_for_function("!document.querySelector('.replay-controls button:last-child').disabled")
        next_step.click()
        self.assertTrue(self.page.get_by_role("button",name="Previous").is_enabled())
        self.assertEqual(self.page.get_by_role("dialog").count(),0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
