/** Track every allocation, including partial setup failures. */
export function context(canvas: HTMLCanvasElement) {
  const gl = canvas.getContext("webgl2", { alpha: true, antialias: false, powerPreference: "low-power" });
  if (!gl) throw new Error("WebGL2 unavailable");
  const cleanup: (() => void)[] = [];
  let disposed = false;
  return {
    gl,
    dispose() {
      if (disposed) return;
      disposed = true;
      cleanup.reverse().forEach((fn) => fn());
      // Return the canvas context's backing storage too, especially on mobile.
      if (!gl.isContextLost()) gl.getExtension("WEBGL_lose_context")?.loseContext();
    },
    program(vertex: string, fragment: string) {
      const shaders = [[gl.VERTEX_SHADER, vertex], [gl.FRAGMENT_SHADER, fragment]].map(([type, source]) => {
        const shader = gl.createShader(type as number)!;
        cleanup.push(() => gl.deleteShader(shader));
        gl.shaderSource(shader, source as string); gl.compileShader(shader);
        if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(shader) ?? "Shader failed");
        return shader;
      });
      const program = gl.createProgram()!;
      cleanup.push(() => gl.deleteProgram(program));
      shaders.forEach((shader) => gl.attachShader(program, shader)); gl.linkProgram(program);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error("Program failed");
      return program;
    },
    buffer(data: Float32Array) {
      const buffer = gl.createBuffer()!; cleanup.push(() => gl.deleteBuffer(buffer));
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer); gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
      return buffer;
    },
    vao() {
      const vao = gl.createVertexArray()!; cleanup.push(() => gl.deleteVertexArray(vao)); gl.bindVertexArray(vao); return vao;
    },
    texture() { const texture = gl.createTexture()!; cleanup.push(() => gl.deleteTexture(texture)); return texture; },
    framebuffer() { const fb = gl.createFramebuffer()!; cleanup.push(() => gl.deleteFramebuffer(fb)); return fb; },
    depth() { const depth = gl.createRenderbuffer()!; cleanup.push(() => gl.deleteRenderbuffer(depth)); return depth; },
  };
}

export function resize(canvas: HTMLCanvasElement, area = 3_000_000) {
  const { width, height } = canvas.getBoundingClientRect();
  const ratio = Math.min(devicePixelRatio || 1, 2, Math.sqrt(area / Math.max(1, width * height)));
  const w = Math.max(1, Math.round(width * ratio)), h = Math.max(1, Math.round(height * ratio));
  if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; return true; }
  return false;
}
