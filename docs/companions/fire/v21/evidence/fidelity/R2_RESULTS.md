# FP-21R round R2 - results (the replacement round for the invalid R1)

## How the round was run

- **Protocol:** `../../08_FIDELITY_PROTOCOL_V21R.md`, **PROPOSED, not approved by the owner**. Change log C-1
  covers this round.
- **Pack:** the same images as R1 (all 120 candidate hashes match), re-shuffled with seed 4200. Pack integrity OK.
- **Reviewers:** three new reviewers.
- **Raw answers:** `r2_raw/`. Transcripts are kept locally; their hashes are in `SHA256SUMS.txt`.
- **Access audit: clean.** Each reviewer read only its own pack folder and wrote only its own answer. Reviewer 1
  made one Glob call, `*.png`, in its own folder.
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

## Reading

1. **The reviewers could not tell Ember from the unanimated painting under the same treatment.** All six reviewers,
   in R1 and R2, said so in their notes, and scored the two identically.
   - **What this supports:**
     - Ember's animation and re-rendering cost nothing measurable, on either surround.
     - Ember is as faithful as the original painting can be in this presentation.
   - **What it does not support:** a measured presentation ratio. R = 1.000 is an artefact of reviewers who cannot
     distinguish the two images, which is the protocol's stated weakness 1. **This report does not claim that
     AC-F1R is meaningfully met.**
2. **Character 90 % is not reachable by the painting itself in the transparent presentation.**
   - On the dark surround the painting scores 83.3-90.8 for character.
     - Depleted is lowest, because its dark smoke disappears against black.
     - In Q2's painted (opaque) presentation the character scores were 92.2-93.1.
     - The panel varies by about 5 points between rounds, so the size of the transparency cost on character is
       uncertain. Its direction is consistent: P3 and R1 point the same way.
   - On a light surround the painting scores 73.9-78.9. The reviewers' reasons were:
     - emissive flames turn pale on white;
     - a hard painted outline on the head;
     - semi-transparent gaps in the robe strokes let the desktop show through;
     - the depleted foot shadow reads as a blob.
   - These are properties of a transparent painted character on a light desktop. Finding **F-LIGHT-1**.
3. **Against V2, Ember V2.1 is clearly better on the dark surround:**
   - character +6.4 to +7.2 (depleted +3.9);
   - visual +5.3 to +6.0 (depleted +2.3).
   V2 was opaque, and in the app it was cropped by the host disc.
4. **Consequence for the owner's decision.** As written, the 90 % character requirement cannot be met by any
   artwork under the mandated transparent presentation as this panel measures it, including the original painting
   itself. Three ways forward:
   - (a) measure character on the opaque painted presentation, which Q2 did and where it was met;
   - (b) accept character fidelity relative to the painting under the same transparency, which these rounds give
     as identical;
   - (c) invest in a light-desktop treatment (F-LIGHT-1) and re-measure.
   This is the owner's decision. Nothing is accepted here.
