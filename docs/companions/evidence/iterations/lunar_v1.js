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

const LUNAR_COMMON = `
// Sky: a vertical night gradient plus a very low-frequency airglow. A flat
// fill reads as a wallpaper swatch; this keeps the corners alive.
vec3 nightSky(vec2 uv, float t) {
  float v = uv.y * 0.5 + 0.5;
  vec3 c = mix(lunarRamp(0.055), lunarRamp(0.175), smoothstep(-0.2, 1.1, v));
  float glow = fbm3(uv * 0.85 + vec2(t * 0.012, -t * 0.008)) * 0.5 + 0.5;
  c += lunarRamp(0.30) * glow * 0.055;
  return c;
}

// The moon disc. Returns (coverage, surface luminance).
vec2 moonDisc(vec2 uv, float R, float t) {
  float r = length(uv);
  float cov = 1.0 - smoothstep(R * 0.985, R * 1.004, r);
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

  // Stars, dimmed close to the moon where its glare would wash them out.
  float st = starField(uv * 16.0 + 7.0, t, 0.055 + uEmber * 0.05);
  col += lunarRamp(0.92) * st * 0.55 * smoothstep(R * 1.1, R * 2.6, r);

  // Halo: atmospheric scattering around the disc.
  float h = max(r - R, 0.0);
  col += lunarRamp(0.58) * exp(-h * 3.1) * (0.085 + uFlare * 0.14);
  col += lunarRamp(0.42) * exp(-h * 0.85) * (0.030 + uFlare * 0.065);

  vec2 m = moonDisc(uv, R, t);
  col = mix(col, lunarRamp(0.30 + m.y * 0.66), m.x);

  // Clouds, far to near.
  vec2 toLight = r > 1e-4 ? -uv / r : vec2(0.0, 1.0);
  for (int L = 0; L < 3; L++) {
    float fl = float(L);
    float par = 1.0 + fl * 0.34;                       // parallax
    float scale = (1.35 + fl * 0.95) * par;
    float drift = (0.030 + fl * 0.026) * (0.5 + uEnergy * 1.4);
    // uFocus parts the clouds: at high focus they thin and the moon clears.
    float cover = (0.30 + uTurb * 0.26 + fl * 0.07) * (1.25 - uFocus * 0.75);
    vec2 cs = cloudSlab(uv * par, t, scale, drift, cover, toLight);
    float dens = cs.x;
    if (dens <= 0.001) continue;
    // Light reaching this parcel: direct transmittance toward the moon, times
    // the moon's own falloff with distance.
    float reach = cs.y * (0.35 + 0.65 * exp(-max(length(uv) - R, 0.0) * 1.25));
    float lit = clamp(0.12 + reach * (0.70 + uFlare * 0.45), 0.0, 1.0);
    vec3 cc = lunarRamp(0.16 + lit * 0.72);
    // Thin illuminated edges: where density is rising but still low.
    float edge = dens * (1.0 - dens) * 4.0;
    cc += lunarRamp(0.93) * edge * reach * (0.16 + uFlare * 0.30);
    float a = dens * (0.62 + fl * 0.14);
    col = mix(col, cc, clamp(a, 0.0, 1.0));
  }

  // Mist wisps escaping the orb region.
  vec2 mw = driftMotes(uv, t, 0.14 + uEmber * 0.16, 2, 53.0, R, 0.45, 5.0);
  col += lunarRamp(0.55) * mw.x * 0.28 + lunarRamp(0.90) * mw.y * 0.32;

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;

// --------------------------------------------------------------------------
// B - Night Window.
// Light shafts are the subject. The clouds are sampled a second time along the
// radial axis, so where a gap opens the escaping moonlight is drawn as a real
// beam whose shape follows the gap.
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
  col += lunarRamp(0.92) * st * 0.50 * smoothstep(R * 1.1, R * 2.4, r);

  float h = max(r - R, 0.0);
  col += lunarRamp(0.60) * exp(-h * 3.6) * (0.075 + uFlare * 0.12);

  // ---- light shafts -------------------------------------------------------
  // The occluder field is the near cloud layer. Smearing it along the radial
  // direction and inverting gives the gaps between clouds, which is exactly
  // where a beam should be.
  {
    float cover = (0.34 + uTurb * 0.24) * (1.25 - uFocus * 0.75);
    vec2 q = uv * 2.1 + vec2(t * 0.045 * (0.5 + uEnergy), 0.0);
    float occ = smearRidge(q, dir, 0.17, 4);
    float gap = pow(clamp(occ, 0.0, 1.0), 1.9);
    float reach = exp(-h * (2.0 - uEnergy * 0.6)) * smoothstep(R * 0.98, R * 1.08, r);
    col += lunarRamp(0.80) * gap * reach
         * (0.10 + uFlare * 0.95) * (1.1 - cover * 0.6);
  }

  vec2 m = moonDisc(uv, R, t);
  col = mix(col, lunarRamp(0.30 + m.y * 0.66), m.x);

  vec2 toLight = r > 1e-4 ? -uv / r : vec2(0.0, 1.0);
  for (int L = 0; L < 3; L++) {
    float fl = float(L);
    float par = 1.0 + fl * 0.45;
    float scale = (1.05 + fl * 0.80) * par;
    float drift = (0.024 + fl * 0.030) * (0.5 + uEnergy * 1.5);
    float cover = (0.34 + uTurb * 0.24 + fl * 0.06) * (1.25 - uFocus * 0.75);
    vec2 cs = cloudSlab(uv * par, t, scale, drift, cover, toLight);
    float dens = cs.x;
    if (dens <= 0.001) continue;
    float reach = cs.y * (0.30 + 0.70 * exp(-max(length(uv) - R, 0.0) * 1.05));
    float lit = clamp(0.10 + reach * (0.72 + uFlare * 0.50), 0.0, 1.0);
    vec3 cc = lunarRamp(0.14 + lit * 0.74);
    float edge = dens * (1.0 - dens) * 4.0;
    cc += lunarRamp(0.95) * edge * reach * (0.20 + uFlare * 0.38);
    col = mix(col, cc, clamp(dens * (0.66 + fl * 0.12), 0.0, 1.0));
  }

  vec2 mw = driftMotes(uv, t, 0.12 + uEmber * 0.16, 2, 61.0, R, 0.40, 4.4);
  col += lunarRamp(0.55) * mw.x * 0.26 + lunarRamp(0.90) * mw.y * 0.30;

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;

// --------------------------------------------------------------------------
// C - Moon Current.
// The atmosphere circulates around the moon instead of passing it. Each layer
// is sampled in a curl-advected frame, so the mist curls, shears and escapes
// outward. The most "alive" of the three, and the least like weather.
// --------------------------------------------------------------------------
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
  col += lunarRamp(0.92) * st * 0.52 * smoothstep(R * 1.1, R * 2.5, r);

  float h = max(r - R, 0.0);
  col += lunarRamp(0.58) * exp(-h * 3.3) * (0.080 + uFlare * 0.13);

  vec2 m = moonDisc(uv, R, t);
  col = mix(col, lunarRamp(0.30 + m.y * 0.66), m.x);

  vec2 toLight = r > 1e-4 ? -uv / r : vec2(0.0, 1.0);
  for (int L = 0; L < 3; L++) {
    float fl = float(L);
    float par = 1.0 + fl * 0.38;
    // Circulation: tangential advection that decays with distance, plus curl.
    float spin = (0.10 + uEnergy * 0.34) * (1.0 + fl * 0.25) * t
               * exp(-max(r - R, 0.0) * 0.55);
    float ca = ang - spin;
    vec2 pr = vec2(cos(ca), sin(ca)) * r * par;
    pr += curl(pr * 1.3 + fl * 9.1, t * 0.30) * (0.045 + uTurb * 0.11);
    float scale = 1.25 + fl * 0.85;
    float cover = (0.28 + uTurb * 0.30 + fl * 0.06) * (1.25 - uFocus * 0.75);
    vec2 cs = cloudSlab(pr, t, scale, 0.012 + fl * 0.010, cover, toLight);
    float dens = cs.x;
    if (dens <= 0.001) continue;
    float reach = cs.y * (0.32 + 0.68 * exp(-max(r - R, 0.0) * 1.15));
    float lit = clamp(0.12 + reach * (0.70 + uFlare * 0.46), 0.0, 1.0);
    vec3 cc = lunarRamp(0.15 + lit * 0.73);
    float edge = dens * (1.0 - dens) * 4.0;
    cc += lunarRamp(0.94) * edge * reach * (0.18 + uFlare * 0.34);
    // Thin the mist well away from the moon so the frame does not fog over.
    float a = dens * (0.60 + fl * 0.13) * mix(1.0, 0.45, smoothstep(R * 2.0, 1.5, r));
    col = mix(col, cc, clamp(a, 0.0, 1.0));
  }

  vec2 mw = driftMotes(uv, t, 0.16 + uEmber * 0.18, 3, 71.0, R, 0.55, 5.6);
  col += lunarRamp(0.55) * mw.x * 0.30 + lunarRamp(0.92) * mw.y * 0.36;

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
  col += lunarRamp(0.92) * st * 0.50 * smoothstep(R * 1.1, R * 2.5, r);

  float h = max(r - R, 0.0);
  // The halo carries a trace of rose, which is what ties the two identities
  // together without tinting the moon itself.
  col += lunarRamp(0.58) * exp(-h * 3.2) * (0.075 + uFlare * 0.12);
  col += sakuraRamp(0.40) * exp(-h * 1.6) * (0.035 + uFlare * 0.070);

  // Petals behind the moon.
  vec4 back = vec4(0.0); vec4 front = vec4(0.0);
  float zb = -1.0, zf = -1.0;
  int count = int(10.0 + uEmber * 20.0);
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
    c += curl(c * 1.3 + fi * 4.3, t * 0.20) * (0.055 + uTurb * 0.13);
    float size = R * (0.12 + 0.15 * depth) * (0.8 + 0.4 * h1.y);
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
  col = mix(col, lunarRamp(0.30 + m.y * 0.66), m.x);

  vec2 toLight = r > 1e-4 ? -uv / r : vec2(0.0, 1.0);
  for (int L = 0; L < 3; L++) {
    float fl = float(L);
    float par = 1.0 + fl * 0.34;
    float scale = (1.35 + fl * 0.95) * par;
    float drift = (0.028 + fl * 0.024) * (0.5 + uEnergy * 1.3);
    float cover = (0.28 + uTurb * 0.24 + fl * 0.06) * (1.25 - uFocus * 0.75);
    vec2 cs = cloudSlab(uv * par, t, scale, drift, cover, toLight);
    float dens = cs.x;
    if (dens <= 0.001) continue;
    float reach = cs.y * (0.35 + 0.65 * exp(-max(r - R, 0.0) * 1.20));
    float lit = clamp(0.12 + reach * (0.70 + uFlare * 0.42), 0.0, 1.0);
    vec3 cc = lunarRamp(0.16 + lit * 0.72);
    float edge = dens * (1.0 - dens) * 4.0;
    // Cloud edges pick up the faintest rose, the only place the two palettes
    // are allowed to meet.
    cc += mix(lunarRamp(0.93), sakuraRamp(0.86), 0.28) * edge * reach
        * (0.16 + uFlare * 0.30);
    col = mix(col, cc, clamp(dens * (0.60 + fl * 0.13), 0.0, 1.0));
  }

  col = mix(col, front.rgb, clamp(front.a, 0.0, 1.0));

  vec2 mw = driftMotes(uv, t, 0.14 + uEmber * 0.16, 2, 83.0, R, 0.5, 5.2);
  col += sakuraRamp(0.46) * mw.x * 0.22 + lunarRamp(0.92) * mw.y * 0.34;

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;
