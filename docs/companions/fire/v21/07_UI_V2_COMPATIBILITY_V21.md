# Ember V2.1 - URI UI V2 Compatibility

Owner directive "Ember V2.1 - URI UI V2 Compatibility" (2026-10-15, MANDATORY; OD-V21-2 in
`00_PLAN_AND_ACCEPTANCE_V21.md`). Two separate records:
- **Record B, transparency readiness (Stage 1):** implemented and tested in Ember now.
- **Record C, final UI V2 integration (Stage 2):** deferred until UI V2 reaches its controlled integration
  checkpoint.

Record A (visual and functional qualification) is the rest of this milestone, summarised in
`FINAL_QUALIFICATION_REPORT_V21.md`.

## 1. Separation of concerns (as required)

| Concern | Owner | Ember's contract |
|---|---|---|
| Companion rendering: artwork, animation, expressions, particles, lighting, **alpha** | Ember (`companion_art/fire_v2`, the atlases, `ember_companion.dart`) | Premultiplied-correct RGBA sprites with genuine alpha. No opaque background, no reliance on any host mask for its edges. Drawn by the existing `EmberPainter` through the existing `CompanionOrb` -> `EmberCompanion` interface. |
| UI presentation: window transparency, borders, position, drag, resize, click-through, transitions | UI V2 (`companion_window_adapter.dart`, `living_shell.dart`, `LivingCompanion`/`SoftDisc`) | Untouched by Ember. Ember adds no window, shader or UI-specific code path. |

## 2. What was wrong before (baseline evidence)

`scripts/fire_companion/transparency_check.py` on the earlier atlases:

| Build | T1 border | T2 outer ring | T3 opaque area | Verdict |
|---|---|---|---|---|
| V2 (`b73bd26c`) | alpha up to 255 (frames cut at the cell edge) | 255 (opaque pool) | 13-21 % | FAIL |
| V2.1 painted (`9933ca2b`) | 94 (soft square edge) | 255 (opaque painted backdrop) | 86 % | FAIL |

Files: `evidence/transparency/baseline_*_gates.json`. In a transparent window, V2 would show a brown pool and V2.1
painted a brown square; both relied on the host's SoftDisc and the app canvas to hide their edges.

## 3. Transparency implementation (`73e84a6d`)

Research summary. The candidate techniques, and what was taken:
- **Straight-alpha atlas plus a premultiplied paint path.** Already in place since V1/V2; kept. The exporter
  downsamples premultiplied (no dark fringes) and stores straight alpha in WebP with `exact=True`.
- **Minimum-alpha matting.** Already in `layers.py`: the luminous strokes keep their painted translucency. Kept.
- **Glow as light.** A desktop compositor blends source-over only; there is no additive blending against the
  desktop. Flame light is therefore encoded as a translucent warm layer: `export_v2.Framing.glow`. It is the bright
  parts of each frame, blurred, with alpha proportional to the blurred brightness and capped at 0.45. It follows the
  animated flames frame by frame and fades before the cell border. Pre-baked into the atlas: zero runtime cost, no
  shader.
- **Painted backdrop as atmosphere.** Used only as a translucent haze (60 %, radial fade, alpha <= 0.29 outside the
  figure) on the depleted clip. There the smoke needs a backdrop (P3: 73.8 without it, 79.0 with it). Other clips
  gained nothing from haze in P3 and are cleaner without it on light desktops.
- **Rejected:**
  - A runtime glow shader: it adds GPU cost and a rendering dependency for no measured gain.
  - Additive or screen blend modes: they are not available against the desktop.
  - The opaque painted backdrop: it violates the directive.
- **Self-contained edges.** Everything Ember draws is transparent in the outer band of its square, so it shows no
  boundary with or without a host SoftDisc.

