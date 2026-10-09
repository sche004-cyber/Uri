// Shared GLSL additions for the Sakura and Lunar companions.
//
// Appended after the solar LIB, so everything there (hashes, gradient noise,
// fbm, ridged, worley, warpFbm, curl, smearRidge, aces, dither, angNoise) is
// already in scope.

export const EXTRA = `
// ---------------------------------------------------------------------------
// Palettes.
// Same anti-mud rule as the fire ramp: as a colour darkens it must get MORE
// saturated, not greyer. A pink lerped toward neutral dark reads as dirty
// mauve, which is the pink equivalent of muddy brown.
// ---------------------------------------------------------------------------
vec3 sakuraRamp(float t) {
  t = clamp(t, 0.0, 1.0);
  const vec3 c0 = vec3(0.070, 0.016, 0.052); // deep plum
  const vec3 c1 = vec3(0.340, 0.055, 0.180); // plum / wine
  const vec3 c2 = vec3(0.780, 0.200, 0.400); // rose
  const vec3 c3 = vec3(1.000, 0.470, 0.650); // sakura pink
  const vec3 c4 = vec3(1.000, 0.760, 0.845); // pale blossom
  const vec3 c5 = vec3(1.000, 0.955, 0.975); // pearl white
  vec3 c = mix(c0, c1, smoothstep(0.00, 0.22, t));
  c = mix(c, c2, smoothstep(0.18, 0.44, t));
  c = mix(c, c3, smoothstep(0.40, 0.64, t));
  c = mix(c, c4, smoothstep(0.60, 0.82, t));
  c = mix(c, c5, smoothstep(0.80, 1.00, t));
  return c;
}

// Lavender arm of the same palette, for the energy ribbons. Keeping it a
// separate ramp rather than a hue shift stops the ribbons from going grey
// where they cross the pink.
vec3 lavenderRamp(float t) {
  t = clamp(t, 0.0, 1.0);
  const vec3 c0 = vec3(0.045, 0.028, 0.085);
  const vec3 c1 = vec3(0.230, 0.120, 0.380);
  const vec3 c2 = vec3(0.520, 0.330, 0.760);
  const vec3 c3 = vec3(0.780, 0.620, 0.960);
  const vec3 c4 = vec3(0.930, 0.870, 1.000);
  vec3 c = mix(c0, c1, smoothstep(0.00, 0.26, t));
  c = mix(c, c2, smoothstep(0.22, 0.52, t));
  c = mix(c, c3, smoothstep(0.48, 0.78, t));
  c = mix(c, c4, smoothstep(0.74, 1.00, t));
  return c;
}

vec3 lunarRamp(float t) {
  t = clamp(t, 0.0, 1.0);
  const vec3 c0 = vec3(0.010, 0.013, 0.030); // near-black
  const vec3 c1 = vec3(0.042, 0.058, 0.125); // midnight navy
  const vec3 c2 = vec3(0.115, 0.140, 0.265); // deep indigo
  const vec3 c3 = vec3(0.305, 0.345, 0.500); // muted blue-grey
  const vec3 c4 = vec3(0.660, 0.715, 0.830); // moonlight silver
  const vec3 c5 = vec3(0.960, 0.975, 1.000); // pearl white
  vec3 c = mix(c0, c1, smoothstep(0.00, 0.24, t));
  c = mix(c, c2, smoothstep(0.20, 0.46, t));
  c = mix(c, c3, smoothstep(0.42, 0.66, t));
  c = mix(c, c4, smoothstep(0.62, 0.84, t));
  c = mix(c, c5, smoothstep(0.80, 1.00, t));
  return c;
}

// ---------------------------------------------------------------------------
// Cherry-blossom petal.
//
// Local space: base at (0,0), outer end at (0,1), long axis +Y.
// A sakura petal is narrow at the base, broadest near the outer end, and
// notched there. The notch is the whole identity of the shape: without it the
// silhouette is a generic leaf, and at companion size it degenerates into the
// "pink glowing dot" the brief rules out.
// Returns (mask, rim, vein).
// ---------------------------------------------------------------------------
vec3 petalShape(vec2 p) {
  if (p.y < -0.10 || p.y > 1.12 || abs(p.x) > 0.62) return vec3(0.0);
  float yc = clamp(p.y, 0.0, 1.0);
  float ax = abs(p.x);

  // Half-width: sqrt flare from the base, easing back just before the tip.
  float hw = 0.44 * sqrt(yc) * (1.0 - 0.42 * smoothstep(0.80, 1.06, yc));

  // The notch. Depth is largest on the centre line and gone by ax = 0.13,
  // which at this width leaves two clear lobes.
  float top = 1.0 - 0.17 * (1.0 - smoothstep(0.0, 0.13, ax));

  float m = smoothstep(hw + 0.030, hw - 0.022, ax)
          * smoothstep(top + 0.050, top - 0.018, p.y)
          * smoothstep(-0.060, 0.030, p.y);
  if (m <= 0.0) return vec3(0.0);

  // Rim: the outer few percent of the width, where a real petal is thinner
  // and more saturated.
  float rim = smoothstep(hw - 0.15, hw - 0.01, ax);
  // Veins fan from the base toward the tip.
  float fan = ax / max(hw, 1e-3);
  float vein = smoothstep(0.62, 0.98, abs(sin(fan * 7.5)))
             * smoothstep(0.12, 0.55, yc) * (1.0 - rim);
  return vec3(m, rim, vein);
}

// One petal placed in the view.
//   c      centre of the petal's base, in uv space
//   size   petal length in uv units
//   rot    in-plane rotation
//   tilt   -1..1, the cosine of the roll about the petal's long axis.
//          |tilt| near 0 is edge-on: the petal narrows to a lit sliver, which
//          is what sells three-dimensional tumbling without any geometry.
// Returns (mask, rim, vein) already shaped by the tilt.
vec3 petalAt(vec2 uv, vec2 c, float size, float rot, float tilt) {
  vec2 d = uv - c;
  if (dot(d, d) > size * size * 1.8) return vec3(0.0);
  float s = sin(rot), co = cos(rot);
  vec2 l = vec2(co * d.x + s * d.y, -s * d.x + co * d.y) / max(size, 1e-5);
  // Shift so the petal straddles its centre rather than hanging off the base.
  l.y += 0.5;
  l.x /= max(abs(tilt), 0.10);
  vec3 sh = petalShape(l);
  // Edge-on petals catch the light: narrow, but brighter per pixel.
  sh.x *= mix(1.0, 1.45, 1.0 - abs(tilt));
  return sh;
}

// ---------------------------------------------------------------------------
// Palette-agnostic drifting motes: pollen for Sakura, dust and mist sparkle
// for Lunar. Same analytic grid as the solar ember field, but it returns an
// intensity and a 0..1 "warmth" instead of a colour, so each companion feeds
// its own ramp. No CPU particles and no overdraw.
// Returns (intensity, warmth).
// ---------------------------------------------------------------------------
vec2 driftMotes(vec2 uv, float t, float density, int layers, float seed,
                float orbR, float rise, float cell, float sizeMul) {
  vec2 acc = vec2(0.0);
  for (int L = 0; L < 3; L++) {
    if (L >= layers) break;
    float fl = float(L);
    float depth = 0.55 + fl * 0.42;          // parallax: far layers move less
    float sc = cell * depth;
    float speed = (0.030 + fl * 0.016) * rise;
    vec2 p = uv * sc + vec2(seed * (fl + 1.3), 0.0);
    vec2 ip = floor(p);
    vec2 fp = fract(p);
    for (int j = -1; j <= 1; j++) {
      for (int i = -1; i <= 1; i++) {
        vec2 g = vec2(float(i), float(j));
        vec2 id = ip + g;
        vec2 h = hash22(id + fl * 19.7);
        if (h.x > density) continue;
        float life = fract(h.x * 3.3 + t * speed * (0.6 + h.y));
        // Fade in and out so nothing pops.
        float env = pow(sin(life * PI), 1.35);
        if (env < 0.01) continue;
        // Two incommensurate waver frequencies: a single sine reads mechanical.
        float wx = sin(t * (0.37 + h.y * 0.51) + h.x * TAU) * 0.26
                 + sin(t * (0.19 + h.x * 0.23) + h.y * TAU) * 0.15;
        vec2 o = vec2(h.y + wx * 0.30, 1.0 - life);
        vec2 d = g + o - fp;
        // Motion blur: squash along the travel axis.
        d.y *= 0.62;
        float rad = (0.0075 + h.y * 0.0125) * sc * sizeMul;
        float q = length(d) / max(rad, 1e-4);
        float flick = 0.70 + 0.30 * sin(t * (2.1 + h.x * 3.7) + h.y * 11.0);
        float v = exp(-q * q) * env * flick / depth;
        // Cool as they travel: the detail most fake particle fields miss.
        acc += vec2(v, v * (0.34 + h.y * 0.42) * (1.0 - life * 0.42));
      }
    }
  }
  // Suppress inside the orb body and thin out far away.
  float rr = length(uv);
  acc *= smoothstep(orbR * 0.92, orbR * 1.22, rr);
  acc *= mix(1.0, 0.30, smoothstep(orbR * 2.2, 1.45, rr));
  return acc;
}

// ---------------------------------------------------------------------------
// Sakura energy core.
//
// The first pass drew a smooth radial gradient inside a hard circle, which is
// the recipe for a pink billiard ball: a specular-looking highlight, a solid
// silhouette, no life. Two things fix it, and both matter. The boundary is
// broken by angular noise and faded over a wide band instead of cut, and the
// internal structure is given more of the tonal range than the radial gradient
// is, so the interior reads as moving light rather than as shading on a solid.
// ---------------------------------------------------------------------------
vec3 sakuraCore(vec2 uv, float r, float ang, float R, float t,
                float energy, float turb) {
  float wob  = angNoise(ang, 2.1, t * 0.07) - 0.5;
  float wob2 = angNoise(ang, 4.7, t * 0.11) - 0.5;
  float Re = R * (1.0 + wob * 0.24 + wob2 * 0.11 * (0.5 + turb));
  if (r > Re * 2.0) return vec3(0.0);

  float rn = clamp(r / Re, 0.0, 1.4);
  float mu = sqrt(max(0.0, 1.0 - min(rn, 1.0) * min(rn, 1.0)));
  vec2 sp = uv / max(0.60 + 0.40 * mu, 0.40);
  vec2 drift = curl(sp * 1.5, t * 0.30) * 0.075;

  float swirl = warpFbm(sp * 3.0 + drift * 3.0 + vec2(-t * 0.09, t * 0.06), t * 0.55, 2.4);
  vec2 tang = r > 1e-4 ? vec2(-uv.y, uv.x) / r : vec2(1.0, 0.0);
  vec2 flowDir = normalize(tang * 0.85 + curl(sp * 1.1, t * 0.22) * 0.55 + 1e-5);
  float fil   = smearRidge(sp * 5.0 + drift * 4.0 + vec2(-t * 0.16, t * 0.11),
                           flowDir, 0.095, 4);
  float fine  = ridged(sp * 11.0 + drift * 8.0 + vec2(t * 0.24, -t * 0.18), 3);

  float tone = clamp(0.53 + 0.19 * (1.0 - rn * rn)
                   + swirl * 0.20 + (fil - 0.40) * 0.15 + (fine - 0.40) * 0.06,
                     0.0, 1.0);

  float body = smoothstep(1.16, 0.74, rn);
  float bright = (0.34 + 0.34 * pow(max(0.0, 1.0 - rn), 1.5))
               * (0.72 + 0.46 * (swirl * 0.5 + 0.5))
               * (0.84 + 0.32 * fil);

  vec3 c = sakuraRamp(tone) * bright * body * (0.80 + energy * 0.60);

  // Heart: textured, never a smooth white disc.
  float heart = pow(max(0.0, 1.0 - rn * 2.9), 2.3);
  float hTex = 0.40 + 0.60 * (swirl * 0.5 + 0.5) * (0.5 + 0.5 * fine);
  c += sakuraRamp(0.93) * heart * hTex * (0.26 + energy * 0.30);

  // Filament crests reaching past the body, so the edge is made of light
  // rather than drawn as an outline.
  float crest = smoothstep(0.46, 0.86, fil) * smoothstep(1.55, 0.70, rn);
  c += sakuraRamp(0.86) * crest * (0.18 + energy * 0.55);

  // Restrained halo. Bloom is the fastest way to lose the petals.
  c += sakuraRamp(0.62) * exp(-max(r - Re, 0.0) * 6.8) * (0.06 + energy * 0.12);
  return c;
}

// Per-particle waver: two incommensurate sine pairs, used where a curl()
// lookup would be correct but is far too expensive to run once per particle
// per fragment. The periods are mutually irrational so the pair never repeats.
vec2 waver(float seed, float t, float amp) {
  return vec2(sin(t * (0.31 + seed * 0.017) + seed * 1.7)
            + 0.55 * sin(t * (0.73 + seed * 0.011) + seed * 4.1),
              cos(t * (0.27 + seed * 0.013) + seed * 2.9)
            + 0.55 * cos(t * (0.61 + seed * 0.019) + seed * 5.3)) * amp;
}

// Energy ribbon: thin, broken, mostly pearl. The first pass drew fat
// continuous bands of saturated violet, which read as plastic hoops.
vec3 ribbon(float r, float ang, float R, float t, float k, float amt) {
  float rr = R * (1.10 + k * 0.38)
           + R * 0.22 * sin(ang * (2.0 + k) + t * (0.28 + k * 0.09))
           + R * 0.10 * sin(ang * (5.0 - k) - t * (0.21 + k * 0.07));
  float ns = (unoise(vec2(ang * 2.4 + k * 5.0, t * 0.20)) - 0.5) * R * 0.16;
  float d = abs(r - rr - ns);
  float w = R * (0.022 + 0.010 * k);
  float g  = exp(-(d * d) / (w * w));
  float gh = exp(-(d * d) / (w * w * 9.0)) * 0.30;
  // Travelling gaps. A continuous band has no direction and no life.
  float seg  = smoothstep(0.34, 0.80, unoise(vec2(ang * 3.4 - t * 0.55, k * 7.0)));
  float flow = 0.30 + 0.70 * unoise(vec2(ang * 9.0 - t * 1.4, k * 3.0));
  vec3 c = lavenderRamp(0.55 + 0.40 * flow) * g * flow;
  c += lavenderRamp(0.95) * g * smoothstep(0.72, 1.0, flow) * 0.80;
  c += lavenderRamp(0.36) * gh * 0.50;
  return c * seg * amt;
}

// ---------------------------------------------------------------------------
// Night-sky helpers for the Lunar companion.
// ---------------------------------------------------------------------------

// Sparse stars with per-star twinkle. Grid-hashed, one candidate per cell.
float starField(vec2 p, float t, float density) {
  vec2 ip = floor(p), fp = fract(p);
  float h = hash12(ip);
  if (h > density) return 0.0;
  vec2 o = hash22(ip + 3.7);
  float d = length(fp - o);
  float mag = 0.35 + 0.65 * hash12(ip + 9.1);
  float tw = 0.55 + 0.45 * sin(t * (0.7 + hash12(ip + 1.3) * 2.1) + h * TAU);
  float core = exp(-d * d * 2400.0 / (mag * mag));
  float bloom = exp(-d * d * 190.0) * 0.16;
  return (core + bloom) * mag * tw;
}

// Sparse craters. Deriving them from the cellular F1 distance put a crater in
// every cell at the same size, which read as foam or bubble wrap rather than
// as a lunar surface. Hashing the cell and rejecting most of them gives the
// uneven distribution and the range of sizes that a real surface has.
float craters(vec2 q, float sc, float density, float seed) {
  vec2 p = q * sc;
  vec2 ip = floor(p), fp = fract(p);
  float acc = 0.0;
  for (int j = -1; j <= 1; j++) {
    for (int i = -1; i <= 1; i++) {
      vec2 g = vec2(float(i), float(j));
      vec2 h = hash22(ip + g + seed);
      if (h.x > density) continue;
      float rad = 0.15 + h.y * 0.28;
      vec2 o = hash22(ip + g + seed + 5.1);
      float d = length(g + o - fp);
      float k = d / max(rad, 1e-4);
      if (k > 1.30) continue;
      // Bright rim, darker floor: a ring, not a disc.
      float rim  = exp(-pow((k - 0.86) * 5.2, 2.0)) * (0.45 + h.y * 0.65);
      float bowl = smoothstep(0.86, 0.14, k) * (0.35 + h.x * 0.55);
      acc += rim * 0.30 - bowl * 0.24;
    }
  }
  return acc;
}

// Lunar surface albedo: large dark maria, highland mottling, sparse craters.
// The maria carry the recognition - a disc with only craters on it reads as an
// asteroid, not as the moon.
float moonAlbedo(vec2 q) {
  float mn = fbm5(q * 1.10 + 4.2);
  float maria = smoothstep(0.14, -0.12, mn);
  float base = mix(1.00, 0.44, maria);
  base *= 0.90 + 0.20 * (fbm3(q * 3.2 - 2.0) * 0.5 + 0.5);

  float cr = craters(q, 3.2, 0.42, 0.0) * 1.00
           + craters(q, 7.5, 0.34, 31.0) * 0.62
           + craters(q, 17.0, 0.26, 77.0) * 0.34;
  // Fine regolith grain, so the disc is never a flat fill.
  float grain = (unoise(q * 30.0) - 0.5) * 0.055;
  return clamp(base + cr + grain, 0.05, 1.30);
}

// A cloud slab: density plus the light reaching it from the moon.
//   p        sample point in uv space
//   toLight  unit vector from p toward the moon centre
// Returns (density, transmittance toward the moon).
// The cover parameter is 0..1; 0 leaves wide gaps of clear sky, 1 is overcast. The first
// pass used a low threshold that made the field non-zero almost everywhere, so
// every frame was overcast no matter what cover said.
vec2 cloudSlab(vec2 p, float t, float scale, float drift, float cover,
               vec2 toLight) {
  float lo = 0.70 - cover * 0.38;
  float hi = 1.04 - cover * 0.30;
  vec2 q = p * scale + vec2(t * drift, t * drift * 0.17);
  float d = smoothstep(lo, hi, warpFbm(q, t * 0.35, 1.8) + 0.5);
  // March three short steps toward the light; cheap, and enough to give the
  // silver edge that only appears where the cloud is thin on the lit side.
  float occ = 0.0;
  for (int i = 1; i <= 3; i++) {
    vec2 s = (p + toLight * (0.045 * float(i))) * scale
           + vec2(t * drift, t * drift * 0.17);
    occ += smoothstep(lo, hi, warpFbm(s, t * 0.35, 1.8) + 0.5);
  }
  return vec2(d, exp(-occ * 1.15));
}
`;
