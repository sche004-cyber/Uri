# URI Living Companions — Solar, Sakura, Lunar

**Branch** `phase/living-companions` · **worktree** `C:\Users\cheta\Development\uri-companions`
· **base** `07a2f38` (`phase/orb-solar-rnd`) · **date** 2026-10-09

Research and prototype phase. Nothing is merged, nothing is accepted, and the
production renderer (`energy_orb.dart`, `orb_core.frag`) is untouched.

---

## 0. Status ledger

The distinction the brief asks for, applied honestly. "Visually verified" means
a frame was captured out of the real Flutter engine and looked at.

| Item | Researched | Prototyped | Implemented | Visually verified | Performance-qualified | Accepted |
|---|---|---|---|---|---|---|
| Solar (refined, direction E) | yes | yes | yes | yes — Flutter run 3 | desktop only | **no** |
| Sakura A — Blossom Vortex | yes | yes | yes | yes — Flutter run 3 | desktop only | **no** |
| Sakura B — Wind Current | yes | yes | no | WebGL only | **failed** (16.9 ms) | **no** |
| Sakura C — Blossom Heart | yes | yes | no | WebGL only | desktop only | **no** |
| Lunar A — Cloud Veil | yes | yes | no | WebGL only | desktop only | **no** |
| Lunar B — Night Window | yes | yes | no | WebGL only | desktop only | **no** |
| Lunar C — Moon Current | yes | yes | yes | yes — Flutter run 3 | desktop only | **no** |
| Moonlit Blossom (Lunar × Sakura) | yes | yes | yes | yes — Flutter run 3 | desktop only | **no** |
| Companion-driven UI theme | yes | yes | yes | yes — themed app frames | n/a | **no** |
| Baked-asset path (Lunar T) | yes | yes | no | WebGL only | measured, **rejected** | **no** |
| Unreal Engine runtime integration | yes | no | no | no | no | **no — not pursued** |

Acceptance is the owner's, through the established independent review. This
report is the candidate, not the verdict.

---

## 1. Acceptance criteria, defined before the work

Set first, per the repository's Verification-First standard, so the result is
measured against something fixed rather than against whatever was achieved.

1. Three visually distinct companions, each with its own geometry, motion
   system and palette — not one shader recoloured three ways.
2. Each covers every state in the existing `CompanionState` contract, and the
   states are distinguishable from one another.
3. Frames captured from the **real Flutter engine**, not only from the
   prototype. A WebGL screenshot is not evidence that Flutter renders.
4. Sakura petals are recognisably cherry blossom, not pink dots.
5. Lunar reads as a moon seen through night cloud, not a blue sphere.
6. Measured GPU cost with stated hardware, resolution and method; no desktop
   number presented as a mobile number.
7. Selecting a companion themes the whole UI through the existing token
   contract, with no new parallel theme system and no change to the four
   accepted Hybrid palettes.
8. Error, warning and security meaning survives every palette, measured.
9. Temporal stability: no visible loop, drift or accumulating artifact over at
   least an hour of shader time.
10. The existing test suite still passes.

All ten are addressed below. Criterion 6 is met only for desktop; the gap is
stated in §11.

---

## 2. Baseline inspected first

`phase/ui-living-companion` ships `orb_core.frag`. Line 68:

```glsl
if (r > 1.0) { fragColor = vec4(0.0); return; }
```

Everything outside the disc is discarded, so flares, petals, embers and cloud
outside the body are not a missing feature — they are structurally impossible.
Its noise is value noise over a `sin(dot())` hash, which is blurry by
construction. This is why a new shader family is justified rather than tuning
the existing one.

The Solar work inherits `phase/orb-solar-rnd` @ `07a2f38` (prototype D) and
its report, including the four corrected mis-diagnoses recorded there.

---

## 3. Tools

