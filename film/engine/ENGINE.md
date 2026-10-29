# The engine: how a kit plugs in (owner A)

Read CONTRACT.md first; this is the practical half of it. The interface below is stable: if you need it to
change, write in REQUESTS.md.

## Running it

    cd film/engine
    node render.mjs --stills 2,4,9.5 --shot placeholder --out ../dailies/<kit>      # stills (PNG)
    node render.mjs --from 0 --to 6 --shot placeholder --out ../scratch/<kit>/x.mp4  # a clip (4 workers, resumable)
    node render.mjs --serve        # then open the printed URL in a browser to scrub (http, not file://)
    node render.mjs ... --p exposure=1.4,halation=0.5   # override print parameters (see print.js)
    node render.mjs ... --skip birds,light               # leave kit files out (placeholder stands in); ?skip= in a browser

render.mjs puts itself inside `systemd-run --user --scope -p MemoryMax=6G -p MemorySwapMax=0`, uses at most
4 workers (each its own headless Chrome, SwiftShader WebGL2), and keeps frames in `<out>.frames/` until the mp4
is written, so rerunning the same command resumes. `?shot=NAME&t=12.5` makes t shot-local; without `shot`,
t is film time through `ENGINE.setSequence([...])`.

## Load order (index.html)

`core.js, print.js, type.js` (classic scripts), then `light.js, birds.js` (loaded with `import()`, so ES modules
are fine; if the module exports `register(ENGINE)` the loader awaits it after import; a classic file that only
touches `window.ENGINE` works too), then `placeholder.js`, then `shots.js` (also via `import()`). light.js,
birds.js and shots.js are optional (skipped if missing). Other files of yours (birds.glsl, data) you fetch
yourself in `init` or `register`; paths are relative to film/engine/, and the server roots at the repo. placeholder.js only fills in what is still missing: once light.js registers the
kit `light` and the chunk `light`, the placeholder's stand-ins are not used; same for `birds`.

## A kit

    ENGINE.kit('light', {
      async init(gl, E) { /* compile programs, make buffers/targets; once per page */ },
      prepare(F) { F.common.uBeamAz = LIGHT.beamAz(F.tl, F.shot.beamFacesAt); },  // optional: publish uniforms
      draw(gl, F) { /* draw into the radiance target, which core has bound */ },
    });
    ENGINE.chunk('light', glslSource);        // or ENGINE.chunkFile('light', 'light.glsl') (fetched at init)

