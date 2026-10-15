"""Decode FP-21 reviewer answers with the key (protocol: ../../03_FIDELITY_PROTOCOL_V21.md).

    python -B docs/companions/fire/v21/evidence/fidelity/decode_v21.py p1

Reads <round>_raw/reviewer<N>.json and <round>_key/key.json, verifies the pack
files against the key's SHA-256 list, and prints (and writes to
<round>_decoded.md) every table the protocol defines: per candidate, per
state, per reviewer, the visual / character / presentation %, the validity
checks, the pass rule and the animation comparison.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATES = ["idle", "joyful", "fierce", "depleted"]
CH = ["C1", "C2", "C3", "C4", "C5", "C6"]
PR = ["P1", "P2", "P3", "P4"]
AN = ["A1", "A2", "A3", "A4"]
ORDER = ["ref_reframed", "painting_app", "painting_card", "ref_copy", "v21", "v21_worst", "v21_mid",
         "v21_frame_only", "v21_disc", "v21_wide", "v21_card", "v21_painted", "t1_glow", "t2_glow_haze35", "t3_glow_haze60", "v2_app", "v1"]


def pct(d: dict, keys: list[str]) -> float:
    return 10 * sum(float(d[k]) for k in keys) / len(keys)


def main() -> None:
    tag = sys.argv[1]
    key = json.loads((HERE / f"{tag}_key" / "key.json").read_text(encoding="utf-8"))
    bad = [f for f, h in key["files"].items()
           if not (HERE / tag / f).exists() or hashlib.sha256((HERE / tag / f).read_bytes()).hexdigest() != h]
    revs = sorted(p.stem for p in (HERE / f"{tag}_raw").glob("reviewer*.json"))
    out: list[str] = [f"# FP-21 round {tag} - decoded", "",
                      f"Pack integrity: {'OK, all files match the key hashes' if not bad else 'MISMATCH ' + str(bad)}",
                      f"Reviewers with answers: {', '.join(revs)}", ""]
    S: dict = {}  # S[state][name][rev] = (visual, character, presentation)
    M: dict = {}  # M[state][name][rev] = animation
    for r in revs:
        ans = json.loads((HERE / f"{tag}_raw" / f"{r}.json").read_text(encoding="utf-8"))
        kr = key[r]
        for st in STATES:
            for L, nm in kr[st].items():
                if L == "anim":
                    continue
                d = ans["static"][st][L]
                v = (pct(d, CH + PR), pct(d, CH), pct(d, PR))
                S.setdefault(st, {}).setdefault(nm, {})[r] = v
            if "v21_worst" not in S[st]:
                continue  # host probe round (P2): no V2.1 frame pair, no animation
            w, m = S[st]["v21_worst"][r], S[st]["v21_mid"][r]
            S[st].setdefault("v21", {})[r] = tuple(min(a, b) for a, b in zip(w, m))
            for lab in "XY":
                nm = kr[st]["anim"][lab]
                M.setdefault(st, {}).setdefault(nm, {})[r] = pct(ans["motion"][st][lab], AN)

    def mean(xs):
        return sum(xs) / len(xs)

    order = [nm for nm in ORDER if nm in S[STATES[0]]]
    for idx, title in ((0, "Visual fidelity %"), (1, "Character %"), (2, "Presentation %")):
        out += [f"## {title} (reviewers {' / '.join(revs)} -> mean)", "",
                "| State | " + " | ".join(order) + " |", "|---|" + "---|" * len(order)]
        for st in STATES:
            cells = []
            for nm in order:
                vals = [S[st][nm][r][idx] for r in revs]
                cells.append(" / ".join(f"{v:.0f}" for v in vals) + f" -> **{mean(vals):.1f}**")
            out.append(f"| {st} | " + " | ".join(cells) + " |")
        out.append("")
    out += ["`v21` = min(v21_worst, v21_mid) per reviewer (protocol section 5).", "", "## Validity (section 6)", ""]
    valid = True
    for st in STATES:
        for r in revs:
            top = S[st]["ref_reframed"][r][0]
            order = S[st]["v1"][r][0] < S[st]["ref_copy"][r][0]
            ok = top >= 90 and order
            valid &= ok
            out.append(f"- {st} {r}: ref_reframed {top:.0f} (>= 90: {top >= 90}); v1 < ref_copy: {order} -> "
                       f"{'ok' if ok else 'INVALID'}")
    out += ["", f"**Round valid: {valid}**", ""]
    if "v21" not in S[STATES[0]]:
        out += ["Host probe round: exploratory, no pass rule or animation (protocol change log C-1)."]
        text = "\n".join(out) + "\n"
        (HERE / f"{tag}_decoded.md").write_text(text, encoding="utf-8")
        print(text)
        return
    out += ["## Pass rule (section 7)", ""]
    passed = True
    for st in STATES:
        vis = [S[st]["v21"][r][0] for r in revs]
        chr_ = [S[st]["v21"][r][1] for r in revs]
        ok = mean(vis) >= 90 and min(vis) >= 85 and mean(chr_) >= 90
        passed &= ok
        out.append(f"- {st}: visual mean {mean(vis):.1f} (>= 90), lowest reviewer {min(vis):.0f} (>= 85), "
                   f"character mean {mean(chr_):.1f} (>= 90) -> {'PASS' if ok else 'FAIL'}")
    out += ["", f"**AC-F1 in this round: {'PASS' if passed and valid else 'NOT MET'}**"
            + ("" if valid else " (round invalid)"), "", "## Animation % (section 7, AC-F2)", "",
            "| State | V2 | V2.1 | V2.1 - V2 | <= 5 below |", "|---|---|---|---|---|"]
    for st in STATES:
        a2, a21 = mean(list(M[st]["v2"].values())), mean(list(M[st]["v21"].values()))
        out.append(f"| {st} | {a2:.1f} | {a21:.1f} | {a21 - a2:+.1f} | {a21 >= a2 - 5} |")
    text = "\n".join(out) + "\n"
    (HERE / f"{tag}_decoded.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
