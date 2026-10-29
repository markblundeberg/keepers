// birds.js: the birds at the South Bishop lantern, night of 21-22 October 1887 (owner C).
//
// A deterministic, stateless simulation (every bird a pure function of shot-local time and the shot; seeded
// hashes only, nothing carried between frames) and its drawing (birds.glsl), lit only by B's illum(p, t).
// Sources and the status of each behaviour: film/research/birds-at-the-light.md. In short:
//   recorded   - the span (11 P.M. to 2.30 A.M.), the 272 dead by species (Larks 146, Starlings 64,
//                Blackbirds 38, Thrushes 24), "several birds seen on the rock at daylight with broken wings",
//                wind S.E. 4, overcast and misty (BAAS report 1887).
//   literature - strikes come "up the beams" (Eagle Clarke 1912); on the windward side (keepers at Bardsey,
//                Isle of May, Samphire I., Eddystone); Starlings sit on the sills, Skylarks flutter at the glass
//                and sink on the gallery, thrushes glance off (Clarke); circling "against the sun" (Isle of May,
//                1882 report); birds follow the rays (Casquets, 1880 report) and swarm in them (Bell Rock 1884);
//                others cross them "at all angles" (Clarke); dead on the gallery, over the rail, at the tower foot.
//   invented   - every probability, radius, speed while circling and hold time below; the ratio of strikes to
//                deaths; how the dead split between gallery and rock (it comes out of a ballistic fall).
//
// Time. Birds move in real seconds (shot-local tl). The night's clock (shot.hour(tl), which a shot may run
// faster than real time) only decides how thick the birds are and which strikes have happened: a strike
// whose clock time falls in the shot happens at the tl where shot.hour reaches it.
//
// Interface (ES module; also registers the kit 'birds' with ENGINE through register(E)):
//   birdsAt(tl, shot)           -> { n, data: Float32Array(n*STRIDE), list, info }
//   strikeEvents(shot, t0, t1)  -> strikes in shot-local [t0, t1): { t, species, kind, hard, pos, bearingDeg }
//                                  (kinds: dead, glance, perch, injured, flutter-tap, land-gallery, land-rock)
//   strikesUpTo(tl, shot)       -> { dead, strikes }: the night's totals so far (for the tally)
//   ledger(seed)                -> the night's strike ledger (canonical), for checks
// A "shot" here is either the coordinator's shot def (fields hour(tl), density(tl), strikeAt, aftermath, dur)
// with the frame's beam (ctx from the engine), or a test shot { birds: { hour, t0, seed, ... } } for the harness.
// In the page, register() also sets window.BIRDS = { strikeEvents, strikesUpTo, ledger, SPECIES, GEOM }.
//
// World units: metres; origin the flame; y up, x east, z south. Bearings in radians clockwise from north
// (0 = -z, pi/2 = +x).

// ------------------------------------------------------------------------------------------- geometry
// From B's light.glsl / light.js (research/south-bishop.md): glazing, gallery, rail, tower.
export const GEOM = {
  glassR: 2.13, glassY0: -0.93, glassY1: 2.12,
  domeY: 3.2, lowerWallR: 2.18,
  galleryY: -2.30, galleryR: 3.40, railR: 3.33, railY: -1.25,
  towerTopR: 2.95, towerBaseR: 3.15,
  summitY: -13.4, seaY: -43.9,
  sillY: -0.93, sillR: 2.22,          // the ledge at the foot of the glazing (2.13 to 2.30 m)
};
export function setGeometry(g) { Object.assign(GEOM, g); }
// rock height (world y) under (x, z): B's heightfield if loaded, else a stand-in round the summit
function rockYAt(x, z) {
  const L = globalThis.LIGHT;
  if (L && L.rockData && L.ROCK) {
    const { x0, z0, size, n } = L.ROCK;
    const u = (x - x0) / size * n - 0.5, v = (z - z0) / size * n - 0.5;
    const i = Math.max(0, Math.min(n - 2, Math.floor(u))), j = Math.max(0, Math.min(n - 2, Math.floor(v)));
    const fu = Math.min(1, Math.max(0, u - i)), fv = Math.min(1, Math.max(0, v - j));
    const d = L.rockData, h = (a, b) => d[b * n + a];
    const hh = (h(i, j) * (1 - fu) + h(i + 1, j) * fu) * (1 - fv) + (h(i, j + 1) * (1 - fu) + h(i + 1, j + 1) * fu) * fv;
    return (L.SEA ?? GEOM.seaY) + hh;
  }
  const r = Math.hypot(x, z);
  return GEOM.summitY - Math.min(3, Math.max(0, r - 4.2) * 1.7);
}

// The light: eight faces, a flash every 20 s, one turn in 160 s (B's light.js; Findlay 1887; RC 1861).
const N_FACES = 8, PERIOD = 160;
const SECT = 2 * Math.PI / N_FACES, OMEGA = 2 * Math.PI / PERIOD;
const WIND_FROM = 135 * Math.PI / 180;   // S.E. (printed)
const WIND_TO = WIND_FROM + Math.PI;

// ------------------------------------------------------------------------------------------- species
// Speeds/sizes: Alerstam et al. 2007 (Protocol S1); wingbeat: Pennycuick's allometry (computed, not measured);
// shapes, tones, flight style: field-guide knowledge. alb = back, belly = underside (reflectance).
export const SPECIES = [
  { key: 'lark', name: 'Skylark', killed: 146, len: 0.18, span: 0.35, chord: 0.059, tail: 0.36, tailW: 0.55,
    tipR: 0.55, f: 8.6, v: 8.5, alb: 0.30, belly: 0.62, bound: 0.22, run: 1.0, flut: 1.2 },
  { key: 'starling', name: 'Starling', killed: 64, len: 0.21, span: 0.38, chord: 0.064, tail: 0.22, tailW: 0.42,
    tipR: 0.12, f: 10.0, v: 10.0, alb: 0.12, belly: 0.18, bound: 0.0, run: 1.4, flut: 1.0 },
  { key: 'blackbird', name: 'Blackbird', killed: 38, len: 0.25, span: 0.37, chord: 0.080, tail: 0.46, tailW: 0.5,
    tipR: 0.45, f: 10.2, v: 9.0, alb: 0.06, belly: 0.08, bound: 0.12, run: 0.8, flut: 0.7 },
  { key: 'thrush', name: 'Song Thrush', killed: 24, len: 0.23, span: 0.36, chord: 0.061, tail: 0.38, tailW: 0.45,
    tipR: 0.35, f: 10.1, v: 9.0, alb: 0.22, belly: 0.55, bound: 0.15, run: 0.8, flut: 0.7 },
];
const KILLED_TOTAL = SPECIES.reduce((a, s) => a + s.killed, 0);   // 272
const SPECIES_CDF = (() => { let c = 0; return SPECIES.map(s => (c += s.killed / KILLED_TOTAL)); })();
function pickSpecies(u) { for (let i = 0; i < 4; i++) if (u < SPECIES_CDF[i]) return i; return 3; }

// ------------------------------------------------------------------------------------------- hashing
function rnd(a, b, c, d) {      // [0, 1), pure in its integer arguments
  let h = Math.imul(a | 0, 0x9E3779B1) ^ Math.imul((b | 0) + 0x7F4A7C15, 0x85EBCA77);
  h = Math.imul(h ^ (h >>> 15), 0x2C1B3C6D);
  h ^= Math.imul((c | 0) + 0x165667B1, 0xC2B2AE3D);
  h = Math.imul(h ^ (h >>> 13), 0x297A2D39);
  h ^= Math.imul((d | 0) + 0x27D4EB2F, 0x9E3779B1);
  h = Math.imul(h ^ (h >>> 16), 0x85EBCA6B);
  h ^= h >>> 13;
  return (h >>> 0) / 4294967296;
}
function gauss(a, b, c, d) {
  const u = Math.max(1e-9, rnd(a, b, c, d)), v = rnd(a + 1013, b, c, d);
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}
const clamp = (x, a, b) => Math.min(b, Math.max(a, x));
const smooth = (u) => { u = clamp(u, 0, 1); return u * u * (3 - 2 * u); };
const lerp = (a, b, u) => a + (b - a) * u;
const TAU = 2 * Math.PI;
const wrap = (a) => a - TAU * Math.floor(a / TAU);
const wrapSect = (a) => a - SECT * Math.round(a / SECT);     // to (-SECT/2, SECT/2]
const wrapPi = (a) => a - TAU * Math.round(a / TAU);

