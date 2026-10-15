# Fidelity checkpoint 3 - blind critique (2026-10-15)

## What changed since checkpoint 2

The pack was rebuilt after the CP2 repairs:
- The matte keeps "darker than background" alpha only near the body and inside the depleted smoke box.
- Faint glow is smoothed.
- The crop edge is feathered.
- Lifted sparks no longer leave holes.
- There is no turbulence around the feet.
- The backdrop pool now sits in the cell frame.

Pack: `cp3/reviewer{1,2}/` (key: `cp3_key/key.json`). Two new fresh reviewers saw it blind and read-only, using the
same 7-dimension rubric. New anchor: `ref_reframed`, the sharp panel scaled to 94 % and shifted, which measures the
top of the scale. V2 strips use the app's own framing and backdrop, on the Solar Ember surface.

| State | Candidate | R1 | R2 | Mean | Motion R1/R2 |
|---|---|---|---|---|---|
| idle | **V2** | 82.9 | 77.1 | **80.0** | 7 / 7 |
| idle | ref_reframed | 98.6 | 100 | 99.3 | - |
| idle | ref_copy (blurred) | 81.4 | 78.6 | 80.0 | - |
| idle | video | 50.0 | 50.0 | 50.0 | - |
| idle | V1 | 41.4 | 41.4 | 41.4 | - |
| joyful | **V2** | 81.4 | 78.6 | **80.0** | 7 / 7 |
| joyful | ref_reframed | 98.6 | 100 | 99.3 | - |
| joyful | ref_copy | 81.4 | 78.6 | 80.0 | - |
| joyful | video | 37.1* | 48.6 | 42.9 | - |
| joyful | V1 | 47.6* | 37.1 | 42.4 | - |
| fierce | **V2** | 77.1 | 77.1 | **77.1** | 6 / 6 |
| fierce | ref_reframed | 98.6 | 100 | 99.3 | - |
| fierce | ref_copy | 81.4 | 78.6 | 80.0 | - |
| fierce | video | 51.4 | 54.3 | 52.9 | - |
| fierce | V1 | 37.1 | 37.1 | 37.1 | - |
| depleted | **V2** | 80.0 | 74.3 | **77.2** | 7 / 7 |
| depleted | ref_reframed | 98.6 | 100 | 99.3 | - |
| depleted | ref_copy | 81.4 | 78.6 | 80.0 | - |
| depleted | video | 48.6 | 47.1 | 47.9 | - |
| depleted | V1 | 37.1 | 37.1 | 37.1 | - |

\* For joyful, reviewer 1's descriptions of candidates C and D do not match the files. Checked against the images:
C is the V1 render and D is the video frame, but the reviewer described C as "different artist" and D as "3D
render". Its two scores are therefore attributed by its descriptions: V1 37.1, video 47.6. The table keeps the
transcribed values against the key, marked *. This affects only the anchors, not V2.

**Verdict for CP3: AC-2a NOT MET.** V2 scores 74-83 per reviewer and 77-80 mean per state.

**Calibration:** the top anchor works (99-100). A sharp, reframed copy of the painting is scored as the painting.
The blurred copy sits at about 80; the video at 43-53, below its old 63-67 prior on the V1 rubric; V1 at 37-42.

V2 now lands level with "the painting, blurred". The reviewers name the remaining gap:
- the halo and glow read larger and stronger than on the sheet (orange glow over a near-black canvas instead of
  the painted brown);
- fierce: the top curl turns maroon and opaque in frames 2-4, as turbulence moves its thin strokes over the
  backdrop;
- depleted: the body and legs read washed out, and the smoke reads faint;
- motion: breathing is barely visible, and joyful's body never moves. That is partly an artefact of the pack:
  two hops per loop sampled at quarter-loop frames always land on the same phase.
