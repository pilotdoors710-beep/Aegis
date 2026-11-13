import { context, resize } from "./gl";
import type { particles } from "./pixels";

export function artworkRenderer(canvas: HTMLCanvasElement, pixels: ReturnType<typeof particles>) {
  const gpu = context(canvas), { gl } = gpu;
  try {
    const program = gpu.program(`#version 300 es
      precision highp float;
      layout(location=0) in vec2 quad;
      layout(location=1) in vec2 target;
      layout(location=2) in vec2 scatter;
      layout(location=3) in vec3 color;
      layout(location=4) in float delay;
      uniform float progress; uniform float cell;
      out vec3 tone; out float alpha;
      void main() {
        float p=clamp((progress-delay)/.78,0.,1.);
        float eased=1.-pow(1.-p,3.);
        vec2 pos=mix(scatter,target,eased)+quad*cell;
        gl_Position=vec4(pos*1.84,0.,1.);
        tone=color; alpha=1.;
      }`, `#version 300 es
      precision highp float; in vec3 tone; in float alpha; out vec4 result;
      void main(){ result=vec4(tone,alpha); }`);
    gpu.vao();
    gpu.buffer(new Float32Array([-.5,-.5,.5,-.5,-.5,.5,.5,.5]));
    gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
    gpu.buffer(pixels.data);
    for (const [index, size, offset] of [[1, 2, 0], [2, 2, 2], [3, 3, 4], [4, 1, 7]]) {
      gl.enableVertexAttribArray(index); gl.vertexAttribPointer(index, size, gl.FLOAT, false, 32, offset * 4); gl.vertexAttribDivisor(index, 1);
    }
    gl.useProgram(program);
    const progress = gl.getUniformLocation(program, "progress");
    gl.uniform1f(gl.getUniformLocation(program, "cell"), pixels.cell);
    return {
      draw(value: number) {
        resize(canvas); gl.viewport(0, 0, canvas.width, canvas.height);
        gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
        gl.uniform1f(progress, value); gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, pixels.count);
      },
      dispose: gpu.dispose,
    };
  } catch (error) { gpu.dispose(); throw error; }
}
