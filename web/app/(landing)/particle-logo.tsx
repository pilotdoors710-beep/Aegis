"use client";

import { useEffect, useRef } from "react";

// Own take on a "particle image": particles live on the logo's opaque pixels; most breathe in
// place to hold the silhouette, a share swirl off on a flow field, fade and respawn at home.
// Each particle's position is a closed-form function of time in the vertex shader, so the CPU
// only sets uniforms per frame.
const COUNT = 150000;
const SIZE = 1.5; // CSS px
const LIFE = 3.2; // seconds, average
const WANDER = 0.35; // share of particles that swirl away from the shape
const CURSOR_R = 120; // CSS px
const COLORS = [[0.902, 0.863, 0.784], [0.761, 0.631, 0.353]]; // #e6dcc8 bone, #c2a15a gold

const VERT = `#version 300 es
in vec2 home; in float seed;
uniform vec2 res; uniform float size, time, intro, wander;
uniform vec2 pointer, pvel; uniform float radius;
out float alpha; out float tint;
float hash(float n) { return fract(sin(n) * 43758.5453); }
void main() {
  float life = ${LIFE.toFixed(2)} * (0.6 + 0.8 * hash(seed * 7.31));
  float cycle = time / life + seed;
  float age = fract(cycle), n = floor(cycle) + seed * 97.0;
  vec2 p = home + vec2(hash(n), hash(n + 1.7)) - 0.5;
  bool wanderer = hash(seed * 3.17) < wander;
  // Flow direction sampled where and when this life began, bending as it ages.
  float tb = (time - age * life) * 0.35;
  float a = (sin(p.x * 0.011 + tb) + sin(p.y * 0.013 - tb * 0.7) + sin((p.x + p.y) * 0.006 + tb * 0.4)) * 2.1
          + age * (hash(n + 3.1) - 0.5) * 5.0;
  float reach = wanderer ? 25.0 + 55.0 * hash(n + 5.3) : 1.5 + 2.0 * hash(n + 5.3);
  p += vec2(cos(a), sin(a)) * reach * age * age;
  // Cursor wake: nearby particles are dragged along the recent pointer motion, then ease home.
  p += pvel * smoothstep(radius, 0.0, distance(p, pointer));
  gl_Position = vec4(p.x / res.x * 2.0 - 1.0, 1.0 - p.y / res.y * 2.0, 0.0, 1.0);
  gl_PointSize = size;
  float shown = clamp((intro - hash(seed * 11.9)) * 8.0, 0.0, 1.0); // entrance: random pop-in order
  alpha = shown * min(1.0, age * 10.0) * (wanderer ? pow(1.0 - age, 1.5) * 0.7 : 0.9 - 0.3 * age);
  tint = pow(hash(seed * 5.71), 3.0);
}`;
const FRAG = `#version 300 es
precision mediump float;
in float alpha; in float tint;
uniform vec3 c0; uniform vec3 c1;
out vec4 o;
void main() {
  float d = length(gl_PointCoord - 0.5);
  o = vec4(mix(c0, c1, tint), alpha * smoothstep(0.5, 0.25, d));
}`;

