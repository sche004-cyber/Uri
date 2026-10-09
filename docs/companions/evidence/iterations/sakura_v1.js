// Sakura Intelligence - three meaningfully different directions.
//
// Uniform reading for this family (the contract is shared with Solar and
// Lunar so one Flutter painter serves all three):
//   uEnergy   overall activity: core brightness, orbital rate, petal count
//   uTurb     wind chaos in the petal field
//   uFlare    energy-ribbon strength
//   uEmber    petal and pollen density
//   uFocus    how ordered the motion is (high: tight arms; low: loose drift)
//
// The three differ in what carries the identity:
//   A  the orbit does    - a sheared vortex, petals on spiral arms
//   B  the wind does     - petals advected through a curl field, passing by
//   C  the flower does   - a layered blossom core, petals as its corona

// --------------------------------------------------------------------------
// A - Blossom Vortex.
// Differential rotation (inner petals orbit faster) winds an initially even
// ring into spiral arms on its own. Nothing draws an "arm": the shear makes
// them, which is why the pattern never repeats exactly.
// --------------------------------------------------------------------------
export const SAKURA_A = `
void main() {
  vec2 fc = gl_FragCoord.xy;
  vec2 uv = (fc - 0.5 * uSize) / min(uSize.x, uSize.y) * 2.0;
  float r = length(uv);
  float ang = atan(uv.y, uv.x);

  float breathe = 0.5 + 0.5 * (sin(uTime * 0.27) * 0.55
                             + sin(uTime * 0.17 + 2.1) * 0.30
                             + sin(uTime * 0.11 + 0.6) * 0.15);
  float R = uRadius * (1.0 + breathe * 0.026 * (0.5 + uEnergy));
  float t = uTime;

  vec3 col = vec3(0.0);

  // ---- petals, back layer and front layer -------------------------------
  // Painter's algorithm per layer: keep only the frontmost petal in each, so
  // overlapping petals occlude instead of summing into a glowing smear.
  vec4 back = vec4(0.0);
  vec4 front = vec4(0.0);
  float zb = -1.0, zf = -1.0;

  int count = int(14.0 + uEmber * 24.0);
  for (int i = 0; i < 38; i++) {
    if (i >= count) break;
    float fi = float(i);
    vec2 h1 = hash22(vec2(fi, 1.0));
    vec2 h2 = hash22(vec2(fi, 2.0));

    float period = 13.0 + h1.x * 17.0;
    float ph = fract(t / period + h1.y);
    float life = smoothstep(0.0, 0.13, ph) * (1.0 - smoothstep(0.76, 1.0, ph));
    if (life < 0.02) continue;

    float depth = h2.x;                                  // 0 far .. 1 near
    // Spirals inward across its life, so the field is always being fed from
    // outside rather than cycling in place.
    float rad = R * (1.15 + h1.x * 2.05) * (1.0 - 0.42 * ph);
    // Differential rotation: this is the spiral generator.
    float omega = (0.42 + 0.80 * uEnergy) / pow(max(rad, 0.18), 1.20);
    float a0 = h2.y * TAU + t * omega * (0.55 + depth * 0.75);
    vec2 c = vec2(cos(a0), sin(a0)) * rad;
    c += curl(c * 1.7 + fi * 3.1, t * 0.22) * (0.022 + uTurb * 0.085)
       * (1.4 - uFocus);

    float size = R * (0.15 + 0.16 * depth) * (0.78 + 0.44 * h1.y);
    float rot = a0 + PI * 0.5 + sin(t * (0.42 + h1.y * 0.6) + fi) * 0.55;
    float tilt = cos(t * (0.55 + h2.x * 1.25) + fi * 2.37);

    vec3 sh = petalAt(uv, c, size, rot, tilt);
    if (sh.x <= 0.0) continue;

    // Backlight: petals close to the core are lit through, which is what makes
    // them read as thin translucent tissue rather than cut-out sprites.
    float lit = exp(-max(length(c) - R, 0.0) * 1.45);
    float tone = clamp(0.56 + 0.30 * lit - 0.20 * sh.y - 0.09 * sh.z
                       + 0.10 * (1.0 - abs(tilt)), 0.0, 1.0);
    vec3 pc = sakuraRamp(tone) * (0.42 + 0.95 * lit + 0.42 * depth) * life;

    if (depth < 0.5) {
      if (depth > zb) { back = vec4(pc, sh.x * life); zb = depth; }
    } else {
      if (depth > zf) { front = vec4(pc, sh.x * life); zf = depth; }
    }
  }
  col = mix(col, back.rgb, clamp(back.a, 0.0, 1.0));

  // ---- energy ribbons ----------------------------------------------------
  // Few, fat, curved. Many thin ones read as a lens flare, exactly as they did
  // on the solar corona.
  for (int k = 0; k < 3; k++) {
    float fk = float(k);
    float rr = R * (1.12 + fk * 0.40)
             + R * 0.20 * sin(ang * (2.0 + fk) + t * (0.30 + fk * 0.09));
    float ns = (unoise(vec2(ang * 2.1 + fk * 5.0, t * 0.22)) - 0.5) * R * 0.22;
    float d = abs(r - rr - ns);
    float w = R * (0.065 + 0.030 * fk);
    float g = exp(-(d * d) / (w * w));
    float flow = 0.35 + 0.65 * unoise(vec2(ang * 5.2 - t * 1.05, fk * 3.0));
    col += lavenderRamp(0.42 + 0.44 * flow) * g * flow * (0.07 + uFlare * 0.80);
  }

  // ---- core --------------------------------------------------------------
  if (r < R * 1.10) {
    float rn = clamp(r / R, 0.0, 1.0);
    float mu = sqrt(max(0.0, 1.0 - rn * rn));
    vec2 sp = uv / max(0.64 + 0.36 * mu, 0.40);
    vec2 drift = curl(sp * 1.3, t * 0.35) * 0.055;
    float swirl = warpFbm(sp * 3.6 + drift * 3.0 + vec2(-t * 0.10, t * 0.07),
                          t * 0.6, 2.0);
    float fil = ridged(sp * 9.0 + drift * 6.0 + vec2(t * 0.14, -t * 0.09), 4);

    float tone = 0.50 + 0.22 * (1.0 - rn * rn) + swirl * 0.11
               + (fil - 0.42) * 0.10;
    tone = clamp(tone * (0.82 + 0.18 * limbDarken(mu)), 0.0, 1.0);
    float bright = (0.36 + 0.42 * pow(1.0 - rn, 1.7)) * limbDarken(mu)
                 * (0.88 + 0.24 * (swirl * 0.5 + 0.5));
    float edge = 1.0 - smoothstep(R * 0.96, R * 1.04, r);
    col += sakuraRamp(tone) * bright * edge * (0.85 + uEnergy * 0.55);
    col += sakuraRamp(0.94) * pow(max(0.0, 1.0 - rn * 3.3), 2.4)
         * (0.45 + 0.55 * (swirl * 0.5 + 0.5)) * edge * (0.26 + uEnergy * 0.30);
    // Soft outer bloom. Kept low: the brief calls out excessive bloom and it
    // is the quickest way to lose the petals.
    col += sakuraRamp(0.72) * exp(-max(r - R, 0.0) * 7.5) * (0.10 + uEnergy * 0.16);
  }

  col = mix(col, front.rgb, clamp(front.a, 0.0, 1.0));

  // ---- pollen ------------------------------------------------------------
  vec2 m = driftMotes(uv, t, 0.22 + uEmber * 0.26, 3, 17.0, R, 0.9, 7.0);
  col += sakuraRamp(0.58) * m.x * 0.55 + sakuraRamp(0.95) * m.y * 0.75;

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;

// --------------------------------------------------------------------------
// B - Wind Current.
// No orbits. A single curl-noise wind field advects every petal, and the orb
// is an obstacle that the flow bends around. Petals enter from outside, sweep
// past the core and leave, so the companion reads as something standing in a
// spring gust rather than something spinning a ring of props.
// --------------------------------------------------------------------------
export const SAKURA_B = `
// The wind: curl noise plus a bias that circulates around the core, so the
// flow accelerates past the orb instead of running through it.
vec2 windAt(vec2 p, float t, float R, float turb, float focus) {
  vec2 w = curl(p * 1.25 + 4.1, t * 0.30) * (0.55 + turb * 0.95);
  float d = max(length(p), 1e-4);
  vec2 tang = vec2(-p.y, p.x) / d;
  vec2 out_ = p / d;
  float near = exp(-max(d - R, 0.0) * 2.1);
  w += tang * near * (0.55 + focus * 0.95);
  w += out_ * near * 0.18;
  w += vec2(0.38, 0.10);                 // prevailing breeze
  return w;
}

