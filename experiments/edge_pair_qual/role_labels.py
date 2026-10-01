"""Pre-registered role labels (PREREGISTRATION.md §6) per arm and family, holdout, worst of 3."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
R = json.load(open(sys.argv[1], encoding="utf-8"))["arms"]
arms = sys.argv[2].split(",")
fams = sorted({f for a in arms for f in R[a]["families"]})
rows = ["| Family | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]
out = {}
for f in fams:
    row = [f]
    for a in arms:
        F = R[a]["families"].get(f)
        if not F:
            row.append("-"); continue
        acc = F["acc_worst"]; zt = F.get("executed_incorrect", 0)
        lab = "UNSUITABLE" if (acc < 0.80 or zt) else ("CANDIDATE" if acc >= 0.95 else "PARTIAL")
        out.setdefault(a, {})[f] = {"label": lab, "k": F["correct_worst"], "n": F["n"], "cp_lower95": F["cp_lower95"], "zero_tolerance_violations": zt}
        row.append(f"{lab} {F['correct_worst']}/{F['n']} lb {F['cp_lower95']}" + (f" ZT{zt}" if zt else ""))
    rows.append("| " + " | ".join(row) + " |")
print("\n".join(rows))
json.dump(out, open(sys.argv[3], "w"), indent=1)
