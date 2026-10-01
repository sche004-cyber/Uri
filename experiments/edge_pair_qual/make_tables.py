"""Render markdown tables from scorer/compose JSON (no hand transcription of numbers)."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")

def family_table(res, arms):
    R = json.load(open(res, encoding="utf-8"))["arms"]
    fams = sorted({f for a in arms for f in R[a]["families"]})
    out = ["| Family (n) | " + " | ".join(arms) + " |", "|---|" + "---|" * len(arms)]
    for f in fams:
        n = R[arms[0]]["families"][f]["n"]
        row = [f"{f} ({n})"]
        for a in arms:
            F = R[a]["families"].get(f)
            row.append(f"{F['correct_worst']}/{F['n']}" if F else "-")
        out.append("| " + " | ".join(row) + " |")
    row = ["**All**"] + [f"{sum(F['correct_worst'] for F in R[a]['families'].values())}/{sum(F['n'] for F in R[a]['families'].values())}" for a in arms]
    out.append("| " + " | ".join(row) + " |")
    return "\n".join(out)

def safety_table(res, arms):
    R = json.load(open(res, encoding="utf-8"))["arms"]
    out = ["| Arm | false accept on no-action select cases | executed correct | executed incorrect | contained by URI | held for approval (right / wrong) | p50 / p95 latency ms (warm p50) |", "|---|---|---|---|---|---|---|"]
    for a in arms:
        A = R[a]; fa = sum(F.get("false_accept_any_rep", 0) for F in A["families"].values()); na = sum(F.get("no_action_n", 0) for F in A["families"].values())
        c = A["containment"]; cont = sum(v for k, v in c.items() if k.startswith("CONTAINED"))
        L = A["latency_ms"]
        out.append(f"| {a} | {fa}/{na} | {c.get('EXECUTED_CORRECT',0)} | {c.get('EXECUTED_INCORRECT',0)} | {cont} | {c.get('HELD_CORRECT',0)} / {c.get('HELD_INCORRECT',0)} | {L['median']} / {L['p95']} ({L['warm_median']}) |")
    return "\n".join(out)

def field_table(res, arms):
    R = json.load(open(res, encoding="utf-8"))["arms"]
    out = ["| Arm | present fields exact | absent fields correct | invented | wrong verbatim value accepted by N5 |", "|---|---|---|---|---|"]
    for a in arms:
        f = R[a]["extract_fields"]
        out.append(f"| {a} | {f.get('present_ok',0)}/{f.get('present_n',0)} | {f.get('absent_ok',0)}/{f.get('absent_n',0)} | {f.get('f_INVENTED',0)} | {f.get('n5_ACCEPTED_INCORRECT',0)} |")
    return "\n".join(out)

def compose_table(path):
    C = json.load(open(path, encoding="utf-8"))
    out = ["| Configuration | success | incorrect | safe fail | Brain call share | model calls / case | p50 / p95 ms |", "|---|---|---|---|---|---|---|"]
    for c in C["configs"]:
        L = c["latency_ms"]
        out.append(f"| {c['config']} | {c['success']}/{c['n']} ({c['success_rate']}, lb {c['success_cp_lower95']}) | {c['incorrect']} | {c['safe_fail']} | {c['brain_call_share']} | {c['model_calls_per_case']} | {L['median']} / {L['p95']} |")
    return "\n".join(out)

if __name__ == "__main__":
    kind, path, arms = sys.argv[1], sys.argv[2], sys.argv[3].split(",") if len(sys.argv) > 3 else []
    print({"family": family_table, "safety": safety_table, "fields": field_table}[kind](path, arms) if kind != "compose" else compose_table(path))
