// shots.js: the shot list as cameras (coordinator). Movement I, cut 2 (Mark's notes on cut 1: open on the lantern
// with strikes; name the keepers; subtitles revealed as spoken; the real printed page; voice clearer).
// World: metres, flame at the origin, y up, x east, z south; summit y = -13.4, gallery y = -2.3, sea y = -43.9
// (film/research/south-bishop.md). Fields every kit may read:
//   beamFacesAt  shot-local seconds when a beam faces the camera (light kit sets the phase from it)
//   hour(tl)     the night's clock, hours after the noon before, GMT (23 = 11 P.M. on the 21st, 26.5 = 2.30 A.M.)
//   dawn(tl)     0 by night, 1 at full grey daylight (sky, sea and the print's plate)
//   density(tl)  how thick the birds are, 0..1 (the entry: "hundreds ... from 11 P.M. to 2.30 A.M.")
const E = window.ENGINE;
const lerp = (a, b, k) => a + (b - a) * k;
const ease = k => k * k * (3 - 2 * k);
const clamp01 = k => Math.min(1, Math.max(0, k));
const mix3 = (a, b, k) => a.map((v, i) => lerp(v, b[i], k));
// bearing (degrees clockwise from north, north = -z), radius, height: as birds.js's polar()
const polar = (b, r, y) => [r * Math.sin(b * Math.PI / 180), y, -r * Math.cos(b * Math.PI / 180)];
// Ride the exposure down through each flash (every 20 s from beamFacesAt), so a close camera's white-out lasts about
// the flash's own 2.4 s (light kit, REQUESTS.md) rather than 4-5 s. depth: how far it dips; w: half-width in seconds.
const ride = (base, faces, depth = 0.55, w = 1.3) => tl => {
  let d = 0;
  for (let k = -2; k <= 3; k++) d = Math.max(d, Math.exp(-(((tl - faces - 20 * k) / w) ** 2)));
  return { exposure: base * (1 - depth * d) };
};

// ---- the voice: when each line starts in its shot, and its character timings (ElevenLabs alignment, tsubomi).
// film/sound/mix_i.py places the same lines; keep the two in step (it reads film/sound/cues_i.json, below).
export const VOICE = {
  sb1: { file: 'sb1_chris_1', shot: 'approach', at: 1.0,
         printed: 'hundreds of birds of all sorts flying around the lantern from 11 P.M. to 2.30 A.M.' },
  sb2: { file: 'sb2_chris_1', shot: 'dawn', at: 1.5,
         printed: 'Several birds seen on the rock at daylight with broken wings.' },
  sb3: { file: 'sb3_chris_1', shot: 'page', at: 3.2, printed: null },
  // movement II: five keepers at once, each read as if alone (LINES.md); placed as their lights come into the frame
  tk1: { file: 'tk1_flynn_1', shot: 'elsewhere', at: 4.5, printed: 'numbers striking at midnight, fifteen killed. [Leg and wing received.]' },
  cg1: { file: 'cg1_keanan_1', shot: 'elsewhere', at: 6.6, printed: 'several about light, 6 P.M. to midnight; many killed striking, dropped into the sea' },
  ed1: { file: 'ed1_tom_1', shot: 'elsewhere', at: 9.0, printed: 'eighty-two killed' },
  cr1: { file: 'cr1_adam_1', shot: 'elsewhere', at: 10.4, printed: 'Thrushes, Blackbirds, Larks, Starlings, and Chaffinches, numbers killed, from 3 A.M. till morning.' },
  md1: { file: 'md1_mark_1', shot: 'elsewhere', at: 12.6, printed: 'striking 9 P.M. to 1 A.M.; about one hundred killed' },
};
for (const v of Object.values(VOICE)) {
  try {
    const j = await (await fetch(`../voice/takes/${v.file}.json`)).json();
    v.end = j.alignment.character_end_times_seconds.at(-1);
    v.starts = j.alignment.character_start_times_seconds;
  } catch (e) { v.end = 6; v.starts = null; }
}
const KEEPERS = 'Messrs Nicholas and Pell, South Bishop';    // the 1887 list (data/keepers.csv)

