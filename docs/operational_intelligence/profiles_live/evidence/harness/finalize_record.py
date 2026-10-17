"""Add status, limitations, annotations and per-profile qualification to the record built by build_record.py."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REC = Path(r"D:\uri-dev\uri-runtime-profiles-integ\docs\operational_intelligence\profiles_live\UI_QUALIFICATION_RUNTIME_PROFILES.json")
r = json.loads(REC.read_text(encoding="utf-8"))
lq = r["criteria"]
r["annotations"] = {
    "sw3": ("automated verdict FAIL kept. The recall prompt said 'secret number plus 1 now'; the model answered 4818, 4819 "
            "and 4820 across the two switches, i.e. it continued the conversation's own arithmetic, which shows the full "
            "history (including its previous answers) was in context. The strict check expected 4818 each time. Re-run "
            "sw4 with unambiguous wording: PASS."),
    "sw2": "harness bug: the next turn was sent while the Core-routed turn was still finishing (TURN_IN_PROGRESS); fixed in sw3",
    "p1b-main": "CRASH-1, see research/CRASH1_RESEARCH.md (leading hypothesis: host commit exhaustion -> uncaught bad_alloc in the prompt-cache save; not verified)",
    "soak-p1": "DEMOTE-P1, see research/DEMOTION_RESEARCH.md (a 1,021.7 MiB weight allocation moved to system memory under a Chrome burst)"}
r["qualification_by_profile"] = {
    "P2 64K main only (c64k-visoff-mtpoff)": {
        "status": "PASS", "on_commit": r["task"]["code_commit"],
        "evidence": "c-p2-main 68/68, c-p2-ret 12/12 on the current commit; soak-p2 60 min clean (host code identical); switch sw4 PASS; history p2-main/s1-p2-main 68/68, s5-p2-ret 12/12",
        "conditions": "desktop as measured (dwm 0.8-1.06 GB, Chrome 6 tabs); lease fit FITS +1,176..+1,324 MiB"},
    "P3 32K + GPU vision (c32k-visgpu-mtpoff)": {
        "status": "PASS", "on_commit": r["task"]["code_commit"],
        "evidence": "c-p3-main 68/68, c-p3-ret 12/12 on the current commit; soak-p3 60 min clean (min 94 tok/s, no demotion, with Chrome); Assist application path 3/3; switch sw4 PASS",
        "conditions": "fit AT_RISK +474 MiB on the 19:00 desktop (dwm 1.05 GB) and FITS +622 earlier; one soak sample; Assist vision only through the application path (no real capture adapter)"},
    "P1 64K + GPU vision (c64k-visgpu-mtpoff)": {
        "status": "FAIL (unqualified)", "on_commit": "fa0a70e6 (history; not re-run on the current commit)",
        "evidence": "p1b-main FAIL (CRASH-1); soak-p1 FAIL (DEMOTE-P1); p1c-main/s4-p1-main 68/68, p1c-ret/s2-p1-ret 12/12, Assist 3/3",
        "conditions": "stays unqualified until CRASH-1 and DEMOTE-P1 are resolved and re-tested"}}
r["remaining_limitations"] = [
    "CRASH-1 open: root cause not verified (hypothesis: commit exhaustion; E0 measured 386-1,600 MiB free commit during soak-p3 with 6-8 GB physical RAM available, other sessions' PowerShell processes holding ~4.2 GB private each). Affects every profile and the frozen config, not only P1. Reproduction E1 not run.",
    "DEMOTE-P1 open: P1 headroom next to the app is ~200-300 MiB; a browser burst demoted a weight allocation. Mitigations proposed (P3, vision on CPU, 256 MiB suballocation) are not measured.",
    "P3 rests on one 60 min soak at +474..+622 MiB; the demotion research estimates a needed margin of ~+450-500 MiB, so P3 is close to the boundary on a heavier desktop.",
    "UI V2 driver checks do not test conversation continuity across app restarts; continuity across profile switches is verified at worker level (sw4), not through UI clicks.",
    "Soak UI window is the app's start screen (a GPU-memory consumer), not a journey run.",
    "URI Assist vision: application path only; real capture adapters not implemented (owner-gated Assist checklist items 8-10); product keeps vision_qualified False.",
    "Automated input; physical keyboard, mouse and microphone not qualified.",
    "Office (separate session) reports a15/o8 PASS on the 64K main-only profile: Office-reported evidence, not part of this record.",
    "No Thinking/Vision/Context UI controls yet; a profile is chosen by the launcher (selection file + host --profile)."]
fails = [k for k, v in lq.items() if isinstance(v, dict) and any(str(x).startswith("FAIL") for x in v.values())]
r["status"] = "FAIL"
r["status_reason"] = ("Record covers three profiles. P2 and P3: every mandatory journey PASS on the current code commit, "
                      "soaks clean, switch continuity PASS. P1: mandatory failures (CRASH-1 journey, soak demotion) -> the "
                      "record as a whole is FAIL and P1 stays unqualified; failed journeys are listed, not excluded. "
                      f"Criteria with a FAIL entry: {fails}.")
REC.write_text(json.dumps(r, indent=1, default=str), encoding="utf-8")
print(r["status"], fails)