export function ParticleLogo({ src, className }: { src: string; className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const gl = canvas?.getContext("webgl2", { premultipliedAlpha: false, antialias: false });
    if (!canvas || !gl) return; // decorative: no WebGL2, no particles

    const program = gl.createProgram()!;
    for (const [type, code] of [[gl.VERTEX_SHADER, VERT], [gl.FRAGMENT_SHADER, FRAG]] as const) {
      const shader = gl.createShader(type)!;
      gl.shaderSource(shader, code);
      gl.compileShader(shader);
      gl.attachShader(program, shader);
    }
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
    gl.useProgram(program);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE); // additive: overlapping particles build a bright core
    const u = (name: string) => gl.getUniformLocation(program, name);
    gl.uniform3fv(u("c0"), COLORS[0]);
    gl.uniform3fv(u("c1"), COLORS[1]);
    gl.uniform1f(u("wander"), WANDER);
    gl.uniform1f(u("radius"), CURSOR_R);

    const buffers: Record<string, WebGLBuffer> = {};
    const attrib = (data: Float32Array, name: string, size: number) => {
      buffers[name] ??= gl.createBuffer(); // reused on resize
      gl.bindBuffer(gl.ARRAY_BUFFER, buffers[name]);
      gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
      const loc = gl.getAttribLocation(program, name);
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0);
    };
    attrib(new Float32Array(COUNT).map(() => Math.random()), "seed", 1);

    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const img = new Image();
    let ready = false, raf = 0, t0 = 0, last = 0;
    const pointer = { x: -1e4, y: -1e4, vx: 0, vy: 0 };

    const draw = (time: number, intro: number) => {
      gl.uniform1f(u("time"), time);
      gl.uniform1f(u("intro"), intro);
      gl.uniform2f(u("pointer"), pointer.x, pointer.y);
      gl.uniform2f(u("pvel"), pointer.vx, pointer.vy);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.drawArrays(gl.POINTS, 0, COUNT);
    };

    // Sample the logo's alpha at canvas size (contain-fit); each particle gets a random opaque pixel as home.
    const layout = () => {
      const { width: w, height: h } = canvas.getBoundingClientRect();
      const dpr = Math.min(devicePixelRatio || 1, 2);
      canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
      gl.viewport(0, 0, canvas.width, canvas.height);
      gl.uniform2f(u("res"), w, h);
      gl.uniform1f(u("size"), SIZE * dpr);
      if (!img.naturalWidth || !w || !h) return;
      const scale = Math.min(w / img.naturalWidth, h / img.naturalHeight) * 0.9;
      const iw = Math.round(img.naturalWidth * scale), ih = Math.round(img.naturalHeight * scale);
      const probe = document.createElement("canvas");
      probe.width = iw; probe.height = ih;
      const ctx = probe.getContext("2d", { willReadFrequently: true })!;
      ctx.drawImage(img, 0, 0, iw, ih);
      const px = ctx.getImageData(0, 0, iw, ih).data;
      const ox = (w - iw) / 2, oy = (h - ih) / 2, pts: number[] = [];
      for (let y = 0; y < ih; y++) for (let x = 0; x < iw; x++) if (px[(y * iw + x) * 4 + 3] > 128) pts.push(ox + x + 0.5, oy + y + 0.5);
      if (!pts.length) return;
      const homes = new Float32Array(COUNT * 2);
      for (let i = 0; i < COUNT; i++) {
        const k = ((Math.random() * pts.length) / 2) | 0;
        homes[i * 2] = pts[k * 2]; homes[i * 2 + 1] = pts[k * 2 + 1];
      }
      attrib(homes, "home", 2);
      ready = true;
      if (reduced) draw(0, 1); // one still frame
    };

    const step = (now: number) => {
      raf = requestAnimationFrame(step);
      if (!ready) return;
      t0 ||= now;
      const dt = Math.min(3, last ? (now - last) / 16.667 : 1);
      last = now;
      pointer.vx *= 0.9 ** dt; pointer.vy *= 0.9 ** dt; // the wake eases home once the mouse stops
      const s = (now - t0) / 1000;
      draw(s, Math.min(1, Math.max(0, (s - 0.8) / 1.6))); // condenses ~0.8–2.4 s, after the wordmark lands
    };

    // Window-level: the wordmark's canvas covers the stage and would swallow events on this element.
    const onMove = (e: PointerEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = e.clientX - rect.left, y = e.clientY - rect.top;
      if (pointer.x > -1e3) {
        pointer.vx += (x - pointer.x) * 0.5; pointer.vy += (y - pointer.y) * 0.5;
        const len = Math.hypot(pointer.vx, pointer.vy), max = 90; // cap the wake so a flick can't fling the shape away
        if (len > max) { pointer.vx *= max / len; pointer.vy *= max / len; }
      }
      pointer.x = x; pointer.y = y;
    };

    img.onload = layout;
    img.src = src;
    const observer = new ResizeObserver(layout);
    observer.observe(canvas);
    if (!reduced) {
      window.addEventListener("pointermove", onMove, { passive: true });
      raf = requestAnimationFrame(step);
    }
    return () => {
      cancelAnimationFrame(raf);
      observer.disconnect();
      window.removeEventListener("pointermove", onMove);
      img.onload = null; // no loseContext(): StrictMode remounts reuse this same context
    };
  }, [src]);

  return <canvas ref={ref} className={className} aria-hidden="true" />;
}
