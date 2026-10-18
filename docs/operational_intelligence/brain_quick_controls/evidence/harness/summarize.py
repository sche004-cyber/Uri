"""BRAIN-QC-20261018: summarize one live run (observations.json + samples.json + session.json + native-execution.json)
into live/<label>/summary.json. Every number names the file it comes from; nothing is estimated.

    python -B summarize.py <label>
"""
import json
import pathlib
import sys

LABEL = sys.argv[1]
OUT = pathlib.Path(__file__).resolve().parent.parent / "live" / LABEL


def load(name, default=None):
    p = OUT / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


obs = load("observations.json", []) or load("observations-main.json", [])
# Only samples of THIS session's live host (a report left by an earlier run reads host_alive False).
samples = [s for s in load("samples.json", []) if "sample_error" not in s and s.get("host_alive")]
session = load("session.json", {})
native = load("native-execution.json", {})
finished = load("ui-finished.json", {})

checks = [{"id": r["id"], "result": r["result"]} for r in obs if r.get("label") == "check"]
turns = [{k: r.get(k) for k in ("scenario", "tier", "route", "seconds", "depth_sent", "error")}
         | {"answer": (r.get("text") or "")[:160],
            "decode_tps": (r.get("metrics") or {}).get("predicted_per_second"),
            "prompt_n": (r.get("metrics") or {}).get("prompt_n"), "cache_n": (r.get("metrics") or {}).get("cache_n")}
         for r in obs if r.get("label") == "turn"]

# Per profile: server pids, calibration, VRAM of llama-server while READY on it.
profiles = {}
for s in samples:
    pid = (s.get("profile") or {}).get("id")
    if not pid:
        continue
    p = profiles.setdefault(pid, {"server_pids": set(), "calibration_tps": set(), "llama_dedicated_mib_max": 0,
                                  "llama_non_local_mib_max": 0, "lease_expected_mib": set(), "fit_margin_mib": set(),
                                  "ready_samples": 0})
    srv = (s.get("server") or {}).get("pid")
    if s.get("state") == "READY":
        p["ready_samples"] += 1
        if srv:
            p["server_pids"].add(srv)
        cal = (s.get("calibration") or {}).get("decode_tps")
        if cal:
            p["calibration_tps"].add(cal)
        for g in (s.get("gpu") or {}).values():
            if g.get("name") == "llama-server.exe":
                p["llama_dedicated_mib_max"] = max(p["llama_dedicated_mib_max"], g.get("dedicated_mib") or 0)
                p["llama_non_local_mib_max"] = max(p["llama_non_local_mib_max"], g.get("non_local_mib") or 0)
        if isinstance(s.get("lease"), int):
            p["lease_expected_mib"].add(s["lease"])
        if s.get("fit_margin_mib") is not None:
            p["fit_margin_mib"].add(s["fit_margin_mib"])
for p in profiles.values():
    for k, v in list(p.items()):
        if isinstance(v, set):
            p[k] = sorted(v)

switches = {}
for s in samples:
    sw = s.get("profile_switch")
    if sw and sw.get("id"):
        switches[sw["id"]] = sw                       # the latest record of each switch
switches = list(switches.values())
workers = sorted({(w["pid"], w["create_time"]) for s in samples for w in (s.get("workers") or [])})
states = []
for s in samples:
    key = (s.get("state"), (s.get("profile") or {}).get("id"))
    if not states or states[-1]["key"] != key:
        states.append({"key": key, "utc": s["utc"], "detail": s.get("detail")})
timelines = [{"to": r.get("to"), "ui_seconds": r.get("ui_seconds"), "rows": len(r.get("rows") or [])}
             for r in obs if r.get("label") == "switch-timeline"]
fails = [c["id"] for c in checks if c["result"] != "PASS"]
# Closure (review QCC-R1-01): a closure run must contain every closure check; a missing one is a failure.
CLOSURE_IDS = ["QC-draft-chip-standard", "QC-confirm-dialog-p3", "QC-header-truthful-p3", "QC-truthful-switch-p3",
               "QC-chips-p3", "QC-no-mismatch-p3", "QC-continuity-p3", "QC-assist-vision-on-p3",
               "QC-chips-standard-after-p3", "QC-continuity-standard-after-p3"]
missing = [i for i in CLOSURE_IDS if i not in {c["id"] for c in checks}] if native.get("closure_steps") else []
fails += ["MISSING:" + i for i in missing]
complete = (session.get("result") == "COMPLETED" and finished.get("by") == "driver" and native.get("exit_code") == 0)
summary = {"label": LABEL, "classification": "COMPLETED_WITH_RESULT" if complete else "INCOMPLETE",
           "verdict": "PASS" if complete and not fails and checks else "FAIL",
           "closure_steps": native.get("closure_steps"), "missing_closure_checks": missing,
           "assist": load("assist-result.json"),
           "source_head": native.get("source_head"), "runtime_candidate_head": (session.get("receipt") or {}).get("candidate_head"),
           "runtime_verified": session.get("runtime_verified"), "checks": checks, "failed_checks": fails,
           "turns": turns, "profiles": profiles, "switches": switches, "switch_ui_timelines": timelines,
           "worker_processes": [list(w) for w in workers], "host_state_sequence": [
               {"state": x["key"][0], "profile": x["key"][1], "utc": x["utc"], "detail": x["detail"]} for x in states],
           "lease_after": (session.get("lease_after") or {}).get("state"),
           "brain_config_digest_unchanged": session.get("brain_config_sha256_before") == session.get("brain_config_sha256_after"),
           "brain_listener_after": session.get("brain_listener_after"), "host_exit": session.get("host_exit"),
           "native_exit_code": native.get("exit_code"), "elapsed_s": native.get("elapsed_s")}
(OUT / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: summary[k] for k in ("label", "classification", "verdict", "failed_checks")}, indent=1))
