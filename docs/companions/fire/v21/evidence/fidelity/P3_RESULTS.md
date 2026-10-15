# FP-21 exploratory round P3 - transparency variants

- **Why this round.** The owner directive "URI UI V2 compatibility" requires a transparent Ember (protocol change
  log C-2).
- **How it was run.** The P2 prompt (no animation task). Three fresh reviewers. Raw answers are in `p3_raw/`;
  transcripts are kept local, with hashes. The access audit is clean.
- **Validity.** The round is valid.
- **Decoded tables:** `p3_decoded.md`.
- **Presentation.** Every candidate is shown in today's app view: `#130F0B` canvas, presence scale and SoftDisc.

| State | painting_app (control) | V2.1 painted (opaque) | t1 glow (transparent) | t2 glow + 35 % haze | t3 glow + 60 % haze | ref_copy | V1 |
|---|---|---|---|---|---|---|---|
| idle | 86.0 | 86.0 | 79.7 | 79.7 | 79.7 | 79.2 | 36.8 |
| joyful | 85.8 | 85.8 | 79.7 | 79.7 | 79.7 | 79.2 | 37.2 |
| fierce | 86.0 | 86.0 | 79.7 | 79.7 | 79.7 | 79.2 | 35.3 |
| depleted | 85.7 | 85.7 | **73.8** | 75.0 | **79.0** | 79.3 | 38.0 |

## Reading

1. **The cost of going transparent.**
   - On this dark canvas a transparent Ember scored about 6 points below the opaque painted build (86 -> 80).
   - For depleted the drop was 12 points without the haze, because its dark smoke needs a backdrop.
   - Reviewers named three costs: an "added halo", fewer distant embers, and a near-black surround in place of the
     painted brown.
2. **The haze.** It made no difference in idle, joyful or fierce, where reviewers scored the three variants
   identically. It helped depleted: 73.8 without it, 79.0 at 60 %.
3. **Choice (the smallest evidence-based change).** Glow only for every clip, plus the 60 % haze for depleted only.
   This is what `73e84a6d` ships.
4. **This is exploratory.** The qualification result for the shipped transparent build is Q2 (`Q2_RESULTS.md`).
