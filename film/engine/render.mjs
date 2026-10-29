// render.mjs: the render farm. Owner: A. Headless Chrome (SwiftShader WebGL2) via puppeteer-core.
//
//   node render.mjs --stills 0,4,12.5 [--shot placeholder] [--p exposure=1.2,warmth=0.3] [--out ../dailies/x]
//   node render.mjs --from 0 --to 6 [--shot placeholder] --out ../scratch/engine/clip.mp4 [--workers 4] [--audio a.wav]
//   --skip birds,light  leaves those kit files out (the placeholder stands in)
//   node render.mjs --serve            (serve the repo on http://127.0.0.1:8737/film/engine/index.html for a browser)
//
// Every render runs inside systemd-run --user --scope -p MemoryMax=6G -p MemorySwapMax=0 (it re-executes itself
// there unless --scoped). At most 4 workers; each is its own headless browser, so its own SwiftShader GPU process.
// Frames go to <out>.frames/ and are kept until the mp4 is written: rerun the same command to resume.
import puppeteer from 'puppeteer-core';
import { spawn, spawnSync } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(here, '../..');
const argv = process.argv.slice(2);
const args = Object.fromEntries(argv.reduce((a, v, i, arr) => {
  if (v.startsWith('--')) a.push([v.slice(2), arr[i + 1] !== undefined && !arr[i + 1].startsWith('--') ? arr[i + 1] : true]);
  return a;
}, []));

// ---- the memory cap: re-exec inside a systemd scope
if (!args.scoped && !args.serve) {
  const r = spawnSync('systemd-run', ['--user', '--scope', '-q', '-p', 'MemoryMax=6G', '-p', 'MemorySwapMax=0',
    process.execPath, fileURLToPath(import.meta.url), ...argv, '--scoped'], { stdio: 'inherit' });
  process.exit(r.status ?? 1);
}

const FPS = +(args.fps || 24);
const CHROME = process.env.CHROME || '/usr/bin/google-chrome';
const WORKERS = Math.min(4, Math.max(1, +(args.workers || 4)));

// ---- a static server for the repo (fetch of .glsl and fonts needs http, not file://)
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.glsl': 'text/plain', '.json': 'application/json',
  '.csv': 'text/csv', '.ttf': 'font/ttf', '.woff2': 'font/woff2', '.png': 'image/png', '.jpg': 'image/jpeg', '.txt': 'text/plain', '.bin': 'application/octet-stream' };
