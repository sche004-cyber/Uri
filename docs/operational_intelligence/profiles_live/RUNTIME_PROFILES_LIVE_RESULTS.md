# RUNTIME-PROFILES-INTEG — live qualification results (v3.1, bound to code f3d5eb29)

Date 2026-10-18. Candidate `milestone/runtime-profiles-integ-20261017`. Code tested live: `f3d5eb29`, which is
`07dca2a8` (the profile code) merged with canonical `348677b7`. Plan and criteria:
`../RUNTIME_PROFILES_INTEGRATION_PLAN.md` (amendment A1 covers the scope beyond the accepted files). Authoritative
record: `UI_QUALIFICATION_RUNTIME_PROFILES.json`. Its status is **FAIL as a whole**, because P1 has mandatory
failures. P2 and P3 are qualified on this commit (section 2).

URI's default Brain is unchanged: the frozen Runtime v1 is used whenever no profile is selected. Nothing is
integrated, deployed or frozen. Independent review is by fresh read-only subagents (lifecycle tier 3, owner decision
2026-10-17). It is not driver-verified (section 8).

## 1. What changed since v2 of this report (4d782ef1)

- **Source binding (review R2-02).** Every harness (`live_session.py`, `soak.py`, `assist_vision_app.py`,
  `switch_live.py`) now refuses to run without a clean source binding (`evidence/harness/binding.py`). The binding
  requires a clean candidate worktree and a byte match of all 358 runtime files in both the runtime and the
  candidate checkout. After review R3-03 it also requires that the runtime was materialized from the candidate HEAD,
  or from an earlier commit that differs from HEAD only in this milestone's evidence, plan and lifecycle config
  (an explicit allowlist since review R4-01; none of these files is in the runtime). No qualification run
  used the allowlist version: `soak-p2-e` ran with the R3-03 version, and its changed paths satisfy both rules. The
  integration run `sw6` used the allowlist version (review R8-01). The
  record's `binding_versions` lists the version each run recorded (review R5-03). It records the
  hashes of the harness scripts at run time. Limits: the binding is taken once, at the start of a run, and it does
  not cover base or overlay files outside the receipt (none of them changes in this milestone). The record counts a
  run for a commit only when its binding names that commit. The soak and Assist runs of v2 ran from the mutable development checkout without a recorded
  binding. They are now **supporting evidence only** (correction C-5). Bound re-runs replace them.
- **ProfileFollower (R2-05, R2-06), code `07dca2a8`.** Change detection now compares the file content, not
  `(mtime, size)`. The same bytes are validated and applied, and `on_change` runs in order under the lock. There are
  22 tests in `tests/oi/test_runtime_profile_selection.py` (correction C-6).
- **Canonical revalidation.** Canonical `348677b7` was merged (`f3d5eb29`). The gates `tests/oi`, `tests/ws`, SSRF,
  `tests/web`, `tests/a2ui`, `tests/assist` and the worker isolation test give the same failure set on the candidate
  and on canonical: 5 failed and 20 errors, all pre-existing and Chromium-dependent Assist tests. The candidate has
  6,845 passed tests and canonical has 6,812; the 33 extra tests are the new profile tests.
- **E0 corrected (R2-01).** The v2 text "free commit 386-1,600 MiB" was wrong. See section 6 and the record's
  `e0_host_memory` (correction C-4).
- **Record (R2-03, R2-04, R2-08, R2-09).** The record keeps each profile's results on earlier commits under
  `history_on_earlier_commits`. Interpretations are labelled as such in `annotations`. Every correction is listed in
  `corrections` (C-1 to C-6 at v3; C-1 to C-9 now).

## 2. Qualification by profile

| Profile | Status | Bound evidence on `f3d5eb29` | Operating condition measured |
|---|---|---|---|
| **P2 64K main only** (13,658 MiB) | **PASS** | `e-p2-main` 68/68, `e-p2-ret` 12/12, switch `sw5` PASS, soak `soak-p2-e` 60 min PASS (added after review R3-01) | lease fit FITS +1,920 MiB (2026-10-18); +1,176..+1,324 on 2026-10-17 |
| **P3 32K + GPU vision** (14,360 MiB) | **PASS** | `e-p3-main` 68/68, `e-p3-ret` 12/12, switch `sw5` PASS, Assist application path `assist-p3-e` 3/3, soak `soak-p3-e` 60 min PASS | fit FITS +1,218 (2026-10-18) .. AT_RISK +474 (2026-10-17 evening, dwm 1.05 GB) |
| **P1 64K + GPU vision** (14,764 MiB) | **FAIL — unqualified** | not re-run. History on `fa0a70e6`: `p1b-main` FAIL (CRASH-1), `soak-p1` FAIL (demotion 99 -> 21 tok/s for 12 min); also 2 x 68/68, 2 x 12/12, Assist 3/3 (unbound) | fit AT_RISK +218; stays unqualified until CRASH-1 and DEMOTE-P1 are resolved and re-tested |

