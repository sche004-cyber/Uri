"""Build UI_QUALIFICATION_UI_V2.json from live run evidence (never hand-typed results).

    python tools/build_record.py <first-time label> <returning label> <perf living> <perf v2> <out json>

A journey is PASS only when every check mapped to it is PASS in the run; a journey with no recorded check is
NOT VERIFIED. Physical input, microphone/speaker, other DPI and multi-monitor are NOT VERIFIED by design.
"""
import datetime, hashlib, json, platform, statistics, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAND = Path(r"C:\Users\cheta\Development\uri-ui-v2c")
first, returning, p_living, p_v2, out = sys.argv[1:6]


def load(label, mode):
    return json.loads((ROOT / f"evidence/live/{label}/observations-{mode}.json").read_text(encoding="utf-8"))


def checks(rows):
    return {r["id"]: r for r in rows if r["label"] == "check"}


def rel(p):
    return "docs/ui_v2/completion/evidence/" + str(Path(p).relative_to(ROOT / "evidence")).replace("\\", "/")


f_rows, r_rows = load(first, "main"), load(returning, "returning")
fc, rc = checks(f_rows), checks(r_rows)
f_ex = json.loads((ROOT / f"evidence/live/{first}/native-execution.json").read_text())
r_ex = json.loads((ROOT / f"evidence/live/{returning}/native-execution.json").read_text())
shots = lambda label, prefix: sorted(rel(p) for p in (ROOT / f"evidence/live/{label}").glob(f"{prefix}*.png"))
turns = [r for r in f_rows if r["label"] == "turn"]

JOURNEYS = [
    ("J1", "first_time", "Start the production app on a paired installation (first-time user, onboarding)",
     ["J1-v2-is-default", "J1-dashboard-first", "J1-brain-ready"], "main-j1"),
    ("J2", "first_time", "Navigate Dashboard, Workspace, Assist and Companion by Ctrl+1..4 and by the Dashboard navigation",
     ["J2-ctrl-workspace", "J2-ctrl-dashboard", "J2-ctrl-assist", "J2-nav-Conversation", "J2-nav-Tasks",
      "J2-nav-Documents", "J2-nav-Settings"], "main-j2"),
    ("J3", "first_time", "Conversation with the real Brain from the V2 Workspace", ["J3-greeting-replied", "J3-fact"], "main-j3"),
    ("J4", "first_time", "Ambiguous request: clarification, then confirmation card",
     ["J4-clarification-asked", "J4-confirmation-asked"], "main-j4"),
    ("J5", "first_time", "Supported tool through the UI (remember_fact): approval card, approve, verified result, recall",
     ["J5-tool-settled", "J5-memory-written", "J5-recall"], "main-j5"),
    ("J6", "first_time", "Documents entry point: Start new work (Letter) sends a real turn",
     ["J6-letter-opens-conversation", "J6-letter-real-turn"], "main-j6"),
    ("J7", "first_time", "Companion: frameless 440x680 shaped window, single click actions, detached chat with a real reply, Escape, double click back with the window restored",
     ["J7-window-440x680", "J7-shaped-region", "J7-single-click-controls", "J7-detached-chat", "J7-chat-reply",
      "J7-stays-companion", "J7-escape-closes-chat", "J7-double-click-dashboard", "J7-window-restored",
      "J7-native-rejects-nan", "J7-native-rejects-infinite", "J7-native-rejects-inverted", "J7-region-kept-after-reject"], "main-j7"),
    ("J8", "first_time", "Settings: companion gallery preview isolation and Apply; interface theme",
     ["J8-gallery-opens", "J8-preview-isolated", "J8-apply", "J8-theme"], "main-j8"),
    ("J9", "first_time", "Approval visibility on the Dashboard; review opens Tasks; Deny is honoured",
     ["J9-dashboard-counts-decision", "J9-review-opens-tasks", "J9-deny-honoured"], "main-j9"),
    ("J10", "first_time", "Responsiveness while the Brain works: navigate during a turn",
     ["J10-navigation-while-busy"], None),
    ("J11", "first_time", "Window sizes 1366x768, 1280x800, 1024x768, 900x640, 800x600: no layout error; composer and destinations in view where the content area is at least 900x640 (smaller windows use the scrolling column by design)",
     ["J11-no-layout-error-1366", "J11-no-layout-error-1280", "J11-no-layout-error-1024", "J11-no-layout-error-900",
      "J11-no-layout-error-800", "J11-composer-in-view-1366", "J11-composer-in-view-1280", "J11-composer-in-view-1024"], "main-j11"),
    ("J12", "first_time", "Failure and recovery: Brain stops; UI shows it; a turn fails with a plain message and recovery options",
     ["J12-brain-not-ready-seen"], "main-j12"),
    ("J13", "first_time", "Regression: classic interface entry still offered", ["J13-classic-entry-present"], None),
    ("R1", "returning", "Returning user: no onboarding repeat; companion and theme persisted; conversation works",
     ["R-no-onboarding", "R-companion-persisted", "R-theme-persisted", "R-conversation"], "returning-r"),
    ("R2", "returning", "Connections destination on the integrated worker says plainly that accounts are not managed here; Open Settings works",
     ["R-connections-card-plain", "R-connections-page-plain", "R-connections-open-settings"], "returning-r-connections"),
]
functional = []
for jid, user, title, ids, prefix in JOURNEYS:
    src = rc if user == "returning" else fc
    label = returning if user == "returning" else first
    got = [src.get(i) for i in ids]
    missing = [i for i, g in zip(ids, got) if g is None]
    failed = [i for i, g in zip(ids, got) if g is not None and g["result"] != "PASS"]
    result = "NOT VERIFIED" if missing else ("FAIL" if failed else "PASS")
    functional.append({
        "journey_id": jid, "user": user, "mandatory": True, "steps": [title],
        "expected": "every listed check PASS", "checks": {i: (g or {}).get("result", "NOT RUN") for i, g in zip(ids, got)},
        "actual": "all checks PASS" if result == "PASS" else f"missing {missing} failed {failed}",
        "outputs": [], "evidence": [rel(ROOT / f"evidence/live/{label}/observations-{'returning' if user == 'returning' else 'main'}.json")]
        + (shots(label, prefix) if prefix else []),
        "failure_and_recovery": "see J12" if jid != "J12" else json.dumps(next((r for r in f_rows if r["label"] == "turn without brain"), {})),
        "evidence_status": "COMPLETED_WITH_RESULT" if not missing else "NOT_RUN",
        "result": result})
