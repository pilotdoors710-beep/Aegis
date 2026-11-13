import { context, resize } from "./gl";
import { randomSource } from "./pixels";

/** Four continuous bars, including front/back and inner/outer walls. */
function mesh(mobile: boolean) {
  const data: number[] = [], random = randomSource(1908);
  const count = mobile ? 9 : 14;
  const half = (mobile ? 90 : 120) * 1.6;
  const inner = half - 12;
  for (let frame = 0; frame < count; frame++) {
    const angles = [(random() - .5) * 1.05, (random() - .5) * 1.05, (random() - .5) * 1.92];
    const center = [(random() - .5) * 65, (random() - .5) * 65, -900 - frame * (4300 / (count - 1))];
    const rotate = (input: number[]) => {
      let [x, y, z] = input;
      const [a, b, c] = angles;
      [y, z] = [y * Math.cos(a) - z * Math.sin(a), y * Math.sin(a) + z * Math.cos(a)];
      [x, z] = [x * Math.cos(b) + z * Math.sin(b), -x * Math.sin(b) + z * Math.cos(b)];
      return [x * Math.cos(c) - y * Math.sin(c), x * Math.sin(c) + y * Math.cos(c), z];
    };
    const quad = (points: number[][], normal: number[]) => {
      const n = rotate(normal);
      for (const index of [0, 1, 2, 0, 2, 3]) {
        const p = rotate(points[index]);
        data.push(...p.map((v, i) => v + center[i]), ...n, frame);
      }
    };
    const outer = [[-half,-half], [half,-half], [half,half], [-half,half]];
    const inside = [[-inner,-inner], [inner,-inner], [inner,inner], [-inner,inner]];
    for (let side = 0; side < 4; side++) {
      const next = (side + 1) % 4, a = outer[side], b = outer[next], c = inside[next], d = inside[side];
      const n = [Math.sign(a[1] - b[1]), Math.sign(b[0] - a[0]), 0];
      quad([[...a,5], [...b,5], [...c,5], [...d,5]], [0,0,1]);
      quad([[...d,-5], [...c,-5], [...b,-5], [...a,-5]], [0,0,-1]);
      quad([[...a,-5], [...b,-5], [...b,5], [...a,5]], n.map((v) => -v));
      quad([[...d,5], [...c,5], [...c,-5], [...d,-5]], n);
    }
  }
  return new Float32Array(data);
}

// CSS cubic-bezier(.45,0,.2,1), solved for x; camera never rotates.
function flight(t: number) {
  let lo = 0, hi = 1, s = t;
  for (let i = 0; i < 12; i++) {
    s = (lo + hi) / 2;
    const x = 3 * (1 - s) ** 2 * s * .45 + 3 * (1 - s) * s ** 2 * .2 + s ** 3;
    if (x < t) lo = s; else hi = s;
  }
  return 3 * (1 - s) * s * s + s ** 3;
}

