// light.glsl: the South Bishop light, the night's mist, and the one lighting function of the film. Owner: B.
// Included as the GLSL chunk 'light' (E.program(src, {use: ['light']})); set its uniforms with LIGHT.uniforms(F).
// Facts and their status: film/research/south-bishop.md. Units: metres; origin the flame; x east, y up, z south.
//
// What a kit uses:
//   float beamAz(float t)          bearing (rad, clockwise from north) of lens face 0 at shot time t; faces k at +k*TAU/8
//   float illum(vec3 p, float t)   irradiance at p from the lamp (beams, escaping light, lens glow), the light the lit
//                                  mist throws about, and the dawn sky. The same terms the beam volume scatters.
//   vec3  lampDir(vec3 p)          unit vector from the flame toward p (the direction the lamp's light travels at p)
//   float mistDensity(vec3 p, float t)   scattering coefficient (1/m) of the mist at p
//   float mistPhase(float c)       phase function (1/sr), c = cos(angle between the light's travel and the view ray reversed)
//   vec4  mistTo(vec3 p, float t)  .rgb = in-scattered radiance between the camera and p, .a = transmittance.
//                                  A bird of radiance B and coverage a, blended (ONE, ONE_MINUS_SRC_ALPHA) as
//                                  vec4(a * (m.rgb + m.a * B), a) over the light kit's frame, composites exactly.
// t is shot-local time (uTl). Everything is a pure function of (p, t) and the uniforms.

precision highp sampler3D;
uniform float uLightPhase;   // bearing of face 0 at t = 0 (set per shot by LIGHT.uniforms)
uniform float uLightLamp;    // 1 = lit, 0 = out
uniform float uLightDawn;    // 0 = night, 1 = grey overcast morning
uniform float uLightMist;    // multiplier on the night's mist (1 = as chosen in research/south-bishop.md)
uniform sampler3D uLightNoise;  // 64^3 tileable smooth noise, zero mean, unit variance

#define LT_TAU 6.28318530718
const float LT_N      = 8.0;      // faces of the lens band ("the central band of lenses with eight faces", RC 1861)
const float LT_FLASH  = 20.0;     // seconds between flashes ("One rev. br. lt., 20 secs.", Findlay 1887)
const float LT_PERIOD = 160.0;    // one turn of the lens: 8 x 20 s (inferred)
const float LT_SEA    = -43.9;    // high water: the flame is 144 ft above it (Findlay 1887)
const float LT_SIG    = 1.5e-3;   // mean extinction of the mist round the rock, 1/m (chosen: visibility about 2.6 km)
// The mist is patchy: thickest within about 1 km of the rock (where the record is), thinner beyond (visibility about
// 6.5 km), so that a ship 5 km off sees the flash as a hard point in a modest glow (chosen; research note).
const float LT_R_NEAR = 1000.0, LT_SIG_FAR = 0.6e-3;
const vec3  LT_WIND   = vec3(-4.74, 0.0, -4.74);  // S.E. force 4 = 6.7 m/s, blowing toward the N.W.
// Photometry, in the film's radiance units (scaled so the print's exposure 1 suits a beam seen side-on, about 1). LT_IF: the flame's intensity (per sr). Each face gathers the flame's light
// over 45 deg of azimuth and +/-26 deg of elevation (0.69 sr) at 80% transmission: LT_PHI. The beam's 1/e angular
// radius LT_BETA gives a 5.4 deg full width at half maximum = flame diameter 8.6 cm / focal length 0.92 m.
const float LT_IF     = 3.75e3;
const float LT_PHI    = 2.05e3;
const float LT_W0     = 0.38;     // beam radius at the lens (m)
const float LT_BETA   = 0.0566;   // beam angular radius (rad, 1/e)
const float LT_FOCAL  = 0.92;
const float LT_FLAME_R = 0.043, LT_FLAME_H = 0.055;  // half width, half height of the flame (m)
const float LT_FLAME_L = 3.1e5;   // the flame's radiance, seen through a face that is aimed at you (x 0.8)
// Geometry (research/south-bishop.md: lantern 4.28 m across, glazed 3.05 m, lower wall 1.37 m, tower 11.3 m)
const float LT_R_GLAZE = 2.13, LT_Y_GLAZE0 = -0.93, LT_Y_GLAZE1 = 2.12;
const float LT_Y_GALLERY = -2.30;
const float LT_R_LENS = 0.92, LT_LENS_H = 0.45;
const float LT_DAWN_E = 3.0;      // irradiance from the overcast morning sky on a level surface
const float LT_DAWN_L = 0.75;     // radiance of the morning mist / horizon

