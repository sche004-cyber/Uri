# Fidelity checkpoint 4 - blind critique (2026-10-15)

## What changed after checkpoint 3

- The backdrop pool is larger and is forced to zero at the cell border.
- Turbulence displacement is capped: 6 px, and 4 px for fierce.
- Breathing is stronger: idle 3.5 px, depleted 2.2 px.
- Critique strip frames are sampled off the motion cycles (0, 0.3, 0.55 and the worst frame).
- Atlases are 9.7 MB on disk.

## How it was run

Pack `cp4/`, key `cp4_key/key.json`. The shuffle seeds are the same as in CP3, so the letters are the same. The
reviewers were two new fresh subagents, blind and read-only. The scores are transcribed from their reports and
decoded with the key.

## Results

| State | V2 R1 | V2 R2 | **V2 mean** | ref_reframed | ref_copy (blurred) | video | V1 | Motion R1/R2 |
|---|---|---|---|---|---|---|---|---|
| idle | 77 | 78.6 | **77.8** | 100 / 100 | 81 / 90 | 49 / 41.4 | 34 / 38.6 | 7 / 7 |
| joyful | 76 | 74.3 | **75.2** | 100 / 100 | 81 / 91.4 | 47* / 40 | 36* / 34.3 | 6 / 7 |
| fierce | 74 | 78.6 | **76.3** | 100 / 100 | 81 / 90 | 51 / 44.3 | 34 / 30 | 6 / 7 |
| depleted | 74 | 74.3 | **74.2** | 100 / 100 | 81 / 90 | 47 / 44.3 | 37 / 38.6 | 7 / 6 |

\* Reviewer 1 again described joyful C as the "different artist" and D as the "3D render". The key and the files
say the opposite: C is the V1 render (checked visually in CP3) and D is the video. Its values are attributed here
by its descriptions. This concerns the anchors only.

## Verdict

**AC-2a NOT MET.** V2 scores 74-79, slightly below CP3 (77-80). The change is within the spread between reviewers.

## Reviewer claims checked against the files

| Claim | Who | Check | Result |
|---|---|---|---|
| "Joyful frame 1: arms horizontal / hands at cheeks; pose jump to frame 2" | Both reviewers | Frames 1 and 2 of `cp4/reviewer2/joyful_candidate_C.png` compared side by side | **Not reproduced.** Both frames have the arms raised in the same V. They differ by the 5 px hop and by flame motion. Recorded as reviewer error. |
| "More saturated orange than the target" | Both reviewers, CP3 and CP4 | Measured in the character mask (alpha > 0.3), V2 frame 0 in app presentation against the painting | **Not a pixel difference.** Mean saturation: V2 0.607 against the painting 0.605 (idle), 0.527/0.525 (joyful), 0.583/0.579 (fierce), 0.379/0.384 (depleted). Mean absolute RGB difference: 0.8-5 %. The impression comes from the surroundings: a near-black canvas with a vignette instead of the painted brown. |
| "Fierce crest has a dark rust swoosh" | Both reviewers | The painting's own crest swoosh is a darker orange-brown stroke | Present in the painting. The animation makes it longer or shorter frame to frame. |
| "Depleted lower body semi-transparent / faded" | Both reviewers | The matte gives the grey robe partial alpha (its colour is close to the backdrop) | **True:** a real V2 limitation of the matte. |

This led to checkpoint 5 (`cp5_RESULTS.md`), a diagnostic. It adds the unanimated painting, shown in the same app
presentation, as an anchor. This separates what the presentation costs from what the animation costs.
