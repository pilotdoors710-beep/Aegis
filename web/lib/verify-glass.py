"""Glass app regression checks; uses schema-built fixtures, no live runs or LLM calls.
Start a production web server on port 3100. Run with the existing Python Playwright environment.
"""
import os
import sys
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'server'))
from aegis.events import sample_run, sample_eval_stats
from aegis.presets import PRESETS

BASE = os.environ.get('LANDING_WEB_URL', 'http://localhost:3100')
OUTPUT = Path(__file__).resolve().parents[1] / '.next/glass-verification'

class GlassChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(channel='chrome')
        OUTPUT.mkdir(parents=True, exist_ok=True)
        summary, events = sample_run()
        cls.summary = summary.model_dump(mode='json')
        cls.events = [e.model_dump(mode='json') for e in events]

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1280, 'height': 720})
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        cors = {'access-control-allow-origin': '*'}
        self.page.route('**/presets', lambda r: r.continue_() if r.request.url.startswith(BASE) else r.fulfill(json=[p.model_dump(mode='json') for p in PRESETS], headers=cors))
        self.page.route('**/runs/sample', lambda r: r.continue_() if r.request.url.startswith(BASE) else r.fulfill(json=self.summary, headers=cors))
        self.page.route('**/runs/sample/events', lambda r: r.continue_() if r.request.url.startswith(BASE) else r.fulfill(json=self.events, headers=cors))
        self.page.route('**/runs', lambda r: r.continue_() if r.request.url.startswith(BASE) else r.fulfill(json=[], headers=cors))
        self.page.route('**/stats', lambda r: r.continue_() if r.request.url.startswith(BASE) else r.fulfill(json=sample_eval_stats().model_dump(mode='json'), headers=cors))
        self.page.route('**/healthz/browser', lambda r: r.continue_() if r.request.url.startswith(BASE) else r.fulfill(status=503, json={'detail': 'Unavailable'}, headers=cors))

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def visit(self, path):
        self.page.goto(BASE + path)
        self.page.locator('.app-theme').wait_for()
        self.page.wait_for_timeout(200)

    def test_responsive_routes_and_current_navigation(self):
        for width, height in [(1280,720),(1440,900),(768,1024),(390,844)]:
            self.page.set_viewport_size({'width':width,'height':height})
            for route in ['/console','/runs','/lab','/stats','/health','/runs/sample?replay=1']:
                self.visit(route)
                self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'), width)
                active = self.page.locator('nav [aria-current="page"]')
                self.assertEqual(active.count(), 1)
                self.page.screenshot(path=str(OUTPUT / f'{width}-{route.split("?")[0].strip("/").replace("/","-")}.png'), full_page=True)

    def test_replay_geometry_and_safety_highlights(self):
        self.visit('/runs/sample?replay=1')
        slider = self.page.get_by_role('slider', name='Replay step')
        slider.wait_for()
        self.page.wait_for_function('!document.querySelector("#replay-step").disabled')
        slider.focus()
        self.page.keyboard.press('End')
        self.page.locator('.outcome-card').first.wait_for()
        panes = self.page.locator('.agent-pane').all()
        self.assertEqual(len(panes), 2)
        self.assertAlmostEqual(panes[0].bounding_box()['width'],panes[1].bounding_box()['width'],delta=1)
        self.assertTrue(self.page.get_by_label('Permission ledger').is_visible())
        self.assertEqual(self.page.locator('dialog[open]').count(),0)
        self.assertEqual(self.page.locator('.highlight-layer').count(),1)
        self.page.screenshot(path=str(OUTPUT / 'replay-outcomes.png'),full_page=True)

    def test_material_preferences_and_theme_isolation(self):
        self.visit('/console')
        self.page.emulate_media(reduced_motion='reduce', contrast='more')
        self.assertEqual(self.page.locator('.console-card').first.evaluate('e=>getComputedStyle(e).backdropFilter'), 'none')
        self.page.emulate_media(forced_colors='active')
        self.page.keyboard.press('Tab')
        self.assertTrue(self.page.locator(':focus-visible').count()>0)
        self.page.emulate_media(forced_colors='none', contrast='no-preference')
        self.page.goto(BASE + '/')
        self.assertEqual(self.page.locator('.app-theme').count(),0)
        self.page.goto(BASE + '/arena/index.html?traps=none')
        self.assertEqual(self.page.locator('.app-theme').count(),0)

    def test_zoom_and_opaque_fallback(self):
        self.visit('/lab')
        self.page.evaluate('document.documentElement.style.zoom="2"')
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),1280)
        # Disable backdrop support in the stylesheet to exercise its fallback branch.
        self.page.evaluate('''() => { for (const sheet of document.styleSheets) {
          try { const walk = rules => { for (const rule of rules) { if (rule.conditionText?.includes('backdrop-filter') && rule.conditionText.includes('not')) {
            const style=document.createElement('style'); style.textContent=Array.from(rule.cssRules,r=>r.cssText).join(''); document.head.append(style);
          } else if (rule.cssRules) walk(rule.cssRules); }}; walk(sheet.cssRules); } catch {} }}''')
        self.assertEqual(self.page.locator('.console-card').first.evaluate('e=>getComputedStyle(e).backgroundColor'),'rgb(25, 25, 25)')

if __name__ == '__main__':
    unittest.main(verbosity=2)
