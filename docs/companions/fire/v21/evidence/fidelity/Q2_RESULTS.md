# FP-21 qualification round Q2 - results (final round)

- **Build.** The pack was built from `73e84a6d`, the transparency-ready build that is now the shipped default
  (`critique_pack_v21.py --tag q2 --reviewers 3 --seed 3200`).
- **Rules.** Q1's prompt (only the round name changed), candidates and rules apply (protocol change log C-3).
- **Images.**
  - `painting_app` stays the painting in Q1's painted presentation, as a fixed control.
  - `v21_worst`, `v21_mid` and the animation frames show the shipped transparent build.
  - `v21_frame_only` is still V2.1 framing with V2's (opaque) pool. It is not a transparent candidate.
- **Reviewers.** Three fresh reviewers. Raw answers are in `q2_raw/`. The transcripts are kept local (hashes in
  `SHA256SUMS.txt`). The access audit is clean: each reviewer read only its own pack and wrote only its own answer.
- **Decoded tables:** `q2_decoded.md`.

**Round valid:** `ref_reframed` scored 98 for every reviewer and state, and V1 scored below the blurred copy throughout.

## Result

| State | V2.1 transparent, visual (r1 / r2 / r3 -> mean) | painting_app control | V2.1 character | V2 in the app | Pass |
|---|---|---|---|---|---|
| idle | 86 / 84 / 86 -> **85.5** | 88.3 | 92.5 | 77.2 | FAIL |
| joyful | 86 / 84 / 86 -> **85.3** | 88.8 | 92.2 | 77.8 | FAIL |
| fierce | 86 / 84 / 86 -> **85.8** | 89.3 | 93.1 | 77.0 | FAIL |
| depleted | 84 / 87 / 89 -> **86.8** | 89.2 | 92.8 | 77.2 | FAIL |

- **AC-F1 (final): NOT MET.** The visual means are 85.3-86.8 against >= 90. The lowest reviewer gave 84, below the
  85 floor.
- **AC-F3 met:** character 92.2-93.1 % against >= 90.
- **AC-F2 met:** V2.1 animation is within 5 points of V2's in every state (idle +1.7, joyful +1.2, fierce -4.2,
  depleted 0.0).

## Reading

1. **What transparency costs.**
   - In this panel the transparent build is 2.5-3.5 points below the painted-presentation control: 85.3-86.8
     against 88.3-89.3.
   - In P3 the transparent variants were about 6 points below. That is consistent within the about +-2 point
     uncertainty per round mean.
   - Reviewers named a "halo that reads slightly cut-out against flat black", fewer distant embers, and the lost
     painted backdrop.
2. **What the haze does for depleted.** Depleted, which keeps the painted backdrop as a 60 % haze, scored highest
   (86.8). That agrees with P3.
3. **Against V2.** V2.1 is still 8-10 points above V2 as users see it (77.0-77.8).
4. **Section 8.** This was the last round the protocol allows. The threshold is not changed. AC-F1 stays NOT MET
   unless the owner decides otherwise.

## Caveats

- The app view composites on flat `#130F0B` (R1-01). In a UI V2 transparent window, the actual background is the
  desktop, which this protocol does not score.
- The reviewer prompt mentions "a dark background with a soft round vignette"; see C-4 item 4.