| Tool | Used for | Decision |
|---|---|---|
| WebGL2 / GLSL ES 3.00 harness (`rnd/companions/`) | sub-second aesthetic iteration | built; same maths as Flutter, so it transfers 1:1 |
| `EXT_disjoint_timer_query_webgl2` | true GPU timing | used; `gl.finish()` does not block under ANGLE and measures nothing |
| Flutter 3.47.2 + Impeller (OpenGLESSDF) on Windows | ground-truth rendering and capture | used; `tool/capture/capture_app.dart` |
| Node export script | generating the `.frag` from the prototype | used; prototype and production cannot drift |
| Python + NumPy + Pillow | offline asset baking, contact sheets, contrast maths | used |
| Blender / Blender MCP | petal geometry, texture bakes | **not installed** — see §9 |
| Unreal Engine 5 / Niagara | particle sim, volumetric cloud, baking | **not installed** — see §9 |

---

## 4. Solar — refinement of prototype D

The first real Flutter frames (`evidence/flutter/run1/`) exposed three defects
that the WebGL prototype had not made obvious:

1. **The core flattened to a featureless cream disc** at high energy. Cause: a
   smooth high-amplitude `nucleus` term plus a steep brightness curve, both
   saturating before the noise was added. Fix: the temperature curve was
   flattened and the structure terms given more of the range, a second finer
   fibril octave and a faculae layer were added for detail that survives the
   tonemap, and the nucleus amplitude was cut from `0.92 + uEnergy*0.42` to
   `0.34 + uEnergy*0.30` and multiplied by the motion field so it is textured.
2. **The magnetic arcs read as smooth geometric crescents** — glass slivers
   floating beside the orb. Cause: a single Gaussian around a perfect
   semi-ellipse. Fix: `loopArcE` builds each loop from three strands that
   wander on their own noise, carry plasma flow along their length, and taper
   into the surface; arc brightness now tracks `uFlare` far more steeply
   (`0.14 + uFlare*2.00` rather than `0.95 + uFlare*1.45`), so idle is calm.
3. **The corona drifted grey-brown** where dim. Cause: sampling the fire ramp
   below 0.38, where it is a desaturated near-black that the tonemap lifts into
   smoke. Fix: the floor was raised to 0.48.

A fourth defect appeared in run 2 and was fixed in run 3: the chromosphere had
a `0.30` angular floor, which drew a continuous ring around the orb at mid
energies and read as an outline. It is now `0.08` with a second low-frequency
modulation.

---

## 5. Sakura — three directions

Each is a different answer to "what carries the identity".

| | Idea | Strong | Weak | 900² cost |
|---|---|---|---|---|
| **A — Blossom Vortex** | differential rotation shears an even ring into spiral arms; nothing draws an arm | the spiral is emergent, so it never repeats; petals read clearly; best balance | the core is still close to circular | **0.444 ms** |
| **B — Wind Current** | one curl wind field advects every petal; the orb is an obstacle the flow bends around | the gust reading is genuine and unlike anything else in the set | petals bunch on the upwind side and the field looks sparse | **16.9 ms** |
| **C — Blossom Heart** | the core *is* a blossom: four counter-rotating rings of five petals, lit from the centre | the most literally "sakura"; charming | reads as a flower emblem more than a living intelligence | 0.507 ms |

**Selected: A.** It is the only one that is simultaneously the most convincing,
the cheapest, and the most clearly alive. B is disqualified twice over — on
appearance and, decisively, on cost: 16.9 ms per frame is more than a whole
60 fps budget, caused by six Euler integration steps per petal each calling
`windAt`, which calls `curl`, which is four fBm evaluations.

**The petal.** A sakura petal is narrow at the base, broadest near the outer
end, and **notched** there. The notch is the entire identity of the shape;
without it the silhouette is a generic leaf and at companion size it degrades
into exactly the "pink glowing dot" the brief rules out. `petalShape` carves it
on the centre line only, leaving two lobes. Three-dimensionality comes from
`petalAt`, which scales the local x axis by the cosine of a roll angle: at
`|tilt| → 0` the petal narrows to a lit sliver and brightens, which sells
tumbling in 3D with no geometry at all.

