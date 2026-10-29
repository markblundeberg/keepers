// core.js: the frame loop as a pure function of film time, render targets, camera, shot and kit registries.
// Owner: A (engine). How a kit plugs in: ENGINE.md. The contract: CONTRACT.md.
//
//   await window.renderFrame(t)   -> the canvas #c holds the printed frame for film time t (seconds)
//
// Nothing is carried between frames: every frame clears every target it draws, and all randomness is seeded.
'use strict';
(function () {
  const E = window.ENGINE = {
    W: 1920, H: 1080, FPS: 24,
    kits: {}, chunks: {}, chunkFiles: {}, shots: {}, sequence: [],
    printDefaults: {}, // filled by print.js
  };
  const q = E.query = new URLSearchParams(location.search);

  // ---------------------------------------------------------------- registries
  // A kit draws part of the scene into the radiance target. def: { init(gl, E) (may be async), draw(gl, F) }.
  E.kit = (name, def) => { E.kits[name] = Object.assign({ name }, def); };
  // A shared GLSL chunk, by name, included in any program that asks for it (see E.program). First one wins,
  // so a real kit loaded before a placeholder replaces the placeholder's chunk.
  E.chunk = (name, src) => { if (!(name in E.chunks) && !(name in E.chunkFiles)) E.chunks[name] = src; };
  E.chunkFile = (name, url) => { if (!(name in E.chunks) && !(name in E.chunkFiles)) E.chunkFiles[name] = url; };
  // A shot. def: { dur, kits: [names, drawn in this order], camera(tl, F) -> {pos, target, up?, fov?, near?, far?},
  //   print: {print params, see print.js}, printAt?(tl, F) -> {params varying in time}, type?(T, tl, F), ...anything else kits read }
  E.shot = (name, def) => { E.shots[name] = Object.assign({ name, dur: 10, kits: [], print: {} }, def); };
  // The film: shot names in order. Film time t runs through them back to back.
  E.setSequence = (names) => { E.sequence = names.slice(); };

  // Which shot and shot-local time a film time falls in. With ?shot=NAME the film is that shot alone and t is
  // shot-local (so ?shot=lantern&t=12.5 is 12.5 s into the lantern shot).
  E.locate = (t) => {
    const only = q.get('shot');
    if (only) {
      if (!E.shots[only]) throw new Error('no shot ' + only);
      return { shot: E.shots[only], tl: t, t0: 0 };
    }
    let t0 = 0;
    const seq = E.sequence.length ? E.sequence : Object.keys(E.shots);
    for (let i = 0; i < seq.length; i++) {
      const s = E.shots[seq[i]];
      if (!s) throw new Error('sequence names unknown shot ' + seq[i]);
      if (t < t0 + s.dur || i === seq.length - 1) return { shot: s, tl: t - t0, t0 };
      t0 += s.dur;
    }
    throw new Error('no shots registered');
  };
  E.filmDuration = () => (E.sequence.length ? E.sequence : Object.keys(E.shots)).reduce((a, n) => a + E.shots[n].dur, 0);

  // ---------------------------------------------------------------- seeded randomness (for JS-side kits)
  E.rng = (seed) => { // mulberry32
    let a = (seed >>> 0) || 1;
    return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  };
  E.gauss = (r) => { const u = Math.max(1e-12, r()), v = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v); };

  // ---------------------------------------------------------------- GL
  const canvas = E.canvas = document.getElementById('c');
  const gl = E.gl = canvas.getContext('webgl2', { antialias: false, alpha: false, depth: false, stencil: false, preserveDrawingBuffer: true, premultipliedAlpha: false });
  if (!gl) throw new Error('WebGL2 unavailable');
  if (!gl.getExtension('EXT_color_buffer_float')) throw new Error('EXT_color_buffer_float unavailable');
  gl.getExtension('OES_texture_float_linear');
  E.emptyVAO = gl.createVertexArray();

  E.COMMON = /* glsl */`
uniform float uT;          // film time (s)
uniform float uTl;         // shot-local time (s)
uniform vec2  uRes;        // target size in pixels
uniform vec3  uCamPos;     // camera position (world metres: x east, y up, z south; origin the South Bishop focal plane)
uniform vec3  uCamRight, uCamUp, uCamFwd;
uniform float uTanHalfFov; // tan(vertical fov / 2)
uniform float uAspect;     // width / height
uniform mat4  uView, uProj, uViewProj;
uniform float uNear, uFar;
const float PI = 3.14159265358979;
// World ray through a pixel (fragCoord in pixels of a target of size uRes).
vec3 cameraRay(vec2 fragCoord) {
  vec2 ndc = fragCoord / uRes * 2.0 - 1.0;
  return normalize(uCamFwd + ndc.x * uAspect * uTanHalfFov * uCamRight + ndc.y * uTanHalfFov * uCamUp);
}
// Depth-buffer value of a world point (for a full-screen kit writing gl_FragDepth so raster kits can test against it).
float depthOf(vec3 p) { vec4 c = uViewProj * vec4(p, 1.0); return clamp(0.5 * c.z / c.w + 0.5, 0.0, 1.0); }
// Screen position (pixels) of a world point; .z < 0 means behind the camera.
vec3 project(vec3 p) { vec4 c = uViewProj * vec4(p, 1.0); return vec3((c.xy / c.w * 0.5 + 0.5) * uRes, c.w); }
// Hashes (integer, so identical on every run and every worker).
uint hashu(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float hash1(uint x) { return float(hashu(x)) / 4294967296.0; }
float hash2i(ivec2 p) { return hash1(uint(p.x) * 1973u + hashu(uint(p.y) * 9277u + 26699u)); }
float hash3i(ivec3 p) { return hash1(hashu(uint(p.x) * 73856093u ^ uint(p.y) * 19349663u ^ uint(p.z) * 83492791u)); }
float vnoise3(vec3 p) {  // value noise, smooth, [0,1]
  vec3 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); ivec3 c = ivec3(i);
  float a = mix(mix(hash3i(c), hash3i(c + ivec3(1,0,0)), f.x), mix(hash3i(c + ivec3(0,1,0)), hash3i(c + ivec3(1,1,0)), f.x), f.y);
  float b = mix(mix(hash3i(c + ivec3(0,0,1)), hash3i(c + ivec3(1,0,1)), f.x), mix(hash3i(c + ivec3(0,1,1)), hash3i(c + ivec3(1,1,1)), f.x), f.y);
  return mix(a, b, f.z);
}
float vnoise2(vec2 p) {
  vec2 i = floor(p), f = fract(p); f = f * f * (3.0 - 2.0 * f); ivec2 c = ivec2(i);
  return mix(mix(hash2i(c), hash2i(c + ivec2(1,0)), f.x), mix(hash2i(c + ivec2(0,1)), hash2i(c + ivec2(1,1)), f.x), f.y);
}
`;
  E.FULLSCREEN_VS = `#version 300 es
const vec2 P[3] = vec2[3](vec2(-1.0,-1.0), vec2(3.0,-1.0), vec2(-1.0,3.0));
out vec2 vUv;
void main() { vec2 p = P[gl_VertexID]; vUv = 0.5 * p + 0.5; gl_Position = vec4(p, 0.0, 1.0); }`;

  function compile(type, src) {
    const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      const log = gl.getShaderInfoLog(s), lines = src.split('\n');
      const m = /0:(\d+)/.exec(log), at = m ? +m[1] : 0;
      throw new Error('shader compile:\n' + log + '\n' + lines.slice(Math.max(0, at - 4), at + 2).map((l, i) => (Math.max(0, at - 4) + i + 1) + ': ' + l).join('\n'));
    }
    return s;
  }
  // Compile a program. frag: the fragment body (no #version). opts.use: names of shared GLSL chunks to include
  // after COMMON (e.g. ['light']); opts.vert: a full vertex shader (default: full-screen triangle, out vUv).
  // opts.vertUse: chunks to include in the vertex shader too (inserted after its first line if it starts with #version).
  E.program = (frag, opts = {}) => {
    const use = opts.use || [];
    for (const u of use) if (!(u in E.chunks)) throw new Error('unknown GLSL chunk ' + u);
    const head = '#version 300 es\nprecision highp float;\nprecision highp int;\nprecision highp sampler2D;\n';
    const fs = head + E.COMMON + use.map(u => `// ---- chunk ${u}\n` + E.chunks[u]).join('\n') + '\n// ---- program\n' + frag;
    let vs = opts.vert || E.FULLSCREEN_VS;
    if (opts.vert && !/^#version/.test(vs.trim())) vs = head + E.COMMON + (opts.vertUse || []).map(u => E.chunks[u]).join('\n') + '\n' + vs;
    const p = gl.createProgram();
    gl.attachShader(p, compile(gl.VERTEX_SHADER, vs)); gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error('link: ' + gl.getProgramInfoLog(p));
    p.u = {};
    const n = gl.getProgramParameter(p, gl.ACTIVE_UNIFORMS);
    let unit = 0;
    for (let i = 0; i < n; i++) {
      const info = gl.getActiveUniform(p, i), name = info.name.replace(/\[0\]$/, '');
      const sampler = [gl.SAMPLER_2D, gl.SAMPLER_3D, gl.SAMPLER_2D_ARRAY, gl.INT_SAMPLER_2D, gl.UNSIGNED_INT_SAMPLER_2D].includes(info.type);
      p.u[name] = { loc: gl.getUniformLocation(p, info.name), type: info.type, size: info.size, unit: sampler ? unit++ : -1 };
    }
    return p;
  };
  // Set uniforms by name; unknown names are ignored, so one object can feed many programs.
  // Values: number, array (vecN / matN / arrays of floats), {tex, target?} for samplers.
  E.set = (p, obj) => {
    gl.useProgram(p);
    for (const k in obj) {
      const u = p.u[k]; if (!u) continue;
      const v = obj[k];
      switch (u.type) {
        case gl.FLOAT: u.size > 1 ? gl.uniform1fv(u.loc, v) : gl.uniform1f(u.loc, v); break;
        case gl.FLOAT_VEC2: gl.uniform2fv(u.loc, v); break;
        case gl.FLOAT_VEC3: gl.uniform3fv(u.loc, v); break;
        case gl.FLOAT_VEC4: gl.uniform4fv(u.loc, v); break;
        case gl.INT: case gl.BOOL: u.size > 1 ? gl.uniform1iv(u.loc, v) : gl.uniform1i(u.loc, v); break;
        case gl.INT_VEC2: gl.uniform2iv(u.loc, v); break;
        case gl.FLOAT_MAT3: gl.uniformMatrix3fv(u.loc, false, v); break;
        case gl.FLOAT_MAT4: gl.uniformMatrix4fv(u.loc, false, v); break;
        default:
          if (u.unit >= 0) {
            gl.activeTexture(gl.TEXTURE0 + u.unit);
            gl.bindTexture(v.target || gl.TEXTURE_2D, v.tex || v);
            gl.uniform1i(u.loc, u.unit);
          }
      }
    }
  };
  // Draw a full-screen triangle with program p (after E.set).
  E.fullscreen = (p) => { gl.useProgram(p); gl.bindVertexArray(E.emptyVAO); gl.drawArrays(gl.TRIANGLES, 0, 3); };

  // A render target. opts: { internal: gl.RGBA16F, format: gl.RGBA, type: gl.HALF_FLOAT, filter: gl.LINEAR, depth: false }
  E.target = (w, h, opts = {}) => {
    const internal = opts.internal || gl.RGBA16F, format = opts.format || gl.RGBA, type = opts.type || gl.HALF_FLOAT;
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texImage2D(gl.TEXTURE_2D, 0, internal, w, h, 0, format, type, null);
    const f = opts.filter || gl.LINEAR;
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, f); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, f);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const fb = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
    let depth = null;
    if (opts.depth) {
      depth = gl.createRenderbuffer(); gl.bindRenderbuffer(gl.RENDERBUFFER, depth);
      gl.renderbufferStorage(gl.RENDERBUFFER, gl.DEPTH_COMPONENT24, w, h);
      gl.framebufferRenderbuffer(gl.FRAMEBUFFER, gl.DEPTH_ATTACHMENT, gl.RENDERBUFFER, depth);
    }
    const st = gl.checkFramebufferStatus(gl.FRAMEBUFFER);
    if (st !== gl.FRAMEBUFFER_COMPLETE) throw new Error('framebuffer incomplete ' + st);
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    return { tex, fb, depth, w, h };
  };
  E.bind = (target) => {
    gl.bindFramebuffer(gl.FRAMEBUFFER, target ? target.fb : null);
    gl.viewport(0, 0, target ? target.w : E.W, target ? target.h : E.H);
  };
  // A texture from typed data (e.g. Float32Array, one channel: internal gl.R16F, format gl.RED, type gl.FLOAT).
  E.dataTexture = (w, h, data, opts = {}) => {
    const tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    gl.texImage2D(gl.TEXTURE_2D, 0, opts.internal || gl.R16F, w, h, 0, opts.format || gl.RED, opts.type || gl.FLOAT, data);
    const f = opts.filter || gl.NEAREST, wrap = opts.wrap || gl.REPEAT;
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, f); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, f);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, wrap); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, wrap);
    return tex;
  };

  // ---------------------------------------------------------------- camera
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const norm = (a) => { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; };
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  E.vec = { sub, cross, norm, dot };
  // cam: { pos, target, up = [0,1,0], fov = 40 (vertical, degrees), near = 0.5, far = 20000, roll = 0 (radians) }
  E.makeCamera = (cam) => {
    const pos = cam.pos, fov = cam.fov || 40, near = cam.near || 0.5, far = cam.far || 20000, aspect = E.W / E.H;
    const fwd = norm(sub(cam.target, pos));
    let right = norm(cross(fwd, cam.up || [0, 1, 0]));
    let up = cross(right, fwd);
    if (cam.roll) {
      const c = Math.cos(cam.roll), s = Math.sin(cam.roll);
      [right, up] = [right.map((r, i) => c * r + s * up[i]), up.map((u, i) => c * u - s * right[i])];
    }
    const view = new Float32Array([right[0], up[0], -fwd[0], 0, right[1], up[1], -fwd[1], 0, right[2], up[2], -fwd[2], 0,
      -dot(right, pos), -dot(up, pos), dot(fwd, pos), 1]);
    const th = Math.tan(fov * Math.PI / 360), f = 1 / th;
    const proj = new Float32Array([f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) / (near - far), -1, 0, 0, 2 * far * near / (near - far), 0]);
    const vp = new Float32Array(16);
    for (let c = 0; c < 4; c++) for (let r = 0; r < 4; r++) { let s = 0; for (let k = 0; k < 4; k++) s += proj[k * 4 + r] * view[c * 4 + k]; vp[c * 4 + r] = s; }
    return { pos, fwd, right, up, fov, near, far, aspect, tanHalfFov: th, view, proj, viewProj: vp };
  };

  // ---------------------------------------------------------------- init
  E.init = async () => {
    for (const [name, url] of Object.entries(E.chunkFiles)) {
      const r = await fetch(url); if (!r.ok) throw new Error('chunk file ' + url + ': ' + r.status);
      E.chunks[name] = await r.text();
    }
    E.hdr = E.target(E.W, E.H, { depth: true });
    if (window.TYPE) await TYPE.init(E);
    await E.printInit();
    for (const k of Object.values(E.kits)) if (k.init) await k.init(gl, E);
    E.ready = true;
  };

  // ---------------------------------------------------------------- the frame
  function resetState() {
    gl.disable(gl.BLEND); gl.disable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE); gl.disable(gl.SCISSOR_TEST);
    gl.depthMask(true); gl.colorMask(true, true, true, true); gl.depthFunc(gl.LESS);
    gl.blendFunc(gl.ONE, gl.ZERO); gl.blendEquation(gl.FUNC_ADD);
  }
  // Build the frame object every kit receives.
  E.frame = (t) => {
    const { shot, tl, t0 } = E.locate(t);
    const cam = E.makeCamera(shot.camera ? shot.camera(tl) : { pos: [0, 0, 100], target: [0, 0, 0] });
    const F = { t, tl, t0, shot, cam, W: E.W, H: E.H };
    F.common = {
      uT: t, uTl: tl, uRes: [E.W, E.H], uCamPos: cam.pos, uCamRight: cam.right, uCamUp: cam.up, uCamFwd: cam.fwd,
      uTanHalfFov: cam.tanHalfFov, uAspect: cam.aspect, uView: cam.view, uProj: cam.proj, uViewProj: cam.viewProj,
      uNear: cam.near, uFar: cam.far,
    };
    F.print = Object.assign({}, E.printDefaults, shot.print || {}, shot.printAt ? shot.printAt(tl, F) : {}, E.urlPrint());
    return F;
  };
  // Print overrides from the URL: ?p.grain=1.4&p.warmth=0.3 (for variants and tests).
  E.urlPrint = () => { const o = {}; for (const [k, v] of q) if (k.startsWith('p.')) o[k.slice(2)] = +v; return o; };

  window.renderFrame = async (t) => {
    if (!E.ready) await window.ready;
    const F = E.frame(t);
    // 1. scene pass: linear radiance into E.hdr (RGBA16F + depth), cleared every frame
    // prepare: every kit in the shot may add uniforms to F.common (e.g. uBeamAz) before anything draws
    for (const name of F.shot.kits) {
      const k = E.kits[name]; if (!k) throw new Error('shot ' + F.shot.name + ' uses unknown kit ' + name);
      if (k.prepare) k.prepare(F);
    }
    E.bind(E.hdr); resetState();
    gl.clearColor(0, 0, 0, 1); gl.clearDepth(1); gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    for (const name of F.shot.kits) {
      const k = E.kits[name]; if (!k) throw new Error('shot ' + F.shot.name + ' uses unknown kit ' + name);
      E.bind(E.hdr); resetState();
      if (k.draw) await k.draw(gl, F);
    }
    // 2. type layer (2D canvas, uploaded) and 3. the print pass to the screen
    resetState();
    const typeTex = window.TYPE ? TYPE.render(F) : null;
    E.printRun(F, typeTex);
    gl.finish();
    return F;
  };
})();