// ------------------------------------------------------------------------------------------- the night
const H_START = 23.0, H_END = 26.5;     // 11 P.M. to 2.30 A.M. (printed)
const N_PEAK = 600;                     // "hundreds" (printed); the peak value is invented
// Shape of the night for test shots and the ledger (invented: rise from 11, a peak near 1 A.M., thinning to 2.30).
export function nightShape(H) {
  const rise = smooth((H - (H_START - 0.05)) / 1.3);
  const fall = 1 - smooth((H - 25.5) / (H_END + 0.08 - 25.5));
  const bump = 0.8 + 0.2 * Math.exp(-(((H - 25.0) / 0.45) ** 2));
  return clamp(rise * fall * bump, 0, 1);
}

// The context for one frame: clock, density, beam, and the shot's wishes.
//   test shot:   { birds: { hour, t0, seed, only, strikeAt, aftermath, density }, camera: { pos } }  (real-time clock)
//   engine shot: the coordinator's shot def, with eng = { azAt: tl => bearing of face 0, camPos }
function makeCtx(shot, eng) {
  const B = (shot && shot.birds) || {};
  const ctx = { seed: B.seed ?? 1887, only: B.only, camPos: (eng && eng.camPos) || (shot && shot.camera && shot.camera.pos) };
  if (typeof (shot && shot.hour) === 'function') {
    ctx.hour = shot.hour;
    ctx.density = shot.density || (() => 0);
    ctx.strikeAt = shot.strikeAt;
    ctx.aftermath = !!shot.aftermath;
    ctx.dur = shot.dur ?? 1e9;
    ctx.specimens = shot.specimens;
  } else {
    const h0 = B.hour ?? 25, t0 = B.t0 ?? (shot && shot.t0) ?? 0;
    ctx.hour = (tl) => h0 + (tl - t0) / 3600;
    ctx.density = (tl) => (B.density ?? 1) * nightShape(ctx.hour(tl));
    ctx.strikeAt = B.strikeAt;
    ctx.aftermath = !!B.aftermath;
    ctx.dur = B.dur ?? 1e9;
  }
  // the beam: face 0's bearing, linear in tl (as B's LIGHT.beamAz is)
  const az = eng && eng.azAt ? eng.azAt : (tl) => OMEGA * (ctx.hour(0) * 3600 + tl);
  ctx.az0 = az(0); ctx.om = az(1) - az(0);
  ctx.beam = (tl) => ctx.az0 + ctx.om * tl;
  // the clock: hour(tl) taken as linear (true of every shot in shots.js); inverted for strike times
  ctx.H0 = ctx.hour(0); ctx.Hr = ctx.hour(1) - ctx.H0;
  ctx.clockToTl = (Ts) => ctx.Hr > 1e-9 ? (Ts / 3600 - ctx.H0) / ctx.Hr : (Ts / 3600 <= ctx.H0 ? -1e9 : 1e9);
  ctx.K = Math.round(ctx.H0 * 3600) % 100000;           // decorrelates the crowd between shots
  return ctx;
}

// ------------------------------------------------------------------------------------------- the ledger
// Every strike of the night, generated once per seed, in clock seconds (hours x 3600).
//   dead    killed: drops to the gallery or goes over the rail to the rock (272, the printed counts)
//   injured rebounds to the rock, alive with a broken wing ("several": 6, invented)
//   perch   a Starling that sits on the sill until dawn ("a few", Clarke; 8, invented)
//   glance  strikes and flies or flutters off into the dark (2.5 per death, invented)
// Bearings: up a beam (a face's bearing, canonical phase) for two thirds, or blundering in from the circling;
// both weighted to the windward (S.E.) side by rejection sampling.
const LEDGER_CACHE = new Map();
const GLANCE_PER_DEAD = 2.5, N_INJURED = 6, N_PERCH = 8;
const WIND_BIAS = 1.5;
function windWeight(b) { return Math.exp(WIND_BIAS * (Math.cos(b - WIND_FROM) - 1)); }

function sampleNightTime(seed, i, salt) {
  for (let k = 0; k < 64; k++) {
    const H = lerp(H_START, H_END, rnd(seed, i, salt, k * 2));
    if (rnd(seed, i, salt, k * 2 + 1) < nightShape(H)) return H * 3600;
  }
  return 25 * 3600;
}

export function ledger(seed = 1887) {
  const key = seed + (globalThis.LIGHT && globalThis.LIGHT.rockData ? ':rock' : '');
  if (LEDGER_CACHE.has(key)) return LEDGER_CACHE.get(key);
  const plan = [];
  SPECIES.forEach((s, si) => { for (let k = 0; k < s.killed; k++) plan.push({ kind: 'dead', sp: si }); });
  for (let k = 0; k < N_INJURED; k++) plan.push({ kind: 'injured', sp: -1 });
  for (let k = 0; k < N_PERCH; k++) plan.push({ kind: 'perch', sp: 1 });
  const nGlance = Math.round(GLANCE_PER_DEAD * KILLED_TOTAL);
  for (let k = 0; k < nGlance; k++) plan.push({ kind: 'glance', sp: -1 });
  const ev = plan.map((p, i) => {
    let sp = p.sp;
    if (sp < 0) {   // glancing: thrushes "glanced off" more readily (Clarke), weighted up 1.6x
      const w = SPECIES.map((s, j) => s.killed * (j >= 2 ? 1.6 : 1)), tot = w.reduce((a, b) => a + b, 0);
      let u = rnd(seed, i, 7, 0) * tot; sp = 0;
      while (sp < 3 && u >= w[sp]) { u -= w[sp]; sp++; }
    }
    const viaBeam = rnd(seed, i, 8, 0) < 0.68;
    let T = 0, bearing = 0;
    for (let k = 0; k < 200; k++) {
      T = sampleNightTime(seed, i, 100 + k);
      bearing = viaBeam ? wrap(OMEGA * T + SECT * Math.floor(rnd(seed, i, 12, k) * N_FACES)) : wrap(WIND_FROM + gauss(seed, i, 9, k) * 0.9);
      if (rnd(seed, i, 10, k) < windWeight(bearing)) break;
    }
    const S = SPECIES[sp];
    const yS = p.kind === 'injured' ? lerp(-0.4, 0.9, rnd(seed, i, 11, 0))
      : viaBeam ? clamp(gauss(seed, i, 11, 0) * 0.35, -0.7, 0.9) : lerp(GEOM.glassY0 + 0.2, GEOM.glassY1 - 0.2, rnd(seed, i, 11, 0));
    let mode = p.kind;
    if (p.kind === 'dead' && S.key === 'lark' && rnd(seed, i, 13, 0) < 0.45) mode = 'dead-flutter';
    if (p.kind === 'dead' && S.key === 'starling' && rnd(seed, i, 13, 0) < 0.25) mode = 'dead-flutter';
    const e = { id: i, kind: p.kind, mode, sp, T, bearing, yS, viaBeam,
      hard: p.kind === 'glance' ? lerp(0.15, 0.6, rnd(seed, i, 14, 0)) : lerp(0.6, 1.0, rnd(seed, i, 14, 0)),
      flutter: mode === 'dead-flutter' ? lerp(2.0, 7.0, rnd(seed, i, 15, 0)) : (p.kind === 'perch' ? lerp(0.8, 2.5, rnd(seed, i, 15, 0)) : 0) };
    restingPlace(e, seed);
    return e;
  });
  ev.sort((a, b) => a.T - b.T);
  const L = { seed, events: ev, byKind: {} };
  for (const e of ev) L.byKind[e.kind] = (L.byKind[e.kind] || 0) + 1;
  LEDGER_CACHE.set(key, L);
  return L;
}

