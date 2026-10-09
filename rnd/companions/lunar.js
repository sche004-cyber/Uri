// Lunar Intelligence - three directions plus the Lunar x Sakura hybrid.
//
// Uniform reading for this family:
//   uEnergy   cloud speed and overall luminance
//   uTurb     cloud turbulence
//   uFlare    moonlight shaft / halo strength
//   uEmber    mist and star density
//   uFocus    how clear the moon is (high: clouds part; low: obscured)
//
// Compositing order is the same in all four: stars, sky, moon disc, halo, then
// cloud layers alpha-composited far to near. Clouds are drawn over the moon
// rather than added to it, which is what lets them actually conceal it.
//
// Iteration 2. In the first pass
// (docs/companions/evidence/iterations/lunar_v1.js, captures v1_lunar*) the
// cloud field filled the entire frame at near-full opacity and buried the
// moon: the result was a blue-grey texture, not a companion. Two changes fix
// it. Cloud opacity is now multiplied by an atmosphere mask that falls off
// away from the moon, so the clouds belong to the orb instead of being
// wallpaper; and the coverage thresholds are much lower, so gaps exist.
// Lunar C additionally had concentric ring banding - the same failure mode as
// the solar differential rotation - because its shear term grew without bound
// with time and smeared the noise into rings. The shear now oscillates.

const LUNAR_COMMON = `
// Sky: a vertical night gradient plus a very low-frequency airglow. A flat
// fill reads as a wallpaper swatch; this keeps the corners alive without
// lifting them off black.
vec3 nightSky(vec2 uv, float t) {
  float v = uv.y * 0.5 + 0.5;
  vec3 c = mix(lunarRamp(0.020), lunarRamp(0.110), smoothstep(-0.2, 1.1, v));
  float glow = fbm3(uv * 0.85 + vec2(t * 0.012, -t * 0.008)) * 0.5 + 0.5;
  c += lunarRamp(0.26) * glow * 0.035;
  return c;
}

// The atmosphere belongs to the moon. Without this the cloud field is simply
// a full-screen texture and the companion disappears into it.
float atmoMask(float r, float R) {
  return 0.02 + 0.98 * exp(-max(r - R, 0.0) * 2.55);
}

// The moon disc. Returns (coverage, surface luminance).
vec2 moonDisc(vec2 uv, float R, float t) {
  float r = length(uv);
  float cov = 1.0 - smoothstep(R * 0.972, R * 1.014, r);
  if (cov <= 0.0) return vec2(0.0);
  float rn = clamp(r / R, 0.0, 1.0);
  float mu = sqrt(max(0.0, 1.0 - rn * rn));
  // Sample the surface on the sphere, so craters compress toward the limb
  // instead of sliding across a flat disc.
  vec2 q = uv / max(R, 1e-4) / max(0.55 + 0.45 * mu, 0.42);
  float alb = moonAlbedo(q);
  // Near-full phase: lit almost face-on, with a slight falloff at the limb and
  // a hint of a terminator on one side so the disc is not perfectly even.
  float lam = 0.80 + 0.20 * mu;
  float term = 0.94 + 0.06 * smoothstep(-0.9, 0.9, uv.x / max(R, 1e-4));
  float lum = alb * lam * term * (0.86 + 0.14 * sin(t * 0.07));
  return vec2(cov, lum);
}

// One composited cloud layer. Shared by all four so the lighting model is
// identical and only the advection differs.
vec3 lightCloud(vec3 under, float dens, float trans, float distToMoon,
                float alpha, float flare, vec3 edgeTint) {
  if (dens <= 0.001) return under;
  float reach = trans * (0.32 + 0.68 * exp(-distToMoon * 1.20));
  float lit = clamp(0.10 + reach * (0.72 + flare * 0.46), 0.0, 1.0);
  vec3 cc = lunarRamp(0.13 + lit * 0.74);
  // Thin illuminated edges: density rising but still low. This is the single
  // detail that makes a noise field read as cloud.
  float edge = dens * (1.0 - dens) * 4.0;
  cc += edgeTint * edge * reach * (0.20 + flare * 0.40);
  return mix(under, cc, clamp(alpha, 0.0, 1.0));
}
`;

