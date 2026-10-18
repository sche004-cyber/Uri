# Ember V2.1 - Fidelity Protocol FP-21

Status: **LOCKED before the first V2.1 scoring round (P1).** Any later change is recorded in the change log at the
end, with its reason, and applies to every candidate in every round after it. The >= 90 threshold is not changed.

## 1. Why a new protocol

Three findings from V2's evidence, checked in V2.1 Phase 1 (`01_DIAGNOSIS_V21.md`), make V2's protocol unsuitable
for qualification:

1. **V2's packs did not show Ember as the app shows it.** They showed the square atlas frame on the app canvas. The
   app's companion host (`LivingCompanion`, accepted UI) draws the cell at presence scale 0.5 / 0.42 = 1.19 and fades
   it to a disc (`SoftDisc`) that ends at the layout box. In the live screenshots this cuts off Ember's feet, lower
   robe and crest tip. The V2 score (about 82) was therefore measured on a more favourable view than users see.
2. **Character and presentation were mixed.** Six of V2's seven dimensions are about the character, one ("painterly
   lighting and material") about presentation, but reviewers' comments show that background, cut-out edges and
   framing were scored inside the character dimensions too.
3. **No control for presentation.** V2 had `still_in_app` (the unanimated cut-out), but no control showing the
   unmodified painting itself inside the app presentation. Without it, a presentation that no artwork could pass
   cannot be told apart from a weak candidate.

## 2. What is shown

`scripts/fire_companion/critique_pack_v21.py --tag <round>` writes one folder per reviewer. Per reference state
(idle, joyful, fierce, depleted): `target.png` (the reference panel, unchanged) and eight candidates under letters
A-H, shuffled per reviewer with a fixed seed. The key and the SHA-256 of every file go to `<round>_key/key.json`,
which reviewers are never given.

| Candidate | What it is | Role |
|---|---|---|
| `ref_reframed` | The panel itself, sharp, 94 %, shifted 5 px | Top anchor |
| `ref_copy` | The panel blurred 2 px, shifted 3 px, JPEG q60 | Calibration anchor |
| `v1` | Ember V1 render | Bottom anchor |
| `painting_app` | The unanimated painting (rig erase only) in the V2.1 app presentation | Presentation control |
| `v2_app` | Ember V2 (b73bd26c settings), as the app shows it | Baseline |
| `v21_worst` | Ember V2.1, the loop frame the automated scorer ranks furthest from the painting | Candidate |
| `v21_mid` | Ember V2.1, half a loop later | Candidate |
| `v21_frame_only` | V2.1 framing with V2's smooth backdrop | Ablation |

"As the app shows it": frame -> 320 px atlas cell -> WebP q88 round trip -> drawn at presence scale 1.19 into a
490 px box (bilinear) -> `SoftDisc` (opaque to 0.72 of the radius, zero at the box edge) -> Solar Ember surface
`#130F0B`. This is the same arithmetic as `living_companion.dart` and `companion_presence.dart`; the live run checks
it against screenshots.

Animation: per state, six frames evenly spaced over the loop for V2 and for V2.1, each as the app shows it, under the
labels X and Y (shuffled per reviewer).

## 3. Reviewers

- Three fresh general-purpose subagents per round. None of them has made images, seen a previous round or seen the
  key. They are told to read only their own pack folder.
- Each reviewer gets the same prompt, stored verbatim as `<round>_prompt.md` before the round starts.
- Each reviewer writes its complete answer as JSON to `<round>_raw/reviewer<N>.json` (raw evidence), and returns the
  same JSON as its final message. The hand-back message is also stored verbatim (`reviewer<N>_handback.txt`).

## 4. Dimensions

Each candidate is scored 0-10 (halves allowed) on ten dimensions. Scale: 10 = indistinguishable from the target on
this dimension; 9 = only minor differences a careful side-by-side reveals; 7-8 = clear but moderate differences;
5-6 = substantial differences; 4 or less = different.

