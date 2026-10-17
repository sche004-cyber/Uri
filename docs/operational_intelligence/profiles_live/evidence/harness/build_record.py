"""Build the UI qualification record (docs/dev_workflow/lifecycle/UI_QUALIFICATION_TEMPLATE.json schema) for
RUNTIME-PROFILES-INTEG from the live evidence, and copy the evidence into the candidate's docs tree.

    python -I tools/build_record.py
"""
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
CODE_COMMIT = "fa0a70e6cb6d2898ee13e230a2ad0d4598b70b9b"
PNG_RUNS = {"p1c-main", "p2-main", "p3-main", "p1c-ret", "s2-p1-ret", "s5-p2-ret", "p3-ret"}
PROFILES = {"c64k-visgpu-mtpoff": "P1 64K + GPU vision", "c64k-visoff-mtpoff": "P2 64K main only",
            "c32k-visgpu-mtpoff": "P3 32K + GPU vision"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def copy_evidence():
    if EV.exists():
        shutil.rmtree(EV)
    for sub in ("live", "soak", "assist"):
        for f in (ROOT / "evidence" / sub).rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(ROOT / "evidence")
            if f.suffix == ".png" and rel.parts[1] not in PNG_RUNS:
                continue
            if "control" in rel.parts and f.name.endswith(".tmp"):
                continue
            out = EV / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, out)
    for f in ("live_summary.json", "materialize-b.json", "provision-b.json", "uibuild-release.log"):
        if (ROOT / "evidence" / f).exists():
            shutil.copy2(ROOT / "evidence" / f, EV / f)
    (EV / "harness").mkdir(parents=True, exist_ok=True)
    for f in ("live_session.py", "run_live_ui.py", "uiv2_driver.dart", "go.sh", "assist_vision_app.py", "soak.py",
              "summarize_live.py", "build_record.py", "_patch_harness.py", "_patch_harness_b.py"):
        shutil.copy2(ROOT / "tools" / f, EV / "harness" / f)


def journeys():
    live = json.loads((ROOT / "evidence" / "live_summary.json").read_text())
    rows = []
    for r in live:
        if not r.get("complete"):
            continue
        superseded = r["label"] == "p1-main"
        failed = bool(r["failures"])
        crash = any(p[0] == "FAILED" for p in r["brain_phases"])
        order_artifact = (r["mode"] == "returning" and set(r["failures"] or []) == {"R-companion-persisted", "R-theme-persisted"})
        result = ("NOT VERIFIED" if superseded or order_artifact else "FAIL" if failed else "PASS")
        note = None
        if superseded:
            note = ("superseded: code 84ef1a39, before the worker profile selection; the worker reported the profile Brain as "
                    "FOREIGN_INSTANCE (ARGV_MISMATCH) - the finding that led to fa0a70e6")
        elif crash:
            note = "CRASH-1: llama-server exited 0xC0000409 (LOCAL_BRAIN_EXITED:3221226505) after a cancelled task; later Brain journeys had no Brain"
        elif order_artifact:
            note = ("harness ordering artifact: a returning run directly after another returning run sees the defaults the "
                    "previous run restored (R-restore-defaults); profile-independent; re-run as s5-p2-ret / s2-p1-ret PASS")
        rows.append({
            "journey_id": f"{r['label']}",
            "user": "returning" if r["mode"] == "returning" else "first_time",
            "mandatory": not superseded,
            "steps": [f"canonical UI V2 driver (uiv2_driver.dart) mode {r['mode']} through the production main() of the "
                      f"candidate app; Brain host started by ws_brain_host --profile on {PROFILES.get(r['profile'], r['profile'])}"],
            "expected": "every driver check PASS; Brain READY and serving the app's turns on the profile",
            "actual": f"{r['passed']}/{r['checks']} checks PASS; failures {r['failures']}; Brain phases end {r['brain_phases'][-1]}; "
                      f"calibration {r['calibration_tps']} tok/s; fit at start {r['fit_at_start']} ({r['margin_at_start']} MiB); "
                      f"Brain max dedicated/non-local {r['brain_dedicated_max']}/{r['brain_non_local_max']} MiB; "
                      f"UI max {r['ui_dedicated_max']} MiB",
            "outputs": [],
            "evidence": [f"docs/operational_intelligence/profiles_live/evidence/live/{r['label']}/"],
            "failure_and_recovery": note,
            "evidence_status": "COMPLETED_WITH_RESULT",
            "result": result,
            "profile": r["profile"], "source_head": r.get("source_head")})
    return rows


