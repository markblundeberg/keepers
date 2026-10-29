// placeholder.js: a stand-in scene so the engine and the print can be seen before the real kits exist. Owner: A.
// Everything here yields: if light.js (B) or birds.js (C) registered the kit or chunk first, theirs is used.
// Nothing in this file is research: the tower, the beam width and the birds are invented for testing the print.
'use strict';
(function () {
  const E = window.ENGINE;
  const CYCLE = 20.0;             // "One rev. br. lt., 20 secs." (Findlay 1887): this one number is recorded
  const H_FOCAL = 44.0;           // contract placeholder until B researches it

  // ---------------------------------------------------------------- light chunk (stand-in for B's light.glsl)
  E.chunk('light', /* glsl */`
uniform float uBeamAz;   // beam azimuth, radians clockwise from north seen from above
const float H_FOCAL = ${H_FOCAL.toFixed(1)};
vec3 beamDir() { return vec3(sin(uBeamAz), 0.0, -cos(uBeamAz)); }
// relative intensity in a direction: narrow in azimuth, wider in elevation (placeholder numbers)
float beamProfile(vec3 u) {
  float az = atan(u.x, -u.z), da = mod(az - uBeamAz + PI, 2.0 * PI) - PI, el = asin(clamp(u.y, -1.0, 1.0));
  return exp(-pow(da / 0.10, 2.0) - pow(el / 0.12, 2.0)) + 0.03 * exp(-pow(da / 0.3, 2.0) - pow(el / 0.3, 2.0));
}
// irradiance at a world point from the beam and the lantern's own glow (placeholder numbers)
float illum(vec3 p, float t) {
  float r = max(length(p), 1.5);
  vec3 d = beamDir();
  float beam = 9000.0 * beamProfile(p / r);
  float glow = 60.0;
  return (beam + glow) / (r * r) + 0.002;
}`);
  // beam azimuth (clockwise from north, seen from above); the shot sets when it faces the camera
if (!window.LIGHT) window.LIGHT = { beamAz: (t, facesAt, camPos) => Math.atan2(camPos[0], -camPos[2]) + 2 * Math.PI * (t - facesAt) / CYCLE };

  // ---------------------------------------------------------------- light kit (sky, sea, tower, lantern, beam)
  if (!E.kits.light) {
    let prog;
    E.kit('light', {
      init() {
        prog = E.program(/* glsl */`
in vec2 vUv; out vec4 o;
float fbm3(vec3 p) { float a = 0.0, w = 0.5; for (int i = 0; i < 4; i++) { a += w * vnoise3(p); p = p * 2.02 + 3.1; w *= 0.5; } return a; }
// ray against the tower: an upright cylinder of radius rad from y0 to y1; returns distance or -1
float cyl(vec3 o, vec3 v, float rad, float y0, float y1) {
  float a = dot(v.xz, v.xz), b = dot(o.xz, v.xz), c = dot(o.xz, o.xz) - rad * rad;
  float h = b * b - a * c; if (h < 0.0) return -1.0;
  float s = (-b - sqrt(h)) / a; float y = o.y + s * v.y;
  return (s > 0.0 && y > y0 && y < y1) ? s : -1.0;
}
void main() {
  vec3 ro = uCamPos, v = cameraRay(gl_FragCoord.xy);
  vec3 wind = vec3(-0.6, 0.0, -0.8) * 6.0;                     // S.E. force 4 drifting the mist toward the N.W.
  float tHit = 1e9; vec3 L = vec3(0.0); float hitDepth = 1.0;
  // sky: overcast, a little paler toward the horizon, faint cloud
  float alt = max(v.y, 0.0);
  float cloud = fbm3(vec3(v.xz / max(v.y, 0.05) * 1.2, uT * 0.01) + vec3(uT * 0.02, 0.0, 0.0));
  L = vec3(0.003 + 0.006 * exp(-alt * 5.0)) * (0.5 + cloud);
  // sea
  if (v.y < 0.0) {
    float s = (-H_FOCAL - ro.y) / v.y; vec3 p = ro + s * v;
    float waves = fbm3(vec3(p.xz * vec2(0.08, 0.2), uT * 0.3));
    float fres = 0.02 + 0.98 * pow(1.0 - abs(v.y), 5.0);
    L = vec3(0.004) + fres * vec3(0.016) * (0.3 + waves) + vec3(illum(p + vec3(0.0, 2.0, 0.0), uT) * 0.02 * waves * waves);
    tHit = s; hitDepth = depthOf(p);
  }
  // rock, tower, gallery, lantern, dome
  float sR = cyl(ro, v, 14.0, -H_FOCAL - 2.0, -H_FOCAL + 6.0 + 0.0);
  float sT = cyl(ro, v, 4.2, -H_FOCAL, -3.2);
  float sG = cyl(ro, v, 5.4, -3.6, -3.0);
  float sL = cyl(ro, v, 2.5, -3.0, 2.8);
  float sD = cyl(ro, v, 2.3, 2.8, 4.6);
  vec3 lampGlass = vec3(0.0);
  if (sR > 0.0 && sR < tHit) { tHit = sR; vec3 p = ro + sR * v; L = vec3(0.004 + 0.0015 * illum(p, uT)) * (0.6 + fbm3(p * 0.4)); hitDepth = depthOf(p); }
  if (sT > 0.0 && sT < tHit) { tHit = sT; vec3 p = ro + sT * v; vec3 n = normalize(vec3(p.x, 0.0, p.z));
    float lit = max(0.0, dot(n, normalize(-p))) * illum(p, uT) * 0.4 + 0.004;
    L = vec3(lit) * (0.8 + 0.3 * fbm3(p * 0.6)); hitDepth = depthOf(p); }
  if (sG > 0.0 && sG < tHit) { tHit = sG; vec3 p = ro + sG * v; L = vec3(0.01 + 0.2 * illum(p, uT)); hitDepth = depthOf(p); }
  if (sD > 0.0 && sD < tHit) { tHit = sD; vec3 p = ro + sD * v; L = vec3(0.006 + 0.03 * illum(p, uT)); hitDepth = depthOf(p); }
  if (sL > 0.0 && sL < tHit) {
    tHit = sL; vec3 p = ro + sL * v; hitDepth = depthOf(p);
    // the glazing: astragals (diagonal bars) dark, the lens behind bright, and blinding when the beam faces us
    float a = atan(p.x, p.z);
    float bars = step(0.88, fract((a * 2.5 + p.y * 0.55) * 1.6)) + step(0.94, fract((p.y + 3.0) / 1.45));
    float face = beamProfile(normalize(ro));
    float glass = 3.0 + 2000.0 * face;
    L = mix(vec3(glass), vec3(0.02), clamp(bars, 0.0, 1.0) * (1.0 - face * 0.9));
  }
  // the beam through mist: analytic in-scatter across a narrow Gaussian cone, modulated by drifting mist
  vec3 d = beamDir();
  vec3 w0 = ro; float bb = dot(v, d), dd = dot(v, w0), ee = dot(d, w0), den = max(1.0 - bb * bb, 1e-4);
  float sv = (bb * ee - dd) / den, sb = (ee - bb * dd) / den;      // closest points: along view, along beam
  if (sb > 0.0 && sv > 0.0 && sv < tHit) {
    vec3 pv = ro + sv * v, pb = sb * d; float rho = length(pv - pb), r = max(sb, 2.0);
    float width = 0.10 * r + 0.6;
    float sinA = max(sqrt(den), 0.04);
    float mist = 0.35 + 1.3 * fbm3(pv / 22.0 - wind * uT / 22.0);
    float phase = 1.0 + 3.0 * pow(max(0.0, dot(d, -v)), 6.0);
    L += vec3(8.0 / (r * sinA) * exp(-pow(rho / width, 2.0)) * mist * phase);
  }
  // the lantern's glow scattered in the mist all round (1/b law for a point source in a uniform haze)
  float sl = clamp(-dot(ro, v), 0.0, tHit), b = length(ro + sl * v);
  float glow = 60.0 * 0.0015 * (atan(sl, b) + atan(max(tHit - sl, 0.0), b) * step(0.0, 1.0)) / max(b, 0.5);
  L += vec3(glow) * (0.7 + 0.6 * fbm3((ro + sl * v) / 15.0 - wind * uT / 15.0));
  o = vec4(L, 1.0);
  gl_FragDepth = hitDepth;
}`, { use: ['light'] });
      },
      prepare(F) { F.common.uBeamAz = window.LIGHT.beamAz(F.tl, F.shot.beamFacesAt ?? 4, F.cam.pos); },
      draw(gl, F) {
        gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.ALWAYS);
        E.set(prog, F.common); E.fullscreen(prog);
      },
    });
  }

  // ---------------------------------------------------------------- birds kit (stand-in for C's)
  if (!E.kits.birds) {
    let prog, buf, vao, N = 3000, seeds;
    E.kit('birds', {
      init(gl) {
        const r = E.rng(42); seeds = new Float32Array(N * 8);
        for (let i = 0; i < N; i++) {
          const rad = 3 + 45 * Math.pow(r(), 1.8), y = E.gauss(r) * (1.5 + 0.12 * rad);
          seeds.set([rad, r() * 6.283, y, (0.4 + r()) * (r() < 0.5 ? -1 : 1) * 4 / Math.sqrt(rad), 7 + 6 * r(), r() * 6.283, r() * 24 - 12, r()], i * 8);
        }
        buf = gl.createBuffer(); vao = gl.createVertexArray();
        prog = E.program(/* glsl */`
in float vLight; in float vWing; out vec4 o;
void main() {
  vec2 c = gl_PointCoord * 2.0 - 1.0;
  // a small bird seen side-on: a 'v' that flattens with the wingbeat
  float y = c.y + vWing * 0.6 * abs(c.x);
  float body = smoothstep(0.32, 0.12, abs(y)) * smoothstep(1.0, 0.7, abs(c.x));
  if (body < 0.5) discard;
  o = vec4(vec3(vLight), 1.0);
}`, { use: ['light'], vertUse: ['light'], vert: `
in vec4 aPos; out float vLight; out float vWing;
void main() {
  vec4 c = uViewProj * vec4(aPos.xyz, 1.0);
  gl_Position = c;
  gl_PointSize = clamp(260.0 / c.w, 2.0, 14.0);
  vLight = min(0.05 * illum(aPos.xyz, uT), 1.2);
  vWing = sin(aPos.w);
}` });
        gl.bindVertexArray(vao); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
        const loc = gl.getAttribLocation(prog, 'aPos'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 4, gl.FLOAT, false, 0, 0);
        gl.bindVertexArray(null);
      },
      draw(gl, F) {
        const t = F.tl, pos = new Float32Array(N * 4);
        for (let i = 0; i < N; i++) {
          const [rad, th0, y, om, flap, ph, arrive] = seeds.subarray(i * 8, i * 8 + 7);
          const th = th0 + om * t, rr = rad * (1 + 0.08 * Math.sin(t * 0.7 + ph));
          const on = t > arrive ? 1 : 0;
          pos.set([rr * Math.cos(th), y + 1.2 * Math.sin(t * 1.1 + ph), rr * Math.sin(th) + (on ? 0 : 1e6), t * flap * 6.283 + ph], i * 4);
        }
        gl.bindBuffer(gl.ARRAY_BUFFER, buf); gl.bufferData(gl.ARRAY_BUFFER, pos, gl.DYNAMIC_DRAW);
        gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LESS);
        E.set(prog, F.common); gl.bindVertexArray(vao); gl.drawArrays(gl.POINTS, 0, N); gl.bindVertexArray(null);
      },
    });
  }

  // ---------------------------------------------------------------- a test chart for measuring the print
  // 16 patches of radiance 0.004 * 2^(k/2), k = 0..15 (top two rows), and a smooth log ramp (bottom row)
  let chartProg;
  E.kit('chart', {
    init() { chartProg = E.program(`in vec2 vUv; out vec4 o;
void main() {
  vec2 u = vec2(vUv.x, 1.0 - vUv.y);
  float Y;
  if (u.y < 0.66) { float k = floor(u.x * 8.0) + 8.0 * floor(u.y / 0.33); Y = 0.004 * exp2(k * 0.5); }
  else Y = 0.004 * exp2(u.x * 7.5);
  vec3 c = vec3(Y);
  // two lamps on the ramp row: red (left) and green (right), each a hot core in a glow (colour test)
  vec2 px = gl_FragCoord.xy;
  float dr = length(px - vec2(480.0, 180.0)), dg = length(px - vec2(1440.0, 180.0));
  c += vec3(1.0, 0.12, 0.06) * (60.0 * exp(-pow(dr / 10.0, 2.0)) + 0.6 * exp(-dr / 60.0));
  c += vec3(0.10, 1.0, 0.35) * (60.0 * exp(-pow(dg / 10.0, 2.0)) + 0.6 * exp(-dg / 60.0));
  o = vec4(c, 1.0);
}`); },
    draw(gl, F) { E.set(chartProg, F.common); E.fullscreen(chartProg); },
  });
  E.shot('chart', { dur: 1, kits: ['chart'], print: { vignette: 0, edgeSoft: 0, plateInset: 0 } });

  // ---------------------------------------------------------------- a shot to look at
  E.shot('placeholder', {
    dur: 20, kits: ['light', 'birds'], beamFacesAt: 4,
    camera: (tl) => ({ pos: [12 - tl * 0.1, -26, 72 - tl * 0.3], target: [0, -7, 0], fov: 40 }),
    type: (T, tl) => {
      const a = Math.min(1, Math.max(0, (tl - 0.5) / 1.0)) * Math.min(1, Math.max(0, (5.5 - tl) / 1.0));
      if (a > 0) T.text('South Bishop Lighthouse, 21 October 1887.', 960, 960, { size: 34, italic: true, alpha: a });
    },
  });
})();
