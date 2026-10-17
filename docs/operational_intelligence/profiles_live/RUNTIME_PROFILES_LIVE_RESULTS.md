# RUNTIME-PROFILES-INTEG — live qualification results (v2, bound to code 4d782ef1)

Date 2026-10-17. Candidate `milestone/runtime-profiles-integ-20261017`. Code tested live: `4d782ef1`. Baseline
canonical `25048709`. Plan and criteria: `../RUNTIME_PROFILES_INTEGRATION_PLAN.md` (amendment A1 covers the scope
beyond the accepted files). Authoritative record: `UI_QUALIFICATION_RUNTIME_PROFILES.json`, status **FAIL as a
whole**, because P1 has mandatory failures. P2 and P3 are qualified on this commit (section 2).

URI's default Brain is unchanged: the frozen Runtime v1, used whenever no profile is selected. Nothing is
integrated, deployed or frozen. Independent review: fresh read-only subagent reviews (lifecycle tier 3, owner
decision 2026-10-17), not driver-verified (section 7).

## 1. What changed since v1 of this report (fa0a70e6)

- **CONTEXT-1 (found after review R1-01, repaired in `4d782ef1`).** Before the repair, the worker read the profile
  selection only at start, so a profile switch needed a worker restart and lost the in-memory conversation.
  `ProfileFollower` now re-reads the selection on change and swaps only the readiness verifier. The guard pins the
  frozen (superset) artifact set, and `brain_health` names the serving profile with `qualified: false` (R1-06).
  Tests: 19 in `tests/oi/test_runtime_profile_selection.py`. Gates `tests/oi`, `tests/ws`, `tests/assist`,
  `tests/web` and the worker isolation test give a failure set identical to canonical (25 pre-existing
  Chromium-dependent Assist failures/errors).
- The v1 report said "17 new tests"; the correct count for `fa0a70e6` was 15 (R1-05).
- The v1 claim "conversation is kept by URI" across switches was not evidenced. The driver's `R-conversation`
  check sends a new prompt only (R1-01). This is now verified at worker level (section 4).
- Research subagents investigated CRASH-1 and the P1 demotion (section 5). One correction to the URI-RUNTIME-VRAM-R1
  report: its 64K + MTP "stays slow after Chrome closed" was measured only 38 s after the close, so it does not show
  process-lifetime stickiness.
- `evidence/live/dry` was an empty folder created by an import check of the harness (no run). It was removed and is
  listed here (R1-04).

## 2. Qualification by profile

| Profile | Status | Evidence on `4d782ef1` | Operating condition measured |
|---|---|---|---|
| **P2 64K main only** (13,658 MiB) | **PASS** | `c-p2-main` 68/68, `c-p2-ret` 12/12; switch `sw4` PASS. Host-only evidence, with host code identical: `soak-p2` 60 min clean. History on `fa0a70e6`: 2 x 68/68, 12/12 | lease fit FITS +1,176..+1,324 MiB; dwm 0.8-1.06 GB; Chrome 6 tabs |
| **P3 32K + GPU vision** (14,360 MiB) | **PASS** | `c-p3-main` 68/68, `c-p3-ret` 12/12; `soak-p3` 60 min with the app + Chrome: 120/120, median 99.3 / min 94.3 tok/s, never demoted; switch `sw4` PASS; Assist application path 3/3 | fit AT_RISK +474 (19:00 desktop, dwm 1.05 GB) .. FITS +622; one soak |
| **P1 64K + GPU vision** (14,764 MiB) | **FAIL — unqualified** | history on `fa0a70e6`: `p1b-main` FAIL (CRASH-1), `soak-p1` FAIL (demotion 99 -> 21 tok/s for 12 min); also 2 x 68/68, 2 x 12/12, Assist 3/3. Not re-run on `4d782ef1` | fit AT_RISK +218; stays unqualified until CRASH-1 and DEMOTE-P1 are resolved and re-tested |

Also reported by the Office session, not part of this record: Office a15/o8 PASS (13/13, 34/34) on the 64K
main-only profile.

## 3. Journeys on the current commit

Every run is listed in the record: 17 journey runs, of which 13 are history on earlier commits and 4 are current.
Failures are listed, never dropped. The ordering-artifact rule (R1-03) now applies only when all of these hold: the
only failures are `R-companion-persisted` and `R-theme-persisted`; the observed values equal the defaults written by
`R-restore-defaults`; and the run immediately before was a returning run.

