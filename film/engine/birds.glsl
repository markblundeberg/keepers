// birds.glsl: drawing the birds (owner C). Included after the film's light chunk, which must
// define  float illum(vec3 p, float t)  (B's light.glsl). Instanced quads, one per bird; the
// silhouette is a 2D distance field of the bird's projected 3D skeleton (body, head, tail and
// two-segment wings), evaluated at several instants across the shutter for motion blur, with
// the wingbeat advancing between instants. Output is premultiplied linear radiance.
//
// Lighting: the bird's radiance is illum(p, t) x albedo x a facing factor. A bird between the
// camera and the lamp shows its unlit side (dark against the lit glazing); a bird with the lamp
// behind the camera shows its lit side (pale in the beam). Nothing else lights the birds.

// From the engine's COMMON: uViewProj, uCamPos, uRes (target size, px), uTl (shot-local time, passed to illum).
uniform float uShutter;   // seconds the shutter is open (1/48 at 180 degrees, 24 fps)
uniform float uDawn;      // 0 night .. 1 grey daylight (selects the sky-facing shading)
uniform vec4 uSpecies[4];   // len, span, chord, tail fraction
uniform vec4 uSpecies2[4];  // tail spread, wingtip roundness, belly albedo, back albedo

//#vertex
in vec4 a0;   // pos.xyz, species
in vec4 a1;   // vel.xyz, wing phase
in vec4 a2;   // wing freq, fold, pose, seed
in vec4 a3;   // roll, yaw, wingOut, albedo scale
in vec4 a4;   // flutter, lie, tumble, fade

out vec2 vPx;
flat out vec4 vBody;    // nose.xy, tailRoot.xy
flat out vec4 vTail;    // tailEnd.xy, body radius, tail half-width
flat out vec4 vWD0, vWD1, vWM0, vWM1, vWU0, vWU1;   // wing points (L wrist, L tip | R wrist, R tip) per pose
flat out vec4 vChDM;    // chord half-widths: D_L, D_R, M_L, M_R
flat out vec4 vChU;     // U_L, U_R, blur.xy
flat out vec4 vAnim;    // phase, freq*shutter, taps, fade
flat out vec4 vShade;   // body radiance, ground (0/1) + 2 x species, pattern seed, mist in-scatter in front
flat out vec4 vLit;     // up.L, right.L, up.C, right.C  (L: toward the light, C: toward the camera)
flat out vec4 vWing;    // E/pi x upper-wing albedo, E/pi x under-wing albedo, fold, mist transmittance in front

vec4 clipOf(vec3 w) { return uViewProj * vec4(w, 1.0); }
vec2 pxOf(vec4 c) { return (c.xy / c.w * 0.5 + 0.5) * uRes; }

// one wing: shoulder -> wrist -> tip in bird-local coordinates (x right, y up, z forward)
struct Wing { vec3 w; vec3 t; };
Wing wingPose(float ea, float eh, float sa, float sh, float frac, float arm, float hand) {
  vec3 da = vec3(cos(ea) * cos(sa), sin(ea), -cos(ea) * sin(sa));
  vec3 dh = vec3(cos(eh) * cos(sh), sin(eh), -cos(eh) * sin(sh));
  Wing W; W.w = da * arm * frac; W.t = W.w + dh * hand * frac; return W;
}
Wing mixW(Wing a, Wing b, float u) { Wing W; W.w = mix(a.w, b.w, u); W.t = mix(a.t, b.t, u); return W; }

