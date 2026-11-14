"""Production app performance probe. Uses local fixtures, never live LLM calls.

LANDING_WEB_URL selects the production preview. Pass an output JSON path.
Use the same browser, hardware and viewport for before/after comparisons.
"""
import json
import os
from pathlib import Path
import runpy
import sys
from statistics import median

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
fixtures = runpy.run_path(str(HERE / 'verify-dithering.py'))
BASE = os.environ.get('LANDING_WEB_URL', 'http://localhost:3100')
PROBE = """() => {
  window.perf = {copies: 0, layouts: 0, longTasks: [], frames: []};
  const draw = CanvasRenderingContext2D.prototype.drawImage;
  CanvasRenderingContext2D.prototype.drawImage = function(...args) {
    if (this.canvas.closest('[data-glass-layer]')) perf.copies++;
    return draw.apply(this, args);
  };
  const rect = Element.prototype.getBoundingClientRect;
  Element.prototype.getBoundingClientRect = function(...args) {
    if (this.closest('[data-glass-layer]')) perf.layouts++;
    return rect.apply(this, args);
  };
  new PerformanceObserver(list => perf.longTasks.push(...list.getEntries().map(e => e.duration)))
    .observe({type: 'longtask', buffered: true});
}"""
SCROLL = """async () => {
  perf.copies = 0; perf.layouts = 0; perf.longTasks = []; perf.frames = [];
  const start = performance.now(); let previous = start;
  const max = document.documentElement.scrollHeight - innerHeight;
  await new Promise(resolve => {
    function frame(now) {
      perf.frames.push(now - previous); previous = now;
      const phase = Math.min(1, (now - start) / 4000);
      scrollTo(0, max * (1 - Math.cos(phase * Math.PI * 4)) / 2);
      if (phase < 1) requestAnimationFrame(frame); else resolve();
    }
    requestAnimationFrame(frame);
  });
  return {...perf, frames: undefined, frameCount: perf.frames.length,
    slowFrameRate: perf.frames.filter(t => t > 33.4).length / perf.frames.length,
    p95FrameMs: [...perf.frames].sort((a,b)=>a-b)[Math.floor(perf.frames.length * .95)]};
}"""


def main():
    results = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=os.environ.get('BROWSER_CHANNEL', 'chrome'))
        for name, viewport in [('desktop', {'width': 1280, 'height': 720}),
                               ('phone', {'width': 390, 'height': 844})]:
            context = browser.new_context(viewport=viewport)
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            fixtures['prepare'](page)
            page.add_init_script('(' + PROBE + ')()')
            page.goto(BASE + '/console')
            page.locator('.dithering-background[data-ready]').wait_for()
            page.locator('[data-refraction="active"] canvas').first.wait_for()
            page.wait_for_timeout(1200)
            cold = page.evaluate(SCROLL)
            samples = [page.evaluate(SCROLL) for _ in range(3)]
            results[name] = {key: median(sample[key] for sample in samples)
                             for key in ['copies', 'layouts', 'frameCount', 'slowFrameRate', 'p95FrameMs']}
            results[name]['longTaskMs'] = median(sum(sample['longTasks']) for sample in samples)
            results[name]['cold'] = cold
            results[name]['samples'] = samples
            page.wait_for_timeout(400)
            # Harmless layout notifications should not repaint unchanged glass.
            before = page.evaluate('perf.copies')
            page.evaluate("for(let i=0;i<10;i++) window.dispatchEvent(new Event('scroll'))")
            page.wait_for_timeout(150)
            results[name]['unchangedCopies'] = page.evaluate('perf.copies') - before
            results[name]['glassSurfaces'] = page.locator('[data-refraction="active"]').count()
            results[name]['errors'] = errors
            assert not errors, errors
            context.close()
        browser.close()
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parent / 'build/performance.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