Supporting (unbound) evidence: `c-p2-*` and `c-p3-*` on `4d782ef1`, `soak-p2` and `soak-p3` (60 min each, clean),
`assist-p3`, `sw4`. Not part of this record: the Office session reports a15/o8 PASS (13/13, 34/34) on the 64K
main-only profile.

## 3. Journeys

The record lists every journey run: 21 in total, 4 of them on the current commit. Failures are listed, never
dropped. The ordering-artifact rule (R1-03) applies only when all of these hold: the only failures are
`R-companion-persisted` and `R-theme-persisted`; the observed values equal the defaults written by
`R-restore-defaults`; and the run immediately before was a returning run. The rule marks a run NOT VERIFIED, not
PASS (`p2-ret`, `s3-p2-ret`).

## 4. Sustained operation (P2, P3) and Assist (P3), bound

- **`soak-p2-e`** (60 min, the app's start screen open, Chrome opened at 20 min and closed at 40 min): 120/120 turns valid. Decode
  median 104.0 tok/s, minimum 87.8 tok/s. Brain non-local memory at most 561.8 MiB, which is the same Vulkan host
  buffers as in the P2 journey runs, so there was no demotion. Dedicated memory at least 13,876.1 MiB. Free commit
  21,352-24,809 MiB. Fit FITS +1,885 MiB at host start; at the end of the run the residency verdict was FITS
  (correction C-8, review R4-02). The lease was FREE after the run. Review R3-01 found that v3
  reported P2 as qualified without a bound soak; this run closes that gap.

- **`soak-p3-e`** (60 min, the app's start screen open, Chrome opened at 20 min): 120/120 turns valid. Decode median
  103.8 tok/s, minimum 90.2 tok/s. Brain non-local memory at most 497.8 MiB, which is the Vulkan host buffers only, so
  there was no demotion. Dedicated memory at least 14,579.6 MiB. The host did not exit early. The lease was FREE after
  the run.
- **`assist-p3-e`** (application path, 3 asks): every answer named error 401 and both enabled toggles. Ask time 1.34
  s cold, then 0.52 s and 0.47 s. Plain decode 106.7 tok/s before and 105.0 tok/s after. Host ready in 23.0 s.

Each profile has one bound soak (n=1), on a lighter desktop than on 2026-10-17. With the unbound `soak-p2` and
`soak-p3` (2026-10-17), each profile has two clean 60-minute runs.

## 5. Profile switch with conversation continuity (LQ-4)

Worker-level test (`tools/switch_live.py`). It uses the real integrated server, the production Brain host, and the
real worker spawned exactly as the app spawns it, driven with the app's commands. One worker process carries one
conversation through P2 -> P3 -> P2.

| Run | Result |
|---|---|
| `sw1` | NOT VERIFIED: the recall prompts routed to Core memory, not to the conversation |
| `sw2` | supporting, not PASS: harness bug (`TURN_IN_PROGRESS`, next turn sent too early) |
| `sw3` | supporting, automated FAIL kept. Interpretation (not verified) in the record's `annotations` |
| `sw4` | supporting PASS (unbound, `4d782ef1`) |
| **`sw5`** | **PASS, bound to `f3d5eb29`**: "4817" recalled through the answer channel before the switch, after P2 -> P3 and after P3 -> P2. Both switches reached READY on the new profile (26.8 s and 21.2 s). The worker pid did not change |

Not tested: a switch through UI clicks. The UI V2 driver does not test it.

Deviation from the plan (review R3-02, plan amendment A2): LQ-4 names the switch P2 -> P1 -> P2. The run used
P2 -> P3 -> P2, because P1 is unqualified and P3 is the qualified vision profile. Cold start is covered by every
bound journey and soak run, each of which starts the Brain host cold. Host restart is covered by each `sw5` switch,
which stops the host and starts it again on the new profile. VRAM release is measured in `sw5`. A P2 -> P1 -> P2
switch stays open together with P1.

## 6. Research (subagents; hypotheses are labelled)

- **CRASH-1** (`evidence/research/CRASH1_RESEARCH.md`; the crashed server log and the reproduction script are in
  `evidence/crash1/`).
  - Leading hypothesis, not verified: host commit exhaustion leads to an uncaught `std::bad_alloc` in the
    prompt-cache save (an unprotected copy; upstream PR #27451 is still open). That leads to `std::terminate` /
    `abort` and 0xC0000409. There is no Windows log, because the terminate handler prints only on Linux/macOS.
  - The reading "the cancel came after the task had finished" is inferred from the log order and the b11510 source.
  - **E0, measured** (record `e0_host_memory`): in `soak-p3` (2026-10-17), free system commit was 386 MiB minimum
    (at t=0), median 2,500 MiB, maximum 5,107 MiB, with 3.6-7.0 GB of physical memory available. In `soak-p3-e`
    (2026-10-18), free commit was 20,841-24,491 MiB. The RAM-1 snapshot shows PowerShell processes of other sessions
    at about 4 GB private each. Commit, not physical memory, was the scarce resource on 2026-10-17. This risk applies
    to every profile and to the frozen configuration.
  - Reproduction E1 was not run.
- **DEMOTE-P1** (`evidence/research/DEMOTION_RESEARCH.md`).
  - What moved: a 1,021.7 MiB allocation, identified by size match as the first of 13 weight allocations. The
    tensor-to-allocation map was not dumped. It happened at a Chrome memory burst. The allocation returned 180-210 s
    after Chrome closed.
  - Estimated margin needed with an ordinary browser: about +450-500 MiB fit. P1 at +218 is not sufficient. P3 at
    +474..+1,218 is near or above the boundary, and its soaks passed.
  - Proposed recovery policy: detect (residency alert plus a decode drop); offer a lighter profile; restart only when
    the fit is FITS. Any automatic restart is opt-in, idle-only and rate-limited.

## 7. Remaining defects and unverified scenarios

- CRASH-1 is open (root cause unverified; E1 not run). It can affect any profile under commit pressure.
- DEMOTE-P1 is open. Its mitigations (vision on CPU at 64K, 256 MiB suballocation) are unmeasured.
- P2 and P3 sustained operation: one bound soak each (n=1) on a light desktop; P3 is near the estimated margin on
  heavy desktops.
- **R2-07 deferred to the UI thread.** The UI does not render `backend.profile` yet. The API exposes it with
  `qualified: false`. UI presentation is outside this milestone (owner brief: the runtime owns the capability, not
  its presentation). The Brain Quick Controls milestone (owner-approved 2026-10-18, branch
  `milestone/brain-quick-controls-20261018`, base `f3d5eb29`) is the UI thread.
- URI Assist vision is verified only through the application path. No real capture adapter exists (owner-gated Assist
  checklist items 8-10). The product keeps `vision_qualified=False`.
- Automated input only. The soak UI window is the app's start screen, not a journey run. Physical keyboard, mouse and
  microphone are not qualified.

## 8. Independent review and integration readiness

- RPI-R1 (nonce `RPI-R1-7f3c91`, commit `3b77aabc`): ACCEPT WITH FINDINGS, 9 findings, all resolved (verified in
  RPI-R2).
- RPI-R2 (nonce `RPI-R2-c41e88`, commit `a5605ae8`): ACCEPT WITH FINDINGS, 9 findings. R2-05/06 fixed in code
  (`07dca2a8`). R2-02 fixed by the binding and the bound re-runs. R2-01/03/04/08/09 fixed in the record and this
  report. R2-07 deferred (section 7).
- RPI-R3 (nonce `RPI-R3-9d27b4`, commit `fec31dfd`): ACCEPT WITH FINDINGS, 5 findings.
  - R3-01 MEDIUM: P2 was reported qualified without a bound soak. Fixed: `soak-p2-e` was run (section 4).
  - R3-02: the LQ-4 deviation was not stated. Fixed (section 5, plan A2).
  - R3-03: the binding was described too strongly. Fixed: the binding now also checks the commit and hashes the
    harness scripts, and its limits are stated (section 1).
  - R3-04: `environment.core` cited the wrong materialization. Fixed.
  - R3-05: the plan and lifecycle config named the old baseline and review focus. Fixed (plan A2, config).
- RPI-R4 (nonce `RPI-R4-5e81a0`, commit `900e9962`): ACCEPT WITH FINDINGS, 4 LOW findings, fixed in the next
  commit except R4-03, which was completed after RPI-R5 (R5-02): R4-01 binding allowlist (correction C-9); R4-02 fit wording (C-8); R4-03 plan A2 and review focus;
  R4-04 the record's status reason names both bound soaks, and correction C-7 records the v3 P2 overclaim.
- RPI-R5 (nonce `RPI-R5-b3f6d2`, commit `47b41df2`): ACCEPT WITH FINDINGS, 3 LOW bookkeeping findings, fixed
  in the next commit: R5-01 the record's audit history; R5-02 the remaining lifecycle review-focus wording
  (completes R4-03); R5-03 which binding version each bound run used.
- RPI-R6 (nonce `RPI-R6-71c4e9`, commit `42cc4e2d`): ACCEPT WITH FINDINGS, one LOW (the corrections range in
  section 1) and one INFO (the committed binding hash), both fixed.
- RPI-R7 (nonce `RPI-R7-2a9f50`, commit `b5007afc`): ACCEPT WITH FINDINGS, two INFO wording findings (the record's
  status-reason tail and this section's R4 line), both fixed in the next commit. No LOW or higher finding is open.
  The INFO wording fixes were not re-reviewed.
- **Driver-verified acceptance: not available.** Codex is over its usage limit until 2026-10-22, and the claude CLI is
  logged out. Subagent acceptance under the 2026-10-17 lifecycle policy is a different verification class and is
  reported as such.
- Integration into canonical needs your explicit authorisation. A change of the default Brain needs a separate
  authorisation.

## 9. Integration (owner decisions D1-D5, 2026-10-18)

- **What is integrated:** P2 and P3 on the qualified code `f3d5eb29`, plus one change after qualification, the D3
  guard in `c3fc8bbc`. `runtime_profile_selection.SELECTABLE` makes the worker follow only the frozen Runtime v1,
  P2 and P3. Any other measured combination, P1 included, is refused with `PROFILE_NOT_QUALIFIED` and keeps the
  frozen config; `write()` refuses it too. The Brain host's `--profile` keeps every measured combination for
  research; a worker never verifies against such a host (FOREIGN_INSTANCE, fail closed). Plan amendment A3.
- **Default Brain unchanged (D2):** with no selection file, the worker and the host use the frozen config exactly as
  before. Nothing in this candidate's product code writes the selection file. After Brain Quick Controls is
  integrated, its Brain host writes it, but only with a catalog profile (frozen, P2, P3); the worker still refuses
  any other key on every read (review R8-03).
- **Live verification on the integration code:** `sw6`, bound to `c3fc8bbc` (runtime-f, installation rp-f), PASS.
  "4817" was recalled before the switch, after P2 -> P3 and after P3 -> P2. Switches were READY in 25.2 s and 23.3 s,
  VRAM was released in 3.4 s, and the worker pid did not change. The P2/P3 journeys and soaks were not repeated: the
  guard does not change their derive path or argv (unit tests).
- **Regression gates** (`evidence/gates_integ`): tests/ws, oi, ssrf, web, a2ui, assist, the office worker isolation
  test, governance and dev_workflow, run with one interpreter on the candidate and on canonical `348677b7`. The
  failure sets are identical: 6 failed and 20 errors, all pre-existing (Chromium-dependent Assist tests and
  `test_win_breakaway_is_refused`). Candidate 7,255 passed, canonical 7,209.
- **Brain Quick Controls compatibility (D4):** `c3fc8bbc` merged into the Brain QC tip `29db21f9` in a scratch
  worktree without conflict; `tests/oi/test_brain_quick_controls.py` plus the profile tests gave 75 passed and 1
  skipped. Repeated on the newer Brain QC tip `f7c08dbc`, merged with `91f2b0bd`: no conflict, 78 passed and 1
  skipped. Brain QC's own catalog lists the same three profiles and refuses P1 on the host side.
- **P1 (D3):** stays unqualified and not selectable. A read-only investigation
  (`evidence/research/P1_D3_INVESTIGATION.md`) found nothing that makes CRASH-1 specific to P1. The leading
  hypothesis, still unverified, is host commit exhaustion. The pagefile is system-managed on an HDD and grows on
  demand, and "virtual memory minimum too low" warnings occurred on 2026-09-17 and 2026-10-15. Mitigations that need
  you (fixed pagefile, crash dumps) and the decisive experiment E1' (commit starvation on P2) are not done.
- **Rollback:** a revert commit on canonical (non-destructive), or, with your authorisation, a force reset to
  `348677b7`. At run time, removing the selection file returns the worker to the frozen fallback (review R8-05).
- **API label (R8-04, R2-07):** `brain_health.backend().profile.qualified` is `false` for every profile, P2 and P3
  included. The value is hard-coded in the accepted `runtime_profiles.describe()` and is left unchanged; showing
  qualification in the UI belongs to Brain Quick Controls, whose catalog marks P2 and P3 qualified.