void main() {
  int si = int(a0.w + 0.5);
  vec4 S1 = uSpecies[si], S2 = uSpecies2[si];
  float L = S1.x, span = S1.y, chord = S1.z, tailF = S1.w;
  vec3 P = a0.xyz;
  vec3 vel = a1.xyz;
  float pose = a2.z, fold = a2.y, roll = a3.x, yaw = a3.y, wingOut = a3.z;
  float tumble = a4.z, lie = a4.y;

  // the bird's frame
  vec3 Y = vec3(0.0, 1.0, 0.0);
  vec3 hyaw = vec3(sin(yaw), 0.0, -cos(yaw));
  vec3 fwd, up, right;
  if (pose < 0.5 || (pose > 2.5)) {
    float sp = length(vel);
    fwd = sp > 0.3 ? vel / sp : hyaw;
    fwd.y = clamp(fwd.y, -0.45, 0.45);           // bodies stay near level; climbs are shallow pitch
    if (pose > 2.5) fwd = normalize(hyaw + vec3(0.0, 1.1, 0.0));  // at the glass: body steep, facing the light
    fwd = normalize(fwd);
    vec3 up0 = normalize(Y - fwd * dot(Y, fwd));
    vec3 r0 = normalize(cross(fwd, up0));
    float rl = roll;
    if (tumble >= 0.0) { rl = tumble * 9.0 + a2.w * 6.28; fwd = normalize(mix(fwd, -Y, clamp(tumble * 2.0, 0.0, 0.7))); up0 = normalize(Y - fwd * dot(Y, fwd) + vec3(1e-3)); r0 = normalize(cross(fwd, up0)); }
    up = up0 * cos(rl) + r0 * sin(rl);
    right = r0 * cos(rl) - up0 * sin(rl);
  } else if (pose < 1.5) {
    // lying: on the belly (0), on a side (1), on the back (2)
    fwd = hyaw;
    vec3 rh = normalize(cross(fwd, Y));
    if (lie < 0.5) { up = Y; right = rh; }
    else if (lie < 1.5) { up = rh; right = -Y; }
    else { up = -Y; right = -rh; }
  } else {
    // sitting (perched or injured): body tilted up a little
    fwd = normalize(hyaw + vec3(0.0, 0.45, 0.0));
    up = normalize(Y - fwd * dot(Y, fwd));
    right = normalize(cross(fwd, up));
  }

  // skeleton (metres, bird-local)
  float tl = tailF * L, bl = L - tl;
  bool still = pose > 0.5 && pose < 2.5;
  float rb = (still ? 0.2 : 0.15) * L;    // lying or sitting, the plumage spreads
  vec3 nose = vec3(0.0, 0.0, bl * 0.55), troot = vec3(0.0, 0.0, -bl * 0.45), tend = troot - vec3(0.0, 0.0, tl);
  float semi = span * 0.5 - rb * 0.5, arm = 0.42 * semi, hand = 0.58 * semi;
  if (pose > 0.5 && pose < 2.5) { nose.y += 0.0; tend.y += (pose > 1.5 ? -0.25 : 0.0) * tl; }
  vec3 sh = vec3(0.0, rb * 0.35, bl * 0.12);

  Wing D = wingPose(-0.45, -0.70, 0.10, 0.22, 1.0, arm, hand);
  Wing M = wingPose(0.05, 0.00, 0.16, 0.32, 1.0, arm, hand);
  Wing U = wingPose(0.95, 1.20, 0.45, 1.05, 0.80, arm, hand);
  Wing F = wingPose(0.12, 0.05, 1.42, 1.56, 0.80, arm, hand);   // folded along the back
  float fl = a4.x > 0.5 ? 0.0 : fold;
  D = mixW(D, F, fl); M = mixW(M, F, fl); U = mixW(U, F, fl);
  // the right wing out of place (dead with a wing out, or injured with a drooped wing)
  Wing Rd = D, Rm = M, Ru = U;
  if (wingOut > 0.0) {
    Wing O = wingPose(-0.15, -0.10, 0.35, 0.60, 0.95, arm, hand);               // lying: half spread
    if (pose > 1.5) O = wingPose(-1.05, -1.25, 0.55, 0.75, 0.9, arm, hand);    // sitting: drooping, trailing
    Rd = mixW(D, O, wingOut); Rm = mixW(M, O, wingOut); Ru = mixW(U, O, wingOut);
  }

  vec4 cC = clipOf(P);
  if (cC.w < 0.2) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
  vec2 c = pxOf(cC);
  #define W2(v) (pxOf(clipOf(P + right * (v).x + up * (v).y + fwd * (v).z)) - c)
  #define WL(v) W2(vec3(-(v).x, (v).y, (v).z))
  vec2 pN = W2(nose), pR = W2(troot), pE = W2(tend), pS = W2(sh);
  vec2 dLw = WL(sh + D.w), dLt = WL(sh + D.t), dRw = W2(sh + Rd.w), dRt = W2(sh + Rd.t);
  vec2 mLw = WL(sh + M.w), mLt = WL(sh + M.t), mRw = W2(sh + Rm.w), mRt = W2(sh + Rm.t);
  vec2 uLw = WL(sh + U.w), uLt = WL(sh + U.t), uRw = W2(sh + Ru.w), uRt = W2(sh + Ru.t);
  // projected scales
  vec2 chV = W2(sh + vec3(0.0, 0.0, chord)) - pS;          // chord along the body
  vec2 rbV = W2(vec3(rb, 0.0, 0.0)), rbU = W2(vec3(0.0, rb, 0.0));
  float rbPx = max(0.45, 0.5 * (length(rbV) + length(rbU)) * 0.9);
  vec2 tailAcross = W2(troot + vec3(S2.x * tl * 0.5, 0.0, 0.0)) - pR;
  vec2 tdir = normalize(pE - pR + 1e-5);
  float tailHW = max(0.3, abs(tailAcross.x * tdir.y - tailAcross.y * tdir.x));
  #define CH(a, b) max(0.35, 0.5 * abs(chV.x * normalize((b) - (a) + 1e-5).y - chV.y * normalize((b) - (a) + 1e-5).x))
  float cDL = CH(pS, dLt), cDR = CH(pS, dRt), cML = CH(pS, mLt), cMR = CH(pS, mRt), cUL = CH(pS, uLt), cUR = CH(pS, uRt);
  // a folded wing lies along the flank: as wide as about three quarters of the body, whatever the chord's projection
  float fw = rbPx * 0.75 * fl;
  float fwR = rbPx * 0.75 * fl * (1.0 - wingOut);
  cDL = max(cDL, fw); cML = max(cML, fw); cUL = max(cUL, fw); cDR = max(cDR, fwR); cMR = max(cMR, fwR); cUR = max(cUR, fwR);

  // motion blur over the open shutter
  vec2 blur = pose < 0.5 || pose > 2.5 ? pxOf(clipOf(P + vel * uShutter)) - c : vec2(0.0);
  float fs = a2.x * uShutter;
  // enough instants that neither the body's travel nor the wingtip's sweep leaves gaps
  float sweep = max(length(uLt - dLt), length(uRt - dRt)) * min(1.0, fs * 2.0);
  float taps = clamp(ceil(max(length(blur), sweep) / 1.2) + 1.0, 1.0, 24.0);

  // bounding quad
  vec2 lo = min(min(min(pN, pE), min(pR, pS)), min(min(dLt, dRt), min(mLt, mRt)));
  lo = min(lo, min(min(uLt, uRt), min(min(dLw, dRw), min(uLw, uRw))));
  vec2 hi = max(max(max(pN, pE), max(pR, pS)), max(max(dLt, dRt), max(mLt, mRt)));
  hi = max(hi, max(max(uLt, uRt), max(max(dLw, dRw), max(uLw, uRw))));
  float pad = max(max(rbPx, tailHW), max(max(cDL, cDR), max(max(cML, cMR), max(cUL, cUR)))) + 1.5;
  bool ground = pose > 0.5 && pose < 2.5;
  if (ground) pad += rbPx * 1.5 + 2.0;   // room for the contact shadow
  lo -= pad + abs(blur) * 0.5; hi += pad + abs(blur) * 0.5;
  vec2 corner = vec2(float(gl_VertexID & 1), float((gl_VertexID >> 1) & 1));
  vec2 q = mix(lo, hi, corner);
  vPx = q;
  vec2 ndc = (c + q) / uRes * 2.0 - 1.0;
  // depth: a bird lying on a surface is pulled toward the camera (so the floor round it doesn't cut it) only when
  // the camera is above that surface; seen from below, it is pushed back so the floor hides it
  vec3 tc = normalize(uCamPos - P);
  float bias = ground ? (tc.y > 0.05 ? min(0.15, 0.5 * length(uCamPos - P)) : -0.08) : 0.0;
  vec4 cz = clipOf(P + tc * bias);
  gl_Position = vec4(ndc * cC.w, cz.z / cz.w * cC.w, cC.w);

  vBody = vec4(pN, pR); vTail = vec4(pE, rbPx, tailHW);
  vWD0 = vec4(dLw, dLt); vWD1 = vec4(dRw, dRt); vWM0 = vec4(mLw, mLt); vWM1 = vec4(mRw, mRt); vWU0 = vec4(uLw, uLt); vWU1 = vec4(uRw, uRt);
  vChDM = vec4(cDL, cDR, cML, cMR); vChU = vec4(cUL, cUR, blur);
  vAnim = vec4(a1.w, fs, taps, a4.w);

  // shading: lit only by illum()
  float E = illum(P, uTl);
  vec3 toCam = normalize(uCamPos - P), toLamp = normalize(-P + vec3(0.0, 1e-4, 0.0));
  // Matte plumage: radiance = albedo x irradiance / pi (as B's surfaces). The light comes from the lamp by night,
  // from the overcast sky (above) by day. The body is shaded as a rounded form (lit side vs dark side as seen
  // from the camera); each wing as a flat plate at its stroke angle (in the fragment shader), lit only when the
  // light and the camera are on the same side of it: so birds glint as their wings catch the beam and go dark
  // edge-on, which is what Clarke saw ("glittering objects", "mere apparitions" between).
  vec3 Ld = normalize(mix(toLamp, Y, uDawn));
  float Epi = E / PI;
  float under = dot(toCam, up) < 0.0 ? 1.0 : 0.0;
  float alb = mix(S2.w, S2.z, under * (ground ? 0.0 : 1.0)) * a3.w;
  if (ground && lie > 1.5) alb = S2.z * a3.w;                   // on its back: the belly up
  float bodyShade = ground ? 0.25 + 0.75 * max(0.0, dot(dot(toCam, up) >= 0.0 ? up : -up, Ld))
                           : mix(0.05, 1.0, pow(0.5 + 0.5 * dot(toCam, Ld), 1.5));
  // the mist between the camera and the bird (B's mistTo: in-scatter rgb, transmittance a; exact compositing)
  vec4 mist = mistTo(P, uTl);
  vShade = vec4(Epi * alb * bodyShade, (ground ? 1.0 : 0.0) + 2.0 * a0.w, a2.w, mist.r);
  vLit = vec4(dot(up, Ld), dot(right, Ld), dot(up, toCam), dot(right, toCam));
  vWing = vec4(Epi * S2.w * a3.w, Epi * mix(S2.z, S2.w, 0.3) * a3.w, (ground || a4.x > 0.5) ? (ground ? 1.0 : 0.0) : fold, mist.a);

  if (pose > 0.5 && pose < 1.5) {
    // A bird lying still is drawn, not built: a plain drawing of a small bird laid on the stone (decal() in the
    // fragment shader). The quad covers its rectangle on the ground; the flight skeleton's slots carry its record.
    // The drawing lies on the stone when seen from above; as the view lowers toward grazing it is tilted up toward
    // the camera (to ~50 deg), as a lying bird's own thickness would show it, so it never thins to a sliver.
    vec3 tcH = normalize(vec3(uCamPos.x - P.x, 0.0, uCamPos.z - P.z) + vec3(1e-4, 0.0, 0.0));
    float elev = asin(clamp(normalize(uCamPos - P).y, -1.0, 1.0));
    float tilt = 0.8 * clamp(1.0 - elev / 0.9, 0.0, 1.0);
    vec3 nrm = normalize(Y * cos(tilt) + tcH * sin(tilt));
    vec3 Fh = normalize(hyaw - nrm * dot(hyaw, nrm));
    vec3 Sh0 = vec3(cos(yaw), 0.0, sin(yaw));
    vec3 Sh = normalize(Sh0 - nrm * dot(Sh0, nrm) - Fh * dot(Sh0, Fh));
    float ext = L * (0.34 + 0.75 * wingOut);
    vec2 l2 = vec2(1e9), h2 = vec2(-1e9);
    for (int k = 0; k < 4; k++) {
      vec3 w = P + Fh * L * (k < 2 ? 0.62 : -0.62) + Sh * ext * ((k & 1) == 0 ? 1.0 : -1.0);
      vec2 s2 = pxOf(clipOf(w)) - c; l2 = min(l2, s2); h2 = max(h2, s2);
    }
    l2 -= 4.0; h2 += 4.0;
    vec2 q2 = mix(l2, h2, corner);
    vPx = q2;
    gl_Position = vec4(((c + q2) / uRes * 2.0 - 1.0) * cC.w, cz.z / cz.w * cC.w, cC.w);
    float sideSign = fract(a2.w * 7.31) < 0.5 ? -1.0 : 1.0;
    // light on the upper surface: the grey sky from above by day; the lantern's glow from above by night
    vWD0 = vec4(P, yaw); vWD1 = vec4(lie, wingOut, a0.w, L); vWM0 = vec4(Epi * 0.9, a3.w, a2.w, sideSign);
    vWM1 = vec4(nrm, 0.0); vWU0 = vec4(Fh, 0.0); vWU1 = vec4(Sh, 0.0);
    vChU.x = -1.0;
  }
}

