// Generates uri_ui/shaders/companion_*.frag from the prototype sources.
//
// The prototype and the Flutter shaders must stay identical in their maths, so
// the .frag files are generated rather than transcribed: there is no way for
// the thing that was reviewed and the thing that ships to drift apart. Only
// three things differ between the WebGL2 prototype and the Flutter build:
//   1. the version/precision header and the runtime_effect include
//   2. gl_FragCoord      -> FlutterFragCoord()
//   3. the opaque output -> premultiplied alpha, so the orb composites over UI
//
// Run: node rnd/companions/export_flutter.mjs

import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const { LIB } = await import('../orb_solar/shaders.js');
const { EXTRA } = await import('./extra.js');
const { SOLAR_E } = await import('./solar.js');
const { SAKURA_A } = await import('./sakura.js');
const { LUNAR_C, LUNAR_SAKURA } = await import('./lunar.js');

// The identity, the prototype key it came from, and the asset it becomes.
const TARGETS = [
  { file: 'companion_solar.frag', from: 'solar.js SOLAR_E', src: SOLAR_E,
    title: 'Solar Intelligence',
    reads: ['uEnergy  flame and brightness', 'uTurb    surface chaos',
            'uFlare   magnetic prominence activity', 'uEmber   drifting ember density',
            'uFocus   coherence of the arcs'] },
  { file: 'companion_sakura.frag', from: 'sakura.js SAKURA_A', src: SAKURA_A,
    title: 'Sakura Intelligence',
    reads: ['uEnergy  core brightness and orbital rate', 'uTurb    wind chaos in the petal field',
            'uFlare   energy-ribbon strength', 'uEmber   petal and pollen count',
            'uFocus   how tightly the petals hold their arms'] },
  { file: 'companion_lunar.frag', from: 'lunar.js LUNAR_C', src: LUNAR_C,
    title: 'Lunar Intelligence',
    reads: ['uEnergy  cloud speed and luminance', 'uTurb    cloud turbulence',
            'uFlare   halo and shaft strength', 'uEmber   star and mist density',
            'uFocus   how far the clouds part (low obscures the moon)'] },
  { file: 'companion_moonlit.frag', from: 'lunar.js LUNAR_SAKURA', src: LUNAR_SAKURA,
    title: 'Moonlit Blossom (Lunar x Sakura)',
    reads: ['uEnergy  cloud speed and luminance', 'uTurb    wind and cloud turbulence',
            'uFlare   halo strength', 'uEmber   petal, star and mist density',
            'uFocus   how far the clouds part'] },
];

const PRELUDE = LIB + EXTRA;

const OPAQUE_OUT = `  col += dither(fc);
  fragColor = vec4(col, 1.0);`;

// Premultiplied-alpha emissive output. Using max() for alpha keeps rgb <= a,
// which is what a premultiplied surface requires; a luminance-based alpha can
// exceed the channel values and clips oddly in the compositor.
const PREMUL_OUT = `  col += dither(fc);

  // Premultiplied emissive output: bright material occludes what is behind it,
  // dark sky lets the UI through, so the companion sits on any background.
  float a = clamp(max(max(col.r, col.g), col.b), 0.0, 1.0);
  fragColor = vec4(col, a);`;

function header(t) {
  return `#version 460 core
#include <flutter/runtime_effect.glsl>

// URI ${t.title} - GENERATED from rnd/companions/${t.from}.
// DO NOT EDIT BY HAND: run \`node rnd/companions/export_flutter.mjs\`.
//
// Uniform order must match lib/living/companion/companion_orb.dart exactly:
//   0,1 uSize  2 uTime  3 uEnergy  4 uTurb  5 uFlare
//   6   uEmber 7 uFocus 8 uRadius  9 uExposure
//
// How this companion reads the expression uniforms:
${t.reads.map((r) => `//   ${r}`).join('\n')}

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
}

let total = 0;
for (const t of TARGETS) {
  let body = PRELUDE + t.src;
  body = body.replaceAll('gl_FragCoord.xy', 'FlutterFragCoord().xy');
  if (!body.includes(OPAQUE_OUT)) {
    throw new Error(`${t.file}: output block not found - prototype changed shape`);
  }
  body = body.replaceAll(OPAQUE_OUT, PREMUL_OUT);
  const text = header(t) + body;
  const out = resolve(here, '../../uri_ui/shaders/', t.file);
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, text, 'utf8');
  total += text.length;
  console.log(`wrote ${t.file} (${text.length} bytes) from ${t.from}`);
}
console.log(`${TARGETS.length} shaders, ${total} bytes total`);
