"""Coexistence table: per run, Brain dedicated / non-local MiB and decode (URI JSON | prose) in phases A-D."""
import glob
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = []
for f in sorted(glob.glob(str(HERE / "evidence" / "coexist" / "*" / "coexist.json"))):
    r = json.load(open(f, encoding="utf-8"))
    row = {"run": Path(f).parent.name, "class": r.get("classification"), "error": r.get("error"),
           "request": (r.get("buffers") or {}).get("device_total_mib"),
           "prefs_unchanged": r.get("owner_prefs_sha256_before") == r.get("owner_prefs_sha256_after")}
    for k in "ABCD":
        p = r.get(k)
        if p:
            row[k] = {"dedicated": p["server"]["dedicated_mib"], "non_local": p["server"]["non_local_mib"],
                      "uri_json_tps": round(p["uri_json_tps"], 1), "prose_tps": round(p["prose_tps"], 1),
                      "chrome": next((m for n, m in p["others"] if n == "chrome.exe"), None),
                      "uri_ui": next((m for n, m in p["others"] if n == "uri_ui.exe"), None)}
    rows.append(row)
json.dump(rows, open(HERE / "evidence" / "coexist_summary.json", "w"), indent=1)
for row in rows:
    cells = [row["run"], row["class"], str(row["request"])]
    for k in "ABCD":
        p = row.get(k)
        cells.append(f"{p['dedicated']:.0f}/{p['non_local']:.0f} {p['uri_json_tps']}|{p['prose_tps']}" if p else "-")
    cells.append(str(row["prefs_unchanged"]))
    print(" | ".join(cells))