Configuration (`companion_art/fire_v2/expressions.json`):
- `stage` (global): `strength 0` switches V2's opaque pool off; `glow` adds the emissive layer.
- `clips.depleted.stage`: the glow plus `texture`, `strength 0.6`, `pool`, `edge` and `edge_margin 0.03`.

Ember runtime code is unchanged.

Fidelity cost (record A): see `evidence/fidelity/P3_RESULTS.md` and `Q2_RESULTS.md`. The
transparent build scored 85.3-86.8 in Q2, against the painted build's 85.7-86.3 in Q1 and the control's 88.3-89.3 in
Q2. In P3 it cost about 6 points against the painted build on today's dark app canvas.

## 4. Tests run now (Stage 1)

| # | Requirement | How tested | Result |
|---|---|---|---|
| 1 | Transparent rendering against multiple backgrounds | Every shipped clip, frames 0, 1/3 and 2/3, composited from the shipped atlases over black, white, saturated blue, mid grey, a colour gradient, a checkerboard and noise: `evidence/transparency/contrast_<clip>.jpg`. Earlier variant sheets also used a Windows wallpaper locally (not committed: third-party image). | PASS (visual) |
| 2 | No rectangular cut-out artefacts | T0: every frame contains Ember (guard against an empty atlas, added after R2-04). T1: outer 2 % band alpha <= 2/255 in **every frame of every shipped clip** (worst 0); T2: outside the central circle alpha <= 128 (worst 73, depleted haze; others 64 or less); T3: opaque area <= 25 % (worst 7.0 %). `transparency_gates.json` | PASS |
| 3 | Flame, smoke and glow alpha blending | T4 matte check: no dark-matte fringe pixels at semi-transparent rims in any frame. Limitation (R2-04): T4 tests rims next to opaque pixels; depleted has almost none, so T4 is close to vacuous there and its smoke is judged from the contrast sheets. T5 checks the blink patch's outer edge only. Visual: flames and glow read as light on dark and light backgrounds. Smoke is dark, painted translucency: faint on black, visible on light backgrounds. That is inherent to dark smoke on a transparent surface, not a defect. | PASS, with the noted limitation |
| 4 | Animation clipping and boundaries | T1 holds for all 456 frames of the 8 shipped clips (fierce is not shipped). Blink patches (T5): inside the cell, patch-edge alpha <= 1. | PASS |
| 5 | Existing companion rendering compatibility | New Flutter test `ember_transparency_test.dart`: the real `EmberCompanion`/`EmberPainter`, real atlases, transparent layer with no host mask, all 8 clips; border, ring and opaque-area gates pass. It failed on the painted atlases when run before the change; that console output was not committed (the committed baseline is the equivalent atlas-gate result, `baseline_v21_painted_9933ca2b_gates.json`). Ember tests: 36 existing plus the 8 new transparency tests, 44/44. The render test covers frame 0 of each clip (`still: true`), without blinks; all frames and the blink patches are covered by the atlas gates. | PASS |
| 6 | Stable animation and performance | Perf series on the transparent atlases under our own GPU lease (`evidence/perf_transparent/`, 12/12 lease checks): GPU 0.28 % median (Solar 6.6-7.5 %), dedicated VRAM 147 MB (= V2), frame p99 2.75-2.78 ms, 47.5-48.4 frames/s. Live run 3 (`evidence/live/run3_returning_transparent/`): Ember restored, irregular blinks, Settings clean. | PASS |
| 7 | No regressions to existing companions | Full Flutter suite at `e792ddc8`: 588 passed, 5 skipped, 0 failed. Solar perf unchanged against the earlier series. | PASS |
| - | Transparent borderless **desktop window** | Not exercised. UI V2's transparent window lives on a separate stream and Ember is not integrated there. Rendering tests are isolated and do not prove the real window. | **PENDING (Stage 2)** |

## 5. UI V2 architecture check (read-only)