function serve(port) {
  const srv = http.createServer((req, res) => {
    const p = path.normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname));
    const f = path.join(repo, p);
    if (!f.startsWith(repo) || !fs.existsSync(f) || !fs.statSync(f).isFile()) { res.writeHead(404); res.end(); return; }
    res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream', 'Cache-Control': 'no-store' });
    fs.createReadStream(f).pipe(res);
  });
  return new Promise(r => srv.listen(port, '127.0.0.1', () => r(srv)));
}
if (args.serve) {
  const port = +(args.port || 8737);
  await serve(port);
  console.log(`http://127.0.0.1:${port}/film/engine/index.html?shot=placeholder&t=4`);
} else {
  const srv = await serve(0), port = srv.address().port;
  const qs = new URLSearchParams({ render: '1' });
  if (args.shot) qs.set('shot', args.shot);
  if (args.skip) qs.set('skip', args.skip);
  if (args.p) for (const kv of String(args.p).split(',')) { const [k, v] = kv.split('='); qs.set('p.' + k.trim(), v.trim()); }
  const url = `http://127.0.0.1:${port}/film/engine/index.html?${qs}`;
  // pipe: Chrome exits when this process dies, even by SIGKILL (an OOM kill once left 8 renderers spinning for hours)
  const launch = () => puppeteer.launch({ executablePath: CHROME, headless: true, pipe: true, protocolTimeout: 900000,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-gpu-sandbox', '--js-flags=--max-old-space-size=2048'] });
  async function openPage(browser) {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    page.on('console', m => { if (['error', 'warning'].includes(m.type()) && !/Failed to load resource/.test(m.text())) console.error('[page]', m.text()); });
    page.on('pageerror', e => console.error('[pageerror]', e.message));
    await page.goto(url);
    await page.evaluate(() => window.ready);
    return page;
  }
  async function grab(page, t) {
    const r = await page.evaluate(async (t) => {
      const a = performance.now(); await renderFrame(t); const b = performance.now();
      const png = ENGINE.canvas.toDataURL('image/png').split(',')[1];
      return { png, render: b - a, encode: performance.now() - b };
    }, t);
    return { buf: Buffer.from(r.png, 'base64'), render: r.render, encode: r.encode };
  }
  const name = args.shot || 'film';
  try {
    if (args.stills) {
      const out = path.resolve(args.out || path.join(here, '../scratch/engine/stills')); fs.mkdirSync(out, { recursive: true });
      const browser = await launch();
      try {
        const t0 = Date.now(); const page = await openPage(browser); const tInit = Date.now() - t0;
        const tag = args.tag ? '_' + args.tag : '';
        for (const t of String(args.stills).split(',').map(Number)) {
          const f = path.join(out, `${name}${tag}_${t.toFixed(2)}.png`);
          const g = await grab(page, t); fs.writeFileSync(f, g.buf);
          console.log(f, `render ${g.render.toFixed(0)} ms, png ${g.encode.toFixed(0)} ms`);
        }
        console.log(`page init ${tInit} ms`);
      } finally { await browser.close(); }
    } else {
      const from = +(args.from || 0), to = +(args.to || 6), n = Math.round((to - from) * FPS);
      const out = path.resolve(args.out || path.join(here, `../scratch/engine/${name}.mp4`));
      const tmp = out.replace(/\.mp4$/, '') + '.frames'; fs.mkdirSync(tmp, { recursive: true });
      // Resume only frames made from the same sources: a stamp of every engine source file and the range. A killed run
      // with other inputs once left frames that a later run under the same name kept, splicing two cuts (29 Oct).
      {
        const crypto = await import('node:crypto');
        const h = crypto.createHash('sha256');
        for (const f of fs.readdirSync(here).filter(f => /\.(js|mjs|glsl|html)$/.test(f)).sort()) h.update(f).update(fs.readFileSync(path.join(here, f)));
        for (const d of ['assets', '../voice/takes']) {
          const dir = path.join(here, d);
          if (fs.existsSync(dir)) for (const f of fs.readdirSync(dir).sort()) h.update(f).update(String(fs.statSync(path.join(dir, f)).size));
        }
        h.update(`${from} ${to} ${FPS} ${JSON.stringify(args.p || '')} ${args.skip || ''}`);
        const stamp = h.digest('hex'), sf = path.join(tmp, 'STAMP');
        const old = fs.existsSync(sf) ? fs.readFileSync(sf, 'utf8') : null;
        if (old !== stamp) {
          const stale = fs.readdirSync(tmp).filter(f => f.endsWith('.png'));
          if (stale.length) console.log(`sources changed since these ${stale.length} frames were made: discarding them`);
          for (const f of stale) fs.unlinkSync(path.join(tmp, f));
          fs.writeFileSync(sf, stamp);
        }
      }
      let done = 0, rendered = 0, sumRender = 0, sumEncode = 0; const t0 = Date.now();
      await Promise.all(Array.from({ length: WORKERS }, async (_, w) => {
        let browser = null, page = null;
        try {
          for (let i = w; i < n; i += WORKERS) {
            const f = path.join(tmp, `f${String(i).padStart(6, '0')}.png`);
            if (fs.existsSync(f) && fs.statSync(f).size > 0) { done++; continue; }   // resume
            for (let attempt = 0; ; attempt++) {
              try {
                if (!browser) browser = await launch();
                if (!page) page = await openPage(browser);
                const g = await grab(page, from + i / FPS);
                fs.writeFileSync(f + '.part', g.buf); fs.renameSync(f + '.part', f);
                sumRender += g.render; sumEncode += g.encode; rendered++;
                break;
              } catch (e) {
                console.error(`\nworker ${w} frame ${i} attempt ${attempt}: ${String(e.message).split('\n')[0]}`);
                try { await browser?.close(); } catch {}
                browser = null; page = null;
                if (attempt >= 2) throw e;
              }
            }
            done++;
            process.stdout.write(`\r${done}/${n} frames  ${((Date.now() - t0) / 1000).toFixed(0)} s`);
          }
        } finally { try { await browser?.close(); } catch {} }
      }));
      const wall = (Date.now() - t0) / 1000;
      if (rendered) console.log(`\n${rendered} frames in ${wall.toFixed(1)} s wall with ${WORKERS} workers: ${(wall / rendered).toFixed(2)} s/frame throughput (incl. start-up); in-page render ${(sumRender / rendered).toFixed(0)} ms + png ${(sumEncode / rendered).toFixed(0)} ms per frame`);
      console.log(`encoding ${out}`);
      const ff = ['-y', '-v', 'error', '-framerate', String(FPS), '-start_number', '0', '-i', path.join(tmp, 'f%06d.png')];
      if (args.audio) ff.push('-ss', String(from), '-i', args.audio, '-shortest', '-c:a', 'aac', '-b:a', '256k');
      ff.push('-c:v', 'libx264', '-crf', String(args.crf || 14), '-preset', 'slow', '-tune', 'grain', '-pix_fmt', 'yuv420p',
        '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', out);
      await new Promise((res, rej) => spawn('ffmpeg', ff, { stdio: 'inherit' }).on('exit', c => c ? rej(new Error('ffmpeg ' + c)) : res()));
      if (!args.keep) fs.rmSync(tmp, { recursive: true });
      console.log(out);
    }
  } finally { srv.close(); }
}
