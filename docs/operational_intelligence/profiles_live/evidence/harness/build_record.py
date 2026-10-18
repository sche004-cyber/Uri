"""Build the UI qualification record (docs/dev_workflow/lifecycle/UI_QUALIFICATION_TEMPLATE.json schema) for
RUNTIME-PROFILES-INTEG from the live evidence, and copy the evidence into the candidate's docs tree.

v2 (after independent review RPI-R1): the record binds to CODE_COMMIT. Runs on earlier code commits are kept and
listed as HISTORY with their own results (never dropped). A returning run is classified as the harness ordering
artifact only when ALL of these hold (R1-03): its only failures are R-companion-persisted and R-theme-persisted, the
observed values are exactly the defaults written by R-restore-defaults (companion solar, theme null), and the run
that started immediately before it was itself a returning run. Each LQ criterion gets its own verdict (R1-01).

    python -I tools/build_record.py
"""
import glob
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(r"D:\uri-dev\uri-runtime-profiles-integ")
DEST = SRC / "docs" / "operational_intelligence" / "profiles_live"
EV = DEST / "evidence"
LAB = Path(r"D:\uri-dev\uri-runtime-vram-r1\research\runtime_vram_r1")
CODE_COMMIT = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SRC, text=True).strip()
CODE_COMMIT = json.loads((ROOT / "evidence" / "materialize-e.json").read_text())["candidate_head"]
PROFILES = {"c64k-visgpu-mtpoff": "P1 64K + GPU vision", "c64k-visoff-mtpoff": "P2 64K main only",
            "c32k-visgpu-mtpoff": "P3 32K + GPU vision"}