// Where a struck bird ends up: a ballistic fall from the glass (rebound outward + a little wind drift). If it
// clears the rail it lands on the rock beyond the tower foot, else on the gallery floor.
function restingPlace(e, seed) {
  const G = GEOM, b = e.bearing;
  const out = [Math.sin(b), 0, -Math.cos(b)];
  e.p0 = [out[0] * (G.glassR + 0.1), e.yS, out[2] * (G.glassR + 0.1)];
  e.fall = null; e.rest = null;
  if (e.kind === 'perch') {
    const bb = b + (rnd(seed, e.id, 20, 0) - 0.5) * 0.2;
    e.rest = { x: Math.sin(bb) * G.sillR, y: G.sillY + 0.02, z: -Math.cos(bb) * G.sillR, where: 'sill', yaw: bb + Math.PI };
    return;
  }
  if (e.kind === 'glance') return;
  // injured birds were "seen on the rock": throw harder until they clear the rail; nobody lands inside a building
  for (let attempt = 0; attempt < 8; attempt++) {
    throwFrom(e, seed, attempt);
    const inside = e.rest.where === 'rock' && inStation(e.rest.x, e.rest.z);
    if (!inside && (e.kind !== 'injured' || e.rest.where === 'rock')) break;
  }
  if (e.rest.where === 'rock' && inStation(e.rest.x, e.rest.z)) {
    const q = pushOutOfStation(e.rest.x, e.rest.z); e.rest.x = q[0]; e.rest.z = q[1]; e.rest.y = rockYAt(q[0], q[1]) + 0.03;
  }
}
// B's keepers' houses and the corridor to the tower (light.js: HOUSE_C, HOUSE_AZ and the two boxes), in plan
const HOUSE = { cx: 10.3, cz: 3.75, az: 1.92, boxes: [[-6.5, 6.5, -4.0, 4.0], [-9.2, -6.4, -1.5, 1.5]] };
function houseLocal(x, z) {
  const qx = x - HOUSE.cx, qz = z - HOUSE.cz, c = Math.cos(HOUSE.az - Math.PI / 2), s = Math.sin(HOUSE.az - Math.PI / 2);
  return [c * qx + s * qz, -s * qx + c * qz];
}
function inStation(x, z, m = 0.15) {
  const [lx, lz] = houseLocal(x, z);
  return HOUSE.boxes.some(([x0, x1, z0, z1]) => lx > x0 - m && lx < x1 + m && lz > z0 - m && lz < z1 + m);
}
function pushOutOfStation(x, z) {        // to the foot of the nearest wall, 0.3 m out
  const [lx, lz] = houseLocal(x, z);
  let best = null;
  for (const [x0, x1, z0, z1] of HOUSE.boxes) {
    if (!(lx > x0 - 0.15 && lx < x1 + 0.15 && lz > z0 - 0.15 && lz < z1 + 0.15)) continue;
    for (const [nx, nz] of [[x0 - 0.3, lz], [x1 + 0.3, lz], [lx, z0 - 0.3], [lx, z1 + 0.3]]) {
      const d = Math.hypot(nx - lx, nz - lz); if (!best || d < best[2]) best = [nx, nz, d];
    }
  }
  const c = Math.cos(HOUSE.az - Math.PI / 2), s = Math.sin(HOUSE.az - Math.PI / 2);
  return [HOUSE.cx + c * best[0] - s * best[1], HOUSE.cz + s * best[0] + c * best[1]];
}
function throwFrom(e, seed, attempt) {
  const G = GEOM, i = e.id, b = e.bearing, p0 = e.p0;
  const out = [Math.sin(b), 0, -Math.cos(b)], right = [Math.cos(b), 0, Math.sin(b)];
  let vOut;
  const A = attempt * 101;
  if (e.kind === 'injured') vOut = lerp(2.6, 4.0, rnd(seed, i, 21, 0)) + 0.8 * attempt;
  else if (e.mode === 'dead-flutter' || e.featured) vOut = lerp(0.0, 0.5, rnd(seed, i, 21, A));   // the featured one "fell like stones"
  else vOut = rnd(seed, i, 21, 0) < 0.68 ? lerp(2.3, 4.2, rnd(seed, i, 22, A)) : lerp(0.1, 1.2, rnd(seed, i, 22, A));
  const tang = (rnd(seed, i, 23, A) - 0.5) * 1.2;
  const wd = 0.5;   // drag-limited drift with the wind, m/s (invented)
  const v0 = [out[0] * vOut + right[0] * tang + Math.sin(WIND_TO) * wd, lerp(-0.3, 0.8, rnd(seed, i, 24, 0)),
              out[2] * vOut + right[2] * tang - Math.cos(WIND_TO) * wd];
  const g = 9.81;
  const tTo = (y) => (v0[1] + Math.sqrt(v0[1] ** 2 + 2 * g * Math.max(0, p0[1] - y))) / g;
  const at = (s) => [p0[0] + v0[0] * s, p0[1] + v0[1] * s - 0.5 * g * s * s, p0[2] + v0[2] * s];
  const pr = at(tTo(G.railY));
  let land, tLand, where;
  if (Math.hypot(pr[0], pr[2]) > G.railR) {
    let y = G.summitY;      // over the rail: to the rock, iterating on the rock's height where it lands
    for (let k = 0; k < 4; k++) { tLand = tTo(y); land = at(tLand); y = rockYAt(land[0], land[2]); }
    const rl = Math.hypot(land[0], land[2]), minR = G.towerBaseR + 0.15 + 0.4 * rnd(seed, i, 25, 0);
    if (rl < minR) { const k = minR / Math.max(rl, 1e-3); land[0] *= k; land[2] *= k; }
    land[1] = rockYAt(land[0], land[2]);
    where = 'rock';
  } else {
    tLand = tTo(G.galleryY); land = at(tLand); where = 'gallery';
    // on the walkway, inside the rail: a 20 cm bird's centre at least 15 cm in from the rail (one that clears the rail
    // falls to the rock above); nothing lies on the 7 cm ledge outside it
    const rf = Math.hypot(land[0], land[2]), rl = clamp(rf, G.lowerWallR + 0.1, G.railR - 0.15), k = rl / Math.max(rf, 1e-3);
    land[0] *= k; land[2] *= k; land[1] = G.galleryY;
  }
  e.fall = { v0, tLand };
  const u = rnd(seed, i, 26, 0);
  e.rest = { x: land[0], y: land[1] + 0.03, z: land[2], where, yaw: TAU * rnd(seed, i, 27, 0),
    lie: e.kind === 'injured' ? 'sit' : (u < 0.62 ? 'side' : u < 0.9 ? 'belly' : 'back'),
    wingOut: e.kind === 'injured' ? lerp(0.6, 1.0, rnd(seed, i, 28, 0)) : (rnd(seed, i, 28, 0) < 0.18 ? lerp(0.2, 0.6, rnd(seed, i, 29, 0)) : 0) };
}

