// Generates uri_ui/shaders/orb_solar.frag from the prototype shader source.
//
// The prototype and the Flutter shader must stay bit-identical in their maths,
// so the .frag is generated rather than transcribed. Only three things differ
// between the WebGL2 prototype and the Flutter build:
//   1. the version/precision header and the runtime_effect include
//   2. gl_FragCoord      -> FlutterFragCoord()
//   3. the opaque output -> premultiplied alpha, so the orb composites over UI
//
// Run: node rnd/orb_solar/export_flutter_frag.mjs

import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const { LIB, PROTO_D } = await import('./shaders.js');

const FLUTTER_HEADER = `#version 460 core
#include <flutter/runtime_effect.glsl>

// URI Solar Orb - generated from rnd/orb_solar/shaders.js (prototype D).
// DO NOT EDIT BY HAND: run \`node rnd/orb_solar/export_flutter_frag.mjs\`.
//
// Uniform order must match orb_solar_shader.dart exactly:
//   0,1 uSize  2 uTime  3 uEnergy  4 uTurb  5 uFlare
//   6   uEmber 7 uFocus 8 uRadius  9 uExposure

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
`;

let body = LIB + PROTO_D;

// gl_FragCoord is not available in a Flutter fragment program.
body = body.replaceAll('gl_FragCoord.xy', 'FlutterFragCoord().xy');

// Premultiplied-alpha emissive output. Using max() for alpha keeps rgb <= a,
// which is what a premultiplied surface requires; a luminance-based alpha can
// exceed the channel values and clips oddly in the compositor.
const OPAQUE_OUT = `  col += dither(fc);
  fragColor = vec4(col, 1.0);`;
const PREMUL_OUT = `  col += dither(fc);

  // Premultiplied emissive output: bright plasma occludes what is behind it,
  // dark sky lets the UI through, so the orb sits on any background.
  float a = clamp(max(max(col.r, col.g), col.b), 0.0, 1.0);
  fragColor = vec4(col, a);`;

if (!body.includes(OPAQUE_OUT)) {
  throw new Error('output block not found - prototype shader changed shape');
}
body = body.replaceAll(OPAQUE_OUT, PREMUL_OUT);

const out = resolve(here, '../../uri_ui/shaders/orb_solar.frag');
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, FLUTTER_HEADER + body, 'utf8');
console.log(`wrote ${out} (${(FLUTTER_HEADER + body).length} bytes)`);
