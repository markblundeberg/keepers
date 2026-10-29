// Strike times for the sound mix: every strike event the birds kit draws, in film time, with its kind, hardness
// and distance from that shot's camera (so near strikes are loud and far ones faint).
//   node film/sound/dump_strikes.mjs [out.json]      (run from the repo; uses film/engine's puppeteer)
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const engine = path.join(here, '..', 'engine');
const require = createRequire(path.join(engine, 'render.mjs'));
const puppeteer = require('puppeteer-core');
const out = process.argv[2] || path.join(here, 'strikes_i.json');

const browser = await puppeteer.launch({ executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: true,
  args: ['--allow-file-access-from-files', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
try {
  const page = await browser.newPage();
  page.on('pageerror', e => console.error('[pageerror]', e.message));
  await page.goto(pathToFileURL(path.join(engine, 'index.html')).href + '?render=1');
  await page.evaluate(() => window.ready);
  const events = await page.evaluate(() => {
    const E = window.ENGINE, B = window.BIRDS, out = [];
    let t0 = 0;
    for (const name of E.sequence) {
      const s = E.shots[name];
      if (B && (s.kits || []).includes('birds')) {
        const F = { shot: s, tl: 0, t: t0, cam: { pos: s.camera(0).pos } };    // what the kit reads from a frame
        for (const e of B.strikeEvents(s, 0, s.dur, F)) {
          const cam = s.camera(e.t);
          const d = Math.hypot(...cam.pos.map((c, i) => c - e.pos[i]));
          out.push({ t: +(t0 + e.t).toFixed(3), shot: name, kind: e.kind, hard: e.hard, dist: +d.toFixed(1) });
        }
      }
      t0 += s.dur;
    }
    return out;
  });
  fs.writeFileSync(out, JSON.stringify(events));
  const by = {};
  for (const e of events) by[e.kind] = (by[e.kind] || 0) + 1;
  console.log(`${events.length} strike events -> ${out}`, by);
} finally {
  await browser.close();
}