// The ledger as one shot sees it. Each event gets its shot-local time. A strike inside the shot's window that came
// up a beam is turned (by at most half the angle between faces) onto the face that is really there then. The
// featured strike (shot.strikeAt) is placed where the camera sees it, and the shot's other strikes are held back.
// Strikes from before the window keep their canonical places, so the dead lie in the same places in every shot.
function shotEvents(ctx) {
  const L = ledger(ctx.seed);
  const out = [];
  let featured = null;
  if (ctx.strikeAt != null) {
    const Hs = ctx.hour(ctx.strikeAt) * 3600;
    for (const e of L.events) if (e.kind === 'dead' && e.mode === 'dead' && SPECIES[e.sp].key !== 'blackbird')
      if (!featured || Math.abs(e.T - Hs) < Math.abs(featured.T - Hs)) featured = e;
  }
  const W0 = -45, W1 = Math.min(ctx.dur, 1e8) + 5;
  for (const e of L.events) {
    const tl = ctx.clockToTl(e.T);
    const inWin = tl > W0 && tl < W1;
    if (e === featured) {
      // The shot's one strike. Up the beam nearest the camera it would be lost in the flash (shots.js has the beam
      // facing the camera 0.5 s before), so this one blunders in from the circling ("crowded on to the lantern
      // windows", Bell Rock 1884; "beat violently against the windows", Clarke): it crosses in front of the camera on
      // its circle, against the sun, and meets the glass about 32 deg round toward the wind, where the glass is dark.
      const cam = ctx.camPos || [0, 0, 10];
      const camB = Math.atan2(cam[0], -cam[2]);
      const side = Math.sin(WIND_FROM - camB) >= 0 ? 1 : -1;
      const f = { ...e, tl: ctx.strikeAt, featured: true, bearing: wrap(camB + side * 0.55), viaBeam: false, mode: 'dead', flutter: 0, yS: 0.45,
        camR: Math.hypot(cam[0], cam[2]), side };
      restingPlace(f, ctx.seed);
      out.push(f);
      continue;
    }
    if (inWin && ctx.strikeAt != null) continue;
    if (inWin && e.viaBeam) {
      const f = { ...e, tl, bearing: wrap(e.bearing + wrapSect(ctx.beam(tl) - e.bearing)) };
      restingPlace(f, ctx.seed);
      out.push(f);
    } else out.push({ ...e, tl });
  }
  return out;
}

// ------------------------------------------------------------------------------------------- the crowd
// NS slots, each hosting a succession of visits (in "motion time" T = tl + ctx.K). Crowd birds never strike
// (strikes are the ledger's), so nothing they do carries forward.
const NS = 1500;
const SLOT_GAP = 4;
function slotPeriod(seed, i) { return lerp(70, 170, rnd(seed, i, 1, 0)); }

let CUR = null;                                           // the frame's ctx (set by birdsAt)
const beamAt = (T, K) => CUR.beam(T - K);                 // bearing of face 0 at motion time T

function buildVisit(seed, i, k, Ts, D, T1, K) {
  const r = (a, b) => rnd(seed, i, k, a * 977 + b);
  const sp = pickSpecies(r(1, 0));
  const S = SPECIES[sp];
  const v = S.v * lerp(0.85, 1.15, r(2, 0));
  const visit = { sp, legs: [], Ts, Te: Ts + D, f: S.f * lerp(1.0, 1.25, r(3, 0)), ph: r(4, 0), alb: lerp(0.8, 1.2, r(5, 0)), id: i * 7919 + ((k % 7919) + 7919) % 7919, K };
  if (S.key === 'blackbird' && r(6, 0) < 0.5) visit.alb *= 2.0;      // females are brown
  const far = 160;     // where a visit begins and ends: under a pixel at the film's lenses, so nobody sees it start
  // most keep near the lamp's height ("the madding crowd in the illumined zone"), some flit above and below in
  // the semi-darkness (Clarke 1912, p. 291); the spread is invented
  const yMean = clamp(gauss(seed, i, k, 8) * (r(31, 0) < 0.7 ? 2.2 : 6.0) + 0.3, GEOM.summitY + 3, 16);
  // heading on: W.N.W., the wind on the shoulder (invented; 1880: birds at South Bishop "flying N.W." on a S.E. wind)
  const headTo = (295 + gauss(seed, i, k, 9) * 35) * Math.PI / 180;
  if (r(7, 0) < 0.22) {
    // crossing the rays without staying: a straight pass
    const dmin = lerp(3.5, 40, r(10, 0) ** 1.5) * (r(11, 0) < 0.5 ? -1 : 1);
    const dir = [Math.sin(headTo), 0, -Math.cos(headTo)], perp = [-dir[2], 0, dir[0]];
    const p = [perp[0] * dmin - dir[0] * far, yMean + gauss(seed, i, k, 12) * 3, perp[2] * dmin - dir[2] * far];
    const q = [perp[0] * dmin * 0.6 + dir[0] * far, yMean + gauss(seed, i, k, 13) * 3, perp[2] * dmin * 0.6 + dir[2] * far];
    const len = Math.hypot(q[0] - p[0], q[1] - p[1], q[2] - p[2]);
    visit.legs.push({ type: 'line', t0: Ts, t1: Ts + len / (v * 1.25), p, q });
    visit.Te = Ts + len / (v * 1.25);
    return visit;
  }
  const fromB = WIND_FROM + gauss(seed, i, k, 14) * 0.8;     // arriving with the wind, from the E.S.E. side
  let th = wrap(fromB + gauss(seed, i, k, 15) * 0.5);
  let rr = clamp(6 + 26 * r(16, 0) ** 1.6 + 3 * gauss(seed, i, k, 17), 3.6, 45);
  let yy = yMean;
  const p = [Math.sin(fromB) * far, yMean + gauss(seed, i, k, 18) * 4, -Math.cos(fromB) * far];
  const q = orbitPos(th, rr, yy, [0, 0, 0]);
  let t = Ts + Math.hypot(q[0] - p[0], q[1] - p[1], q[2] - p[2]) / v;
  visit.legs.push({ type: 'line', t0: Ts, t1: t, p, q });
  let sgn = r(19, 0) < 0.72 ? -1 : 1;                  // most "against the sun": anticlockwise from above
  const tLeave = visit.Te - lerp(6, 10, r(20, 0));
  let j = 0;
  while (t < tLeave && t < T1 + 0.5 && j < 600) {
    j++;
    const kj = k * 1000 + j;
    const rj = (a) => rnd(seed, i, kj, a);
    if (rj(1) < 0.08) sgn = -sgn;
    let rT = clamp(rr * lerp(0.7, 1.35, rj(2)) + gauss(seed, i, kj, 3) * 2, 3.6, 48);
    let yT = clamp(yy + gauss(seed, i, kj, 4) * 1.4 + (yMean - yy) * 0.4, GEOM.summitY + 2.5, 18);
    const om = sgn * v * lerp(0.8, 1.15, rj(5)) / Math.max(rr, 3);
    // next crossing of any face
    const rel = om - CUR.om;
    const d0 = th - beamAt(t, K);
    const ds = d0 - SECT * Math.floor(d0 / SECT);        // [0, SECT)
    let dtc = Infinity;
    if (Math.abs(rel) > 1e-3) {
      dtc = rel < 0 ? ds / -rel : (SECT - ds) / rel;
      if (dtc < 0.08) dtc += SECT / Math.abs(rel);
    }
    const dtr = -Math.log(1 - rj(6) * 0.999) * 2.6 + 0.6;
    const L = Math.min(dtc, dtr, tLeave - t);
    rT = rr + clamp(rT - rr, -3 * L, 3 * L);
    yT = yy + clamp(yT - yy, -1.5 * L, 1.5 * L);
    visit.legs.push({ type: 'orbit', t0: t, t1: t + L, th0: th, om, r0: rr, r1: rT, y0: yy, y1: yT });
    th = wrap(th + om * L); rr = rT; yy = yT; t += L;
    if (L === dtc && t < tLeave) {
      const face = Math.round((th - beamAt(t, K)) / SECT);
      const pr = rj(7);
      // following the beam round ("the larger birds follow the rays", Casquets, 1880 report; "swarmed in the rays
      // of light", Bell Rock 1884): milling in it, to and fro across it and in and out along it
      const pFol = 0.24 * S.flut * (rr < 32 ? 1 : 0.4);
      const pRun = 0.018 * S.run * (rr < 30 ? 1 : 0.2) * (0.6 + 0.8 * windWeight(th));
      if (pr < pFol) {
        const h = lerp(1.0, 7.0, rj(8) ** 1.5);
        const off = (rj(9) - 0.5) * 0.6 / Math.max(rr, 3);
        const r1 = clamp(rr * lerp(0.6, 1.0, rj(10)), 3.4, 48);
        const y1 = clamp(lerp(yy, 0.2, lerp(0.2, 0.7, rj(11))) + (rj(16) - 0.5), GEOM.summitY + 3, 18);
        // amplitudes and periods keep each to and fro under ~6-8 m/s (invented)
        const A = lerp(0.5, 1.2, rj(17)) / Math.max(rr, 3), Pf = lerp(1.2, 2.4, rj(18)), phi = TAU * rj(19);
        const Ar = lerp(0.8, 2.5, rj(20)), Pr = lerp(2.0, 3.5, rj(21)), phr = TAU * rj(22);
        visit.legs.push({ type: 'beam', t0: t, t1: t + h, face, off, r0: rr, r1, y0: yy, y1, flutter: 1, A, Pf, phi, Ar, Pr, phr });
        t += h; rr = r1; yy = y1; th = wrap(beamAt(t, K) + face * SECT + off);
      } else if (pr < pFol + pRun && rr > GEOM.glassR + 6) {
        // "streaks of approaching light": up the beam, then recovering, out of the ray (Clarke 1912, p. 291)
        const vr = lerp(5, 8, rj(12));
        const rv = lerp(GEOM.glassR + 1.2, GEOM.glassR + 4.5, rj(13));
        const off = (rj(9) - 0.5) * 0.04;
        const y1 = lerp(yy, clamp(gauss(seed, i, kj, 14) * 0.6, -0.8, 1.2), 0.8);
        const h = Math.max(0.3, (rr - rv) / vr, Math.abs(y1 - yy) / 2.5);
        visit.legs.push({ type: 'beam', t0: t, t1: t + h, face, off, r0: rr, r1: rv, y0: yy, y1, flutter: 0 });
        t += h; rr = rv; yy = y1; th = wrap(beamAt(t, K) + face * SECT + off);
        sgn = rj(15) < 0.5 ? -1 : 1;
      }
    }
  }
  const p2 = orbitPos(th, rr, yy, [0, 0, 0]);
  const q2 = [Math.sin(headTo) * far + p2[0] * 0.3, yy + gauss(seed, i, k, 30) * 4, -Math.cos(headTo) * far + p2[2] * 0.3];
  const lenD = Math.hypot(q2[0] - p2[0], q2[1] - p2[1], q2[2] - p2[2]);
  visit.legs.push({ type: 'line', t0: t, t1: t + lenD / v, p: p2, q: q2 });
  visit.Te = t + lenD / v;
  return visit;
}