// The printed words, revealed in step with the spoken ones: the share of the spoken line said so far sets the share of
// the printed line shown, a whole word at a time (the spoken line has "eleven P.M." where the print has "11 P.M.").
function subtitle(T, tl, v, y = 1000, mode = 'light') {   // mode 'ink' on a pale (dawn) plate
  if (!v.printed) return;
  const s = tl - v.at;
  if (s < 0 || s > v.end + 2.2) return;
  const frac = v.starts ? v.starts.filter(x => x <= s).length / v.starts.length : clamp01(s / v.end);
  const words = v.printed.split(' ');
  const total = v.printed.length;
  let shown = 0, acc = 0;
  for (const w of words) { if (acc / total <= frac) shown++; acc += w.length + 1; }
  const fade = clamp01((v.end + 2.2 - s) / 0.8);
  const o = { size: 42, alpha: fade, mode };
  const lines = T.measure(v.printed, o) > 1500 ? splitHalf(v.printed) : [v.printed];
  let used = 0;
  lines.forEach((line, i) => {
    const lw = T.measure(line, o), n = line.split(' ').length;
    const k = Math.max(0, Math.min(n, shown - used)); used += n;
    if (k > 0) T.text(line.split(' ').slice(0, k).join(' '), 960 - lw / 2, y - (lines.length - 1 - i) * 54, Object.assign({}, o, { align: 'left' }));
  });
  T.text(KEEPERS, 960, y + 46, { size: 26, italic: true, mode, alpha: 0.75 * fade * clamp01(s / 0.6) });
}
function splitHalf(str) {
  const ws = str.split(' '); let best = 1, bd = 1e9;
  for (let i = 1; i < ws.length; i++) { const d = Math.abs(ws.slice(0, i).join(' ').length - ws.slice(i).join(' ').length); if (d < bd) { bd = d; best = i; } }
  return [ws.slice(0, best).join(' '), ws.slice(best).join(' ')];
}

// 1. Open on the lantern, in the thick of it (about 1 A.M.): no voice, only the birds striking the glass (Mark's cold
// open, cut 2 notes), and the tally of the dead so far.
const OPEN = {
  dur: 9, kits: ['light', 'birds'], beamFacesAt: 8,
  hour: tl => 25.0 + tl / 60, dawn: () => 0, density: () => 1,
  camera: tl => ({ pos: mix3([6.6, -7.2, 16.5], [6.2, -6.9, 15.3], ease(tl / 9)), target: [0, 0.3, 0], fov: 26 }),
  printAt: tl => ({ exposure: ride(1, 8)(tl).exposure * Math.max(0.02, clamp01(tl / 1.2)) }),     // up out of black
  type: (T, tl) => {
    const B = window.BIRDS;
    let n = null;
    try { n = B && B.strikesUpTo(tl, OPEN).dead; } catch (e) { n = null; }
    // rows of eight fives, so the whole count is on the frame and the last row visibly grows (146 at 1 A.M.)
    if (n != null) for (let r = 0; r * 40 < n; r++)
      T.tally(Math.min(40, n - r * 40), 1580, 100 + r * 32, { h: 20, alpha: clamp01((tl - 1) / 1) });
  },
};
E.shot('open', OPEN);

// 1b. What made that sound: the gallery at night, the dead on the iron floor, seen in the light of the beams.
E.shot('nightdead', {
  dur: 2.2, kits: ['light', 'birds'], beamFacesAt: 1.4,
  hour: tl => 25.15 + tl / 60, dawn: () => 0, density: () => 1,
  camera: () => ({ pos: polar(126, 6.8, -0.6), target: polar(146, 3.1, -2.3), fov: 36 }),
  printAt: ride(1.6, 1.4, 0.5),
});

// 2. Cut away: the whole station as one point of light far out at sea (about 5 km south-west), and who kept it.
E.shot('cold', {
  dur: 7, kits: ['light'], beamFacesAt: 2.5,
  hour: () => 25.3, dawn: () => 0, density: () => 0,
  camera: () => ({ pos: [-3200, -40, 3900], target: [0, -6, 0], fov: 14 }),
  print: { exposure: 0.5 },               // constant: the light kit now makes the flash a hard point in a modest glow (B, cut 2 notes)
  type: (T, tl) => {
    const a = clamp01((tl - 0.8) / 1.0) * clamp01((7 - tl) / 0.8);
    T.text('South Bishop Lighthouse, Pembrokeshire', 120, 900, { size: 40, italic: true, alpha: a, align: 'left' });
    T.text('21 October 1887', 120, 955, { size: 40, italic: true, alpha: a, align: 'left' });
    T.text('Keepers: Messrs Nicholas and Pell', 120, 1010, { size: 40, italic: true, alpha: a * clamp01((tl - 1.6) / 1.0), align: 'left' });
  },
});

