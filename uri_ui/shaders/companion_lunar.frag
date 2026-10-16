#version 460 core
#include <flutter/runtime_effect.glsl>

// URI Lunar Intelligence - GENERATED from rnd/companions/lunar.js LUNAR_C.
// DO NOT EDIT BY HAND: run `node rnd/companions/export_flutter.mjs`.
//
// Uniform order must match lib/living/companion/companion_orb.dart exactly:
//   0,1 uSize  2 uTime  3 uEnergy  4 uTurb  5 uFlare
//   6   uEmber 7 uFocus 8 uRadius  9 uExposure
//
// How this companion reads the expression uniforms:
//   uEnergy  cloud speed and luminance
//   uTurb    cloud turbulence
//   uFlare   halo and shaft strength
//   uEmber   star and mist density
//   uFocus   how far the clouds part (low obscures the moon)

uniform vec2  uSize;
uniform float uTime;
uniform float uEnergy;
uniform float uTurb;
uniform float uFlare;
uniform float uEmber;
uniform float uFocus;
uniform float uRadius;
uniform float uExposure;

out vec4 fragColor;

#define PI 3.14159265359
#define TAU 6.28318530718

// Dave Hoskins style hashes - far better distribution than sin(dot()).
float hash12(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}
vec2 hash22(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.xx + p3.yz) * p3.zy);
}

// Gradient noise (quintic interpolant). Returns roughly [-0.7, 0.7].
// Gradient noise keeps high-frequency detail that value noise smears away;
// value noise is the main reason the previous orb read as blurry fog.
float gnoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
  vec2 ga = normalize(hash22(i + vec2(0.0, 0.0)) * 2.0 - 1.0);
  vec2 gb = normalize(hash22(i + vec2(1.0, 0.0)) * 2.0 - 1.0);
  vec2 gc = normalize(hash22(i + vec2(0.0, 1.0)) * 2.0 - 1.0);
  vec2 gd = normalize(hash22(i + vec2(1.0, 1.0)) * 2.0 - 1.0);
  float va = dot(ga, f - vec2(0.0, 0.0));
  float vb = dot(gb, f - vec2(1.0, 0.0));
  float vc = dot(gc, f - vec2(0.0, 1.0));
  float vd = dot(gd, f - vec2(1.0, 1.0));
  return mix(mix(va, vb, u.x), mix(vc, vd, u.x), u.y);
}

float unoise(vec2 p) { return gnoise(p) * 0.5 + 0.5; }

const mat2 ROT = mat2(0.80, 0.60, -0.60, 0.80);

float fbm3(vec2 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 3; i++) { v += a * gnoise(p); p = ROT * p * 2.07 + 1.3; a *= 0.5; }
  return v;
}
float fbm5(vec2 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 5; i++) { v += a * gnoise(p); p = ROT * p * 2.03 + 1.7; a *= 0.5; }
  return v;
}

// Ridged fbm - sharp creases that read as filaments rather than clouds.
float ridged(vec2 p, int oct) {
  float v = 0.0, a = 0.5, prev = 1.0;
  for (int i = 0; i < 6; i++) {
    if (i >= oct) break;
    float n = 1.0 - abs(gnoise(p));
    n *= n;
    v += a * n * prev;
    prev = n;
    p = ROT * p * 2.11 + 2.3;
    a *= 0.5;
  }
  return v;
}

// Worley / cellular F1,F2. Real photospheric granulation is bright convection
// cells separated by dark intergranular lanes - a cellular function, not noise.
// Ridged noise in a radially stretched space (the v2 attempt) produced radial
// pinstripes that read as a cheap lens flare.
vec2 worley(vec2 p) {
  vec2 ip = floor(p), fp = fract(p);
  float f1 = 9.0, f2 = 9.0;
  for (int j = -1; j <= 1; j++) {
    for (int i = -1; i <= 1; i++) {
      vec2 g = vec2(float(i), float(j));
      vec2 o = hash22(ip + g);
      vec2 d = g + o - fp;
      float dd = dot(d, d);
      if (dd < f1) { f2 = f1; f1 = dd; }
      else if (dd < f2) { f2 = dd; }
    }
  }
  return vec2(sqrt(f1), sqrt(f2));
}

// Bright cell interiors, dark lanes at the cell boundaries.
float granules(vec2 p, float lane) {
  vec2 w = worley(p);
  return smoothstep(0.015, lane, w.y - w.x);
}

// Inigo Quilez style domain warp: noise that reads as moving fluid rather than
// a scrolling texture.
float warpFbm(vec2 p, float t, float amt) {
  vec2 q = vec2(fbm3(p + vec2(0.0, 0.0) + t * 0.11),
                fbm3(p + vec2(5.2, 1.3) - t * 0.09));
  vec2 r = vec2(fbm3(p + amt * q + vec2(1.7, 9.2) + t * 0.15),
                fbm3(p + amt * q + vec2(8.3, 2.8) - t * 0.13));
  return fbm5(p + amt * r);
}

