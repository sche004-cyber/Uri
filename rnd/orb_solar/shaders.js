// URI Solar Orb R&D - shader sources (v3).
// The body math below is written so it ports to Flutter's GLSL 460 core
// FragmentProgram with only the header and uniform block changed.
//
// v1 -> v2: split temperature from brightness (v1 clipped the whole disc to
//           flat white); fixed B's silhouette mask using R instead of Reff.
// v2 -> v3: replaced ridged-noise "granulation" with Worley convection cells
//           (v2 produced radial pinstripes that read as a lens flare); removed
//           the hard limb rim that traced a circle outline; clumped the corona
//           into a few fat curved streamers instead of hundreds of uniform
//           hairs; tightened the nucleus so white is rare.

export const HEADER = `#version 300 es
precision highp float;
precision highp int;
out vec4 fragColor;

uniform vec2  uSize;      // canvas size in px
uniform float uTime;      // seconds, unbounded
uniform float uEnergy;    // 0..1 overall activity
uniform float uTurb;      // 0..1 turbulence / chaos
uniform float uFlare;     // 0..1 flare + prominence activity
uniform float uEmber;     // 0..1 ember field density
uniform float uFocus;     // 0..1 how coherent/intentional motion reads
uniform float uRadius;    // orb radius in normalized units (1.0 = half min side)
uniform float uExposure;  // HDR exposure before tonemap
`;

// ---------------------------------------------------------------------------
// Shared library.
// ---------------------------------------------------------------------------
export const LIB = `
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
`;

