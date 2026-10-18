# Fire Companion - Research and Approach

Status of this document: RESEARCHED. Measurements that confirm or change the decision are recorded in
`03_MEASUREMENTS.md` and in the final report; this file is not edited to hide a later correction.

## 1. Repository findings (canonical 1b5423bc)

| Area | Finding | Reuse |
|------|---------|-------|
| Companion seam | `LivingCompanion` (`uri_ui/lib/living/companion/living_companion.dart`) is the only widget surfaces use. It switches on `CompanionChoice.identity`; classic orb when `null`. | Add the fire identity here; no surface changes. |
| Identity | `CompanionIdentity` enum + `CompanionIdentityInfo` (label, tagline, shader asset, body radius). | Extend with one value. |
| State | `CompanionState` (9 values) from authoritative sources (`companion_sources.dart`, `voice_session.dart`, `oi_sources.dart`). | Consume unchanged. |
| Frames | `CompanionFrameDriver` mixin (`frame_clock.dart`): shared clock, minimise suspension, frame cap, `wantsFrames`. | Drive sprite playback with it. |
| Preferences | `CompanionPreferences`: choice, per-companion look (size, motion, brightness...), quality, persisted keys. | Fire becomes one more `CompanionChoice`; look/quality apply. |
| Theme | `CompanionTheme` maps identity to an existing `UriThemeChoice`/`UriColors`. | Fire maps to the existing Solar Ember palette (warm); no new theme. |
| Reduced effects / motion | `EffectsSettings`: reduced effects -> classic orb; reduced motion -> still image. | Same rules. |
| Presence scale | `presenceScale(id)` in `voice/companion_presence.dart`. | Add a value for fire. |
| Capture harness | `uri_ui/tool/capture/capture_app.dart` renders companions in a real Windows window. | Reuse for fire frames and frame-time measurement. |
| 3D / Blender | None in the repository; Blender was not installed (installed 5.2.2 under OD-1). | New: `companion_art/fire/`. |
| Wake word | None. `HOTWORDS = "URI"` in `uri_ui/assets/voice/uri_voice_service.py` only biases the recogniser during push-to-talk. | Wake journey reported NOT AVAILABLE. |

## 2. Reference analysis

### 2.1 Emotions sheet (primary)

Shared identity across all four panels:
- Head: wide, slightly flattened oval (about 1.25:1), cream-white, lit from inside; warm orange at the rim.
- Eyes: very large, glossy, set low and wide; pure black in Idle, brown iris with a catch-light in the other three.
- Flame: wispy brush strokes radiating from the back and crown of the head; white-hot at the root, gold, then
  orange at the tips. Strong sideways "mane" in Idle, upward billow in Joyful, tall swept plume in Fierce,
  a few dying flickers plus smoke in Depleted.
- Body: small dark tattered robe from neck to knees, thin dark limbs, tiny hands with small flames.
- Atmosphere: warm halo around the head, ember sparks, a pool of light on the ground, painterly brown backdrop.

Per state:
- Idle: arms slightly out, palms with tiny flames, curling flame "tail" on the left, calm.
- Joyful: arms up, hop, open smiling mouth, blush, eyes with iris and lower-lid smile, many sparks.
- Fierce: wide stance, arms out holding swirling fireballs, angry brows and slanted lids, frown, tall flame.
- Depleted: head turns ash-grey, half-closed sad eyes, sad brows, small frown, slumped posture, a few flickers
  and two smoke columns, no hand or tail flame.

### 2.2 Video (`reference/motion_reference_gemini.mp4`, 10 s, 1280x720, 24 fps)

Contact sheets: `reference/video_frames/contact_01.jpg`, `contact_02.jpg`; key frames `key_*.jpg`.

| Time | Behaviour | Taken into the design |
|------|-----------|-----------------------|
| 0.0-2.3 s Idle | Slow body sway, flame leans and flickers, tail flame flicks at the side, occasional sparks. | Idle loop: sway + bob, tail flame, sparse embers, blink overlay. |
| 2.3-5.0 s Joyful | Jump with knees up, flame whips around, sparkles orbit the body, eyes close into happy arcs. | Joyful loop: hop, arms up, dense embers, flame lift. Eyes stay open to follow the sheet (primary). |
| 5.0-7.5 s Fierce | Widens stance, fireballs swirl in both hands, shouting mouth, smoke appears behind. | Fierce: swirl in hand flames, stance; smoke kept low. |
| 7.5-10 s Depleted | Head flame shrinks to embers, then to two smoke wisps; head droops; tail ember remains. | Depleted: smoke strands, slump, dim. A short "reignite" transition is the reverse. |