void main() {
  vec2 fc = gl_FragCoord.xy;
  vec2 uv = (fc - 0.5 * uSize) / min(uSize.x, uSize.y) * 2.0;
  float r = length(uv);
  float ang = atan(uv.y, uv.x);

  float breathe = 0.5 + 0.5 * (sin(uTime * 0.23) * 0.56 + sin(uTime * 0.15 + 1.4) * 0.44);
  float R = uRadius * (1.0 + breathe * 0.024 * (0.5 + uEnergy));
  float t = uTime;

  vec3 col = vec3(0.0);

  // Visible wind: the same field drawn as faint streaks, so the petals are
  // clearly riding something rather than wandering.
  {
    vec2 w = windAt(uv, t, R, uTurb, uFocus);
    vec2 wd = normalize(w + 1e-5);
    float streak = smearRidge(uv * 2.6 + vec2(-t * 0.22, t * 0.08), wd, 0.11, 4);
    col += lavenderRamp(0.30 + streak * 0.34) * pow(streak, 2.2)
         * (0.05 + uFlare * 0.34) * smoothstep(R * 0.9, R * 1.6, r);
  }

  vec4 back = vec4(0.0); vec4 front = vec4(0.0);
  float zb = -1.0, zf = -1.0;

  int count = int(12.0 + uEmber * 24.0);
  for (int i = 0; i < 36; i++) {
    if (i >= count) break;
    float fi = float(i);
    vec2 h1 = hash22(vec2(fi, 5.0));
    vec2 h2 = hash22(vec2(fi, 6.0));

    float period = 9.0 + h1.x * 9.0;
    float ph = fract(t / period + h1.y);
    float life = smoothstep(0.0, 0.10, ph) * (1.0 - smoothstep(0.84, 1.0, ph));
    if (life < 0.02) continue;
    float depth = h2.x;

    // Launch point on a wide entry arc upwind, then integrate the wind with a
    // few Euler steps. Four steps is enough for the path to visibly curve
    // around the orb, which is the whole point of the direction.
    float a0 = (h1.y * 0.9 - 0.45) + PI;
    vec2 c = vec2(cos(a0), sin(a0)) * (1.55 + h2.y * 0.55);
    float travel = ph * (1.5 + uEnergy * 1.4);
    for (int s = 0; s < 4; s++) {
      c += windAt(c, t, R, uTurb, uFocus) * (travel * 0.25);
    }

    float size = R * (0.14 + 0.17 * depth) * (0.80 + 0.40 * h1.y);
    vec2 wv = windAt(c, t, R, uTurb, uFocus);
    // Petals align with the flow and tumble about that axis.
    float rot = atan(wv.y, wv.x) + PI * 0.5
              + sin(t * (0.7 + h1.y) + fi) * (0.35 + uTurb * 0.6);
    float tilt = cos(t * (0.9 + h2.x * 1.8) + fi * 1.91);

    vec3 sh = petalAt(uv, c, size, rot, tilt);
    if (sh.x <= 0.0) continue;

    float lit = exp(-max(length(c) - R, 0.0) * 1.25);
    float tone = clamp(0.54 + 0.32 * lit - 0.20 * sh.y - 0.09 * sh.z
                       + 0.12 * (1.0 - abs(tilt)), 0.0, 1.0);
    vec3 pc = sakuraRamp(tone) * (0.40 + 1.00 * lit + 0.40 * depth) * life;
    if (depth < 0.5) { if (depth > zb) { back = vec4(pc, sh.x * life); zb = depth; } }
    else            { if (depth > zf) { front = vec4(pc, sh.x * life); zf = depth; } }
  }
  col = mix(col, back.rgb, clamp(back.a, 0.0, 1.0));

  // ---- core: a lantern, not a sun ---------------------------------------
  if (r < R * 1.12) {
    float rn = clamp(r / R, 0.0, 1.0);
    float mu = sqrt(max(0.0, 1.0 - rn * rn));
    vec2 sp = uv / max(0.66 + 0.34 * mu, 0.42);
    float veil = warpFbm(sp * 2.8 + vec2(-t * 0.06, t * 0.04), t * 0.4, 1.7);
    float tone = clamp(0.48 + 0.26 * (1.0 - rn) + veil * 0.13, 0.0, 1.0);
    float bright = (0.34 + 0.40 * pow(1.0 - rn, 2.0)) * limbDarken(mu);
    float edge = 1.0 - smoothstep(R * 0.95, R * 1.05, r);
    col += sakuraRamp(tone) * bright * edge * (0.80 + uEnergy * 0.60);
    col += sakuraRamp(0.92) * pow(max(0.0, 1.0 - rn * 2.8), 2.2) * edge
         * (0.22 + uEnergy * 0.26);
    col += sakuraRamp(0.70) * exp(-max(r - R, 0.0) * 6.0) * (0.09 + uEnergy * 0.15);
  }

  col = mix(col, front.rgb, clamp(front.a, 0.0, 1.0));

  vec2 m = driftMotes(uv, t, 0.20 + uEmber * 0.24, 3, 31.0, R, 1.1, 6.2);
  col += sakuraRamp(0.56) * m.x * 0.50 + sakuraRamp(0.95) * m.y * 0.70;

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;

// --------------------------------------------------------------------------
// C - Blossom Heart.
// The core itself is a blossom: five layered petal rings seen face-on, each
// rotating at its own rate, with light passing through them. The orbiting
// petals are its corona rather than the main event.
// --------------------------------------------------------------------------
export const SAKURA_C = `
void main() {
  vec2 fc = gl_FragCoord.xy;
  vec2 uv = (fc - 0.5 * uSize) / min(uSize.x, uSize.y) * 2.0;
  float r = length(uv);
  float ang = atan(uv.y, uv.x);

  float breathe = 0.5 + 0.5 * (sin(uTime * 0.25) * 0.58 + sin(uTime * 0.16 + 2.4) * 0.42);
  float R = uRadius * (1.0 + breathe * 0.030 * (0.5 + uEnergy));
  float t = uTime;

  vec3 col = vec3(0.0);

  // ---- halo of orbiting petals (drawn behind the blossom) ----------------
  vec4 back = vec4(0.0); vec4 front = vec4(0.0);
  float zb = -1.0, zf = -1.0;
  int count = int(10.0 + uEmber * 18.0);
  for (int i = 0; i < 28; i++) {
    if (i >= count) break;
    float fi = float(i);
    vec2 h1 = hash22(vec2(fi, 9.0));
    vec2 h2 = hash22(vec2(fi, 10.0));
    float period = 15.0 + h1.x * 15.0;
    float ph = fract(t / period + h1.y);
    float life = smoothstep(0.0, 0.14, ph) * (1.0 - smoothstep(0.78, 1.0, ph));
    if (life < 0.02) continue;
    float depth = h2.x;
    float rad = R * (1.35 + h1.x * 1.6) * (1.0 + 0.22 * sin(t * 0.3 + fi));
    float a0 = h2.y * TAU + t * (0.10 + 0.22 * uEnergy) * (0.6 + depth * 0.7)
             * (h1.y > 0.5 ? 1.0 : -0.75);
    vec2 c = vec2(cos(a0), sin(a0)) * rad;
    c += curl(c * 1.5 + fi * 2.7, t * 0.18) * (0.030 + uTurb * 0.080);
    float size = R * (0.13 + 0.15 * depth) * (0.8 + 0.4 * h1.y);
    float rot = a0 + sin(t * (0.3 + h1.y * 0.5) + fi) * 0.7;
    float tilt = cos(t * (0.45 + h2.x * 1.1) + fi * 3.11);
    vec3 sh = petalAt(uv, c, size, rot, tilt);
    if (sh.x <= 0.0) continue;
    float lit = exp(-max(length(c) - R, 0.0) * 1.35);
    float tone = clamp(0.55 + 0.30 * lit - 0.20 * sh.y - 0.08 * sh.z, 0.0, 1.0);
    vec3 pc = sakuraRamp(tone) * (0.40 + 0.95 * lit + 0.40 * depth) * life;
    if (depth < 0.5) { if (depth > zb) { back = vec4(pc, sh.x * life); zb = depth; } }
    else            { if (depth > zf) { front = vec4(pc, sh.x * life); zf = depth; } }
  }
  col = mix(col, back.rgb, clamp(back.a, 0.0, 1.0));

  // ---- the blossom core: four nested rings of five petals ----------------
  // Each ring is offset half a petal from the one beneath, counter-rotates,
  // and is lit from the centre, so the stack reads as depth and not as a
  // flat rosette.
  {
    vec2 drift = curl(uv * 1.1, t * 0.25) * 0.030;
    vec2 q = uv + drift * (0.4 + uTurb);
    for (int ring = 3; ring >= 0; ring--) {
      float fr = float(ring);
      float scale = 1.00 - fr * 0.195;
      float spin = t * (0.055 + 0.055 * uEnergy) * (fr == 1.0 || fr == 3.0 ? -1.0 : 1.0)
                 + fr * 0.62;
      float lift = 0.26 + fr * 0.11;          // how far the ring opens out
      for (int k = 0; k < 5; k++) {
        float a = float(k) * (TAU / 5.0) + spin;
        float wob = (unoise(vec2(fr * 3.1 + float(k), t * 0.35)) - 0.5)
                  * (0.10 + uTurb * 0.22);
        vec2 c = vec2(cos(a + wob), sin(a + wob)) * R * lift;
        float size = R * 0.80 * scale;
        // Petals point outward from the centre.
        vec3 sh = petalAt(q, c, size, a + wob + PI * 0.5, 1.0);
        if (sh.x <= 0.0) continue;
        float rr = length(q - c);
        // Light leaks from the middle of the blossom outward through the
        // tissue; the rim stays deeper and more saturated.
        float thru = exp(-length(c + normalize(c + 1e-5) * size * 0.5) * 1.9);
        float tone = clamp(0.62 + 0.26 * thru - 0.26 * sh.y - 0.10 * sh.z
                           - fr * 0.045, 0.0, 1.0);
        vec3 pc = sakuraRamp(tone)
                * (0.55 + 0.80 * thru) * (1.0 - fr * 0.13)
                * (0.80 + uEnergy * 0.55);
        col = mix(col, pc, sh.x);
      }
    }
    // Stamen cluster: a tight knot of pollen light at the very centre.
    float rn = r / R;
    float stam = exp(-rn * rn * 46.0);
    float grain = 0.45 + 0.55 * unoise(uv * 44.0 + vec2(t * 0.6, -t * 0.4));
    col += sakuraRamp(0.97) * stam * grain * (0.55 + uEnergy * 0.55);
    col += lavenderRamp(0.70) * exp(-rn * rn * 7.0) * (0.10 + uEnergy * 0.20);
  }

  // ---- ribbons, drawn outside the blossom --------------------------------
  for (int k = 0; k < 2; k++) {
    float fk = float(k);
    float rr = R * (1.22 + fk * 0.52)
             + R * 0.26 * sin(ang * (3.0 - fk) + t * (0.24 + fk * 0.1));
    float d = abs(r - rr);
    float w = R * (0.075 + 0.035 * fk);
    float g = exp(-(d * d) / (w * w));
    float flow = 0.35 + 0.65 * unoise(vec2(ang * 4.4 - t * 0.9, fk * 7.0));
    col += lavenderRamp(0.44 + 0.42 * flow) * g * flow * (0.06 + uFlare * 0.70);
  }

  col = mix(col, front.rgb, clamp(front.a, 0.0, 1.0));

  vec2 m = driftMotes(uv, t, 0.24 + uEmber * 0.26, 3, 41.0, R, 0.8, 7.6);
  col += sakuraRamp(0.58) * m.x * 0.52 + sakuraRamp(0.96) * m.y * 0.78;

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;