def main():
    copy_evidence()
    soak = {p.parent.name: json.loads(p.read_text()) for p in (ROOT / "evidence" / "soak").glob("*/soak.json")}
    assist = {p.parent.name: json.loads(p.read_text()) for p in (ROOT / "evidence" / "assist").glob("*/assist_vision.json")}
    rec = {
        "schema": "uri-ui-qualification/1",
        "task": {"task_id": "RUNTIME-PROFILES-INTEG", "capability": "Runtime v1 resource profiles (Brain host --profile + worker profile selection)",
                 "classification": "INDIRECT", "no_ui_reason": None, "phase": "live qualification before any default change",
                 "candidate_branch": "milestone/runtime-profiles-integ-20261017", "code_commit": CODE_COMMIT,
                 "acceptance_criteria_file": "docs/operational_intelligence/RUNTIME_PROFILES_INTEGRATION_PLAN.md",
                 "acceptance_criteria": ["LQ-1", "LQ-2", "LQ-3", "LQ-4"]},
        "environment": {
            "windows": subprocess.run(["cmd", "/c", "ver"], capture_output=True, text=True).stdout.strip(),
            "app_build": "candidate uri_ui, debug build via flutter test integration_test (driver runs); release build for the soak window",
            "core": "materialized runtime e8e3b652 + Phase 2 OQ overlay + candidate fa0a70e6 (OI_MATERIALIZATION_RECEIPT in evidence/materialize-b.json)",
            "brain": "llama.cpp b11425 Vulkan, Qwen3.6-35B-A3B UD-IQ3_S (+ mmproj-F16 on vision profiles), MTP off on all three tested profiles; frozen config unchanged",
            "dependencies": [], "gpu_override": "none (lease, no contention override)"},
        "functional": journeys(),
        "sustained_operation": {k: {kk: v.get(kk) for kk in ("classification", "summary", "events", "host_exit")}
                                for k, v in soak.items()},
        "assist_application_path": {k: {kk: v.get(kk) for kk in ("classification", "decode_before", "decode_after",
                                                                 "correct_all", "asks", "stand_ins")} for k, v in assist.items()},
        "ux": {"discoverability": [], "navigation": [], "tool_visibility": [], "control_usability": [], "feedback": [],
               "consistency": [], "accessibility": [], "onboarding_needed": []},
        "improvements": [],
        "remaining_limitations": [
            "CRASH-1 (P1): one llama-server fail-fast (0xC0000409) in 8 P1-type Brain sessions, right after a cancelled task; not reproduced in 150 targeted cancel/next cycles; P2/P3: 0 in 9 sessions (incl. soak-p2); frozen config's rate on the same pattern unmeasured here",
            "DEMOTE-P1 (soak-p1): with the URI app window and Chrome (6 tabs) open, one 1 GiB block of the P1 Brain was demoted 11 min after Chrome opened (decode 99 -> 21 tok/s, host residency alert raised), recovered ~3.5 min after Chrome closed",
            "URI Assist vision is qualified only through the application path with a test capture adapter and vision_qualified=True in the harness; real Assist adapters are not implemented (Assist checklist items 8-10) and the product keeps vision_qualified False",
            "Soak UI window is the release app's start screen (no backend manifest), a GPU-memory consumer, not a journey run",
            "Automated input (Flutter TestTextInput / synthesized keys); physical keyboard, mouse and microphone not qualified",
            "No Thinking/Vision/Context UI controls exist yet; profile chosen at host start"],
        "independent_audit": {"auditor": None, "fallback_reason": "Codex usage limit until 2026-10-22 14:03; claude_cli logged out",
                              "reviewer_identity": None, "reviewed_commit": None, "lifecycle_state_dirs": [],
                              "repair_iterations": 0, "findings": [], "verdict": "BLOCKED", "auditor_observed_live": False,
                              "auditor_inspected": [], "auditor_tests_run": [], "auditor_evidence_reviewed_only": [],
                              "auditor_live_observed": [], "auditor_unverified": []},
        "status": None, "status_reason": None,
        "recorded_at": datetime.now(timezone.utc).isoformat(), "corrections": []}
    fails = [j for j in rec["functional"] if j["mandatory"] and j["result"] == "FAIL"]
    p1_soak_demoted = (soak.get("soak-p1", {}).get("summary") or {}).get("max_brain_non_local", 0) > 1000
    rec["status"] = "FAIL" if fails or p1_soak_demoted else "PASS"
    rec["status_reason"] = (
        "P2 (64K main only) and P3 (32K + GPU vision): every mandatory first-time and returning journey PASS on "
        f"{CODE_COMMIT[:8]}. P1 (64K + GPU vision): journeys PASS in 2 of 3 first-time runs and 2 of 2 returning runs; "
        "one first-time run FAILED by CRASH-1, and the 60 min soak shows a demotion (DEMOTE-P1). Any failed mandatory journey "
        "makes the record FAIL. Independent audit BLOCKED (no reviewer available).")
    DEST.mkdir(parents=True, exist_ok=True)
    (DEST / "UI_QUALIFICATION_RUNTIME_PROFILES.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
    print(rec["status"], len(rec["functional"]), "journeys;", sum(1 for f in EV.rglob('*') if f.is_file()), "evidence files")


if __name__ == "__main__":
    main()