// ---------------------------------------------------------------------------
// PROTOTYPE A - Solar Intelligence
// Clean star-core: two-scale convection granulation, soft broken limb, a few
// controlled corona streamers, sparse embers, slow confident breathing.
// ---------------------------------------------------------------------------
export const PROTO_A = `
void main() {
  vec2 fc = gl_FragCoord.xy;
  vec2 uv = (fc - 0.5 * uSize) / min(uSize.x, uSize.y) * 2.0;
  float r = length(uv);
  vec2 dir = r > 1e-5 ? uv / r : vec2(0.0, 1.0);
  float ang = atan(uv.y, uv.x);

  // Breathing on three incommensurate periods: never exactly repeats.
  float breathe = 0.5 + 0.5 * (sin(uTime * 0.41) * 0.5
                             + sin(uTime * 0.27 + 1.3) * 0.33
                             + sin(uTime * 0.17 + 2.7) * 0.17);
  float R = uRadius * (1.0 + breathe * 0.018 * (0.4 + uEnergy));

  float t = uTime * (0.10 + uEnergy * 0.42);
  vec3 col = vec3(0.0);

  // ---- photosphere -------------------------------------------------------
  // Temperature and brightness are SEPARATE fields. Driving both from one
  // value blows the whole disc to flat white and hides all the texture.
  if (r < R * 1.03) {
    float rn = clamp(r / R, 0.0, 1.0);
    float mu = sqrt(max(0.0, 1.0 - rn * rn));

    // Mild sphere projection. Strong radial stretching is what produced the
    // pinstripe lens-flare look, so keep it gentle.
    vec2 sp = uv / max(0.62 + 0.38 * mu, 0.40);

    // Slow large-scale mottling.
    float sg = warpFbm(sp * 2.3 + vec2(t * 0.16, -t * 0.11), t, 2.4);

    // Surface structure. Worley convection cells were tried here and rejected:
    // the fire ramp is steep around gold, so even a 0.013 heat delta rendered
    // the intergranular lanes as a visible net across the disc. Domain-warped
    // mottling plus ridged fibrils give flow instead of a lattice.
    vec2 drift = curl(sp * 1.4, t * 0.6) * 0.060;
    float mot = warpFbm(sp * 4.6 + drift * 3.0 + vec2(-t * 0.21, t * 0.13), t * 1.3, 2.2);
    float fib = ridged(sp * 7.5 + drift * 5.0 + vec2(-t * 0.36, t * 0.26), 4);

    float heat = 0.44 + 0.30 * (1.0 - rn * rn)
               + sg * 0.11
               + mot * 0.09
               + (fib - 0.42) * 0.085 * (0.6 + uTurb * 0.8);
    heat = clamp(heat * (0.78 + 0.22 * limbDarken(mu)), 0.0, 1.0);

    float bright = (0.38 + 0.68 * pow(1.0 - rn, 1.7)) * limbDarken(mu)
                 * (0.90 + 0.18 * (mot * 0.5 + 0.5));

    float edge = 1.0 - smoothstep(R * 0.975, R * 1.012, r);
    col += fireRamp(heat) * bright * edge * (1.0 + uEnergy * 0.45);

    // Filament crests: thin white-hot fibrils, the way magnetic structure shows
    // on a real photosphere. Sparkle without washing the disc out.
    float crest = smoothstep(0.52, 0.88, fib);
    col += fireRamp(0.96) * crest * edge * mu * (0.22 + uEnergy * 0.72);

    // Tight white-hot nucleus. Small on purpose: white should be the rarest
    // colour on screen, not the default.
    float nucleus = pow(max(0.0, 1.0 - rn * 5.1), 3.2);
    col += fireRamp(0.99) * nucleus * edge * (0.95 + uEnergy * 0.45);
  }

  col += coronaLayer(uv, r, dir, ang, R, t, uEnergy);
  col += emberField(uv, uTime, 0.26 + uEmber * 0.30, 2, 11.0, R) * (0.7 + uEmber * 1.2);

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;

// ---------------------------------------------------------------------------
// PROTOTYPE B - Ember Storm
// One coherent flame volume whose outer boundary varies with angle and time,
// so the silhouette is ragged rather than circular, plus a dense ember field.
// A circular outline is the main thing that makes an orb read as a glowing ball.
// ---------------------------------------------------------------------------
export const PROTO_B = `
void main() {
  vec2 fc = gl_FragCoord.xy;
  vec2 uv = (fc - 0.5 * uSize) / min(uSize.x, uSize.y) * 2.0;
  float r = length(uv);
  vec2 dir = r > 1e-5 ? uv / r : vec2(0.0, 1.0);
  float ang = atan(uv.y, uv.x);

  float breathe = 0.5 + 0.5 * (sin(uTime * 0.37) * 0.55 + sin(uTime * 0.23 + 2.1) * 0.45);
  float R = uRadius * (1.0 + breathe * 0.030 * (0.5 + uEnergy));
  float t = uTime * (0.14 + uEnergy * 0.60);

  // Advection. Kept deliberately mild: a strong curl term rolls the tongues
  // into cartoon hooks instead of letting them reach outward.
  vec2 flow = curl(uv * 1.5, t) * (0.022 + uTurb * 0.042);
  vec2 cuv = uv + flow;

  // ---- flame boundary -----------------------------------------------------
  // Long radial smear so tongues point outward; angular swell so some sectors
  // of the limb erupt further than others.
  float tongue = smearRidge(cuv * 3.2 + vec2(-t * 0.30, t * 0.22), dir, 0.165, 5);
  float lick = warpFbm(cuv * 2.1, t * 1.1, 2.6 + uTurb * 1.8) * 0.5 + 0.5;
  float swell = angNoise(ang, 1.8, t * 0.085);
  float breach = (tongue * 0.72 + lick * 0.34 + swell * 0.40) * (0.35 + uEnergy * 0.70);

  float Reff = R * (1.0 + breach * (0.36 + uTurb * 0.44));

  // Signed field: > 0 inside the flame, 0 at its edge.
  float field = (Reff - r) / max(R, 1e-3);
  float dens = smoothstep(-0.05, 0.26, field);

  vec3 col = vec3(0.0);

  // ---- body ---------------------------------------------------------------
  {
    float rn = clamp(r / R, 0.0, 1.0);
    float mu = sqrt(max(0.0, 1.0 - min(rn, 0.999) * min(rn, 0.999)));
    vec2 sp = cuv / max(0.64 + 0.36 * mu, 0.42);

    float conv = warpFbm(sp * 2.8 + vec2(t * 0.22, -t * 0.18), t, 3.2 + uTurb * 2.2);
    vec2 drift = curl(sp * 1.7, t * 0.9) * 0.10;
    float fib = ridged(sp * 8.0 + drift * 5.0 - vec2(t * 0.42, t * 0.28), 4);

    // Temperature falls steadily outward: roots gold, tips deep red.
    float heat = clamp(0.24 + 0.46 * clamp(field, 0.0, 1.0)
                     + conv * 0.15
                     + (fib - 0.42) * 0.075 * (0.6 + uTurb), 0.0, 1.0);
    float bright = dens * (0.30 + 0.80 * smoothstep(0.0, 0.52, field))
                 * (0.90 + 0.18 * (conv * 0.5 + 0.5));
    col += fireRamp(heat) * bright * (1.05 + uEnergy * 0.55);

    float crest = smoothstep(0.56, 0.90, fib) * (rn < 0.99 ? 1.0 : 0.0);
    col += fireRamp(0.95) * crest * mu * (0.20 + uEnergy * 0.65);

    float nucleus = pow(max(0.0, 1.0 - rn * 5.2), 3.1);
    col += fireRamp(0.99) * nucleus * (0.90 + uEnergy * 0.40);
  }

  // ---- detached flame tips ------------------------------------------------
  // Fragments torn off the main body. These sell "fire" far more than a
  // continuous gradient does.
  {
    float h = max(r - R, 0.0);
    float tip = smoothstep(0.52, 0.90, tongue) * smoothstep(0.38, 0.0, abs(field - 0.05));
    col += fireRamp(clamp(0.72 - h * 1.1, 0.14, 1.0)) * tip * (0.9 + uEnergy * 1.5);
  }

  // ---- outer heat haze ----------------------------------------------------
  {
    float h = max(r - R, 0.0);
    float hn = warpFbm(uv * 1.6 + vec2(0.0, -t * 0.4), t, 2.0) * 0.5 + 0.5;
    col += fireRamp(0.26 + hn * 0.18) * exp(-h * 2.2) * hn * (0.07 + uEnergy * 0.11);
    float rimN = 0.30 + 0.70 * angNoise(ang, 3.6, t * 0.09);
    col += fireRamp(0.80) * exp(-abs(r - R) * 40.0) * rimN * 0.16;
  }

  col += emberField(uv, uTime, 0.40 + uEmber * 0.42, 3, 3.0, R * 0.95)
       * (1.0 + uEmber * 1.6);

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;

// ---------------------------------------------------------------------------
// PROTOTYPE C - Magnetic Sun
// Photosphere plus parametric magnetic loop arcs anchored on the limb, each on
// its own lifecycle. The arcs are explicit geometry, so the motion reads as
// intentional - which is what makes the orb feel intelligent rather than merely
// turbulent.
// ---------------------------------------------------------------------------
export const PROTO_C = `
// One magnetic loop: an elliptical arch rising from the limb between two
// footpoints. Returns (core, halo) so the arc is volumetric, not a wire.
vec2 loopArc(float r, float ang, float R,
             float aMid, float aSpan, float height, float thick) {
  float da = atan(sin(ang - aMid), cos(ang - aMid));
  float u = da / max(aSpan, 1e-3);
  if (abs(u) > 1.0) return vec2(0.0);

  float arch = R * (1.0 + height * sqrt(max(0.0, 1.0 - u * u)));
  float d = abs(r - arch);

  // Thin at the apex, thicker at the feet, like a real flux tube.
  float w = thick * (0.60 + 0.40 * abs(u));
  float coreG = exp(-(d * d) / (w * w));
  float haloG = exp(-(d * d) / (w * w * 5.0)) * 0.22;
  float endFade = smoothstep(1.0, 0.42, abs(u));
  return vec2(coreG * endFade, haloG * endFade * endFade);
}

void main() {
  vec2 fc = gl_FragCoord.xy;
  vec2 uv = (fc - 0.5 * uSize) / min(uSize.x, uSize.y) * 2.0;
  float r = length(uv);
  vec2 dir = r > 1e-5 ? uv / r : vec2(0.0, 1.0);
  float ang = atan(uv.y, uv.x);

  float breathe = 0.5 + 0.5 * (sin(uTime * 0.33) * 0.6 + sin(uTime * 0.19 + 1.9) * 0.4);
  float R = uRadius * (1.0 + breathe * 0.020 * (0.4 + uEnergy));
  float t = uTime * (0.12 + uEnergy * 0.48);

  vec3 col = vec3(0.0);

  // ---- photosphere with differential-rotation shear ----------------------
  if (r < R * 1.03) {
    float rn = clamp(r / R, 0.0, 1.0);
    float mu = sqrt(max(0.0, 1.0 - rn * rn));
    vec2 sp = uv / max(0.62 + 0.38 * mu, 0.40);

    // Latitude-dependent rotation rate, the way a real star rotates.
    float lat = uv.y / max(R, 1e-3);
    vec2 rp = sp + vec2(t * (0.14 - 0.07 * lat * lat), 0.0);

    float band = warpFbm(vec2(rp.x * 1.9, rp.y * 3.4), t, 2.2);
    vec2 drift = curl(rp * 1.5, t * 0.6) * 0.065;
    // Fibrils are sampled in the UNSHEARED frame. Sampling them in the
    // sheared frame was tried and rejected: the shear offset grows with time,
    // which smeared the fine noise into regular horizontal coil banding.
    // Differential rotation now shows only in the large-scale bands below.
    float fib = ridged(sp * 7.2 + drift * 5.0 + vec2(-t * 0.30, t * 0.21), 4);

    float heat = 0.44 + 0.29 * (1.0 - rn * rn) + band * 0.12
               + (fib - 0.42) * 0.080;
    heat = clamp(heat * (0.78 + 0.22 * limbDarken(mu)), 0.0, 1.0);
    float bright = (0.37 + 0.66 * pow(1.0 - rn, 1.8)) * limbDarken(mu)
                 * (0.90 + 0.18 * (band * 0.5 + 0.5));

    float edge = 1.0 - smoothstep(R * 0.975, R * 1.012, r);
    col += fireRamp(heat) * bright * edge * (1.0 + uEnergy * 0.45);

    float crest = smoothstep(0.54, 0.89, fib);
    col += fireRamp(0.96) * crest * edge * mu * (0.20 + uEnergy * 0.65);

    float nucleus = pow(max(0.0, 1.0 - rn * 5.1), 3.2);
    col += fireRamp(0.99) * nucleus * edge * (0.92 + uEnergy * 0.42);
  }

  // ---- magnetic loop arcs -------------------------------------------------
  // Four arcs on staggered, incommensurate lifecycles: at any moment some are
  // forming and some are decaying. Deliberate, not random.
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float seed = fi * 7.3;
    float period = 11.0 + fi * 3.17;
    float cyc = floor((uTime + seed * 3.1) / period);
    float phase = fract((uTime + seed * 3.1) / period);

    // Fast rise, held plateau, slow decay.
    float life = smoothstep(0.00, 0.16, phase) * (1.0 - smoothstep(0.46, 1.00, phase));
    if (life < 0.004) continue;

    float aMid = hash12(vec2(seed, cyc)) * TAU + t * 0.14;
    float aSpan = 0.34 + hash12(vec2(seed + 1.0, cyc)) * 0.30;
    float height = (0.22 + hash12(vec2(seed + 2.0, cyc)) * 0.36)
                 * (0.45 + uFlare * 1.10) * life;
    float thick = R * (0.055 + 0.035 * (1.0 - uFocus)) * (0.6 + life * 0.6);

    vec2 g = loopArc(r, ang, R, aMid, aSpan, height, thick);
    if (g.x + g.y <= 0.0) continue;

    // Plasma flowing along the loop: bright knots travelling foot to foot.
    float da = atan(sin(ang - aMid), cos(ang - aMid)) / max(aSpan, 1e-3);
    float knot = 0.55 + 0.45 * sin(da * 6.0 - uTime * (1.5 + fi * 0.21));
    float grain = 0.72 + 0.46 * unoise(vec2(da * 8.0, r * 13.0 - uTime * 1.1));

    float amt = life * (0.95 + uFlare * 1.45);
    col += fireRamp(0.56 + 0.34 * knot) * g.x * knot * grain * amt;
    col += fireRamp(0.48) * g.y * amt * 0.75;
  }

  col += coronaLayer(uv, r, dir, ang, R, t, uEnergy);
  col += emberField(uv, uTime, 0.30 + uEmber * 0.34, 2, 23.0, R) * (0.8 + uEmber * 1.3);

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;

// ---------------------------------------------------------------------------
// PROTOTYPE D - Solar Intelligence (refined)
// The improvement pass on the strongest direction. C's photosphere and magnetic
// loop arcs supply the intentional motion; B's energy-gated silhouette breach
// supplies the non-circular outline. At idle the limb is clean and composed; as
// energy rises the limb erupts. The orb is calm when calm and violent when busy,
// which is what makes it read as a presence rather than an effect.
// ---------------------------------------------------------------------------
export const PROTO_D = `
vec2 loopArcD(float r, float ang, float R,
              float aMid, float aSpan, float height, float thick) {
  float da = atan(sin(ang - aMid), cos(ang - aMid));
  float u = da / max(aSpan, 1e-3);
  if (abs(u) > 1.0) return vec2(0.0);
  float arch = R * (1.0 + height * sqrt(max(0.0, 1.0 - u * u)));
  float d = abs(r - arch);
  float w = thick * (0.60 + 0.40 * abs(u));
  float coreG = exp(-(d * d) / (w * w));
  // The halo was far wider and cut off over a narrow angular ramp, which drew
  // hard grey wedges beside the orb. Tighter radially, softer in angle.
  float haloG = exp(-(d * d) / (w * w * 5.0)) * 0.22;
  float endFade = smoothstep(1.0, 0.42, abs(u));
  return vec2(coreG * endFade, haloG * endFade * endFade);
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

  // ---- energy-gated silhouette breach ------------------------------------
  // Idle keeps a composed, near-circular limb. Only as energy rises does the
  // outline break up, so the orb has somewhere to go.
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

    // Differential rotation, at a rate small enough that it does not smear the
    // fine structure into bands.
    float lat = uv.y / max(R, 1e-3);
    vec2 rp = sp + vec2(t * (0.14 - 0.07 * lat * lat), 0.0);

    float band = warpFbm(vec2(rp.x * 1.9, rp.y * 3.4), t, 2.2);
    vec2 drift = curl(sp * 1.4, t * 0.6) * 0.060;
    float mot = warpFbm(sp * 4.4 + drift * 3.0 + vec2(-t * 0.20, t * 0.12), t * 1.2, 2.2);
    float fib = ridged(sp * 7.2 + drift * 5.0 + vec2(-t * 0.30, t * 0.21), 4);

    float heat = 0.44 + 0.29 * (1.0 - rn * rn)
               + band * 0.085 + mot * 0.075
               + (fib - 0.42) * 0.080 * (0.6 + uTurb * 0.7);
    heat = clamp(heat * (0.78 + 0.22 * limbDarken(mu)), 0.0, 1.0);

    float bright = (0.38 + 0.66 * pow(1.0 - rn, 1.7)) * limbDarken(mu)
                 * (0.90 + 0.18 * (mot * 0.5 + 0.5));

    float edge = 1.0 - smoothstep(R * 0.975, R * 1.012, r);
    col += fireRamp(heat) * bright * edge * (1.0 + uEnergy * 0.45);

    float crest = smoothstep(0.56, 0.90, fib);
    col += fireRamp(0.88) * crest * edge * mu * (0.17 + uEnergy * 0.60);

    float nucleus = pow(max(0.0, 1.0 - rn * 5.1), 3.2);
    col += fireRamp(0.99) * nucleus * edge * (0.92 + uEnergy * 0.42);
  }

  // ---- erupting limb ------------------------------------------------------
  {
    float field = (Reff - r) / max(R, 1e-3);
    float outside = smoothstep(R * 0.97, R * 1.01, r);
    float dens = smoothstep(-0.04, 0.22, field) * outside;
    float h = max(r - R, 0.0);
    float temp = clamp(0.74 - h * 1.25, 0.12, 1.0);
    col += fireRamp(temp) * dens * tongue * (0.85 + uEnergy * 1.45);
  }

  // ---- magnetic loop arcs -------------------------------------------------
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float seed = fi * 7.3;
    float period = 11.0 + fi * 3.17;
    float cyc = floor((uTime + seed * 3.1) / period);
    float phase = fract((uTime + seed * 3.1) / period);
    float life = smoothstep(0.00, 0.16, phase) * (1.0 - smoothstep(0.46, 1.00, phase));
    if (life < 0.004) continue;

    float aMid = hash12(vec2(seed, cyc)) * TAU + t * 0.14;
    float aSpan = 0.34 + hash12(vec2(seed + 1.0, cyc)) * 0.30;
    float height = (0.22 + hash12(vec2(seed + 2.0, cyc)) * 0.36)
                 * (0.45 + uFlare * 1.10) * life;
    float thick = R * (0.055 + 0.035 * (1.0 - uFocus)) * (0.6 + life * 0.6);

    float da = atan(sin(ang - aMid), cos(ang - aMid)) / max(aSpan, 1e-3);
    float amt = life * (0.95 + uFlare * 1.45);

    // Footpoint brightening where the loop meets the limb, so the arcs read as
    // plasma anchored in the surface rather than detached crescents floating
    // beside the orb. It is computed BEFORE the arc's early exit: this term
    // peaks exactly at the arc's angular cutoff, so skipping it there drew hard
    // radial wedge edges beside the orb.
    float fa = (abs(da) - 1.0) / 0.22;
    float fr = (r - R) / (R * 0.11);
    col += fireRamp(0.90) * exp(-fa * fa) * exp(-fr * fr) * life
         * (0.45 + uFlare * 0.80);

    vec2 g = loopArcD(r, ang, R, aMid, aSpan, height, thick);
    if (g.x + g.y <= 0.0) continue;

    float knot = 0.55 + 0.45 * sin(da * 6.0 - uTime * (1.5 + fi * 0.21));
    float grain = 0.72 + 0.46 * unoise(vec2(da * 8.0, r * 13.0 - uTime * 1.1));
    col += fireRamp(0.56 + 0.34 * knot) * g.x * knot * grain * amt;
    col += fireRamp(0.48) * g.y * amt * 0.75;
  }

  col += coronaLayer(uv, r, dir, ang, R, t, uEnergy);
  col += emberField(uv, uTime, 0.28 + uEmber * 0.40, 3, 23.0, R) * (0.8 + uEmber * 1.5);

  col *= uExposure;
  col = aces(col);
  col += dither(fc);
  fragColor = vec4(col, 1.0);
}
`;

export const PROTOS = {
  A: { name: 'A - Solar Intelligence', src: PROTO_A },
  B: { name: 'B - Ember Storm', src: PROTO_B },
  C: { name: 'C - Magnetic Sun', src: PROTO_C },
  D: { name: 'D - Solar Intelligence (refined)', src: PROTO_D },
};

// Expressive states. One table drives every prototype, so the state machine is
// portable regardless of which direction wins.
export const STATES = {
  idle:      { energy: 0.22, turb: 0.16, flare: 0.10, ember: 0.28, focus: 0.85, exposure: 1.00 },
  listening: { energy: 0.36, turb: 0.14, flare: 0.14, ember: 0.44, focus: 0.95, exposure: 1.08 },
  thinking:  { energy: 0.62, turb: 0.48, flare: 0.30, ember: 0.52, focus: 0.70, exposure: 1.06 },
  speaking:  { energy: 0.74, turb: 0.34, flare: 0.62, ember: 0.60, focus: 0.88, exposure: 1.10 },
  acting:    { energy: 1.00, turb: 0.74, flare: 0.92, ember: 1.00, focus: 0.55, exposure: 1.16 },
};