// Divergence-free curl of an fbm potential: genuine fluid rotation.
vec2 curl(vec2 p, float t) {
  const float e = 0.035;
  float n1 = fbm3(p + vec2(0.0, e) + t * 0.08);
  float n2 = fbm3(p - vec2(0.0, e) + t * 0.08);
  float n3 = fbm3(p + vec2(e, 0.0) + t * 0.08);
  float n4 = fbm3(p - vec2(e, 0.0) + t * 0.08);
  return vec2(n1 - n2, -(n3 - n4)) / (2.0 * e);
}

// Directional smear along dir: taps max-combined. Cheap anisotropy that
// elongates structures radially so they read as tongues, not blobs.
float smearRidge(vec2 p, vec2 dir, float len, int oct) {
  float s = ridged(p, oct);
  s = max(s, ridged(p - dir * len, oct) * 0.90);
  s = max(s, ridged(p - dir * len * 2.0, oct) * 0.78);
  s = max(s, ridged(p - dir * len * 3.0, oct) * 0.62);
  return s;
}

// ---------------------------------------------------------------------------
// Fire palette. Deliberately piecewise, not a two-colour lerp.
// Anti-mud rule: as brightness falls, saturation RISES toward red. Mixing
// orange toward a desaturated dark is exactly what produces muddy brown.
// ---------------------------------------------------------------------------
vec3 fireRamp(float t) {
  t = clamp(t, 0.0, 1.0);
  const vec3 c0 = vec3(0.090, 0.005, 0.001); // near-black ember
  const vec3 c1 = vec3(0.520, 0.055, 0.004); // deep red
  const vec3 c2 = vec3(0.960, 0.260, 0.020); // bright orange
  const vec3 c3 = vec3(1.000, 0.580, 0.110); // amber
  const vec3 c4 = vec3(1.000, 0.840, 0.420); // golden yellow
  const vec3 c5 = vec3(1.000, 0.975, 0.880); // white hot
  vec3 c = mix(c0, c1, smoothstep(0.00, 0.22, t));
  c = mix(c, c2, smoothstep(0.18, 0.44, t));
  c = mix(c, c3, smoothstep(0.40, 0.64, t));
  c = mix(c, c4, smoothstep(0.60, 0.82, t));
  c = mix(c, c5, smoothstep(0.80, 1.00, t));
  return c;
}

// ACES filmic approximation. Lets the core run above 1.0 and roll off to white
// instead of clipping flat: the biggest single lever between premium and cheap.
vec3 aces(vec3 x) {
  const float a = 2.51, b = 0.03, c = 2.43, d = 0.59, e = 0.14;
  return clamp((x * (a * x + b)) / (x * (c * x + d) + e), 0.0, 1.0);
}

float dither(vec2 fc) { return (hash12(fc) - 0.5) * (1.0 / 255.0); }

// Limb darkening for a stellar disc. mu = cos(angle from view normal).
float limbDarken(float mu) { return 0.34 + 0.66 * pow(max(mu, 0.0), 0.62); }

// Noise that is seamless around the orb: sampled on a circle in noise space,
// so there is no visible join at angle = PI.
float angNoise(float ang, float radius, float t) {
  return unoise(vec2(cos(ang), sin(ang)) * radius + vec2(t, -t * 0.7));
}

// ---------------------------------------------------------------------------
// Corona: a few fat, curved streamers. Hundreds of thin uniform rays read as a
// dandelion or a lens flare; a smooth radial gradient reads as excess bloom.
// ---------------------------------------------------------------------------
vec3 coronaLayer(vec2 uv, float r, vec2 dir, float ang, float R,
                 float t, float energy) {
  float h = max(r - R, 0.0);

  // Low-frequency angular mask: a handful of lobes, drifting slowly.
  float clump = smoothstep(0.26, 0.92, angNoise(ang, 1.15, t * 0.030));
  float lenMod = 0.30 + 1.25 * clump;
  float fall = exp(-h * (6.6 - energy * 2.2) / max(lenMod, 0.18));

  // Bend the lookup with the curl field so rays curve instead of radiating
  // dead straight out of the centre.
  vec2 bend = curl(uv * 1.1 + 13.0, t * 0.5) * 0.050;
  vec2 cp = (uv + bend) * 2.4 - vec2(0.0, t * 0.16);
  float ray = pow(smearRidge(cp, dir, 0.26, 4), 2.1);

  float amt = fall * (0.07 + ray * 1.15 * (0.35 + clump)) * (0.45 + energy * 0.90);
  vec3 col = fireRamp(0.38 + ray * 0.34) * amt;

  // Chromosphere: a soft, angularly broken limb brightening. A tight even rim
  // traces a circle outline and makes the orb look like a sticker.
  float rimN = 0.30 + 0.70 * angNoise(ang, 3.6, t * 0.09);
  col += fireRamp(0.82) * exp(-abs(r - R) * 46.0) * rimN * (0.26 + energy * 0.34);

  // The orb lights the space around it: very low level, long falloff.
  col += fireRamp(0.26) * exp(-h * 1.3) * 0.030 * (0.5 + energy);
  return col;
}

