// The keepers' nights: a calendar of every night 1879-1887 and a chart of any one of them (grown from sketch 1,
// sketches/round-the-lantern.html). Data from tools/explorer_data.py in ../data/.
(() => {
  'use strict';
  const RM = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const C = { sea: css('--sea'), seaDay: css('--sea-day'), land: css('--land'), line: css('--line'), ink: css('--ink'), dim: css('--ink-dim'),
    lamp: css('--lamp'), red: css('--lamp-red'), green: css('--lamp-green'), tally: css('--tally'), moon: css('--moon'), rule: css('--rule'),
    re: css('--reanalysis'), serif: css('--serif') };
  const LAMP = { white: C.lamp, red: C.red, green: C.green };
  const SPEED = 7.5;                                   // night minutes per real second
  const $ = id => document.getElementById(id);
  const map = $('map'), mctx = map.getContext('2d'), tl = $('timeline'), tctx = tl.getContext('2d'), cal = $('cal'), cctx = cal.getContext('2d');
  const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  let S = null, CAL = null, COAST = null, D = null, dpr = 1, W = 0, H = 0, proj = null, coastLayer = null;
  let tNight = 660, playing = !RM, last = performance.now(), selected = null;
  const yearCache = {};

  // ---------------------------------------------------------------- the projection: Lambert conformal conic, 50 and 60 N, 4 W
  const RAD = Math.PI / 180, P1 = 50 * RAD, P2 = 60 * RAD, L0 = -4 * RAD, F0 = 55 * RAD;
  const N = Math.log(Math.cos(P1) / Math.cos(P2)) / Math.log(Math.tan(Math.PI / 4 + P2 / 2) / Math.tan(Math.PI / 4 + P1 / 2));
  const FF = Math.cos(P1) * Math.pow(Math.tan(Math.PI / 4 + P1 / 2), N) / N;
  const rho = phi => FF / Math.pow(Math.tan(Math.PI / 4 + phi / 2), N), RHO0 = rho(F0);
  const raw = (lon, lat) => { const p = rho(lat * RAD), t = N * (lon * RAD - L0); return [p * Math.sin(t), RHO0 - p * Math.cos(t)]; };
  function makeProj(year) {                            // framed on the year's lights, so the chart holds still within a year
    const st = S.stations.filter(s => { const y = s.years[year]; return y && (y.keepers || y.records); });
    const pts = st.map(s => raw(s.lon, s.lat)), xs = pts.map(c => c[0]), ys = pts.map(c => c[1]);
    let x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const mx = 0.08 * (x1 - x0), my = 0.05 * (y1 - y0); x0 -= mx; x1 += mx; y0 -= my; y1 += my;
    const s = Math.min(W / (x1 - x0), H / (y1 - y0)), ox = (W - s * (x1 - x0)) / 2, oy = (H - s * (y1 - y0)) / 2;
    return (lon, lat) => { const [x, y] = raw(lon, lat); return [ox + (x - x0) * s, H - (oy + (y - y0) * s)]; };
  }

  // ---------------------------------------------------------------- sunset and sunrise (the sunrise equation; against skyfield on
  // 21 Oct 1887 at 132 lights: mean error 4 min, worst 7)
  const jdNoon = iso => Date.parse(iso + 'T12:00:00Z') / 86400000 + 2440587.5;
  function solar(jd, lat, lon) {                      // transit and half-day arc (days) for the day whose noon is jd
    const n = Math.round(jd - 2451545.0), Js = n - lon / 360;
    const M = (357.5291 + 0.98560028 * Js) % 360, Mr = M * RAD;
    const Cc = 1.9148 * Math.sin(Mr) + 0.02 * Math.sin(2 * Mr) + 0.0003 * Math.sin(3 * Mr);
    const lam = ((M + Cc + 180 + 102.9372) % 360) * RAD;
    const transit = 2451545.0 + Js + 0.0053 * Math.sin(Mr) - 0.0069 * Math.sin(2 * lam);
    const sd = Math.sin(lam) * Math.sin(23.4397 * RAD), cd = Math.cos(Math.asin(sd));
    const cw = (Math.sin(-0.833 * RAD) - Math.sin(lat * RAD) * sd) / (Math.cos(lat * RAD) * cd);
    return [transit, Math.acos(Math.max(-1, Math.min(1, cw))) / (2 * Math.PI)];
  }
  function sunTimes(night, lat, lon) {                // minutes after noon GMT: sunset that evening, sunrise next morning
    const j = jdNoon(night), [t1, w1] = solar(j, lat, lon), [t2, w2] = solar(j + 1, lat, lon);
    return [(t1 + w1 - j) * 1440, (t2 - w2 - j) * 1440];
  }

  // ---------------------------------------------------------------- the lamps
  function hash(s) { let h = 2166136261; for (const ch of s) h = Math.imul(h ^ ch.charCodeAt(0), 16777619); return ((h >>> 0) % 10000) / 10000; }
  function lampState(l, ts) {
    const L = l.light;
    if (!L || !L.cycle) return [1, (L && L.steps[0][1]) || 'white'];
    let ph = (ts + l.phase * L.cycle) % L.cycle;
    for (const [on, col, sec] of L.steps) {
      if (ph < sec) { if (!on) return [0, col]; return [L.kind === 'revolving' ? Math.pow(Math.sin(Math.PI * ph / sec), 2) : 1, col]; }
      ph -= sec;
    }
    return [0, 'white'];
  }

  // ---------------------------------------------------------------- dates
  const dayName = iso => { const d = new Date(iso + 'T12:00:00Z'); return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`; };
  const addDays = (iso, k) => new Date(Date.parse(iso + 'T12:00:00Z') + k * 86400000).toISOString().slice(0, 10);
  function clockText(t) {
    const d = new Date(Date.parse(D.night + 'T12:00:00Z') + t * 60000);
    const h = d.getUTCHours(), mi = d.getUTCMinutes(), ap = h >= 12 ? 'P.M.' : 'A.M.', h12 = ((h + 11) % 12) + 1;
    const label = (h === 12 && mi < 1) ? 'noon' : (h === 0 && mi < 1) ? 'midnight' : `${h12}.${String(mi).padStart(2, '0')} ${ap}`;
    return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}, ${label}`;
  }

  // ---------------------------------------------------------------- the calendar
  let CL = null;                                      // layout
  function calLayout() {
    const w = cal.clientWidth, rows = CAL.rows, left = w < 520 ? 30 : 44;
    const cw = (w - left - 4) / 30, rh = Math.max(4, Math.min(7, cw * 0.17));
    cal.style.height = (rows * rh + 4) + 'px';
    cal.width = Math.round(w * dpr); cal.height = Math.round((rows * rh + 4) * dpr);
    CL = { w, left, cw, rh };
  }
  function drawCal() {
    const { w, left, cw, rh } = CL;
    cctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cctx.fillStyle = C.sea; cctx.fillRect(0, 0, w, CAL.rows * rh + 4);
    let year = null;
    cctx.font = `italic ${w < 520 ? 10 : 12}px ` + C.serif; cctx.textAlign = 'right';
    for (const r of CAL.nights) {
      const x = left + r.col * cw, y = 2 + r.lun * rh;
      if (r.light > 0) { cctx.fillStyle = `rgba(201,196,179,${(0.05 + 0.24 * r.light).toFixed(3)})`; cctx.fillRect(x, y, cw, rh); }
      const yr = r.night.slice(0, 4);
      if (yr !== year) { year = yr; cctx.fillStyle = C.dim; cctx.fillText(yr, left - 6, y + rh * 2); }
      const k = r.struck.length;
      if (k) {                                           // one stroke per station, full light, so it reads on any ground
        const sp = Math.min(2.1, (cw - 3) / k), sw = Math.max(0.7, Math.min(1.3, sp * 0.65));
        cctx.fillStyle = C.tally;
        for (let j = 0; j < k; j++) cctx.fillRect(x + 1.5 + j * sp, y + 0.8, sw, rh - 1.6);
      }
    }
    if (selected && CAL.byNight[selected]) {
      const r = CAL.byNight[selected], x = left + r.col * cw, y = 2 + r.lun * rh;
      cctx.strokeStyle = C.lamp; cctx.lineWidth = 1.5; cctx.strokeRect(x - 1.5, y - 1.5, cw + 3, rh + 3);
    }
  }
  function calPick(ev) {
    const r = cal.getBoundingClientRect(), { left, cw, rh } = CL;
    const col = Math.floor((ev.clientX - r.left - left) / cw), lun = Math.floor((ev.clientY - r.top - 2) / rh);
    return CAL.byCell[lun * 30 + col] || null;
  }
  function tipText(r) {
    if (!r) return '';
    const k = r.struck.length, moon = r.light > 0 ? `moon up, ${Math.round(r.light * 100)}% lit` : 'no moon at midnight';
    return `${dayName(r.night)} · ${r.reporting} station${r.reporting === 1 ? '' : 's'} reporting · ${k ? k + ' with a strike' : 'no strike'} · ${moon}`;
  }

  // ---------------------------------------------------------------- a night
  async function loadYear(y) {
    if (!yearCache[y]) yearCache[y] = fetch(`../data/nights/${y}.json`).then(r => r.ok ? r.json() : {}).catch(() => ({}));
    return yearCache[y];
  }
  async function selectNight(night, keepTime) {
    if (!CAL.byNight[night]) return;
    selected = night;
    const nights = await loadYear(night.slice(0, 4));
    if (selected !== night) return;                   // a later choice won
    const N0 = nights[night] || { entries: [], tallies: [], winds: [], moon: null };
    const year = Math.min(1887, +night.slice(0, 4));
    if (year !== projYear) resize(year);
    const lights = [];
    for (const s of S.stations) {
      const y = s.years[year];
      if (!y || !(y.keepers || y.records)) continue;
      const [on, off] = sunTimes(night, s.lat, s.lon);
      let light = y.light;
      if (light === undefined) for (let d = 1; d < 9 && light === undefined; d++) light = (s.years[year - d] || {}).light ?? (s.years[year + d] || {}).light;
      lights.push({ id: s.id, name: s.name, s, light: light || null, on, off, phase: hash(s.id), xy: proj(s.lon, s.lat) });
    }
    const byId = Object.fromEntries(lights.map(l => [l.id, l]));
    for (const s of S.stations) if (!byId[s.id]) byId[s.id] = { id: s.id, name: s.name, s, xy: proj(s.lon, s.lat), off: 1440, unlisted: true };
    const r = CAL.byNight[night];
    D = { night, lights, byId, entries: N0.entries, tallies: N0.tallies, winds: N0.winds, moon: N0.moon, waxing: r.age < 14.77,
          meanSunset: lights.reduce((a, l) => a + l.on, 0) / lights.length, meanSunrise: lights.reduce((a, l) => a + l.off, 0) / lights.length };
    if (!keepTime) tNight = RM ? Math.max(D.meanSunset + 60, 600) : D.meanSunset - 30;
    $('nightTitle').textContent = `The night of ${dayName(night)}`;
    $('dateIn').value = night;
    $('calTip').textContent = tipText(r);
    if (location.hash.slice(1) !== night) history.replaceState(null, '', '#' + night);
    buildLog(); drawCal(); showStation(null); redraw();
  }

  // ---------------------------------------------------------------- the chart
  let projYear = 1887;
  function resize(year = projYear) {
    projYear = year;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = map.clientWidth; H = map.clientHeight;
    map.width = Math.round(W * dpr); map.height = Math.round(H * dpr);
    tl.width = Math.round(tl.clientWidth * dpr); tl.height = Math.round(tl.clientHeight * dpr);
    proj = makeProj(projYear);
    coastLayer = document.createElement('canvas'); coastLayer.width = map.width; coastLayer.height = map.height;
    const c = coastLayer.getContext('2d'); c.scale(dpr, dpr); c.beginPath();
    for (const ring of COAST) ring.forEach(([lo, la], i) => { const [x, y] = proj(lo, la); i ? c.lineTo(x, y) : c.moveTo(x, y); });
    c.fillStyle = C.land; c.fill('evenodd'); c.strokeStyle = C.line; c.lineWidth = 0.7; c.stroke();
    calLayout();
    if (D) { for (const l of Object.values(D.byId)) l.xy = proj(l.s.lon, l.s.lat); }
  }
  function daylight(t) {
    const ss = D.meanSunset, sr = D.meanSunrise, ramp = 40;
    if (t < ss - ramp / 2 || t > sr + ramp / 2) return 1;
    if (t < ss + ramp / 2) return 1 - (t - (ss - ramp / 2)) / ramp;
    if (t > sr - ramp / 2) return (t - (sr - ramp / 2)) / ramp;
    return 0;
  }
  function mix(a, b, k) {
    const pa = a.match(/\w\w/g).map(h => parseInt(h, 16)), pb = b.match(/\w\w/g).map(h => parseInt(h, 16));
    return 'rgb(' + pa.map((v, i) => Math.round(v + (pb[i] - v) * k)).join(',') + ')';
  }
  function drawTally(x, y, n, uncounted) {
    mctx.strokeStyle = C.tally; mctx.lineWidth = 1; mctx.globalAlpha = 0.8;
    const gw = 7, gh = 6, per = 8;
    let g = 0;
    for (let left = n; left > 0; left -= 5, g++) {
      const gx = x - (per * gw) / 2 + (g % per) * gw, gy = y + Math.floor(g / per) * (gh + 3), k = Math.min(5, left);
      mctx.beginPath();
      for (let j = 0; j < Math.min(4, k); j++) { mctx.moveTo(gx + j * 1.4, gy); mctx.lineTo(gx + j * 1.4, gy + gh); }
      if (k === 5) { mctx.moveTo(gx - 1, gy + gh - 1); mctx.lineTo(gx + 5.5, gy + 1); }
      mctx.stroke();
    }
    if (uncounted) { const gy = y + Math.ceil(n / 5 / per) * (gh + 3); mctx.beginPath(); mctx.arc(x, gy + 3, 2.6, 0, 7); mctx.stroke(); }
    mctx.globalAlpha = 1;
  }
  function arrow(x, y, fromDeg, len, col, alpha) {     // pointing the way the wind blows (from fromDeg, true north up)
    const a = (fromDeg + 180) * RAD, dx = Math.sin(a) * len, dy = -Math.cos(a) * len;
    mctx.strokeStyle = col; mctx.globalAlpha = alpha; mctx.lineWidth = 1.2; mctx.beginPath();
    mctx.moveTo(x - dx / 2, y - dy / 2); mctx.lineTo(x + dx / 2, y + dy / 2);
    const hx = x + dx / 2, hy = y + dy / 2, ha = Math.atan2(dy, dx);
    mctx.moveTo(hx, hy); mctx.lineTo(hx - 4 * Math.cos(ha - 0.5), hy - 4 * Math.sin(ha - 0.5));
    mctx.moveTo(hx, hy); mctx.lineTo(hx - 4 * Math.cos(ha + 0.5), hy - 4 * Math.sin(ha + 0.5));
    mctx.stroke(); mctx.globalAlpha = 1;
  }
  function wrap(text, maxW) {
    const words = text.split(' '), lines = []; let cur = '';
    for (const w of words) { const t = cur ? cur + ' ' + w : w; if (mctx.measureText(t).width > maxW && cur) { lines.push(cur); cur = w; } else cur = t; }
    if (cur) lines.push(cur);
    return lines;
  }
  function drawMap(ts) {
    mctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    mctx.fillStyle = mix(C.sea.slice(1), C.seaDay.slice(1), daylight(tNight));
    mctx.fillRect(0, 0, W, H);
    mctx.drawImage(coastLayer, 0, 0, W, H);
    // the winds: as printed (lamp) and as reconstructed (blue), shown from their hour for three hours, or all night if no hour
    for (const w of D.winds) {
      const l = D.byId[w.station]; if (!l) continue;
      const live = w.at == null ? 1 : (tNight >= w.at - 30 && tNight < w.at + 180) ? 1 : 0;
      if (!live) continue;
      const [x, y] = l.xy;
      if (w.reanalysis != null) arrow(x + 9, y - 9, w.reanalysis, 14, C.re, 0.8);
      if (w.keeper != null) arrow(x + 9, y - 9, w.keeper, 14, C.lamp, 0.75);
    }
    for (const l of D.lights) {
      const [x, y] = l.xy, lit = tNight >= l.on && tNight <= l.off;
      if (!lit) { mctx.fillStyle = C.dim; mctx.globalAlpha = 0.6; mctx.beginPath(); mctx.arc(x, y, 1.4, 0, 7); mctx.fill(); mctx.globalAlpha = 1; continue; }
      const [b, col] = RM ? [1, (l.light && l.light.steps.find(s => s[0]) || [1, 'white'])[1]] : lampState(l, ts);
      const c = LAMP[col] || C.lamp, fixed = !l.light || !l.light.cycle, r = fixed ? 5 : 3 + 9 * b;
      if (b > 0.02) {
        const g = mctx.createRadialGradient(x, y, 0, x, y, r);
        g.addColorStop(0, c); g.addColorStop(0.25, c); g.addColorStop(1, 'rgba(0,0,0,0)');
        mctx.globalAlpha = fixed ? 0.55 : 0.35 + 0.65 * b; mctx.fillStyle = g; mctx.beginPath(); mctx.arc(x, y, r, 0, 7); mctx.fill(); mctx.globalAlpha = 1;
      }
      mctx.fillStyle = b > 0.02 ? c : '#2c3338'; mctx.beginPath(); mctx.arc(x, y, 1.6, 0, 7); mctx.fill();
    }
    for (const t of D.tallies) {
      const l = D.byId[t.station]; if (!l) continue;
      if (tNight >= (t.at ?? l.off)) drawTally(l.xy[0], l.xy[1] + 8, t.killed, t.uncounted);
    }
    if (D.station) { const l = D.byId[D.station]; if (l) { mctx.strokeStyle = C.lamp; mctx.lineWidth = 1.2; mctx.beginPath(); mctx.arc(l.xy[0], l.xy[1], 9, 0, 7); mctx.stroke(); } }
    const fresh = D.entries.filter(e => e.at != null && tNight >= e.at && tNight < e.at + 120).slice(-3);
    const fs = W < 520 ? 11 : 13, maxW = Math.min(230, W * 0.42), placed = [];
    for (const e of fresh) {
      const l = D.byId[e.station]; if (!l) continue;
      mctx.font = `italic ${fs}px ` + C.serif;
      const [x, y] = l.xy, left = x > W * 0.55, lines = wrap(e.quotes[0], maxW).slice(0, 4), hgt = (lines.length + 1) * (fs + 3);
      let ty = y - hgt / 2;
      for (const p of placed) if (Math.abs(p.x - x) < maxW && ty < p.y + p.h + 6 && ty + hgt > p.y - 6) ty = p.y + p.h + 8;
      ty = Math.max(6, Math.min(H - hgt - 6, ty));
      const tx = Math.max(6, Math.min(W - maxW - 6, left ? x - 16 - maxW : x + 16));
      placed.push({ x, y: ty, h: hgt });
      const age = (tNight - e.at) / 120, alpha = age < 0.08 ? age / 0.08 : age > 0.75 ? (1 - age) / 0.25 : 1;
      mctx.globalAlpha = alpha;
      mctx.strokeStyle = C.dim; mctx.lineWidth = 0.6; mctx.beginPath(); mctx.moveTo(x + (left ? -4 : 4), y); mctx.lineTo(left ? tx + maxW : tx, ty + fs); mctx.stroke();
      mctx.fillStyle = 'rgba(10,17,24,0.72)'; mctx.fillRect(tx - 4, ty - 2, maxW + 8, hgt + 4);
      mctx.textAlign = 'left'; mctx.fillStyle = C.lamp; mctx.font = `${fs}px ` + C.serif;
      mctx.fillText(l.name + (e.time ? ',  ' + e.time : ''), tx, ty + fs);
      mctx.fillStyle = C.ink; mctx.font = `italic ${fs}px ` + C.serif;
      lines.forEach((s, i) => mctx.fillText(s, tx, ty + (i + 2) * (fs + 3)));
      mctx.globalAlpha = 1;
    }
    if (D.moon) {
      const m = D.moon[Math.max(0, Math.min(D.moon.length - 1, Math.round(tNight / 120)))], [alt, lit] = m;
      const mx = W - 28, my = 28, mr = 9;
      mctx.globalAlpha = alt > 0 ? 0.9 : 0.3;
      mctx.fillStyle = '#20282e'; mctx.beginPath(); mctx.arc(mx, my, mr, 0, 7); mctx.fill();
      mctx.fillStyle = C.moon; mctx.beginPath(); mctx.arc(mx, my, mr, -Math.PI / 2, Math.PI / 2, !D.waxing); mctx.fill();
      mctx.fillStyle = lit < 0.5 ? '#20282e' : C.moon;
      mctx.beginPath(); mctx.ellipse(mx, my, Math.max(0.01, mr * Math.abs(1 - 2 * lit)), mr, 0, 0, 7); mctx.fill();
      mctx.globalAlpha = 1;
      mctx.font = '11px ' + C.serif; mctx.fillStyle = C.dim; mctx.textAlign = 'right';
      mctx.fillText(alt > 0 ? `moon ${Math.round(lit * 100)}% lit` : 'moon down', mx - mr - 6, my + 4);
    }
    if (!D.entries.length && !D.winds.length) {
      mctx.font = `italic 14px ` + C.serif; mctx.fillStyle = C.dim; mctx.textAlign = 'center';
      mctx.fillText('No keeper’s entry is printed for this night.', W / 2, H - 18);
    }
  }
  function drawTimeline() {
    const w = tl.width / dpr, h = tl.height / dpr;
    tctx.setTransform(dpr, 0, 0, dpr, 0, 0); tctx.clearRect(0, 0, w, h);
    const X = t => 4 + (w - 8) * t / 1440;
    tctx.fillStyle = C.seaDay; tctx.fillRect(X(0), 10, X(1440) - X(0), 30);
    tctx.fillStyle = '#05090d'; tctx.fillRect(X(D.meanSunset), 10, X(D.meanSunrise) - X(D.meanSunset), 30);
    if (D.moon) {
      tctx.strokeStyle = C.moon; tctx.globalAlpha = 0.55; tctx.lineWidth = 1; tctx.beginPath();
      D.moon.forEach(([alt], i) => { const y = 25 - alt / 90 * 15; i ? tctx.lineTo(X(i * 120), y) : tctx.moveTo(X(0), y); });
      tctx.stroke(); tctx.globalAlpha = 1;
    }
    tctx.strokeStyle = C.rule; tctx.beginPath(); tctx.moveTo(X(0), 25); tctx.lineTo(X(1440), 25); tctx.stroke();
    for (const e of D.entries) if (e.at != null) { tctx.fillStyle = C.lamp; tctx.globalAlpha = 0.7; tctx.fillRect(X(e.at) - 0.5, 34, 1, 6); }
    for (const t of D.tallies) { const at = t.at ?? D.byId[t.station]?.off; if (at != null) { tctx.fillStyle = C.tally; tctx.globalAlpha = 0.9; tctx.fillRect(X(at) - 0.5, 10, 1.5, 8); } }
    tctx.globalAlpha = 1;
    tctx.font = '11px ' + C.serif; tctx.fillStyle = C.dim; tctx.textAlign = 'center';
    [[0, 'noon'], [360, '6 P.M.'], [720, 'midnight'], [1080, '6 A.M.'], [1440, 'noon']].forEach(([t, s]) => tctx.fillText(s, Math.min(Math.max(X(t), 18), w - 18), 54));
    tctx.strokeStyle = C.lamp; tctx.lineWidth = 1.5; tctx.beginPath(); tctx.moveTo(X(tNight), 6); tctx.lineTo(X(tNight), 44); tctx.stroke();
  }

  // ---------------------------------------------------------------- the log and the station
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const deg = d => d == null ? '?' : Math.round(d) + '°';
  function windLine(w) {
    const div = el('div', 'wind');
    div.append('wind as printed ', el('b', null, w.printed + (w.force ? `, force ${w.force}` : '')), ` (${deg(w.keeper)})`);
    if (w.reanalysis != null) div.append(' · reanalysis ', el('i', null, `${deg(w.reanalysis)}, ${w.speed} m/s`));
    return div;
  }
  function stationButton(id) {
    const l = D.byId[id], b = el('button', 'st', l ? l.name : id); b.type = 'button';
    b.addEventListener('click', () => showStation(id));
    return b;
  }
  function buildLog() {
    const log = $('log'); log.textContent = '';
    const make = e => {
      const div = el('div', 'entry'), head = el('div');
      head.append(stationButton(e.station), ' ', el('span', 'when', e.time || ''));
      div.append(head);
      for (const q of e.quotes) div.append(el('q', null, q));
      for (const w of D.winds.filter(w => w.station === e.station)) div.append(windLine(w));
      const a = el('a', null, `${e.report} report, p. ${e.page}`); a.href = e.scan; a.target = '_blank'; a.rel = 'noopener';
      div.append(a); e.el = div; return div;
    };
    const timed = D.entries.filter(e => e.at != null), untimed = D.entries.filter(e => e.at == null);
    timed.forEach(e => log.append(make(e)));
    if (untimed.length) { log.append(el('h3', null, 'This night, no hour printed')); untimed.forEach(e => log.append(make(e))); }
    if (!D.entries.length) log.append(el('p', 'small dim', 'No keeper’s entry is printed for this night.'));
    updateLog();
  }
  function updateLog() { for (const e of D.entries) if (e.el) e.el.classList.toggle('future', e.at != null && e.at > tNight); }
  function showStation(id) {
    const box = $('stationBox'); box.textContent = ''; D.station = id; redraw();
    if (!id) return;
    const l = D.byId[id], s = l.s, div = el('div', 'station');
    const close = el('button', 'close', '×'); close.type = 'button'; close.setAttribute('aria-label', 'Close'); close.onclick = () => showStation(null);
    div.append(close, el('h4', null, s.name), el('div', 'small dim', `${s.kind === 'light-vessel' ? 'light-vessel' : s.kind}, ${Math.abs(s.lat).toFixed(2)}° N, ${Math.abs(s.lon).toFixed(2)}° ${s.lon < 0 ? 'W' : 'E'}`));
    const t = el('table'), hr = el('tr');
    ['year', 'light, as printed', 'keepers', 'records', 'strike nights'].forEach((h, i) => { const th = el('th', i >= 3 ? 'num' : null, h); hr.append(th); });
    t.append(hr);
    for (let y = 1879; y <= 1887; y++) {
      const r = s.years[y]; if (!r) continue;
      const tr = el('tr');
      tr.append(el('td', null, y), el('td', null, r.character || ''), el('td', null, (r.keepers || []).join('; ')),
                el('td', 'num', r.records || ''), el('td', 'num', r.nights ? `${r.strikes} of ${r.nights}` : ''));
      t.append(tr);
    }
    div.append(t);
    const ws = D.winds.filter(w => w.station === id);
    if (ws.length) { div.append(el('div', 'small dim', 'This night:')); ws.forEach(w => div.append(windLine(w))); }
    if (l.unlisted) div.append(el('p', 'small dim', 'Not on this year’s lists.'));
    box.append(div);
    if (window.matchMedia('(max-width: 860px)').matches) box.scrollIntoView({ block: 'nearest', behavior: RM ? 'auto' : 'smooth' });
  }

  // ---------------------------------------------------------------- the loop and the controls
  function frame(now) {
    const dt = Math.min(0.1, (now - last) / 1000); last = now;
    if (D) {
      if (playing) { tNight += dt * SPEED; if (tNight > 1440) tNight = 0; }
      drawMap(now / 1000); drawTimeline();
      $('clock').textContent = clockText(tNight);
      if (Math.floor(tNight) !== frame.lastMin) { frame.lastMin = Math.floor(tNight); updateLog(); }
    }
    if (!RM || frame.dirty) requestAnimationFrame(frame);
    frame.dirty = false;
  }
  function redraw() { if (RM) { frame.dirty = true; requestAnimationFrame(frame); } }
  function scrub(ev) { const r = tl.getBoundingClientRect(); tNight = Math.max(0, Math.min(1440, (ev.clientX - r.left - 4) / (r.width - 8) * 1440)); redraw(); }
  tl.addEventListener('pointerdown', ev => { tl.setPointerCapture(ev.pointerId); scrub(ev); tl.onpointermove = scrub; });
  tl.addEventListener('pointerup', () => { tl.onpointermove = null; });
  tl.addEventListener('keydown', ev => {
    if (ev.key === 'ArrowRight') tNight = Math.min(1440, tNight + 15); else if (ev.key === 'ArrowLeft') tNight = Math.max(0, tNight - 15); else return;
    ev.preventDefault(); redraw();
  });
  $('play').addEventListener('click', () => {
    playing = !playing; $('play').textContent = playing ? 'Pause' : 'Play'; last = performance.now();
    if (RM && playing) requestAnimationFrame(function go(n) { frame(n); if (playing) requestAnimationFrame(go); });
  });
  $('play').textContent = playing ? 'Pause' : 'Play';
  map.addEventListener('click', ev => {
    if (!D) return;
    const r = map.getBoundingClientRect(), x = ev.clientX - r.left, y = ev.clientY - r.top;
    let best = null, bd = 14 * 14;
    for (const l of Object.values(D.byId)) { const d = (l.xy[0] - x) ** 2 + (l.xy[1] - y) ** 2; if (d < bd) { bd = d; best = l; } }
    showStation(best ? best.id : null);
  });
  cal.addEventListener('pointermove', ev => { const r = calPick(ev); $('calTip').textContent = r ? tipText(r) : (selected ? tipText(CAL.byNight[selected]) : ''); });
  cal.addEventListener('pointerleave', () => { $('calTip').textContent = selected ? tipText(CAL.byNight[selected]) : ''; });
  cal.addEventListener('click', ev => { const r = calPick(ev); if (r) selectNight(r.night); });
  cal.addEventListener('keydown', ev => {
    const k = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -30, ArrowDown: 30 }[ev.key];
    if (!k || !selected) return;
    ev.preventDefault();
    let n = addDays(selected, k);
    for (let i = 0; i < 40 && !CAL.byNight[n]; i++) n = addDays(n, Math.sign(k));
    if (CAL.byNight[n]) selectNight(n);
  });
  $('dateIn').addEventListener('change', ev => { const v = ev.target.value; if (CAL.byNight[v]) selectNight(v); else $('calTip').textContent = 'No reports cover that date (1879–1887).'; });
  window.addEventListener('hashchange', () => { const h = location.hash.slice(1); if (CAL.byNight[h] && h !== selected) selectNight(h); });
  window.addEventListener('resize', () => { resize(); drawCal(); redraw(); });

  Promise.all(['coast', 'stations', 'calendar'].map(f => fetch(`../data/${f}.json`).then(r => r.json()))).then(([coast, stations, calendar]) => {
    COAST = coast; S = stations;
    CAL = { nights: calendar.nights, rows: calendar.nights.at(-1).lun + 1, byNight: {}, byCell: {} };
    for (const r of CAL.nights) { r.col = Math.min(29, Math.floor(r.age)); CAL.byNight[r.night] = r; CAL.byCell[r.lun * 30 + r.col] = r; }
    $('rule').textContent = 'Light rhythms: ' + S.rule;
    resize();
    const h = location.hash.slice(1);
    selectNight(CAL.byNight[h] ? h : '1887-10-21');
    requestAnimationFrame(frame);
  });
})();
