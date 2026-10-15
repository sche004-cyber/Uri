# Fidelity checkpoint 2 - blind critique (2026-10-15)

Pack: `cp2/reviewer{1,2}/`, built by `scripts/fire_companion/critique_pack_v2.py` from commit `8a585108`. The
letter key is in `cp2_key/key.json`; the reviewers were not given it. There were two fresh general-purpose
subagents. Neither made the images, both worked read-only, and they used the 7-dimension rubric of AC-2a.

The scores below are transcribed from the reviewers' reports and decoded with the key. Fidelity % is the mean of the
7 dimensions × 10.

| State | Candidate | Reviewer 1 | Reviewer 2 | Mean | Motion (strip) |
|---|---|---|---|---|---|
| idle | **V2** | 84 | 85.7 | **84.9** | 6 / 6 |
| idle | ref_copy (degraded panel) | 77 | 77.1 | 77.1 | - |
| idle | video redraw | 53 | 50.0 | 51.5 | - |
| idle | V1 | 47 | 48.6 | 47.8 | - |
| joyful | **V2** | 80 | 85.7 | **82.9** | 6 / 6 |
| joyful | ref_copy | 77 | 77.1 | 77.1 | - |
| joyful | video | 53 | 48.6 | 50.8 | - |
| joyful | V1 | 43 | 45.7 | 44.4 | - |
| fierce | **V2** | 80 | 80.0 | **80.0** | 6 / 4 |
| fierce | ref_copy | 77 | 77.1 | 77.1 | - |
| fierce | video | 60 | 51.4 | 55.7 | - |
| fierce | V1 | 43 | 41.4 | 42.2 | - |
| depleted | **V2** | 74 | 74.3 | **74.2** | 7 / 6 |
| depleted | ref_copy | 77 | 77.1 | 77.1 | - |
| depleted | video | 53 | 50.0 | 51.5 | - |
| depleted | V1 | 40 | 40.0 | 40.0 | - |

**Verdict for CP2: AC-2a NOT MET.** V2 scores 74-86 against a target of >= 90 per state.

**Calibration (AC-2b): MISCALIBRATED.** Two anchors fell outside +-10 points of their expected values:
- The degraded copy of the panel itself was expected near 100 and scored 77. Both reviewers capped the lighting
  and material dimensions for blur.
- The video redraw had a V1-critique prior of 63-67 and scored 48-56.

V1 matched its prior (40-48 against 41-51). The new rubric and reviewers score more harshly at the top of the scale.
This is recorded, not corrected: AC-2 is judged on the raw scores. The next session adds an undegraded panel anchor,
to measure where "the painting itself" lands on this rubric.

Defects both reviewers named, with their cause in V2:
1. **Halo.** A muddy, boxy glow halo with speckled edges, and a hard cut at the crop edge. Cause: low-alpha glow
   carried background brush texture, and alpha was not feathered at the panel crop border.
2. **Dark specks and rings among the sparks, dark-tipped tendrils, dark streaks in the fierce crest.** Cause: the
   minimum-alpha matte keeps "darker than background" alpha outside the body. Semi-transparent strokes lose the
   painting's brown background and read darker on a near-black canvas.
3. **Fierce pose jump between frames; ground puddles under the feet.** Cause: flame turbulence was applied to the
   luminous ground glow next to the legs, weighted by distance from the head, which is largest at the feet.
4. **Depleted: body, legs and smoke nearly lost on black.** Cause: dark elements depend on the painting's mid-brown
   background for contrast.
5. **Idle reads nearly static** across 4 frames taken at quarter-loop spacing.