// ---------------------------------------------------------------------------
// Ember field. Analytic, in-shader, no CPU particle system and no overdraw.
// Grid-hashed cells; each cell carries one ember with its own phase, size,
// brightness and lateral waver. Embers cool as they rise, which is the detail
// most fake ember effects miss.
// ---------------------------------------------------------------------------
vec3 emberField(vec2 uv, float t, float density, int layers, float seed, float orbR) {
  vec3 acc = vec3(0.0);
  for (int L = 0; L < 3; L++) {
    if (L >= layers) break;
    float lf = float(L);
    float scale = 3.4 + lf * 2.6;          // nearer layers are coarser
    float rise  = 0.085 + lf * 0.062;      // and slower: parallax depth
    float sz    = 1.0 - lf * 0.26;

    vec2 p = uv * scale;
    p.y -= t * rise * scale;
    vec2 cell = floor(p);
    vec2 f = p - cell;

    for (int j = -1; j <= 1; j++) {
      for (int i = -1; i <= 1; i++) {
        vec2 nb = vec2(float(i), float(j));
        vec2 h = hash22(cell + nb + seed + lf * 41.7);
        float h2 = hash12(cell + nb + seed * 1.7 + lf * 13.1);

        // Cull a fraction so embers cluster instead of tiling evenly.
        if (h2 > density) continue;

        float speed = 0.055 + h.y * 0.085;
        float life = fract(h.x + t * speed);
        float env = pow(sin(life * PI), 1.35);

        // Lateral waver: two incommensurate frequencies, so no visible loop.
        float wob = sin(life * 5.3 + h.x * 31.0) * 0.17
                  + sin(life * 11.7 + h.y * 17.0) * 0.07;
        vec2 pos = nb + vec2(0.5 + wob, h.y * 0.6 + life * 0.55);

        vec2 d = f - pos;
        float dist2 = dot(d, d);

        // Motion-blur streak: squash the kernel along the travel axis.
        float stretch = 1.0 + 2.2 * speed * 6.0;
        float dist2s = d.x * d.x + (d.y * d.y) / (stretch * stretch);

        // Small cores. Large soft dots read as snow, not embers.
        float rad = (0.0065 + h.y * 0.0115) * sz;
        float core = exp(-dist2s / (rad * rad)) * 1.7;
        float halo = exp(-dist2 / (rad * rad * 60.0)) * 0.16;

        float flick = 0.60 + 0.40 * sin(t * (7.0 + h.x * 15.0) + h.y * 29.0);
        // Most embers sit in the deep-orange band; only a few run amber.
        float temp = (0.34 + h.y * 0.40) * (1.0 - life * 0.42);

        acc += fireRamp(0.26 + temp * 0.62) * core * env * flick * sz
             + fireRamp(0.20) * halo * env;
      }
    }
  }
  // Embers are born from the orb: thin them far away, kill them inside.
  float r = length(uv);
  float gate = smoothstep(orbR * 0.86, orbR * 1.25, r) * exp(-(r - orbR) * 0.55);
  return acc * max(gate, 0.0);
}

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

void main() {
  vec2 fc = FlutterFragCoord().xy;
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

  // UIV2-F4: the faint sky and the dither never reach exactly zero, so on a
  // light theme the square's bounds showed as a faint frame. Fade the output
  // to exactly zero before the edge and drop the sub-1/255 haze; true alpha
  // and the borderless window are kept (no background, no extra pass).
  vec2 en = abs(fc / uSize * 2.0 - 1.0);
  float edge = 1.0 - smoothstep(0.90, 0.985, max(en.x, en.y));
  col = max(col, vec3(0.0)) * edge;

  // Premultiplied emissive output: bright material occludes what is behind it,
  // dark sky lets the UI through, so the companion sits on any background.
  float a = clamp(max(max(col.r, col.g), col.b), 0.0, 1.0);
  if (a < 1.5 / 255.0) {
    col = vec3(0.0);
    a = 0.0;
  }
  fragColor = vec4(col, a);
}
