# Ember V2 - Fidelity Evaluation Method

The method was defined before scoring (AC-2) and refined during the work. Every refinement is recorded below with
its reason; no threshold was lowered.

## Primary measure: blind, calibrated critique (AC-2a/b)

1. **Pack.** `scripts/fire_companion/critique_pack_v2.py --tag cpN` writes, for each of the four reference states,
   the target panel and the candidates under letters. The letters are shuffled per reviewer with a fixed seed, and
   the key is written to `cpN_key/`, which the reviewers are never given.
2. **Candidates.**
   - V2 as the app shows it: the app's cell framing and backdrop, on the Solar Ember surface `#130F0B`, as a strip
     of 4 frames that includes the frame the automated scorer ranks furthest from the painting.
   - The anchors listed below.
3. **Reviewers.** Two fresh general-purpose subagents per checkpoint. None of them made the images or saw a previous
   round. They work read-only and score 7 dimensions from 0 to 10:
   - silhouette and proportions;
   - head shape and surface;
   - eyes and expression;
   - flame density, shape and colour;
   - body proportions and pose;
   - painterly lighting and material;
   - emotional consistency.

   Fidelity % is the mean × 10. Strips also get a motion-plausibility score and an artefact list.
4. **Pass rule.** For each state, the mean of the two reviewers must be >= 90 % and neither reviewer may score the
   state below 85 %. Scores are transcribed verbatim and decoded with the key in `cpN_RESULTS.md`.
5. **Anchors.**

   | Anchor | Meaning | Added |
   |---|---|---|
   | `ref_reframed` | The painting, sharp, scaled to 94 % and shifted 5 px: top of scale | CP3 |
   | `ref_copy` | The painting, blurred (2 px), shifted 3 px, JPEG q60 | CP2 |
   | `video` | The owner's AI video redraw key frame: same character, other hand | CP2 |
   | `v1` | Ember V1 render | CP2 |

   A session is valid when `ref_reframed` scores >= 90 and V1 scores below the video. CP2 had no top anchor and is
   recorded as miscalibrated.

## Secondary measure: automated scorer (AC-2c, regression only)

`scripts/fire_companion/score_v2.py` scores every 6th frame of each reference clip with V1's
`fidelity_score.py --aligned`. The frame is composited over the panel's own background plate, in the panel's pixel
frame. The results are reported as the median and the minimum over the loop.

V2 frames are made from the painting, so on this scale they score near or above the "degraded reference" anchor by
construction. The number shows how far animation moves a frame away from the painting. It is not evidence of
fidelity.

`--aligned` was added in V2 because automatic registration is fragile when candidate and panel differ in extent. A
control showed this: the reference itself, cropped with a slightly different box, scored 39 on depleted when
registered automatically. In aligned mode the reference scores 115-143 against itself.

## Checkpoints run

| CP | Built from | Purpose | Result file |
|---|---|---|---|
| 1 | Layer cut-out only | Automated scorer on the cut-out. It exposed the registration fragility above. | `cp1/*.json` |
| 2 | First animation (`8a585108`) | Blind critique, 2 reviewers | `cp2_RESULTS.md` |
| 3 | After the CP2 repairs | Blind critique, new reviewers, top anchor added | `cp3_RESULTS.md` |
| 4 | After the CP3 repairs | Blind critique, new reviewers | `cp4_RESULTS.md` |

## Known limits of the method

- **Motion.** Reviewers judge motion from 4 still frames, not from playback. Live screenshots and the frame strips
  are the motion evidence, so motion scores are indicative only.
- **Reviewer slips.** Reviewers are language models looking at images, and one mislabelled two anchors in CP3. The
  results file records such cases instead of silently fixing them.
- **Derived expressions.** The functional expressions (listening, thinking and so on) have no reference panel.
  They are judged for identity consistency in the live run, not scored against the 90 % target.
