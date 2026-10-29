// print.js: radiance in, a mezzotint printed in warm ink on paper out. Owner: A.
// The shader is print.glsl; this file makes the plate (the rocker grain, once per page, seeded), the paper,
// the halation pyramid, and runs the pass. Notes on what the look rests on: ENGINE.md, "The print".
'use strict';
(function () {
  const E = window.ENGINE, gl = E.gl;

  // Print parameters. Per shot: shot.print = {...}; varying in a shot: shot.printAt(tl) => {...};
  // from the URL for tests and variants: ?p.exposure=1.5. Plate parameters (marked PLATE) shape the grain,
  // which is made once per page and fixed to the frame for the whole film; set them only from the URL.
  E.printDefaults = {
    // lens (before the plate)
    exposure: 1.0,       // radiance multiplier
    halation: 1.0,       // glow round bright things (lens and burnished halo), 0 = none
    vignette: 0.30,      // darkening toward the corners
    edgeSoft: 0.6,       // period optics: softer toward the corners
    // burnishing: radiance to how far the plate is burnished (0 = rocked black, 1 = polished to paper)
    gamma: 1.15,         // tone curve power (lower = lifts the darks); burnish = 1 - exp(-2.5 * (exposure*Y)^gamma)
    toe: 0.02,           // the darkest tones are left as the rocked ground: velvet black
    // the screen
    grain: 0.20,         // contrast of the grain, in ink load (0..1)
    grainSym: 0.5,       // 0 = only the surviving pits (specks), 1 = only the ground's texture (velvet)
    grainSoft: 0.15,     // softness of the pit threshold (0 = hard-edged specks)
    grainDrift: 0.0,     // px per second the plate drifts (0 = fixed to the frame, like a print)
    paperTake: 0.05,     // how much the paper's hollows refuse ink (pale specks in the black)
    // ink and paper
    warmth: 0.5,         // 0 = neutral black ink, 1 = strong sepia
    inkMax: 1.0,         // full ink load (1 = darkest black the ink gives)
    plateTone: 0.10,     // film of ink left by the wipe, in the lights (0 = wiped clean)
    paperTex: 1.0,       // paper surface relief in the lights
    // the plate mark
    plateInset: 8,       // px from the frame edge to the plate's edge (0 = no mark)
    plateAspect: 0,      // 0 = the plate fills the frame; 0.8 = a 4:5 plate centred (for the social cut)
    plateMark: 1.0,      // strength of the embossed edge
    // colour: the lamps' red and green as a watercolour wash
    wash: 1.0,
    // PLATE (URL only): the rocker
    grainPitch: 3.4,     // px between teeth: the frame is a detail of a print seen close, as the scans at ~440 ppi
    grainStep: 1.0,      // rock advance, in pitches
    grainPasses: 28,     // directions the rocker was walked
    grainSeed: 1887,
  };
  const plateQ = Object.assign({}, E.printDefaults, E.urlPrint());

  // ---------------------------------------------------------------- the plate: a mezzotint ground
  // Each pass walks the rocker across the plate in one direction; each rock stabs a row of pits, one per tooth,
  // along the blade (perpendicular to the walk). Pit depth varies with the pressure along the blade and from rock to
  // rock. The sum over passes is the depth of the ground at each point. Burnishing flattens the plate from the top,
  // so the shallow pits go first and the deep ones survive into the lights: the print shader inks where depth exceeds
  // the burnish level. The depth is ranked (equalised to uniform on [0,1]) so the mean ink equals the asked tone.
  function makeGround(W, H, q) {
    const rnd = E.rng(q.grainSeed), P = new Float32Array(W * H);
    const N = Math.max(1, Math.round(q.grainPasses));
    for (let k = 0; k < N; k++) {
      // directions spread through the half-turn, in the order an engraver might use: a rose, then between
      const th = Math.PI * ((k * 0.618034) % 1) + (rnd() - 0.5) * Math.PI / N;
      const c = Math.cos(th), s = Math.sin(th);
      const d = q.grainPitch * (1 + 0.06 * E.gauss(rnd)), st = d * q.grainStep * (1 + 0.15 * E.gauss(rnd));
      const su = 0.30 * d, sv = 0.42 * st;                       // pit size: a little longer along the walk
      const iu2 = 1 / (2 * su * su), iv2 = 1 / (2 * sv * sv);
      const R = Math.ceil(Math.max(su, sv) * 2.6);
      const half = Math.hypot(W, H) / 2 + 4, cx = W / 2 + (rnd() - 0.5) * d, cy = H / 2 + (rnd() - 0.5) * d;
      const nRows = Math.ceil(2 * half / st), nTeeth = Math.ceil(2 * half / d);
      const pressPhase = rnd() * 6.283, pressK = (0.5 + rnd()) * 6.283 / (2 * half);
      for (let j = 0; j < nRows; j++) {
        const v = -half + j * st + 0.25 * st * E.gauss(rnd) * 0.5;
        const uOff = rnd() * d;                                  // where the blade sits this rock
        const rock = 0.75 + 0.5 * rnd();                         // this rock's pressure
        for (let i = 0; i < nTeeth; i++) {
          const u = -half + i * d + uOff + 0.08 * d * (rnd() - 0.5);
          const x = cx + u * c - v * s, y = cy + u * s + v * c;
          if (x < -R || y < -R || x > W + R || y > H + R) continue;
          const depth = rock * (0.8 + 0.25 * Math.sin(pressPhase + u * pressK)) * (0.7 + 0.6 * rnd());
          const xi = Math.round(x), yi = Math.round(y);
          for (let dy = -R; dy <= R; dy++) {
            const py = yi + dy; if (py < 0 || py >= H) continue;
            const ry = py - y;
            for (let dx = -R; dx <= R; dx++) {
              const px = xi + dx; if (px < 0 || px >= W) continue;
              const rx = px - x, du = rx * c + ry * s, dv = -rx * s + ry * c;
              const e = du * du * iu2 + dv * dv * iv2;
              if (e < 6) P[py * W + px] += depth * Math.exp(-e);
            }
          }
        }
      }
    }
    return equalise(P);
  }
  function equalise(P) {
    let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < P.length; i++) { const v = P[i]; if (v < lo) lo = v; if (v > hi) hi = v; }
    const B = 65536, hist = new Float64Array(B + 1), sc = (B - 1) / (hi - lo || 1);
    for (let i = 0; i < P.length; i++) hist[Math.floor((P[i] - lo) * sc) + 1]++;
    for (let b = 1; b <= B; b++) hist[b] += hist[b - 1];
    const n = P.length;
    for (let i = 0; i < n; i++) {
      const x = (P[i] - lo) * sc, b = Math.floor(x), f = x - b;
      P[i] = (hist[b] + f * (hist[Math.min(B, b + 1)] - hist[b]) + 0.5) / n;   // rank in (0,1)
    }
    return P;
  }

  // ---------------------------------------------------------------- the paper and the wipe (made once, on the GPU)
  const PAPER_FS = `
in vec2 vUv; out vec4 o;
float fbm(vec2 p) { float a = 0.0, w = 0.5; for (int i = 0; i < 5; i++) { a += w * vnoise2(p); p = p * 2.03 + 17.1; w *= 0.5; } return a; }
void main() {
  vec2 px = gl_FragCoord.xy;
  // wove paper: a felt of short fibres (stretched noise at several angles) over a soft cloudy formation
  float fib = 0.0;
  for (int k = 0; k < 6; k++) {
    float a = float(k) * 0.5236 + 0.3;
    mat2 r = mat2(cos(a), sin(a), -sin(a), cos(a));
    vec2 q = r * px; fib += vnoise2(vec2(q.x / 7.0, q.y / 1.3) + float(k) * 31.7);
  }
  fib /= 6.0;
  float cloud = fbm(px / 90.0);
  float h = 0.5 + 1.6 * (0.6 * (fib - 0.5) + 0.4 * (fbm(px / 3.0 + 9.0) - 0.48));   // fine relief only, mean 0.5
  // the wipe: the printer's hand and tarlatan leave a film of ink in long soft swirls
  vec2 w = px / vec2(${E.W}.0, ${E.H}.0);
  float sw = fbm(vec2(w.x * 3.0 + 0.8 * fbm(w * 2.0), w.y * 9.0 + 2.0 * fbm(w * 3.0 + 4.0)));
  float wipe = smoothstep(0.25, 0.75, sw) * 0.7 + 0.3 * fbm(w * 14.0);
  o = vec4(h, wipe, cloud, 1.0);
}`;

  // ---------------------------------------------------------------- halation pyramid (13-tap down, tent up)
  const DOWN_FS = `
in vec2 vUv; out vec4 o; uniform sampler2D uSrc; uniform vec2 uTexel;
void main() {
  vec2 t = uTexel;
  vec3 a = texture(uSrc, vUv + t * vec2(-2, 2)).rgb, b = texture(uSrc, vUv + t * vec2(0, 2)).rgb, c = texture(uSrc, vUv + t * vec2(2, 2)).rgb;
  vec3 d = texture(uSrc, vUv + t * vec2(-2, 0)).rgb, e = texture(uSrc, vUv).rgb, f = texture(uSrc, vUv + t * vec2(2, 0)).rgb;
  vec3 g = texture(uSrc, vUv + t * vec2(-2, -2)).rgb, h = texture(uSrc, vUv + t * vec2(0, -2)).rgb, i = texture(uSrc, vUv + t * vec2(2, -2)).rgb;
  vec3 j = texture(uSrc, vUv + t * vec2(-1, 1)).rgb, k = texture(uSrc, vUv + t * vec2(1, 1)).rgb;
  vec3 l = texture(uSrc, vUv + t * vec2(-1, -1)).rgb, m = texture(uSrc, vUv + t * vec2(1, -1)).rgb;
  o = vec4(e * 0.125 + (a + c + g + i) * 0.03125 + (b + d + f + h) * 0.0625 + (j + k + l + m) * 0.125, 1.0);
}`;
  const UP_FS = `
in vec2 vUv; out vec4 o; uniform sampler2D uSrc, uBase; uniform vec2 uTexel; uniform float uMix;
void main() {
  vec2 t = uTexel;
  vec3 s = texture(uSrc, vUv).rgb * 4.0;
  s += (texture(uSrc, vUv + vec2(t.x, 0)).rgb + texture(uSrc, vUv - vec2(t.x, 0)).rgb + texture(uSrc, vUv + vec2(0, t.y)).rgb + texture(uSrc, vUv - vec2(0, t.y)).rgb) * 2.0;
  s += texture(uSrc, vUv + t).rgb + texture(uSrc, vUv - t).rgb + texture(uSrc, vUv + vec2(t.x, -t.y)).rgb + texture(uSrc, vUv + vec2(-t.x, t.y)).rgb;
  o = vec4(mix(texture(uBase, vUv).rgb, s / 16.0, uMix), 1.0);
}`;

  let ground, paper, progPaper, progDown, progUp, progPrint, down = [], up = [], emptyType;
  const LEVELS = 6;
  E.printInit = async () => {
    const W = E.W, H = E.H, t0 = performance.now();
    ground = E.dataTexture(W, H, makeGround(W, H, plateQ), { internal: gl.R16F, filter: gl.LINEAR, wrap: gl.REPEAT });
    E.printStats = { groundMs: performance.now() - t0 };
    progPaper = E.program(PAPER_FS);
    paper = E.target(W, H, { internal: gl.RGBA16F });
    E.bind(paper); E.fullscreen(progPaper);
    gl.bindTexture(gl.TEXTURE_2D, paper.tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
    progDown = E.program(DOWN_FS); progUp = E.program(UP_FS);
    let w = W, h = H;
    for (let i = 0; i < LEVELS; i++) { w = Math.max(1, w >> 1); h = Math.max(1, h >> 1); down.push(E.target(w, h)); up.push(E.target(w, h)); }
    const r = await fetch('print.glsl'); if (!r.ok) throw new Error('print.glsl ' + r.status);
    progPrint = E.program(await r.text());
    emptyType = E.dataTexture(1, 1, new Uint8Array([0, 0, 0, 255]), { internal: gl.RGBA8, format: gl.RGBA, type: gl.UNSIGNED_BYTE });
  };

  E.printRun = (F, typeTex) => {
    // halation pyramid from the radiance
    let src = E.hdr;
    for (let i = 0; i < LEVELS; i++) {
      E.bind(down[i]); E.set(progDown, { uSrc: src.tex, uTexel: [1 / src.w, 1 / src.h] }); E.fullscreen(progDown); src = down[i];
    }
    // up[i] = blur of down[i] merged with upsampled coarser level: a wide, smooth glow with a long tail
    let coarse = down[LEVELS - 1];
    for (let i = LEVELS - 2; i >= 0; i--) {
      E.bind(up[i]); E.set(progUp, { uSrc: coarse.tex, uBase: down[i].tex, uTexel: [1 / coarse.w, 1 / coarse.h], uMix: 0.6 }); E.fullscreen(progUp); coarse = up[i];
    }
    const p = F.print, drift = p.grainDrift * F.t;
    E.bind(null);
    E.set(progPrint, Object.assign({}, F.common, {
      uHdr: E.hdr.tex, uGlowNear: down[1].tex, uGlowFar: up[0].tex, uGround: ground, uPaper: paper.tex, uType: typeTex || emptyType,
      uDrift: [drift * 0.83, drift * 0.56],
    }, Object.fromEntries(Object.entries(p).map(([k, v]) => ['p_' + k, v]))));
    E.fullscreen(progPrint);
  };
})();