// the circling centre sits a little downwind (birds holding station against a S.E. 4; invented)
const DRIFT = [Math.sin(WIND_TO), 0, -Math.cos(WIND_TO)];
function orbitPos(th, r, y, out, ds = 1) {
  const dd = 0.07 * r * ds;
  out[0] = Math.sin(th) * r + DRIFT[0] * dd; out[1] = y; out[2] = -Math.cos(th) * r + DRIFT[2] * dd;
  return out;
}
function weave(id, T, out, amp) {         // a small irregular weave: birds don't fly on rails
  const a = (id % 997) * 0.37, b = (id % 991) * 0.53;
  out[0] += amp * (Math.sin(1.7 * T + a) * 0.6 + Math.sin(3.9 * T + b) * 0.25);
  out[1] += amp * (Math.sin(1.3 * T + b) * 0.5 + Math.sin(4.7 * T + a) * 0.2);
  out[2] += amp * (Math.sin(2.1 * T + a * 1.3) * 0.6 + Math.sin(3.3 * T + b * 0.7) * 0.25);
  return out;
}
function evalVisit(V, T, out) {
  const legs = V.legs;
  let L = legs[legs.length - 1];
  for (let n = 0; n < legs.length; n++) if (T < legs[n].t1) { L = legs[n]; break; }
  const u = clamp((T - L.t0) / Math.max(1e-6, L.t1 - L.t0), 0, 1);
  let mode = 0;
  if (L.type === 'line') {
    const s = smooth(u) * 0.3 + u * 0.7;
    out[0] = lerp(L.p[0], L.q[0], s); out[1] = lerp(L.p[1], L.q[1], s); out[2] = lerp(L.p[2], L.q[2], s);
  } else if (L.type === 'orbit') {
    orbitPos(L.th0 + L.om * (T - L.t0), lerp(L.r0, L.r1, smooth(u)), lerp(L.y0, L.y1, smooth(u)), out, L.land ? 1 - u : 1);
  } else {
    const env = smooth(u / 0.15) * (1 - smooth((u - 0.85) / 0.15));
    let th = beamAt(T, V.K) + (L.face || 0) * SECT + L.off * smooth(u / 0.3);
    let rr = lerp(L.r0, L.r1, L.flutter ? smooth(u) : u);
    if (L.A) th += L.A * Math.sin(TAU * (T - L.t0) / L.Pf + L.phi) * env;
    if (L.Ar) rr += L.Ar * Math.sin(TAU * (T - L.t0) / L.Pr + L.phr) * env;
    orbitPos(th, rr, lerp(L.y0, L.y1, smooth(u)), out, L.land ? 1 - u : 1);
    mode = L.flutter ? 1 : 0;
  }
  weave(V.id, T, out, (L.type === 'beam' && L.flutter ? 0.35 : 0.22) * (L.land ? 1 - smooth(u) : 1));
  return mode;
}

// ------------------------------------------------------------------------------------------- ledger birds
// A struck bird's path, built backward from its strike at shot-local time e.tl (motion time with K = 0).
function ledgerBird(e, seed) {
  const i = e.id, r = (a) => rnd(seed, 50000 + i, a, 3);
  const S = SPECIES[e.sp];
  const v = S.v * lerp(0.9, 1.1, r(1));
  let runSpeed = lerp(6, 9, r(2));
  let r0 = lerp(7, 20, r(3));
  if (e.featured) { r0 = GEOM.glassR + 1.6; runSpeed = 4.0; }
  const tRun = (r0 - (GEOM.glassR + 0.12)) / runSpeed;
  const T2 = e.tl, T1 = T2 - tRun;
  const y0 = clamp(e.yS + gauss(seed, 50000 + i, 4, 3) * Math.min(3, 1.5 * tRun), GEOM.summitY + 3, 12);
  const legs = [];
  if (e.viaBeam) {
    const face = Math.round((e.bearing - CUR.beam(T2)) / SECT);
    legs.push({ type: 'beam', t0: T1, t1: T2, face, off: 0, r0, r1: GEOM.glassR + 0.12, y0, y1: e.yS, flutter: 0, land: true });
  } else {
    const om = (e.featured ? e.side : (r(5) < 0.7 ? -1 : 1)) * (e.featured ? 6 : v) / ((r0 + GEOM.glassR) * 0.5);
    legs.push({ type: 'orbit', t0: T2 - tRun * 1.6, t1: T2, th0: e.bearing - om * tRun * 1.6, om, r0, r1: GEOM.glassR + 0.12, y0, y1: e.yS, land: true });
  }
  const first = legs[0];
  const thA = first.type === 'beam' ? CUR.beam(first.t0) + first.face * SECT : first.th0;
  const circ = e.featured ? 2.5 : lerp(4, 14, r(6));
  const omC = (e.featured ? e.side : (r(7) < 0.72 ? -1 : 1)) * (e.featured ? 6 : v) / r0;
  legs.unshift({ type: 'orbit', t0: first.t0 - circ, t1: first.t0, th0: thA - omC * circ, om: omC, r0: r0 * lerp(0.8, 1.3, r(8)), r1: r0, y0: y0 + gauss(seed, 50000 + i, 9, 3) * 2, y1: y0 });
  const L0 = legs[0];
  const pq = orbitPos(L0.th0, L0.r0, L0.y0, [0, 0, 0]);
  const fromB = WIND_FROM + gauss(seed, 50000 + i, 10, 3) * 0.8;
  const pp = [Math.sin(fromB) * 160, L0.y0 + gauss(seed, 50000 + i, 11, 3) * 3, -Math.cos(fromB) * 160];
  const lenA = Math.hypot(pq[0] - pp[0], pq[1] - pp[1], pq[2] - pp[2]);
  legs.unshift({ type: 'line', t0: L0.t0 - lenA / v, t1: L0.t0, p: pp, q: pq });
  return { e, sp: e.sp, legs, Ts: legs[0].t0, K: 0, f: S.f * lerp(1.0, 1.2, r(12)), ph: r(13),
    alb: lerp(0.8, 1.2, r(14)) * (S.key === 'blackbird' && r(15) < 0.5 ? 2.0 : 1), id: 900000 + i };
}
// a bird that struck long before: only its resting state matters
function restingBird(e, seed) {
  const r = (a) => rnd(seed, 50000 + e.id, a, 3), S = SPECIES[e.sp];
  return { e, sp: e.sp, legs: [], Ts: -1e9, K: 0, f: S.f, ph: 0, alb: lerp(0.8, 1.2, r(14)) * (S.key === 'blackbird' && r(15) < 0.5 ? 2.0 : 1), id: 900000 + e.id };
}

