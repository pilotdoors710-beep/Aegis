"""Shader and glass browser checks. Use an existing Python Playwright environment.

Start the web app, then set LANDING_WEB_URL (default http://localhost:3100).
Only schema-built preset fixtures are used; no live runs or LLM calls.
"""
import os
import sys
import base64
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'server'))
from aegis.presets import PRESETS
from aegis.events import sample_run

BASE = os.environ.get('LANDING_WEB_URL', 'http://localhost:3100')
OUTPUT = Path(__file__).resolve().parents[1] / 'build/dithering-verification'
PROBE = """() => {
  window.dither = { draws: 0, uniforms: {} };
  const draw = WebGLRenderingContext.prototype.drawArrays;
  WebGLRenderingContext.prototype.drawArrays = function(...args) {
    if (this.canvas.matches('.dithering-background')) {
      window.dither.draws++; window.dither.gl = this; window.dither.args = args;
    }
    return draw.apply(this, args);
  };
  for (const name of ['uniform3fv','uniform4fv','uniform4f']) {
    const original = WebGLRenderingContext.prototype[name];
    WebGLRenderingContext.prototype[name] = function(location, ...values) {
      const result = original.call(this, location, ...values);
      if (this.canvas.matches('.dithering-background')) {
        const program = this.getParameter(this.CURRENT_PROGRAM);
        for (let i = 0; i < this.getProgramParameter(program, this.ACTIVE_UNIFORMS); i++) {
          const info = this.getActiveUniform(program, i);
          // Locations are opaque objects; getUniform records the authoritative value.
          window.dither.uniforms[info.name] = Array.from(this.getUniform(program, this.getUniformLocation(program, info.name)));
        }
      }
      return result;
    };
  }
}"""


def prepare(page):
    page.route('**/presets', lambda route: route.fulfill(
        json=[preset.model_dump(mode='json') for preset in PRESETS],
        headers={'access-control-allow-origin': '*'}))
    page.add_init_script('(' + PROBE + ')()')
    summary, events = sample_run()
    pending = next(i for i, event in enumerate(events) if event.kind == 'ask' and event.payload.status == 'pending')
    stream = 'event: run\ndata: ' + summary.model_dump_json() + '\n\n'
    for i, event in enumerate(events[:pending + 1]):
        stream += f'id: {i}\nevent: {event.kind}\ndata: {json.dumps(event.model_dump(mode="json"))}\n\n'
    page.route('**/runs/sample/stream', lambda route: route.fulfill(
        body=stream, content_type='text/event-stream', headers={'access-control-allow-origin': '*'}))