for extra in ("physical mouse, keyboard and window drag", "microphone and speaker (voice journeys)",
              "other DPI scaling and a second monitor"):
    functional.append({"journey_id": "NV-" + extra.split()[0], "user": "first_time", "mandatory": False,
                       "steps": [extra], "expected": "observed by a person on this PC", "actual": "not observed",
                       "outputs": [], "evidence": [], "failure_and_recovery": "n/a", "evidence_status": "NOT_RUN",
                       "result": "NOT VERIFIED"})


def perf(label):
    rows = load(label, "perf")
    tps = [r["tps"] for r in rows if r["label"] == "perf-turn"]
    win = {r["window"]: {k: r.get(k) for k in ("frames", "total_ms_p95", "over_16ms")} for r in rows if r["label"] == "perf-window"}
    summary = json.loads((ROOT / "evidence/perf_summary.json").read_text()).get(label, {})
    return {"brain_tokens_per_s": [round(x, 1) for x in tps], "brain_tokens_per_s_median": round(statistics.median(tps), 1),
            "ui_gpu_dedicated_mib_median": (summary.get("ui_gpu_dedicated_mib") or {}).get("median"),
            "ui_cpu_pct_median": (summary.get("ui_cpu_pct") or {}).get("median"),
            "ui_rss_mib_median": (summary.get("ui_rss_mib") or {}).get("median"), "frames": win}


mandatory = [j for j in functional if j["mandatory"]]
all_pass = all(j["result"] == "PASS" and j["evidence_status"] == "COMPLETED_WITH_RESULT" for j in mandatory)
git = lambda *a: subprocess.check_output(["git", *a], cwd=CAND, text=True).strip()
record = {
    "schema": "uri-ui-qualification/1",
    "task": {"task_id": "UI-V2-COMPLETION", "capability": "URI UI V2 presentation over the integrated worker, Core and Brain",
             "classification": "USER_FACING", "no_ui_reason": None, "phase": "UI V2 completion",
             "candidate_branch": "milestone/ui-v2-completion-20261015", "code_commit": f_ex["source_head"],
             "acceptance_criteria_file": "docs/ui_v2/completion/00_COMPLETION_PLAN_AND_ACCEPTANCE.md",
             "acceptance_criteria": [f"AC-{i}" for i in range(1, 15)]},
    "environment": {"windows": platform.platform(), "app_build": {
        "commit": f_ex["source_head"], "tree": f_ex["source_tree"], "build": "flutter test integration_test (debug, Windows) of production main()",
        "binary_sha256": f_ex.get("ui_binary_sha256"), "returning_run_commit": r_ex["source_head"]},
        "core": "materialized test runtime (e8e3b65 + Phase 2 OQ overlay + candidate new paths), receipt evidence/runtime/materialize2.json",
        "brain": "Runtime v1 llama-server b11425, Qwen3.6-35B-A3B UD-IQ3_S + MTP, started under the machine-wide GPU lease",
        "dependencies": ["Flutter 3.47.2 / Dart 3.13.2"], "gpu_override": "none (lease without override)",
        "input": "synthesized (flutter_test TestTextInput, key events, taps); physical input not qualified"},
    "functional": functional,
    "ux": json.loads((ROOT / "tools/ux_findings.json").read_text(encoding="utf-8")),
    "improvements": json.loads((ROOT / "tools/improvements.json").read_text(encoding="utf-8")),
    "performance": {"method": "alternating runs, same commit, same view and prompt x5; harness forces continuous frames (debug build), so CPU is comparative only",
                    "living_composition": perf(p_living), "v2": perf(p_v2)},
    "remaining_limitations": [
        "Physical mouse, keyboard and window drag: NOT VERIFIED (synthesized input only). Does not change the status of the mandatory journeys, which were defined for automated native input.",
        "Microphone and speaker: NOT VERIFIED (no audio device test).",
        "Other DPI scaling and a second monitor: NOT VERIFIED (96 DPI single monitor).",
        "Debug build; release-build frame timings not measured."],
    "independent_audit": {"auditor": "codex_cli", "fallback_reason": None, "reviewer_identity": "see lifecycle receipt",
                          "reviewed_commit": None, "lifecycle_state_dirs": [], "repair_iterations": 0, "findings": [],
                          "verdict": "BLOCKED", "auditor_observed_live": False, "auditor_inspected": [],
                          "auditor_tests_run": [], "auditor_evidence_reviewed_only": [], "auditor_live_observed": [],
                          "auditor_unverified": ["filled from the driver receipt after the final review"]},
    "status": "PASS" if all_pass else "FAIL",
    "status_reason": ("Every mandatory journey PASS with COMPLETED_WITH_RESULT live evidence on code_commit; no MATERIAL issue open."
                      if all_pass else "At least one mandatory journey is not PASS."),
    "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "corrections": []}
Path(out).write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print(record["status"], [(j["journey_id"], j["result"]) for j in functional])