//#fragment
in vec2 vPx;
flat in vec4 vBody, vTail, vWD0, vWD1, vWM0, vWM1, vWU0, vWU1, vChDM, vChU, vAnim, vShade, vLit, vWing;
out vec4 frag;

float cap(vec2 p, vec2 a, vec2 b, float ra, float rb) {
  vec2 pa = p - a, ba = b - a;
  float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-6), 0.0, 1.0);
  return length(pa - ba * h) - mix(ra, rb, h);
}
vec2 bez(vec2 d, vec2 m, vec2 u, float s) {     // through D (s=-1), M (s=0), U (s=1)
  float x = s * 0.5 + 0.5;
  vec2 cc = 2.0 * m - 0.5 * (d + u);
  return (1.0 - x) * (1.0 - x) * d + 2.0 * x * (1.0 - x) * cc + x * x * u;
}
float h21(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float sdEll(vec2 p, vec2 r) { return (length(p / r) - 1.0) * min(r.x, r.y); }
float smin(float a, float b, float k) { float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0); return mix(b, a, h) - k * h * (1.0 - h); }
// a half-spread wing in the drawing's units: from shoulder s0 along dir, a broad blade narrowing, and three
// primaries splayed at its tip
float spreadWing(vec2 p, vec2 s0, vec2 dir, float len) {   // one blade, broad at the arm, rounded at the tip
  vec2 wr = s0 + dir * len * 0.55;
  return smin(cap(p, s0, wr, 0.085, 0.075), cap(p, wr, s0 + dir * len, 0.075, 0.04), 0.04);
}