ORDER_FAILS = {"R-companion-persisted", "R-theme-persisted"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def runs():
    out = []
    for d in sorted(glob.glob(str(ROOT / "evidence" / "live" / "*"))):
        d = Path(d)
        try:
            start = json.loads((d / "session-start.json").read_text())
            fin = json.loads((d / "ui-finished.json").read_text())
            phases = json.loads((d / "brain-phases.json").read_text())
            native = json.loads((d / "native-execution.json").read_text())
        except (OSError, ValueError):
            out.append({"label": d.name, "complete": False})
            continue
        mode = fin.get("mode")
        obs = json.loads((d / f"observations-{mode}.json").read_text()) if (d / f"observations-{mode}.json").exists() else []
        checks = [x for x in obs if x.get("label") == "check"]
        ready = json.loads((d / "brain-ready.json").read_text()).get("host", {}) if (d / "brain-ready.json").exists() else {}
        samples = json.loads((d / "resource-samples.json").read_text()) if (d / "resource-samples.json").exists() else []
        ls = [v for s in samples for v in (s.get("gpu") or {}).values() if v.get("name") == "llama-server.exe"]
        out.append({"label": d.name, "complete": True, "started": start.get("started_utc"),
                    "profile": (start.get("profile") or {}).get("id"), "mode": mode, "checks": checks,
                    "failures": fin.get("failures") or [], "phases": [(p["state"], round(p["t"]), p.get("detail")) for p in phases],
                    "source_head": native.get("source_head"), "flutter_exit": native.get("exit_code"),
                    "calibration": (ready.get("calibration") or {}).get("decode_tps"),
                    "fit": ((ready.get("gpu") or {}).get("fit") or {}).get("verdict"),
                    "margin": ((ready.get("gpu") or {}).get("fit") or {}).get("margin_mib"),
                    "brain_max": (max((v["dedicated_mib"] for v in ls), default=None),
                                  max((v.get("non_local_mib") or 0 for v in ls), default=None)),
                    "worker_instance": (json.loads((d / "worker-instance.json").read_text()).get("brain_profile")
                                        if (d / "worker-instance.json").exists() else None)})
    return out


def classify(rs):
    done = sorted([r for r in rs if r["complete"]], key=lambda r: r["started"])
    prev = {}
    for i, r in enumerate(done):
        prev[r["label"]] = done[i - 1] if i else None
    rows = []
    for r in rs:
        if not r["complete"]:
            rows.append({"journey_id": r["label"], "result": "NOT VERIFIED", "mandatory": False, "class": "INCOMPLETE",
                         "failure_and_recovery": "no complete run record (session-start/ui-finished/brain-phases missing)"})
            continue
        current = r["source_head"] == CODE_COMMIT
        crash = any(p[0] == "FAILED" for p in r["phases"])
        order = False
        if r["mode"] == "returning" and set(r["failures"]) == ORDER_FAILS:
            vals = {c["id"]: c for c in r["checks"] if c["id"] in ORDER_FAILS}
            p = prev[r["label"]]
            order = (vals.get("R-companion-persisted", {}).get("choice") == "solar"
                     and vals.get("R-theme-persisted", {}).get("theme") is None
                     and p is not None and p["mode"] == "returning")
        result = "FAIL" if r["failures"] else "PASS"
        note = None
        if crash:
            note = "CRASH-1: llama-server exited 0xC0000409 (LOCAL_BRAIN_EXITED:3221226505); later Brain journeys had no Brain"
        if order:
            result = "NOT VERIFIED"
            note = (f"harness ordering artifact: the run that started just before ({prev[r['label']]['label']}) was a "
                    "returning run, whose final step R-restore-defaults reset companion/theme to the observed defaults "
                    "(solar, null); every other check PASS")
        rows.append({
            "journey_id": r["label"], "class": "CURRENT" if current else "HISTORY", "source_head": r["source_head"],
            "user": "returning" if r["mode"] == "returning" else "first_time",
            "mandatory": current, "profile": r["profile"],
            "steps": [f"canonical UI V2 driver mode {r['mode']} through the production main() of the candidate app; Brain "
                      f"host ws_brain_host --profile on {PROFILES.get(r['profile'], r['profile'])}"],
            "expected": "every driver check PASS; Brain READY serving the app on the profile",
            "actual": f"{sum(1 for c in r['checks'] if c['result'] == 'PASS')}/{len(r['checks'])} PASS; failures "
                      f"{r['failures']}; last Brain phase {r['phases'][-1]}; calibration {r['calibration']} tok/s; fit "
                      f"{r['fit']} ({r['margin']} MiB); Brain max dedicated/non-local {r['brain_max']}; worker selection "
                      f"{r['worker_instance']}",
            "evidence": [f"docs/operational_intelligence/profiles_live/evidence/live/{r['label']}/"],
            "failure_and_recovery": note, "evidence_status": "COMPLETED_WITH_RESULT", "result": result})
    return rows


def copy_evidence(rows):
    if EV.exists():
        shutil.rmtree(EV)
    png_runs = {r["journey_id"] for r in rows if r.get("class") == "CURRENT"} | {"p1b-main", "s4-p1-main", "c-p2-main", "c-p2-ret", "c-p3-main", "c-p3-ret"}  # c-*: committed in a5605ae8, kept
    for sub in ("live", "soak", "assist", "switch_live"):
        for f in (ROOT / "evidence" / sub).rglob("*"):
            if not f.is_file() or (f.name.endswith(".tmp")):
                continue
            rel = f.relative_to(ROOT / "evidence")
            if f.suffix == ".png" and rel.parts[1] not in png_runs:
                continue
            out = EV / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)
    for f in ("live_summary.json", "materialize-b.json", "provision-b.json", "materialize-c.json", "provision-c.json",
              "materialize-d.json", "provision-d.json", "materialize-e.json", "provision-e.json", "uibuild-release.log",
              "uibuild-release-e.log", "ram1_snapshot.json"):
        if (ROOT / "evidence" / f).exists():
            shutil.copy2(ROOT / "evidence" / f, EV / f)
    # CRASH-1 evidence (R1-02): the crashed server's own log, the reproduction script and its result.
    c1 = EV / "crash1"
    c1.mkdir(parents=True, exist_ok=True)
    for f in (ROOT / "fixtures" / "brain-state-p1b-main" / "logs").glob("*.log"):
        shutil.copy2(f, c1 / f.name)
    shutil.copy2(LAB / "crash_repro.py", c1 / "crash_repro.py")
    for f in (LAB / "evidence" / "crash_repro").rglob("*.json"):
        out = c1 / "crash_repro" / f.relative_to(LAB / "evidence" / "crash_repro")
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, out)
    for f in (ROOT / "research").glob("*.md"):
        (EV / "research").mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, EV / "research" / f.name)
    (EV / "harness").mkdir(parents=True, exist_ok=True)
    for f in ("live_session.py", "run_live_ui.py", "uiv2_driver.dart", "go.sh", "assist_vision_app.py", "soak.py",
              "switch_live.py", "summarize_live.py", "build_record.py", "_patch_harness.py", "_patch_harness_b.py",
              "_patch_harness_c.py", "_patch_harness_d.py", "_patch_harness_e.py", "binding.py", "finalize_record.py", "chain10.sh", "chain11.sh"):
        if (ROOT / "tools" / f).exists():
            shutil.copy2(ROOT / "tools" / f, EV / "harness" / f)


