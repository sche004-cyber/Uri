# FP-21R round R1 - INVALID (reported, not used)

- **Protocol:** `../../08_FIDELITY_PROTOCOL_V21R.md`, which is PROPOSED and not approved.
- **Pack:** built from `6adf8fbf` (build `e43e97a7`) with `critique_pack_v21r.py --tag r1 --seed 4100`. The pack
  integrity check is OK.
- **Raw answers:** in `r1_raw/`. Transcripts are kept locally; their hashes are in `SHA256SUMS.txt`.
- **Access audit (`access_audit.txt`): clean.** Reviewer 1 made one Bash call, which printed its own answer file.
- **Decoded tables:** `r1_decoded.md`.

## Validity: INVALID

Reviewer 2 scored depleted `ref_reframed` (letter B) at 64, against the >= 90 required.
- The image under B is `ref_reframed`; the hashes match the key.
- Reviewer 2's notes for B and C each describe the other image. B's note describes a light-background candidate,
  and C's note describes "the painting inset in a dark frame".
- The answer therefore looks transposed between B and C. Under section 5 the round is invalid regardless.
- Nothing was edited or removed. The replacement round is R2 (protocol change log C-1).

## Observations (informational only; this round counts for nothing)

1. **Class-scoring.**
   - All three reviewers said they could not tell Ember from `painting_t` on the same surround.
   - They gave both identical scores, so R = 1.000 almost everywhere.
   - This is the protocol's stated weakness 1 (shared treatment cancels). The reviewers did not detect the animation
     or re-rendering at all.
2. **Light surround.** Character scores were 67-76 on light against 85-92 on dark, for Ember and the control alike.
   The reviewers gave these reasons:
   - flames washed to peach, because an emissive glow cannot brighten a white desktop;
   - a "hard rim" on the head (the painted outline);
   - white streaks in the fierce robe (semi-transparent gaps in the painted strokes show the desktop);
   - a dark blob by the depleted feet.
   Because the painting under the same treatment scores the same, this is a property of transparent presentation
   on light desktops, not of Ember's animation. It is recorded as finding **F-LIGHT-1** for the owner.
3. **The `ref_reframed` P3 and P4 discount.** Reviewer 3 noted that it docked P3 and P4 for the thin added border.
