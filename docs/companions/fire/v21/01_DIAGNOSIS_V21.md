# Ember V2.1 - Phase 1: Research and Diagnosis

Branch `phase/fire-companion-v21-20261015`, cut from V2's final commit `b73bd26c`. Local only.

## Acceptance criteria for this diagnosis

- D-1: every claim below cites a file, a measurement or a picture that can be re-run.
- D-2: the gap is split into character, presentation and animation fidelity, with evidence for each.
- D-3: the cause of the gap is named before any change is made, and the smallest change that addresses it is chosen.
- D-4: options that were considered and not taken are listed with the reason.

## 1. What V2's own evidence already showed

| Evidence | Finding |
|---|---|
| V2 `cp8_RESULTS.md` | Every V2 frame scored the same as the unanimated cut-out (`still_in_app`), 80.5-83.5. Animation cost about 0. |
| V2 `cp5_RESULTS.md` | The unanimated painting cut out and shown the app's way scored 69-81; on its own background, 100. |
| V2 `cp6_RESULTS.md` | A "painting card" was tried, but only as a downscaled 4-frame strip (a format later shown to cost about 6 points). It was never re-tested as single frames. |
| Reviewer notes CP2-CP8 | Repeated named costs: dark surround, lost background brush strokes and swirls, translucent strokes reading differently, crest and smoke changing colour, signature and floor texture gone. |

So **character** fidelity was not the main problem: the pixels of the character are the painting's own pixels, and a
frozen cut-out scored the same as the animation. **Animation** cost was about zero. The cost was in
**presentation**.

## 2. New findings in V2.1

### F-1: the app crops Ember, and V2's packs never showed it

The companion host draws every companion through `LivingCompanion` (`uri_ui/lib/living/companion/living_companion.dart`):
the cell is drawn at `presenceScale` = 0.50 / bodyRadius = 0.50 / 0.42 = 1.19 times the box, then faded to a disc by
`SoftDisc` (`uri_ui/lib/living/voice/companion_presence.dart`): opaque to 72 % of the radius, zero at the box edge.

V2 framed the cell around the neck with the feet at 95.5 % of its height. Combined with the 1.19 zoom and the disc,
the feet, the lower robe and the crest tip fall in or beyond the fade. The V2 live screenshot
(`docs/companions/fire/v2/evidence/live/run4_first/first-05-idle-brain-ready.jpg`) shows exactly this: Ember's lower
body fades out.

Measured share of the character's alpha mass that the app actually shows (frame 0; script
`scripts/fire_companion/diag_v21.py`, output `evidence/diagnosis/diag_v21.json`, added in review R1-07):

| State | V2 | V2.1 framing |
|---|---|---|
| idle | 79 % | 96 % |
| joyful | 91 % | 98 % |
| fierce | 80 % | 95 % |
| depleted | 89 % | 98 % |

V2's blind packs showed the square cell without the zoom and the disc. The crop is real geometry. How much of the
change from V2's reported 82 to FP-21's 72-78 it explains is **not measured**: the rubric (7 -> 10 dimensions, 4 of
them presentation) and the reviewer panels changed at the same time. In P1, V2's character % (82.2-82.5) equals its
V2-era score, and V2 sits level with the blurred-copy anchor under both protocols (correction after review R1-02; the
first version said the 82 "was measured on a more favourable view").

### F-2: the cut-out discards the painting's background, which carries the style

`layers.py` models each panel as `src = bg * (1 - a) + F * a` and deliberately suppresses faint alpha, so background
brush strokes, swirls and distant glow are in neither the layer nor the smooth plate `bg`. V2's backdrop pool was that
smooth plate, blurred again (8 px). The strokes are therefore lost, which is what reviewers kept naming.

They can be recovered: what lies behind the layer is `(src - F * a) / (1 - a)` wherever the layer is not opaque.
Under the opaque head and body the smooth plate stands in; those areas are only uncovered by a few pixels of motion.
When nothing moves, layer over this backdrop reproduces the painting.

Limitation (review R1-05, disclosed): where `layers.py` clipped `F` to [0, 1] (bright flame cores at low alpha) and
where faint flame fringes fell under the alpha floor, part of the flame's own light stays in the **static** backdrop
(p99 difference from the plate about 0.18-0.20 at alpha 0.02-0.3). When the flames move, that residue does not, which
can read as faint ghosted wisps; one P1 reviewer noted it. Animation artefact scores were not worse than V2's. Since
`73e84a6d` the shipped build uses the backdrop only as the depleted clip's 60 % haze.

### F-3: the evaluation mixed character and presentation, and had no presentation control

See `03_FIDELITY_PROTOCOL_V21.md` section 1. The new protocol scores character and presentation separately, shows
every candidate as the app shows it, and adds `painting_app`: the unmodified painting in the app presentation. If
that control does not reach 90, the presentation, not Ember, sets the limit for this rubric and panel size (see
`evidence/fidelity/P1_P2_RESULTS.md` for how strong that reading is).

## 3. Answer: where the 82 % came from

Mostly **presentation**: the cut-out on near-black loses the background brushwork, glow context and floor light.
The app's disc and zoom then crop the figure, a cost V2's measurement did not include.
**Character** distortion is small; reviewers see the same character. **Animation** is about zero (CP7, CP8).
**Methodology** also contributed: presentation was not measured separately, the app view was not measured, and
there was no presentation control.

## 4. Approaches considered

| Approach | Verdict | Reason |
|---|---|---|
| Recover the painted background (texture backdrop) | **Taken** | Restores exactly the strokes, glow and floor reviewers named. Precomputed in the atlas; zero runtime cost. |
| Reframe inside the host's disc (Ember's own frame config) | **Taken** | Fixes F-1 with no Dart change and no change to the shared host. |
| Adaptive edge matting / alpha refinement | Not needed | With the painted background behind it, the matte edge is no longer seen against a foreign colour. |
| Dynamic background-aware glow (runtime) | Rejected | Needs a shader or per-frame compositing; V2 measured 0.3 % GPU and the gain would be invisible once the painted glow is back. |
| Layered depth and lighting (parallax) | Rejected for now | Adds motion the painting does not have; risks the identity; no evidence it raises fidelity. |
| Shader-based transitions | Not needed | V2's premultiplied cross-fade already blends whole frames; backdrops of all panels are similar browns. |
| Change the shared host (no disc for Ember) | Not taken (AMBER) | Touches accepted UI used by every companion. Kept as a fallback proposal if the in-disc framing cannot reach 90. |
| Raise atlas resolution | Deferred | Only if the qualification round shows a resolution cost; costs VRAM. |

## 5. Smallest change chosen

Two configuration-level changes to the existing V2 pipeline, no new dependency, no new rendering path, no Dart
change:

1. `animate.Panel.backdrop` and a textured branch in `export_v2.Framing.aura`, enabled by the `stage` block in
   `expressions.json`. With V2's `frame` and no `stage`, the code path is V2's (checked: those settings reproduce the
   shipped V2 atlas cell to WebP noise, mean absolute difference 0.0022, `diag_v21.py`). Note (R1-06): a stage
   `strength` replaces every clip's `motion.aura` strength; the transparent stage uses `strength: 0` to switch the
   V2 pool off.
2. `expressions.json` `frame`: a square of 643 panel pixels centred on the panel, so the app's box shows 540 panel
   pixels (about the painting's own composition) inside the disc.

The nine clips, their motion, the blink overlay and every runtime file are unchanged.