def run():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel=os.environ.get('BROWSER_CHANNEL', 'chrome'))
        context = browser.new_context(viewport={'width': 1280, 'height': 720})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        prepare(page)
        page.goto(BASE + '/console')
        page.locator('.dithering-background[data-ready]').wait_for()
        page.locator('.featured-run').wait_for()
        page.wait_for_timeout(300)
        count = page.evaluate('dither.draws')
        page.wait_for_timeout(300)
        assert page.evaluate('dither.draws') == count
        assert page.evaluate('dither.uniforms.u_scene[2]') == 0
        assert page.locator('.dithering-background').evaluate('e=>getComputedStyle(e).filter') == 'blur(14px)'
        assert page.evaluate('dither.args') == [4, 0, 3]
        assert page.evaluate('dither.gl.getError()') == 0
        uniforms = page.evaluate('dither.uniforms')
        for name, expected in {
            'u_shape': [2.14, .45, .55, .2], 'u_surface': [3.55, 1, 0, 1],
            'u_finish': [0, 0, 0, .13], 'u_transform': [1, 2.58, 0, 0],
            'u_space': [0, 0, 0, 0], 'u_cursor': [0, 2, .65, .46],
        }.items():
            assert all(abs(a - b) < .00001 for a, b in zip(uniforms[name], expected)), name
        assert uniforms['u_scene'][:2] == [1280, 720]
        for i, color in enumerate([[0, .071, .098], [0, .373, .451], [.580, .824, .741], [.914, .847, .651]]):
            actual = page.evaluate('(i)=>Array.from(dither.gl.getUniform(dither.gl.getParameter(dither.gl.CURRENT_PROGRAM), dither.gl.getUniformLocation(dither.gl.getParameter(dither.gl.CURRENT_PROGRAM), `u_colors[${i}]`)))', i)
            assert all(abs(a - b) < .00001 for a, b in zip(actual, color))
        assert page.locator('[data-refraction="active"] canvas').count() > 0
        page.screenshot(path=str(OUTPUT / 'desktop.png'))

        page.evaluate("Object.defineProperty(document, 'hidden', {configurable:true,get:()=>true}); document.dispatchEvent(new Event('visibilitychange'))")
        count = page.evaluate('dither.draws')
        page.wait_for_timeout(200)
        assert page.evaluate('dither.draws') == count
        page.evaluate("Object.defineProperty(document, 'hidden', {configurable:true,get:()=>false}); document.dispatchEvent(new Event('visibilitychange'))")
        page.wait_for_function(f'dither.draws > {count}')

        page.emulate_media(reduced_motion='reduce')
        page.wait_for_function('matchMedia("(prefers-reduced-motion: reduce)").matches')
        page.wait_for_timeout(600)
        count = page.evaluate('dither.draws')
        page.mouse.move(400, 300)
        page.wait_for_timeout(150)
        assert page.evaluate('dither.draws') == count
        assert page.evaluate('dither.uniforms.u_cursor[0]') == 0
        box = page.locator('.featured-run').bounding_box()
        crop = {'x': box['x'] + 14, 'y': box['y'] + 14, 'width': box['width'] - 28, 'height': box['height'] - 28}
        hidden = page.add_style_tag(content='.featured-text,.featured-actions {visibility:hidden}')
        on = page.screenshot(clip=crop)
        surface = page.locator('.featured-run > [data-glass-mount] > [data-glass-layer] > span').first
        surface.evaluate('e=>e.style.filter="none"')
        off = page.screenshot(clip=crop)
        surface.evaluate('e=>e.style.removeProperty("filter")')
        hidden.evaluate('e=>e.remove()')
        result = page.evaluate("""async ([a,b])=>{
          const load=async src=>{let img=new Image();img.src=src;await img.decode();let c=document.createElement('canvas');c.width=img.width;c.height=img.height;let ctx=c.getContext('2d');ctx.drawImage(img,0,0);return ctx.getImageData(0,0,c.width,c.height).data};
          const x=await load(a),y=await load(b);
          const lum=v=>v.reduce((s,c,i)=>s+[.2126,.7152,.0722][i]*(c/255<=.04045?c/255/12.92:((c/255+.055)/1.055)**2.4),0);
          let difference=0,max=0;
          for(let i=0;i<x.length;i+=4){difference+=Math.abs(x[i]-y[i])+Math.abs(x[i+1]-y[i+1])+Math.abs(x[i+2]-y[i+2]);max=Math.max(max,lum([x[i],x[i+1],x[i+2]]))}
          return {difference:difference/(x.length/4*3),contrast:(lum([224,228,235])+.05)/(max+.05)};
        }""", ['data:image/png;base64,' + base64.b64encode(png).decode() for png in [on, off]])
        print('Sampled glass optics and metadata contrast:', result, flush=True)
        assert result['difference'] > .15
        assert result['contrast'] >= 4.5
        page.emulate_media(contrast='more')
        page.wait_for_timeout(100)
        assert not page.locator('.console-sky').is_visible()
        count = page.evaluate('dither.draws')
        page.wait_for_timeout(150)
        assert page.evaluate('dither.draws') == count
        page.emulate_media(contrast='no-preference')
        page.locator('.dithering-background[data-ready]').wait_for()
        page.evaluate("dither.loss = dither.gl.getExtension('WEBGL_lose_context'); dither.loss.loseContext()")
        page.wait_for_function('!document.querySelector(".dithering-background").dataset.ready')
        # Let Chromium finish dispatching the loss event before requesting recovery.
        page.wait_for_timeout(300)
        page.evaluate("dither.loss.restoreContext()")
        page.locator('.dithering-background[data-ready]').wait_for()
        assert page.evaluate('dither.gl.getError()') == 0

        page.set_viewport_size({'width': 390, 'height': 844})
        page.wait_for_timeout(200)
        assert page.locator('.dithering-background').evaluate('e=>e.width') == 390
        assert page.evaluate('document.documentElement.scrollWidth') == 390
        page.screenshot(path=str(OUTPUT / 'mobile.png'))
        page.get_by_role('button', name='Play sample run').click()
        page.locator('dialog[open]').wait_for()
        page.wait_for_timeout(300)
        assert page.locator('dialog [data-refraction="active"] canvas').count() > 0
        assert page.get_by_role('button', name='Approve', exact=True).is_disabled()
        page.screenshot(path=str(OUTPUT / 'sample-approval.png'))
        # Release the held fixture dialog before checking client-side navigation.
        page.locator('dialog[open]').evaluate('e=>e.close()')
        page.get_by_role('button', name='Open menu', exact=True).click()
        page.get_by_role('link', name='Scan', exact=True).click()
        page.wait_for_url(BASE + '/scan')
        count = page.evaluate('dither.draws')
        page.wait_for_timeout(200)
        assert page.evaluate('dither.draws') == count
        assert page.locator('.dithering-background').count() == 0
        assert page.locator('[data-refraction="active"]').count() == 0
        assert not errors, errors
        context.close()

        context = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=3, reduced_motion='reduce')
        page = context.new_page()
        prepare(page)
        page.goto(BASE + '/console')
        page.locator('.dithering-background[data-ready]').wait_for()
        assert page.locator('.dithering-background').evaluate('e=>[e.width,e.height]') == [780, 1688]
        context.close()

        context = browser.new_context(reduced_motion='reduce')
        page = context.new_page()
        prepare(page)
        page.add_init_script("const get = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function(kind,...args) {return kind==='webgl' ? null : get.call(this,kind,...args)}")
        page.goto(BASE + '/console')
        page.get_by_role('button', name='Launch live run', exact=False).first.wait_for()
        assert page.locator('.dithering-background[data-ready]').count() == 0
        assert page.locator('.console-sky').evaluate('e=>getComputedStyle(e).backgroundImage') != 'none'
        context.close()
        browser.close()
    print('Shader uniforms, static frame, blur, glass copies, visibility pause, reduced motion, context restore, mobile, DPR, route cleanup and no-WebGL fallback passed.')


if __name__ == '__main__':
    run()