Inspected candidate `C:\Users\cheta\Development\uri-ui-v2-final-repair` at `316e6475`, read-only:
- Companion Mode makes the Windows window frameless with a transparent background
  (`services/companion_window_adapter.dart`: `setAsFrameless`, `setBackgroundColor(Colors.transparent)`, 440x680).
- The companion is drawn through the same `LivingCompanion` -> `SoftDisc` -> `CompanionOrb` path as today, with
  `scale = presenceScale(id) * look.size * presentationScale`. `presentationScale` is 1.85 only for Solar in Companion
  Mode with `services.visualV2`, and 1 otherwise.
- **Ember is not present in UI V2:** no `CompanionIdentity.ember`, no `ember_companion.dart`, no Ember assets.

Compatibility reading:
- Ember's transparent cell inside UI V2's SoftDisc and transparent window needs no change on either side for alpha.
- The disc fades a transparent image, so no square and no backdrop can appear.

## 6. Remaining UI V2 integration dependencies (for Stage 2)

1. **Port into the accepted UI V2 candidate:**
   - `CompanionIdentity.ember` (bodyRadius 0.42) and the `CompanionOrb` hand-off to `EmberCompanion`;
   - `ember_companion.dart`, the Ember assets and the pubspec asset entries.

   `companion_orb.dart` is a shared, accepted UI V2 file, so this goes through UI V2's approval and repair process,
   not a silent edit.
2. **Size preference.** At `look.size` above 1.0 (up to 1.25) the host zooms Ember inside the disc, and the feet and
   crest move into the fade. Either Ember's frame gets a margin, or the owner accepts it. This is a visual decision.
3. **Presentation scale.** UI V2 gives Solar 1.85 in Companion Mode. Whether Ember needs its own value is for UI V2
   to decide; Ember's frame assumes 1.
4. **Startup state.** `CompanionState.starting` is still a proposal (AMBER, `04_STARTUP_PROPOSAL_V21.md`).
5. **Stage 2 live checks, all on the exact accepted UI V2 candidate:**
   - transparent borderless window over real desktops;
   - dragging and positioning;
   - resizing;
   - click-through and interactive regions;
   - always-on-top;
   - Companion -> Workspace and Companion -> Dashboard transitions;
   - expression consistency;
   - GPU and VRAM with the real Brain;
   - companion regression tests.

## 7. Gate status

| Gate | Status | Evidence |
|---|---|---|
| B1 Genuine alpha transparency | **PASS** | gates T2/T3, Flutter test |
| B2 No permanent opaque rectangular background | **PASS** for opacity. Qualifier (R2-05): the depleted haze covers about 59 % of the cell at alpha > 0.1 and reads as a soft grey field on white; translucent, but a visible atmosphere, so it shares B4's owner sign-off | T2, T3, contrast sheets |
| B3 No visible window boundaries (Ember's own edges) | **PASS** | T1 on all frames |
| B4 Painterly lighting blends into transparency | **PASS** (technical). The depleted haze look on light desktops needs **owner visual sign-off** (PENDING owner) | contrast sheets |
| B5 Correct alpha for flames, smoke, particles | **PASS**; limitation: dark smoke is faint on dark desktops | T4, contrast sheets |
| B6 Existing rendering interfaces | **PASS** | no `uri_ui/lib` change; Ember tests |
| B7 Existing interaction and animation behaviour | **PASS** (UI V1 host) | live run 3; perf |
| B8 Minimal GPU/VRAM | **PASS** | perf_transparent |
| B9 No regression to existing companions | **PASS** | full suite 588/5/0 at `e792ddc8`; Solar perf unchanged |
| C1-C10 UI V2 live integration (Stage 2 list) | **PENDING** | UI V2 not at its integration checkpoint; Ember not in UI V2 |
| Stage 3 canonical integration | **NOT ELIGIBLE** | AC-F1 NOT MET; lifecycle acceptance BLOCKED; Stage 2 PENDING; licensing (OD-2) open |