Character (the character itself):
- C1 silhouette and proportions
- C2 head shape and surface
- C3 eyes and expression
- C4 flames: density, shape and colour
- C5 body and pose
- C6 emotional identity (the same character in the same mood)

Presentation (how the artwork is presented):
- P1 painterly texture and material (brushwork preserved)
- P2 lighting and glow (luminosity and atmosphere as painted)
- P3 background and edge integration (no cut-out or sticker look; natural transitions)
- P4 composition and framing (the character complete and placed as in the painting)

Animation (per state, X and Y sequences):
- A1 motion plausibility (organic, natural for fire)
- A2 identity stability across frames
- A3 freedom from artefacts (10 = none)
- A4 expressiveness of the motion for the mood

## 5. Calculations

- Character % = mean(C1-C6) x 10. Presentation % = mean(P1-P4) x 10.
- **Visual fidelity % = mean of all ten dimensions x 10.**
- V2.1's value per reviewer and state is the **minimum** over `v21_worst` and `v21_mid` (for each of the three
  measures separately).
- Animation % = mean(A1-A4) x 10.
- `evidence/fidelity/decode_v21.py` computes every table from the raw JSON files and the key.

## 6. Validity of a round (decided before decoding V2.1's scores)

A round is valid only if, for every reviewer and every state:
- `ref_reframed` visual fidelity >= 90, and
- `v1` visual fidelity < `ref_copy` visual fidelity.

All three reviewers must complete. An invalid round is kept and reported, and the whole round is repeated with new
reviewers. No reviewer and no score is removed selectively.

## 7. Pass rule (unchanged threshold)

V2.1 passes AC-F1 when, in the qualification round, for **each** of the four states:
- the mean over reviewers of V2.1's visual fidelity is >= 90;
- no reviewer scores V2.1's visual fidelity below 85;
- the mean over reviewers of V2.1's character fidelity is >= 90.

Animation (AC-F2): V2.1's mean animation % in each state is not more than 5 points below V2's in the same round.

## 8. Rounds

- **P1** (exploratory): baseline and candidates. It may inform one repair. It is not used for the verdict.
- **Q1** (qualification): fresh reviewers, the final assets rebuilt from the final commit. The verdict comes from Q1.
- At most one repair and one further round (Q2) after Q1. If Q2 also fails, the work stops and reports NOT MET.
- Every round is reported, including invalid and failed ones.

## 9. Known limits

- The reviewers are language models looking at still images. Motion is judged from six stills, not playback.
- The 490 px box is larger than the app's typical box (about 270-300 px at 100 % scaling), so reviewers see more
  detail than a user at 100 % scaling; every candidate gets the same treatment.
- `painting_app` uses the panel after the rig's `erase` rectangles (the signature on idle, a pale rectangle on
  depleted), like every Ember frame.

## Change log

**C-1 (after P1, before P2): an extra exploratory round, P2 "host probe".** P1 was valid. V2.1 scored exactly the
same as the `painting_app` control (89.0-89.2), so the remaining cost is the host presentation itself, which no
artwork can pass inside. P2 measures what alternative host presentations would allow, as evidence for an owner
decision (changing the host is AMBER). P2 uses the same prompt minus TASK 2 (stored as `p2_prompt_reviewer<N>.md`), the same dimensions, anchors and validity rule; its
candidates replace V2 and the V2.1 frame variants with: `v21_disc` (the current host), `v21_wide` (disc opaque to
0.86 of the radius), `v21_card` (square box with soft rounded edges over the outer 10 %) and the control
`painting_card`. P2 has no animation part and no pass rule. It does not change the qualification rules: the verdict
still comes only from Q1 under section 7, on whatever presentation is actually implemented.

