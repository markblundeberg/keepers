// chart.js: the night chart for movement II (coordinator, kit D; kit name 'nightchart', since the placeholder's 'chart' is its print calibration chart). The western approaches at night, seen from far
// above as a chart: sea and land as two plate tones and the coast a fine line, and every light on the 1887 lists a
// point flashing at its own recorded character (sketch 1's data: film/engine/assets/night-1887-10-21.json, made by
// tools/sketch_night.py; durations the sources don't state by the rule printed there).
//   A shot using it sets  chart(tl) -> { lon, lat, km }   the frame's centre and its width in kilometres
//                         phase: { stationId: seconds }   where in its cycle a light starts (the phases between
//                                                          lights are not known; unset ones come from a hash)
//   window.CHART = { toScreen(lon, lat, view), view(shot, tl), lights, byId, lampState(light, ts, shot) }
// Projection: Lambert conformal conic, standard parallels 50 and 60 N, central meridian 4 W, as sketch 1.

const R_KM = 6371;
const deg = Math.PI / 180;
const P1 = 50 * deg, P2 = 60 * deg, L0 = -4 * deg, F0 = 55 * deg;
const N = Math.log(Math.cos(P1) / Math.cos(P2)) / Math.log(Math.tan(Math.PI / 4 + P2 / 2) / Math.tan(Math.PI / 4 + P1 / 2));
const FF = Math.cos(P1) * Math.pow(Math.tan(Math.PI / 4 + P1 / 2), N) / N;
const rho = phi => FF / Math.pow(Math.tan(Math.PI / 4 + phi / 2), N), RHO0 = rho(F0);
// projected chart units (earth radii, near true scale between 50 and 60 N), y north
export const project = (lon, lat) => { const p = rho(lat * deg), t = N * (lon * deg - L0); return [p * Math.sin(t), RHO0 - p * Math.cos(t)]; };

// The land texture covers this box (lon/lat); everything outside it is sea.
const BOX = { lon0: -12.5, lon1: 0.5, lat0: 48.8, lat1: 56.6 };
const TEX = 4096;

const LAMP = { white: [1, 1, 1], red: [1.0, 0.22, 0.16], green: [0.25, 1.0, 0.45] };

function hash(s) { let h = 2166136261; for (const ch of s) h = Math.imul(h ^ ch.charCodeAt(0), 16777619); return ((h >>> 0) % 10000) / 10000; }

// brightness (0..1) and colour of a light at real seconds ts (sketch 1's lampState: a revolving beam swells and fades)
export function lampState(l, ts, shot) {
  const L = l.light;
  if (!L || !L.cycle) return [1, (L && L.steps[0][1]) || 'white'];
  const ph0 = shot && shot.phase && l.id in shot.phase ? shot.phase[l.id] : hash(l.id) * L.cycle;
  let ph = ((ts + ph0) % L.cycle + L.cycle) % L.cycle;
  for (const [on, col, sec] of L.steps) {
    if (ph < sec) {
      if (!on) return [0, col];
      if (L.kind === 'revolving') return [Math.pow(Math.sin(Math.PI * ph / sec), 2), col];
      return [1, col];
    }
    ph -= sec;
  }
  return [0, 'white'];
}

const BG_FRAG = `
uniform sampler2D uLand;
uniform vec4 uChart;      // centre x, y (chart units), chart units per pixel, km per pixel
uniform vec4 uBox;       // the land texture's chart-unit box: x0, y0, x1, y1
in vec2 vUv;
out vec4 o;
void main() {
  vec2 px = gl_FragCoord.xy - 0.5 * uRes;
  vec2 p = uChart.xy + px * uChart.z;
  vec2 uv = (p - uBox.xy) / (uBox.zw - uBox.xy);
  float m = (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0) ? 0.0 : texture(uLand, uv).r;
  // the coast: where the (blurred) mask crosses one half, about a pixel wide whatever the zoom
  float w = max(fwidth(m), 1e-4);
  float line = 1.0 - smoothstep(0.6, 1.4, abs(m - 0.5) / w);
  vec2 km = p * ${R_KM.toFixed(1)};
  // a little mist drifting before the S.E. wind (towards the north-west), on the sea only
  float mist = vnoise2(km / 9.0 + vec2(-0.6, 0.6) * uTl * 0.05) * 0.6 + vnoise2(km / 2.7 + vec2(-1.4, 1.1) * uTl * 0.05) * 0.4;
  float sea = 0.006 * (0.7 + 0.6 * mist);
  float land = 0.016;
  float L = mix(sea, land, smoothstep(0.35, 0.65, m)) + 0.05 * line;
  o = vec4(vec3(L), 1.0);
}`;

