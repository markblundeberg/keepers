// light.js: the South Bishop lighthouse kit. Owner: B.
// Draws, in one full-screen pass into the radiance target: the sky, the sea, the rock, the station (tower, keepers'
// houses, compound wall), the lantern (lower wall, glazing of 4 x 24 flat panes on vertical astragals, conical roof and
// ball vent, gallery and railing), the eight-faced lens band turning inside it, and the beams as a volume in the
// drifting mist. Writes depth for the solid surfaces, so later kits (the birds) can depth-test against them.
// The shared GLSL chunk 'light' (light.glsl) holds beamAz, illum, mistDensity, mistPhase and mistTo.
// What is recorded and what is reconstructed: film/research/south-bishop.md.
//
// The kit reads the shot's beamFacesAt, hour(tl) and dawn(tl) (shots.js); see L.settings below.
// Its prepare() puts the chunk's uniforms (uLightPhase, uLightLamp, uLightDawn, uLightMist, uLightNoise) into
// F.common, so any kit that does E.set(prog, F.common) can use the 'light' chunk with nothing more.
'use strict';
(function () {
  const E = window.ENGINE, gl = E.gl;
  const TAU = 2 * Math.PI;
  const L = window.LIGHT = {
    N_FACES: 8,            // lens band of eight faces (Royal Commission 1861, visit of July 1859)
    FLASH: 20,             // s between flashes (Findlay 1887)
    PERIOD: 160,           // s per turn of the lens (8 x 20; inferred)
    H_FOCAL: 43.9,         // flame above high water, m (144 ft, Findlay 1887)
    SEA: -43.9,
    WIND: [-4.74, 0, -4.74],   // m/s: S.E. force 4, blowing toward the N.W.
  };

  // ---------------------------------------------------------------- per-shot settings
  // Read from the shot (shots.js): beamFacesAt (s), hour(tl), dawn(tl). The lamp burns until sunrise, 06:57 GMT on
  // 22 Oct 1887 at the South Bishop (skyfield, de440s; civil twilight from 06:23), i.e. hour 30.95 after the noon before.
  // shot.light = { phase, lamp, dawn, mist } overrides anything (for tests).
  L.SUNRISE_HOUR = 30.95;
  L.settings = (F) => {
    const sh = F.shot, o = Object.assign({}, sh.light || {}, sh.lightAt ? sh.lightAt(F.tl, F) : {});
    const val = (v, d) => (typeof v === 'function' ? v(F.tl, F) : v === undefined ? d : v);
    const s = { mist: val(o.mist, 1) };
    s.flashAt = val(sh.beamFacesAt, val(o.flashAt, 4));
    s.dawn = val(o.dawn, val(sh.dawn, 0));
    const hour = sh.hour ? sh.hour(F.tl) : null;
    s.lamp = val(o.lamp, hour === null ? 1 : hour < L.SUNRISE_HOUR ? 1 : 0);
    s.phase = o.phase;
    if (s.phase === undefined) {
      // a beam faces the camera (as placed at time flashAt, clamped into the shot) at time flashAt
      const tc = Math.max(0, Math.min(sh.dur || 1e9, s.flashAt));
      const c = sh.camera ? E.makeCamera(sh.camera(tc, F)).pos : F.cam.pos;
      s.phase = Math.atan2(c[0], -c[2]) - TAU * s.flashAt / L.PERIOD;
    }
    return s;
  };
  // Bearing (rad, clockwise from north) of face 0 at shot-local time tl; faces k at + k * TAU / 8.
  L.beamAz = (tl, F) => L.settings(F).phase + TAU * tl / L.PERIOD;
  L.uniforms = (F) => {
    const s = L.settings(F);
    return { uLightPhase: s.phase, uLightLamp: s.lamp, uLightDawn: s.dawn, uLightMist: s.mist,
             uLightNoise: { tex: L.noiseTex, target: gl.TEXTURE_3D } };
  };

  // JS mirror of illum() without the mist's attenuation and ambient (for simulations that want to know where light is).
  L.illumJS = (p, tl, F) => {
    const s = L.settings(F), r2 = Math.max(1, p[0] * p[0] + p[1] * p[1] + p[2] * p[2]), r = Math.sqrt(r2), se = p[1] / r;
    const tauR = s.mist * (1.5e-3 * Math.min(r, 1000) + 0.6e-3 * Math.max(r - 1000, 0));   // as ltTauR in light.glsl
    const a0 = s.phase + TAU * tl / L.PERIOD, sect = TAU / L.N_FACES, az = Math.atan2(p[0], -p[2]);
    const k0 = Math.floor((az - a0) / sect + 0.5);
    let Eb = 0;
    for (let j = -1; j <= 1; j++) {
      const a = a0 + (k0 + j) * sect, ax = [Math.sin(a), 0, -Math.cos(a)];
      const sx = p[0] * ax[0] + p[2] * ax[2]; if (sx <= 0) continue;
      const q2 = r2 - sx * sx, w = 0.38 + 0.0566 * sx, x2 = q2 / (w * w);
      Eb += 2.05e3 / (Math.PI * w * w) * (0.96 * Math.exp(-x2) + 0.0025 * Math.exp(-x2 / 16));
    }
    const ss = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };
    const esc = 3.75e3 * 0.5 / r2 * ss(0.42, 0.46, se) * (1 - ss(0.69, 0.72, se));
    const glow = 3.75e3 * 0.02 / r2 * ss(-0.43, -0.37, se) * (1 - ss(0.69, 0.72, se));
    return s.lamp * (Eb + esc + glow) * Math.exp(-tauR);
  };

  // ---------------------------------------------------------------- textures
  // Smooth tileable 3D noise: white noise blurred by a periodic Gaussian, then standardised.
  function makeNoise3D(n, sigma, seed) {
    const rnd = E.rng(seed);
    let a = new Float32Array(n * n * n);
    for (let i = 0; i < a.length; i++) a[i] = rnd() - 0.5;
    const R = Math.ceil(3 * sigma), k = [];
    for (let i = -R; i <= R; i++) k.push(Math.exp(-i * i / (2 * sigma * sigma)));
    const idx = (x, y, z) => ((z % n + n) % n) * n * n + ((y % n + n) % n) * n + ((x % n + n) % n);
    for (let axis = 0; axis < 3; axis++) {
      const b = new Float32Array(a.length);
      for (let z = 0; z < n; z++) for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
        let s = 0;
        for (let i = -R; i <= R; i++) s += k[i + R] * a[axis === 0 ? idx(x + i, y, z) : axis === 1 ? idx(x, y + i, z) : idx(x, y, z + i)];
        b[idx(x, y, z)] = s;
      }
      a = b;
    }
    let m = 0, v = 0;
    for (const x of a) m += x; m /= a.length;
    for (const x of a) v += (x - m) * (x - m); v = Math.sqrt(v / a.length);
    for (let i = 0; i < a.length; i++) a[i] = (a[i] - m) / v;
    return a;
  }

  // The rock: plan from OpenStreetMap (coastline ways 226403277 / 1265020215, (c) OpenStreetMap contributors, ODbL),
  // in metres from the light (x east, z south). Relief reconstructed: 30.5 m at the station (Coflein / Hague), steep
  // sides, a lower western shoulder (2018 photographs), blocky. Height above high water, in a 512^2 texture.
  const ISLAND = [-86.3, 99.2, -88.9, 93.6, -88.9, 87.0, -86.1, 79.1, -83.7, 70.5, -83.3, 66.1, -85.0, 62.7, -88.4, 59.2, -93.0, 57.6, -99.5, 58.0, -104.2, 59.2, -109.5, 60.7, -113.7, 60.8, -117.2, 58.6, -119.2, 54.9, -118.9, 50.5, -114.3, 35.4, -105.7, 21.9, -97.3, 11.4, -87.5, 1.8, -83.7, -0.7, -79.6, -2.5, -72.4, -3.4, -65.1, -1.4, -60.1, -0.6, -55.4, -2.8, -52.5, -6.5, -51.4, -16.6, -47.9, -23.3, -42.6, -29.3, -34.0, -33.5, -24.3, -36.8, -6.0, -40.3, 10.0, -41.4, 18.7, -39.7, 29.7, -34.2, 43.8, -23.4, 50.7, -18.2, 53.0, -14.3, 53.1, -7.9, 50.5, 1.6, 44.4, 16.5, 41.3, 23.7, 36.4, 34.3, 30.6, 41.1, 21.8, 49.6, 13.6, 55.2, 6.4, 58.1, 0.1, 60.8, -7.2, 61.3, -16.1, 63.8, -21.6, 67.8, -28.1, 70.7, -33.9, 74.8, -37.9, 78.4, -41.0, 82.0, -43.7, 86.4, -46.7, 89.5, -53.1, 94.8, -60.8, 98.5, -66.3, 100.2, -73.1, 101.4, -80.5, 100.9, -86.3, 99.2];
  const REEF = [42.1, 49.6, 42.9, 46.9, 45.1, 44.8, 50.2, 39.7, 61.2, 30.1, 69.7, 23.5, 78.6, 17.2, 85.0, 13.5, 89.9, 12.1, 94.9, 13.1, 97.4, 14.7, 98.9, 17.1, 99.7, 20.6, 98.6, 25.2, 96.5, 29.8, 85.1, 36.3, 74.4, 42.6, 64.8, 50.1, 57.6, 53.8, 51.2, 55.4, 47.5, 54.7, 43.8, 53.0, 42.1, 49.6];
  // The station's walled compound (OSM way 1265020213).
  const COMPOUND = [-10.0, -16.4, -16.4, -12.1, -15.5, -10.7, -18.1, -8.9, -8.1, 5.9, -11.0, 7.8, -11.1, 8.6, -9.0, 10.1, -7.3, 12.3, -5.6, 18.2, -1.2, 14.8, 11.2, 14.2, 21.4, 7.4, 8.4, -11.7, 3.6, -8.5, 3.1, -9.3, 5.1, -13.7, 4.3, -15.1, -1.6, -17.9, -3.4, -17.3, -5.3, -13.5, -7.4, -16.6, -9.3, -15.4, -10.0, -16.4];
  L.ROCK = { x0: -160, z0: -80, size: 280, n: 512 };
  // The keepers' houses (placement chosen; research note). Frame: origin c = [x, z] (world, the block's centre at
  // yard level y = -16.4), local x along bearing az (rad, clockwise from north), local z 90 deg clockwise from it.
  // boxes in that frame: [x0, x1, z0, z1, yTop (world)]: the block (eaves; the hipped roof rises 3 m above) and the corridor.
  L.HOUSE = { c: [10.3, 3.75], az: 1.92, yard: -16.4, boxes: [[-6.5, 6.5, -4.0, 4.0, -10.4], [-9.2, -6.4, -1.5, 1.5, -11.8]] };
  L.houseLocal = (x, z) => { const a = L.HOUSE.az - Math.PI / 2, c = Math.cos(a), s = Math.sin(a), qx = x - L.HOUSE.c[0], qz = z - L.HOUSE.c[1];
    return [c * qx + s * qz, -s * qx + c * qz]; };

  function sdPoly(P, x, z) {      // signed distance to a closed polygon, positive inside
    let d = 1e9, inside = false;
    for (let i = 0, j = P.length / 2 - 1; i < P.length / 2; j = i++) {
      const ax = P[2 * j], az = P[2 * j + 1], bx = P[2 * i], bz = P[2 * i + 1];
      const ex = bx - ax, ez = bz - az, wx = x - ax, wz = z - az;
      if (ex * ex + ez * ez < 1e-12) continue;            // the closing point repeats the first
      const h = Math.max(0, Math.min(1, (wx * ex + wz * ez) / (ex * ex + ez * ez)));
      d = Math.min(d, Math.hypot(wx - h * ex, wz - h * ez));
      if ((az > z) !== (bz > z) && x < ax + (z - az) * ex / ez) inside = !inside;
    }
    return inside ? d : -d;
  }
  function vnoise2(seed) {          // value noise in JS (smooth), [-1, 1]
    const h = (i, j) => { let x = Math.imul(i, 374761393) + Math.imul(j, 668265263) + Math.imul(seed, 1442695041); x = Math.imul(x ^ (x >>> 13), 1274126177); return ((x ^ (x >>> 16)) >>> 0) / 4294967296 * 2 - 1; };
    return (x, z) => {
      const i = Math.floor(x), j = Math.floor(z), fx = x - i, fz = z - j, u = fx * fx * (3 - 2 * fx), v = fz * fz * (3 - 2 * fz);
      return (h(i, j) * (1 - u) + h(i + 1, j) * u) * (1 - v) + (h(i, j + 1) * (1 - u) + h(i + 1, j + 1) * u) * v;
    };
  }
  function makeRock() {
    const { x0, z0, size, n } = L.ROCK, out = new Float32Array(n * n);
    const n1 = vnoise2(11), n2 = vnoise2(23), n3 = vnoise2(37);
    for (let j = 0; j < n; j++) for (let i = 0; i < n; i++) {
      const x = x0 + (i + 0.5) * size / n, z = z0 + (j + 0.5) * size / n;
      const d = Math.max(sdPoly(ISLAND, x, z), sdPoly(REEF, x, z) - 1.0);
      const top = 13 + 17.5 * Math.exp(-(x * x + z * z) / (2 * 48 * 48));                    // 30.5 m at the station
      const ridge = 1 - Math.abs(n2(x / 9, z / 9));                                           // blocky, fissured
      const rough = 3.4 * n1(x / 14, z / 14) + 3.0 * ridge * ridge + 1.0 * n3(x / 3.5, z / 3.5);
      let h = d > 0 ? top * (1 - Math.exp(-d / 5.5)) + rough * Math.min(1, d / 5) : 1.4 * d + 0.8 * n1(x / 5, z / 5);
      if (h > 0) {                 // jointed lava breaks in ledges: soft terraces about 2.4 m high
        const st = 2.4, k = h / st, f = k - Math.floor(k);
        h = 0.35 * h + 0.65 * st * (Math.floor(k) + (f > 0.72 ? (f - 0.72) / 0.28 : 0));
      }
      if (sdPoly(REEF, x, z) > -1 && sdPoly(ISLAND, x, z) < 0) h = Math.min(h, 1.5 + 0.8 * n3(x / 4, z / 4));   // the low tidal reef
      // the station: a levelled yard for the houses, the tower on the summit (corridor at mezzanine level, Hague)
      const dc = sdPoly(COMPOUND, x, z);
      if (dc > -1.5) h = h * (1 - Math.min(1, (dc + 1.5) / 1.5)) + 27.5 * Math.min(1, (dc + 1.5) / 1.5);
      const rt = Math.hypot(x, z);
      if (rt < 6) h = Math.max(h, 30.5 - Math.max(0, rt - 4.2) * 1.7);
      out[j * n + i] = h;
    }
    return out;
  }

  // ---------------------------------------------------------------- the scene shader
  const FRAG = /* glsl */`
uniform sampler2D uRock;
uniform vec4 uRockBox;          // x0, z0, size, texel
uniform vec4 uWall[24];         // compound wall segments: x0, z0, x1, z1
uniform int uNWall;
out vec4 outColor;

const float BIG = 1e9;
const float HOUSE_AZ = 1.92;    // the houses' long axis, bearing 110 deg (chosen; see research note)
const vec3  HOUSE_C = vec3(10.3, -16.4, 3.75);

// ---- intersections (vertical axes through the origin unless stated)
vec2 iCyl(vec3 ro, vec3 rd, float R) {
  float a = dot(rd.xz, rd.xz), b = dot(ro.xz, rd.xz), c = dot(ro.xz, ro.xz) - R * R;
  float h = b * b - a * c; if (h < 0.0 || a < 1e-9) return vec2(BIG);
  h = sqrt(h); return vec2((-b - h) / a, (-b + h) / a);
}
// cone frustum r(y) = r0 + k (y - y0) for y in [y0, y1]; returns the first t > 0 inside the y range; n: outward normal
float iCone(vec3 ro, vec3 rd, float y0, float y1, float r0, float r1, out vec3 n) {
  float k = (r1 - r0) / (y1 - y0);
  float rr = r0 + k * (ro.y - y0);
  float A = dot(rd.xz, rd.xz) - k * k * rd.y * rd.y;
  float B = dot(ro.xz, rd.xz) - k * rr * rd.y;
  float C = dot(ro.xz, ro.xz) - rr * rr;
  float h = B * B - A * C; if (h < 0.0 || abs(A) < 1e-9) return BIG;
  h = sqrt(h);
  float ts[2]; ts[0] = (-B - h) / A; ts[1] = (-B + h) / A;
  if (ts[0] > ts[1]) { float s = ts[0]; ts[0] = ts[1]; ts[1] = s; }
  for (int i = 0; i < 2; i++) {
    float t = ts[i]; if (t <= 1e-3) continue;
    vec3 p = ro + rd * t;
    if (p.y < y0 || p.y > y1 || r0 + k * (p.y - y0) < 0.0) continue;
    vec2 rad = normalize(p.xz + 1e-6);
    n = normalize(vec3(rad.x, -k, rad.y));
    return t;
  }
  return BIG;
}
float iDisc(vec3 ro, vec3 rd, float y, float r0, float r1) {
  if (abs(rd.y) < 1e-6) return BIG;
  float t = (y - ro.y) / rd.y; if (t <= 1e-3) return BIG;
  float r = length((ro + rd * t).xz); return (r >= r0 && r <= r1) ? t : BIG;
}
float iSphere(vec3 ro, vec3 rd, vec3 c, float R) {
  vec3 o = ro - c; float b = dot(o, rd), h = b * b - dot(o, o) + R * R;
  if (h < 0.0) return BIG; float t = -b - sqrt(h); return t > 1e-3 ? t : BIG;
}
float iBox(vec3 ro, vec3 rd, vec3 bmin, vec3 bmax, out vec3 n) {
  vec3 inv = 1.0 / rd, t0 = (bmin - ro) * inv, t1 = (bmax - ro) * inv;
  vec3 tn = min(t0, t1), tf = max(t0, t1);
  float a = max(max(tn.x, tn.y), tn.z), b = min(min(tf.x, tf.y), tf.z);
  if (a > b || b < 1e-3 || a < 1e-3) return BIG;
  n = -sign(rd) * step(tn.yzx, tn.xyz) * step(tn.zxy, tn.xyz);
  return a;
}
// convex polytope from up to 5 planes n.p <= d
float iConvex5(vec3 ro, vec3 rd, vec4 P[5], out vec3 nOut) {
  float a = -BIG, b = BIG; vec3 na = vec3(0.0, 1.0, 0.0);
  for (int i = 0; i < 5; i++) {
    float dn = dot(P[i].xyz, rd), dist = P[i].w - dot(P[i].xyz, ro);
    if (abs(dn) < 1e-9) { if (dist < 0.0) return BIG; continue; }
    float t = dist / dn;
    if (dn < 0.0) { if (t > a) { a = t; na = P[i].xyz; } } else b = min(b, t);
  }
  if (a > b || a < 1e-3) return BIG;
  nOut = normalize(na); return a;
}

// ---- the rock heightfield
float rockH(vec2 xz) {
  vec2 uv = (xz - uRockBox.xy) / uRockBox.z;
  if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) return -20.0;
  return texture(uRock, uv).r;
}
float iRock(vec3 ro, vec3 rd, float tMax) {
  vec3 bmin = vec3(uRockBox.x, LT_SEA - 0.5, uRockBox.y), bmax = vec3(uRockBox.x + uRockBox.z, LT_SEA + 33.5, uRockBox.y + uRockBox.z);
  vec3 inv = 1.0 / rd, t0 = (bmin - ro) * inv, t1 = (bmax - ro) * inv;
  vec3 tn = min(t0, t1), tf = max(t0, t1);
  float a = max(max(max(tn.x, tn.y), tn.z), 0.0), b = min(min(min(tf.x, tf.y), tf.z), tMax);
  if (a >= b) return BIG;
  float t = a, prev = a, dPrev = 1.0;
  for (int i = 0; i < 140; i++) {
    vec3 p = ro + rd * t;
    float d = p.y - (LT_SEA + rockH(p.xz));
    if (d < 0.0) {             // refine between prev and t
      float lo = prev, hi = t;
      for (int k = 0; k < 6; k++) { float m = 0.5 * (lo + hi); vec3 q = ro + rd * m; if (q.y - (LT_SEA + rockH(q.xz)) < 0.0) hi = m; else lo = m; }
      return hi;
    }
    prev = t;
    t += clamp(d * 0.45, 0.05 + 0.002 * t, 8.0);
    if (t > b) break;
  }
  return BIG;
}
vec3 rockN(vec2 xz) {
  float e = uRockBox.w;
  float hx = rockH(xz + vec2(e, 0.0)) - rockH(xz - vec2(e, 0.0));
  float hz = rockH(xz + vec2(0.0, e)) - rockH(xz - vec2(0.0, e));
  vec3 n = normalize(vec3(-hx, 2.0 * e, -hz));
  // fine relief: fissures and blocks smaller than a texel
  vec3 q = vec3(xz, 0.0) * 0.9;
  float a = texture(uLightNoise, vec3(xz * 0.021, 0.3)).r, b = texture(uLightNoise, vec3(xz * 0.021 + 0.013, 0.3)).r, c = texture(uLightNoise, vec3(xz * 0.021, 0.313)).r;
  return normalize(n + 0.18 * vec3(b - a, 0.0, c - a));
}

// ---- materials
const int M_NONE = 0, M_SEA = 1, M_ROCK = 2, M_WHITE = 3, M_IRON = 4, M_LENS = 5, M_ROOFIN = 6, M_SLATE = 7, M_BRASS = 8, M_FLOOR = 9, M_PAINT = 10,
          M_HOUSE = 11, M_STACK = 12, M_WALL = 13;

struct Hit { float t; vec3 n; int m; int face; };
void take(inout Hit h, float t, vec3 n, int m) { if (t < h.t) { h.t = t; h.n = n; h.m = m; h.face = -1; } }

vec3 houseLocal(vec3 p) {   // into the houses' frame: x along the long axis (toward bearing 110), z across
  vec3 q = p - HOUSE_C; float c = cos(HOUSE_AZ - 1.5707963), s = sin(HOUSE_AZ - 1.5707963);
  return vec3(c * q.x + s * q.z, q.y, -s * q.x + c * q.z);
}
vec3 houseWorldDir(vec3 d) { float c = cos(HOUSE_AZ - 1.5707963), s = sin(HOUSE_AZ - 1.5707963); return vec3(c * d.x - s * d.z, d.y, s * d.x + c * d.z); }

Hit traceSolid(vec3 ro, vec3 rd, float t) {
  Hit h; h.t = BIG; h.n = vec3(0.0, 1.0, 0.0); h.m = M_NONE; h.face = -1;
  vec3 n;
  // sea
  if (rd.y < 0.0) take(h, (LT_SEA - ro.y) / rd.y, vec3(0.0, 1.0, 0.0), M_SEA);
  // rock
  float tr = iRock(ro, rd, h.t); if (tr < h.t) { vec3 p = ro + rd * tr; take(h, tr, rockN(p.xz), M_ROCK); }
  // tower: very slightly tapering granite, whitewashed; corbelled cornice; gallery
  float tt = iCone(ro, rd, -13.4, -2.75, 3.15, 2.95, n); take(h, tt, n, M_WHITE);
  tt = iCone(ro, rd, -2.75, -2.42, 2.95, 3.40, n); take(h, tt, n, M_WHITE);
  vec2 c = iCyl(ro, rd, 3.40); { vec3 p = ro + rd * c.x; if (c.x > 1e-3 && p.y > -2.42 && p.y < -2.30) take(h, c.x, vec3(normalize(p.xz).x, 0.0, normalize(p.xz).y), M_WHITE); }
  take(h, iDisc(ro, rd, -2.30, 2.18, 3.40), vec3(0.0, 1.0, 0.0), M_PAINT);
  // lantern: iron lower wall, floor inside, roof cone (outside and in), ball vent and finial
  c = iCyl(ro, rd, 2.18);
  for (int i = 0; i < 2; i++) { float tc = i == 0 ? c.x : c.y; vec3 p = ro + rd * tc;
    if (tc > 1e-3 && p.y > -2.30 && p.y < LT_Y_GLAZE0) { vec3 nn = vec3(normalize(p.xz).x, 0.0, normalize(p.xz).y); take(h, tc, i == 0 ? nn : -nn, M_PAINT); break; } }
  take(h, iDisc(ro, rd, LT_Y_GLAZE0, 0.55, 2.18), vec3(0.0, 1.0, 0.0), M_FLOOR);
  take(h, iDisc(ro, rd, LT_Y_GLAZE0, 2.13, 2.30), vec3(0.0, 1.0, 0.0), M_PAINT);
  tt = iCone(ro, rd, LT_Y_GLAZE1, 3.22, 2.34, 0.0, n);
  if (tt < h.t) take(h, tt, dot(n, rd) < 0.0 ? n : -n, dot(n, rd) < 0.0 ? M_PAINT : M_ROOFIN);
  c = iCyl(ro, rd, 2.34); { vec3 p = ro + rd * c.x; if (c.x > 1e-3 && p.y > LT_Y_GLAZE1 - 0.06 && p.y < LT_Y_GLAZE1 + 0.10) take(h, c.x, vec3(normalize(p.xz).x, 0.0, normalize(p.xz).y), M_PAINT); }
  take(h, iDisc(ro, rd, LT_Y_GLAZE1 - 0.06, 0.0, 2.34), vec3(0.0, -1.0, 0.0), M_ROOFIN);
  tt = iSphere(ro, rd, vec3(0.0, 3.46, 0.0), 0.27); if (tt < h.t) take(h, tt, normalize(ro + rd * tt - vec3(0.0, 3.46, 0.0)), M_PAINT);
  c = iCyl(ro, rd, 0.07); { vec3 p = ro + rd * c.x; if (c.x > 1e-3 && p.y > 3.15 && p.y < 3.30) take(h, c.x, vec3(normalize(p.xz).x, 0.0, normalize(p.xz).y), M_PAINT); }
  c = iCyl(ro, rd, 0.022); { vec3 p = ro + rd * c.x; if (c.x > 1e-3 && p.y > 3.70 && p.y < 4.35) take(h, c.x, vec3(normalize(p.xz).x, 0.0, normalize(p.xz).y), M_IRON); }
  // inside: the pedestal, the lamp's chimney, the brass rings of the band, and the band itself (8 faces)
  c = iCyl(ro, rd, 0.50); { vec3 p = ro + rd * c.x; if (c.x > 1e-3 && p.y > LT_Y_GLAZE0 && p.y < -0.52) take(h, c.x, vec3(normalize(p.xz).x, 0.0, normalize(p.xz).y), M_BRASS); }
  c = iCyl(ro, rd, 0.05); { vec3 p = ro + rd * c.x; if (c.x > 1e-3 && p.y > 0.52 && p.y < 1.75) take(h, c.x, vec3(normalize(p.xz).x, 0.0, normalize(p.xz).y), M_BRASS); }
  for (int s = -1; s <= 1; s += 2) {
    float y0 = s < 0 ? -0.55 : LT_LENS_H, y1 = s < 0 ? -LT_LENS_H : 0.55;
    c = iCyl(ro, rd, 1.02); vec3 p = ro + rd * c.x;
    if (c.x > 1e-3 && p.y > y0 && p.y < y1) take(h, c.x, vec3(normalize(p.xz).x, 0.0, normalize(p.xz).y), M_BRASS);
    take(h, iDisc(ro, rd, s < 0 ? -0.55 : 0.55, 0.0, 1.02), vec3(0.0, float(s), 0.0), M_BRASS);
  }
  {
    float a0 = beamAz(t), sect = LT_TAU / LT_N;
    vec4 P[5]; float tn = -BIG, tf = BIG; int fk = -1; vec3 nk = vec3(0.0);
    for (int k = 0; k < 8; k++) {
      vec3 nn = bearingDir(a0 + float(k) * sect);
      float dn = dot(nn, rd), dist = LT_R_LENS - dot(nn, ro);
      if (abs(dn) < 1e-9) { if (dist < 0.0) { tn = BIG; } continue; }
      float tk = dist / dn;
      if (dn < 0.0) { if (tk > tn) { tn = tk; fk = k; nk = nn; } } else tf = min(tf, tk);
    }
    // the y caps
    if (abs(rd.y) > 1e-9) { float ta = (-LT_LENS_H - ro.y) / rd.y, tb = (LT_LENS_H - ro.y) / rd.y;
      if (min(ta, tb) > tn) { tn = min(ta, tb); fk = -2; } tf = min(tf, max(ta, tb)); }
    else if (abs(ro.y) > LT_LENS_H) tn = BIG;
    if (tn < tf && tn > 1e-3 && tn < h.t) { h.t = tn; h.n = fk >= 0 ? nk : vec3(0.0, sign(-rd.y), 0.0); h.m = fk >= 0 ? M_LENS : M_BRASS; h.face = fk; }
  }
  // the keepers' houses: a pair under one hipped slate roof, a chimney stack, the corridor to the tower
  {
    vec3 lo = houseLocal(ro), ld = houseLocal(ro + rd) - lo;
    vec3 nl; float tb = iBox(lo, ld, vec3(-6.5, 0.0, -4.0), vec3(6.5, 6.0, 4.0), nl);
    if (tb < h.t) take(h, tb, houseWorldDir(nl), M_HOUSE);
    float k = 0.7; vec4 P[5];
    P[0] = vec4(0.0, -1.0, 0.0, -6.0);
    P[1] = vec4(0.0, 1.0, k, 6.0 + 4.3 * k); P[2] = vec4(0.0, 1.0, -k, 6.0 + 4.3 * k);
    P[3] = vec4(k, 1.0, 0.0, 6.0 + 6.8 * k); P[4] = vec4(-k, 1.0, 0.0, 6.0 + 6.8 * k);
    tb = iConvex5(lo, ld, P, nl); if (tb < h.t) take(h, tb, houseWorldDir(nl), M_SLATE);
    // a pair of stacks on the ridge over the party wall (the postcard shows two close together; Cadw: an axial stack)
    for (int i = -1; i <= 1; i += 2) {
      float cx = 0.78 * float(i);
      tb = iBox(lo, ld, vec3(cx - 0.42, 7.5, -0.34), vec3(cx + 0.42, 9.95, 0.34), nl); if (tb < h.t) take(h, tb, houseWorldDir(nl), M_STACK);
      tb = iBox(lo, ld, vec3(cx - 0.49, 9.95, -0.41), vec3(cx + 0.49, 10.12, 0.41), nl); if (tb < h.t) take(h, tb, houseWorldDir(nl), M_STACK);
      for (int j = -1; j <= 1; j += 2) {       // two clay pots on each
        vec3 pc = vec3(cx + 0.19 * float(j), 0.0, 0.0);
        vec3 o = lo - pc; float a = dot(ld.xz, ld.xz), b = dot(o.xz, ld.xz), cc = dot(o.xz, o.xz) - 0.11 * 0.11, hh = b * b - a * cc;
        if (hh > 0.0) { float tp = (-b - sqrt(hh)) / a; float yy = lo.y + ld.y * tp;
          if (tp > 1e-3 && yy > 10.12 && yy < 10.55 && tp < h.t) { vec3 q = o + ld * tp; take(h, tp, houseWorldDir(normalize(vec3(q.x, 0.0, q.z))), M_PAINT); } }
      }
    }
    // the corridor to the tower ("a wide corridor connecting it with the dwellings", Hague), under a small slate roof
    tb = iBox(lo, ld, vec3(-9.2, 0.0, -1.5), vec3(-6.4, 4.6, 1.5), nl); if (tb < h.t) take(h, tb, houseWorldDir(nl), M_HOUSE);
    vec4 Q[5];
    Q[0] = vec4(0.0, -1.0, 0.0, -4.6); Q[1] = vec4(0.0, 1.0, 0.6, 4.6 + 1.75 * 0.6); Q[2] = vec4(0.0, 1.0, -0.6, 4.6 + 1.75 * 0.6);
    Q[3] = vec4(1.0, 0.0, 0.0, -6.2); Q[4] = vec4(-1.0, 0.0, 0.0, 9.6);
    tb = iConvex5(lo, ld, Q, nl); if (tb < h.t) take(h, tb, houseWorldDir(nl), M_SLATE);
  }
  // the compound wall: low, limewashed rubble
  for (int i = 0; i < 24; i++) {
    if (i >= uNWall) break;
    vec4 w = uWall[i]; vec2 a = w.xy, b = w.zw, e = b - a; float L = length(e); vec2 u = e / L, v = vec2(-u.y, u.x);
    vec3 o = ro - vec3(a.x, 0.0, a.y);
    vec3 lo = vec3(dot(o.xz, u), o.y, dot(o.xz, v)), ld = vec3(dot(rd.xz, u), rd.y, dot(rd.xz, v));
    vec3 nl; float tw = iBox(lo, ld, vec3(-0.3, -30.0, -0.3), vec3(L + 0.3, -14.9, 0.3), nl);
    if (tw < h.t) take(h, tw, vec3(nl.x * u.x + nl.z * v.x, nl.y, nl.x * u.y + nl.z * v.y), M_WALL);
  }
  return h;
}

// ---- the thin layers: railing and glazing bars (coverage, filtered by pixel footprint)
float pxAngle() { return 2.0 * uTanHalfFov / uRes.y; }
float barCov(float x, float halfw, float fw) { return ltBarCov(x, halfw, fw); }
float railCov(vec3 p, float fw) { return ltRailCov(p, fw); }
float glazeCov(vec3 p, float fw) { return ltGlazeCov(p, fw); }

// ---- shading
vec3 skyL(vec3 rd) {
  float e = max(rd.y, 0.0);
  float night = 0.0016 * (0.7 + 0.3 * (1.0 - e));
  float day = LT_DAWN_L * 1.25 * (1.0 + 2.0 * e) / 3.0 * (1.0 + 0.12 * max(0.0, dot(normalize(rd.xz + 1e-6), normalize(vec2(0.94, 0.34)))));
  return vec3(night + uLightDawn * day);
}
// irradiance on a surface: lamp light (directional, from the flame) + the lit mist's ambient + the morning sky
float surfE(vec3 p, vec3 n, float t, bool inside) {
  float r = length(p); vec3 l = -p / max(r, 1e-3);
  float direct;
  if (inside) {   // inside the lantern: the flame's own light reaches every surface outside the band's shadow
    float se = p.y / max(r, 1e-3);
    direct = ltBeamE(p, t) + LT_IF * 0.5 / max(r * r, 0.2) * smoothstep(0.42, 0.46, abs(se)) + ltGlowE(p);
  } else direct = ltLampE(p, t);
  float amb = ltAmbE(r) * (0.55 + 0.45 * n.y);
  return uLightLamp * (direct * max(dot(n, l), 0.0) + amb) + uLightDawn * LT_DAWN_E * (0.55 + 0.45 * n.y);
}
float gPoint = 0.0;   // how far the lantern is drawn as a point (when it is only a few pixels across)
// The flash as seen from a point c far off: the face nearest c's bearing, its flame image (no ring errors: averaged)
float flashFrom(vec3 c, float t) {
  float sect = LT_TAU / LT_N, a0 = beamAz(t), az = atan(c.x, -c.z);
  float a = a0 + floor((az - a0) / sect + 0.5) * sect;
  vec3 ax = bearingDir(a), eh = vec3(cos(a), 0.0, sin(a)), v = normalize(c);
  float va = max(dot(v, ax), 1e-3);
  vec2 off = LT_FOCAL * vec2(dot(v, eh), v.y) / va;
  float core = smoothstep(1.25, 0.75, length(off / vec2(LT_FLAME_R, LT_FLAME_H)));
  return core + 0.0026 * exp(-dot(off, off) / (16.0 * LT_FOCAL * LT_FOCAL * LT_BETA * LT_BETA));
}
vec3 shadeLens(vec3 p, vec3 rd, int k, float t) {
  float a0 = beamAz(t) + float(k) * LT_TAU / LT_N;
  vec3 ax = bearingDir(a0), eh = vec3(cos(a0), 0.0, sin(a0));
  vec3 v = -rd;
  float va = max(dot(v, ax), 1e-3);
  vec2 off = LT_FOCAL * vec2(dot(v, eh), v.y) / va;           // where in the focal plane this direction looks
  vec2 uv = vec2(dot(p, eh), p.y);                            // position on the face
  float rr = length(uv);
  float ring = floor(rr / 0.048);
  float seg = floor((atan(uv.y, uv.x) + 3.14159) / (LT_TAU / (6.0 + 2.0 * ring)));
  float hr = hash1(uint(ring) * 131u + uint(k) * 977u), hs = hash1(uint(ring) * 31u + uint(seg) * 7u + uint(k) * 389u + 5u);
  vec2 err = (vec2(hr, hs) - 0.5) * 0.026;                    // an old cemented lens: each ring and piece a little off
  vec2 q = (off + err) / vec2(LT_FLAME_R, LT_FLAME_H);
  float core = smoothstep(1.25, 0.75, length(q));
  float wing = 0.0026 * exp(-dot(off, off) / (16.0 * LT_FOCAL * LT_FOCAL * LT_BETA * LT_BETA));
  float joint = 1.0 - 0.6 * (1.0 - smoothstep(0.0, 0.004, abs(mod(rr, 0.048) - 0.024) - 0.020));
  // off the axis the lens still glows: the flame's light caught and scattered in each ring's edges and joints (chosen)
  float edge = pow(max(0.0, 1.0 - abs(fract(rr / 0.048) - 0.5) * 2.0), 8.0);
  float glass = (0.15 + 0.3 * hs + 3.0 * edge) * (0.6 + 0.4 * exp(-dot(off, off) / 0.09));
  return vec3(uLightLamp * (LT_FLAME_L * 0.8 * (core * joint + wing) * (1.0 - gPoint) + glass));
}
vec3 shadeSea(vec3 p, vec3 rd, float t) {
  // waves under a S.E. force 4: crests across the wind, and smaller choppy ones
  vec2 w = normalize(LT_WIND.xz); vec2 x = p.xz - LT_WIND.xz * 0.0;
  float ph1 = dot(x, w) * 0.33 - 1.6 * t, ph2 = dot(x, vec2(w.y, -w.x) * 0.6 + w * 0.8) * 0.71 - 2.4 * t;
  vec2 g = w * 0.33 * 0.30 * cos(ph1) + (vec2(w.y, -w.x) * 0.6 + w * 0.8) * 0.71 * 0.10 * cos(ph2);
  vec3 nq = vec3(x * 0.11, t * 0.25);
  g += 0.12 * vec2(texture(uLightNoise, nq + vec3(0.01, 0.0, 0.0)).r - texture(uLightNoise, nq).r, texture(uLightNoise, nq + vec3(0.0, 0.01, 0.0)).r - texture(uLightNoise, nq).r);
  vec3 n = normalize(vec3(-g.x, 1.0, -g.y));
  vec3 v = -rd, l = normalize(-p);
  vec3 hv = normalize(v + l);
  float nh = max(dot(n, hv), 1e-3), m2 = 0.02;
  float D = exp(-(1.0 - nh * nh) / (nh * nh * m2)) / (PI * m2 * nh * nh * nh * nh);
  float F = 0.02 + 0.98 * pow(1.0 - max(dot(hv, v), 0.0), 5.0);
  float spec = uLightLamp * F * D * ltLampE(p, t) / (4.0 * max(dot(n, v), 0.05));
  vec3 rdir = reflect(rd, n); rdir.y = abs(rdir.y);
  float Fv = 0.02 + 0.98 * pow(1.0 - max(dot(n, v), 0.0), 5.0);
  float body = 0.012 * surfE(p, vec3(0.0, 1.0, 0.0), t, false) / PI;
  // white water where the swell meets the rock
  float hr = rockH(p.xz);
  float foam = smoothstep(-5.0, -0.3, hr) * smoothstep(0.35, 0.75, texture(uLightNoise, vec3(p.xz * 0.09, t * 0.12)).r * 0.25 + 0.5 + 0.2 * sin(t * 0.9 + hr));
  return vec3(spec + Fv * skyL(rdir).r + body + foam * 0.55 * surfE(p, vec3(0.0, 1.0, 0.0), t, false) / PI);
}
// ---- the houses' fronts: openings, sashes, doors, render lines and weather. lp, ln in the houses' frame; fw = the
// pixel's footprint (m). Returns (albedo, glass: 1 where the eye meets window glass).
float rect(vec2 q, vec4 r, float fw) {         // coverage of the rectangle r = (u0, v0, u1, v1), filtered
  vec2 a = clamp((q - r.xy) / fw + 0.5, 0.0, 1.0) * clamp((r.zw - q) / fw + 0.5, 0.0, 1.0); return a.x * a.y;
}
float lineCov(float x, float period, float halfw, float fw) { return barCov(mod(x + 0.5 * period, period) - 0.5 * period, halfw, fw); }
vec2 windowAt(vec2 q, vec4 r, float fw, inout float stain) {
  // a sash window in a plain opening: painted frame, two sashes of 3 x 2 panes (six over six), a slate sill below,
  // tooled dressings round it; the sill sheds water down the wall below it
  float inO = rect(q, r, fw);
  float w = r.z - r.x, hgt = r.w - r.y;
  vec2 l = (q - r.xy) / vec2(w, hgt);
  float frame = 1.0 - rect(q, vec4(r.xy + 0.06, r.zw - 0.06), fw);
  float meet = barCov(q.y - (r.y + 0.5 * hgt), 0.03, fw);
  float vb = max(barCov(q.x - (r.x + w / 3.0), 0.013, fw), barCov(q.x - (r.x + 2.0 * w / 3.0), 0.013, fw));
  float hb = max(barCov(q.y - (r.y + 0.25 * hgt), 0.013, fw), barCov(q.y - (r.y + 0.75 * hgt), 0.013, fw));
  float wood = max(frame, max(meet, max(vb, hb)));
  float recess = 0.55 + 0.45 * smoothstep(0.0, 0.25, (r.w - q.y));          // the head of the reveal shades the top
  float sill = rect(q, vec4(r.x - 0.08, r.y - 0.09, r.z + 0.08, r.y), fw);
  float dress = rect(q, vec4(r.x - 0.16, r.y - 0.09, r.z + 0.16, r.w + 0.18), fw) * (1.0 - inO) * (1.0 - sill);
  float below = step(q.y, r.y - 0.09) * smoothstep(0.0, 0.25, min(q.x - r.x, r.z - q.x) + 0.1);
  stain = max(stain, below * 0.32 * exp(-(r.y - q.y) / 1.1) * (0.6 + 0.4 * sin(q.x * 23.0 + q.y * 3.0)));
  float alb = mix(mix(1.0, 0.76, 0.0), 0.0, 0.0);
  // compose: outside the opening -> wall (marked by -1), sill, dressings; inside -> glass or painted wood
  float a = -1.0, g = 0.0;
  if (sill > 0.0) a = mix(-1.0, 0.30, sill);
  if (dress > 0.0 && a < 0.0) a = -2.0 - dress;          // dressing: a slightly brighter, smoother wall
  if (inO > 0.0) { float glass = (1.0 - wood) * inO; a = mix(0.78, 0.035 * recess, glass); g = glass; }
  return vec2(a, g);
}
vec2 doorAt(vec2 q, vec4 r, float fw, inout float stain) {
  float inO = rect(q, r, fw);
  if (inO <= 0.0) { float dress = rect(q, vec4(r.x - 0.16, r.y, r.z + 0.16, r.w + 0.2), fw); return vec2(dress > 0.0 ? -2.0 - dress : -1.0, 0.0); }
  float w = r.z - r.x, hgt = r.w - r.y;
  float frame = 1.0 - rect(q, vec4(r.x + 0.07, r.y, r.z - 0.07, r.w - 0.07), fw);
  // four sunk panels in a dark painted door
  float px = q.x - (r.x + 0.5 * w), py = q.y - r.y;
  float panel = rect(vec2(abs(px), py), vec4(0.09, 0.18, 0.5 * w - 0.17, 0.5 * hgt - 0.08), fw) + rect(vec2(abs(px), py), vec4(0.09, 0.5 * hgt + 0.08, 0.5 * w - 0.17, hgt - 0.22), fw);
  float a = mix(mix(0.13, 0.09, panel), 0.78, frame);
  return vec2(a, 0.0);
}
vec2 facade(vec3 lp, vec3 ln, float fw) {
  vec2 q; float face;                  // q = (along the wall, height above the yard)
  if (abs(ln.z) > 0.7) { q = vec2(lp.x * sign(ln.z), lp.y); face = ln.z > 0.0 ? 0.0 : 1.0; }
  else if (abs(ln.x) > 0.7) { q = vec2(-lp.z * sign(ln.x), lp.y); face = ln.x > 0.0 ? 2.0 : 3.0; }
  else return vec2(-1.0, 0.0);
  bool corridor = lp.x < -6.45;
  float stain = 0.0; vec2 r = vec2(-1.0, 0.0);
  vec2 o;
  if (corridor) {
    if (face == 0.0 || face == 1.0) { o = windowAt(q, vec4(-7.95 * sign(ln.z) - 0.35, 1.7, -7.95 * sign(ln.z) + 0.35, 2.7), fw, stain); if (o.x > -1.0 || o.x < -1.5) r = o; }
  } else if (face == 0.0) {            // the front (S.S.W.): a door and a window below, two windows above, each house
    for (int i = -1; i <= 1; i += 2) {
      float sx = float(i);
      o = doorAt(q, vec4(sx * 1.25 - 0.48, 0.0, sx * 1.25 + 0.48, 2.15), fw, stain); if (o.x != -1.0) r = o;
      o = windowAt(q, vec4(sx * 4.3 - 0.48, 0.95, sx * 4.3 + 0.48, 2.40), fw, stain); if (o.x != -1.0) r = o;
      o = windowAt(q, vec4(sx * 1.25 - 0.45, 3.55, sx * 1.25 + 0.45, 4.80), fw, stain); if (o.x != -1.0) r = o;
      o = windowAt(q, vec4(sx * 4.3 - 0.45, 3.55, sx * 4.3 + 0.45, 4.80), fw, stain); if (o.x != -1.0) r = o;
    }
  } else if (face == 1.0) {            // the back (N.N.E.), into the weather: smaller and fewer
    for (int i = -1; i <= 1; i += 2) {
      float sx = float(i);
      o = windowAt(q, vec4(sx * 2.6 - 0.36, 1.10, sx * 2.6 + 0.36, 2.10), fw, stain); if (o.x != -1.0) r = o;
      o = windowAt(q, vec4(sx * 2.6 - 0.40, 3.60, sx * 2.6 + 0.40, 4.70), fw, stain); if (o.x != -1.0) r = o;
    }
  } else if (face == 2.0) {            // the east end
    o = windowAt(q, vec4(-0.40, 1.00, 0.40, 2.20), fw, stain); if (o.x != -1.0) r = o;
    o = windowAt(q, vec4(-0.40, 3.60, 0.40, 4.70), fw, stain); if (o.x != -1.0) r = o;
  } else {                             // the west end, over the corridor
    for (int i = -1; i <= 1; i += 2) { o = windowAt(q, vec4(float(i) * 2.6 - 0.40, 3.60, float(i) * 2.6 + 0.40, 4.70), fw, stain); if (o.x != -1.0) r = o; }
  }
  // the wall: lined-out render (incised to look like ashlar, Cadw), weathered
  float top = corridor ? 4.6 : 6.0;
  float course = floor(q.y / 0.34);
  float lines = max(lineCov(q.y, 0.34, 0.006, fw), lineCov(q.x + 0.33 * mod(course, 2.0), 0.66, 0.006, fw));
  float n = texture(uLightNoise, vec3(q * 0.35, face * 0.31)).r, n2 = texture(uLightNoise, vec3(q * vec2(2.2, 0.25), face * 0.17 + 0.5)).r;
  float eaves = 0.30 * smoothstep(-0.3, 1.0, n2) * exp(-(top - q.y) / 1.6);          // runs from the eaves
  float damp = 0.30 * (1.0 - smoothstep(0.0, 0.7, q.y + 0.25 * n));                // splash and rising damp
  float shade = 0.82 + 0.18 * smoothstep(0.0, 0.35, top - q.y);                     // under the eaves
  float wall = 0.74 * (1.0 - 0.06 * n) * (1.0 - 0.12 * lines) * (1.0 - stain) * (1.0 - eaves) * (1.0 - damp) * shade;
  if (r.x == -1.0) return vec2(wall, 0.0);
  if (r.x < -1.5) return vec2(mix(wall, 0.78 * shade * (1.0 - damp), clamp(-r.x - 2.0, 0.0, 1.0)), 0.0);   // dressings
  return vec2(r.x * (r.x > 0.5 ? (1.0 - 0.5 * eaves) * shade : 1.0), r.y);
}
float slateAlb(vec3 lp, vec3 ln, float fw) {
  // Welsh slate in courses (about 0.22 m to the weather): a shadow line at each slate's tail, staggered joints, each
  // slate its own grey; lead on the hips and ridge
  float along = abs(ln.z) > abs(ln.x) ? lp.x : lp.z;
  float yy = lp.y / 0.126;
  float course = floor(yy);
  float tail = barCov(fract(yy) * 0.126 - 0.012, 0.012, fw);
  float jx = along / 0.30 + 0.5 * mod(course, 2.0);
  float joint = barCov((fract(jx) - 0.5) * 0.30, 0.004, fw) * 0.0 + barCov(fract(jx) * 0.30 - 0.0, 0.005, fw);
  float hs = hash2i(ivec2(int(floor(jx)), int(course) + 4000));
  float hc = hash1(uint(course + 7000.0));
  float a = 0.095 * (0.75 + 0.5 * hs) * (0.9 + 0.2 * hc) * (1.0 - 0.6 * max(tail, joint));
  bool main = lp.x > -6.3;
  if (main) {
    float hip = abs((4.3 - abs(lp.z)) - (6.8 - abs(lp.x)));                 // the hip lines
    float ridge = abs(lp.y - (6.0 + 4.3 * 0.7));
    float lead = max(1.0 - smoothstep(0.08, 0.08 + fw, hip), 1.0 - smoothstep(0.06, 0.06 + fw, ridge));
    a = mix(a, 0.17, lead);
  }
  a *= 1.0 + 0.6 * smoothstep(1.4, 2.4, texture(uLightNoise, lp * 0.6).r * 1.5 + 0.3);   // pale lichen in the sea air
  return a;
}
float albedo(int m, vec3 p) {
  if (m == M_ROCK) {
    float v = texture(uLightNoise, p * 0.05).r, w = texture(uLightNoise, p * 0.37).r;
    return 0.13 * (1.0 + 0.25 * v + 0.15 * w) + 0.10 * smoothstep(1.2, 2.2, v + 0.3 * w);   // dark lava, pale lichen
  }
  if (m == M_WHITE) {   // the tower: whitewashed render; rust runs from the gallery's ironwork, damp at the foot
    float a = 0.72 * (1.0 - 0.08 * texture(uLightNoise, p * 0.4).r);
    if (length(p.xz) < 3.5 && p.y < -2.4) {
      float ang = atan(p.z, p.x);
      float col = texture(uLightNoise, vec3(ang * 3.0, p.y * 0.04, 0.7)).r;
      float rust = 0.32 * smoothstep(0.2, 1.4, col) * exp(-(-2.75 - p.y) / 2.2);
      float damp = 0.25 * (1.0 - smoothstep(-13.4, -12.6, p.y + 0.3 * col));
      a *= (1.0 - rust) * (1.0 - damp);
    }
    return a;
  }
  if (m == M_WALL) {    // limewashed rubble: rough coursed stones, dark joints, a rounded coping
    float c = floor(p.y / 0.24);
    float st = (p.x * 0.707 + p.z * 0.707) / (0.38 + 0.15 * hash1(uint(c + 900.0)));
    float hs = hash2i(ivec2(int(floor(st + 0.5 * c)), int(c)));
    float joint = max(1.0 - smoothstep(0.02, 0.05, fract(p.y / 0.24) * 0.24), 1.0 - smoothstep(0.02, 0.06, fract(st + 0.5 * c) * 0.4));
    float a = 0.62 * (0.88 + 0.2 * hs) * (1.0 - 0.35 * joint);
    a *= 1.0 - 0.15 * (1.0 - smoothstep(-16.6, -15.9, p.y));
    return p.y > -15.1 ? 0.68 : a;
  }
  if (m == M_STACK) return 0.10 * (1.0 + 0.3 * texture(uLightNoise, p * 0.9).r);  // tarred black (Cadw: "black axial stack")
  if (m == M_PAINT) {   // the lantern's iron lower wall keeps "the original brass vent covers" (Hague); eight, round (chosen)
    float r = length(p.xz);
    if (r > 2.15 && r < 2.21 && p.y > -2.3 && p.y < -0.93) {
      float ang = atan(p.z, p.x), sect = 6.2831853 / 8.0;
      vec2 q = vec2((mod(ang + 0.5 * sect, sect) - 0.5 * sect) * 2.18, p.y + 1.62);
      float d = length(q);
      if (d < 0.13) return d > 0.105 ? 0.18 : 0.36 - 0.12 * step(0.5, fract(q.y * 18.0));   // a rim, and louvres
    }
    return 0.55;
  }
  if (m == M_IRON) return 0.10;
  if (m == M_SLATE) return 0.09;
  if (m == M_BRASS) return 0.30;
  if (m == M_FLOOR) return 0.25;
  if (m == M_ROOFIN) return 0.60;
  return 0.2;
}

void main() {
  float t = uTl;
  vec3 ro = uCamPos, rd = cameraRay(gl_FragCoord.xy);
  float jit = fract(52.9829189 * fract(dot(gl_FragCoord.xy, vec2(0.06711056, 0.00583715))));
  float dL = length(ro), pxa = pxAngle();
  gPoint = 1.0 - smoothstep(2.0 * pxa, 5.0 * pxa, 1.84 / dL);
  Hit h = traceSolid(ro, rd, t);
  vec3 col; float tEnd;
  if (h.t < BIG * 0.5) {
    vec3 p = ro + rd * h.t;
    tEnd = h.t;
    if (h.m == M_SEA) col = shadeSea(p, rd, t);
    else if (h.m == M_LENS) col = shadeLens(p, rd, h.face, t);
    else {
      bool inside = length(p.xz) < LT_R_GLAZE + 0.01 && p.y > LT_Y_GLAZE0 - 0.01 && p.y < 3.3 && h.m != M_PAINT || h.m == M_ROOFIN;
      float alb = albedo(h.m, p), glass = 0.0;
      if (h.m == M_HOUSE || h.m == M_SLATE) {
        vec3 lp = houseLocal(p), ln = normalize(houseLocal(p + h.n) - lp);
        float fw = pxAngle() * h.t;
        if (h.m == M_HOUSE) { vec2 f = facade(lp, ln, fw); alb = f.x; glass = f.y; }
        else alb = slateAlb(lp, ln, fw);
      }
      col = vec3(alb / PI * surfE(p + h.n * 0.02, h.n, t, inside));
      if (h.m == M_SLATE) col += 0.04 * skyL(reflect(rd, h.n)) * uLightDawn;
      if (glass > 0.0) col += glass * (0.04 + 0.5 * pow(1.0 - max(dot(-rd, h.n), 0.0), 5.0)) * skyL(reflect(rd, h.n));
    }
    // the print cannot hold a lit lantern's range: surfaces roll off toward paper white (the lens flash is left whole)
    if (h.m != M_LENS) col = col / (1.0 + col / 6.0);
  } else { tEnd = 6000.0; col = skyL(rd); }

  // the mist between the camera and whatever the ray ends on
  vec4 m = ltMarch(ro, rd, tEnd, t, 40, jit);
  col = m.rgb + m.a * col;

  // thin layers in front of the solid: railing (two crossings) and glazing (two crossings), back to front. Each is
  // composited over the finished ray with its own mist in front: cov (front + T x layer) + (1 - cov) behind. (Cut 2 and
  // before blended them in before the mist's transmittance over the whole ray, so against the sky, 6 km of mist
  // multiplied the rail away: it showed only where the lighthouse was behind it.)
  float fwk = pxAngle();
  vec2 cr = iCyl(ro, rd, LT_R_RAIL), cg = iCyl(ro, rd, LT_R_GLAZE);
  float lt[4]; int lk[4];
  lt[0] = cr.y; lk[0] = 0; lt[1] = cg.y; lk[1] = 1; lt[2] = cg.x; lk[2] = 1; lt[3] = cr.x; lk[3] = 0;
  for (int i = 0; i < 4; i++) {        // already ordered far to near for a ray from outside both cylinders
    float tl = lt[i]; if (tl <= 1e-3 || tl >= tEnd || tl > BIG * 0.5) continue;
    vec3 p = ro + rd * tl, nr = vec3(normalize(p.xz).x, 0.0, normalize(p.xz).y);
    float fw = fwk * tl;
    float Tf = exp(-ltTau(ro, p));
    vec3 Vf = m.rgb * clamp((1.0 - Tf) / max(1.0 - m.a, 1e-4), 0.0, 1.0);   // the in-scatter in front, pro rata
    if (lk[i] == 0) {
      float cov = railCov(p, fw);
      if (cov > 0.0) col = mix(col, Vf + Tf * vec3(0.10 / PI * surfE(p, -rd, t, false)), cov);
    } else if (p.y > LT_Y_GLAZE0 && p.y < LT_Y_GLAZE1) {
      // glass: a little lost, and 1% of the light crossing it scattered by salt ("Spray occasionally strikes the
      // lantern", Royal Commission 1861) and lamp smoke (the 1% is chosen): the panes glow where the beams cross them
      float Eg = ltBeamE(p, t) + ltEscE(p) + ltGlowE(p);
      col = col * 0.90 + Tf * vec3(uLightLamp * 0.01 * Eg / PI);
      float cov = glazeCov(p, fw);
      bool farSide = dot(nr, rd) > 0.0;     // seen from inside: its inner face, lit by the lamp
      vec3 nf = farSide ? -nr : nr;
      float Ei = farSide ? uLightLamp * (ltBeamE(p * 0.98, t) + ltEscE(p) + ltGlowE(p)) * 0.5 : surfE(p, nf, t, false);
      if (cov > 0.0) col = mix(col, Vf + Tf * vec3(0.12 / PI * Ei), cov);
    }
  }
  // the lantern far off: a point whose energy is kept whatever its size in pixels (a Gaussian about a pixel wide);
  // the lens face (0.68 m2) at its flash, and the glazing's glow (4.3 x 3 m at radiance ~1.5) between flashes
  if (gPoint > 0.0 && uLightLamp > 0.0) {
    float th = acos(clamp(dot(rd, -ro / dL), -1.0, 1.0)), sg = 0.7 * pxa;
    float psf = exp(-th * th / (2.0 * sg * sg)) / (2.0 * PI * sg * sg);
    float I = LT_FLAME_L * 0.8 * flashFrom(ro, t) * 0.68 + 1.5 * 12.9;     // radiance x area: intensity (per sr)
    col += vec3(gPoint * uLightLamp * I / (dL * dL) * psf * exp(-ltTauR(dL)));
  }
  // the light seen through deep mist: what is scattered forward more than once arrives as a glow round the lamp.
  // Its share of the unattenuated light: exp(-tau (1 - g)) less the unscattered and the once-scattered parts (which
  // the point and the march above already carry); its width grows as sqrt(tau). Negligible within a few hundred m.
  if (uLightLamp > 0.0) {
    float tau = ltTauR(dL);
    float share = max(0.0, exp(-tau * 0.15) - exp(-tau) - tau * exp(-tau));
    if (share > 1e-4) {
      // The profile: a mist droplet (~10 um) sends about half its scattered light into a diffraction peak a few degrees
      // wide (lambda/d ~ 0.06 rad) and the rest over tens of degrees; multiple scattering widens both as sqrt(tau).
      // Half in each, falling exponentially in angle: scales 0.03 and 0.15 sqrt(tau) (3.3 and 16 deg at 5 km; chosen).
      float th = acos(clamp(dot(rd, -ro / dL), -1.0, 1.0)), e1 = 0.03 * sqrt(tau), e2 = 0.15 * sqrt(tau);
      float I = LT_FLAME_L * 0.8 * flashFrom(ro, t) * 0.68 + 1.5 * 12.9;
      float psf = 0.5 * exp(-th / e1) / (2.0 * PI * e1 * e1) + 0.5 * exp(-th / e2) / (2.0 * PI * e2 * e2);
      col += vec3(uLightLamp * share * I / (dL * dL) * psf);
    }
  }
  outColor = vec4(min(col, vec3(60000.0)), 1.0);
  gl_FragDepth = h.t < BIG * 0.5 ? depthOf(ro + rd * h.t) : 1.0;
}
`;

  // ---------------------------------------------------------------- kit
  let prog = null, rockTex = null;
  const walls = [];
  for (let i = 0; i < COMPOUND.length / 2 - 1; i++) walls.push(COMPOUND[2 * i], COMPOUND[2 * i + 1], COMPOUND[2 * i + 2], COMPOUND[2 * i + 3]);
  while (walls.length < 24 * 4) walls.push(0);

  E.chunkFile('light', 'light.glsl');
  E.kit('light', {
    prepare(F) { Object.assign(F.common, L.uniforms(F)); },
    async init(gl, E) {
      const n = 64, data = makeNoise3D(n, 2.0, 1887);
      L.noiseTex = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_3D, L.noiseTex);
      gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
      gl.texImage3D(gl.TEXTURE_3D, 0, gl.R16F, n, n, n, 0, gl.RED, gl.FLOAT, data);
      for (const p of [gl.TEXTURE_WRAP_S, gl.TEXTURE_WRAP_T, gl.TEXTURE_WRAP_R]) gl.texParameteri(gl.TEXTURE_3D, p, gl.REPEAT);
      gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_3D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      L.rockData = makeRock();
      rockTex = E.dataTexture(L.ROCK.n, L.ROCK.n, L.rockData, { filter: gl.LINEAR, wrap: gl.CLAMP_TO_EDGE });
      prog = E.program(FRAG, { use: ['light'] });
    },
    draw(gl, F) {
      E.set(prog, F.common);
      E.set(prog, { uRock: rockTex, uRockBox: [L.ROCK.x0, L.ROCK.z0, L.ROCK.size, L.ROCK.size / L.ROCK.n], uWall: walls, uNWall: COMPOUND.length / 2 - 1 });
      gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.ALWAYS); gl.depthMask(true);
      E.fullscreen(prog);
      gl.depthFunc(gl.LESS);
    },
  });
})();
