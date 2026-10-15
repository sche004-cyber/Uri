You are an independent visual reviewer. You have not seen any earlier work on this subject. Work read-only, except for the one answer file named below.

Read ONLY the image files in this folder: C:/Users/cheta/AppData/Local/Temp/claude/C--Users-cheta-Development-Uri--V1/1ac9fcbc-5341-4d15-98e2-21395c171a6e/scratchpad/fp21/p2/pack_r2
Do not open, search or list any other folder or file, and do not run scripts. Judge only what you see.

The folder holds, for four reference states (idle, joyful, fierce, depleted):
- `<state>_target.png`: the reference artwork (a painted character).
- `<state>_candidate_A.png` ... `<state>_candidate_H.png`: eight candidate images. Some may be identical to the
  target or nearly so; some are shown as they would appear inside an app, on a dark background with a soft
  vignette (round or square). Candidates are in random order and their letters mean nothing.

TASK 1 - static fidelity. For every state and every candidate A-H, compare the candidate with the target and score
each dimension from 0 to 10 (halves allowed):
  10 = indistinguishable from the target on this dimension
   9 = only minor differences that a careful side-by-side reveals
 7-8 = clear but moderate differences
 5-6 = substantial differences
 0-4 = different
Character dimensions (the character itself):
  C1 silhouette and proportions; C2 head shape and surface; C3 eyes and expression; C4 flames: density, shape and
  colour; C5 body and pose; C6 emotional identity (the same character in the same mood).
Presentation dimensions (how the artwork is presented):
  P1 painterly texture and material (brushwork preserved); P2 lighting and glow (luminosity and atmosphere as
  painted); P3 background and edge integration (no cut-out or sticker look; natural transitions); P4 composition and
  framing (the character complete and placed as in the painting).
Put differences in the background, edges, framing and lighting under P1-P4, and differences in the character under
C1-C6. Score every candidate on its own merits against the target, with the same scale for all.

Look at every image before scoring. Then write your complete answer as JSON, exactly in this shape, to the file
C:/Users/cheta/AppData/Local/Temp/claude/C--Users-cheta-Development-Uri--V1/1ac9fcbc-5341-4d15-98e2-21395c171a6e/scratchpad/fp21/p2_raw/reviewer2.json:

{
  "reviewer": "p2-reviewer2",
  "static": {
    "idle": {"A": {"C1": 0, "C2": 0, "C3": 0, "C4": 0, "C5": 0, "C6": 0, "P1": 0, "P2": 0, "P3": 0, "P4": 0,
                   "note": "one or two sentences on the main differences"},
             "B": {...}, ... "H": {...}},
    "joyful": {...}, "fierce": {...}, "depleted": {...}
  },
  "general_notes": "anything else you noticed, including uncertainty"
}

Finally, return the same JSON as your final message, with nothing before or after it.