// optical depth from the flame out to radius r, and along any segment a -> b
float ltTauR(float r) { return uLightMist * (LT_SIG * min(r, LT_R_NEAR) + LT_SIG_FAR * max(r - LT_R_NEAR, 0.0)); }
float ltTau(vec3 a, vec3 b) {
  vec3 d = b - a; float L = length(d); if (L < 1e-4) return 0.0; d /= L;
  float bb = dot(a, d), cc = dot(a, a) - LT_R_NEAR * LT_R_NEAR, h = bb * bb - cc, inside = 0.0;
  if (h > 0.0) { h = sqrt(h); inside = max(0.0, min(L, -bb + h) - max(0.0, -bb - h)); }
  return uLightMist * (LT_SIG_FAR * L + (LT_SIG - LT_SIG_FAR) * inside);
}
float beamAz(float t) { return uLightPhase + LT_TAU * t / LT_PERIOD; }
vec3 bearingDir(float az) { return vec3(sin(az), 0.0, -cos(az)); }
vec3 lampDir(vec3 p) { return p / max(length(p), 1e-4); }

// ---- the lamp's light, before the mist takes its share
// Beams: one Gaussian cone per face (core 96%, a wide faint wing 4% for an old cemented lens), flux conserved.
float ltBeamE(vec3 p, float t) {
  float sect = LT_TAU / LT_N, a0 = beamAz(t);
  float az = atan(p.x, -p.z);
  float k0 = floor((az - a0) / sect + 0.5);
  float E = 0.0;
  for (int j = -1; j <= 1; j++) {
    vec3 ax = bearingDir(a0 + (k0 + float(j)) * sect);
    float s = dot(p, ax);
    if (s <= 0.0) continue;
    vec3 q = p - s * ax;
    float w = LT_W0 + LT_BETA * s, x2 = dot(q, q) / (w * w);
    E += LT_PHI / (PI * w * w) * (0.96 * exp(-x2) + 0.0025 * exp(-x2 * 0.0625));
  }
  return E;
}
// Light that misses the band (no prisms above or below it) and leaves through the upper glazing, 26 to 45 deg up.
// Half the flame's horizontal intensity: a cylindrical flame seen from 35 deg up, and the burner's shadow (chosen).
float ltEscE(vec3 p) {
  float r2 = max(dot(p, p), 1.0), se = p.y * inversesqrt(r2);
  return LT_IF * 0.5 / r2 * smoothstep(0.42, 0.46, se) * (1.0 - smoothstep(0.69, 0.72, se));
}
// Light scattered by the lens's many cemented joints and the glass: faint, all round; the lantern floor cuts it below,
// the roof above.
float ltGlowE(vec3 p) {
  float r2 = max(dot(p, p), 1.0), se = p.y * inversesqrt(r2);
  return LT_IF * 0.02 / r2 * smoothstep(-0.43, -0.37, se) * (1.0 - smoothstep(0.69, 0.72, se));
}
// The lit mist lights everything near it a little: the flux scattered within ~100 m spread over a sphere of ~50 m,
// doubled for light scattered more than once (rough).
float ltAmbE(float r) { return 4.6e3 / (4.0 * PI * (r * r + 2500.0)); }

float ltLampE(vec3 p, float t) {
  float r = length(p);
  return (ltBeamE(p, t) + ltEscE(p) + ltGlowE(p)) * exp(-ltTauR(r));
}
float illum(vec3 p, float t) {
  return uLightLamp * (ltLampE(p, t) + ltAmbE(length(p))) + uLightDawn * LT_DAWN_E * 0.6;
}

// ---- the mist
float mistDensity(vec3 p, float t) {
  vec3 q = p - LT_WIND * t;
  float n = 0.62 * texture(uLightNoise, q * (1.0 / 520.0)).r
          + 0.34 * texture(uLightNoise, q * (1.0 / 170.0) + vec3(0.37, 0.0021 * t, 0.71)).r
          + 0.18 * texture(uLightNoise, q * (1.0 / 55.0) + vec3(0.13, 0.53, 0.0043 * t)).r;
  float h = exp(-(p.y - LT_SEA) * (1.0 / 30.0));                     // thicker over the water
  float inLantern = (dot(p.xz, p.xz) < 4.75 && p.y > -1.0 && p.y < 3.3) ? 0.0 : 1.0;
  float far = mix(1.0, LT_SIG_FAR / LT_SIG, smoothstep(LT_R_NEAR - 150.0, LT_R_NEAR + 150.0, length(p)));
  return inLantern * uLightMist * LT_SIG * far * exp(1.15 * n - 0.55) * (0.75 + h);
}
float ltHG(float c, float g) { float g2 = g * g; return (1.0 - g2) / (4.0 * PI * pow(max(1.0 + g2 - 2.0 * g * c, 1e-5), 1.5)); }
float mistPhase(float c) { return 0.7 * ltHG(c, 0.85) + 0.3 * ltHG(c, 0.3); }