// ---- a dead bird, drawn in the plain manner of a naturalist's figure, laid flat on the stone. Units: body
// lengths, the bill's tip at x = +0.5, the tail's end at -0.5. On its side: the profile; on its belly: from above;
// on its back: from below, the feet curled. Species by their marks: the Skylark's streaked back, the Starling's
// pale spangles, the Blackbird's plain dark plumage and pale (yellow) bill, the Song Thrush's spotted breast.
// Nothing broken is drawn beyond "a wing out of place" where the ledger says so.
vec4 decal() {
  vec3 P = vWD0.xyz; float yaw = vWD0.w;
  float lie = vWD1.x, wo = vWD1.y, L = vWD1.w; int si = int(vWD1.z + 0.5);
  vec3 rd = cameraRay(gl_FragCoord.xy);
  vec3 nrm = vWM1.xyz, Fh = vWU0.xyz, Sh = vWU1.xyz;               // the drawing's plane (see the vertex shader)
  float dn = dot(rd, nrm);
  float tt = dot(P - uCamPos, nrm) / (abs(dn) > 1e-4 ? dn : -1e-4);
  vec3 w = uCamPos + rd * tt;
  vec2 q = vec2(dot(w - P, Fh), dot(w - P, Sh)) / L;
  vec4 S1 = uSpecies[si], S2 = uSpecies2[si];
  float tr = -0.5 + S1.w;                                    // tail root
  float bl = si == 1 ? 0.12 : (si == 0 ? 0.06 : 0.09);       // bill length
  float hx = 0.5 - bl - 0.07;                                // head centre
  float bc = 0.5 * (tr + hx) - 0.02, bhl = 0.5 * (hx - tr) + 0.02;
  bool side = lie > 0.5 && lie < 1.5, back = lie > 1.5;
  vec2 p = side ? vec2(q.x, q.y * vWM0.w) : vec2(q.x, q.y);
  float d, dW, dLeg = 1e9, dEye = 1e9, dBill;
  float bellyZone = 0.0;
  if (side) {
    float body = sdEll(p - vec2(bc, -0.005), vec2(bhl, 0.12));
    float head = length(p - vec2(hx, 0.045)) - 0.083;
    d = smin(body, head, 0.05);
    dBill = cap(p, vec2(hx + 0.06, 0.036), vec2(hx + 0.07 + bl, 0.028), 0.026, 0.005);
    float tail = cap(p, vec2(tr + 0.05, 0.012), vec2(-0.5, 0.0), 0.038, 0.046);
    d = min(min(d, dBill), tail);
    dW = min(sdEll(p - vec2(bc - 0.02, 0.035), vec2(bhl * 0.8, 0.068)), cap(p, vec2(bc - 0.08, 0.03), vec2(tr - 0.07, 0.016), 0.04, 0.012));
    if (wo > 0.01) {      // the upper wing out of place: half spread, lying back over the stone
      dW = spreadWing(p, vec2(bc + 0.06, 0.06), normalize(vec2(-0.8, 0.35 + 0.35 * wo)), 0.45 + 0.2 * wo);
    }
    d = min(d, dW);
    dLeg = min(cap(p, vec2(bc + 0.03, -0.1), vec2(bc + 0.01, -0.165), 0.008, 0.006), cap(p, vec2(bc + 0.08, -0.1), vec2(bc + 0.075, -0.16), 0.008, 0.006));
    dLeg = min(dLeg, min(cap(p, vec2(bc + 0.01, -0.165), vec2(bc + 0.045, -0.175), 0.006, 0.004), cap(p, vec2(bc + 0.075, -0.16), vec2(bc + 0.105, -0.168), 0.006, 0.004)));
    d = min(d, dLeg);
    dEye = length(vec2((p.x - hx - 0.025) * 0.6, p.y - 0.062)) - 0.006;
    bellyZone = smoothstep(0.01, -0.04, p.y) * step(-0.12, p.x - tr);
  } else {
    float body = sdEll(p - vec2(bc, 0.0), vec2(bhl, 0.13));
    float head = length(p - vec2(hx, 0.0)) - 0.078;
    d = smin(body, head, 0.05);
    dBill = cap(p, vec2(hx + 0.06, 0.0), vec2(hx + 0.07 + bl, 0.0), 0.024, 0.005);
    float tail = cap(p, vec2(tr + 0.05, 0.0), vec2(-0.47, 0.0), 0.04, 0.075);     // a wedge, widening to its end
    d = min(min(d, dBill), tail);
    vec2 pm = vec2(p.x, abs(p.y));
    dW = min(sdEll(pm - vec2(bc - 0.02, 0.075), vec2(bhl * 0.8, 0.064)), cap(pm, vec2(bc - 0.06, 0.068), vec2(tr - 0.09, 0.03), 0.042, 0.016));
    if (wo > 0.01) dW = min(dW, spreadWing(p, vec2(bc + 0.06, 0.1), normalize(vec2(-0.8, 0.35 + 0.35 * wo)), 0.45 + 0.2 * wo));
    d = min(d, dW);
    if (back) {          // on its back: the feet, small and curled
      dLeg = min(cap(pm, vec2(bc + 0.02, 0.035), vec2(bc + 0.07, 0.05), 0.008, 0.006), cap(pm, vec2(bc + 0.07, 0.05), vec2(bc + 0.085, 0.035), 0.006, 0.004));
      d = min(d, dLeg);
      bellyZone = 1.0;
    }
  }
  float fw = max(fwidth(d), 1e-5);
  float cov = clamp(0.5 - d / fw, 0.0, 1.0);
  // tone: albedo by zone, x irradiance/pi (vWM0.x), with the species' marks
  float back_ = S2.w * vWM0.y, belly = S2.z * vWM0.y;
  float alb = mix(back_, belly, bellyZone);
  if (dW < 0.0 && !back) alb = back_ * 1.12;                               // the folded wing, a shade paler
  if (dW < 0.0 && back) alb = mix(belly, back_, 0.5);                      // the underwing
  if (wo > 0.01 && dW < 0.0) alb *= 1.0 - 0.18 * step(0.75, fract(dot(p, vec2(0.6, 0.8)) * 34.0));   // its feathers, engraved
  vec2 cell;
  if (si == 0 && dW >= 0.0 && bellyZone < 0.5) {                           // Skylark: streaked back
    float n = h21(floor(vec2(p.x * 26.0, p.y * 70.0)) + vWM0.z * 13.0); alb *= 1.0 - 0.32 * step(0.55, n);
  }
  if (si == 0 && bellyZone > 0.5 && p.x > bc) {                            // and a finely streaked breast
    float n = h21(floor(vec2(p.x * 40.0, p.y * 60.0)) + vWM0.z * 7.0); alb *= 1.0 - 0.25 * step(0.7, n);
  }
  if (si == 1) {                                                           // Starling: pale spangles
    cell = p * 30.0; vec2 f = fract(cell) - 0.5; float n = h21(floor(cell) + vWM0.z * 5.0);
    if (n > 0.45 && length(f) < 0.22) alb = mix(alb, 0.42, 0.7);
  }
  if (si == 3 && bellyZone > 0.5 && p.x > bc - 0.05) {                    // Song Thrush: spotted breast
    cell = p * 32.0; vec2 f = fract(cell) - 0.5; float n = h21(floor(cell) + vWM0.z * 3.0);
    if (n > 0.35 && length(f) < 0.24) alb *= 0.35;
  }
  if (dBill < 0.0) alb = si == 2 ? (vWM0.y > 1.5 ? 0.18 : 0.5) : 0.1;     // the cock Blackbird's bill is yellow: pale here
  if (dLeg < 0.0) alb = 0.12;
  if (dEye < 0.0) alb = 0.04;
  float rad = vWM0.x * alb;
  rad *= 0.76 + 0.32 * smoothstep(0.0, 0.06, -d);                          // a little roundness
  rad *= 1.0 - 0.4 * (1.0 - smoothstep(0.0, 1.5 * fw, abs(dW))) * step(d, 0.0);   // engraved line: the wing's edge
  // the figure's outline, engraved just inside its edge (about a pixel and a half wide at any distance)
  rad *= 1.0 - 0.7 * (1.0 - smoothstep(0.8 * fw, 2.2 * fw, -d)) * step(d, 0.0);
  // overcast light: a soft darkening of the stone all round the body
  float sa = 0.4 * (1.0 - smoothstep(0.0, 0.1, d)) * step(0.0, d);
  float a = cov + (1.0 - cov) * sa * vWing.w;
  // what stands between the camera and the figure (the railing, the glazing: B's thinTransmit), tested at the
  // figure's footprint on the floor, so the tilt toward the camera can never lift it through the rail's plane
  vec3 F0 = vec3(sin(yaw), 0.0, -cos(yaw)), S0 = vec3(cos(yaw), 0.0, sin(yaw));
  float T = thinTransmit(uCamPos, P + (F0 * q.x + S0 * q.y) * L);
  return vec4(vec3(vShade.w + vWing.w * rad) * cov, a) * T;
}

