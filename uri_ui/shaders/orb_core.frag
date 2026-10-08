#version 460 core
#include <flutter/runtime_effect.glsl>

// URI Energy Orb core: a slowly turning plasma inside a sphere.
// Uniform layout (must match orb_shader.dart):
//   0,1  uSize      (width, height) in logical px
//   2    uTime      seconds
//   3    uEnergy    0..1  activity level (idle low, thinking/working high)
//   4    uTurbulence 0..1 how chaotic the swirl is (error high)
//   5,6,7 uColor    glow color rgb (0..1)
//   8    uAlpha     overall opacity

uniform vec2 uSize;
uniform float uTime;
uniform float uEnergy;
uniform float uTurbulence;
uniform vec3 uColor;
uniform float uAlpha;

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
  for (int i = 0; i < 4; i++) {
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
  // Fake sphere normal for a little volume.
  float z = sqrt(max(0.0, 1.0 - r * r));
  float speed = 0.12 + uEnergy * 0.55;
  float t = uTime * speed;
  float ang = atan(uv.y, uv.x);
  vec2 swirl = vec2(cos(ang + t * 0.7), sin(ang + t * 0.7)) * r;
  float n1 = fbm(swirl * (2.2 + uTurbulence * 2.5) + vec2(t, -t * 0.6));
  float n2 = fbm(uv * 3.5 - vec2(t * 0.4, t * 0.9) + n1 * 1.5);
  float plasma = smoothstep(0.25, 0.95, n2 * 0.8 + n1 * 0.6);
  // Brighter towards the centre, with a soft limb.
  float core = pow(z, 1.6);
  float limb = smoothstep(1.0, 0.72, r);
  vec3 bright = mix(uColor, vec3(1.0), 0.65);
  vec3 col = mix(uColor * 0.55, bright, plasma) * (0.35 + core * 0.9);
  col += uColor * (0.25 + uEnergy * 0.35) * pow(1.0 - r, 2.0);
  float alpha = limb * uAlpha;
  fragColor = vec4(col * alpha, alpha);
}
