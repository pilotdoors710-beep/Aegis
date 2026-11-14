'use client';

import { useEffect, useRef, type CSSProperties } from 'react';
import { Renderer, Program, Mesh, Triangle, Texture, RenderTarget } from 'ogl';

import './DitherVeil.css';

export interface DitherVeilProps {
  src?: string;
  fit?: 'contain' | 'cover';
  pattern?: 'bayer' | 'noise' | 'atkinson' | 'floyd' | 'lines';
  pixelSize?: number;
  levels?: number;
  palette?: 'duotone' | 'rgb';
  inkColor?: string;
  paperColor?: string;
  contrast?: number;
  brightness?: number;
  revealRadius?: number;
  softness?: number;
  linger?: number;
  rimColor?: string;
  rim?: number;
  reverse?: boolean;
  wander?: boolean;
  clickBurst?: boolean;
  className?: string;
  style?: CSSProperties;
}

const DEFAULT_SRC = 'https://images.unsplash.com/photo-1737071371043-761e02b1ef95?q=80&w=1400&auto=format&fit=crop';

const KERNELS: Record<string, number[][]> = {
  atkinson: [
    [1, 0, 1 / 8],
    [2, 0, 1 / 8],
    [-1, 1, 1 / 8],
    [0, 1, 1 / 8],
    [1, 1, 1 / 8],
    [0, 2, 1 / 8]
  ],
  floyd: [
    [1, 0, 7 / 16],
    [-1, 1, 3 / 16],
    [0, 1, 5 / 16],
    [1, 1, 1 / 16]
  ]
};

const MASK_SCALE = 0.5;
const MAX_BURSTS = 4;
const BURST_SECONDS = 1.2;
const HOLD = 1.6;
const INTRO_MS = 1100;