vec3 birdParts(vec2 p, float s) {     // distances to (body+tail, left wing, right wing)
  vec2 nose = vBody.xy, tr = vBody.zw, te = vTail.xy;
  float rb = vTail.z, thw = vTail.w;
  vec2 chest = mix(tr, nose, 0.55), sh = mix(tr, nose, 0.62);
  float d = min(cap(p, tr, chest, rb * 0.72, rb), cap(p, chest, mix(chest, nose, 0.5), rb, rb * 0.5));
  // the head (set off from the breast by the neck) and the bill
  vec2 hc = mix(chest, nose, 0.74);
  d = min(d, length(p - hc) - rb * 0.62);
  d = min(d, cap(p, hc, nose + (nose - hc) * 0.55, rb * 0.22, 0.25));
  d = min(d, cap(p, tr, te, rb * 0.42, thw));
  vec2 lw = bez(vWD0.xy, vWM0.xy, vWU0.xy, s), lt = bez(vWD0.zw, vWM0.zw, vWU0.zw, s);
  vec2 rw = bez(vWD1.xy, vWM1.xy, vWU1.xy, s), rt = bez(vWD1.zw, vWM1.zw, vWU1.zw, s);
  float x = s * 0.5 + 0.5;
  float cl = mix(mix(vChDM.x, vChDM.z, min(1.0, 2.0 * x)), vChU.x, max(0.0, 2.0 * x - 1.0));
  float cr = mix(mix(vChDM.y, vChDM.w, min(1.0, 2.0 * x)), vChU.y, max(0.0, 2.0 * x - 1.0));
  float tipR = uSpecies2[int(floor(vShade.y * 0.5) + 0.5)].y;
  float dl = min(cap(p, sh, lw, cl, cl * 0.95), cap(p, lw, lt, cl * 0.9, max(0.25, cl * tipR * 0.9)));
  float dr = min(cap(p, sh, rw, cr, cr * 0.95), cap(p, rw, rt, cr * 0.9, max(0.25, cr * tipR * 0.9)));
  return vec3(d, dl, dr);
}
// radiance of one wing at stroke angle e (normal = up cos e -+ right sin e)
float wingRad(float e, float side) {
  float ce = cos(e), se = sin(e) * side;
  float nL = vLit.x * ce - vLit.y * se, nC = vLit.z * ce - vLit.w * se;
  float lit = nL * nC > 0.0 ? abs(nL) : 0.08 * abs(nL);       // a little light through the feathers
  return (nC > 0.0 ? vWing.x : vWing.y) * lit;
}