def load(sub, name):
    return {p.parent.name: json.loads(p.read_text()) for p in (ROOT / "evidence" / sub).glob(f"*/{name}")}


def main():
    rows = classify(runs())
    copy_evidence(rows)
    soak, assist, switch = load("soak", "soak.json"), load("assist", "assist_vision.json"), load("switch_live", "switch_live.json")
    cur = [r for r in rows if r.get("class") == "CURRENT"]

    def prof_ok(pid, user):
        rr = [r for r in cur if r.get("profile") == pid and r["user"] == user]
        return ("PASS" if rr and all(r["result"] == "PASS" for r in rr if r["result"] != "NOT VERIFIED")
                and any(r["result"] == "PASS" for r in rr) and not any(r["result"] == "FAIL" for r in rr)
                else "FAIL" if any(r["result"] == "FAIL" for r in rr) else "NOT VERIFIED")
    lq = {}
    hist = [r for r in rows if r.get("class") == "HISTORY"]
    for pid, name in PROFILES.items():
        lq[f"LQ-1 {name}"] = {"first_time": prof_ok(pid, "first_time"), "returning": prof_ok(pid, "returning")}
        h = [r for r in hist if r.get("profile") == pid]
        if h:   # review R2-03: earlier-commit results stay visible per profile
            lq[f"LQ-1 {name}"]["history_on_earlier_commits"] = {r["journey_id"]: r["result"] for r in h}
    def bound(v):
        b = v.get("binding") or {}
        return b.get("ok") is True and b.get("materialized_from") == CODE_COMMIT

    lq["LQ-2 Assist vision (application path)"] = {
        k: (("PASS" if v.get("correct_all") else "FAIL") if bound(v)
            else "SUPPORTING ONLY (no source binding): " + ("correct" if v.get("correct_all") else "FAIL"))
        for k, v in assist.items()}
    def soak_verdict(v):
        if v.get("classification") != "COMPLETED_WITH_RESULT":
            return "NOT VERIFIED (harness %s: %s)" % (v.get("classification"), v.get("error"))
        if not bound(v):
            sm = v.get("summary") or {}
            ok = sm.get("max_brain_non_local", 0) < 1000 and sm.get("decode_min", 0) >= 60
            return "SUPPORTING ONLY (no source binding; ran before R2-02): " + ("would PASS" if ok else "FAIL")
        sm = v.get("summary") or {}
        return "PASS" if sm.get("max_brain_non_local", 0) < 1000 and sm.get("decode_min", 0) >= 60 else "FAIL"
    lq["LQ-3 sustained operation"] = {k: soak_verdict(v) for k, v in soak.items()}
    sw = [v for v in switch.values() if v.get("classification") == "COMPLETED_WITH_RESULT"]
    lq["LQ-4 profile switch with conversation continuity (worker level)"] = (
        {k: ("SUPPORTING ONLY (no source binding): " + ("PASS" if v.get("all_recalled") and v.get("all_answer_route")
                                                        and v.get("all_switches_ready_on_new_profile") else "not PASS")
             if not bound(v) and "all_answer_route" in v else
             "NOT VERIFIED (test design: recall turns were routed to Core memory, not the conversation; superseded)"
             if "all_answer_route" not in v else
             "NOT VERIFIED (a recall turn was not routed to the answer channel)" if not v.get("all_answer_route") else
             "PASS" if v.get("all_recalled") and v.get("all_switches_ready_on_new_profile") and v.get("worker_pid_constant")
             else "FAIL") for k, v in switch.items() if v.get("classification") == "COMPLETED_WITH_RESULT"}
        or "NOT VERIFIED")
    rec = {
        "schema": "uri-ui-qualification/1",
        "task": {"task_id": "RUNTIME-PROFILES-INTEG", "capability": "Runtime v1 resource profiles (Brain host --profile + worker profile selection/follower)",
                 "classification": "INDIRECT", "no_ui_reason": None, "phase": "live qualification before any default change",
                 "candidate_branch": "milestone/runtime-profiles-integ-20261017", "code_commit": CODE_COMMIT,
                 "acceptance_criteria_file": "docs/operational_intelligence/RUNTIME_PROFILES_INTEGRATION_PLAN.md",
                 "acceptance_criteria": ["LQ-1", "LQ-2", "LQ-3", "LQ-4"]},
        "environment": {
            "windows": subprocess.run(["cmd", "/c", "ver"], capture_output=True, text=True).stdout.strip(),
            "app_build": "candidate uri_ui, debug build via flutter test integration_test (driver runs); release build for soak windows",
            "core": f"materialized runtime e8e3b652 + Phase 2 OQ overlay + candidate {CODE_COMMIT[:8]} (evidence/materialize-e.json; runtime-e, installation rp-e)",
            "brain": "llama.cpp b11425 Vulkan, Qwen3.6-35B-A3B UD-IQ3_S (+ mmproj-F16 on vision profiles), MTP off on all tested profiles; frozen config unchanged",
            "dependencies": [], "gpu_override": "none (lease, no contention override)"},
        "functional": rows,
        "criteria": lq,
        "sustained_operation": {k: {kk: v.get(kk) for kk in ("classification", "summary", "events", "host_exit", "profile_arg")} for k, v in soak.items()},
        "assist_application_path": {k: {kk: v.get(kk) for kk in ("classification", "decode_before", "decode_after", "correct_all", "asks", "stand_ins")} for k, v in assist.items()},
        "profile_switch": {k: {kk: v.get(kk) for kk in ("classification", "all_recalled", "all_switches_ready_on_new_profile",
                                                        "worker_pid_constant", "steps", "commit")} for k, v in switch.items()},
        "ux": {"discoverability": [], "navigation": [], "tool_visibility": [], "control_usability": [], "feedback": [],
               "consistency": [], "accessibility": [], "onboarding_needed": []},
        "improvements": [], "remaining_limitations": [],
        "independent_audit": {"auditor": "fresh read-only Claude subagent (lifecycle tier: subagent review; not driver-verified)",
                              "verdict": None, "reviewed_commit": None},
        "status": None, "status_reason": None, "recorded_at": datetime.now(timezone.utc).isoformat(), "corrections": []}
    (DEST / "UI_QUALIFICATION_RUNTIME_PROFILES.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    print(CODE_COMMIT[:8], json.dumps(lq, indent=1))
    print(sum(1 for f in EV.rglob('*') if f.is_file()), "evidence files")


if __name__ == "__main__":
    main()
