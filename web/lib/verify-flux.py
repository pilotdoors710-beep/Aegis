"""FluxLines landing regression checks. Start web on port 3100; no backend needed."""
import os
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = os.environ.get('LANDING_WEB_URL', 'http://localhost:3100')
OUT = Path(__file__).resolve().parents[1] / '.next/flux-verification'

class FluxChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        OUT.mkdir(parents=True, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.pw.stop()

    def setUp(self):
        self.browser = self.pw.chromium.launch(channel='chrome')
        self.context = self.browser.new_context(viewport={'width':1280,'height':720})
        self.context.add_init_script('''const draw=WebGL2RenderingContext.prototype.drawArrays;
          window.fluxDraws=0; WebGL2RenderingContext.prototype.drawArrays=function(...args){
            if(this.canvas.classList.contains('flux-lines-canvas')) window.fluxDraws++;
            return draw.apply(this,args); };''')
        self.page = self.context.new_page()
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))

    def tearDown(self):
        self.context.close()
        self.browser.close()
        self.assertEqual(self.errors, [])

    def ready(self):
        self.page.goto(BASE)
        try:
            self.page.wait_for_selector('main[data-phase="ready"]')
        except Exception:
            self.page.screenshot(path=str(OUT/'not-ready.png'))
            print(self.page.locator('main').get_attribute('data-phase'),self.page.url,self.errors)
            raise

    def enter(self):
        self.page.get_by_role('slider').focus()
        self.page.keyboard.press('End')
        self.page.wait_for_url('**/console',timeout=12000)
        self.page.locator('.flux-lines-canvas').wait_for(state='hidden')
        self.page.wait_for_timeout(300)
        draws=self.page.evaluate('window.fluxDraws')
        self.page.wait_for_timeout(200)
        self.assertEqual(self.page.evaluate('window.fluxDraws'),draws)

    def test_render_interaction_and_navigation(self):
        self.ready()
        canvas=self.page.locator('.flux-lines-canvas')
        self.assertTrue(canvas.is_visible())
        self.assertGreater(self.page.evaluate('window.fluxDraws'),0)
        before=self.page.evaluate('window.fluxDraws')
        self.page.mouse.move(700,350)
        self.page.mouse.click(700,350)
        self.page.wait_for_timeout(300)
        self.assertGreater(self.page.evaluate('window.fluxDraws'),before)
        self.assertEqual(self.page.locator('main').get_attribute('data-phase'),'ready')
        self.page.screenshot(path=str(OUT/'desktop.png'))
        self.page.set_viewport_size({'width':390,'height':844})
        self.page.wait_for_timeout(200)
        self.assertEqual(canvas.evaluate('e=>e.width'),585)
        self.assertLessEqual(self.page.evaluate('document.documentElement.scrollWidth'),390)
        self.page.screenshot(path=str(OUT/'mobile.png'))
        self.enter()

    def test_reduced_motion_changes_and_context_loss(self):
        self.ready()
        self.page.emulate_media(reduced_motion='reduce')
        self.page.wait_for_timeout(1200)
        before=self.page.evaluate('window.fluxDraws')
        self.page.wait_for_timeout(300)
        self.assertEqual(self.page.evaluate('window.fluxDraws'),before)
        self.page.emulate_media(reduced_motion='no-preference')
        self.page.wait_for_timeout(300)
        self.assertGreater(self.page.evaluate('window.fluxDraws'),before)
        self.page.locator('.flux-lines-canvas').evaluate("e=>{const gl=e.getContext('webgl2'); const ext=gl?.getExtension('WEBGL_lose_context'); if(ext) ext.loseContext(); else e.dispatchEvent(new Event('webglcontextlost'));}")
        self.page.wait_for_timeout(200)
        self.enter()

    def test_no_webgl_fallback(self):
        self.page.add_init_script("const get=HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext=function(type,...args){return type.includes('webgl')?null:get.call(this,type,...args)}")
        self.ready()
        self.assertTrue(self.page.get_by_role('heading',name='AEGIS').is_visible())
        self.enter()

if __name__ == '__main__':
    unittest.main(verbosity=2)