void main() {
  if (vChU.x < -0.5) { frag = decal(); return; }
  float taps = vAnim.z;
  vec2 blur = vChU.zw;
  float cov = 0.0, rad = 0.0;
  float fold = vWing.z;
  float j0 = h21(gl_FragCoord.xy + vShade.z * 91.0);
  for (int k = 0; k < 24; k++) {
    if (float(k) >= taps) break;
    float tau = (float(k) + fract(j0 + float(k) * 0.618034)) / taps - 0.5;   // jittered per pixel
    float s = sin(6.2831853 * (vAnim.x + vAnim.y * tau));
    vec3 d = birdParts(vPx - blur * tau, s);
    float cb = clamp(0.5 - d.x, 0.0, 1.0), cl = clamp(0.5 - d.y, 0.0, 1.0), cr = clamp(0.5 - d.z, 0.0, 1.0);
    float c = max(cb, max(cl, cr));
    float x = s * 0.5 + 0.5;
    float e = mix((1.0 - x) * (1.0 - x) * -0.45 + 2.0 * x * (1.0 - x) * -0.15 + x * x * 0.95, 0.12, fold);
    float rw = cl >= cr ? wingRad(e, -1.0) : wingRad(e, 1.0);
    rw = mix(rw, vShade.x, fold);
    rad += cb * vShade.x + max(0.0, c - cb) * rw;
    cov += c;
  }
  cov /= taps; rad /= taps;
  rad /= max(cov, 1e-4);
  // the print can't hold a bird lit in a beam a few metres from the lens (radiance ~100s): roll it off toward paper
  // white, as B does for the lit lantern's surfaces, so it prints as a pale shape rather than a halo
  rad = rad * 6.0 / (6.0 + rad);
  // a little plumage pattern, only where a bird is large on screen (close-ups at dawn)
  float rb = vTail.z;
  if (mod(vShade.y, 2.0) > 0.5 && rb > 2.0) {   // a still bird seen close: a little roundness (edges darker than the middle)
    vec3 dp = birdParts(vPx, 0.0);
    rad *= 0.72 + 0.4 * clamp(-dp.x / (rb * 0.8), 0.0, 1.0);
    // the folded wing a shade paler than the body, with an engraved line where its edge lies on the body
    float dw = min(dp.y, dp.z);
    if (dw < 0.0) rad *= 1.15;
    rad *= 1.0 - 0.35 * (1.0 - smoothstep(0.0, 1.2, abs(dw))) * step(dp.x, 0.0);
  }
  if (rb > 3.0) {
    vec2 g = floor(vPx / max(1.2, rb * 0.32) + vShade.z * 17.0);
    float n = h21(g);
    float sp = floor(vShade.y * 0.5);
    float amp = sp < 0.5 ? 0.18 : sp < 1.5 ? 0.22 : sp < 2.5 ? 0.05 : 0.2;   // lark, starling, blackbird, thrush
    rad *= 1.0 + amp * (n - 0.5) * smoothstep(3.0, 6.0, rb);
  }
  // composite through the mist in front (B's recipe): seen = in-scatter + transmittance x the bird's own radiance
  cov *= vAnim.w;
  // B: the gallery railing and the glazing's bars in front of this fragment (its own ray, at the bird's depth)
  { vec3 rdF = cameraRay(gl_FragCoord.xy); cov *= thinTransmit(uCamPos, uCamPos + rdF * ((1.0 / gl_FragCoord.w) / dot(rdF, uCamFwd))); }
  float a = cov;
  vec3 col = vec3(vShade.w + vWing.w * rad) * cov;
  if (mod(vShade.y, 2.0) > 0.5) {
    // contact shadow under a bird on stone: darkens what's beneath, adds no light
    // overcast light: the shadow is a soft darkening all round the body, not cast to one side
    float ds = cap(vPx, vTail.xy, vBody.xy, rb * 1.1, rb * 0.9);
    float sa = 0.35 * vWing.w * clamp(0.5 - ds / (rb * 0.7 + 1.0), 0.0, 1.0);
    a = cov + (1.0 - cov) * sa;
  }
  frag = vec4(col, a);
}