// 3. The approach: middle distance from the sea, the rock and tower, the beams through mist; the keepers' first line.
E.shot('approach', {
  dur: 10, kits: ['light', 'birds'], beamFacesAt: 5,
  hour: tl => 25.4 + tl / 60, dawn: () => 0, density: () => 0.7,
  camera: tl => ({ pos: mix3([-150, -36, 330], [-110, -32, 245], ease(tl / 10)), target: [0, -9, 0], fov: 28 }),
  printAt: ride(1, 5, 0.4),
  type: (T, tl) => subtitle(T, tl, VOICE.sb1),
});

// 4. At the glazing: one strike; the beam moves on.
E.shot('glazing', {
  dur: 6, kits: ['light', 'birds'], beamFacesAt: 2.5,
  hour: tl => 25.6 + tl / 60, dawn: () => 0, density: () => 0.8, strikeAt: 3.0,
  camera: () => ({ pos: [2.6, -0.6, 4.4], target: [0, 0.5, 0], fov: 42 }),
  printAt: ride(0.06, 2.5, 0.8),          // the lens is 100s of times brighter than anything else; its rings show near 0.01-0.06
});

// 5. Dawn: the rock, the tower and the houses in grey light; the keepers' second line.
E.shot('dawn', {
  dur: 9, kits: ['light', 'birds'], beamFacesAt: 99,
  hour: tl => 30.6 + tl / 60, dawn: tl => lerp(0.75, 0.9, tl / 9), density: () => 0, aftermath: true,
  camera: tl => ({ pos: mix3([-26.0, -6, 21.9], [-24.5, -6.2, 20.6], ease(tl / 9)), target: [0, -7, 0], fov: 40 }),
  type: (T, tl) => subtitle(T, tl, VOICE.sb2, 150, 'ink'),   // in the pale sky: ink over the dark rock was unreadable (cut 4)
});

// 6. The gallery's windward arc where the dead lie, from 8 m off and a little above (C: under ~5 m they read as lumps).
E.shot('gallery', {
  dur: 4.5, kits: ['light', 'birds'], beamFacesAt: 99,
  hour: tl => 30.75 + tl / 60, dawn: () => 0.85, density: () => 0, aftermath: true,
  camera: tl => ({ pos: polar(lerp(122, 128, ease(tl / 4.5)), 8.5, -0.4), target: polar(148, 3.1, -2.3), fov: 34 }),
});

// 7. The printed page: the Report for 1887, p. 99, the October 21st paragraph; the plate pales to paper and the
// page prints on it in ink, the South Bishop entry full strength and the rest of the paragraph faint.
const PAGE = new Image();
PAGE.src = 'assets/p99_oct21_ink.png';
try { await PAGE.decode(); } catch (e) { /* the shot shows an empty page */ }
E.shot('page', {
  dur: 8, kits: ['light'], beamFacesAt: 99,
  hour: () => 31.2, dawn: () => 1, density: () => 0,
  camera: () => ({ pos: [-40, -8, 60], target: [-40, 60, -40], fov: 30 }),   // up into the grey morning sky: the plate as paper
  printAt: tl => ({ exposure: lerp(1.2, 3.0, clamp01(tl / 1.5)) }),
  type: (T, tl) => {
    const ctx = T.ctx, W = 2030, H = 930;
    const k = ease(clamp01(tl / 8));
    const s = lerp(0.84, 0.9, k);                              // a slow push in
    const cy = lerp(H / 2, 700, k);                            // drifting down to the entry (crop rows ~520-880)
    const x0 = 960 - W * s / 2, y0 = 540 - cy * s;
    const a = clamp01(tl / 1.0);
    ctx.save();
    ctx.globalAlpha = a * lerp(1, 0.38, clamp01((tl - 1.5) / 1.5));
    ctx.drawImage(PAGE, x0, y0, W * s, H * s);              // the whole paragraph, fading back
    ctx.globalAlpha = a;
    ctx.beginPath();                                          // the entry, from "South Bishop" (x ~ 820 on its first line) to its end
    ctx.rect(x0 + 820 * s, y0 + 505 * s, (W - 820) * s, 92 * s);
    ctx.rect(x0, y0 + 597 * s, W * s, (H - 597) * s);
    ctx.clip();
    ctx.drawImage(PAGE, x0, y0, W * s, H * s);
    ctx.restore();
    T.text('Report on the Migration of Birds, 1887, p. 99', 960, 1030, { size: 26, italic: true, alpha: 0.7 * clamp01((tl - 1) / 1), mode: 'ink' });
  },
});

