# BRAIN-QC-CLOSURE-20261018 — runtime profiles post-integration closure and Quick Controls

Branch `milestone/brain-qc-closure-20261018`, worktree `D:\uri-dev\uri-brain-qc-closure`.
- **Built on:** canonical `feaabe3f` (runtime profiles `cd4a7963` + Brain Quick Controls, integrated by the coordinating
  session), merged as `fcc1f183`.
- **Code under test:** `fcc1f183`. Live runs, gates and the runtime receipt all name this commit.
- **Not done:** nothing is pushed, integrated, frozen or deployed. The default Brain stays the frozen Runtime v1.

## 1. Acceptance criteria (owner closure task, D1-D6)

| # | Criterion | Result |
|---|---|---|
| C1 | Frozen fallback works; default unchanged | MET (live: Standard = frozen at start and end of `qcc-1`; config digest unchanged; no product code changes the default) |
| C2 | P2 and P3 work through the Windows UI | MET (live `qcc-1`: Context 64K -> P2; Draft Off -> P3; recall and decode on both) |
| C3 | P1 not selectable through normal controls | MET (catalog refuses it; worker `SELECTABLE` refuses it; the UI lists it disabled with its reason; live check `QC-unqualified-not-requested`) |
| C4 | UI qualification and active-profile information accurate; host, worker and selection never disagree silently | MET (`active` only after worker verification; new `mismatch` with the host's `selection_error`, shown as a `qc-mismatch` line; live `QC-no-mismatch-p3`; unit and widget tests for each mismatch kind) |
| C5 | Conversation and worker survive switching | MET (live: "4817" recalled after 4 switches; the same 2 worker processes and the same session) |
| C6 | Vision stays available during an active Assist session | MET in code and tests. Live: a vision answer on P3 by the production Assist classes in the session process, not through the worker (L-2) |
| C7 | Loading, switching, readiness and failure states truthful | MET (live: the header is never "ready" while a switch is pending; a turn during a switch is refused; P3 is shown only when it is READY) |
| C8 | No new material regression | MET (gates; UI V2 journeys 68/68; resource numbers in section 5) |
| C9 | Independent review: no unresolved blocking issue | see section 7 |
| C10 | Canonical unchanged until approved | MET (this branch is not pushed) |

## 2. What was implemented (code)

- **P3 through the UI (D2/D6).** The catalog entry `standard-nodraft` (P3, 32K + GPU vision, no MTP) is now switchable,
  as "Standard, draft off".
  - A new **Draft** chip (On = Standard (frozen, MTP), Off = P3) appears only where two qualified profiles differ in
    the draft alone, which today means only at 32K + vision.
  - Vision and Context still prefer Standard.
  - This replaces the earlier coordinator rule "never offer P3" (owner closure decision). It also resolves QC-F8.
- **Disagreement made visible (D3, QC-F9, R9-01 follow-up).** `controls.mismatch` reports these cases:
  - host profile ≠ worker config (`HOST_WORKER_PROFILE_MISMATCH`);
  - a research host profile that is not selectable (`PROFILE_NOT_SELECTABLE`, from the host's `selection_error`);
  - a failed selection write (`HOST_SELECTION_ERROR`);
  - an unreadable host profile.

  It is suppressed only during a switch that the chip already shows. The UI states it in words. The worker remains
  the fail-closed authority (`runtime_profile_selection.SELECTABLE`, unchanged).
- **Assist keeps vision (D2/D6).**
  - While URI Assist holds a grant (ACTIVE or PAUSED), a switch that turns vision off is refused (`ASSIST_NEEDS_VISION`) and shown disabled.
  - A running Assist answer blocks any reload (`ASSIST_ASK_IN_PROGRESS`).
  - `assist_ask` and `assist_grant` wait (`BRAIN_RESTARTING`) while a profile switch runs.
- **R9-02:** the runtime-profiles lifecycle review focus now names the `c3fc8bbc` / sw6 integration verification.
- **R9-01:** already fixed by Brain QC (`4c61a0b3`, integrated in `feaabe3f`). The host writes a selection only for a
  SELECTABLE profile. This closure re-verified it (QCC-R1) and added the UI visibility above.
- **Not changed:** `ws_brain_host.py` and the runtime files (no speculative runtime change, D6); P1 status; the
  default Brain.

Files changed against canonical `feaabe3f`:
- **Code:** `brain_quick_controls.py`, `worker_bridge.py`, `run_uri_integrated_worker.py`,
  `brain_quick_controls.dart`, `oi_conversation.dart` (+2 strings; frozen UI V2 file, additive only).
- **Tests:** `test_brain_quick_controls.py` and `brain_quick_controls_test.dart`.
- **Documents:** `RUNTIME-PROFILES-INTEG.json` (review focus) and this milestone's documents and evidence.

## 3. Tested (exact commit `fcc1f183`)

| Gate | Result | Evidence |
|---|---|---|
| pytest `tests/oi` + `tests/ws` | 793 passed, 23 skipped, rc 0 | `evidence/gates/closure_fcc1f183/pytest_oi_ws.log` |
| flutter test (full) | 788 passed (5 skipped), rc 0 | `…/flutter_test.log` |
| flutter analyze | 4 info messages (exit 1, as at the QC baseline), all pre-existing, in files this milestone did not touch | `…/flutter_analyze.log` |
| `ws_frozen_check` | ok, no unapproved drift; same as the QC baseline | `…/frozen_check.json` |
| Frozen UI V2 files vs `7893aaed` | +137 / -0 lines (additive) | `…/ui_v2_frozen_files_stat_vs_7893aaed.txt` |
| Windows release build | OK (`uri_ui.exe` Release built), rc 0 | `…/uibuild-release.log` |
| Worktree after the gates | clean (`porcelain_after.txt` empty) | |

Focused tests added by this closure:
- Python: P3 target, every mismatch kind, mismatch suppressed during a switch, the Assist guard (vision off refused,
  vision kept allowed, ask in progress), a real `AssistCommands` grant / pause / revoke, `switch_pending`, the
  dispatch guard (a source-order check only), and assist-state failure isolation.
- Dart: Draft choices (32K, P3, 64K, unknown), lockVision cases, mismatch and selection-error notices, a Draft switch
  through the confirm dialog, and the refusal texts.

## 4. Live Windows verification (`fcc1f183`, runtime6 verified byte for byte, production `main()`, real worker, Core and Brain host, lease, no override)

**`qcc-1`: QC journey plus closure steps. PASS, 32/32 checks; all 10 required closure checks present.**

| Step | Switch (UI s) | Decode tok/s (perf turn) | Recall "4817" |
|---|---|---|---|
| Standard (frozen) at start | - | 110.7 | - |
| -> Long context (P2), via Context 64K | 34.9 | 96.2 | yes |
| -> Standard, via Vision On | 54.2 | 148.9 | yes |
| -> Standard, draft off (P3), via Draft Off | 36.8 | 99.8 | yes |
| -> Standard, via Draft On | (host 39.2) | - | yes |

- **Thinking:** Off gave tier FAST and On gave NORMAL, with no reload.
- **P1:** listed but disabled, with its reason. It was never requested.
- **During a switch:** a turn sent during a switch was refused with BRAIN_RESTARTING.
- **States:** the header was never "ready" while a switch was pending.
- **Same processes:** the same two worker processes and the same session throughout.
- **After the run:** lease FREE; Brain config digest unchanged.
- **Assist vision on P3, after the UI switched to it (`QC-assist-vision-on-p3`):** the host reported
  `c32k-visgpu-mtpoff`. The production `AssistCommands` code (grant, observe, screenshot, VisionGate, loopback Brain)
  answered correctly in 1.54 s: error 401, Voice input and Gmail drafts on.
  - Stand-ins: the test capture adapter, and `vision_qualified=True` in a separate session-process instance. The
    worker's own Assist keeps vision unqualified (owner-gated).

**`qcc-uiv2`: canonical UI V2 journeys on the Standard Brain. 68/68 PASS, flutter exit 0, session COMPLETED.**
`summary.json` reads "INCOMPLETE" only because `summarize.py` is written for the QC driver: it expects
`ui-finished.json` to say `by: driver`, and the UI V2 driver does not write that key. The raw evidence
(`observations-main.json`, `native-execution.json`, `session.json`) is the record. The tool was not changed after the
run.

## 5. Resources (live `qcc-1`, measured)

| Profile | Request MiB | Fit before the switch | Dedicated max MiB | Non-local max MiB | Calibration tok/s |
|---|---|---|---|---|---|
| Standard (frozen, 32K + vision + MTP) | 15,626 | AT_RISK -321 / -328 (app open) | 15,008 | 1,731 (partly in system memory) | 146.7-150.5 |
| P2 Long context (64K, no vision) | 13,658 | FITS +1,665 | 13,896 | 562 (host buffers only) | 94.6 |
| P3 Standard, draft off (32K + vision) | 14,360 | FITS +943 | 14,589 | 500 (host buffers only) | 98.4 |

- **Host commit (D5, read-only sampling):** limit 52,148 MiB; free 17,803 to 39,659 MiB.
- **llama-server:** private bytes up to 20,430 MiB with a working set of only 3,651 MiB. This fits the investigation
  hypothesis that GPU allocations are charged to commit. The hypothesis is not verified; this is one observation.

## 6. Default-profile comparison (D2: evidence only, no change)

| | Standard (frozen) | P3 (draft off) | P2 |
|---|---|---|---|
| GPU headroom next to the app | negative (AT_RISK); about 1.7 GB in system memory | +0.9 GB, fully resident | +1.7 GB, fully resident |
| Decode, list task (measured turns) | 110.7 at the first turn, 148.9 after a switch (MTP); calibration 146.7-150.5 | 99.8; calibration 98.4 | 96.2; calibration 94.6 |
| Vision | yes | yes | no |
| Context | 32K | 32K | 64K |
| Qualification | frozen baseline | live-qualified (runtime profiles), subagent-reviewed, not driver-accepted; plus this closure | same as P3 |

- **Standard:** fastest. On this desktop it runs past the safe GPU budget, as known since Runtime v1 (P-GOV-1).
- **P3:** keeps vision, with headroom.
- **P2:** has the most headroom and context, but no vision.
- **Recommendation:** do not change the default yet. If you prefer reliability under desktop load over draft speed,
  P3 is the evidence-backed default candidate with vision. The decision needs your separate authorisation.

## 7. Independent review

- QCC-R1 (fresh read-only subagent, nonce `QCC-R1-8b2e47`, commit `cde75580`): REVISE, 1 MEDIUM + 6 LOW, all
  repaired in `18831515` (`review/closure/REVIEW_QCC_R1.md`).
  - The MEDIUM finding: the live closure steps could pass vacuously. The closure flag is now set, recorded and
    required by the summary.
- QCC-R2 reviews the final commit (code, gates, live evidence). Its result is recorded in section 9.
- Verification class: subagent review, not driver-verified. Codex is out of quota until 2026-10-22, and the claude
  CLI is logged out.

## 8. Remaining limitations

- **L-1:** switching was driven by automation (flutter_test taps); physical keyboard and mouse are not qualified.
- **L-2:** Assist vision through the worker is still unqualified (owner-gated capture adapters). The live Assist
  check ran the production Assist classes in the session process (not the worker path) with stand-ins. The worker's vision lock and switch guard are covered by unit and
  widget tests, not live.
- **L-3:** `qc-mismatch` is unit and widget tested only. Live, it would need a research P1 host; P1 was deliberately
  not started.
- **L-4:** Standard next to the app is AT_RISK, a pre-existing frozen-config property. Other open items carry over
  unchanged: QC-F1 (the choice is not persisted; a new host starts on Standard), QC-F2, QC-F3, QC-F5 to QC-F7, QC-F10.
- **L-5:** P1 is unqualified; CRASH-1 and DEMOTE-P1 are open. Starvation experiments are deferred (D5).
- **L-6:** the parallel task "UI Interactive Controls & Typography" will redesign these chips. The contract of this
  closure (Draft only where qualified, the vision lock, the mismatch line) was sent to it.

## 9. Review results

- **QCC-R2** (fresh read-only subagent, nonce `QCC-R2-d61f93`, commit `0988176d`): **ACCEPT WITH FINDINGS**, 4 LOW,
  no HIGH or MEDIUM (`review/closure/REVIEW_QCC_R2.md`). Every owner criterion was MET, and the numbers in sections
  4-6 were recomputed from the raw files. The repairs below are wording and evidence only; they were not re-reviewed:
  - R2-01: the live Assist check is described as the production Assist classes in the session process, not the
    worker path. The harness comments that still say "application path" (`qc_session.py`, `qc_driver.dart`) are kept
    unchanged, because the runs recorded the driver hash.
  - R2-02: decode now shows the measured range.
  - R2-03: the flutter analyze log is added. The dispatch guard is marked as a source-order test. `frozen_check.head`
    names the commit and the baseline file.
  - R2-04: the qualification class is stated. The host report's `profile.qualified: false` for P2 and P3 is the
    research flag of the accepted `runtime_profiles.describe()` (R2-07 / R8-04). The UI does not show it; the Quick
    Controls catalog is the qualification authority in the UI.
- **Status:** ACCEPT WITH FINDINGS by independent subagent review. This is not driver-verified, not integrated, not
  frozen and not deployed.
