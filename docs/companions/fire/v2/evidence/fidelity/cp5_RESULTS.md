# Fidelity checkpoint 5 - diagnostic: presentation vs animation (2026-10-15)

Question: V2 plateaued at 74-80 across checkpoints 2-4. Is that cost from the animation, or from presenting a
cut-out of the painting on the app's dark canvas?

Method: the same blind pack as CP4, built with `critique_pack_v2.py --tag cp5 --diagnostic`. The video anchor was
replaced by `still_in_app`: the painting with no animation at all (the lifted sparks put back), cut out with the
same matte and shown exactly as the app shows V2, with the same framing, backdrop pool and canvas. Two new fresh
reviewers. Key: `cp5_key/key.json`.

| State | ref_reframed | still_in_app (no animation) | **V2 animated** | ref_copy (blurred) | V1 |
|---|---|---|---|---|---|
| idle | 100 / 100 | 81 / 76 | **71 / 73** | 76 / 80 | 37 / 37 |
| joyful | 100 / 100 | 81 / 79 | **74 / 76** | 76 / 80 | 39 / 36 |
| fierce | 100 / 100 | 71 / 77 | **70 / 77** | 73 / 80 | 39 / 31 |
| depleted | 100 / 100 | 69 / 76 | **69 / 73** | 73 / 80 | 40 / 39 |

(reviewer 1 / reviewer 2)

## Finding

The presentation, not the animation, holds V2 below 90:
- The unanimated painting, shown the way the app shows Ember, scores **69-81**.
- The same painting on its own background scores **100**.
- Animation costs 0-10 points (mean 3.4; first published as 3.3 and corrected in review R2-03) on top of that.

Because the presentation alone costs 20-30 points, the cut-out presentation cannot reach the >= 90 target with
any animation. A perfect, motionless cut-out does not reach it either.

Named presentation costs, consistent across reviewers:
- The near-black surround makes the orange read more saturated and the glow stronger. Measured pixels are equal
  (`cp4_RESULTS.md`).
- The fierce crest swoosh reads dark maroon. It is a translucent brown stroke whose look depends on the painted
  background behind it.
- The depleted robe and legs look ghostly: the grey robe is close to the background colour, so the matte gives it
  partial alpha.
- Without the painted background, head and eye proportions are perceived as different.

## Reviewer-reliability notes

- Reviewer 1 again reported a "joyful frame 1 identity jump". The CP4 check of the same kind of claim found no
  such jump.
- Both reviewers mark several of their own frame-to-frame observations as uncertain at about 490 px per frame.
