# Fidelity checkpoint 7 - single full-resolution frames (2026-10-15)

## What changed

**Format correction (CP6, finding 3).** V2 is no longer shown as a downscaled 4-frame strip. It appears as two
separate full-resolution frames as the app shows them:
- `v2_worst`: the frame the automated scorer rates furthest from the painting;
- `v2_mid`: half a loop later.

The V2 score is the **minimum** of the two, so the weakest-frame rule is kept.

**Art built after the CP6 repairs:**
- rigid joyful hop;
- breathing of 1.2-1.5 px;
- one cap on all flame motion.

**Controls:** `still_in_app` (the unanimated cut-out in app presentation), `ref_reframed`, `ref_copy` and V1.

Two new fresh reviewers. Pack `cp7/`, key `cp7_key/key.json`.

## Results

| State | v2_worst | v2_mid | **V2 (min)** | still_in_app | ref_reframed | ref_copy | V1 |
|---|---|---|---|---|---|---|---|
| idle | 87.1 / 80.0 | 87.1 / 80.0 | **87.1 / 80.0 -> mean 83.6** | 87.1 / 80.0 | 98.6 / 98.6 | 77.1 / 85.7 | 35.7 / 32.9 |
| joyful | 85.7 / 84.3 | 85.7 / 84.3 | **85.7 / 84.3 -> mean 85.0** | 85.7 / 84.3 | 98.6 / 98.6 | 77.1 / 85.7 | 30.0 / 34.3 |
| fierce | 87.1 / 81.4 | 87.1 / 81.4 | **87.1 / 81.4 -> mean 84.3** | 87.1 / 81.4 | 98.6 / 98.6 | 77.1 / 85.7 | 32.9 / 32.9 |
| depleted | 88.6 / 82.9 | 88.6 / 82.9 | **88.6 / 82.9 -> mean 85.8** | 88.6 / 82.9 | 98.6 / 98.6 | 78.6 / 87.1 | 35.7 / 34.3 |

(reviewer 1 / reviewer 2)

## Verdict

**AC-2a NOT MET.** The per-state means are 83.6-85.8, against a target of >= 90. Reviewer 2 is below 85 in idle,
joyful and fierce.

## Findings

1. **The format confound was real.** With the same art, V2 rose from 74-79 (CP4, strips) to 80-89 (single
   frames).
2. **The animation now costs nothing measurable.** Both reviewers scored each V2 frame exactly equal to the
   unanimated cut-out, in every state. Reviewer 1, who ran read-only pixel checks, confirmed that the three images
   differ, by a mean absolute difference of 1-8 per channel. The remaining gap of about 15 points is the cut-out
   itself.
3. **Named remaining costs:**
   - **Joyful:** the large painted embers had become fine dust. Cause: the CP3 glow smoothing also smoothed the
     sparks. Repaired for CP8.
   - **Depleted:** the robe and legs read pale and ghostly. Cause: the matte gives a grey robe partial alpha.
     Repaired for CP8 with a solid robe inside the painted outline.
   - **Fierce:** the crest swirl reads as a dark brown streak, and the eyes read slightly rounder with white
     catch-lights. The catch-lights are in the painting; reading them as rounder is a perception of the cut-out.
   - **All states:** a darker, vignetted surround instead of the painted brown. The signature has been removed
     (intentional: it is the artist's mark, not the character).