**Depth.** Petals are split into a layer behind the core and a layer in front,
each resolved with a per-pixel painter's algorithm (frontmost wins) rather than
summed. Summing is what turns overlapping petals into a glowing smear.

---

## 6. Lunar — three directions plus the hybrid

| | Idea | Strong | Weak | 900² cost |
|---|---|---|---|---|
| **A — Cloud Veil** | three bands drifting horizontally at different rates | simplest and cheapest; very legible | the least alive; reads as weather | **1.330 ms** |
| **B — Night Window** | light shafts are the subject; gaps in the occluder field become beams | the shafts are genuinely pretty | the shaft term is hard to keep from washing the frame | 1.439 ms |
| **C — Moon Current** | the atmosphere circulates around the moon instead of passing it | the only one that reads as the moon's *own* atmosphere; matches the brief's "layered clouds form subtle circulating currents" for thinking | slightly dearest of the three | **1.571 ms** |

**Selected: C**, on the strength of the circulation, which is what makes the
state table expressive rather than decorative.

**Hybrid — Moonlit Blossom** (the "mix these two" option): kept as a fourth
identity at 1.450 ms. It works on one condition, which turned out to be the
whole design problem: **the petals must be lit by the moon, not self-lit.** A
self-luminous pink petal in front of a silver moon reads as two unrelated
effects sharing a frame. Petal brightness is therefore driven by proximity to
the disc and by how much of its face is turned toward it, so petals crossing
the moon are the brightest things in frame, and the only place the two palettes
are allowed to meet is the illuminated cloud edge.

---

## 7. What actually mattered, technically

- **Separating temperature from brightness.** Driving colour and intensity from
  one value is what clips a core to flat white.
- **Anti-mud ramps.** In all three palettes, as a colour darkens it gets *more*
  saturated, not greyer. Mixing toward a neutral dark is what produces muddy
  brown and dirty mauve.
- **Domain warping and curl advection** for flow that reads as fluid rather
  than as a scrolling texture.
- **Directional smear (`smearRidge`) along the local flow.** The Sakura core
  originally used plain ridged noise and read as coral or cerebral folds;
  smearing the same function along the flow turns closed crease networks into
  elongated strands, which is what energy looks like.
- **Broken silhouettes.** Both the Solar limb and the Sakura core boundary are
  displaced by angular noise and faded over a wide band. A smooth gradient
  inside a hard circle is a billiard ball.
- **Sparse, hashed craters.** Deriving craters from the cellular F1 distance
  puts one in every cell at the same size and reads as bubble wrap.
- **Incommensurate periods everywhere**, so nothing visibly loops.

---

## 8. Performance

**Method.** `EXT_disjoint_timer_query_webgl2`, extension and query created on
each view's own context (a query made on another context silently returns 0),
60 draws per query, two independent repeats, `working` state, disjoint frames
rejected. Hardware: **AMD Radeon RX 7900 GRE, 16 GB, via ANGLE / Direct3D 11**.

| Shader | 420×420 (ms) | 900×900 (ms) | 900² as % of a 16.6 ms frame |
|---|---|---|---|
| Solar E | 0.141 / 0.140 | 0.627 / 0.626 | 3.8 % |
| Sakura A | 0.104 / 0.104 | **0.444 / 0.442** | 2.7 % |
| Sakura B | 3.754 / 3.759 | **16.953 / 16.933** | **102 %** |
| Sakura C | 0.120 / 0.121 | 0.507 / 0.513 | 3.1 % |
| Lunar A | 0.306 / 0.304 | 1.330 / 1.336 | 8.0 % |
| Lunar B | 0.328 / 0.326 | 1.439 / 1.444 | 8.7 % |
| Lunar C | 0.359 / 0.358 | 1.571 / 1.574 | 9.5 % |
| Lunar T (baked albedo) | 0.356 / 0.360 | 1.557 / 1.564 | 9.4 % |
| Moonlit Blossom | 0.329 / 0.330 | 1.450 / 1.458 | 8.8 % |

