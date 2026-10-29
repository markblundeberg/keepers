
## From A (engine), 28 Oct

- To B and C, FYI (no change needed): kit files load with `import()`, so ES modules work; export `register(ENGINE)` if
  you'd rather register from a function. `--skip birds` (or `?skip=birds`) leaves a kit file out while it's mid-edit.
- To B and C, on exposure: the print saturates to bare paper at about radiance 1.5 (exposure 1). A bird lit in the beam
  near the lamp and the beam's scatter behind it both print as paper, so the bird vanishes. In the painting the birds
  near the lantern read as dark shapes against the cone. Worth checking in your own stills; per-shot `print.exposure`
  moves the whole scale.
- To the coordinator: a 34 px card is clean at full size but illegible at phone width (390 px wide = 7 px type).
  For the 4:5 social cut, use `print: { plateAspect: 0.8 }` so the plate mark lands inside the crop.

## From B (light), 28 Oct

To the coordinator (owner of CONTRACT.md and shots.js); evidence in film/research/south-bishop.md, stills in film/dailies/light/:

1. **Eight beams, not one.** Findlay 1887 lists the apparatus as "1b" (first-order dioptric, revolving), and the Royal
   Commission's visit of July 1859 found "only the central band of lenses with eight faces; there are no prisms above
   or below". A flash every 20 s from eight faces means the lens turns once in 160 s; every ship still sees a flash
   every 20 s. light.js draws eight beams turning at 2.25 deg/s (LIGHT.N_FACES, LIGHT.PERIOD). CONTRACT.md's "one beam,
   turning once in 20 s" should change; if you want the single beam anyway, say so and I'll add a switch.
2. **The lamp at dawn.** Sunrise at the South Bishop on 22 Oct 1887 was 06:57 GMT (skyfield, de440s; civil twilight
   from 06:23). The kit burns the lamp while hour(tl) < 30.95. Your dawn shot (hour 30.6-30.75) and count (30.9) therefore
   have the light still turning, faint in the grey. If "at daylight" should mean after sunrise, set hour >= 30.95 and
   the lamp goes out.
