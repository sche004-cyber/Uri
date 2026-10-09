#version 460 core
#include <flutter/runtime_effect.glsl>

// URI shared voice waveform.
//
// One shader for both speakers. It has no notion of who is talking: the user's
// microphone and URI's own speech arrive as the same two numbers (level, flux)
// through the same mapping (lib/living/voice/voice_level.dart), and the colours
// are the active companion theme's tokens. Equal audio therefore draws equal
// pixels, which is the requirement, not a convention.
//
// Uniform order must match lib/living/voice/voice_waveform.dart exactly:
//   0,1 uSize  2 uTime  3 uLevel  4 uFlux  5 uPresence  6 uMotion
//   7-9 uColA (accent)  10-12 uColB (accentInk)  13-15 uColC (ink)
//
// Shape: a horizontal oval holding a few soft, mirrored wave bands. Each band
// is tapered by an envelope that reaches zero at the oval's ends, so the waves
// grow out of the centre and never touch the boundary. Silence leaves a thin,
// slowly breathing line; speech opens the bands with the level.

uniform vec2  uSize;
uniform float uTime;
uniform float uLevel;     // 0..1 display level, already smoothed
uniform float uFlux;      // 0..1 onset emphasis
uniform float uPresence;  // 0..1 fade in/out of the whole component
uniform float uMotion;    // 1 normal, 0 reduced motion (no travelling phase)
uniform vec3  uColA;
uniform vec3  uColB;
uniform vec3  uColC;

out vec4 fragColor;

// One band: returns (signed height, envelope) at normalised x in -1..1.
float band(float x, float t, float k1, float k2, float s1, float s2, float ph) {
  float a = sin(x * k1 + t * s1 + ph);
  float b = sin(x * k2 - t * s2 + ph * 1.7);
  // A slow travelling lobe so the bands bulge in different places over time
  // instead of breathing in lockstep.
  float lobe = 0.62 + 0.38 * sin(x * 1.9 - t * 0.37 + ph * 2.3);
  return (a * 0.64 + b * 0.36) * lobe;
}

void main() {
  vec2 fc = FlutterFragCoord().xy;
  float hh = 0.5 * uSize.y;
  vec2 p = (fc - 0.5 * uSize) / hh;          // y in -1..1, x in -asp..asp
  float asp = uSize.x / uSize.y;
  float rx = asp * 0.97;
  float x = p.x / rx;                        // -1..1 along the oval
  float px = 1.0 / hh;                       // one pixel in these units

  // Oval boundary, soft over a few pixels.
  float e = length(vec2(x, p.y / 0.96));
  float inside = 1.0 - smoothstep(1.0 - 3.0 * px, 1.0, e);
  if (inside <= 0.0 || uPresence <= 0.0) { fragColor = vec4(0.0); return; }

  float t = uTime * uMotion;
  // Elliptical envelope: the bands' combined silhouette is itself an oval, so
  // loud speech fills the oval rather than drawing a spindle along its axis.
  float env = pow(max(0.0, 1.0 - x * x), 0.62);
  float lvl = clamp(uLevel, 0.0, 1.0);
  float flx = clamp(uFlux, 0.0, 1.0);
  float y = abs(p.y);
  float aa = 1.25 * px;

  vec3 col = vec3(0.0);
  // Four bands. Their weights fall off so the first carries the speech and the
  // others add depth; their spatial and temporal frequencies are mutually
  // irrational so the pattern does not visibly repeat.
  for (int i = 0; i < 4; i++) {
    float fi = float(i);
    float w = 1.0 - fi * 0.17;
    float k1 = 3.1 + fi * 1.37;
    float k2 = 6.3 + fi * 2.11;
    float s1 = 1.15 + fi * 0.41;
    float s2 = 1.63 + fi * 0.29;
    float ph = fi * 2.399;                   // golden angle
    float amp = (0.05 + lvl * 1.30 * w + flx * 0.30 * (1.0 - fi * 0.25))
              * uPresence;
    float h = min(abs(band(x, t, k1 + flx * 2.0, k2, s1, s2, ph)) * amp * env, 0.92);
    // Filled lens between the band and its mirror, brighter towards its edge,
    // then a thin bright edge. Widths are in pixels so the line stays crisp at
    // any size.
    float fill = smoothstep(h + aa, h - aa, y);
    float depth = h > 1e-4 ? clamp(y / h, 0.0, 1.0) : 0.0;
    float edge = exp(-pow((y - h) / (1.1 * px + 0.010 * lvl), 2.0));
    vec3 tint = i == 0 ? uColB : (i == 1 ? uColA : (i == 2 ? mix(uColA, uColC, 0.5) : uColC));
    float bw = i == 0 ? 1.0 : 0.66 - fi * 0.08;
    col += tint * (fill * (0.05 + 0.20 * depth * depth) + edge * 0.48) * bw;
  }

  // The centre line: strongest in silence, so a quiet channel still reads as
  // "a voice is here" without pretending there is speech, and it recedes
  // once the bands carry real audio.
  float line = exp(-pow(p.y / (1.0 * px + 0.004), 2.0)) * (0.30 - 0.20 * lvl);
  col += mix(uColB, uColC, 0.35) * line * uPresence * env;

  // A faint glass body and rim so the oval reads as a shape at rest.
  // Deliberately quiet: no neon, no glow halo.
  float body = (1.0 - e * e) * 0.045;
  float rim = exp(-pow((e - 0.982) / 0.014, 2.0)) * 0.07;
  col += mix(uColA, uColC, 0.3) * (body + rim) * uPresence;

  col *= inside;
  // Soft shoulder so overlapping bands never clip to flat white.
  col = col / (1.0 + col * 0.55);
  float a = clamp(max(max(col.r, col.g), col.b), 0.0, 1.0);
  fragColor = vec4(col, a);
}