## 4. Profile switch with conversation continuity (LQ-4)

Worker-level test (`tools/switch_live.py`). It uses the real integrated server, the production Brain host and the
real worker spawned exactly as the app spawns it, driven with the app's commands. One worker process carried one
conversation through P2 -> P3 -> P2.

| Run | Result |
|---|---|
| `sw1` | NOT VERIFIED: my prompts routed to Core memory, not to the conversation |
| `sw2` | NOT VERIFIED: harness bug (`TURN_IN_PROGRESS`, next turn sent too early); the post-switch recalls were already correct |
| `sw3` | automated FAIL, kept. The prompt "plus 1 now" was ambiguous; the answers 4818 -> 4819 -> 4820 continued the conversation's own arithmetic, which shows the history was in context |
| **`sw4`** | **PASS**: "4817" through the answer channel before the switch, after P2 -> P3 and after P3 -> P2. Switches reached READY on the new profile in 26-33 s; VRAM released in 3.8-3.9 s; same worker pid |

## 5. Research (subagents; hypotheses are labelled)

- **CRASH-1** (`evidence/research/CRASH1_RESEARCH.md`, crashed server log and reproduction script in
  `evidence/crash1/`).
  - Leading hypothesis, not verified: host commit exhaustion leads to an uncaught `std::bad_alloc` in the
    prompt-cache save (an unprotected copy, upstream PR #27451, still open), which leads to `std::terminate` /
    `abort` and 0xC0000409. There is no Windows log, because the terminate handler prints only on Linux/macOS.
  - Task 841 was not a grammar request; its "cancel" came after it had already finished.
  - **E0 measured in soak-p3:** free system commit was 386-1,600 MiB while 6-8 GB of physical RAM was available.
    Two PowerShell processes of other sessions held about 4.2 GB private each (RAM-1). This risk applies to every
    profile and to the frozen configuration.
- **DEMOTE-P1** (`evidence/research/DEMOTION_RESEARCH.md`).
  - What moved: a 1,021.7 MiB weight allocation (the first of 13 weight allocations), not the KV cache or the
    projector. It happened at a Chrome memory burst, and the allocation returned 180-210 s after Chrome closed.
  - Estimated margin needed with an ordinary browser: about +450-500 MiB fit. P1 at +218 is insufficient; P3 at
    +474..+622 is near the boundary, but its soak passed.
  - Recovery policy proposed: detect (residency alert plus a decode drop); offer a lighter profile; restart only when
    the fit is FITS; any automatic restart is opt-in, idle-only and rate-limited.

## 6. Remaining defects and unverified scenarios

- CRASH-1 open (root cause unverified; reproduction E1 not run); it can affect any profile under commit pressure.
- DEMOTE-P1 open. Its mitigations (vision on CPU at 64K, 256 MiB suballocation) are unmeasured.
- P3 qualification rests on one soak near the estimated margin boundary.
- URI Assist vision is verified only through the application path (no real capture adapter; owner-gated Assist
  checklist items 8-10). The product keeps `vision_qualified=False`.
- Automated input only; the soak UI window is the app's start screen; there are no Thinking/Vision/Context controls.

## 7. Independent review and integration readiness

- Round RPI-R1 (fresh read-only subagent, nonce `RPI-R1-7f3c91`, commit `3b77aabc`): ACCEPT WITH FINDINGS, 9
  findings. Repairs:
  - R1-01: CONTEXT-1 repair plus the worker-level test;
  - R1-02: CRASH-1 log and reproduction committed;
  - R1-03: classifier;
  - R1-04: `dry` folder disclosed;
  - R1-05: test count;
  - R1-06: health profile;
  - R1-07: documented;
  - R1-08: `worker-instance.json` preserved for runs on the current commit;
  - R1-09: plan amendment A1.
- The next subagent round reviews this exact head.
- **Driver-verified acceptance: not yet.** Codex is over its usage limit until 2026-10-22 and the claude CLI is
  logged out. Subagent acceptance under the 2026-10-17 lifecycle policy is a different verification class and is
  reported as such.
- Integration into canonical needs your explicit authorisation. A default change needs a separate authorisation.
