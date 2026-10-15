# Fidelity checkpoint 6 - option test: V2 as a "living painting card" (2026-10-15)

## Why this checkpoint

CP5 suggested the cost came from presentation. This checkpoint tests the obvious remedy: V2's animated frames
over the painting's own background plate, as a whole panel softly vignetted into the canvas. The cut-out V2 was
replaced by `v2_card`; `still_in_app` was kept.

Pack: `critique_pack_v2.py --tag cp6 --card`. Two new fresh reviewers. Key: `cp6_key/key.json`.

## Results

| State | ref_reframed | still_in_app | **v2_card (strip)** | ref_copy (blurred) | V1 |
|---|---|---|---|---|---|
| idle | 100 / 100 | 81 / 78.6 | **73 / 71.4** | 79 / 82.9 | 34 / 38.6 |
| joyful | 100 / 100 | 80 / 81.4 | **79 / 78.6** | 79 / 81.4 | 30 / 35.7 |
| fierce | 100 / 100 | 81 / 81.4 | **70 / 77.1** | 79 / 81.4 | 31 / 35.7 |
| depleted | 100 / 100 | 81 / 81.4 | **73 / 77.1** | 79 / 81.4 | 34 / 35.7 |

(reviewer 1 / reviewer 2)

## Findings

1. **The card presentation does not lift V2.** It scored 70-79, the same as the cut-out V2 in CP3 and CP4. The CP5
   explanation, "presentation alone", is therefore **corrected**: presentation is not the whole cost.

2. **The pose and stretch claims were real.** Both reviewers reported body or leg changes between frames: joyful
   legs, the fierce stance and arms. A measurement confirmed them. Body pixels below the neck moved 2-6 px between
   frames (95th percentile up to 4.5 px), because breathing and the joyful hop stretched the figure between pinned
   feet and the neck. Flame displacement also reached 10-12 px, because the sway was added after the 6 px cap.
   Both are **repaired** for CP7:
   - joyful hops rigidly ("airborne");
   - breathing is 1.2-1.5 px;
   - one cap now covers all flame motion.

   After the repair, body deformation is <= 0.8 px at the 95th percentile and flame displacement is 2-8 px.

3. **Format confound.** V2 is always shown as a 1,792-1,960 px wide strip of 4 frames. The anchors are single
   448 px images. Reviewers see the strip downscaled, so each V2 frame appears at roughly a quarter of the target's
   resolution, a handicap similar to the blurred anchor, which scores about 80, just where V2 sits. CP7 therefore
   shows V2 as separate full-resolution frames. The strictest frame is kept: the frame the automated scorer rates
   furthest from the painting, plus a mid-loop frame, with V2 scored as the minimum of the two.
