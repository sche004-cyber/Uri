"""Print failing cases for one arm and predicate (diagnostic; reads results + raw runs)."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
res, runs, arm, kind = sys.argv[1], sys.argv[2].split(","), sys.argv[3], sys.argv[4]
n = int(sys.argv[5]) if len(sys.argv) > 5 else 12
R = json.load(open(res, encoding="utf-8"))
cases = {c["id"]: c for c in json.load(open("battery/cases.json", encoding="utf-8"))}
raw = {}
for p in runs:
    for l in open(p, encoding="utf-8"):
        r = json.loads(l)
        if r["type"] == "call" and r["rep"] == 1:
            raw[(r["arm"], r["case"])] = r
k = 0
for cid, d in R["cases"].items():
    c = cases[cid]
    if arm not in d:
        continue
    e = d[arm][0]
    ok = (kind == "exec_incorrect" and e.get("containment") == "EXECUTED_INCORRECT") or \
         (kind in ("extract", "label", "route", "select") and c["kind"] == kind and not e["correct"])
    if ok:
        r = raw[(arm, cid)]
        exp = c["expected"]
        print(cid, "|", c["text"][:60], "|", (c.get("document") or "")[:60].replace("\n", " / "), "| exp", json.dumps(exp, ensure_ascii=False)[:120],
              "| got", json.dumps(r["calls"], ensure_ascii=False)[:160], "|", e.get("outcome"))
        k += 1
        if k >= n:
            break