// ================================================================ movement II: the same hours, elsewhere
// One shot on the night chart (chart.js): from the South Bishop out to the whole western approaches; every 1887 light
// flashing at its own character; five keepers' lines at once, each printed beside its own light as it is spoken.
// The 16 stations with a strike that night (notes/TESTS.md G1) ringed at the end.
// Which keepers: data/keepers.csv, 1887 (the Maidens' are not in our list, so none are named).
const STATIONS_II = [
  // id, voice, name, keepers, label beside the light (dx px, align; up: the block ends at the light rather than starts)
  { id: 'south-bishop', voice: null, name: 'South Bishop', keepers: 'Messrs Nicholas and Pell', words: '272 killed', dx: 18, align: 'left' },
  { id: 'tuskar-rock', voice: 'tk1', name: 'The Tuskar', keepers: 'Patrick Corish, P. Page, E. M\u2019Kenna, J. M. Leary', dx: -18, dy: -16, align: 'right', up: true },
  { id: 'coningbeg-lv', voice: 'cg1', name: 'Coningbeg light-vessel', keepers: 'Patrick Cullen, Wm. Clydesdale', dx: -18, dy: 14, align: 'right' },
  { id: 'eddystone', voice: 'ed1', name: 'The Eddystone', keepers: 'Messrs Ainger and Gaudion', dx: 18, align: 'left' },
  { id: 'chicken-rock', voice: 'cr1', name: 'Chickens Rock', keepers: 'Messrs Black and Beggs', dx: 18, align: 'left' },
  { id: 'maidens-north', voice: 'md1', name: 'The Maidens', keepers: null, dx: -18, align: 'right' },
];
const STRUCK_1887_10_21 = ['arklow-south-lv', 'bull-point', 'caernarfon-bay-lv', 'caldey', 'chicken-rock', 'coningbeg-lv', 'eddystone',
  'fastnet', 'godrevy', 'longships', 'maidens-north', 'selker-lv', 'slyne-head-south', 'south-bishop', 'south-stack', 'tuskar-rock'];

