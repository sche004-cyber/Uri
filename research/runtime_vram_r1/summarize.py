"""Table of every probe: request, residency, demotion, decode, vision. Prints markdown; writes evidence/summary.json."""
import glob
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent


def med(xs):
    xs = [x for x in xs if x]
    return round(statistics.median(xs), 1) if xs else None


rows = []
for f in sorted(glob.glob(str(HERE / "evidence" / "probe" / "*" / "probe.json"))):
    r = json.load(open(f, encoding="utf-8"))
    b = r.get("buffers") or {}
    dev = b.get("device_mib") or {}
    sp = r.get("speed") or {}
    p = r["profile"]
    loaded = (r.get("loaded") or {}).get("server") or {}
    after = (r.get("after_vision") or r.get("after_speed") or {}).get("server") or {}
    host = b.get("host_total_mib") or 0
    rows.append({
        "run": Path(f).parent.name, "class": r.get("classification"), "ctx": p["ctx"], "mtp": p["mtp"],
        "vision": p["vision"], "draft_kv": p.get("draft_kv") or "f16",
        "free_before": (r.get("before") or {}).get("free_for_one_process_mib"),
        "request": b.get("device_total_mib"), "host_visible": host,
        "draft_mib": round(sum(v for k, v in dev.items() if k.startswith("draft.")), 1),
        "vision_mib": round(sum(v for k, v in dev.items() if k.startswith("vision.")), 1),
        "kv_mib": dev.get("main.KV"), "dedicated": after.get("dedicated_mib") or loaded.get("dedicated_mib"),
        "non_local": after.get("non_local_mib"),
        "demoted_est": (round(after["non_local_mib"] - host, 1) if after.get("non_local_mib") is not None else None),
        "load_s": r.get("load_seconds"),
        "prose_tps": med([s.get("decode_tps") for s in sp.get("prose", [])]),
        "uri_tps": med([s.get("decode_tps") for s in sp.get("uri_structured", [])]),
        "uri_prefill_1200": next((round(s["prompt_tps"]) for s in sp.get("uri_structured", [])
                                  if (s.get("prompt_n") or 0) > 1000), None),
        "vision_first": (r.get("vision") or [{}])[0].get("prompt_ms"),
        "vision_ok": all(v.get("mentions_401") for v in r.get("vision") or []) if r.get("vision") else None,
        "error": r.get("error")})
json.dump(rows, open(HERE / "evidence" / "summary.json", "w"), indent=1)
cols = ["run", "class", "ctx", "mtp", "vision", "draft_kv", "free_before", "request", "dedicated", "non_local",
        "host_visible", "demoted_est", "draft_mib", "vision_mib", "kv_mib", "load_s", "prose_tps", "uri_tps",
        "uri_prefill_1200", "vision_first", "vision_ok", "error"]
print("| " + " | ".join(cols) + " |")
print("|" + "---|" * len(cols))
for r in rows:
    print("| " + " | ".join(str(r[c]) for c in cols) + " |")