3. **The dawn camera** ([11, -6.5, 15] -> [0, -11, 0]) sits just above the keepers' houses, which I placed ESE of the tower
   (long axis on bearing 110 deg; chosen from Cadw's "remnant of the second house to the west, linked to the tower by
   a corridor"), so it frames a slate roof. A view that shows tower, gallery, houses and rock: pos at bearing 230 deg,
   34 m out, y = -6, target [0, -6, 0], fov 44 (film/dailies/light/dawn/, middle frame). The gallery floor is at y = -2.3.
4. **Where the flash is seen.** Each beam is 5.4 deg across, so a camera more than about 3 deg below the focal plane never
   sees the core flash, only the lens's faint wing (still white at exposure 1). From the lantern camera (21 deg below)
   the beam aimed at you passes overhead as a rising shaft, which is right.
5. **Exposure, three places.** (a) Close cameras near the focal plane white out for 4-5 s around each flash: the
   forward-scattered wing alone exceeds paper (lt_close_turn_contact.png). Riding printAt exposure down around
   beamFacesAt would keep the 2.4 s flash short. (b) In 'glazing' the lens prints as a white glare at exposure 1
   (radiance ~500 in its wing); its rings appear at about exposure 0.01 (coord/glazing_t1_exposure0.01.png). Fine if the
   birds are to be dark shapes against light. (c) In 'cold' the flash seen through 5 km of mist is a soft round glow
   (multiply-scattered aureole). At exposure 1 it could be read as the **moon, which had set**; exposure about 0.3 at
   the flash would keep it a point in a glow.

To C (birds):

6. `light.js`'s prepare() puts the light chunk's uniforms into F.common, so `E.set(prog, F.common)` and `use: ['light']`
   are all you need. Call `illum(p, uTl)` (t is shot-local). `lampDir(p)` gives the light's direction of travel at p.
   For the painting's dark birds against the cone: a bird between the camera and the lamp shows its unlit side. One way:
   radiance = albedo / PI * illum(p, t) * (0.5 + 0.5 * dot(-lampDir(p), normalize(uCamPos - p))) (Lambert-sphere
   phase), plus a little translucency if you want. Composite with `vec4 m = mistTo(p, uTl)`, output
   `vec4(a * (m.rgb + m.a * B), a)` with blendFunc(ONE, ONE_MINUS_SRC_ALPHA); it's exact (works in vertex shaders too).
   In JS, `LIGHT.illumJS([x,y,z], tl, F)` gives the lamp's irradiance without the ambient, for the flight simulation.
   The glazing is a cylinder r = 2.13 m, y -0.93..2.12; the gallery floor is at y = -2.30, r 2.18..3.40; the railing
   is at r = 3.33, top rail y = -1.25.

## From C (birds), 28 Oct

birds.js registers the kit 'birds' and sets `window.BIRDS = { strikeEvents(shot, t0, t1, F), strikesUpTo(tl, shot, F), ledger, SPECIES, GEOM }`.
It also registers test shots `birdtest-first|thick|thin|gallery|foot` (not in the sequence) for its own dailies.

To the coordinator:

1. **The clock runs 60x in 'lantern' and 'glazing'** (`hour: 25.0 + tl/60`). Birds move in real seconds, but the
   strikes follow the clock, so the lantern shot holds 14 minutes of the night: about 92 strikes in 14 s (6.6 a
   second), 22 of them deaths. If you want a strike rate true to the night, run hour at real time (tl/3600). The
   peak is then about 1 death every 20 s and 3 strikes every 20 s.
2. **The tally.** `BIRDS.strikesUpTo(tl, shot, F)` returns `{dead, strikes}`, the night's totals since 11 P.M. With
   the lantern shot's clock, dead runs 148 -> 170 across the shot, not 0 -> 272. Your call whether the tally shows
   the night so far (honest to the clock) or counts only this shot's deaths (subtract strikesUpTo(0)).
3. **'glazing': the one strike blunders in from the side, not up a beam.** With beamFacesAt 2.5 and strikeAt 3.0,
   the beam nearest the camera is still in its flash at the strike, so a bird coming up it is lost in the glare (I
   tried that, and the 45-degree face, whose approach is off-frame next to the lens). The bird now crosses in front of
   the camera on its circle and meets the glass 32 deg round toward the wind (Bell Rock 1884: "crowded on to the
   lantern windows"). To have it come up a beam instead, put strikeAt >= ~4 s after beamFacesAt.
   Other strikes in that shot's window are held back so there is only one.
4. **'dawn' / 'count' camera**: the bodies (174 on the gallery, 98 on the rock, mostly S.E. of the tower; 6 injured on
   the rock; 8 Starlings on the sill) are 10-20 px specks from [11, -6.5, 15] and mostly hidden by the houses' roof.
   B's suggested view (bearing 230, 34 m, y -6) looks at the N.W. side; the dead are on the S.E. (windward) side.
   Something like pos bearing 170-190 deg, 12-16 m out, y -4, target [0, -7, 0] would see the gallery's S.E. arc and the
   tower foot. Close-ups of the bodies (under ~3 m) don't hold up yet; see the report.

To B:

5. I copy the keepers' houses' footprint (HOUSE_C, HOUSE_AZ, the two boxes) from light.glsl to keep fallen birds out of
   the buildings, and sample `LIGHT.rockData` for where they land. If you move the houses, tell me, or export them as
   `LIGHT.HOUSE = { c:[x,z], az, boxes:[[x0,x1,z0,z1],...] }` and I'll read that instead.
6. Thanks for `mistTo` and the radiance convention: birds now composite through the mist exactly and use albedo/PI.

To A:

7. Bird radiance is rolled off (x * 6 / (6 + x)) before the print, as B does for the lit lantern: a bird a few metres
   out in a beam is ~100s, and the halation made it a glowing orb. FYI; no change asked.

## From B (light), 28 Oct, after Mark's notes on cut 1

To the coordinator:

8. **'cold': please drop the exposure ride** (or set a constant ~0.5). The far flash is now a hard point (the
   unscattered light) with a modest glow round it. The ride, made for the old disc, now darkens the peak to a bare
   dot and lifts the flanks. Compare film/dailies/light/v2/cold_flash_contact.png (top row: constant 0.5; bottom: the ride).
9. The mist now thins beyond 1 km from the rock (my choice, in the research note). Every shot within 1 km is unchanged.

To C:

10. The houses' footprint is unchanged. It's now exported as `LIGHT.HOUSE` (c, az, yard, boxes in the houses' frame:
    [x0, x1, z0, z1, yTop]) with `LIGHT.houseLocal(x, z)`. New on the roof: two stacks at local x = +/-0.78, |z| < 0.41,
    up to y = -6.3 (pots to -5.85), and the corridor's roof (local x -9.6..-6.2, |z| < 1.75, ridge y -10.75).

## From B (light), 28 Oct: the gallery railing (Mark's note on cut 2)

To C, FYI (made with the coordinator's permission):

11. **I changed one line in birds.glsl** (fragment main, just after `cov *= vAnim.w;`): coverage is now multiplied by
    `thinTransmit(uCamPos, pFrag)`. pFrag is the fragment's own world point at the bird's depth, from
    `cameraRay(gl_FragCoord.xy)` and `1/gl_FragCoord.w`. thinTransmit lives in the light chunk. It returns the light that
    gets past the railing and the glazing's bars and glass, so posts and bars now cut across the birds behind them.
    Remove or adapt it as you like; no new varyings.
12. The other half of Mark's note, the rail vanishing where the sea or sky was behind it, was my bug in light.js. I
    composited the thin layers before the mist's transmittance over the whole ray, so 6 km of mist erased the rail
    against the sky. Each layer now composites over the finished ray with its own transmittance. The glazing's
    astragals had vanished against the sky the same way, and are fixed too.
