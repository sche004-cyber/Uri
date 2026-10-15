# Ember V2 - Research and Approach Comparison

## 1. What exists (inspected 2026-10-15)

- **Companion seam.** Every surface (shell, rail, dashboard, onboarding and settings) draws `LivingCompanion`, which
  dispatches through `CompanionOrb` by `CompanionIdentity`.
  - Solar, Sakura, Lunar and Moonlit are one fragment shader each, redrawn every frame while animating.
  - Ember (V1) is `EmberCompanion`, a sprite player. Each frame it draws one textured quad cut from a WebP atlas. It
    has 320 px cells at 24 fps, cross-fades additively between clips, keeps only the current and previous clips
    resident, and asks for frames only on sprite boundaries (`wantsFrames`).
- **Theme.** Choosing Ember selects the Solar Ember palette (`companion_theme.dart`). Its canvas is `#0A0806` and its
  surface is `#130F0B`, so living surfaces always show Ember on a warm near-black background. A light-theme backdrop
  is not a runtime case.
- **State contract.** There are 9 `CompanionState` values from authoritative sources (`companion_sources.dart`,
  `integration/oi_sources.dart`). `OiCompanionSource` has no path to `success` (V1 finding F-SUCCESS). There is no
  "starting" state: a Brain that is still loading reports `unavailable` with detail `Brain <STATE>`.
- **V1 measurements** (V1 `evidence/perf*`, harness `tool/capture/ember_perf_app.dart`):

  | Measure | Ember V1 (sprite player) | Solar (shader) |
  |---|---|---|
  | GPU 3D, median | 0.23 % | 6.2 % |
  | Frames requested per second | 35-60 | 145-160 |
  | Dedicated VRAM | +40-65 MB | — |

  V1 fidelity was 41-51 % in critique and 0-21 on the automated scale.
- **Reference.**
  - The four-panel sheet `uri_emotions_sheet.png` (896x1200), one panel of about 448x500 px per state.
  - The owner's motion video (Gemini, 10 s). It is a redraw, and scored 63-67 %.
- **Tools on this PC.**
  - Blender 5.2.2 (portable), ffmpeg.
  - Python 3.13 with numpy 2.5, scipy 1.18 and Pillow 12. OpenCV, scikit-image and torch are not installed.
  - Flutter: the existing UI toolchain.

## 2. Why V1 could not reach the target

V1 rebuilt the character in 3D, with Geometry Nodes flames and a shaded head. The critique gaps were:
- the flame structure;
- the head material;
- per-state poses;
- the joyful eyes;
- the painterly surface.

These are exactly the qualities a painting has and a procedural model must imitate. V1 also showed that "redrawn
by another hand" sits near 65 %. The 90 % target therefore means *this painting*, not *this design*. The source of
the pixels has to be the painting.

## 3. Approaches compared

| | A. V1 3D, improved (NPR, swept sheets) | B. Painting-derived 2.5D, pre-rendered (selected) | C. Painting-derived 2.5D, real-time in Flutter | D. Rig tools (Live2D / Spine / Rive) | E. AI-generated video sprites |
|---|---|---|---|---|---|
| Visual fidelity | Ceiling about 65 % (redraw evidence); V1 measured 41-51 % | Rest frame recomposes the painting: mean abs. error 0.4-0.6 % (`layers.py` prototype, section 4). Animation moves painted pixels. | Same as B | Same source art, but needs hand-built meshes in a GUI editor | 63-67 % measured (the owner's video); identity drifts between shots |
| Animation quality | Full 3D freedom | Organic flame flow, sway, breathing, face rig and sparks inside each painted pose. Big pose changes only between panels (cross-fade). | Like B, plus non-repeating noise and interactive gaze | Best for limb animation; flames still need a shader | Rich motion, uncontrollable |
| GPU / VRAM | Sprite player (V1 numbers) | **Sprite player: V1 measured 0.23 % GPU, about 40-65 MB VRAM, at most 24 sprite frames/s** | Per-frame mesh deform plus a flow-warp shader at display rate. That is the Solar-class path, measured at 6.2 % GPU and 145-160 frames/s. | Extra runtime library; real-time | Sprite player |
| Complexity | High (Blender); V1 shows diminishing returns | Python only (numpy/scipy, already installed); player unchanged except a small blink overlay | New mesh, shader and texture pipeline in the protected companion seam | New dependency, proprietary editor or licence, no headless authoring | External service, licence, no control |
| Compatibility | Same seam | Same seam, same atlas format, same manifest | Same seam, new code path | New package in `pubspec` | Same seam |
| Maintainability | 1,300-line Blender script | Rig landmarks in `rig.json`, one expression table, reproducible build | More runtime code to maintain | Tied to a vendor | Not reproducible |

Rejected:
- **A**: evidence shows its ceiling is below the target.
- **D**: it adds a dependency and needs GUI authoring that cannot be scripted or reviewed. The Live2D and Spine
  runtimes carry commercial licences, and Rive needs its editor.
- **E**: it scored 63-67 %, has generator marks and its licence is unclear. It is used only as a motion reference.
- **C**: it brings fidelity no higher than B. It raises GPU cost towards Solar's measured level, which the brief puts
  last behind Brain responsiveness. It also adds a new rendering path to accepted code.

## 4. Selected: B, plus one small runtime layer

**Offline**, `companion_art/fire_v2/`, Python only:
1. `layers.py` cuts each reference panel into straight-alpha RGBA.
   - A background plate is estimated by normalised convolution around the character.
   - The minimum alpha that keeps colour in gamut is taken. This gives flames, glow and sparks their painted
     softness.
   - Head, eyes and body are forced opaque from the `rig.json` landmarks and a dark-body mask.
   - The artist signature (idle) and the generator mark (depleted) are inpainted out.
   - Prototype result: recomposition error 0.38 % (idle), 0.60 % (joyful), 0.41 % (fierce), 0.58 % (depleted).
2. `animate.py` builds one displacement field per frame:
   - flame turbulence that scrolls upward a whole number of tiles per loop, so the loop is seamless;
   - tip-weighted sway;
   - breathing with the feet planted;
   - flame flicker;
   - sparks.
   A face rig built from the panel's own pixels adds lids, gaze offset and a mouth. It derives the functional
   expressions from the reference faces.
3. The atlases are exported in V1's format (same manifest, 320 px cells, 24 fps).

**Runtime**, `ember_companion.dart`:
- The V1 player stays.
- One addition: a blink overlay, a few lid frames per clip drawn over the eyes and scheduled at irregular intervals.
  This makes blinking natural and keeps it out of the loops, so loops can stay short and VRAM bounded.
- The overlay is drawn only on sprite frames the player already produces. It adds no new continuous rendering.

Limits accepted with this choice:
- Each state keeps the pose of its painting.
- Between panels the player cross-fades. It does not articulate limbs.
- Derived expressions (listening, thinking and so on) are new compositions of reference parts, so they have no
  reference to score against. They are judged for identity consistency.
