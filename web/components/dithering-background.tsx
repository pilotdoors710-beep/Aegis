"use client";

import { useEffect, useRef } from "react";
import { ditheringFragmentShader } from "@/lib/dithering-shader";
import { publishDitheringScene } from "@/lib/dithering-scene";

const vertexShader = `attribute vec2 a_position;
void main() { gl_Position = vec4(a_position, 0.0, 1.0); }`;

export default function DitheringBackground() {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const gl = canvas.getContext("webgl", {
      alpha: false, antialias: false, depth: false, stencil: false,
      // The glass reads this same frame on scroll and for the static motion fallback.
      preserveDrawingBuffer: true,
    });
    if (!gl) return;
    const motion = matchMedia("(prefers-reduced-motion: reduce)");
    const opaque = matchMedia("(prefers-reduced-transparency: reduce), (prefers-contrast: more), (forced-colors: active)");
    let program: WebGLProgram | null = null;
    let buffer: WebGLBuffer | null = null;
    let shaders: WebGLShader[] = [];
    let scene: WebGLUniformLocation | null = null;
    let frame = 0, elapsed = 0, previous = 0;

    const pause = () => { cancelAnimationFrame(frame); frame = 0; previous = 0; };
    const dispose = () => {
      pause();
      delete canvas.dataset.ready;
      publishDitheringScene(null);
      gl.deleteBuffer(buffer); gl.deleteProgram(program);
      shaders.forEach(shader => gl.deleteShader(shader));
      buffer = null; program = null; shaders = [];
    };
    const initialize = () => {
      try {
        program = gl.createProgram();
        if (!program) throw new Error("WebGL program unavailable");
        for (const [type, source] of [[gl.VERTEX_SHADER, vertexShader], [gl.FRAGMENT_SHADER, ditheringFragmentShader]] as const) {
          const shader = gl.createShader(type);
          if (!shader) throw new Error("WebGL shader unavailable");
          shaders.push(shader);
          gl.shaderSource(shader, source); gl.compileShader(shader);
          if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error("Shader compilation failed");
          gl.attachShader(program, shader);
        }
        gl.linkProgram(program);
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error("Shader linking failed");
        gl.useProgram(program);
        buffer = gl.createBuffer();
        if (!buffer) throw new Error("WebGL buffer unavailable");
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
        const position = gl.getAttribLocation(program, "a_position");
        gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);
        gl.uniform3fv(gl.getUniformLocation(program, "u_colors[0]"), new Float32Array([
          0.000, 0.071, 0.098, 0.000, 0.373, 0.451,
          0.580, 0.824, 0.741, 0.914, 0.847, 0.651,
          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        ]));
        for (const [name, value] of Object.entries({
          u_shape: [2.14, 0.45, 0.55, 0.20],
          u_surface: [3.55, 1.00, 0.00, 1.00],
          u_finish: [0.00, 0.00, 0.000, 0.13],
          u_transform: [1.0, 2.58, 0.00, 0.0],
          u_space: [0.00, 0.00, 0.00, 0.00],
          u_cursor: [0.00, 2.0, 0.65, 0.46],
        })) gl.uniform4fv(gl.getUniformLocation(program, name), value);
        scene = gl.getUniformLocation(program, "u_scene");
      } catch {
        dispose();
      }
    };
    const render = (now: number) => {
      frame = 0;
      if (!program || gl.isContextLost() || document.hidden || opaque.matches) return;
      const dpr = Math.min(devicePixelRatio || 1, 2);
      const width = Math.max(1, Math.round(canvas.clientWidth * dpr));
      const height = Math.max(1, Math.round(canvas.clientHeight * dpr));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width; canvas.height = height;
        gl.viewport(0, 0, width, height);
      }
      if (previous && !motion.matches) elapsed += (now - previous) / 1000;
      previous = now;
      gl.uniform4f(scene, width, height, elapsed * 1.56, 4.0);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
      canvas.dataset.ready = "true";
      publishDitheringScene(canvas);
      if (!motion.matches) frame = requestAnimationFrame(render);
    };
    const resume = () => {
      pause();
      if (!document.hidden && !opaque.matches && program) frame = requestAnimationFrame(render);
    };
    const lost = (event: Event) => { event.preventDefault(); dispose(); };
    const restored = () => { initialize(); resume(); };
    canvas.addEventListener("webglcontextlost", lost);
    canvas.addEventListener("webglcontextrestored", restored);
    document.addEventListener("visibilitychange", resume);
    motion.addEventListener("change", resume); opaque.addEventListener("change", resume);
    window.addEventListener("resize", resume);
    const resize = new ResizeObserver(resume); resize.observe(canvas);
    initialize(); resume();
    return () => {
      resize.disconnect();
      canvas.removeEventListener("webglcontextlost", lost);
      canvas.removeEventListener("webglcontextrestored", restored);
      document.removeEventListener("visibilitychange", resume);
      motion.removeEventListener("change", resume); opaque.removeEventListener("change", resume);
      window.removeEventListener("resize", resume);
      dispose();
    };
  }, []);
  return <canvas ref={ref} className="dithering-background" aria-hidden="true" />;
}