- `F` (one per frame): `t` film time, `tl` shot-local time, `shot` (the shot's def, any fields the coordinator
  puts there), `cam` (pos, fwd, right, up, fov, view, proj, viewProj), `common` (the uniforms below; every
  kit's `prepare` runs before any `draw`, so a uniform added there reaches everyone), `print` (print params).
- Before each kit's `draw`, core binds `E.hdr` (1920x1080 RGBA16F + 24-bit depth), sets the viewport, and
  resets state: blend off, depth test off, depth mask on. Set what you need. Do not clear it (core cleared it
  to black, depth 1, at the start of the frame). Kits draw in the order the shot lists them.
- Write **linear radiance**. Rough scale, for a print exposure of 1: 0.01 dark overcast night sky, 0.2 a mid
  grey, 1 a full light; the lens glass and beam core can go to 100s (halation and the print's shoulder handle
  it). Keep RGB equal (grey) for everything except the lamps' own red and green: any colour in the radiance
  comes out as a watercolour wash, so stray chroma will show.
- A full-screen kit can write `gl_FragDepth = depthOf(p)` so later raster kits (birds) depth-test against it.

## GLSL

`ENGINE.program(fragSource, { use: ['light'], vert, vertUse })` compiles with `#version 300 es`, highp, then
COMMON, then the named chunks, then your source. Default vertex shader: a full-screen triangle with `out vec2
vUv`; call `E.set(prog, F.common)` then `E.fullscreen(prog)`. With your own `vert` (without `#version`),
COMMON and `vertUse` chunks are prepended. `E.set(prog, {name: value})` sets uniforms by name, ignoring names
the program lacks; samplers take a texture or `{tex}`.

COMMON gives: `uT, uTl, uRes, uCamPos, uCamRight, uCamUp, uCamFwd, uTanHalfFov, uAspect, uView, uProj,
uViewProj, uNear, uFar, PI`, `vec3 cameraRay(vec2 fragCoord)`, `float depthOf(vec3 p)`, `vec3 project(vec3 p)`
(pixels, z = clip w), integer hashes `hashu, hash1, hash2i, hash3i`, `vnoise2, vnoise3` (value noise, [0,1]).

Helpers in JS: `E.target(w, h, {internal, format, type, filter, depth})`, `E.bind(target)`, `E.dataTexture(w,
h, data, opts)`, `E.rng(seed)` (mulberry32), `E.gauss(rng)`, `E.makeCamera(cam)`, `E.vec`.

## Shots (coordinator, shots.js)

    ENGINE.shot('lantern', {
      dur: 37, kits: ['light', 'birds'], beamFacesAt: 4,   // any extra fields are for kits to read
      camera: (tl) => ({ pos: [0, -30, 150], target: [0, -8, 0], fov: 36 }),   // metres, degrees (vertical)
      print: { exposure: 1.2 },                  // per-shot print params
      printAt: (tl) => ({ exposure: 1 + 0.1 * tl }),   // optional, varying through the shot
      type: (T, tl) => { T.text('South Bishop Lighthouse, 21 October 1887.', 960, 960, { size: 34, italic: true }); },
    });
    ENGINE.setSequence(['cold', 'lantern', ...]);

## Type (type.js)

Old Standard TT (SIL OFL 1.1, fonts/OFL.txt). In `shot.type(T, tl)`: `T.text(str, x, y, {size, italic, bold,
align, mode, alpha, tracking, caps})`, `T.run([{text, italic}, ...], x, y, o)` for a line set like the printed
reports, `T.block(lines, x, y, o)`, `T.tally(n, x, y, {h})` (tally in fives), `T.measure`. `mode: 'light'`
(default) is lettering burnished out of the dark; `mode: 'ink'` prints dark. Type goes through the print, so
it is grained at its edges like engraved lettering.

## Determinism

Everything a function of t: seeded randomness only (`E.rng`, the GLSL hashes), no Date, no Math.random, no
state between frames. Check: render one t twice in separate runs and `cmp` the PNGs.

## The print (print.glsl, print.js)

Parameters and defaults are in print.js, one line each. Per shot: `print: {...}` or `printAt(tl)`; for tests:
`--p name=value`. The grain (`grainPitch`, `grainPasses`, `grainSeed`) is made once per page from a seed and
is fixed to the frame, like a print's; the image moves under it (`grainDrift` > 0 lets it creep, default 0).

**What it does, in order.** Lens: a halation pyramid (13-tap down, tent up) adds a glow round anything
bright; vignette; softer toward the corners. Burnish level: `ell = 1 - exp(-2.5 (exposure Y)^gamma)`, with a
toe below which the plate stays the rocked ground (velvet black). Ink: the asked reflectance between the
ink's black and the paper, turned into an ink load, then the grain added in ink load (not in reflectance:
in reflectance sRGB blows the grain up in the darks; in ink load its sRGB size scales with brightness, which
is what the scans show). The grain is half "pits that survive the burnisher" (a soft threshold of the plate's
pit depth against the burnish level: dark specks in the lights, pale ones in the darks) and half the ground's
own texture (the velvet), fading where the plate is polished. Ink on paper per channel (Beer-Lambert), so a
warm ink goes brown in the half-tones; plate tone left by the wipe, in long soft swirls, heavier in the darks;
paper relief in the lights. Colour: any chroma in the radiance (the lamps' red and green) is laid on like a
watercolour wash, transparent over the ink, as prints were hand-coloured. Plate mark: the plate inset from the
frame, corners rounded, a hairline of ink in the bevel and the emboss in the paper; `plateAspect: 0.8` puts a
4:5 plate in the centre for the social cut.

**The ground.** `makeGround` in print.js walks a rocker across the plate in 28 directions; each rock stabs a
row of pits, one per tooth (pitch 3.4 px, i.e. the frame is a detail of a print seen close), depth varying
with pressure along the blade and from rock to rock. The summed depth is ranked to uniform, so the mean ink
equals the asked tone. With many directions the rows vanish into an isotropic, fine, sandy grain, which is
what the scans show (no visible rows; see below). Fewer passes (`grainPasses=6`) would show the rocker's rows.

**What the look rests on (measured from two scans; `film/scratch/engine/tools/measure.py`, `chart.py`).**
- William Pether after Joseph Wright, *A Philosopher Giving a Lecture on the Orrery*, mezzotint, 1768
  (Science History Institute, digital.sciencehistory.org/works/37720d47z, 10014x8400 px, ~440 ppi).
- John Martin, *Pandemonium*, mezzotint, 1831 (Yale Center for British Art, tms:31729, public domain IIIF).
- Measured at ~440 ppi: the grain's autocorrelation half-width is 2 px (both prints); grain std (sRGB, after
  removing the tone with a 16 px box) is 4-5 in the darks (L 60-70), 12-19 in the half-tones (L 90-125),
  22-25 in the lights (L 100-136), 4-7 on bare paper. The darkest ink is 10-14x darker than the paper (linear),
  a warm umber-black in Pether's impression and a near-neutral black in Martin's; the paper is cream.
- Our chart shot (`--shot chart`) measured the same way: half-width 2 px; std 3-7 in the darks, 14-22 in the
  half-tones and lights, 5.5 near paper. So the grain is matched to the scans in size and in how its contrast
  varies with tone, not invented by eye. Our black is deeper (about 30:1) than the scans' (a scan lifts it, and
  the film is a night).
- From the crops: tone is continuous at viewing distance, and the grain is a fine sand of dark specks in the
  lights and a soft mottle in the darks, with no lines; scraped highlights are crisp, burnished ones soft;
  plate tone fills the plate and stops at the plate mark; the lettering is engraved in the margin below.

**Invented (judgement, not measurement):** the exact tone curve and toe, the halation strengths, the wipe
pattern, the paper texture, the rocker's 28 directions and pitch (chosen to match the measured grain size),
the watercolour wash for the lamps' colour (hand-colouring is a real practice, but these lamps' wash is ours),
the plate mark's width. The frame being "a detail of a print seen close" is a choice of scale.

**Checks you can rerun.** Determinism: the same t in two runs, and as a worker frame, gave byte-identical PNGs
(placeholder, t = 4 and 6.5; control: t = 4 vs the next frame differ in 368k pixels). Boil: `tools/boil.py`
gives the per-pixel temporal std over 24 frames in static patches against the spatial grain std: 0.00 with the
screen fixed, 0.9-1.0 with `grainDrift=40` (the control), so motion reads through a grain that stays put.

## Frame time (measured 28 Oct, 1920x1080, SwiftShader, 4 workers, 12-core machine)

- Placeholder scene + print + PNG: 0.46-0.58 s/frame throughput (144 frames in 67-83 s wall, start-up included);
  about 1.5-1.9 s per frame inside each worker.
- With B's light.js and C's birds.js as of 11:50: 3.6 s/frame throughput over 24 frames (12.8 s per frame per
  worker), so the scene kits, not the print, set the budget. Each page takes ~4 s to start (the ground is made
  in JS); that is amortised over a long render.
