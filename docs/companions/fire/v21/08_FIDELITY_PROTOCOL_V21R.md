# Ember V2.1 - Fidelity Protocol FP-21R (reference-relative presentation)

Status: **LOCKED before its only round (R1) is built.** This file is committed before
`critique_pack_v21r.py` writes any pack. Any later change goes in the change log at the end.

**Approval status: PROPOSED, NOT APPROVED.** This protocol changes how presentation fidelity is judged.
Its results count towards qualification only once the owner explicitly approves it (section 8). Until then:
- AC-F1, as defined in `00_PLAN_AND_ACCEPTANCE_V21.md` and FP-21, stays the rule of record;
- its last result (Q2) stays **NOT MET**.

## 1. Why

The owner's direction for the final Ember qualification (2026-10-15) has three parts:
- Keep the 90 % character-fidelity requirement.
- Measure character fidelity and presentation fidelity separately.
- Judge presentation fidelity against the original reference rendered under equivalent application and
  transparency conditions.

FP-21 cannot answer that question, for three reasons:
1. **Mixed measure.** Its pass rule (AC-F1) averages character and presentation into one visual score.
2. **Wrong control.** Its control, `painting_app`, is the painting with its painted, opaque background.
   - The owner has since made transparency a permanent requirement for all URI companions.
   - No transparent companion can carry that background.
   - So part of the gap to the control is the mandated transparency itself, not Ember.
3. **Dark surround only.** It scores Ember on the dark app canvas.
   - A transparent companion is seen over the user's desktop, which is often light.

## 2. The reference under equivalent conditions

**`painting_t` (new control).** The unanimated painting, given exactly the treatment that the shipped Ember frames
get. It isolates what Ember's animation and re-rendering change from what transparency and the host change.
- **Pixels.** The painting's own pixels (after the rig's `erase` only), cut out with the alpha of Ember's layer
  model.
- **Soft edges.** Where the alpha is below 0.85, the layer colour is used. That is where the painting mixes
  character and background.
- **Stage.** Each clip's shipped transparent stage, from `expressions.json`:
  - the emissive glow for every state;
  - the 60 % painted haze, held near the figure, for depleted.
- **Host.** The 320 px atlas cell, the WebP q88 round trip, the presence scale and the SoftDisc, exactly as for
  Ember (FP-21 section 2).

**Surrounds.** Each transparent image is shown over two surrounds:
- **dark:** `#130F0B`, the app canvas used by every FP-21 round;
- **light:** `#E8E8E8`, a plain light desktop.

## 3. What is shown

`scripts/fire_companion/critique_pack_v21r.py --tag r1` writes one folder per reviewer. The candidates are in the
table below; letters are shuffled per reviewer with a fixed seed. The key and the SHA-256 of every file go to
`r1_key/key.json`.

Per state (idle, joyful, fierce, depleted), there is `target.png` (the reference panel) and ten candidates:

| Candidate | What it is | Role |
|---|---|---|
| `ref_reframed` | As in FP-21 | Top anchor (validity) |
| `ref_copy` | As in FP-21 | Calibration anchor (validity) |
| `v1` | As in FP-21 | Bottom anchor (validity) |
| `v2_app` | Ember V2 as the app showed it (opaque), dark surround | Baseline |
| `painting_t_dark` | The reference under equivalent conditions, dark surround | **Control** |
| `v21_worst_dark` | Shipped Ember, FP-21's worst frame, dark surround | Candidate |
| `v21_mid_dark` | Shipped Ember, half a loop later, dark surround | Candidate |
| `painting_t_light` | Control, light surround | **Control** |
| `v21_worst_light` | As `v21_worst_dark`, light surround | Candidate |
| `v21_mid_light` | As `v21_mid_dark`, light surround | Candidate |

**No animation task.** The motion is unchanged since Q2, where AC-F2 was met.
- The two changes since Q2 are the depleted haze footprint and the new `kindling` clip. Neither changes motion.
- `kindling` has no reference panel and is not scored.

## 4. Reviewers, dimensions, calculations

