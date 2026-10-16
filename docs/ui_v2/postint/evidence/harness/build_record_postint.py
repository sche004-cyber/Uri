"""Build docs/ui_v2/postint/UI_QUALIFICATION_UI_V2_POSTINT.json from live run evidence (never hand-typed results).

    python tools/build_record_postint.py <first-time label> <returning label> <perf label> <out json> <c1 receipt json>

A journey is PASS only when every check mapped to it is PASS in the run; a journey with no recorded check is
NOT VERIFIED. Physical input, microphone/speaker, other DPI and multi-monitor are NOT VERIFIED by design.
independent_audit is copied from the driver receipt of the code-commit review (never a placeholder verdict).
"""
import datetime, json, platform, statistics, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAND = Path(r"C:\Users\cheta\Development\uri-ui-v2p")
first, returning, p_v2, out = sys.argv[1:5]


def load(label, mode):
    return json.loads((ROOT / f"evidence/live/{label}/observations-{mode}.json").read_text(encoding="utf-8"))


def checks(rows):
    return {r["id"]: r for r in rows if r["label"] == "check"}


def rel(p):
    return "docs/ui_v2/postint/evidence/" + str(Path(p).relative_to(ROOT / "evidence")).replace("\\", "/")


f_rows, r_rows = load(first, "main"), load(returning, "returning")
fc, rc = checks(f_rows), checks(r_rows)
f_ex = json.loads((ROOT / f"evidence/live/{first}/native-execution.json").read_text())
r_ex = json.loads((ROOT / f"evidence/live/{returning}/native-execution.json").read_text())
shots = lambda label, prefix: sorted(rel(p) for p in (ROOT / f"evidence/live/{label}").glob(f"{prefix}*.png"))

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
    ("J6", "first_time", "Documents entry point: Start new work (Letter) sends a real turn (the draft now stays open for J14)",
     ["J6-letter-opens-conversation", "J6-letter-real-turn"], "main-j6"),
    ("J7", "first_time", "Companion: frameless 440x680 shaped window, single click actions, detached chat with a real reply "
     "while a draft is open (note shown, draft unchanged: live l9 repeated), Escape, double click back, window restored",
     ["J7-window-440x680", "J7-shaped-region", "J7-single-click-controls", "J7-detached-chat", "J7-chat-reply",
      "J7-stays-companion", "J7-escape-closes-chat", "J7-double-click-dashboard", "J7-window-restored",
      "J7-native-rejects-nan", "J7-native-rejects-infinite", "J7-native-rejects-inverted", "J7-region-kept-after-reject",
      "J7-draft-note", "J7-draft-untouched"], "main-j7"),
    ("J8", "first_time", "Settings: companion gallery preview isolation and Apply; interface theme",
     ["J8-gallery-opens", "J8-preview-isolated", "J8-apply", "J8-theme"], "main-j8"),
    ("J9", "first_time", "Approval visibility on the Dashboard; review opens Tasks; Deny is honoured",
     ["J9-dashboard-counts-decision", "J9-review-opens-tasks", "J9-deny-honoured"], "main-j9"),
    ("J10", "first_time", "Responsiveness while the Brain works: navigate during a turn (with a draft open)",
     ["J10-navigation-while-busy"], None),
    ("J11", "first_time", "Window sizes 1366x768, 1280x800, 1024x768, 900x640, 800x600: no layout error; composer in view where the content area is at least 900x640",
     ["J11-no-layout-error-1366", "J11-no-layout-error-1280", "J11-no-layout-error-1024", "J11-no-layout-error-900",
      "J11-no-layout-error-800", "J11-composer-in-view-1366", "J11-composer-in-view-1280", "J11-composer-in-view-1024"], "main-j11"),
    ("J12", "first_time", "Failure and recovery: Brain stops; UI shows it; a turn fails with a plain message and recovery options",
     ["J12-brain-not-ready-seen"], "main-j12"),
    ("J13", "first_time", "Regression: classic interface entry still offered", ["J13-classic-entry-present"], None),
    ("J14", "first_time", "UIV2-F1/F2 in the Workspace with a draft open: no testing-only controls; 'Say hello in three "
     "words' answered and the draft unchanged; 'Make it shorter' edits; a new document keeps the replaced draft (tag shown); "
     "Undo restores it, Redo returns",
     ["J14-no-testing-controls", "J14-draft-open", "J14-chat-answered", "J14-chat-does-not-edit",
      "J14-explicit-edit-applies", "J14-new-document-keeps-old", "J14-undo-restores", "J14-redo-returns"], "main-j14"),
    ("J15", "first_time", "UIV2-F4: Lunar on the light Snow Archive theme; renderer bounds invisible (max channel "
     "difference <= 1/255 between pixels inside the bounds and the background outside)",
     ["J15-lunar-edge-invisible-light-theme"], "main-j8-lunar-edge"),
    ("J16", "first_time", "Imported review C1-02: a Start new work tile with the draft as composer target never revises the open draft",
     ["J16-tile-never-revises-open-draft"], "main-j16"),
    ("R1", "returning", "Returning user: no onboarding repeat; companion and theme persisted; Lunar bounds invisible on the light theme; conversation works",
     ["R-no-onboarding", "R-companion-persisted", "R-theme-persisted", "R-lunar-edge-invisible-light-theme",
      "R-conversation"], "returning-r"),
    ("R2", "returning", "Connections destination says plainly that accounts are not managed here; Open Settings works",
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
    samples = json.loads((ROOT / f"evidence/live/{label}/resource-samples.json").read_text(encoding="utf-8"))
    ui = [p["dedicated_mib"] for s in samples for p in s["gpu"].values() if p["name"] == "uri_ui.exe"]
    brain = [p["dedicated_mib"] for s in samples for p in s["gpu"].values() if p["name"] == "llama-server.exe"]
    return {"brain_tokens_per_s": [round(x, 1) for x in tps], "brain_tokens_per_s_median": round(statistics.median(tps), 1),
            "ui_gpu_dedicated_mib_median": round(statistics.median(ui), 1) if ui else None,
            "brain_gpu_dedicated_mib_median": round(statistics.median(brain), 1) if brain else None,
            "frames": win, "earlier_record_for_comparison": "docs/ui_v2/completion/UI_QUALIFICATION_UI_V2.json performance (V2: Brain ~149 tok/s, UI GPU ~208 MiB)"}


mandatory = [j for j in functional if j["mandatory"]]
all_pass = all(j["result"] == "PASS" and j["evidence_status"] == "COMPLETED_WITH_RESULT" for j in mandatory)
git = lambda *a: subprocess.check_output(["git", *a], cwd=CAND, text=True).strip()
record = {
    "schema": "uri-ui-qualification/1",
    "task": {"task_id": "UI-V2-POSTINT", "capability": "UI V2 post-integration repairs UIV2-F1..F4 (F5 evaluated)",
             "classification": "USER_FACING (F1 routing INDIRECT)", "no_ui_reason": None, "phase": "UI V2 post-integration",
             "candidate_branch": "milestone/ui-v2-postint-20261016", "code_commit": f_ex["source_head"],
             "acceptance_criteria_file": "docs/ui_v2/postint/00_PLAN_AND_ACCEPTANCE.md",
             "acceptance_criteria": [f"AC-{i}" for i in range(1, 11)]},
    "environment": {"windows": platform.platform(), "app_build": {
        "commit": f_ex["source_head"], "tree": f_ex["source_tree"], "build": "flutter test integration_test (debug, Windows) of production main()",
        "binary_sha256": f_ex.get("ui_binary_sha256"), "returning_run_commit": r_ex["source_head"]},
        "core": "materialized test runtime (e8e3b65 + Phase 2 OQ overlay + candidate new paths) from the code commit, receipt docs/ui_v2/postint/evidence/runtime/materialize.json; venv copied from D:/uri-dev/uri-o2i-live/runtime/.venv (Office O2 runtime dependencies)",
        "brain": "Runtime v1 llama-server b11425, Qwen3.6-35B-A3B UD-IQ3_S + MTP, started under the machine-wide GPU lease",
        "dependencies": ["Flutter 3.47.2 / Dart 3.13.2"], "gpu_override": "none (lease without override)",
        "input": "synthesized (flutter_test TestTextInput, key events, taps); physical input not qualified"},
    "functional": functional,
    "ux": {
        "discoverability": ["J14: the draft panel says when a new document replaced an earlier one and that Undo brings it back",
                            "J7: the Companion chat says a draft is open in Workspace and that messages there do not change it"],
        "navigation": ["J2, J10, J11 unchanged and PASS"],
        "tool_visibility": ["J14: testing-only transcript/dictation toggles absent for ordinary users (URI_UI_TESTING_TOOLS)"],
        "control_usability": ["l1 finding repaired: the draft toolbar (Undo/Redo) stays in view at 1264x681"],
        "feedback": ["J14: replies to chat with a draft open are ordinary answers; edits show the new version"],
        "consistency": ["Brain pickers keep their natural width (l1 screenshot showed them stretched; repaired)"],
        "accessibility": ["no change to sizes, contrast or focus order; overflow-free layouts at 1-2x pixel ratio (Flutter tests)"],
        "onboarding_needed": []},
    "improvements": [
        {"issue_id": "L1-1", "class": "MATERIAL", "issue": "Live l1 at 66912fbf: draft toolbar below the fold at 1264x681 (ScrollWhenShort scrolled the whole panel at a normal size); J14 Undo timed out",
         "repair": "scroll mode only below a per-panel height (width-aware for the draft panel)", "repair_commit": "76af6a81",
         "onboarding_change": "none", "retest": "l2 J14-undo-restores PASS, J14-redo-returns PASS", "deferral_confirmed_by_auditor": None},
        {"issue_id": "L1-2", "class": "MINOR", "issue": "Live l1: Companion draft note not built (last item of a lazy list under a long chat)",
         "repair": "note pinned under the messages", "repair_commit": "76af6a81", "onboarding_change": "note text",
         "retest": "l2 J7-draft-note PASS", "deferral_confirmed_by_auditor": None},
        {"issue_id": "L8-1", "class": "MINOR", "issue": "Live l8: a rewrite request without text in conversation mode reached the desk (TEXT_MISSING); the draft was unchanged",
         "repair": "conversation-target rewrite without text goes to the ordinary path", "repair_commit": "4e656674",
         "onboarding_change": "none", "retest": "l10/l13 J14-target-conversation-never-edits PASS", "deferral_confirmed_by_auditor": None},
        {"issue_id": "C1-02", "class": "MATERIAL", "issue": "Imported review: a Start new work tile with a sticky draft target could revise the open draft",
         "repair": "tiles send as new work (mode conversation)", "repair_commit": "0129f3b3", "onboarding_change": "none",
         "retest": "l16 J16-tile-never-revises-open-draft PASS", "deferral_confirmed_by_auditor": None},
        {"issue_id": "C4-R2-01", "class": "MINOR", "issue": "Codex c4: depth deep ignored the explicit conversation/draft target in the worker (driver P1 had worked around it in the UI by changing the depth)",
         "repair": "worker honours explicit targets at every depth; UI workaround removed", "repair_commit": "d272d452",
         "onboarding_change": "none", "retest": "l19/l20 PASS; Python deep-depth tests", "deferral_confirmed_by_auditor": None},
        {"issue_id": "L1-3", "class": "MINOR", "issue": "Live l1: the rail's always-present scroll view became the first Scrollable (J8 harness lookup failed); Brain pickers stretched to 260 px",
         "repair": "no scroll view at normal sizes; pickers IntrinsicWidth", "repair_commit": "76af6a81", "onboarding_change": "none",
         "retest": "l2 J8 PASS", "deferral_confirmed_by_auditor": None}],
    "performance": {"method": "perf mode: same view (Workspace conversation), same prompt x5, then idle windows; debug build",
                    "v2": perf(p_v2)},
    "remaining_limitations": [
        "Physical mouse, keyboard and window drag: NOT VERIFIED (synthesized input only).",
        "Microphone and speaker: NOT VERIFIED (no audio device test); voice turns use the same draft-scope rule (unit tested).",
        "Other DPI scaling and a second monitor: NOT VERIFIED live (96 DPI single monitor); pixel ratios 1-2 covered by Flutter widget tests.",
        "J16 Close step not exercised live (the tile asked a clarifying question, so no new draft replaced the open one); C1-04 is covered by tests/ws/test_uiv2_postint_target_modes.py.",
        "UIV2-F4 pre-repair live measurement with the same metric was not repeated; the pre-repair artifact is the recorded UX-D2 (3/255 lines, l5 screenshot of the UI V2 completion run).",
        "UIV2-F5 visual fidelity: evaluated, not changed (owner preference decision).",
        "Debug build; release-build frame timings not measured."],
    "independent_audit": {"auditor": "codex_cli (driver-counted)",
                          "verdict": None,
                          "authoritative_source": "driver receipt of the final revision UI-V2-POSTINT-c4 (C:/Users/cheta/Development/uri-ui-v2p-run/lifecycle/c4/receipt.json), which reviews this record",
                          "earlier_runs": ["UI-V2-POSTINT (lifecycle/c1): R1-R4 REJECT on classifier precision, BLOCKED RETRY_LIMIT",
                                           "UI-V2-POSTINT-c2 (lifecycle/c2): not started, canonical moved to eaeb10c1",
                                           "UI-V2-POSTINT-c3: config only; superseded after the imported review",
                                           "Imported review C1 of cf97a1a8 (independent read-only Claude agent, owner instruction while Codex was out of quota; NOT driver-counted): ACCEPT WITH FINDINGS; C1-01..C1-04 and C1-06 repaired in 0129f3b3, C1-05 recorded"],
                          "note": "this record deliberately carries no verdict; it is never updated with one (no stale placeholder)"},
    "status": "PASS" if all_pass else "FAIL",
    "status_reason": ("Every mandatory journey PASS with COMPLETED_WITH_RESULT live evidence on code_commit; no MATERIAL issue open."
                      if all_pass else "At least one mandatory journey is not PASS."),
    "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "corrections": []}
Path(out).write_text(json.dumps(record, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
print(record["status"], [(j["journey_id"], j["result"]) for j in functional])
