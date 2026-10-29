# Engine contract (read first; owned by the coordinator, change only by asking)

The film: film/TREATMENT.md. This file is how the parts fit together, so three
people can build them at once.

## Runtime

- One page, `film/engine/index.html`, that renders any frame as a pure
  function of film time: `await window.renderFrame(t)` (t in seconds), then
  the canvas holds the frame. No state carried between frames, so frames can
  be rendered in any order by several workers.
- 1920x1080, 24 fps. WebGL2 for the picture; a 2D canvas over it for type.
  Headless Chrome via puppeteer-core (start from `~/git/vid/engine/render.mjs`:
  workers, resume from frames already on disk). Software GL (SwiftShader) is
  what headless Chrome has here: budget about 2 s per frame at 4 workers.
- A `?t=12.5&shot=lantern` query renders one still, for dailies and tests.

## Two passes per frame

1. **Scene pass** into a half-float target: linear radiance (luminance is
   enough; the film is monochrome except the lamps' own red and green, so
   carry RGB). Sky, sea, rock, tower, lantern, beam volume, birds.
2. **Print pass** (owner A): radiance to ink, as a **mezzotint** printed in
   warm sepia ink on paper: the plate starts black and lights are burnished
   out of it; tone carried by a rocker-grain screen (fine, irregular, cross
   directional dots), plate tone in the darks, paper texture showing through
   the lights, a little halation round the lamp, a faint plate mark at the
   frame edge. Lamp colours (red, green) survive the print as the only colour.

## World (owner B fills in the real numbers from research)

- Units: metres. Origin: the focal plane centre of the South Bishop's lamp.
  y up; sea level at y = -H_focal (Findlay or the Trinity House record; until
  researched, 44). x east, z south.
- The beams (amended after B's research): "One rev. br. lt., 20 secs."
  (Findlay 1887) came from a first-order lens of **eight faces** (Royal
  Commission 1861, visit of 1859; no later change found), so **eight beams,
  the lens turning once in 160 s**, a flash every 20 s lasting about 2.4 s.
  Direction of rotation not recorded: clockwise seen from above,
  reconstructed. Each shot sets the phase (when a beam faces the camera).
- Weather at South Bishop that night: S.E. force 4, overcast, misty (the
  printed entry). Mist is a 3D density field drifting with the wind.

## Shared modules and who owns them

| file | owner | provides |
|---|---|---|
| `core.js`, `print.glsl`, `type.js`, `render.mjs`, `index.html` | A | the loop, render targets, camera, the print pass, type overlay, the render farm |
| `light.js`, `light.glsl` | B | `beamAz(t)`; GLSL `float illum(vec3 p, float t)` (irradiance at a world point from beam, lens glow and dawn sky, the same function the beam volume uses, so birds are lit exactly where the beam is seen); sky, sea, rock, tower, lantern geometry; the beam volume |
| `birds.js`, `birds.glsl` | C | a deterministic bird simulation `birdsAt(t, shot)` (positions, headings, wingbeat phase, species, state: flying, circling, striking, fallen) and their drawing, lit only by `illum()` |
| `shots.js`, `TREATMENT.md` | coordinator | the shot list: camera, time ranges, which kits are on |

A shared GLSL chunk is included by string concatenation; B's `illum()` is
the only lighting function in the film.

## Rules every kit keeps

- Deterministic: seeded randomness only, everything a function of t.
- Memory: render processes inside `systemd-run --user --scope -p
  MemoryMax=6G -p MemorySwapMax=0`, and at most 4 workers. Put this in
  render.mjs, not only in a message.
- Scratch in your own folder `film/scratch/<kit>/` (gitignored); stills you
  want seen in `film/dailies/<kit>/`.
- Don't commit; the coordinator commits at checkpoints. Touch only your own
  files; if you need a change in someone else's, write it in
  `film/engine/REQUESTS.md` with your name.
- Everything visible is either recorded or reconstructed, and the kit's
  notes say which (film/TREATMENT.md, true/reconstructed table).
