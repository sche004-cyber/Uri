"""Decode FP-21R reviewer answers with the key (protocol: ../../08_FIDELITY_PROTOCOL_V21R.md).

    python -B docs/companions/fire/v21/evidence/fidelity/decode_v21r.py r1

Reads <round>_raw/reviewer<N>.json and <round>_key/key.json, verifies the pack
files against the key's SHA-256 list, and writes <round>_decoded.md: every
candidate's visual / character / presentation %, the validity checks, the
proposed gates AC-F3 (character) and AC-F1R (relative presentation) per
surround, and FP-21 AC-F1 (absolute visual, dark surround) for continuity.
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
SURR = ["dark", "light"]
ORDER = ["ref_reframed", "ref_copy", "painting_t_dark", "v21_dark", "v21_worst_dark", "v21_mid_dark",
         "painting_t_light", "v21_light", "v21_worst_light", "v21_mid_light", "v2_app", "v1"]


def pct(d: dict, keys: list[str]) -> float:
    return 10 * sum(float(d[k]) for k in keys) / len(keys)


def mean(xs):
    return sum(xs) / len(xs)


def main() -> None:
    tag = sys.argv[1]
    key = json.loads((HERE / f"{tag}_key" / "key.json").read_text(encoding="utf-8"))
    bad = [f for f, h in key["files"].items()
           if not (HERE / tag / f).exists() or hashlib.sha256((HERE / tag / f).read_bytes()).hexdigest() != h]
    revs = sorted(p.stem for p in (HERE / f"{tag}_raw").glob("reviewer*.json"))
    out: list[str] = [f"# FP-21R round {tag} - decoded", "",
                      f"Pack integrity: {'OK, all files match the key hashes' if not bad else 'MISMATCH ' + str(bad)}",
                      f"Reviewers with answers: {', '.join(revs)}", ""]
    S: dict = {}  # S[state][name][rev] = (visual, character, presentation)
    for r in revs:
        ans = json.loads((HERE / f"{tag}_raw" / f"{r}.json").read_text(encoding="utf-8"))
        for st in STATES:
            for L, nm in key[r][st].items():
                d = ans["static"][st][L]
                S.setdefault(st, {}).setdefault(nm, {})[r] = (pct(d, CH + PR), pct(d, CH), pct(d, PR))
            for s in SURR:
                w, m = S[st][f"v21_worst_{s}"][r], S[st][f"v21_mid_{s}"][r]
                S[st].setdefault(f"v21_{s}", {})[r] = tuple(min(a, b) for a, b in zip(w, m))
    for idx, title in ((0, "Visual %"), (1, "Character %"), (2, "Presentation %")):
        out += [f"## {title} (reviewers {' / '.join(revs)} -> mean)", "",
                "| State | " + " | ".join(ORDER) + " |", "|---|" + "---|" * len(ORDER)]
        for st in STATES:
            cells = []
            for nm in ORDER:
                vals = [S[st][nm][r][idx] for r in revs]
                cells.append(" / ".join(f"{v:.0f}" for v in vals) + f" -> **{mean(vals):.1f}**")
            out.append(f"| {st} | " + " | ".join(cells) + " |")
        out.append("")
    out += ["`v21_<surround>` = min(v21_worst, v21_mid) per reviewer and measure (protocol section 4).", "",
            "## Validity (section 5)", ""]
    valid = True
    for st in STATES:
        for r in revs:
            top = S[st]["ref_reframed"][r][0]
            order = S[st]["v1"][r][0] < S[st]["ref_copy"][r][0]
            ok = top >= 90 and order
            valid &= ok
            out.append(f"- {st} {r}: ref_reframed {top:.0f} (>= 90: {top >= 90}); v1 < ref_copy: {order} -> "
                       f"{'ok' if ok else 'INVALID'}")
    out += ["", f"**Round valid: {valid}**", "", "## Proposed gates (section 6)", "",
            "| State | Surround | Character mean (>= 90) | lowest (>= 85) | AC-F3 | R per reviewer | R mean (>= 0.95) "
            "| lowest R (>= 0.90) | AC-F1R |", "|---|---|---|---|---|---|---|---|---|"]
    f3 = f1r = True
    for st in STATES:
        for s in SURR:
            ch = [S[st][f"v21_{s}"][r][1] for r in revs]
            R = [S[st][f"v21_{s}"][r][2] / S[st][f"painting_t_{s}"][r][2] for r in revs]
            ok3 = mean(ch) >= 90 and min(ch) >= 85
            okr = mean(R) >= 0.95 and min(R) >= 0.90
            f3 &= ok3
            f1r &= okr
            out.append(f"| {st} | {s} | {mean(ch):.1f} | {min(ch):.1f} | {'PASS' if ok3 else 'FAIL'} | "
                       f"{' / '.join(f'{x:.3f}' for x in R)} | {mean(R):.3f} | {min(R):.3f} | "
                       f"{'PASS' if okr else 'FAIL'} |")
    out += ["", f"**AC-F3 (character, owner's 90 %): {'PASS' if f3 and valid else 'NOT MET'}**",
            f"**AC-F1R (relative presentation, PROPOSED, not approved): {'PASS' if f1r and valid else 'NOT MET'}**"
            " (as computed; R near 1.000 when reviewers cannot tell Ember from painting_t is not evidence on its own,"
            " see the results document)",
            "", "## FP-21 AC-F1 for continuity (absolute visual, dark surround; rule unchanged)", ""]
    f1 = True
    for st in STATES:
        vis = [S[st]["v21_dark"][r][0] for r in revs]
        ch = [S[st]["v21_dark"][r][1] for r in revs]
        ok = mean(vis) >= 90 and min(vis) >= 85 and mean(ch) >= 90
        f1 &= ok
        ctl = mean([S[st]["painting_t_dark"][r][0] for r in revs])
        out.append(f"- {st}: visual mean {mean(vis):.1f} (control painting_t_dark {ctl:.1f}), lowest "
                   f"{min(vis):.0f}, character mean {mean(ch):.1f} -> {'PASS' if ok else 'FAIL'}")
    out += ["", f"**FP-21 AC-F1 (absolute): {'PASS' if f1 and valid else 'NOT MET'}**"]
    text = "\n".join(out) + "\n"
    (HERE / f"{tag}_decoded.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