// pose: 0 flying, 1 lying, 2 sitting (perched starling / injured), 3 at the glass (fluttering)
function evalLedgerBird(B, T, st) {
  const e = B.e, G = GEOM;
  st.pose = 0; st.fold = 0; st.flutter = 0; st.wingOut = 0; st.lie = 0; st.yaw = 0; st.visible = true; st.tumble = -1;
  if (T < e.tl) { evalVisit(B, T, st.p); return st; }
  const dt = T - e.tl, b = e.bearing;
  const out = [Math.sin(b), 0, -Math.cos(b)], right = [Math.cos(b), 0, Math.sin(b)];
  if (e.kind === 'glance') {
    // glanced off "a little stunned or quite uninjured": tumbles a little, recovers, flies off into the dark
    const r = (a) => rnd(B.id, e.id, a, 77);
    const drop = lerp(0.5, 5, r(1)) * e.hard, away = lerp(4, 8, r(2)), side = (r(3) - 0.5) * 2;
    const d = Math.min(dt, 12);
    st.p[0] = e.p0[0] + out[0] * away * d + right[0] * side * d * 1.5;
    st.p[2] = e.p0[2] + out[2] * away * d + right[2] * side * d * 1.5;
    st.p[1] = e.p0[1] - drop * (1 - Math.exp(-d * 2.2)) + 0.3 * Math.max(0, d - 1);
    st.flutter = dt < 0.7 ? 1 : 0;
    st.visible = dt < 12;
    return st;
  }
  if (e.flutter && dt < e.flutter) {
    // at the glass, beating against it (Clarke: Skylarks "fluttered violently against the glass for a time")
    const s = dt / e.flutter;
    const env = smooth(dt / 0.25) * (1 - smooth((s - 0.8) / 0.2));
    const jit = (Math.sin(dt * 7.3 + e.id) * 0.12 + Math.sin(dt * 3.1 + e.id * 0.7) * 0.08) * env;
    const yTarget = e.kind === 'perch' ? e.rest.y + 0.06 : e.yS - 0.4;
    const rr = G.glassR + 0.1 + 0.05 * Math.abs(Math.sin(dt * 9 + e.id)) * env;
    st.p[0] = out[0] * rr + right[0] * jit; st.p[2] = out[2] * rr + right[2] * jit;
    st.p[1] = lerp(e.yS, yTarget, smooth(s)) + 0.05 * Math.sin(dt * 5 + e.id) * env;
    if (e.kind === 'perch') { const w = smooth((s - 0.7) / 0.3); st.p[0] = lerp(st.p[0], e.rest.x, w); st.p[1] = lerp(st.p[1], e.rest.y, w); st.p[2] = lerp(st.p[2], e.rest.z, w); }
    st.pose = 3; st.flutter = 1; st.face = b + Math.PI;
    return st;
  }
  const dt2 = dt - (e.flutter || 0);
  if (e.kind === 'perch') { st.p[0] = e.rest.x; st.p[1] = e.rest.y; st.p[2] = e.rest.z; st.pose = 2; st.yaw = e.rest.yaw; st.fold = 1; return st; }
  const fall = e.fall;
  if (dt2 < fall.tLand) {
    const p0 = e.flutter ? [out[0] * (G.glassR + 0.1), e.yS - 0.4, out[2] * (G.glassR + 0.1)] : e.p0;
    const v0 = fall.v0, g = 9.81;
    st.p[0] = p0[0] + v0[0] * dt2; st.p[1] = p0[1] + v0[1] * dt2 - 0.5 * g * dt2 * dt2; st.p[2] = p0[2] + v0[2] * dt2;
    const s = smooth((dt2 - fall.tLand * 0.6) / (fall.tLand * 0.4));
    st.p[0] = lerp(st.p[0], e.rest.x, s); st.p[2] = lerp(st.p[2], e.rest.z, s);
    st.p[1] = Math.max(st.p[1], e.rest.y);
    st.fold = e.kind === 'injured' ? 0.4 : 0.85; st.tumble = dt2;
    return st;
  }
  st.p[0] = e.rest.x; st.p[1] = e.rest.y; st.p[2] = e.rest.z; st.yaw = e.rest.yaw;
  if (e.kind === 'injured') { st.pose = 2; st.fold = 1; st.wingOut = e.rest.wingOut; return st; }
  st.pose = 1; st.fold = 1; st.wingOut = e.rest.wingOut;
  st.lie = e.rest.lie === 'side' ? 1 : e.rest.lie === 'back' ? 2 : 0;
  return st;
}

// ------------------------------------------------------------------------------------------- output
// STRIDE floats per bird (instanced attributes a0..a4 in birds.glsl):
//  0-3 pos.xyz, species | 4-7 vel.xyz, wing phase | 8-11 wing freq, fold, pose, seed
// 12-15 roll, yaw, wingOut, albedo scale | 16-19 flutter, lie, tumble (s since the fall began, -1 none), fade
export const STRIDE = 20;

