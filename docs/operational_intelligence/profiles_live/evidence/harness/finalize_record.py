"""Add status, limitations, corrections, annotations and per-profile qualification to the record built by
build_record.py (v3, 2026-10-18: candidate f3d5eb29 = 07dca2a8 + canonical 348677b7; bound evidence only for PASS)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REC = Path(r"D:\uri-dev\uri-runtime-profiles-integ\docs\operational_intelligence\profiles_live\UI_QUALIFICATION_RUNTIME_PROFILES.json")
r = json.loads(REC.read_text(encoding="utf-8"))
code = r["task"]["code_commit"]
lq = r["criteria"]


def soak(label):
    p = ROOT / "evidence" / "soak" / label / "soak.json"
    return json.loads(p.read_text()) if p.exists() else {}


def mem_range(s):
    hm = [x.get("host_mem") or {} for x in s.get("samples", [])]
    cf = [h["commit_free_mib"] for h in hm if "commit_free_mib" in h]
    ap = [h["avail_phys_mib"] for h in hm if "avail_phys_mib" in h]
    if not cf:
        return None
    srt = sorted(cf)
    return {"samples": len(cf), "commit_free_mib_min": srt[0], "commit_free_mib_median": srt[len(srt) // 2],
            "commit_free_mib_max": srt[-1], "avail_phys_mib_min": min(ap), "avail_phys_mib_max": max(ap)}


e0 = {k: mem_range(soak(k)) for k in ("soak-p3", "soak-p3-e", "soak-p2-e") if mem_range(soak(k))}
ram1 = json.loads((ROOT / "evidence" / "ram1_snapshot.json").read_text(encoding="utf-8-sig"))
sp3e = soak("soak-p3-e")
r["e0_host_memory"] = {"measured": e0, "ram1_snapshot": {k: ram1.get(k) for k in ("utc", "free_phys_mib", "commit_used_mib",
                                                                                   "commit_limit_mib", "commit_free_mib")}
                       | {"top_private": (ram1.get("top_private") or [])[:4]}}
r["annotations"] = {
    "sw3": ("automated verdict FAIL kept. INTERPRETATION (not verified): the 'plus 1 now' prompt was ambiguous and the "
            "answers 4818, 4819, 4820 may continue the conversation's own arithmetic. Verified fact: every answer >= 4818 "
            "requires the number 4817 from the first turn, so that turn was in context. sw2 (same prompt) answered 4818 "
            "twice after its first recall failed with TURN_IN_PROGRESS."),
    "sw2": "a harness bug (next turn sent while the previous Core-routed turn was still finishing, TURN_IN_PROGRESS) made one recall fail; the record's criterion entry reports it as a recall not routed to the answer channel, which is the same event",
    "sw4": "PASS (n=1) after the sw3 automated FAIL, with reworded prompts; unbound (ran on runtime-c / 4d782ef1 before the binding helper)",
    "sw5": "PASS (n=1) bound to the current commit with the sw4 wording",
    "p1b-main": "CRASH-1, research/CRASH1_RESEARCH.md: leading HYPOTHESIS (unverified) host commit exhaustion -> uncaught bad_alloc in the prompt-cache save; the 'cancel came after the task finished' reading is INFERRED from log order and b11510 source",
    "soak-p1": "DEMOTE-P1, research/DEMOTION_RESEARCH.md: the demoted block is IDENTIFIED BY SIZE MATCH (1,021.7 MiB = first of 13 weight allocations); the tensor-to-allocation map was not dumped",
    "LQ-4 deviation": ("review R3-02: the plan names the switch P2 -> P1 -> P2; it ran P2 -> P3 -> P2 because P1 is "
                       "unqualified (CRASH-1, DEMOTE-P1) and P3 is the qualified vision profile. Mapping of the other "
                       "LQ-4 items: cold start = every e-* journey run and soak-*-e starts the Brain host cold "
                       "(host_ready / calibration in each run's files); host restart = each sw5 switch stops and "
                       "restarts the host on the new profile (READY in 26.8 s and 21.2 s); VRAM release = sw5 "
                       "vram_release_s. Continuity is verified at worker level, not through UI clicks."),
    "vram_release_s": "switch_live measures release as 'no process holds more than 2 GiB dedicated', not a full release"}
r["qualification_by_profile"] = {
    "P2 64K main only (c64k-visoff-mtpoff)": {
        # Review R3-01: the plan's LQ-3 requires a 60-minute soak on P2; only a bound soak counts.
        "status": ("PASS" if (lq.get("LQ-3 sustained operation") or {}).get("soak-p2-e") == "PASS"
                   else "NOT QUALIFIED YET: journeys and switch PASS; LQ-3 bound soak "
                        + str((lq.get("LQ-3 sustained operation") or {}).get("soak-p2-e", "not run"))),
        "on_commit": code,
        "bound_evidence": "e-p2-main 68/68, e-p2-ret 12/12, sw5 PASS, soak-p2-e (see LQ-3)",
        "supporting": "c-p2-main/c-p2-ret on 4d782ef1, soak-p2 60 min clean (unbound), history runs on fa0a70e6",
        "conditions": "lease fit FITS (+1,176..+1,920 MiB across days)"},
    "P3 32K + GPU vision (c32k-visgpu-mtpoff)": {
        "status": "PASS" if (lq.get("LQ-3 sustained operation") or {}).get("soak-p3-e") == "PASS" else "PENDING soak-p3-e",
        "on_commit": code,
        "bound_evidence": "e-p3-main 68/68, e-p3-ret 12/12, sw5 PASS, assist-p3-e 3/3, soak-p3-e (see LQ-3)",
        "supporting": "c-p3-* on 4d782ef1, soak-p3 60 min clean (unbound), assist-p3 (unbound)",
        "conditions": "fit FITS +1,218 (2026-10-18) .. AT_RISK +474 (2026-10-17 evening, dwm 1.05 GB); Assist only through the application path"},
    "P1 64K + GPU vision (c64k-visgpu-mtpoff)": {
        "status": "FAIL (unqualified)", "on_commit": "fa0a70e6 history only; not re-run",
        "evidence": "p1b-main FAIL (CRASH-1), soak-p1 FAIL (DEMOTE-P1); passing runs p1c-main, s4-p1-main, p1c-ret, s2-p1-ret, assist-p1 (unbound)",
        "conditions": "stays unqualified until CRASH-1 and DEMOTE-P1 are resolved and re-tested"}}
r["remaining_limitations"] = [
    "CRASH-1 open: root cause UNVERIFIED (hypothesis host commit exhaustion; E0: see e0_host_memory - commit is the scarce resource on this PC while physical RAM is available; RAM-1 snapshot shows other sessions' PowerShell processes at ~4 GB private each). Can affect every profile and the frozen config. Reproduction E1 not run.",
    "DEMOTE-P1 open; mitigations (vision on CPU at 64K, 256 MiB suballocation) unmeasured.",
    "P3 sustained operation: soak-p3 (unbound, AT_RISK desktop) and soak-p3-e (bound) - see LQ-3; n=2 at most, near the estimated margin on heavy desktops.",
    "P2 sustained operation: one bound soak, soak-p2-e PASS (n=1, light desktop, free commit above 21 GB; review R3-01); the earlier soak-p2 is unbound and supporting only.",
    "Conversation continuity across profile switches verified at worker level (sw5 bound, sw4), not through UI clicks; the UI V2 driver does not test it.",
    "R2-07 DEFERRED to the UI thread: the UI does not yet render backend.profile; the API exposes it (qualified false). UI presentation is outside this milestone (owner brief: runtime owns capability, not presentation).",
    "Soak UI window is the app's start screen (a GPU-memory consumer), not a journey run.",
    "URI Assist vision: application path only; real capture adapters not implemented (owner-gated); product keeps vision_qualified False.",
    "Automated input; physical keyboard, mouse and microphone not qualified.",
    "Office reports a15/o8 PASS on the 64K main-only profile (Office evidence, not part of this record)."]
r["corrections"] = [
    {"id": "C-1", "was": "report v1: 'conversation is kept by URI' across switches", "now": "withdrawn; verified at worker level only after the CONTEXT-1 repair (sw4/sw5)", "source": "RPI-R1 R1-01"},
    {"id": "C-2", "was": "report v1: '17 new tests' for fa0a70e6", "now": "15 (now 22 after 4d782ef1/07dca2a8)", "source": "RPI-R1 R1-05"},
    {"id": "C-3", "was": "URI-RUNTIME-VRAM-R1 report: 64K+MTP demotion 'stays after close'", "now": "measured only 38 s after Chrome closed; does not show process-lifetime stickiness (DEMOTE-P1 returned after 180-210 s)", "source": "demotion research subagent"},
    {"id": "C-4", "was": "report v2 E0: 'free commit 386-1,600 MiB with 6-8 GB physical available'", "now": "see e0_host_memory (soak-p3: commit free min 386 at t=0, median well above 1,600; physical 3.6-7.0 GB)", "source": "RPI-R2 R2-01"},
    {"id": "C-5", "was": "report v2: soak/Assist evidence 'on 4d782ef1', 'host code identical'", "now": "those runs ran from the mutable dev checkout without a recorded binding: supporting only; bound re-runs soak-p3-e / assist-p3-e on the current commit", "source": "RPI-R2 R2-02"},
    {"id": "C-6", "was": "ProfileFollower change detection by (mtime, size), on_change outside the lock", "now": "content comparison, same-bytes validation, ordered delivery under the lock (07dca2a8)", "source": "RPI-R2 R2-05/R2-06"},
    {"id": "C-7", "was": "report/record v3: P2 'PASS / qualified on this commit' without a bound 60-minute soak", "now": "P2 qualified only after the bound soak-p2-e PASS (v3.1)", "source": "RPI-R3 R3-01"},
    {"id": "C-8", "was": "report v3.1: 'Fit after the run FITS +1,885 MiB' for soak-p2-e", "now": "that fit was taken at host start; at the end of the run only the residency verdict FITS is recorded", "source": "RPI-R4 R4-02"},
    {"id": "C-9", "was": "binding.py after R3-03: any docs/ path outside the receipt may differ from the runtime's commit", "now": "explicit allowlist (profiles_live evidence, the plan, the lifecycle config); soak-p2-e's changed paths satisfy both rules", "source": "RPI-R4 R4-01"}]
r["independent_audit"]["prior_rounds"] = [
    {"round": "RPI-R1", "nonce": "RPI-R1-7f3c91", "reviewed_commit": "3b77aabc", "verdict": "ACCEPT WITH FINDINGS",
     "findings": 9, "outcome": "all 9 resolved (verified in RPI-R2)"},
    {"round": "RPI-R2", "nonce": "RPI-R2-c41e88", "reviewed_commit": "a5605ae8", "verdict": "ACCEPT WITH FINDINGS",
     "findings": 9, "outcome": "R2-05/06 code fix 07dca2a8; R2-02 binding + bound re-runs on f3d5eb29; R2-01/03/04/08/09 "
                               "record/report fixes; R2-07 DEFERRED to the UI thread (see remaining_limitations)"}]
r["independent_audit"]["prior_rounds"].append(
    {"round": "RPI-R3", "nonce": "RPI-R3-9d27b4", "reviewed_commit": "fec31dfd", "verdict": "ACCEPT WITH FINDINGS",
     "findings": 5, "outcome": "R3-01 bound soak-p2-e; R3-02 LQ-4 deviation annotated; R3-03 binding checks the commit "
                               "and hashes the harness at run time; R3-04 environment.core; R3-05 plan amendment A2 "
                               "and lifecycle config baseline/focus"})
r["independent_audit"]["next_round"] = "RPI-R4 on the commit that carries this record"
fails = [k for k, v in lq.items() if isinstance(v, dict) and any(str(x).startswith("FAIL") for x in v.values())]
r["status"] = "FAIL"
r["status_reason"] = ("The record covers three profiles. P2 and P3: every mandatory journey PASS on the bound current commit "
                      f"{code[:8]}, switch continuity PASS (sw5), P3 Assist PASS, bound 60-minute soaks soak-p2-e and soak-p3-e per LQ-3. P1: failed journeys "
                      "(p1b-main CRASH-1, soak-p1 demotion) on earlier code and no re-run -> P1 unqualified, which makes the "
                      f"record as a whole FAIL; failed and superseded runs are listed, not excluded. Criteria with FAIL entries: {fails}.")
REC.write_text(json.dumps(r, indent=1, default=str), encoding="utf-8")
print(r["status"], fails, json.dumps(e0))