**C-2 (after Q1, before P3): exploratory round P3 "transparency".** The owner directive "Ember V2.1 - URI UI V2
Compatibility" (2026-10-15) requires Ember to have no permanent opaque background. V2.1's painted backdrop (and V2's
pool) is opaque. P3 measures what transparent-ready variants cost in fidelity, in the same app view as Q1. It uses
the P2 prompt (no animation task), the same dimensions, anchors and validity rule. Candidates: `ref_reframed`,
`ref_copy`, `v1`, `painting_app`, `v21_painted` (Q1's V2.1), `t1_glow` (alpha-only character with emissive flame
glow, alpha capped at 0.45), `t2_glow_haze35` and `t3_glow_haze60` (t1 plus the painted backdrop as a translucent
haze at 35 % / 60 %). P3 has no pass rule. Q1 remains the qualification result for the presentation it measured;
any transparent build that becomes the shipped default needs its own qualification round under section 7.

**C-3 (before Q2): Q2 is the one further round section 8 allows after Q1.** The repair it measures is the
owner-mandated transparency change (`73e84a6d`), now the shipped default. Q2 uses Q1's prompt, candidates and rules
unchanged, except that `painting_app` stays the painting in the painted V2.1 presentation of Q1 (a fixed control
across rounds), while `v21_worst`/`v21_mid`/animation show the shipped transparent build. Section 7 applies. After Q2
there are no further rounds.

**C-4 (record of deviations found by review R1-11):**
1. *Lock evidence.* The protocol was written before P1's pack was built (session order: protocol file, then
   `critique_pack_v21.py --tag p1`), but it was first committed in `9933ca2b`, after P1 and P2 had run. Git therefore
   does not evidence the lock time; the file was not edited between P1 and that commit except for C-1. Future
   rounds: commit the protocol before building a pack.
2. *Hand-back files.* Section 3 promised `reviewer<N>_handback.txt`. They were not written. Instead each reviewer's
   full transcript (which contains the hand-back verbatim) is preserved locally as
   `<round>_raw/reviewer<N>_transcript.jsonl.gz`, hashed in `SHA256SUMS.txt`, and audited with
   `audit_reviewer_access.py`.
3. *Worst frame.* "The loop frame the automated scorer ranks furthest" comes from V2's `auto_cp8/scores_v2.json`. The
   motion is unchanged in V2.1, but the frame was not re-scored for V2.1. Impact: none measured (worst and mid scored
   the same in every round).
4. *Prompt wording.* The prompt tells reviewers some candidates are shown "inside an app ... with a soft round
   vignette". This applies to all candidates equally but may encourage class-scoring (R1-03).
5. *Canvas and box (R1-01).* The pack composites on flat `#130F0B` in a 490 px box. The live companion screen has a
   lighter, warmer radial surround next to the disc (about (29,20,11) sampled from `first-05`) and a box of about
   300 px. The host arithmetic (scale, disc) is exact; the surround and size are approximations, applied equally to
   every candidate and to the control. A pixel check against a live crop is in `evidence/diagnosis/`.

**C-5 (record of deviations found by review R2):**
1. *Two rounds after Q1 (R2-07).* Section 8 allows one round after Q1. P3 (exploratory, no pass rule) and Q2 both ran
   after Q1. P3 did not qualify anything, but it is a deviation from the letter of section 8, recorded here. Q2 is
   the last scored round.
2. *Panel variance (R2-01).* Q2 re-scored images pixel-identical to Q1's for `painting_app`, `v2_app` and
   `v21_frame_only`, and nearly identical to P3's `t1_glow` for the transparent build. Those images moved 2.0-4.9 and
   5.6-7.8 points between panels. The "+-2 points" stated after R1 understates the uncertainty. Use only
   within-round comparisons.
3. *Indistinguishable variants (R2-08).* In P3 the t1, t2 and t3 images differ by 3-8/255 outside depleted, and
   reviewers scored them identically. "Made no difference" means "reviewers did not distinguish them".