The FP-21 sections 3 and 4 apply unchanged:
- three fresh reviewers;
- the prompt is stored verbatim before the round, as `r1_prompt_reviewer<N>.md`;
- each reviewer writes its own raw JSON answer;
- transcripts are kept locally and hashed;
- the access audit uses `audit_reviewer_access.py`;
- dimensions C1-C6 and P1-P4, with the same scale.

The prompt is the P3 prompt with these differences:
- it has ten candidates (A-J);
- it says that app images are shown "over a dark or a light background".

Calculations:
- Character % = mean(C1-C6) x 10.
- Presentation % = mean(P1-P4) x 10.
- Visual % = mean(C1-P4) x 10.
- **Ember's value per reviewer, state and surround is the minimum over `v21_worst` and `v21_mid`, for each measure
  separately.**
- **Relative presentation:** for each reviewer, state and surround, `R = Presentation%(Ember) /
  Presentation%(painting_t, same surround)`.

## 5. Validity (decided before the candidates are decoded)

The FP-21 section 6 rule applies:
- `ref_reframed` visual >= 90 and `v1` visual < `ref_copy` visual, for every reviewer and state;
- all three reviewers complete.

An invalid round is reported and not used.

## 6. Proposed pass rules (pre-registered)

| Gate | Rule (for each of the four states) |
|---|---|
| **AC-F3 character (owner's 90 % requirement, unchanged)** | The mean over reviewers of Ember's character % is >= 90, on each surround. No reviewer is below 85. |
| **AC-F1R presentation, reference-relative (proposed)** | The mean over reviewers of R is >= 0.95, on each surround. No reviewer's R is below 0.90. |

**Why 0.95.**
- Ember is the painting re-rendered in motion, so under equal conditions its presentation should be close to the
  painting's own.
- 0.95 allows about the within-round noise seen in FP-21 (2-3 points on a scale near 85-90).
- It is deliberately stricter than restating the old threshold as a ratio (0.90), so that a ratio cannot be used to
  turn an absolute 85 into a "90".

**Also reported, for continuity, with no change to its rule:** FP-21 AC-F1, the absolute visual score >= 90 on the
dark surround. Its status is reported as measured.

## 7. Effect on the previous acceptance rule

FP-21 AC-F1 required visual >= 90 (character and presentation together, absolute), with no reviewer below 85.

If the owner approves FP-21R, AC-F1 is replaced by AC-F3 plus AC-F1R:
- **Character:** still an absolute 90 %, now required on both surrounds.
- **Presentation:** judged against the painting under the same transparent conditions, rather than against an
  absolute 90 that the mandated presentation prevents.
  - In Q2, the painting itself scored 88.3-89.3 there, and that was with its own opaque painted background.

Known weaknesses of the relative rule:
1. **Shared defects cancel.** A defect that `painting_t` shares with Ember cancels in R: the alpha matte, the glow
   and the host disc. These are covered elsewhere:
   - the matte and glow by the transparency gates (T0-T5, haze H1-H3) and by the owner's visual sign-off;
   - the host by UI V2's own qualification.
2. **Shared low scores.** If both Ember and the control score low, R can still pass. Mitigation: the absolute
   numbers are always reported next to R, and the character gate stays absolute.
3. **Same limits as FP-21.** Language-model reviewers, judging still images, with about 5 points of panel variance
   between rounds.
   - Every comparison in this rule is within-round, which is the comparison FP-21's evidence supports.

## 8. Rounds and approval

- **One round (R1).** There is no repair round under this protocol. If R1 is invalid, one replacement round (R2)
  with new reviewers is allowed, and both are reported.
- **Results before approval.** R1's results are recorded as **measured under a proposed protocol**.
  - Ember's fidelity status becomes "qualified under FP-21R" only after the owner approves this protocol.
  - The owner may approve, change the 0.95, or reject it. A rejection leaves AC-F1 NOT MET.
- **No threshold changes after the fact.** If the owner chooses a different ratio after seeing R1, the report says so
  explicitly.

## Change log

(none)
