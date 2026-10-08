#version 460 core
#include <flutter/runtime_effect.glsl>

// URI Energy Orb core: a turning plasma inside a sphere, two-tone.
// Uniform layout (must match orb_shader.dart / energy_orb.dart):
//   0,1   uSize       (width, height) in logical px
//   2     uTime       seconds
//   3     uEnergy     0..1 activity (idle low, thinking/working high)
//   4     uTurbulence 0..1 chaos (error high)
//   5,6,7 uColor      primary rgb (0..1)
//   8     uAlpha      overall opacity
//   9,10,11 uColor2   secondary rgb (0..1), the plasma's second hue
//   12    uStyle      0 = plasma swirl, 1 = sun (granular, hot), 2 = liquid (slow veins)

uniform vec2 uSize;
uniform float uTime;
uniform float uEnergy;
uniform float uTurbulence;
uniform vec3 uColor;
uniform float uAlpha;
uniform vec3 uColor2;
uniform float uStyle;

out vec4 fragColor;

float hash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  float a = hash(i);
  float b = hash(i + vec2(1.0, 0.0));
  float c = hash(i + vec2(0.0, 1.0));
  float d = hash(i + vec2(1.0, 1.0));
  return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

float fbm(vec2 p) {
  float v = 0.0;
  float amp = 0.5;
  for (int i = 0; i < 5; i++) {
    v += amp * noise(p);
    p = p * 2.03 + vec2(1.7, 9.2);
    amp *= 0.5;
  }
  return v;
}

void main() {
  vec2 uv = (FlutterFragCoord().xy / uSize) * 2.0 - 1.0;
  float r = length(uv);
  if (r > 1.0) {
    fragColor = vec4(0.0);
    return;
  }
  float z = sqrt(max(0.0, 1.0 - r * r));
  float speed = 0.12 + uEnergy * 0.55;
  float t = uTime * speed;
  float ang = atan(uv.y, uv.x);
  vec3 col;
  if (uStyle < 0.5) {
    // Plasma: two-tone swirl with bright filaments.
    vec2 swirl = vec2(cos(ang + t * 0.7), sin(ang + t * 0.7)) * r;
    float n1 = fbm(swirl * (2.2 + uTurbulence * 2.5) + vec2(t, -t * 0.6));
    float n2 = fbm(uv * 3.5 - vec2(t * 0.4, t * 0.9) + n1 * 1.5);
    float plasma = smoothstep(0.2, 0.95, n2 * 0.8 + n1 * 0.6);
    float filament = pow(1.0 - abs(fract(n2 * 3.0 + t * 0.3) * 2.0 - 1.0), 8.0);
    vec3 base = mix(uColor2 * 0.5, uColor, plasma);
    vec3 hot = mix(uColor, vec3(1.0), 0.75);
    col = base * (0.35 + pow(z, 1.4) * 0.9) + hot * filament * (0.6 + uEnergy * 0.6);
    col += uColor * (0.2 + uEnergy * 0.3) * pow(1.0 - r, 2.0);
  } else if (uStyle < 1.5) {
    // Sun: granular hot surface, limb darkening, cooler second colour at the edge.
    float g1 = fbm(uv * 6.0 + vec2(t * 0.5, t * 0.3));
    float g2 = fbm(uv * 12.0 - vec2(t * 0.8, t * 0.2));
    float gran = smoothstep(0.3, 0.85, g1 * 0.7 + g2 * 0.5);
    vec3 hot = mix(uColor, vec3(1.0, 0.98, 0.9), 0.7);
    col = mix(uColor2, hot, gran) * (0.5 + pow(z, 0.8) * 0.8);
    col += hot * pow(max(0.0, 1.0 - r * 1.1), 3.0) * 0.6;
  } else {
    // Liquid: slow deep veins.
    float v1 = fbm(uv * 2.5 + vec2(t * 0.25, -t * 0.2));
    float v2 = fbm(uv * 5.0 + v1 * 2.0 - vec2(t * 0.1, t * 0.3));
    float vein = pow(1.0 - abs(fract(v2 * 2.5) * 2.0 - 1.0), 6.0);
    vec3 deep = uColor2 * 0.45;
    col = mix(deep, uColor, smoothstep(0.35, 0.8, v1)) * (0.4 + pow(z, 1.2) * 0.8);
    col += mix(uColor, vec3(1.0), 0.6) * vein * (0.5 + uEnergy * 0.7);
  }
  float limb = smoothstep(1.0, 0.72, r);
  float alpha = limb * uAlpha;
  fragColor = vec4(col * alpha, alpha);
}