export function birdsAt(tl, shot = {}, eng) {
  const ctx = makeCtx(shot, eng);
  CUR = ctx;
  const seed = ctx.seed, list = [], eps = 0.02;
  if (ctx.specimens) return specimenTray(ctx);
  if (!ctx.aftermath) {     // the crowd
    const T = tl + ctx.K;
    for (let i = 0; i < NS; i++) {
      const P = slotPeriod(seed, i), off = P * rnd(seed, i, 2, 0);
      const k = Math.floor((T + off) / P);
      for (let kk = k; kk >= k - 1; kk--) {
        const Ts = kk * P - off;
        const occ = clamp(ctx.density(Ts + P * 0.5 - ctx.K), 0, 1) * N_PEAK / (NS * 0.775);
        if (rnd(seed, i, kk, 3) >= occ) continue;
        const V = buildVisit(seed, i, kk, Ts, P - SLOT_GAP, T + 0.1, ctx.K);
        if (T < V.Ts || T >= V.Te) continue;
        list.push(birdRecord(V, T, eps, false));
      }
    }
  }
  // the ledger's birds: strikes up to now leave their dead; strikes about to happen are on their way in
  for (const e of shotEvents(ctx)) {
    if (e.tl > tl + 60) continue;
    if (e.kind === 'glance' && tl > e.tl + 12) continue;
    const B = e.tl < tl - 30 ? restingBird(e, seed) : ledgerBird(e, seed);
    if (B.Ts > tl) continue;
    const rec = birdRecord(B, tl, eps, true);
    if (ctx.aftermath && rec.pose === 0) continue;
    list.push(rec);
  }
  let vis = list.filter(b => b.visible);
  if (ctx.only != null) vis = vis.filter(b => b.id === ctx.only);
  const cam = ctx.camPos;
  if (cam) {
    if (!eng) vis = vis.filter(b => !occluded(cam, b.p));          // harness only; the engine depth-tests
    // only what would be inside the lens itself; a bird passing close is drawn, large and blurred, until it leaves
    // the frame (a 1.8 m cull here made birds vanish just before the frame edge: Mark's note on cut 1)
    vis = vis.filter(b => (b.p[0] - cam[0]) ** 2 + (b.p[1] - cam[1]) ** 2 + (b.p[2] - cam[2]) ** 2 > 0.35 * 0.35);
    for (const b of vis) b.d2 = (b.p[0] - cam[0]) ** 2 + (b.p[1] - cam[1]) ** 2 + (b.p[2] - cam[2]) ** 2;
    vis.sort((a, b) => b.d2 - a.d2);
  }
  const data = new Float32Array(vis.length * STRIDE);
  // far out (120-160 m from the lantern, where visits begin and end) a bird thins into the mist
  vis.forEach((b, n) => data.set([b.p[0], b.p[1], b.p[2], b.sp, b.v[0], b.v[1], b.v[2], b.phase, b.f, b.fold, b.pose, b.seed,
    b.roll, b.yaw, b.wingOut, b.alb, b.flutter, b.lie, b.tumble, 1 - smooth((Math.hypot(b.p[0], b.p[1], b.p[2]) - 120) / 40)], n * STRIDE));
  return { n: vis.length, data, list: vis, info: { tl, H: ctx.hour(tl), density: ctx.density(tl), crowd: list.filter(b => !b.ledger).length } };
}

// Test only (shot.specimens): each species lying each way, and one with a wing out, in a row on the gallery floor.
function specimenTray(ctx) {
  const list = [];
  let n = 0;
  for (let sp = 0; sp < 4; sp++) for (let lie = 0; lie < 4; lie++) {
    const r = 2.36 + lie * 0.27, b = (146 + (sp - 1.5) * 0.33 / r * 180 / Math.PI) * Math.PI / 180;
    list.push({ p: [Math.sin(b) * r, GEOM.galleryY + 0.03, -Math.cos(b) * r], v: [0, 0, 0], sp, phase: 0, f: 0, fold: 1, pose: 1, seed: (n * 0.137) % 1,
      roll: 0, yaw: b + Math.PI / 2 + ((n * 7) % 5 - 2) * 0.12, wingOut: lie === 3 ? 0.8 : 0, alb: sp === 2 && n % 2 ? 2 : 1, flutter: 0, lie: lie === 3 ? 1 : lie, tumble: -1, visible: true, ledger: true, kind: 'dead', id: 990000 + n });
    n++;
  }
  const cam = ctx.camPos;
  if (cam) list.sort((a, b) => ((b.p[0] - cam[0]) ** 2 + (b.p[2] - cam[2]) ** 2) - ((a.p[0] - cam[0]) ** 2 + (a.p[2] - cam[2]) ** 2));
  const data = new Float32Array(list.length * STRIDE);
  list.forEach((b, i) => data.set([b.p[0], b.p[1], b.p[2], b.sp, 0, 0, 0, 0, 0, 1, 1, b.seed, 0, b.yaw, b.wingOut, b.alb, 0, b.lie, -1, 1], i * STRIDE));
  return { n: list.length, data, list, info: { specimens: true } };
}

function birdRecord(V, T, eps, isLedger) {
  const p = [0, 0, 0], pa = [0, 0, 0], pb = [0, 0, 0];
  let pose = 0, fold = 0, flutter = 0, wingOut = 0, lie = 0, yaw = 0, tumble = -1, visible = true;
  if (isLedger) {
    const s = evalLedgerBird(V, T, { p });
    ({ pose, fold, flutter, wingOut, lie, yaw, visible, tumble } = s);
    if (pose === 3) yaw = s.face;
    evalLedgerBird(V, T - eps, { p: pa }); evalLedgerBird(V, T + eps, { p: pb });
  } else {
    flutter = evalVisit(V, T, p); evalVisit(V, T - eps, pa); evalVisit(V, T + eps, pb);
  }
  const v = [(pb[0] - pa[0]) / (2 * eps), (pb[1] - pa[1]) / (2 * eps), (pb[2] - pa[2]) / (2 * eps)];
  const acc = [(pb[0] - 2 * p[0] + pa[0]) / (eps * eps), 0, (pb[2] - 2 * p[2] + pa[2]) / (eps * eps)];
  const spd = Math.hypot(v[0], v[2]) + 1e-6;
  const lat = (v[0] * acc[2] - v[2] * acc[0]) / spd;
  const roll = pose === 0 && tumble < 0 ? clamp(Math.atan2(lat, 9.81), -1.1, 1.1) : 0;
  const S = SPECIES[V.sp];
  let ph = V.ph + V.f * (T - V.Ts) * (flutter ? 1.3 : 1);
  if (pose === 0 && !flutter && S.bound > 0 && tumble < 0) {     // flap-bounding pauses (cadence invented)
    const cyc = 0.75 + 0.25 * ((V.id % 13) / 13), u = ((((T - V.Ts + V.ph * 7) % cyc) + cyc) % cyc) / cyc;
    if (u > 1 - S.bound) fold = Math.max(fold, smooth((u - (1 - S.bound)) / 0.05) * (1 - smooth((u - 0.96) / 0.04)));
  }
  if (pose === 0 && !flutter && S.key === 'starling' && tumble < 0) {   // short glides, wings out (cadence invented)
    const u = ((((T - V.Ts + V.ph * 5) % 1.6) + 1.6) % 1.6) / 1.6;
    if (u > 0.82) ph = Math.floor(ph);
  }
  return { p, v, sp: V.sp, phase: ph - Math.floor(ph), f: (pose === 0 || pose === 3) ? V.f * (flutter ? 1.3 : 1) : 0,
    fold, pose, seed: ((V.id * 2654435761) >>> 0) / 4294967296, roll, yaw, wingOut, alb: V.alb, flutter, lie, tumble,
    visible, ledger: !!isLedger, kind: isLedger ? V.e.kind : 'crowd', ev: isLedger ? V.e : null, id: V.id };
}

function occluded(c, p) {      // harness only: cylinders for the tower, gallery and lantern
  const G = GEOM;
  const cyl = (R, y0, y1) => {
    const dx = p[0] - c[0], dy = p[1] - c[1], dz = p[2] - c[2];
    const a = dx * dx + dz * dz; if (a < 1e-9) return false;
    const b = 2 * (c[0] * dx + c[2] * dz), cc = c[0] * c[0] + c[2] * c[2] - R * R, disc = b * b - 4 * a * cc;
    if (disc < 0) return false;
    const s = (-b - Math.sqrt(disc)) / (2 * a);
    if (s <= 0 || s >= 0.995) return false;
    const y = c[1] + dy * s; return y > y0 && y < y1;
  };
  return cyl(G.glassR, G.galleryY, G.domeY - 0.3) || cyl(G.towerTopR, G.summitY, G.galleryY - 0.3) || cyl(G.galleryR, G.galleryY - 0.12, G.galleryY);
}