**The optimisation that mattered.** Before it, Sakura A cost 2.972 / 2.982 ms,
Sakura C 2.399 / 2.412 ms and Moonlit 2.918 / 2.927 ms at 900². The entire
difference was a single `curl()` call per petal per fragment: `curl` is four
fBm evaluations, roughly fifty gradient-noise samples, and it was running up to
38 times for every pixel on screen. Replacing it with `waver()` — two
incommensurate sine pairs — gave the same "not on a rail" motion for a few ALU
operations. Sakura A got **6.8× faster with no visible change**
(`evidence/webgl/sheet_v7_optimised.png`).

---

## 9. Unreal Engine evaluation

The question asked was whether Unreal materially improves these companions
without making URI's runtime heavy. It was answered by research plus one
decisive measurement, before installing anything.

### 9.1 Option 3 — Unreal at runtime inside URI: rejected

- **No working path exists today.** The only Flutter↔Unreal package on pub.dev,
  [`gameframework_unreal`](https://pub.dev/packages/gameframework_unreal), is at
  version 0.0.3, 8 months old, 33 downloads, 1 like, "work in progress" for
  Android and iOS and **"planned" for Windows** — that is, not implemented for
  the platform URI runs on.
- **The texture bridge is not a bridge to Flutter.** Unreal's
  [Texture Share](https://dev.epicgames.com/documentation/unreal-engine/texture-share-in-unreal-engine)
  does keep data on the GPU, but it is DirectX 11/12 and is designed for
  Unreal↔Unreal and nDisplay. Flutter on Windows here runs Impeller over
  OpenGLES (observed in the run log: `embedder_surface_gl_impeller.cc … OpenGLESSDF`),
  so adopting it means writing an embedder-level external-texture plugin and
  owning a second render process, its lifetime, and its failure modes.
- **It collides directly with the stated constraint.** A reported
  [~4.8 GB of VRAM for an idle empty UE5 project](https://forums.unrealengine.com/t/vram-usage-editor-vs-packaged-game/548549)
  (editor; a packaged build is smaller but not small) on a 16 GB card **shared
  with URI's Brain** is a resource conflict, not an optimisation. The current
  companions add no VRAM beyond the framebuffer they already draw into.
- **Cost of the alternative, for comparison:** 127 KB of shader source, one
  `drawRect`, 0.44–1.57 ms.

**Verdict: red.** Not pursued, and it should not be pursued without explicit
owner approval and a concrete problem it is the only solution to.

### 9.2 Option 2 — Unreal-assisted baking: tested, and it bought nothing

Unreal's genuine offer here is the
[Niagara Flipbook Baker](https://dev.epicgames.com/documentation/unreal-engine/niagara-flipbook-baker-quick-start-guide-in-unreal-engine):
simulate something expensive offline, bake it to a tiled texture, sample the
texture cheaply at runtime. So the brief's question — *can expensive effects be
baked into reusable assets while preserving live state-driven animation?* — was
tested directly, on the single best candidate in the whole set.

The lunar surface albedo is the only genuinely static field in any of the three
companions. It does not move, does not react to URI's state, and is sampled by
every fragment inside the disc. `rnd/companions/bake_moon.py` (90 lines, NumPy,
no engine) bakes it to a 1024² seamless map with **more** crater detail than
the shader can afford at runtime — four crater scales instead of two, with
directional lit/shadowed walls.

**Measured result: 1.557 / 1.564 ms baked versus 1.571 / 1.574 ms procedural.
A 0.9 % saving, for 351 KB of texture and the VRAM to hold it.** Side by side
(`evidence/webgl/sheet_bake_vs_procedural.png`) the baked version actually shows
*less* crater detail at companion size, because the disc covers roughly 8 % of
the frame and the map is sampled over a fraction of its area.

The reason generalises, and it is the real finding:

> **In these companions the expensive work is the part that cannot be baked,
> and the bakeable part is not expensive.** Cost is dominated by full-frame
> advected cloud, plasma and petal fields that must stay live to follow URI's
> state. Freezing them into a flipbook would reintroduce exactly the repetitive
> loop the brief forbids.

A flipbook also cannot express a continuous parameter: the companions move
through a six-dimensional parameter space that blends smoothly between nine
states, and a baked sequence can only replay what was baked.

**Verdict: amber, with no current target.** The pipeline works — it was built
and measured — but it has nothing worth applying it to here. It would become
relevant if a future companion needed a genuinely static, high-frequency,
large-area asset, and even then the Python path produced a usable asset for
90 lines and no install.

### 9.3 Option 1 — native Flutter shaders: recommended

Already implemented, rendering in the real engine, and measured. Four assets,
127 KB total, one fragment program each, no extra process, no extra VRAM, no
new dependency, and every parameter live.

### 9.4 What Unreal would genuinely be good for, and the cheaper substitute

| Want | Unreal would give | Cheaper substitute used | Verdict |
|---|---|---|---|
| Lunar surface detail | photoreal bake from a height field | procedural craters + maria, or the NumPy bake | substitute wins on measurement |
| Sakura petal geometry and lighting | real 3D petals with normals, GPU instanced | SDF petal + cosine-roll tilt + per-layer depth sort | substitute is convincing and costs 0.44 ms |
| Volumetric cloud | true raymarched volumetrics with multiple scattering | three advected layers with a 3-step transmittance march toward the moon | substitute is honest about being 2.5D; the lit-edge term is what sells it |
| Solar plasma | Niagara GPU particles + fluid sim | analytic ember field + stranded arc SDF | substitute has no particle budget at all |
| Cinematic key art | genuinely better | — | **the one real use**, and it is a separate deliverable, not a runtime concern |

**Nothing was installed.** Disk had 100 GB free; UE5 plus a derived-data cache
would consume a large share of it for a path already shown to have no target.

---

## 10. Flutter implementation

| File | What it is |
|---|---|
| `uri_ui/shaders/companion_{solar,sakura,lunar,moonlit}.frag` | **generated** from the prototype by `rnd/companions/export_flutter.mjs`; 127,313 bytes total |
| `uri_ui/lib/living/companion/companion_orb.dart` | `CompanionIdentity`, `CompanionParams` (tables for all 9 states × 4 identities), `CompanionShaderCache` (never throws), `CompanionOrbFrame` (deterministic), `CompanionOrb` (ticker-driven) |
| `uri_ui/lib/living/companion/companion_theme.dart` | identity → palette / theme choice, `CompanionController`, `CompanionScope` |
| `uri_ui/lib/theme/uri_theme.dart` | three palettes added; the four accepted Hybrid palettes untouched (asserted by test) |
| `uri_ui/tool/capture/capture_app.dart` | real-engine capture harness |
| `uri_ui/tool/demo/theme_demo.dart` | interactive theme + state demonstration, and its capture mode |

**One widget, four shaders, ten uniforms.** The uniform vector is built by
`CompanionOrbPainter.uniformsFor` as a list rather than written straight into
the shader, so its order can be asserted in a test — a silently reordered
uniform is invisible in review and produces a plausible but wrong image.

**Covering nine states, not five.** `CompanionState` is an existing contract
driven by authoritative facts. A companion that could not express
`awaitingApproval` or `unavailable` would fall back to some other state's
appearance and misreport what URI is doing.

### Evidence from the real engine

`flutter run -d windows -t tool/capture/capture_app.dart` → Impeller
(OpenGLESSDF) → `CAPTURE_DONE written=52 failed=0`. 52 frames:
4 identities × (9 states + 4 temporal-stability probes), in
`evidence/flutter/run3/`.

Temporal stability was probed at t = 90, 240, 900 and 3600 s. No loop, no drift
to a fixed point, no accumulating shear (`sheet_stability.png`).

### Tests

`flutter test` → **294 passed, 2 skipped, 0 failed** (baseline before this work
was 277; 17 new). `flutter analyze` on the changed code → no issues.

The new tests deliberately do **not** assert appearance. They assert the things
that break the companion without a pixel changing: the shader-missing fallback,
the uniform count and order, the completeness and range of every state table,
that `error` is distinguishable from `working`, that the four accepted Hybrid
palettes are byte-identical, and that switching identity mid-transition does not
throw.

---

## 11. Theme system

Selecting a companion selects the palette the whole app reads. It resolves
through the **existing** `UriColors` / `UriGlass` / `UriThemeChoice` contract,
so every living widget already reading `UriColors.of(context)` is themed with
no new call site and no parallel theme system. Layout and interaction are
identical across themes — `evidence/themes/` shows the same workspace under all
four identities.

### Measured contrast (WCAG 2.1, `rnd/companions/contrast.py`)

| Pair | Solar Ember | Sakura Bloom | Lunar Silver |
|---|---|---|---|
| body text on surface | 16.37 | 16.44 | 16.27 |
| secondary text on surface | 8.20 | 8.67 | 8.77 |
| faint text on surface | **4.73** | 4.60 | 4.93 |
| accent text on accentSoft | 11.40 | 10.61 | 13.08 |
| success on successSoft | 8.08 | 7.87 | 7.57 |
| warning on warningSoft | 9.03 | 7.70 | 7.41 |
| danger on dangerSoft | 5.73 | 5.23 | 6.10 |

**A real failure was found and fixed.** Solar's `inkFaint` measured **4.42:1**,
below WCAG AA's 4.5:1 for normal text, and that tier is used for placeholder
and inactive labels. It was lifted from `0xFF86776A` to `0xFF8B7C6F` → 4.73:1.

**Status meaning across palettes.** Status colours keep their own hue family in
every theme. Where a companion accent sat near a status hue, the *accent* was
moved, not the status: Solar's accent is solar orange rather than amber so
`warning` stays legible beside it, and Sakura's accent is magenta-pink rather
than rose so `danger` does not read as branding. Luminance separation between
accent and status is low by construction (1.1–1.9), which is why it matters
that status is **never colour-only** — every badge carries its text label and a
`Semantics` label (verified in `status_badge.dart`).

### Accessibility

`EffectsSettings.reducedEffects` drops the shader entirely and shows the
fallback. `reducedMotion` freezes the clock at a representative moment rather
than hiding the companion, so the state stays readable while nothing moves.
Both are covered by tests.

---

## 12. Correction history

Preserved rather than overwritten, per the repository's evidence rules.

| # | Conclusion that turned out wrong | How it was disproved | Correction |
|---|---|---|---|
| 1 | The Sakura core needed a brighter centre | v1 frames showed a pink billiard ball with a specular-looking highlight | the problem was the *structure*, not the brightness: smooth radial gradient inside a hard circle. Replaced by `sakuraCore` |
| 2 | Ridged noise would give the Sakura core energy structure | it rendered as coral / cerebral folds at every amplitude | ridged noise makes *closed* crease networks; smearing it along the local flow makes strands |
| 3 | Lowering cloud `cover` would clear the Lunar sky | v2 frames were still fully overcast at `cover ≈ 0.02` | the threshold in `cloudSlab` was so low the field was non-zero almost everywhere; `cover` was never the lever |
| 4 | The Lunar atmosphere mask would localise the cloud | v2 still filled the frame | the mask had a 0.06 far-field floor and three layers stacked over it; needed a steeper falloff *and* per-layer opacity cuts |
| 5 | Baking the static lunar albedo would be a worthwhile optimisation | measured 1.557 vs 1.571 ms — 0.9 % | the bakeable part was never the expensive part (§9.2) |
| 6 | Craters could come from the cellular F1 distance | rendered as bubble wrap, in both the shader and the first bake | F1 puts one crater in every cell at the same size; craters must be hashed sparse and lit directionally |
| 7 | The Sakura B wind field just needed more petals | raising the count did nothing | the Euler step was up to 0.7 uv units, flinging petals off-frame before they were drawn |

---

## 13. What is NOT verified

Stated plainly, because none of it is covered by the evidence above.

1. **No mobile or low-end measurement.** Every number is one discrete desktop
   GPU (RX 7900 GRE) through ANGLE/D3D11. A weak integrated GPU could plausibly
   be 5–15× slower, which would put Lunar C at 8–24 ms and over budget. **No
   quality tier or resolution cap has been built.** This is the largest gap.
2. **No measurement of Flutter's own frame cost.** The GPU figures are from the
   WebGL prototype, which runs the identical fragment maths but not Flutter's
   compositing, raster pipeline or `drawRect` overhead. Flutter frames were
   captured and inspected; they were not profiled.
3. **No CPU or VRAM measurement** of the Flutter companion, and no measurement
   of contention with the Brain sharing the GPU.
4. **The interactive demo was driven by me, not by a user.** Switching themes
   preserves navigation and conversation *by construction* (a `ChangeNotifier`
   that only the theme and the companion listen to), and no test exercises a
   real session surviving a switch.
5. **Unreal was researched, not trialled.** §9.1 rests on documentation, a
   package listing and a forum-reported VRAM figure — not on a build I ran.
   The conclusion is a judgement from those facts, and it would be overturned
   by evidence of a working, light Windows Flutter↔Unreal texture path.
6. **The hybrid is an extra, not a requested deliverable.** It was built because
   the owner floated it; it has had less iteration than the other three.
7. **Nothing is wired into the running app.** `energy_orb.dart` and
   `orb_core.frag` are untouched; `CompanionOrb` is reachable only from the
   capture harness and the demo.
8. **No independent review.** This is a self-assessment.

---

## 14. Next steps

1. **Owner decision:** which Sakura (A recommended), which Lunar (C
   recommended), and whether Moonlit Blossom is a fourth identity or dropped.
2. Measure on the weakest target device; add a resolution cap and a quality
   tier (fewer petals, two cloud layers, smaller ember field) driven by a
   measured frame budget rather than a guess.
3. Profile the Flutter widget itself — raster thread, CPU, VRAM — and under
   Brain contention.
4. Decide whether `energy_orb.dart` adopts `CompanionOrb` or is replaced.
5. Persist the companion choice through `ThemeStore` and add a test that a live
   session survives a switch.
6. Remaining visual work: the Sakura core is still close to circular; Sakura B
   needs either a cheap reformulation or retirement; Lunar A/B/C are less
   differentiated from one another than the Sakura set.
7. Independent acceptance review before any integration candidate.

---

## 15. Evidence index

| Path | What |
|---|---|
| `evidence/flutter/run1/` | first real Flutter frames; the three Solar defects |
| `evidence/flutter/run2/` | all four identities, pre-optimisation |
| `evidence/flutter/run3/` | **final** — 52 frames, 4 identities × 9 states + stability probes |
| `evidence/flutter/run3/sheet_identities.png` | the four companions across four states |
| `evidence/flutter/run3/sheet_states_sakura.png` | all nine states |
| `evidence/flutter/run3/sheet_stability.png` | t = 90 … 3600 s |
| `evidence/themes/` | the same workspace under each companion theme |
| `evidence/webgl/sheet_v1…v7` | the iteration trail, including every rejected pass |
| `evidence/webgl/sheet_bake_vs_procedural.png` | the Unreal baking question, measured |
| `evidence/iterations/` | archived rejected shader sources |
| `rnd/companions/` | harness, shaders, export, bake, contrast, sheet tooling |

Raw frames are stored at review resolution rather than at capture resolution
(720 px for the final run, 460 px for superseded iterations) to keep the
repository workable; the labelled contact sheets, which are what the
conclusions in this report were drawn from, are unmodified. Captures can be
reproduced exactly from the harnesses at any resolution.