The video is a cleaner, more cartoon rendering than the painted sheet (smooth flames, egg-shaped head,
shaggy body). It also carries a Gemini mark. It is used for motion only; shape and colour follow the sheet.

### 2.3 Provenance

Both images and the video are AI-generated derivatives of an illustration listed on Fiverr. Owner decision OD-2:
the owner holds or will obtain the rights. This is recorded, not verified; release outside the owner's PC must
wait for that licence.

## 3. Blender techniques considered

| Element | Technique chosen | Why |
|---------|------------------|-----|
| Head | Ellipsoid mesh, layer-weight emission ramp (white core to orange rim), mild subsurface | Gives the "lit from within" look without volumetrics (cheap, deterministic). |
| Eyes | Glossy spheres, procedural iris ramp, emissive catch-light, lid shells driven by rotation | Lids give blink, squint, sad and angry slants from one control each. |
| Mouth | One small mesh with shape keys (smile, open, frown); talk is a periodic driver | Shape keys are the standard, cheapest facial control. |
| Flame | Curves objects with per-strand attributes + one geometry-nodes group (grow, rise, sweep, swirl, periodic noise) | Brush-stroke flames like the sheet; one node group serves head, hands, tail and smoke. Periodic noise sampled on a circle makes every clip loop exactly. |
| Embers | Points + geometry nodes, modular rise with an integer number of cycles per loop | Seamless loops; amount and speed are controls. |
| Rig | Armature (root, body, head, arms, legs); limbs are skin-modifier tubes with an Armature modifier | Small, robust, scriptable. |
| Controls | One `EMBER_CTRL` empty, every expression a custom property; simple-expression drivers | Files work without Python auto-run; any new emotion is a new row in `states.json`, not a rebuild. |
| Look | Eevee, AgX, orthographic camera; glow in post (numpy) | Bloom must create alpha for transparent sprites, which the compositor cannot. |
| Volumetric fire / Mantaflow | Rejected | Minutes per frame, not art-directable to brush strokes, not loopable. |

## 4. Getting Blender animation into the Flutter companion

| Option | Visual fidelity | Runtime cost | Memory | Dependency | Verdict |
|--------|-----------------|--------------|--------|------------|---------|
| (a) Recreate as a fragment shader | Low for a face, eyes, limbs and painted strokes | Like existing companions (1-2 ms GPU) | Tiny | None | Rejected: fidelity |
| (b) Pre-rendered transparent sprite loops (WebP atlases) | Highest: what Blender renders is what ships | One textured quad per frame | Bounded: only the active and previous clip decoded | None (Flutter decodes WebP) | **Selected (to be confirmed by measurement)** |
| (c) Layered 2.5D rig in Flutter (body/face/flame layers) | Medium; flames lose depth | Several quads + transforms | Lower than (b) | None | Kept as fallback if (b) memory is too high |
| (d) Real-time 3D (glTF) in Flutter (`flutter_scene`) | Lower than Eevee (no bloom, no painted look) | Highest | 3D runtime | New experimental package | Rejected: dependency, risk |
| (e) Video with alpha | High | Decoder per frame | Low | No Windows alpha video in Flutter | Rejected |
| (f) Rive / Lottie | Vector look, not the painted one; re-authoring outside Blender | Low | Low | New package | Rejected: not Blender, fidelity |

Measured facts already known (living companions phase, same GPU): Solar shader ~1 ms, Lunar 1.57 ms per frame at
companion size; a sprite blit is far below either. The open question for (b) is memory, settled in section 5.

## 5. Sprite budget (to be confirmed)

Largest display: companion mode 320 dp. Cell 320 px, 24 fps. A 48-frame clip is 320x320x4x48 = 19.7 MB decoded;
96 frames 39 MB. The widget keeps the active clip and, during a cross-fade, the previous one; others are decoded on
demand (async, off the UI thread). Ceiling: two 96-frame clips = 79 MB. A "compact" quality tier can halve the cell.