// words of a printed line shown s seconds after its voice starts (the share spoken sets the share printed, as subtitle())
function wordsShown(v, s) {
  if (s < 0) return 0;
  const frac = v.starts ? v.starts.filter(x => x <= s).length / v.starts.length : clamp01(s / v.end);
  let shown = 0, acc = 0;
  for (const w of v.printed.split(' ')) { if (acc / v.printed.length <= frac) shown++; acc += w.length + 1; }
  return shown;
}
function wrapWords(T, words, maxW, o) {
  const lines = []; let cur = [];
  for (const w of words) { if (cur.length && T.measure([...cur, w].join(' '), o) > maxW) { lines.push(cur); cur = []; } cur.push(w); }
  if (cur.length) lines.push(cur);
  return lines;
}
const CHART_DUR = 26;
const zoomK = tl => ease(clamp01((tl - 1.0) / 12));
E.shot('elsewhere', {
  dur: CHART_DUR, kits: ['nightchart'], clock0: 0,
  // where each light starts in its cycle: unknown, so chosen to show each speaking light lit as it speaks
  phase: { 'south-bishop': 19.0, 'tuskar-rock': 0, 'coningbeg-lv': 54, 'eddystone': 21, 'chicken-rock': 20 },
  chart: tl => { const k = zoomK(tl); return { lon: lerp(-5.41, -6.7, k), lat: lerp(51.85, 52.55, k), km: 60 * Math.pow(1300 / 60, k) }; },
  camera: () => ({ pos: [0, 0, 1], target: [0, 0, 0], fov: 30 }),        // unused: the chart has its own view
  printAt: tl => ({ exposure: 1.0 * clamp01(tl / 1.0) + 0.02 }),
  type: (T, tl, F) => {
    const C = window.CHART; if (!C) return;
    const shot = F.shot, v = C.view(shot, tl);
    for (const st of STATIONS_II) {
      const l = C.byId[st.id]; if (!l) continue;
      const [x, y] = C.toScreen(l.lon, l.lat, v);
      const vo = st.voice && VOICE[st.voice];
      const s = vo ? tl - vo.at : tl - 0.8;
      if (s < -0.6) continue;
      const a = clamp01((s + 0.6) / 0.6) * (vo ? lerp(1, 0.6, clamp01((s - vo.end - 1.5) / 1.5)) : lerp(1, 0.6, clamp01((tl - 4) / 2)));
      // laid out on the whole printed line, so the block doesn't reflow as the words come; an 'up' block ends at the light
      const o = { size: 27, align: st.align, alpha: a };
      const lines = wrapWords(T, (vo ? vo.printed : st.words).split(' '), 430, o);
      const h = (st.keepers ? 26 : 0) + 34 * lines.length;
      const bx = x + st.dx;
      let yy = (st.up ? y + 8 - h : y + 8) + (st.dy || 0);
      T.text(st.name, bx, yy, { size: 24, italic: true, align: st.align, alpha: a });
      if (st.keepers) { yy += 26; T.text(st.keepers, bx, yy, { size: 19, italic: true, align: st.align, alpha: 0.7 * a }); }
      let left = vo ? wordsShown(vo, s) : Infinity;
      for (const line of lines) {
        yy += 34;
        const k = Math.min(line.length, left); left -= k;
        if (k > 0) T.text(line.slice(0, k).join(' '), bx, yy, o);
      }
      const ctx = T.ctx;                                       // its light ringed, so it is found even in its dark
      ctx.save(); ctx.strokeStyle = `rgba(255,0,0,${0.85 * a})`; ctx.lineWidth = 1.6;
      ctx.beginPath(); ctx.arc(x, y, 11, 0, 2 * Math.PI); ctx.stroke(); ctx.restore();
    }
    // the sixteen, ringed
    const ra = clamp01((tl - 17.2) / 1.2);
    if (ra > 0) {
      const ctx = T.ctx;
      ctx.save(); ctx.strokeStyle = `rgba(255,0,0,${0.85 * ra})`; ctx.lineWidth = 1.6;
      for (const id of STRUCK_1887_10_21) {
        const l = C.byId[id]; if (!l) continue;
        const [x, y] = C.toScreen(l.lon, l.lat, v);
        ctx.beginPath(); ctx.arc(x, y, 11, 0, 2 * Math.PI); ctx.stroke();
      }
      ctx.restore();
    }
    const a1 = clamp01((tl - 18.6) / 1.0), a2 = clamp01((tl - 20.6) / 1.0), out = clamp01((CHART_DUR - tl) / 1.0);
    T.text('Sixteen lanterns that night.', 120, 880, { size: 44, italic: true, align: 'left', alpha: a1 * out });
    T.text('Each keeper wrote down only their own.', 120, 940, { size: 44, italic: true, align: 'left', alpha: a2 * out });
  },
});