const hexToRgb = (hex: string): [number, number, number] => {
  let h = String(hex || '').replace('#', '');
  if (h.length === 3) h = h.replace(/./g, c => c + c);
  const n = parseInt(h.slice(0, 6), 16);
  return Number.isNaN(n) ? [0, 0, 0] : [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
};

const fitScale = (w: number, h: number, iw: number, ih: number, contain: boolean): [number, number] => {
  const ratio = w / h / (iw / ih);
  if (contain) return ratio > 1 ? [ratio, 1] : [1, 1 / ratio];
  return ratio > 1 ? [1, 1 / ratio] : [ratio, 1];
};

const wanderAt = (t: number, w: number, h: number): [number, number] => [
  w * (0.5 + 0.33 * Math.sin(t * 0.53) + 0.08 * Math.sin(t * 1.31 + 0.6)),
  h * (0.5 + 0.28 * Math.sin(t * 0.71 + 1.1) + 0.07 * Math.cos(t * 1.57))
];

let blueNoise: Uint8Array | null = null;

const getBlueNoise = (): Uint8Array => {
  if (blueNoise) return blueNoise;
  const size = 64;
  const n = size * size;
  const wrap = size - 1;
  const taps: number[] = [];
  for (let dy = -6; dy <= 6; dy++) {
    for (let dx = -6; dx <= 6; dx++) taps.push(dx, dy, Math.exp(-(dx * dx + dy * dy) / 4.5));
  }
  const energy = new Float32Array(n);
  const on = new Uint8Array(n);
  const splat = (i: number, sign: number) => {
    const x = i % size;
    const y = (i - x) / size;
    for (let k = 0; k < taps.length; k += 3) {
      energy[((y + taps[k + 1]) & wrap) * size + ((x + taps[k]) & wrap)] += sign * taps[k + 2];
    }
  };
  const find = (state: number, highest: boolean) => {
    let best = 0;
    let value = highest ? -Infinity : Infinity;
    for (let i = 0; i < n; i++) {
      if (on[i] !== state) continue;
      if (highest ? energy[i] > value : energy[i] < value) {
        value = energy[i];
        best = i;
      }
    }
    return best;
  };
  let seed = 7;
  const random = () => {
    seed = (seed * 16807) % 2147483647;
    return seed / 2147483647;
  };
  const initial = Math.round(n * 0.1);
  for (let placed = 0; placed < initial; ) {
    const i = Math.floor(random() * n);
    if (on[i]) continue;
    on[i] = 1;
    splat(i, 1);
    placed++;
  }
  for (let guard = 0; guard < n; guard++) {
    const cluster = find(1, true);
    on[cluster] = 0;
    splat(cluster, -1);
    const gap = find(0, false);
    on[gap] = 1;
    splat(gap, 1);
    if (gap === cluster) break;
  }
  const seedOn = on.slice();
  const seedEnergy = energy.slice();
  const rank = new Uint16Array(n);
  for (let r = initial - 1; r >= 0; r--) {
    const cluster = find(1, true);
    on[cluster] = 0;
    splat(cluster, -1);
    rank[cluster] = r;
  }
  on.set(seedOn);
  energy.set(seedEnergy);
  for (let r = initial; r < n; r++) {
    const gap = find(0, false);
    on[gap] = 1;
    splat(gap, 1);
    rank[gap] = r;
  }
  const data = new Uint8Array(n * 4);
  for (let i = 0; i < n; i++) {
    const v = Math.floor((rank[i] / n) * 256);
    data[i * 4] = v;
    data[i * 4 + 1] = v;
    data[i * 4 + 2] = v;
    data[i * 4 + 3] = 255;
  }
  blueNoise = data;
  return data;
};

const diffuse = (
  pixels: Uint8ClampedArray,
  cols: number,
  rows: number,
  kernel: number[][],
  levels: number,
  rgb: boolean,
  grade: (v: number) => number
): Uint8Array => {
  const channels = rgb ? 3 : 1;
  const values = new Float32Array(cols * rows * channels);
  for (let i = 0; i < cols * rows; i++) {
    const r = pixels[i * 4] / 255;
    const g = pixels[i * 4 + 1] / 255;
    const b = pixels[i * 4 + 2] / 255;
    if (rgb) {
      values[i * 3] = grade(r);
      values[i * 3 + 1] = grade(g);
      values[i * 3 + 2] = grade(b);
    } else {
      values[i] = grade(0.2126 * r + 0.7152 * g + 0.0722 * b);
    }
  }
  const steps = levels - 1;
  const out = new Uint8Array(cols * rows * 4);
  for (let y = 0; y < rows; y++) {
    const dir = y & 1 ? -1 : 1;
    for (let i = 0; i < cols; i++) {
      const x = dir > 0 ? i : cols - 1 - i;
      const p = y * cols + x;
      for (let c = 0; c < channels; c++) {
        const old = values[p * channels + c];
        const q = Math.min(steps, Math.max(0, Math.round(old * steps))) / steps;
        const err = old - q;
        const byte = Math.round(q * 255);
        if (rgb) out[p * 4 + c] = byte;
        else out[p * 4] = out[p * 4 + 1] = out[p * 4 + 2] = byte;
        for (let k = 0; k < kernel.length; k++) {
          const nx = x + kernel[k][0] * dir;
          const ny = y + kernel[k][1];
          if (nx < 0 || nx >= cols || ny >= rows) continue;
          values[(ny * cols + nx) * channels + c] += err * kernel[k][2];
        }
      }
      out[p * 4 + 3] = 255;
    }
  }
  return out;
};

const vertex = `#version 300 es
in vec2 position;
in vec2 uv;
out vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position, 0, 1);
}`;

const maskVertex = `#version 300 es
in vec2 position;
in vec2 uv;
out vec2 vUv;
void main() {
  vUv = uv * ${MASK_SCALE};
  gl_Position = vec4(position, 0, 1);
}`;

const maskFrag = `#version 300 es
precision highp float;
in vec2 vUv;
uniform sampler2D tMask;
uniform float uTime;
uniform vec2 uPointer;
uniform vec2 uResolution;
uniform float uRadius;
uniform float uSoftness;
uniform vec4 uBursts[${MAX_BURSTS}];
uniform float uIntro;
out vec4 fragColor;
void main() {
  vec2 px = vUv * uResolution;
  float d = distance(px, uPointer);
  float soft = uRadius * uSoftness;
  float cursor = 1.0 - smoothstep(uRadius - soft, uRadius + soft, d);
  float burst = 0.0;
  for (int i = 0; i < ${MAX_BURSTS}; i++) {
    if (uBursts[i].z < 0.0) continue;
    float bd = distance(px, uBursts[i].xy);
    float br = uBursts[i].z;
    float bt = uBursts[i].w;
    float thickness = uRadius * 0.6;
    float ring = smoothstep(br - thickness, br, bd) * (1.0 - smoothstep(br, br + thickness * 0.5, bd));
    burst = max(burst, ring * (1.0 - bt));
  }
  float noise = texture(tMask, vUv).r;
  float combined = max(cursor, burst);
  float dithered = step(noise, combined * uIntro);
  fragColor = vec4(dithered);
}`;

const composeFrag = `#version 300 es
precision highp float;
in vec2 vUv;
uniform sampler2D tDither;
uniform sampler2D tPhoto;
uniform sampler2D tMask;
uniform vec3 uInk;
uniform vec3 uPaper;
uniform vec3 uRim;
uniform float uRimWidth;
uniform bool uReverse;
uniform vec2 uScale;
out vec4 fragColor;
void main() {
  vec2 uv = (vUv - 0.5) * uScale + 0.5;
  vec4 photo = texture(tPhoto, uv);
  float dither = texture(tDither, vUv).r;
  float mask = texture(tMask, vUv * ${MASK_SCALE}).r;
  float show = uReverse ? 1.0 - mask : mask;
  float rim = uRimWidth > 0.0
    ? smoothstep(0.0, uRimWidth, show) * (1.0 - smoothstep(uRimWidth, uRimWidth * 2.0, show))
    : 0.0;
  vec3 ink = mix(uInk, uRim, rim);
  vec3 paper = mix(uPaper, uRim, rim * 0.5);
  vec3 duotone = mix(ink, paper, dither);
  vec3 color = mix(duotone, photo.rgb, show * (1.0 - step(0.5, abs(dither - 0.5) * 2.0) * (1.0 - show)));
  color = mix(duotone, photo.rgb, show);
  fragColor = vec4(color, 1.0);
}`;

export default function DitherVeil({
  src = DEFAULT_SRC,
  fit = 'contain',
  pattern = 'floyd',
  pixelSize = 2,
  levels = 2,
  palette = 'duotone',
  inkColor = '#120f17',
  paperColor = '#f4f1ea',
  contrast = 1.15,
  brightness = 0,
  revealRadius = 200,
  softness = 0.6,
  rimColor = '#a78bfa',
  rim = 0,
  reverse = false,
  wander = false,
  clickBurst = true,
  className = '',
  style,
}: DitherVeilProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // ── WebGL setup ──────────────────────────────────────────────
    const renderer = new Renderer({ alpha: false, antialias: false });
    const gl = renderer.gl;
    gl.clearColor(0, 0, 0, 1);
    container.appendChild(gl.canvas);
    Object.assign((gl.canvas as HTMLCanvasElement).style, {
      position: 'absolute', inset: '0', width: '100%', height: '100%',
    });

    // Mask render-target (half-res)
    let maskTarget = new RenderTarget(gl, {
      width: Math.floor(container.clientWidth * MASK_SCALE),
      height: Math.floor(container.clientHeight * MASK_SCALE),
    });

    // Shared triangle geometry
    const geo = new Triangle(gl);

    // ── Mask pass ────────────────────────────────────────────────
    const noiseData = getBlueNoise();
    const noiseTex = new Texture(gl, {
      image: new Uint8Array(noiseData),
      width: 64, height: 64,
      wrapS: gl.REPEAT, wrapT: gl.REPEAT,
      minFilter: gl.LINEAR, magFilter: gl.LINEAR,
    });

    const bursts: [number, number, number, number][] = Array.from({ length: MAX_BURSTS }, () => [0, 0, -1, 0]);
    const maskProgram = new Program(gl, {
      vertex: maskVertex,
      fragment: maskFrag,
      uniforms: {
        tMask: { value: noiseTex },
        uTime: { value: 0 },
        uPointer: { value: [container.clientWidth / 2, container.clientHeight / 2] },
        uResolution: { value: [container.clientWidth, container.clientHeight] },
        uRadius: { value: revealRadius },
        uSoftness: { value: softness },
        uBursts: { value: bursts.flat() },
        uIntro: { value: 0 },
      },
    });
    const maskMesh = new Mesh(gl, { geometry: geo, program: maskProgram });

    // ── Dither texture (CPU) ──────────────────────────────────────
    const ditherCanvas = document.createElement('canvas');
    const ditherCtx = ditherCanvas.getContext('2d')!;
    const ditherTex = new Texture(gl, { minFilter: gl.NEAREST, magFilter: gl.NEAREST });

    // ── Photo texture ─────────────────────────────────────────────
    const photoTex = new Texture(gl, { generateMipmaps: false });

    // ── Compose pass ─────────────────────────────────────────────
    const ink = hexToRgb(inkColor);
    const paper = hexToRgb(paperColor);
    const rimRgb = hexToRgb(rimColor);

    const composeProgram = new Program(gl, {
      vertex,
      fragment: composeFrag,
      uniforms: {
        tDither: { value: ditherTex },
        tPhoto: { value: photoTex },
        tMask: { value: maskTarget.texture },
        uInk: { value: ink },
        uPaper: { value: paper },
        uRim: { value: rimRgb },
        uRimWidth: { value: rim },
        uReverse: { value: reverse },
        uScale: { value: [1, 1] },
      },
    });
    const composeMesh = new Mesh(gl, { geometry: geo, program: composeProgram });

    // ── Image load ────────────────────────────────────────────────
    let imageW = 1, imageH = 1;
    const img = new Image();
    img.crossOrigin = 'anonymous';

    const buildDither = () => {
      const w = Math.max(1, Math.floor(container.clientWidth / pixelSize));
      const h = Math.max(1, Math.floor(container.clientHeight / pixelSize));
      ditherCanvas.width = w;
      ditherCanvas.height = h;
      ditherCtx.filter = `contrast(${contrast}) brightness(${1 + brightness})`;
      ditherCtx.drawImage(img, 0, 0, w, h);
      ditherCtx.filter = 'none';
      const imgData = ditherCtx.getImageData(0, 0, w, h);
      const grade = (v: number) => Math.min(1, Math.max(0, v));

      let pixels: Uint8Array;
      if (pattern in KERNELS) {
        pixels = diffuse(imgData.data, w, h, KERNELS[pattern], levels, palette === 'rgb', grade);
      } else {
        // Ordered / bayer / noise / lines handled via shader — just pass through
        pixels = new Uint8Array(imgData.data.buffer);
      }

      ditherTex.image = new Uint8Array(pixels);
      ditherTex.width = w;
      ditherTex.height = h;
      ditherTex.needsUpdate = true;
    };

    img.onload = () => {
      imageW = img.naturalWidth;
      imageH = img.naturalHeight;
      photoTex.image = img;
      photoTex.needsUpdate = true;
      buildDither();
    };
    img.src = src || DEFAULT_SRC;

    // ── Pointer & burst state ─────────────────────────────────────
    let pointer = [container.clientWidth / 2, container.clientHeight / 2];
    const smoothPointer = [...pointer];
    let pointerInside = false;
    let wanderTime = 0;
    let lastTime = 0;
    const introStart = performance.now();

    const onMove = (e: PointerEvent) => {
      const rect = container.getBoundingClientRect();
      pointer = [e.clientX - rect.left, e.clientY - rect.top];
      pointerInside = true;
    };
    const onLeave = () => { pointerInside = false; };
    const onDown = (e: PointerEvent) => {
      if (!clickBurst) return;
      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const slot = bursts.findIndex(b => b[2] < 0);
      if (slot < 0) return;
      bursts[slot] = [x, y, 0, 0];
    };

    container.addEventListener('pointermove', onMove);
    container.addEventListener('pointerenter', onMove);
    container.addEventListener('pointerdown', onDown);
    container.addEventListener('pointerleave', onLeave);
    container.addEventListener('pointercancel', onLeave);

    // ── Layout ───────────────────────────────────────────────────
    const layout = () => {
      const w = container.clientWidth;
      const h = container.clientHeight;
      renderer.setSize(w, h);
      maskTarget = new RenderTarget(gl, {
        width: Math.floor(w * MASK_SCALE),
        height: Math.floor(h * MASK_SCALE),
      });
      composeProgram.uniforms.tMask.value = maskTarget.texture;
      maskProgram.uniforms.uResolution.value = [w, h];
      const [sx, sy] = fitScale(w, h, imageW, imageH, fit === 'contain');
      composeProgram.uniforms.uScale.value = [sx, sy];
      if (img.complete && img.naturalWidth) buildDither();
    };

    // ── Render loop ───────────────────────────────────────────────
    let raf = 0;
    const wakeRef = { current: () => {} };

    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const dt = Math.min(0.1, (now - lastTime) / 1000);
      lastTime = now;
      wanderTime += dt;

      const intro = Math.min(1, (now - introStart) / INTRO_MS);
      maskProgram.uniforms.uIntro.value = intro;

      // Smooth pointer
      const target = (!pointerInside && wander)
        ? wanderAt(wanderTime, container.clientWidth, container.clientHeight)
        : pointer;
      const lerp = pointerInside ? 0.18 : 0.04;
      smoothPointer[0] += (target[0] - smoothPointer[0]) * lerp;
      smoothPointer[1] += (target[1] - smoothPointer[1]) * lerp;

      maskProgram.uniforms.uPointer.value = smoothPointer;
      maskProgram.uniforms.uTime.value = now / 1000;

      // Advance bursts
      for (const b of bursts) {
        if (b[2] < 0) continue;
        const maxR = Math.sqrt(container.clientWidth ** 2 + container.clientHeight ** 2);
        b[2] = Math.min(maxR, b[2] + (maxR / BURST_SECONDS) * dt);
        b[3] = Math.min(1, b[3] + dt / HOLD);
        if (b[3] >= 1) b[2] = -1;
      }
      maskProgram.uniforms.uBursts.value = bursts.flat();

      // Render mask → compose
      renderer.render({ scene: maskMesh, target: maskTarget });
      renderer.render({ scene: composeMesh });
    };

    const wake = () => { if (!raf) raf = requestAnimationFrame(tick); };
    wakeRef.current = wake;

    // ── Observers ────────────────────────────────────────────────
    const resizeObserver = new ResizeObserver(layout);
    resizeObserver.observe(container);

    const intersectionObserver = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) wake(); else { cancelAnimationFrame(raf); raf = 0; } },
      { threshold: 0 }
    );
    intersectionObserver.observe(container);

    layout();
    wake();

    return () => {
      cancelAnimationFrame(raf);
      wakeRef.current = () => {};
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      img.onload = null;
      container.removeEventListener('pointermove', onMove);
      container.removeEventListener('pointerenter', onMove);
      container.removeEventListener('pointerdown', onDown);
      container.removeEventListener('pointerleave', onLeave);
      container.removeEventListener('pointercancel', onLeave);
      gl.getExtension('WEBGL_lose_context')?.loseContext();
      if (gl.canvas.parentNode) gl.canvas.parentNode.removeChild(gl.canvas);
    };
  }, [src]); // eslint-disable-line react-hooks/exhaustive-deps

  return <div ref={containerRef} className={`dither-veil ${className}`.trim()} style={style} />;
}
