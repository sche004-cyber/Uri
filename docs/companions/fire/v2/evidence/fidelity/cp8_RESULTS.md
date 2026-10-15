# Fidelity checkpoint 8 - final (2026-10-15)

Built from `fce51708`. Changes since checkpoint 7:
- The glow smoothing no longer touches painted sparks.
- The depleted robe is solid inside its painted outline.

The format is the same as CP7: single full-resolution frames, with V2 scored as the minimum of its frames. Two new
fresh reviewers. Pack `cp8/`, key `cp8_key/key.json`. Both reviewers also ran read-only, in-memory pixel checks. The
letter shuffle is seeded, so the letters match CP7.

| State | v2_worst | v2_mid | **V2 (min), mean** | still_in_app | ref_reframed | ref_copy | V1 |
|---|---|---|---|---|---|---|---|
| idle | 83 / 84 | 83 / 84 | **83 / 84 -> 83.5** | 83 / 84 | 100 / 100 | 81 / 81 | 36 / 34 |
| joyful | 81 / 83 | 81 / 83 | **81 / 83 -> 82.0** | 81 / 83 | 100 / 100 | 81 / 81 | 34 / 34 |
| fierce | 80 / 81 | 80 / 81 | **80 / 81 -> 80.5** | 80 / 81 | 100 / 100 | 81 / 81 | 34 / 33 |
| depleted | 81 / 84 | 81 / 84 | **81 / 84 -> 82.5** | 81 / 84 | 100 / 100 | 81 / 83 | 36 / 36 |

(reviewer 1 / reviewer 2)

## Verdict

**AC-2a NOT MET (final).** The means are 80.5-83.5, against a target of >= 90.

## Trend over all checkpoints

| | CP2 | CP3 | CP4 | CP5 | CP6 | CP7 | CP8 |
|---|---|---|---|---|---|---|---|
| V2 mean range | 74-85 | 77-80 | 74-78 | 71-75 | 72-79 (card) | 83.5-85.8 | 80.5-83.5 |
| Format | strip | strip | strip | strip | strip | single | single |

Correction (review R2-03): the "V2 mean range" row first read CP5 "72-77", CP6 "74-77" and CP7 "84-86". The values above are the two-reviewer means recomputed by `decode_raw_scores.py`.

From CP7 to CP8, with almost unchanged art, the scores moved by -1 to -4. The two changes (sparks, robe) are within
the spread between reviewers. They were still repaired, because they were concrete defects.

## Conclusion from the whole series

1. On this rubric, V2 scores at the level of "the painting, blurred" (77-87). The painting itself scores 98.6-100.
   V1 scores 30-41, and an AI redraw of the same character 40-55.
2. The animation costs nothing measurable. In CP7 and CP8, every V2 frame scored identically to the unanimated
   cut-out.
3. What remains is the cost of lifting the character out of its painting:
   - It sits on the app's near-black canvas instead of the painted brown.
   - The translucent strokes, the crest swirl and the smoke depend on that brown to read as painted.
   - The signature and the background brush texture are gone.
   - Sparks drift, so the full spark field is never seen in one frame.

   CP6 tested a card presentation on the painting's background plate and saw no gain while V2 was still shown as
   strips; it was not re-tested in the single-frame format.
4. Further tuning would be tuning to reviewer noise. The work stops here, as planned. The threshold is not
   lowered; the gap is reported, and the presentation choice goes to the owner (see the final report).
