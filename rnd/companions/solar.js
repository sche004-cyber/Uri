// Solar Intelligence - refined direction (E), successor to PROTO_D.
//
// Three defects were visible in the first real Flutter frames (see
// docs/companions/evidence/flutter/run1/solar_*.png):
//   1. the core flattened to a featureless cream disc at high energy;
//   2. the magnetic arcs rendered as smooth geometric crescents, reading as
//      glass slivers floating beside the orb rather than anchored plasma;
//   3. the corona drifted grey-brown where it was dim.
// Each is addressed below and the reasoning is kept next to the fix.

export const SOLAR_E = `
// A prominence loop built from several wandering strands rather than one
// smooth arch. The crescent look came from a single Gaussian around a perfect
// semi-ellipse: no shape that clean occurs in plasma.
// Returns (strand core, halo, hot knots).
vec3 loopArcE(float r, float ang, float R, float aMid, float aSpan,
              float height, float thick, float seed, float t) {
  float da = atan(sin(ang - aMid), cos(ang - aMid));
  float u = da / max(aSpan, 1e-3);
  if (abs(u) > 1.10) return vec3(0.0);
  float au = min(abs(u), 1.0);
  float lift = sqrt(max(0.0, 1.0 - au * au));

  vec3 acc = vec3(0.0);
  for (int s = 0; s < 3; s++) {
    float fs = float(s);
    // Each strand wanders on its own slow noise, so the loop is never a clean
    // conic section and the three never stay parallel.
    float wob = unoise(vec2(u * 2.6 + fs * 5.1 + seed, t * 0.40 + fs * 2.7)) - 0.5;
    float hgt = height * (0.76 + fs * 0.16) * (1.0 + wob * 0.42);
    float arch = R * (1.0 + hgt * lift);
    float w = thick * (0.40 + 0.60 * au) * (0.66 + fs * 0.26);
    float d = (r - arch) / max(w, 1e-4);
    float g = exp(-d * d);
    // Plasma draining along the strand toward the footpoints.
    float flow = 0.38 + 0.62 * unoise(vec2(u * 8.0 + fs * 3.3 + seed, -t * 1.7 + fs));
    acc.x += g * flow * (1.0 - fs * 0.24);
    acc.y += exp(-d * d * 0.14) * 0.075;
    acc.z += g * smoothstep(0.62, 1.00, flow) * (1.0 - fs * 0.30);
  }
  // Fade the ends into the surface instead of stopping at a hard angle.
  return acc * smoothstep(1.08, 0.34, au);
}

void main() {
  vec2 fc = gl_FragCoord.xy;
  vec2 uv = (fc - 0.5 * uSize) / min(uSize.x, uSize.y) * 2.0;
  float r = length(uv);
  vec2 dir = r > 1e-5 ? uv / r : vec2(0.0, 1.0);
  float ang = atan(uv.y, uv.x);

  float breathe = 0.5 + 0.5 * (sin(uTime * 0.33) * 0.52
                             + sin(uTime * 0.21 + 1.9) * 0.31
                             + sin(uTime * 0.13 + 0.7) * 0.17);
  float R = uRadius * (1.0 + breathe * 0.020 * (0.4 + uEnergy));
  float t = uTime * (0.11 + uEnergy * 0.45);

  vec3 col = vec3(0.0);

  float gate = smoothstep(0.26, 0.85, uEnergy);
  vec2 cuv = uv + curl(uv * 1.5, t) * (0.016 + uTurb * 0.034) * gate;
  float tongue = smearRidge(cuv * 3.4 + vec2(-t * 0.28, t * 0.20), dir, 0.150, 5);
  float swell = angNoise(ang, 1.7, t * 0.080);
  float breach = (tongue * 0.66 + swell * 0.42) * gate * (0.30 + uEnergy * 0.55);
  float Reff = R * (1.0 + breach * (0.24 + uTurb * 0.34));

  // ---- photosphere --------------------------------------------------------
  if (r < R * 1.03) {
    float rn = clamp(r / R, 0.0, 1.0);
    float mu = sqrt(max(0.0, 1.0 - rn * rn));
    vec2 sp = uv / max(0.62 + 0.38 * mu, 0.40);

    float lat = uv.y / max(R, 1e-3);
    vec2 rp = sp + vec2(t * (0.14 - 0.07 * lat * lat), 0.0);

    float band = warpFbm(vec2(rp.x * 1.9, rp.y * 3.4), t, 2.2);
    vec2 drift = curl(sp * 1.4, t * 0.6) * 0.060;
    float mot = warpFbm(sp * 4.4 + drift * 3.0 + vec2(-t * 0.20, t * 0.12), t * 1.2, 2.2);
    float fib = ridged(sp * 7.2 + drift * 5.0 + vec2(-t * 0.30, t * 0.21), 4);
    // A second, finer fibril octave. Detail at this scale is what survives the
    // tonemap near the centre, where the broad terms are all saturated.
    float fine = ridged(sp * 15.0 + drift * 9.0 + vec2(t * 0.42, -t * 0.26), 3);

    // Temperature still rises toward the centre, but less steeply, and the
    // structure terms are given more of the range. The old curve reached the
    // top of the ramp well before the noise was added, so every detail in the
    // middle third mapped to the same white.
    float heat = 0.46 + 0.22 * (1.0 - rn * rn)
               + band * 0.090 + mot * 0.085
               + (fib - 0.42) * 0.095 * (0.6 + uTurb * 0.7)
               + (fine - 0.45) * 0.055;
    heat = clamp(heat * (0.80 + 0.20 * limbDarken(mu)), 0.0, 1.0);

    // Brightness is a separate, flatter field: the centre is hotter in colour
    // but only moderately brighter, which is what keeps detail there.
    float bright = (0.40 + 0.46 * pow(1.0 - rn, 1.6)) * limbDarken(mu)
                 * (0.86 + 0.28 * (mot * 0.5 + 0.5))
                 * (0.90 + 0.20 * (fine - 0.45));

    float edge = 1.0 - smoothstep(R * 0.975, R * 1.012, r);
    col += fireRamp(heat) * bright * edge * (1.0 + uEnergy * 0.34);

    float crest = smoothstep(0.58, 0.92, fib);
    col += fireRamp(0.86) * crest * edge * mu * (0.15 + uEnergy * 0.52);

    // Faculae: small bright grains that read as surface, strongest near the
    // limb where foreshortening packs them together.
    float fac = smoothstep(0.74, 0.97, unoise(sp * 22.0 + vec2(-t * 0.5, t * 0.33)));
    col += fireRamp(0.93) * fac * edge * (0.10 + uEnergy * 0.26) * (0.35 + rn * 0.9);

    // The nucleus is textured and far weaker than before. A smooth
    // high-amplitude blob here is what produced the flat cream centre.
    float nucleus = pow(max(0.0, 1.0 - rn * 3.6), 2.6);
    float nTex = 0.48 + 0.52 * (mot * 0.5 + 0.5) * (0.55 + 0.45 * fine);
    col += fireRamp(0.95) * nucleus * nTex * edge * (0.34 + uEnergy * 0.30);
  }

  // ---- erupting limb ------------------------------------------------------
  {
    float field = (Reff - r) / max(R, 1e-3);
    float outside = smoothstep(R * 0.97, R * 1.01, r);
    float dens = smoothstep(-0.04, 0.22, field) * outside;
    float h = max(r - R, 0.0);
    float temp = clamp(0.76 - h * 1.25, 0.14, 1.0);
    col += fireRamp(temp) * dens * tongue * (0.85 + uEnergy * 1.45);
  }

  // ---- magnetic loop arcs -------------------------------------------------
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float seed = fi * 7.3;
    float period = 11.0 + fi * 3.17;
    float cyc = floor((uTime + seed * 3.1) / period);
    float phase = fract((uTime + seed * 3.1) / period);
    float life = smoothstep(0.00, 0.18, phase) * (1.0 - smoothstep(0.44, 1.00, phase));
    if (life < 0.004) continue;

    float aMid = hash12(vec2(seed, cyc)) * TAU + t * 0.14;
    float aSpan = 0.34 + hash12(vec2(seed + 1.0, cyc)) * 0.30;
    float height = (0.22 + hash12(vec2(seed + 2.0, cyc)) * 0.36)
                 * (0.45 + uFlare * 1.10) * life;
    float thick = R * (0.050 + 0.040 * (1.0 - uFocus)) * (0.55 + life * 0.70);

    // Arc brightness now tracks uFlare far more steeply. At idle (uFlare 0.10)
    // the old curve still produced near-white crescents, which is why the calm
    // state looked wrong.
    float amt = life * (0.14 + uFlare * 2.00);

    float da = atan(sin(ang - aMid), cos(ang - aMid)) / max(aSpan, 1e-3);
    // Footpoints are computed before the arc's early exit on purpose: the term
    // peaks at the angular cutoff, and skipping it there cut hard radial
    // wedges into the background.
    float fa = (abs(da) - 1.0) / 0.26;
    float fr = (r - R) / (R * 0.12);
    col += fireRamp(0.88) * exp(-fa * fa) * exp(-fr * fr) * life
         * (0.10 + uFlare * 1.05);

    vec3 g = loopArcE(r, ang, R, aMid, aSpan, height, thick, seed, uTime);
    if (g.x + g.y + g.z <= 0.0) continue;
    col += fireRamp(0.54) * g.x * amt;
    col += fireRamp(0.40) * g.y * amt * 0.55;
    col += fireRamp(0.84) * g.z * amt * 0.85;
  }

  // ---- corona -------------------------------------------------------------
  // Same structure as D, warmer floor. The grey cast came from sampling the
  // ramp below 0.38, where it is a desaturated near-black that reads as smoke
  // once the tonemap lifts it.
  {
    float h = max(r - R, 0.0);
    float clump = smoothstep(0.26, 0.92, angNoise(ang, 1.15, t * 0.030));
    float lenMod = 0.30 + 1.25 * clump;
    float fall = exp(-h * (6.6 - uEnergy * 2.2) / max(lenMod, 0.18));
    vec2 bend = curl(uv * 1.1 + 13.0, t * 0.5) * 0.050;
    vec2 cp = (uv + bend) * 2.4 - vec2(0.0, t * 0.16);
    float ray = pow(smearRidge(cp, dir, 0.26, 4), 2.1);
    float amt = fall * (0.06 + ray * 1.10 * (0.35 + clump)) * (0.45 + uEnergy * 0.90);
    col += fireRamp(0.48 + ray * 0.30) * amt;

    float rimN = 0.08 + 0.92 * angNoise(ang, 3.6, t * 0.09)
               * (0.45 + 0.55 * angNoise(ang, 1.3, t * 0.05));
    col += fireRamp(0.82) * exp(-abs(r - R) * 46.0) * rimN * (0.24 + uEnergy * 0.32);
    col += fireRamp(0.36) * exp(-h * 1.3) * 0.028 * (0.5 + uEnergy);
  }

  col += emberField(uv, uTime, 0.28 + uEmber * 0.40, 3, 23.0, R) * (0.8 + uEmber * 1.5);

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;
