"""Decode raw_letter_scores.json with cpN_key/key.json (review R1-03).

    python -B decode_raw_scores.py
Prints, per checkpoint and state, each source's score from both reviewers and
the V2 score used for the verdict (min over V2 frames per reviewer; mean of the
two reviewers).
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
raw = json.load(open(os.path.join(HERE, "raw_letter_scores.json"), encoding="utf-8"))
for cp in [k for k in raw if k.startswith("cp")]:
    key = json.load(open(os.path.join(HERE, f"{cp}_key", "key.json"), encoding="utf-8"))
    print(f"== {cp}")
    for state in ("idle", "joyful", "fierce", "depleted"):
        per = {}
        for r in ("reviewer1", "reviewer2"):
            for letter, score in raw[cp][r][state].items():
                per.setdefault(key[r][state][letter], []).append(score)
        v2 = [n for n in per if n.startswith("v2")]
        v2_by_rev = [min(per[n][i] for n in v2) for i in range(2)]
        line = "  ".join(f"{n}={'/'.join(str(x) for x in s)}" for n, s in sorted(per.items()))
        print(f"  {state:9s} V2(min)={v2_by_rev} mean={sum(v2_by_rev) / 2:.1f}   {line}")
