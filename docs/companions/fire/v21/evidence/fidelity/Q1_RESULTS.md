# FP-21 qualification round Q1 - results

- Pack built from commit `9933ca2b` (`critique_pack_v21.py --tag q1 --reviewers 3 --seed 3100`). The candidates and
  prompt are the same as P1 (prompt files differ from P1's only in the round name).
- Three fresh reviewers. Raw answers are in `q1_raw/reviewer<N>.json`. The transcripts are kept local, with their
  hashes in `q1_raw/SHA256SUMS.txt`.
- Access audit: each reviewer read only its own pack and wrote only its own answer. Reviewer 3's single Glob was on
  its own pack folder; the auditor lists that folder's parent.
- Full decoded tables: `q1_decoded.md`.

**Round valid** (protocol section 6): `ref_reframed` scored 95-97, and V1 scored below the blurred copy for every
reviewer and state.

## Result

| State | V2.1 visual (r1 / r2 / r3 -> mean) | painting_app control | V2.1 character | V2 in the app | Pass |
|---|---|---|---|---|---|
| idle | 84 / 88 / 85 -> **85.7** | 85.7 | 91.1 | 73.3 | FAIL |
| joyful | 84 / 88 / 86 -> **85.7** | 86.8 | 91.1 | 73.5 | FAIL |
| fierce | 84 / 88 / 86 -> **85.8** | 86.0 | 91.4 | 73.3 | FAIL |
| depleted | 84 / 89 / 86 -> **86.3** | 86.3 | 91.4 | 72.3 | FAIL |

**AC-F1: NOT MET.** The visual means are 85.7-86.3 against >= 90. The lowest reviewer gave 84, below the 85 floor.
AC-F3 (character >= 90) is met at 91.1-91.4. AC-F2 (animation) is met: V2.1 scored 76.7-78.3 against V2's 73.8-76.7.

## Reading

1. **V2.1 equals the control.** V2.1 scores the same as the unmodified painting in the same app presentation:
   - in all twelve state-reviewer pairs, within one point;
   - in joyful the min-of-two-frames rule puts V2.1 0.1-1.1 below the control, from ember density.

   This is the third valid round (P1, P2, Q1) to show it.
2. **The textured backdrop matters for depleted.** In Q1 the framing-only ablation lost the smoke plume, and two
   reviewers named it: character 87.5 against 91.4 for V2.1. In the other states the backdrop is within 1 point.
3. **The panel moves between rounds.** The same control scored 89.0 (P1), 85.3 (P2) and 85.7-86.8 (Q1). Reviewer
   panels differ by about 3-4 points. In every round the control stays below 90.
4. **What V2.1 gained over V2:** +12.4 to +14.0 points visual, about +14 character and +10 presentation, as users
   actually see it.

## Protocol consequence

Section 8 allows one repair and a round Q2. No repair is available that the evidence supports:
- V2.1 already equals the presentation control;
- P2 showed that no host presentation tested raises the control above 86.3.

The work stops here and reports NOT MET. The threshold is not changed.
