# FP-21 exploratory rounds P1 and P2 - results

Protocol: `../../03_FIDELITY_PROTOCOL_V21.md`. Decoded tables: `p1_decoded.md`, `p2_decoded.md` (regenerate with
`decode_v21.py p1|p2`). Raw evidence per round in `<round>_raw/`: each reviewer's own answer file (`reviewer<N>.json`),
its full transcript (`reviewer<N>_transcript.jsonl.gz`, kept local and out of git: about 15 MB each, mostly the pack
images), `SHA256SUMS.txt` and `access_audit.txt`. The prompts are `<round>_prompt_reviewer<N>.md`.

Both rounds are **valid** (section 6): every reviewer scored `ref_reframed` 93-98 and V1 below the blurred copy.
The access audits show each reviewer read only its own pack and wrote only its own answer file (P2 reviewer 3 also
edited its own answer once, a wording fix in `general_notes`).

## P1: baseline and V2.1 (3 fresh reviewers)

Visual fidelity %, mean of three reviewers:

| State | ref_reframed | painting_app (control) | **V2.1** (min of 2 frames) | V2.1 framing only | **V2 in the app** | ref_copy (blurred) | V1 |
|---|---|---|---|---|---|---|---|
| idle | 96.2 | 89.0 | **89.0** | 89.0 | **78.2** | 77.7 | 37.2 |
| joyful | 96.2 | 89.0 | **89.0** | 88.2 | **78.2** | 77.8 | 37.0 |
| fierce | 96.2 | 89.0 | **89.0** | 89.0 | **78.0** | 77.8 | 36.8 |
| depleted | 96.2 | 89.2 | **89.2** | 88.3 | **78.0** | 78.3 | 38.0 |

- V2.1 character % 94.2 in every state (V2: 82.2-82.5). V2.1 presentation % 81.2-81.7 (V2: 71.7).
- Pass rule: visual mean 89.0-89.2 against >= 90 -> **FAIL in P1** (lowest reviewer 88 >= 85 and character 94.2 >= 90
  hold).
- Animation % V2.1 74.2-78.8 against V2 71.2-77.9: no regression (AC-F2 holds).
- **V2.1 scored exactly the same as the unanimated, unmodified painting shown the same way, for every reviewer and
  state.** Nothing in V2.1's character, animation or compositing is costing points; the whole remaining gap is the
  presentation. The textured backdrop did not show up as a separate gain at this resolution (the framing-only
  ablation scored within 1 point).
- V2 as users actually see it (cropped by the disc) is 78, not the 82 reported in V2 from the uncropped view.

## P2: host presentation probe (3 fresh reviewers; change log C-1)

| State | ref_reframed | painting_app (disc) | painting_card | V2.1 disc (current host) | V2.1 wide disc | V2.1 card | ref_copy | V1 |
|---|---|---|---|---|---|---|---|---|
| idle | 95.8 | 85.3 | 86.3 | 85.3 | 84.7 | 86.3 | 78.2 | 37.3 |
| joyful | 95.8 | 85.3 | 86.3 | 85.3 | 84.5 | 86.3 | 78.0 | 36.2 |
| fierce | 95.8 | 85.3 | 86.3 | 85.3 | 85.2 | 86.3 | 78.2 | 35.8 |
| depleted | 95.8 | 85.5 | 86.3 | 85.5 | 84.5 | 86.3 | 78.0 | 36.5 |

- No host presentation reaches 90. A soft square card is about 1 point better than the disc; a wider disc is not
  better (reviewers saw its rim as a "porthole").
- Again V2.1 equals the painting in the same presentation, to the point.
- The same control scored 89.0 in P1 and 85.3 in P2: the reviewer panel moves by about 4 points between rounds.

## What this means

1. Under FP-21, the painting itself in the tested app presentations scored 85-89 across three panels (P1, P2, Q1).
   With this rubric and 3 reviewers per round, 90 was not reached by any app-presented candidate, including the
   control. That is weaker than "no artwork can pass": a round mean is uncertain by about +-2 points and P1's control
   was 89.0-89.2 with one reviewer at 90 (review R1-03). Reviewers name the same costs every time: darker surround instead of the painted brown, the figure scaled
   down, slight softening from the 320 px atlas, and the margins (signature, edge glow) faded.
2. V2.1 has reached that ceiling: in all 24 state-reviewer pairs across two rounds, V2.1 equals the painting control.
3. The >= 90 target as written was not shown for any in-app presentation with this rubric. The evidence points to a
   limit of comparing an app rendering with a standalone painting, not to a defect in Ember. The threshold is not
   changed; the evidence goes to the owner.
4. Changing the shared host is not justified by the evidence (+1 point at most).
