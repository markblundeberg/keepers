// print.glsl: the print pass. Radiance in; a mezzotint printed in warm ink on paper out. Owner: A.
// Order: lens (halation, vignette, soft corners) -> burnish level from radiance -> ink where the plate's pits
// survive the burnishing -> plate tone from the wipe -> ink on paper (Beer-Lambert, per channel) -> watercolour
// wash for the lamps' colour -> plate mark -> sRGB.
in vec2 vUv;
out vec4 outColor;
uniform sampler2D uHdr, uGlowNear, uGlowFar, uGround, uPaper, uType;
uniform vec2 uDrift;
uniform float p_exposure, p_halation, p_vignette, p_edgeSoft, p_gamma, p_toe;
uniform float p_grainSoft, p_grain, p_grainSym, p_paperTake, p_warmth, p_inkMax, p_plateTone, p_paperTex;
uniform float p_plateInset, p_plateMark, p_plateAspect, p_wash;

vec3 srgbToLinear(vec3 c) { return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(0.04045, c)); }
vec3 linearToSrgb(vec3 c) { c = max(c, 0.0); return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c)); }
float lum(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }

void main() {
  vec2 px = gl_FragCoord.xy;
  vec2 uv = vUv;
  vec2 cuv = uv * 2.0 - 1.0;
  float r2 = dot(cuv * vec2(1.0, 0.75), cuv * vec2(1.0, 0.75));

  // ---- lens: a period objective, soft toward the corners, with a glow round anything bright
  vec3 L = texture(uHdr, uv).rgb;
  vec3 near = texture(uGlowNear, uv).rgb, far = texture(uGlowFar, uv).rgb;
  L = mix(L, near, clamp(p_edgeSoft * r2 * r2 * 0.6, 0.0, 0.8));
  L += p_halation * (0.035 * near + 0.06 * far);
  L *= 1.0 - p_vignette * r2;
  L *= p_exposure;

  // ---- burnish level: how far the engraver polished the plate here (0 = rocked ground, 1 = polished)
  float Y = lum(L);
  float ell = 1.0 - exp(-2.5 * pow(max(Y, 0.0), p_gamma));
  ell = clamp((ell - p_toe) / (1.0 - p_toe), 0.0, 1.0);
  vec4 ty = texture(uType, vec2(uv.x, 1.0 - uv.y));
  ell = max(ell, ty.r);                                   // light lettering: scraped and burnished clean

  // ---- ink and paper (linear). A warm ink goes brown in the half-tones and near-black at full load.
  vec3 paperC = srgbToLinear(vec3(0.925, 0.886, 0.800));
  vec3 inkFull = srgbToLinear(mix(vec3(0.105, 0.100, 0.098), vec3(0.150, 0.098, 0.066), p_warmth));
  vec3 od = -log(inkFull / paperC);                       // optical density (natural log) at full load
  float rhoInk = lum(inkFull) / lum(paperC);              // darkest reflectance, relative to the paper

  // ---- the ground: pits deeper than the burnish level still hold ink. The tone is carried continuously (the
  // burr and the pits average out at viewing distance); the grain is the pits that survive, as a modulation of
  // the reflectance: dark specks in the lights, pale specks (pits polished through, paper hollows) in the darks.
  vec4 pa = texture(uPaper, px / vec2(textureSize(uPaper, 0)));
  float paperH = pa.r, wipe = pa.g;
  float pit = texture(uGround, (px + uDrift) / vec2(textureSize(uGround, 0))).r;
  pit += p_paperTake * (paperH - 0.5);                    // the paper's hollows don't reach the ink
  float cov = clamp((pit - ell) / max(p_grainSoft, 1e-3) + 0.5, 0.0, 1.0);
  float rho = mix(rhoInk, 1.0, ell);                      // the asked reflectance
  float D = log(rho) / log(rhoInk);                       // the ink load that gives it (0 = paper, 1 = full)
  // the grain, in density: part the pits that survive the burnisher (skewed: dark specks in the lights, pale in
  // the darks), part the ground's texture itself (symmetric, the velvet); fading where the plate is polished
  float n = mix((cov - (1.0 - ell)), (pit - 0.5) * 1.2, p_grainSym);
  D += p_grain * n * (1.0 - 0.8 * smoothstep(0.45, 0.95, ell));
  D = clamp(D, 0.0, 1.0);
  D = max(D * p_inkMax, ty.g);                            // dark lettering
  // plate tone: the wipe leaves a thin film everywhere, heavier in the darker passages
  D += p_plateTone * (0.35 + 0.65 * wipe) * (0.4 + 0.6 * (1.0 - ell));
  float shade = 1.0 + p_paperTex * 0.06 * (paperH - 0.5) * 2.0;   // paper relief catches light in the lights
  vec3 R = paperC * shade * exp(-od * D);

  // ---- colour: the lamps' red and green, laid on like a watercolour wash (transparent, over the ink)
  float m = max(max(L.r, L.g), L.b);
  if (m > 1e-5) {
    vec3 hue = L / m;
    float sat = 1.0 - min(min(hue.r, hue.g), hue.b);
    vec3 washC = mix(vec3(1.0), hue, clamp(sat * p_wash, 0.0, 1.0) * smoothstep(0.0, 0.25, ell));
    R *= washC;
  }

  // ---- the plate mark: outside the plate the paper is bare; the bevel is pressed into it
  if (p_plateInset > 0.0) {
    // the plate: a rectangle inset from the frame (or from a centred crop of aspect p_plateAspect, e.g. 0.8 for a
    // 4:5 cut), its corners rounded as a bevelled copper plate's are. dIn > 0 inside the plate, in px.
    vec2 res = vec2(textureSize(uHdr, 0));
    vec2 hs = 0.5 * res;
    if (p_plateAspect > 0.0) hs.x = min(hs.x, 0.5 * res.y * p_plateAspect);
    vec2 q = abs(px - 0.5 * res) - (hs - p_plateInset - 6.0);
    float dIn = -(length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - 6.0);
    float inside = smoothstep(-0.7, 0.7, dIn);
    vec3 bare = paperC * (1.0 + p_paperTex * 0.08 * (paperH - 0.5));
    // the bevel holds a little ink (a dark hairline); the damp paper is pressed into a step just outside it
    float bevel = exp(-pow(dIn / 1.1, 2.0));
    float emboss = exp(-pow((dIn + 3.0) / 2.5, 2.0));
    R = mix(bare, R, inside);
    R *= 1.0 - p_plateMark * (0.30 * bevel + 0.10 * emboss);
  }

  outColor = vec4(linearToSrgb(R), 1.0);
}