const PT_VERT = `
in vec4 a0;   // x, y (chart units), brightness, light-vessel (0/1)
in vec4 a1;   // colour rgb, glow radius in pixels
out vec2 vOff; out vec4 vA; out vec4 vB;
uniform vec4 uChart;
void main() {
  vec2 corner = vec2(gl_VertexID & 1, gl_VertexID >> 1) * 2.0 - 1.0;
  float half_ = a1.w * 7.0 + 4.0;
  vec2 c = (a0.xy - uChart.xy) / uChart.z;
  vec2 px = c + corner * half_;
  gl_Position = vec4(px / (0.5 * uRes), 0.0, 1.0);
  vOff = corner * half_; vA = a0; vB = a1;
}`;
const PT_FRAG = `
in vec2 vOff; in vec4 vA; in vec4 vB;
out vec4 o;
void main() {
  float r = length(vOff);
  float b = vA.z;
  float strength = vA.w > 0.5 ? 0.45 : 1.0;           // a light-vessel's lamp is lower and weaker than a tower's
  float core = exp(-r * r / 1.6) * 60.0;               // the lamp itself: a hard point; the print's halation blooms it
  float glow = exp(-r / max(vB.w, 1.0)) * 0.35;        // its light in the mist round it
  o = vec4(vB.rgb * b * strength * (core + glow), 0.0);
}`;

export async function register(E) {
  const D = await (await fetch(new URL('assets/night-1887-10-21.json', import.meta.url))).json();
  const lights = D.lights.map(l => Object.assign({}, l, { xy: project(l.lon, l.lat), lv: l.kind === 'light-vessel' ? 1 : 0 }));
  const byId = Object.fromEntries(lights.map(l => [l.id, l]));
  // The South Bishop as movement I has it (film/research/south-bishop.md): eight beams, a flash every 20 s lasting
  // about 2.4 s, where sketch 1's rule gives 6 s.
  if (byId['south-bishop']) byId['south-bishop'].light = { kind: 'revolving', cycle: 20, steps: [[1, 'white', 2.4, false], [0, 'white', 17.6, false]] };

  const c0 = project(BOX.lon0, BOX.lat0), c1 = project(BOX.lon1, BOX.lat0), c2 = project(BOX.lon0, BOX.lat1), c3 = project(BOX.lon1, BOX.lat1);
  const xs = [c0[0], c1[0], c2[0], c3[0]], ys = [c0[1], c1[1], c2[1], c3[1]];
  let x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const side = Math.max(x1 - x0, y1 - y0); x1 = x0 + side; y1 = y0 + side;     // square texture, square texels
  const box = [x0, y0, x1, y1];

  const view = (shot, tl) => {
    const v = shot.chart(tl), [cx, cy] = project(v.lon, v.lat);
    return { cx, cy, upp: v.km / R_KM / E.W, kmpp: v.km / E.W };
  };
  const toScreen = (lon, lat, v) => { const [x, y] = project(lon, lat); return [E.W / 2 + (x - v.cx) / v.upp, E.H / 2 - (y - v.cy) / v.upp]; };

  let bg = null, pt = null, land = null, vao = null, buf = null;
  E.kit('nightchart', {
    async init(gl, E) {
      // the land mask, drawn once in chart units (y north, so flipped for the canvas), then blurred a little
      const cv = document.createElement('canvas'); cv.width = cv.height = TEX;
      const g = cv.getContext('2d');
      g.fillStyle = '#000'; g.fillRect(0, 0, TEX, TEX);
      g.filter = 'blur(1.5px)';
      g.beginPath();
      for (const ring of D.coast) ring.forEach(([lo, la], i) => {
        const [x, y] = project(lo, la), u = (x - x0) / side * TEX, w = (1 - (y - y0) / side) * TEX;
        i ? g.lineTo(u, w) : g.moveTo(u, w);
      });
      g.fillStyle = '#fff'; g.fill('evenodd');
      land = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, land);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, cv);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      bg = E.program(BG_FRAG);
      pt = E.program(PT_FRAG, { vert: PT_VERT });
      vao = gl.createVertexArray(); buf = gl.createBuffer();
      gl.bindVertexArray(vao); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      for (let a = 0; a < 2; a++) {
        const loc = gl.getAttribLocation(pt, 'a' + a); if (loc < 0) continue;
        gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 4, gl.FLOAT, false, 32, a * 16); gl.vertexAttribDivisor(loc, 1);
      }
      gl.bindVertexArray(null);
    },
    draw(gl, F) {
      const v = view(F.shot, F.tl);
      const uChart = [v.cx, v.cy, v.upp, v.kmpp];
      E.set(bg, F.common); E.set(bg, { uLand: land, uChart, uBox: box });
      E.fullscreen(bg);
      // the lights: real seconds since the shot began, plus each light's phase
      const ts = (F.shot.clock0 || 0) + F.tl;
      const glowPx = Math.min(9, Math.max(2.2, 0.5 / v.kmpp));   // ~0.5 km of lit mist round a lamp, 2-9 px (wider read as a moon)
      const data = new Float32Array(lights.length * 8);
      lights.forEach((l, i) => {
        const [b, col] = lampState(l, ts, F.shot), c = LAMP[col] || LAMP.white;
        data.set([l.xy[0], l.xy[1], b, l.lv, c[0], c[1], c[2], glowPx], i * 8);
      });
      E.set(pt, F.common); E.set(pt, { uChart });
      gl.bindVertexArray(vao); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, data, gl.DYNAMIC_DRAW);
      gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE);
      gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, lights.length);
      gl.disable(gl.BLEND); gl.bindVertexArray(null);
    },
  });
  globalThis.CHART = { toScreen, view, lights, byId, lampState, project };
}