// In-scattered radiance along ro + rd * [0, b], and the transmittance over it. N samples placed equiangularly about
// the flame (they gather where the light is strong), jittered by j in [0,1). Camera-side extinction is the mean one.
vec4 ltMarch(vec3 ro, vec3 rd, float b, float t, int N, float j) {
  float sig0 = LT_SIG * uLightMist;
  float t0 = -dot(ro, rd);
  float D = max(length(ro + rd * t0), 0.03);
  float th0 = atan((0.0 - t0) / D), th1 = atan((b - t0) / D);
  float sum = 0.0;
  if (uLightLamp > 0.0) {
    for (int i = 0; i < 64; i++) {
      if (i >= N) break;
      float th = mix(th0, th1, (float(i) + j) / float(N));
      float s = t0 + D * tan(th);
      vec3 p = ro + rd * s;
      float w = (th1 - th0) * (D * D + (s - t0) * (s - t0)) / D;   // 1 / pdf
      float sig = mistDensity(p, t);
      if (sig <= 0.0) continue;
      float r = length(p);
      float Ein = (ltBeamE(p, t) + ltEscE(p) + ltGlowE(p)) * exp(-ltTauR(r));
      float c = dot(p / max(r, 1e-3), -rd);
      sum += sig * exp(-ltTau(ro, p)) * (Ein * mistPhase(c) + ltAmbE(r) * (1.0 / (4.0 * PI))) * w;
    }
    sum *= uLightLamp / float(N);
  }
  float T = exp(-ltTau(ro, ro + rd * b));
  sum += uLightDawn * LT_DAWN_L * (1.0 - exp(-sig0 * 1.6 * b));   // the grey morning mist (denser to the eye by day)
  return vec4(vec3(sum), T * mix(1.0, exp(-sig0 * 0.6 * b), uLightDawn));
}
vec4 mistTo(vec3 p, float t) {     // usable in vertex or fragment shaders
  vec3 d = p - uCamPos; float b = max(length(d), 1e-3);
  float j = fract(sin(dot(p, vec3(12.9898, 78.233, 37.719))) * 43758.5453);
  return ltMarch(uCamPos, d / b, b, t, 12, j);
}

// ---- the thin things: the gallery railing and the glazing's bars (and glass), as coverage filtered by the pixel's
// footprint fw (m). thinTransmit(c, p): the fraction of the light from p that reaches a camera at c past them; a kit
// drawing something behind the railing or the glazing multiplies its coverage by it (birds.glsl does).
const float LT_R_RAIL = 3.33;
float ltBarCov(float x, float halfw, float fw) { return clamp((halfw - abs(x)) / max(fw, 1e-5) + 0.5, 0.0, 1.0); }
float ltRailCov(vec3 p, float fw) {     // posts every 0.21 m, bellied at mid height (Hague), a top rail and one between
  if (p.y < LT_Y_GALLERY || p.y > -1.22) return 0.0;
  float a = atan(p.z, p.x) * 3.40, sp = 0.21;
  float post = ltBarCov(mod(a, sp) - 0.5 * sp, 0.018, fw);
  post = max(post, ltBarCov(mod(a, sp) - 0.5 * sp, 0.018 + 0.010 * sin(3.14159 * (p.y - LT_Y_GALLERY) / 1.08), fw) * 0.7);
  float top = ltBarCov(p.y + 1.25, 0.03, fw), mid = ltBarCov(p.y + 1.78, 0.016, fw);
  return max(post, max(top, mid));
}
float ltGlazeCov(vec3 p, float fw) {   // 24 vertical astragals, four rows of panes
  float a = atan(p.z, p.x) * LT_R_GLAZE, sp = LT_TAU * LT_R_GLAZE / 24.0;
  float ast = ltBarCov(mod(a, sp) - 0.5 * sp, 0.028, fw);
  float y = p.y - LT_Y_GLAZE0, rp = (LT_Y_GLAZE1 - LT_Y_GLAZE0) / 4.0;
  float hb = ltBarCov(mod(y + 0.5 * rp, rp) - 0.5 * rp, 0.022, fw);
  hb = max(hb, ltBarCov(y, 0.05, fw)); hb = max(hb, ltBarCov(y - (LT_Y_GLAZE1 - LT_Y_GLAZE0), 0.05, fw));
  return max(ast, hb);
}
vec2 ltCyl(vec3 ro, vec3 rd, float R) {
  float a = dot(rd.xz, rd.xz), b = dot(ro.xz, rd.xz), c = dot(ro.xz, ro.xz) - R * R;
  float h = b * b - a * c; if (h < 0.0 || a < 1e-9) return vec2(-1.0);
  h = sqrt(h); return vec2((-b - h) / a, (-b + h) / a);
}
float thinTransmit(vec3 c, vec3 p) {
  vec3 d = p - c; float L = length(d); if (L < 1e-3) return 1.0; d /= L;
  float pa = 2.0 * uTanHalfFov / uRes.y, T = 1.0;
  vec2 r = ltCyl(c, d, LT_R_RAIL);
  for (int i = 0; i < 2; i++) { float t = i == 0 ? r.x : r.y;
    if (t > 1e-3 && t < L - 0.02) T *= 1.0 - ltRailCov(c + d * t, pa * t); }
  vec2 g = ltCyl(c, d, LT_R_GLAZE);
  for (int i = 0; i < 2; i++) { float t = i == 0 ? g.x : g.y;
    if (t > 1e-3 && t < L - 0.02) { vec3 q = c + d * t;
      if (q.y > LT_Y_GLAZE0 && q.y < LT_Y_GLAZE1) T *= 0.9 * (1.0 - ltGlazeCov(q, pa * t)); } }
  return T;
}
