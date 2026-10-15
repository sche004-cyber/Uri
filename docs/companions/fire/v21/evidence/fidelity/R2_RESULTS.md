# FP-21R round R2 - results (the replacement round for the invalid R1)

## How the round was run

- **Protocol:** `../../08_FIDELITY_PROTOCOL_V21R.md`, **PROPOSED, not approved by the owner**. Change log C-1
  covers this round.
- **Pack:** the same images as R1 (all 120 candidate hashes match), re-shuffled with seed 4200. Pack integrity OK.
- **Reviewers:** three new reviewers.
- **Raw answers:** `r2_raw/`. Transcripts are kept locally; their hashes are in `SHA256SUMS.txt`.
- **Access audit: clean (R4-N9, R5-N6).** Every file each reviewer read or wrote is in its own pack folder or its
  own answer file.
  - Reviewer 1 also made one Glob call (`*.png`) whose `path` is its own folder `...\fp21r\r2\reviewer1`.
  - `audit_reviewer_access.py` reduces every path argument to its parent folder, so that call appears in
    `access_audit.txt` as `...\fp21r\r2`. No file outside the reviewer's own folder was read.
  - The key folder (`r2_key`) is never in the scratch area.
- **Decoded tables:** `r2_decoded.md`.

**Round valid:**
- `ref_reframed` scored 96-98 for every reviewer and state;
- V1 scored below `ref_copy` throughout.

## Result (means over the three reviewers)

| State | Surround | Ember character | Ember presentation | `painting_t` character / presentation | R | V2 in the app (character) |
|---|---|---|---|---|---|---|
| idle | dark | **88.9** | 72.1 | 88.9 / 72.1 | 1.000 | 81.9 |
| idle | light | **76.9** | 58.8 | 76.9 / 58.8 | 1.000 | - |
| joyful | dark | **89.2** | 72.5 | 89.2 / 72.5 | 1.000 | 82.8 |
| joyful | light | **78.3** | 60.4 | 78.1 / 60.0 | 1.007 | - |
| fierce | dark | **90.8** | 73.3 | 90.8 / 73.3 | 1.000 | 83.6 |
| fierce | light | **78.9** | 60.4 | 78.9 / 60.4 | 1.000 | - |
| depleted | dark | **83.3** | 68.8 | 83.3 / 68.8 | 1.000 | 79.4 |
| depleted | light | **73.9** | 59.2 | 73.9 / 59.2 | 1.000 | - |

| Gate | Result |
|---|---|
| **AC-F3, character >= 90 (owner requirement, kept)** | **NOT MET.** Only fierce on the dark surround passes (90.8). Dark: 83.3-90.8. Light: 73.9-78.9. |
| **AC-F1R, relative presentation (proposed)** | Passes as computed: R = 1.000-1.007. It is **not meaningful**; see reading 1. |
| FP-21 AC-F1, absolute visual >= 90 (rule of record) | **NOT MET** (dark: 77.5-83.8) |

## Reading (repaired after independent review R3, findings R3-04 and R3-10)

1. **The reviewers could not tell Ember from the unanimated painting under the same treatment.**
   - All six reviewers, in R1 and R2, said so in their notes and scored the two identically.
   - **Why this happens.** The control `painting_t` is cut out with Ember's own layer alpha and edge colours, so the
     two images are close by construction: mean pixel difference 0.8-5.1 / 255 (review R3-04).
   - **What it supports, and only this:** in these still frames, at this size, the animated and re-rendered Ember
     shows no difference the panel can see from the unanimated painting given the same cut-out and presentation.
   - **What it does not support:**
     - that the animation costs nothing in motion: only two still frames per state were scored, and motion was
       last judged in Q2 (AC-F2);
     - a measured presentation ratio. R = 1.000 is an artefact of indistinguishable images (protocol weakness 1).
       **AC-F1R is not claimed as meaningfully met.**
2. **The painting under the same cut-out and presentation does not reach 90 % character either.**
   - On the dark surround it scores 83.3-90.8 for character.
     - Depleted is lowest, because its dark smoke disappears against black.
     - In Q2's painted (opaque) presentation, character was 92.2-93.1.
     - Panel variance between rounds is about 5 points, so the size of the transparency cost on character is
       uncertain. Its direction is consistent with P3 and R1.
   - On a light surround it scores 73.9-78.9. The reviewers' reasons, all shared by the control:
     - emissive flames turn pale on white;
     - a hard painted outline on the head;
     - semi-transparent gaps in the robe strokes let the desktop show through;
     - the depleted foot shadow reads as a blob.
   - This is about **this** cut-out: Ember's matte, glow and haze. It does not show that no transparent artwork could
     reach 90. A different matte or a light-desktop treatment might. Finding **F-LIGHT-1**.
3. **Against V2, Ember V2.1 scores clearly higher on the dark surround:**
   - character +6.4 to +7.2 (depleted +3.9);
   - visual +5.3 to +6.0 (depleted +2.3).
   V2 was opaque, and the host disc cropped it in the app.
4. **Consequence for the owner's decision.** As measured, the 90 % character requirement is not met by Ember, nor by
   the painting given Ember's transparent cut-out and presentation. Ways forward:
   - (a) measure character on the opaque painted presentation, where Q2 met it;
   - (b) accept character relative to the painting under the same transparency. Note that this panel cannot
     separate the two, so the comparison is weak evidence;
   - (c) invest in a light-desktop and matte treatment (F-LIGHT-1) and re-measure.
   This is the owner's decision. Nothing is accepted here.

### Wording corrections (R3-10)

- **"AC-F3 unchanged" in the protocol.** The threshold (90, with a reviewer floor of 85) is unchanged, but FP-21R
  requires it on both surrounds. That is stricter than FP-21's AC-F3, which was dark-canvas only.
  - On the dark surround alone, AC-F3 is still NOT MET in R2: idle 88.9, joyful 89.2, depleted 83.3.
- **The protocol's alpha rule.** It says "where the alpha is below 0.85, the layer colour". The code
  (`critique_pack_v21r.py`) blends the painting's pixels and the layer colour linearly between alpha 0.60 and 0.85.
  The images match the code, and both candidates and the control used them.
- **Decoder rounding.** Before change log C-2, `r2_decoded.md` printed the "lowest" values rounded to whole numbers; it now prints one decimal. The decimal values do
  not change any gate result. The lowest character values on the dark surround are 87.5 (idle), 88.3 (joyful),
  90.8 (fierce) and 80.8 (depleted), from `r2_raw`.
