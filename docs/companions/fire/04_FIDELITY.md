# Ember - Visual Fidelity Evaluation

Status: TESTED. Target (AC-2): >= 90 per reference state, automated AND independent critique. **NOT MET in any state.**

## Method

Two independent measures, as the brief asked (not pixel similarity alone):

1. **Automated, reproducible** - `scripts/fire_companion/fidelity_score.py`, driven by `score_all.py`.
   - Reference: the four panels of `reference/uri_emotions_sheet.png` (labels excluded, Gemini mark masked).
   - Candidate: Blender renders from `companion_art/fire/ember.blend` at the comparison framing (448x480), frames
     1, 12, 24, 36 of each state's loop, post-processed exactly as the shipped sprites. Composited on the panel's
     backdrop colour and registered (uniform scale and translation only) so the character occupies the same box.
   - Components (weights): silhouette IoU (0.25), low-pass luminance SSIM (0.25), stroke-orientation flow (0.20),
     Lab colour distribution over the character (0.15), eye pair position/size (0.15).
   - Calibration: 100 = the panel against a mildly degraded copy of itself (blur, 3 px shift, JPEG q60);
     0 = a generic fire spirit (teardrop flame, two black eyes, stick body) drawn in the panel's own colours and
     bounding box. Both anchors go through the same registration as a candidate. Unclamped values are reported.
   - Informational point: an AI video redraw of the same character (owner-supplied video, key frames).
2. **Independent visual critique** - a separate reviewer that did not make the images scored nine dimensions
   (silhouette, proportions, eyes, expression, flame structure, colour, material, lighting, overall identity) 0-10 per
   state, and scored the video redraw the same way for calibration. Full table:
   `evidence/fidelity/independent_visual_critique.md`.

## Results (final scorer; renders from `companion_art/fire/ember.blend`, unchanged since 8a1438ec)

Evidence: `evidence/fidelity/fidelity_scores.json`, `evidence/fidelity/fidelity_sheet.jpg`.

| State | Automated, median of 4 frames (range) | Video redraw, automated | Independent critique | Video redraw, critique | Target |
|-------|--------------------------------------|-------------------------|----------------------|-----------------------|--------|
| Idle | 0.3 (0.0 - 0.7) | 0.0 (unclamped -8.5) | 51 % | 66 % | 90 - NOT MET |
| Joyful | 13.2 (12.3 - 15.6) | 7.0 | 41 % | 63 % | 90 - NOT MET |
| Fierce | 6.1 (3.9 - 8.3) | 3.9 | 46 % | 66 % | 90 - NOT MET |
| Depleted | 21.5 (18.9 - 32.3) | 18.8 | 50 % | 67 % | 90 - NOT MET |

Eye-component self-check (panel against its own degraded copy, `eye_self_check` in `fidelity_scores.json`):
idle 0.97, joyful 0.50, fierce 0.50, depleted 0.84. Below 0.9 the eye component is not trustworthy for that panel: the joyful and fierce eyes have bright
irises the detector cannot isolate, so they score "unknown" (0.5) for every candidate.

## What the numbers mean

- The automated scale measures similarity to one specific painted panel. The same character redrawn by another
  artist (the AI video) scores 0 to 19 on it, and the independent critic places "recognisably the same character,
  different artist" at about 63-67 %. On that scale 90 means reproducing the painting itself, not the design. A
  real-time 3D recreation with this shading approach cannot reach it; this is a property of the target as specified,
  not only of this implementation.
- Ember scores at or above the video redraw on the automated scale in every state, and 15-22 points below it in the
  critique. The critic's verdict: the same idea, not yet the same character.
- Largest gaps (critic, all states): flame structure (thin radial strands vs a dense swept painterly mane with a
  white-hot core), head material (crisp matte ellipse vs a soft emissive head melting into the flame), per-state
  poses (no joyful kick, no depleted slump), joyful eyes (round black vs squinted brown smiling), painterly surface.
- Recommended next step if the owner wants higher fidelity: flame rebuilt as swept emissive sheets merging with the
  head, NPR/painterly shading pass, per-state pose and eye work. Estimated as a new milestone, not a tweak.

## Correction history (nothing below was deleted)

| When | Change | Effect on reported scores |
|------|--------|---------------------------|
| 2026-10-14, before any candidate render | Registration of the candidate to the reference box added (framing dominated the first calibration). | Calibration only. |
| 2026-10-14, iteration rounds r2-r12 | Look tuned over 12 rounds with the first scorer (comparison sheets kept in `evidence/fidelity_iterations/`; per-round scores were printed, not saved: UNVERIFIABLE). | Superseded: the first scorer's eye component measured the backdrop (review R1-04). |
| 2026-10-15, review R1-04 | Eyes must lie inside the character and be 12 L* darker than the backdrop; both anchors registered; unclamped reported. | Intermediate medians (idle -8.5, joyful -6.9, fierce -9.7, depleted 19.3) were printed in the session but that output was not preserved: UNVERIFIABLE from the evidence folder. Superseded by the final values. |
| 2026-10-15, review R2-03 | Eyes must form a side-by-side pair of at least 0.1 % of the frame each; an undetectable pair scores 0.5. | Final values above. |
| 2026-10-15, review R1-02 | `02_STATE_MATRIX.md` had said fierce was "qualified for fidelity". It never was. | Wording corrected. |