// ================================================================ movement III: the pattern
// Every night of the reports, 1879-1887, on a lunar calendar (tools/film_calendar.py -> assets/calendar.json): a row
// per lunation, a column per day of the moon's age, new moon at both edges and full in the middle. A cell's paper is
// burnished by that night's moonlight at midnight; each station with a strike that night (strike_wide, as K1 and G1)
// adds one stroke. The strokes arrive in date order; they gather where the moon is dark. Cards: K1's calendar
// check (3.1% against 7.9%; notes/TESTS.md), then the film's claim.
let CAL = null;
try { CAL = await (await fetch('assets/calendar.json')).json(); } catch (e) { CAL = null; }
const PAT_DUR = 22;
const GRID = { x0: 210, y0: 92, cw: 50, rows: CAL ? CAL.nights.at(-1).lun + 1 : 109, h: 800 };
GRID.rh = GRID.h / GRID.rows;
const MARK_T0 = 1.5, MARK_T1 = 9.5;          // the strokes arrive in date order over these seconds
E.shot('pattern', {
  dur: PAT_DUR, kits: [],
  camera: () => ({ pos: [0, 0, 1], target: [0, 0, 0], fov: 30 }),        // unused: all type
  printAt: tl => ({ exposure: 1.0 }),
  type: (T, tl) => {
    if (!CAL) return;
    const ctx = T.ctx, N = CAL.nights, n = N.length;
    const fadeOut = clamp01((PAT_DUR - tl) / 1.0);
    const head = { size: 24, italic: true, alpha: 0.75 * clamp01(tl / 1.0) * fadeOut };
    T.text('new moon', GRID.x0, GRID.y0 - 22, Object.assign({}, head, { align: 'left' }));
    T.text('full moon', GRID.x0 + 14.77 * GRID.cw, GRID.y0 - 22, head);
    T.text('new moon', GRID.x0 + 30 * GRID.cw, GRID.y0 - 22, Object.assign({}, head, { align: 'right' }));
    let year = null;
    const shownUpTo = Math.floor(n * clamp01((tl - MARK_T0) / (MARK_T1 - MARK_T0)));
    let mark = null;
    N.forEach((r, i) => {
      const col = Math.min(29, Math.floor(r.age)), x = GRID.x0 + col * GRID.cw, y = GRID.y0 + r.lun * GRID.rh;
      const sweep = clamp01((tl - 2.2 * r.lun / GRID.rows) / 0.5);         // the nights laid down row by row
      if (sweep > 0 && r.light > 0) {
        ctx.fillStyle = `rgba(255,0,0,${(0.03 + 0.13 * r.light) * sweep * fadeOut})`;
        ctx.fillRect(x, y, GRID.cw, GRID.rh);
      }
      const yr = r.night.slice(0, 4);
      if (yr !== year && r.night.slice(5) >= '01-01') {
        year = yr;
        T.text(yr, GRID.x0 - 18, y + GRID.rh, { size: 20, italic: true, align: 'right', alpha: 0.7 * clamp01(tl / 1.0) * fadeOut });
      }
      if (i < shownUpTo && r.struck.length) {
        // one stroke per station, full light, so it reads on a moonlit cell (tone at most 0.16) as on a dark one
        const k = r.struck.length;
        ctx.fillStyle = `rgba(255,0,0,${fadeOut})`;
        for (let j = 0; j < k; j++) ctx.fillRect(x + 3 + j * 2.1, y + 1, 1.3, GRID.rh - 2);
        if (r.night === '1887-10-21') mark = [x, y];
      }
    });
    if (mark) {                                // the night of movements I and II
      const a = clamp01((tl - (MARK_T1 - 0.3)) / 0.8) * fadeOut;
      ctx.save(); ctx.strokeStyle = `rgba(255,0,0,${0.9 * a})`; ctx.lineWidth = 1.5;
      ctx.strokeRect(mark[0] - 2, mark[1] - 3, GRID.cw + 4, GRID.rh + 6);
      const gy = GRID.y0 + GRID.rows * GRID.rh;                // a tick down past the grid to the date
      ctx.beginPath(); ctx.moveTo(mark[0] + GRID.cw / 2, mark[1] + GRID.rh + 3); ctx.lineTo(mark[0] + GRID.cw / 2, gy + 14); ctx.stroke();
      ctx.restore();
      T.text('21 October 1887', mark[0] + GRID.cw / 2, gy + 38, { size: 22, italic: true, alpha: a });
    }
    const c1 = clamp01((tl - 10.5) / 1.0) * clamp01((15.6 - tl) / 0.6);
    T.text('Strikes on 3 in 100 nights under a bright moon; 8 in 100 without.', 960, 995, { size: 40, italic: true, alpha: c1 });
    const c2 = clamp01((tl - 16.2) / 1.0) * fadeOut;
    T.text('No keeper could see it from one rock.', 960, 975, { size: 40, italic: true, alpha: c2 });
    T.text('It is there when their notes are laid together.', 960, 1030, { size: 40, italic: true, alpha: clamp01((tl - 17.6) / 1.0) * fadeOut });
  },
});