export function tunnelRenderer(canvas: HTMLCanvasElement, mobile: boolean) {
  const gpu = context(canvas), { gl } = gpu;
  try {
    const scene = gpu.program(`#version 300 es
      precision highp float;
      layout(location=0) in vec3 position; layout(location=1) in vec3 normal; layout(location=2) in float frame;
      uniform vec2 viewport; uniform float travel; uniform float spacing;
      out float light; out float fade;
      void main(){
        float depth=900.-position.z-travel;
        gl_Position=vec4(position.xy*1800./viewport,1.01258*depth-100.629,depth);
        light=.43+.57*abs(dot(normal,normalize(vec3(-.3,.5,1.))));
        fade=smoothstep(250.,530.,900.+900.+frame*spacing-travel);
      }`, `#version 300 es
      precision highp float; in float light; in float fade; out vec4 result;
      void main(){result=vec4(vec3(.988,.973,.031)*light*fade,1.);}`);
    const fullscreen = `#version 300 es
      precision highp float; out vec2 uv;
      void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);uv=p;gl_Position=vec4(p*2.-1.,0.,1.);}`;
    const blur = gpu.program(fullscreen, `#version 300 es
      precision highp float; in vec2 uv; uniform sampler2D source; uniform vec2 direction; out vec4 result;
      void main(){vec3 c=texture(source,uv).rgb*.227027;
        c+=(texture(source,uv+direction*1.384615).rgb+texture(source,uv-direction*1.384615).rgb)*.316216;
        c+=(texture(source,uv+direction*3.230769).rgb+texture(source,uv-direction*3.230769).rgb)*.070270;
        result=vec4(c,1.);}`);
    const composite = gpu.program(fullscreen, `#version 300 es
      precision highp float; in vec2 uv; uniform sampler2D scene; uniform sampler2D glow; uniform float fade; out vec4 result;
      void main(){vec3 core=texture(scene,uv).rgb;
        result=vec4((core+texture(glow,uv).rgb*1.5)*fade,1.);}`);
    const geometry = mesh(mobile), vao = gpu.vao(); gpu.buffer(geometry);
    for (const [i, size, offset] of [[0,3,0],[1,3,3],[2,1,6]]) {
      gl.enableVertexAttribArray(i); gl.vertexAttribPointer(i,size,gl.FLOAT,false,28,offset*4);
    }
    const screen = gpu.vao();
    const targets = [0,1,2].map(() => ({ texture: gpu.texture(), fb: gpu.framebuffer() }));
    const depth = gpu.depth();
    let width = 0, height = 0;
    const bind = (i: number) => {
      gl.bindFramebuffer(gl.FRAMEBUFFER, targets[i].fb);
      gl.viewport(0,0,i ? Math.ceil(width/4) : width,i ? Math.ceil(height/4) : height);
    };
    return {
      draw(progress: number) {
        resize(canvas, mobile ? 1_000_000 : 2_000_000);
        if (canvas.width !== width || canvas.height !== height) {
          width = canvas.width; height = canvas.height;
          targets.forEach((target, i) => {
            gl.bindTexture(gl.TEXTURE_2D,target.texture);
            gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,i ? Math.ceil(width/4) : width,i ? Math.ceil(height/4) : height,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
            gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
            gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
            gl.bindFramebuffer(gl.FRAMEBUFFER,target.fb);
            gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,target.texture,0);
          });
          gl.bindFramebuffer(gl.FRAMEBUFFER,targets[0].fb); gl.bindRenderbuffer(gl.RENDERBUFFER,depth);
          gl.renderbufferStorage(gl.RENDERBUFFER,gl.DEPTH_COMPONENT16,width,height);
          gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.RENDERBUFFER,depth);
          for (const target of targets) {
            gl.bindFramebuffer(gl.FRAMEBUFFER,target.fb);
            if (gl.checkFramebufferStatus(gl.FRAMEBUFFER) !== gl.FRAMEBUFFER_COMPLETE) throw new Error("Tunnel target unavailable");
          }
        }
        bind(0); gl.clearColor(0,0,0,1); gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
        gl.enable(gl.DEPTH_TEST); gl.bindVertexArray(vao); gl.useProgram(scene);
        const box = canvas.getBoundingClientRect();
        gl.uniform2f(gl.getUniformLocation(scene,"viewport"),box.width,box.height);
        gl.uniform1f(gl.getUniformLocation(scene,"spacing"),4300/((mobile ? 9 : 14)-1));
        gl.uniform1f(gl.getUniformLocation(scene,"travel"),flight(progress)*5900);
        gl.drawArrays(gl.TRIANGLES,0,geometry.length/7);
        gl.disable(gl.DEPTH_TEST); gl.bindVertexArray(screen); gl.useProgram(blur);
        gl.activeTexture(gl.TEXTURE0); gl.uniform1i(gl.getUniformLocation(blur,"source"),0);
        // Wide, fixed blur in quarter resolution; only camera transforms change.
        for (let pass = 0; pass < 2; pass++) {
          bind(pass+1); gl.bindTexture(gl.TEXTURE_2D,targets[pass].texture);
          gl.uniform2f(gl.getUniformLocation(blur,"direction"),pass ? 0 : 8/width,pass ? 8/height : 0);
          gl.drawArrays(gl.TRIANGLES,0,3);
        }
        gl.bindFramebuffer(gl.FRAMEBUFFER,null); gl.viewport(0,0,width,height); gl.useProgram(composite);
        gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D,targets[0].texture);
        gl.uniform1i(gl.getUniformLocation(composite,"scene"),0);
        gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D,targets[2].texture);
        gl.uniform1i(gl.getUniformLocation(composite,"glow"),1);
        gl.uniform1f(gl.getUniformLocation(composite,"fade"),1-Math.max(0,(progress-.864)/.136));
        gl.drawArrays(gl.TRIANGLES,0,3);
      },
      dispose: gpu.dispose,
    };
  } catch (error) { gpu.dispose(); throw error; }
}