// --------------------------------------------------------------------------
// A - Cloud Veil.
// Three cloud bands drift horizontally at different rates and scales. Simple,
// legible, and the cheapest of the three.
// --------------------------------------------------------------------------
export const LUNAR_A = LUNAR_COMMON + `
void main() {
  vec2 fc = gl_FragCoord.xy;
  vec2 uv = (fc - 0.5 * uSize) / min(uSize.x, uSize.y) * 2.0;
  float r = length(uv);
  float t = uTime;

  float breathe = 0.5 + 0.5 * (sin(t * 0.19) * 0.6 + sin(t * 0.12 + 1.7) * 0.4);
  float R = uRadius * (1.0 + breathe * 0.010);

  vec3 col = nightSky(uv, t);

  float st = starField(uv * 16.0 + 7.0, t, 0.055 + uEmber * 0.05);
  col += lunarRamp(0.92) * st * 0.60 * smoothstep(R * 1.1, R * 2.6, r);

  float h = max(r - R, 0.0);
  col += lunarRamp(0.58) * exp(-h * 3.1) * (0.085 + uFlare * 0.14);
  col += lunarRamp(0.42) * exp(-h * 0.85) * (0.030 + uFlare * 0.065);

  vec2 m = moonDisc(uv, R, t);
  col += lunarRamp(0.88) * exp(-abs(r - R) * 62.0) * (0.10 + uFlare * 0.12);
  col = mix(col, lunarRamp(0.30 + m.y * 0.66), m.x);

  float atmo = atmoMask(r, R);
  vec2 toLight = r > 1e-4 ? -uv / r : vec2(0.0, 1.0);
  for (int L = 0; L < 3; L++) {
    float fl = float(L);
    float par = 1.0 + fl * 0.34;                       // parallax
    float scale = (0.62 + fl * 1.45) * par;
    float drift = (0.030 + fl * 0.026) * (0.5 + uEnergy * 1.4);
    // uFocus parts the clouds: at high focus they thin and the moon clears.
    float cover = (0.30 + uTurb * 0.34 + fl * 0.06) * (1.10 - uFocus * 0.72);
    vec2 cs = cloudSlab(uv * par, t, scale, drift, cover, toLight);
    float a = cs.x * (0.52 + fl * 0.09) * atmo * mix(1.0, 0.60, m.x);
    col = lightCloud(col, cs.x, cs.y, h, a, uFlare, lunarRamp(0.93));
  }

  vec2 mw = driftMotes(uv, t, 0.12 + uEmber * 0.14, 2, 53.0, R, 0.45, 5.0, 0.8);
  col += lunarRamp(0.55) * mw.x * 0.22 + lunarRamp(0.90) * mw.y * 0.28;

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;

// --------------------------------------------------------------------------
// B - Night Window.
// Light shafts are the subject. The occluder field is sampled a second time
// along the radial axis, so where a gap opens the escaping moonlight is drawn
// as a real beam whose shape follows the gap.
// --------------------------------------------------------------------------
export const LUNAR_B = LUNAR_COMMON + `
void main() {
  vec2 fc = gl_FragCoord.xy;
  vec2 uv = (fc - 0.5 * uSize) / min(uSize.x, uSize.y) * 2.0;
  float r = length(uv);
  vec2 dir = r > 1e-5 ? uv / r : vec2(0.0, 1.0);
  float t = uTime;

  float breathe = 0.5 + 0.5 * (sin(t * 0.17) * 0.62 + sin(t * 0.11 + 2.2) * 0.38);
  float R = uRadius * (1.0 + breathe * 0.009);

  vec3 col = nightSky(uv, t);
  float st = starField(uv * 14.0 + 3.0, t, 0.050 + uEmber * 0.05);
  col += lunarRamp(0.92) * st * 0.55 * smoothstep(R * 1.1, R * 2.4, r);

  float h = max(r - R, 0.0);
  col += lunarRamp(0.60) * exp(-h * 3.6) * (0.075 + uFlare * 0.12);

  // ---- light shafts -------------------------------------------------------
  {
    vec2 q = uv * 2.1 + vec2(t * 0.045 * (0.5 + uEnergy), 0.0);
    float occ = smearRidge(q, dir, 0.17, 4);
    float gap = pow(clamp(occ, 0.0, 1.0), 3.2);
    float lane = smoothstep(0.40, 0.86, angNoise(atan(uv.y, uv.x), 1.6, t * 0.035));
    float reach = exp(-h * (3.6 - uEnergy * 0.8)) * smoothstep(R * 0.98, R * 1.12, r);
    col += lunarRamp(0.84) * gap * lane * reach * (0.06 + uFlare * 0.80);
  }

  vec2 m = moonDisc(uv, R, t);
  col += lunarRamp(0.88) * exp(-abs(r - R) * 62.0) * (0.10 + uFlare * 0.12);
  col = mix(col, lunarRamp(0.30 + m.y * 0.66), m.x);

  float atmo = atmoMask(r, R);
  vec2 toLight = r > 1e-4 ? -uv / r : vec2(0.0, 1.0);
  for (int L = 0; L < 3; L++) {
    float fl = float(L);
    float par = 1.0 + fl * 0.45;
    float scale = (0.55 + fl * 1.30) * par;
    float drift = (0.024 + fl * 0.030) * (0.5 + uEnergy * 1.5);
    float cover = (0.32 + uTurb * 0.32 + fl * 0.05) * (1.10 - uFocus * 0.72);
    vec2 cs = cloudSlab(uv * par, t, scale, drift, cover, toLight);
    float a = cs.x * (0.54 + fl * 0.08) * atmo * mix(1.0, 0.60, m.x);
    col = lightCloud(col, cs.x, cs.y, h, a, uFlare, lunarRamp(0.95));
  }

  vec2 mw = driftMotes(uv, t, 0.10 + uEmber * 0.14, 2, 61.0, R, 0.40, 4.4, 0.8);
  col += lunarRamp(0.55) * mw.x * 0.20 + lunarRamp(0.90) * mw.y * 0.26;

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;

// --------------------------------------------------------------------------
// C - Moon Current.
// The atmosphere circulates around the moon instead of passing it. The rigid
// part of the rotation is safe because a rotation is periodic; the part that
// varies with radius is the dangerous one, and it is bounded by a sine so it
// cannot accumulate and shear the noise into rings.
// --------------------------------------------------------------------------

// Texture-backed variant of the lunar common block. Identical in every respect
// except that the surface albedo is a lookup into a baked map instead of four
// noise fields plus three crater passes evaluated per fragment.
//
// This is the "bake the expensive part into a reusable asset" question from
// the Unreal brief, made concrete and measurable. Nothing animated moves into
// the texture: the clouds, the moonlight, the halo, the mist and every
// state-driven parameter stay procedural, so the companion is still live.
const LUNAR_COMMON_TEX = LUNAR_COMMON.replace(
  '  float alb = moonAlbedo(q);',
  '  float alb = texture(uTex, q * 0.42 + 0.5).r * 1.30;'
);

export const LUNAR_C = LUNAR_COMMON + `
void main() {
  vec2 fc = gl_FragCoord.xy;
  vec2 uv = (fc - 0.5 * uSize) / min(uSize.x, uSize.y) * 2.0;
  float r = length(uv);
  float ang = atan(uv.y, uv.x);
  float t = uTime;

  float breathe = 0.5 + 0.5 * (sin(t * 0.21) * 0.58 + sin(t * 0.13 + 1.1) * 0.42);
  float R = uRadius * (1.0 + breathe * 0.012);

  vec3 col = nightSky(uv, t);
  float st = starField(uv * 15.0 + 11.0, t, 0.052 + uEmber * 0.05);
  col += lunarRamp(0.92) * st * 0.58 * smoothstep(R * 1.1, R * 2.5, r);

  float h = max(r - R, 0.0);
  col += lunarRamp(0.58) * exp(-h * 3.3) * (0.080 + uFlare * 0.13);

  vec2 m = moonDisc(uv, R, t);
  col += lunarRamp(0.88) * exp(-abs(r - R) * 62.0) * (0.10 + uFlare * 0.12);
  col = mix(col, lunarRamp(0.30 + m.y * 0.66), m.x);

  float atmo = atmoMask(r, R);
  vec2 toLight = r > 1e-4 ? -uv / r : vec2(0.0, 1.0);
  for (int L = 0; L < 3; L++) {
    float fl = float(L);
    float par = 1.0 + fl * 0.38;
    float rigid = (0.07 + uEnergy * 0.20) * t * (1.0 + fl * 0.22);
    float shear = 0.75 * sin(t * (0.055 + fl * 0.011)) * exp(-h * 0.85);
    float ca = ang - rigid - shear;
    vec2 pr = vec2(cos(ca), sin(ca)) * r * par;
    pr += curl(pr * 1.3 + fl * 9.1, t * 0.30) * (0.055 + uTurb * 0.13);
    float scale = 0.58 + fl * 1.35;
    float cover = (0.28 + uTurb * 0.36 + fl * 0.06) * (1.10 - uFocus * 0.72);
    vec2 cs = cloudSlab(pr, t, scale, 0.012 + fl * 0.010, cover, toLight);
    float a = cs.x * (0.50 + fl * 0.09) * atmo * mix(1.0, 0.60, m.x);
    col = lightCloud(col, cs.x, cs.y, h, a, uFlare, lunarRamp(0.94));
  }

  vec2 mw = driftMotes(uv, t, 0.14 + uEmber * 0.16, 3, 71.0, R, 0.55, 5.6, 0.8);
  col += lunarRamp(0.55) * mw.x * 0.26 + lunarRamp(0.92) * mw.y * 0.32;

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;

export const LUNAR_T = LUNAR_COMMON_TEX + `
void main() {
  vec2 fc = gl_FragCoord.xy;
  vec2 uv = (fc - 0.5 * uSize) / min(uSize.x, uSize.y) * 2.0;
  float r = length(uv);
  float ang = atan(uv.y, uv.x);
  float t = uTime;

  float breathe = 0.5 + 0.5 * (sin(t * 0.21) * 0.58 + sin(t * 0.13 + 1.1) * 0.42);
  float R = uRadius * (1.0 + breathe * 0.012);

  vec3 col = nightSky(uv, t);
  float st = starField(uv * 15.0 + 11.0, t, 0.052 + uEmber * 0.05);
  col += lunarRamp(0.92) * st * 0.58 * smoothstep(R * 1.1, R * 2.5, r);

  float h = max(r - R, 0.0);
  col += lunarRamp(0.58) * exp(-h * 3.3) * (0.080 + uFlare * 0.13);

  vec2 m = moonDisc(uv, R, t);
  col += lunarRamp(0.88) * exp(-abs(r - R) * 62.0) * (0.10 + uFlare * 0.12);
  col = mix(col, lunarRamp(0.30 + m.y * 0.66), m.x);

  float atmo = atmoMask(r, R);
  vec2 toLight = r > 1e-4 ? -uv / r : vec2(0.0, 1.0);
  for (int L = 0; L < 3; L++) {
    float fl = float(L);
    float par = 1.0 + fl * 0.38;
    float rigid = (0.07 + uEnergy * 0.20) * t * (1.0 + fl * 0.22);
    float shear = 0.75 * sin(t * (0.055 + fl * 0.011)) * exp(-h * 0.85);
    float ca = ang - rigid - shear;
    vec2 pr = vec2(cos(ca), sin(ca)) * r * par;
    pr += curl(pr * 1.3 + fl * 9.1, t * 0.30) * (0.055 + uTurb * 0.13);
    float scale = 0.58 + fl * 1.35;
    float cover = (0.28 + uTurb * 0.36 + fl * 0.06) * (1.10 - uFocus * 0.72);
    vec2 cs = cloudSlab(pr, t, scale, 0.012 + fl * 0.010, cover, toLight);
    float a = cs.x * (0.50 + fl * 0.09) * atmo * mix(1.0, 0.60, m.x);
    col = lightCloud(col, cs.x, cs.y, h, a, uFlare, lunarRamp(0.94));
  }

  vec2 mw = driftMotes(uv, t, 0.14 + uEmber * 0.16, 3, 71.0, R, 0.55, 5.6, 0.8);
  col += lunarRamp(0.55) * mw.x * 0.26 + lunarRamp(0.92) * mw.y * 0.32;

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;

// --------------------------------------------------------------------------
// H - Moonlit Blossom (Lunar x Sakura).
// The owner asked whether the cloudy moon and the sakura petals could be one
// companion. They can, on one condition: the petals must be lit by the moon
// rather than glowing on their own. A self-luminous pink petal in front of a
// silver moon reads as two unrelated effects sharing a frame.
// --------------------------------------------------------------------------
export const LUNAR_SAKURA = LUNAR_COMMON + `
void main() {
  vec2 fc = gl_FragCoord.xy;
  vec2 uv = (fc - 0.5 * uSize) / min(uSize.x, uSize.y) * 2.0;
  float r = length(uv);
  float t = uTime;

  float breathe = 0.5 + 0.5 * (sin(t * 0.19) * 0.6 + sin(t * 0.12 + 1.7) * 0.4);
  float R = uRadius * (1.0 + breathe * 0.011);

  vec3 col = nightSky(uv, t);
  float st = starField(uv * 16.0 + 5.0, t, 0.050 + uEmber * 0.04);
  col += lunarRamp(0.92) * st * 0.55 * smoothstep(R * 1.1, R * 2.5, r);

  float h = max(r - R, 0.0);
  // The halo carries a trace of rose, which is what ties the two identities
  // together without tinting the moon itself.
  col += lunarRamp(0.58) * exp(-h * 3.2) * (0.075 + uFlare * 0.12);
  col += sakuraRamp(0.44) * exp(-h * 3.4) * (0.018 + uFlare * 0.034);

  // Petals, split into a layer behind the moon and a layer in front of it.
  vec4 back = vec4(0.0); vec4 front = vec4(0.0);
  float zb = -1.0, zf = -1.0;
  int count = int(12.0 + uEmber * 18.0);
  for (int i = 0; i < 30; i++) {
    if (i >= count) break;
    float fi = float(i);
    vec2 h1 = hash22(vec2(fi, 13.0));
    vec2 h2 = hash22(vec2(fi, 14.0));
    float period = 14.0 + h1.x * 16.0;
    float ph = fract(t / period + h1.y);
    float life = smoothstep(0.0, 0.12, ph) * (1.0 - smoothstep(0.80, 1.0, ph));
    if (life < 0.02) continue;
    float depth = h2.x;
    // A slow night breeze across the frame, curved by the air around the moon.
    vec2 c = vec2(mix(-1.75, 1.75, ph) + h1.x * 0.3,
                  mix(1.25, -1.05, ph * 0.72) + h2.y * 1.6 - 0.8);
    c += waver(fi * 4.3, t, 0.055 + uTurb * 0.13);
    float size = R * (0.13 + 0.16 * depth) * (0.8 + 0.4 * h1.y);
    float rot = sin(t * (0.4 + h1.y * 0.6) + fi) * 0.9 + ph * 1.3;
    float tilt = cos(t * (0.65 + h2.x * 1.4) + fi * 2.11);
    vec3 sh = petalAt(uv, c, size, rot, tilt);
    if (sh.x <= 0.0) continue;
    // Moonlit, not self-lit: brightness comes from how much of the moon the
    // petal faces, so petals crossing the disc are the brightest in frame.
    float toMoon = exp(-max(length(c) - R, 0.0) * 0.95);
    float facing = 0.35 + 0.65 * (1.0 - abs(tilt));
    float lum = (0.10 + 0.90 * toMoon) * facing;
    vec3 pc = mix(lunarRamp(0.42 + lum * 0.45), sakuraRamp(0.52 + lum * 0.34), 0.58)
            * (0.30 + 1.15 * lum) * life;
    pc = mix(pc, sakuraRamp(0.30), sh.y * 0.45);     // deeper, rosier rim
    if (depth < 0.5) { if (depth > zb) { back = vec4(pc, sh.x * life); zb = depth; } }
    else            { if (depth > zf) { front = vec4(pc, sh.x * life); zf = depth; } }
  }
  col = mix(col, back.rgb, clamp(back.a, 0.0, 1.0));

  vec2 m = moonDisc(uv, R, t);
  col += lunarRamp(0.88) * exp(-abs(r - R) * 62.0) * (0.10 + uFlare * 0.12);
  col = mix(col, lunarRamp(0.30 + m.y * 0.66), m.x);

  float atmo = atmoMask(r, R);
  vec2 toLight = r > 1e-4 ? -uv / r : vec2(0.0, 1.0);
  for (int L = 0; L < 3; L++) {
    float fl = float(L);
    float par = 1.0 + fl * 0.34;
    float scale = (0.62 + fl * 1.45) * par;
    float drift = (0.028 + fl * 0.024) * (0.5 + uEnergy * 1.3);
    float cover = (0.28 + uTurb * 0.32 + fl * 0.06) * (1.10 - uFocus * 0.72);
    vec2 cs = cloudSlab(uv * par, t, scale, drift, cover, toLight);
    float a = cs.x * (0.48 + fl * 0.09) * atmo * mix(1.0, 0.60, m.x);
    // Cloud edges pick up the faintest rose, the only place the two palettes
    // are allowed to meet.
    col = lightCloud(col, cs.x, cs.y, h, a, uFlare,
                     mix(lunarRamp(0.93), sakuraRamp(0.86), 0.28));
  }

  col = mix(col, front.rgb, clamp(front.a, 0.0, 1.0));

  vec2 mw = driftMotes(uv, t, 0.12 + uEmber * 0.14, 2, 83.0, R, 0.5, 5.2, 0.7);
  col += sakuraRamp(0.46) * mw.x * 0.18 + lunarRamp(0.92) * mw.y * 0.30;

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;