// ================================================================ the title, the roll, the credits
// Every station on the lists with its keepers and their years (tools/film_roll.py -> assets/roll.json), set in three
// columns and rolled; beside four stations the committee's own line about their returns. Then what it was made from.
let ROLL = null;
try { ROLL = await (await fetch('assets/roll.json')).json(); } catch (e) { ROLL = null; }
const TITLE_DUR = 5.5, ROLL_SPEED = 230, CREDITS_DUR = 9;
const COLS = [{ x: 150 }, { x: 735 }, { x: 1320 }], COL_W = 470;
let ROLL_LAYOUT = null;
function rollLayout(T) {                          // blocks placed in order into the shortest column (fonts loaded by now)
  if (ROLL_LAYOUT || !ROLL) return ROLL_LAYOUT;
  const hs = COLS.map(() => 0), items = [];
  const nameO = { size: 22, italic: true }, kO = { size: 20 }, lO = { size: 20, italic: true };
  for (const st of ROLL.stations) {
    const c = hs.indexOf(Math.min(...hs)), lines = [];
    lines.push([st.station, nameO, 0.8]);
    for (const l of wrapWords(T, st.keepers.join('; ').split(' '), COL_W, kO)) lines.push([l.join(' '), kO, 1.0]);
    if (st.line) for (const l of wrapWords(T, ('“' + st.line + '”').split(' '), COL_W - 20, lO)) lines.push([l.join(' '), lO, 0.65]);
    let y = hs[c];
    for (const [text, o, a] of lines) { y += 27; items.push({ x: COLS[c].x, y, text, o, a }); }
    hs[c] = y + 22;
  }
  ROLL_LAYOUT = { items, height: Math.max(...hs) };
  return ROLL_LAYOUT;
}
const ROLL_DUR = () => ROLL_LAYOUT ? (ROLL_LAYOUT.height + 1080) / ROLL_SPEED : 24;
E.shot('roll', {
  dur: TITLE_DUR + 24 + CREDITS_DUR, kits: [],
  camera: () => ({ pos: [0, 0, 1], target: [0, 0, 0], fov: 30 }),
  printAt: () => ({ exposure: 1.0 }),
  type: (T, tl) => {
    const L = rollLayout(T);
    // the title
    const ta = clamp01(tl / 1.2) * clamp01((TITLE_DUR - tl) / 0.8);
    if (ta > 0) {
      T.text('Round the Lantern', 960, 500, { size: 92, alpha: ta, tracking: 2 });
      T.text('The keepers’ reports on the migration of birds, 1879–1887:', 960, 590, { size: 34, italic: true, alpha: 0.85 * ta });
      T.text('nearly 36,000 observations, read again.', 960, 638, { size: 34, italic: true, alpha: 0.85 * ta });
    }
    // the roll: up from the bottom of the frame at ROLL_SPEED px/s
    const rt = tl - TITLE_DUR, rd = 24;
    if (L && rt > 0 && rt < rd) {
      const off = 1080 + 20 - rt * (L.height + 1080) / rd;
      T.text('The keepers', 960, Math.max(70, off - 40), { size: 30, italic: true, alpha: 0.75 * clamp01(rt / 0.6) * clamp01((rd - rt) / 0.6) });
      for (const it of L.items) {
        const y = off + it.y;
        if (y < 100 || y > 1110) continue;
        const edge = clamp01((y - 100) / 60) * clamp01((1110 - y) / 60);
        T.text(it.text, it.x, y, Object.assign({}, it.o, { align: 'left', alpha: it.a * edge }));
      }
    }
    // the credits
    const ct = tl - TITLE_DUR - rd, ca = clamp01(ct / 0.8) * clamp01((CREDITS_DUR - ct) / 1.0);
    if (ca > 0) {
      const o = { size: 25, alpha: 0.85 * ca }, oi = { size: 25, italic: true, alpha: 0.85 * ca };
      const lines = [
        ['The keepers\u2019 words are as printed in the Reports on the Migration of Birds, 1879\u20131887, from the schedules', o],
        ['they sent to the British Association\u2019s committee; the cards are ours. The lights flash at their 1887 characters', o],
        ['(Findlay 1887; Edwards 1884). The rock, the tower and the birds are reconstructed; no picture of that night exists.', o],
        ['After Marian Eagle Clarke\u2019s painting of the Eddystone lantern, 12 October 1901.', oi],
        ['Voices: ElevenLabs. Each accent is a guess at who kept the light, not a record.', o],
        ['Moon: JPL DE440s. Coast: Natural Earth.', o],
        ['', o],
        ['A film by Mark Lundeberg’s Claude agent (Opus 5.5, an AI model made by Anthropic).', oi],
        ['Mark Lundeberg set the brief and answers for it.', oi],
      ];
      lines.forEach(([t, oo], i) => T.text(t, 960, 330 + i * 46, oo));
    }
  },
});

E.setSequence(['open', 'nightdead', 'cold', 'approach', 'glazing', 'dawn', 'gallery', 'page', 'elsewhere', 'pattern', 'roll']);