// ------------------------------------------------------------------------------------------- strikes, for sound and the tally
export function strikeEvents(shot, t0, t1, eng) {
  const ctx = makeCtx(shot, eng); CUR = ctx;
  const out = [];
  for (const e of shotEvents(ctx)) {
    const base = { species: SPECIES[e.sp].name, kind: e.kind, hard: +e.hard.toFixed(2), pos: e.p0.map(x => +x.toFixed(2)),
      bearingDeg: +(wrap(e.bearing) * 180 / Math.PI).toFixed(1), featured: !!e.featured };
    if (e.tl >= t0 && e.tl < t1) out.push({ t: e.tl, ...base });
    if (e.flutter) {
      const n = Math.floor(e.flutter * 3);
      for (let k = 1; k < n; k++) {
        const tt = e.tl + k * e.flutter / n + (rnd(ctx.seed, e.id, k, 55) - 0.5) * 0.15;
        if (tt >= t0 && tt < t1) out.push({ t: tt, ...base, kind: 'flutter-tap', hard: 0.15 });
      }
    }
    if (e.rest && e.fall) {
      const tland = e.tl + (e.flutter || 0) + e.fall.tLand;
      if (tland >= t0 && tland < t1) out.push({ t: tland, ...base, kind: 'land-' + e.rest.where, hard: 0.3, pos: [e.rest.x, e.rest.y, e.rest.z].map(x => +x.toFixed(2)) });
    }
  }
  return out.sort((a, b) => a.t - b.t);
}
// the night's totals up to shot-local time tl: dead (of the 272) and all strikes (for the tally in fives)
export function strikesUpTo(tl, shot, eng) {
  const ctx = makeCtx(shot, eng); CUR = ctx;
  let dead = 0, strikes = 0;
  for (const e of shotEvents(ctx)) if (e.tl <= tl) { strikes++; if (e.kind === 'dead') dead++; }
  return { dead, strikes };
}

// ------------------------------------------------------------------------------------------- drawing
// BirdRenderer: instanced quads, premultiplied alpha over the radiance target, depth-tested (not written)
// against what B's light kit wrote. COMMON's uniforms (uViewProj, uCamPos, uRes, uTl) and the light chunk's are
// the caller's to set before draw().
export class BirdRenderer {
  constructor(gl, prog) {
    this.gl = gl; this.prog = prog;
    this.vao = gl.createVertexArray(); this.buf = gl.createBuffer();
    gl.bindVertexArray(this.vao); gl.bindBuffer(gl.ARRAY_BUFFER, this.buf);
    for (let a = 0; a < 5; a++) {
      const loc = gl.getAttribLocation(prog, 'a' + a); if (loc < 0) continue;
      gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 4, gl.FLOAT, false, STRIDE * 4, a * 16); gl.vertexAttribDivisor(loc, 1);
    }
    gl.bindVertexArray(null);
    this.uS = gl.getUniformLocation(prog, 'uSpecies'); this.uS2 = gl.getUniformLocation(prog, 'uSpecies2');
    this.uSh = gl.getUniformLocation(prog, 'uShutter'); this.uD = gl.getUniformLocation(prog, 'uDawn');
  }
  draw(res, { shutter = 1 / 48, dawn = 0, depthTest = true } = {}) {
    const gl = this.gl;
    if (!res.n) return;
    gl.useProgram(this.prog);
    gl.bindVertexArray(this.vao); gl.bindBuffer(gl.ARRAY_BUFFER, this.buf);
    gl.bufferData(gl.ARRAY_BUFFER, res.data, gl.DYNAMIC_DRAW);
    gl.uniform4fv(this.uS, SPECIES.flatMap(s => [s.len, s.span, s.chord, s.tail]));
    gl.uniform4fv(this.uS2, SPECIES.flatMap(s => [s.tailW, s.tipR, s.belly, s.alb]));
    gl.uniform1f(this.uSh, shutter); gl.uniform1f(this.uD, dawn);
    gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
    if (depthTest) { gl.enable(gl.DEPTH_TEST); gl.depthFunc(gl.LEQUAL); gl.depthMask(false); } else gl.disable(gl.DEPTH_TEST);
    gl.drawArraysInstanced(gl.TRIANGLE_STRIP, 0, 4, res.n);
    gl.bindVertexArray(null); gl.depthMask(true); gl.disable(gl.BLEND);
  }
}
// birds.glsl holds a shared part, then '//#vertex', then '//#fragment'.
export function splitGLSL(glsl) {
  const iv = glsl.indexOf('//#vertex'), ifr = glsl.indexOf('//#fragment');
  return { common: glsl.slice(0, iv), vert: glsl.slice(iv, ifr), frag: glsl.slice(ifr) };
}

// ------------------------------------------------------------------------------------------- the engine kit
export async function register(E) {
  const glsl = await (await fetch(new URL('birds.glsl', import.meta.url))).text();
  const { common, vert, frag } = splitGLSL(glsl);
  let R = null;
  const engCtx = (F) => ({ azAt: (tl) => globalThis.LIGHT ? globalThis.LIGHT.beamAz(tl, F) : OMEGA * tl, camPos: F.cam.pos });
  E.kit('birds', {
    async init(gl, E) {
      const prog = E.program(common + frag, { use: ['light'], vert: common + vert, vertUse: ['light'] });
      R = new BirdRenderer(gl, prog);
    },
    draw(gl, F) {
      const res = birdsAt(F.tl, F.shot, engCtx(F));
      if (!res.n) return;
      E.set(R.prog, F.common);
      const dawn = typeof F.shot.dawn === 'function' ? F.shot.dawn(F.tl) : (globalThis.LIGHT ? globalThis.LIGHT.settings(F).dawn : 0);
      R.draw(res, { dawn, shutter: 1 / 48, depthTest: true });
    },
  });
  // Test shots for this kit's dailies only (not in the sequence): the night at three densities with a real-time clock,
  // and the aftermath seen close. Named birdtest-*.
  const deg = Math.PI / 180, polar = (bd, r, y) => [Math.sin(bd * deg) * r, y, -Math.cos(bd * deg) * r];
  const night = (h) => ({ dur: 10, kits: ['light', 'birds'], beamFacesAt: 3, hour: tl => h + tl / 3600, dawn: () => 0,
    density: tl => nightShape(h + tl / 3600), camera: () => ({ pos: polar(160, 30, -7), target: [0, 0.3, 0], fov: 40 }) });
  E.shot('birdtest-first', night(23.2));
  E.shot('birdtest-thick', night(25.0));
  E.shot('birdtest-thin', night(26.3));
  const after = (cam) => ({ dur: 4, kits: ['light', 'birds'], beamFacesAt: 99, hour: () => 30.9, dawn: () => 0.9, density: () => 0, aftermath: true, camera: () => cam });
  E.shot('birdtest-gallery', after({ pos: polar(100, 3.0, -0.7), target: polar(145, 2.75, -2.3), fov: 55 }));
  E.shot('birdtest-foot', after({ pos: polar(150, 11, -9.0), target: polar(135, 5, -13.6), fov: 45 }));
  E.shot('birdtest-dawnmid', after({ pos: polar(175, 14, -4), target: [0, -7.5, 0], fov: 44 }));
  const tray = (cam) => ({ ...after(cam), specimens: true });
  E.shot('birdtest-tray-above', tray({ pos: polar(146, 3.6, -0.6), target: polar(146, 2.75, -2.3), fov: 40 }));
  E.shot('birdtest-tray-8m', tray({ pos: polar(125, 8.5, -0.4), target: polar(146, 2.8, -2.3), fov: 22 }));
  E.shot('birdtest-gallery4', after({ pos: polar(128, 4.6, -0.9), target: polar(148, 3.1, -2.3), fov: 34 }));
  E.shot('birdtest-dawngallery', after({ pos: polar(150, 6.5, 1.8), target: polar(138, 2.8, -2.3), fov: 45 }));
  globalThis.BIRDS = {
    strikeEvents: (shot, t0, t1, F) => strikeEvents(shot, t0, t1, F && engCtx(F)),
    strikesUpTo: (tl, shot, F) => strikesUpTo(tl, shot, F && engCtx(F)),
    ledger, SPECIES, GEOM,
  };
}

export const _debug = { beam: (tl, shot) => makeCtx(shot).beam(tl), N_FACES, PERIOD, makeCtx };
