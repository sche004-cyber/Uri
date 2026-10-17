# RUNTIME-PROFILES-INTEG — live Windows qualification results (report to the owner before any default change)

Date 2026-10-17. Candidate `milestone/runtime-profiles-integ-20261017`. Code tested live: `fa0a70e6`. Baseline
canonical `25048709`. Plan and criteria: `../RUNTIME_PROFILES_INTEGRATION_PLAN.md`. Record (authoritative, JSON):
`UI_QUALIFICATION_RUNTIME_PROFILES.json`, **status FAIL** (one P1 journey failed; see below).

URI's default Brain configuration is unchanged: the frozen Runtime v1, used whenever no profile is selected.
Nothing is integrated, deployed or frozen. Independent review is BLOCKED: Codex is over its usage limit until
2026-10-22 14:03, and the claude_cli login is expired. This is a code-and-live result, not an operational
qualification of any default.

## 1. What ran

- The real URI Windows app (UI V2 production `main()` via `integration_test`), driven by the canonical UI V2 driver
  (`docs/ui_v2/postint/evidence/harness/uiv2_driver.dart`, unchanged), with the real Core, worker and Brain.
  - Runtime: materialized from the candidate in `D:\uri-dev\uri-profiles-live\runtime-b`; installation `rp-b`,
    port 18337.
  - Brain: started by the production `scripts/ws_brain_host.py --profile`, port 18470, GPU lease, no override.
  - The harness copy in `evidence/harness/` changes only paths, the `--profile` option and the selection file.
- Profiles, all with MTP off (MTP stays an optional speed profile):
  - P1: 64K + GPU vision, request 14,764 MiB;
  - P2: 64K main only, request 13,658 MiB;
  - P3: 32K + GPU vision, request 14,360 MiB.
- Desktop: dwm 903-1006 MiB, ChatGPT, Claude, Edge WebView. Free for one process about 14,982 MiB.

## 2. Integration finding fixed during the live run (beyond the accepted scope; needs its own review)

The first P1 run (`p1-main`, code `84ef1a39`) showed the app reporting the Brain as `FOREIGN_INSTANCE`, detail
`ARGV_MISMATCH`. The product worker always verified the Brain against the frozen argv, so the accepted host-side
code alone cannot serve the app. That check is correct as a safeguard.

Repair `fa0a70e6`:
- New module `uri_operational_intelligence/runtime_profile_selection.py`, plus 6 lines in
  `scripts/run_uri_integrated_worker.py`.
- The worker reads `control/oi/brain_profile.json` once, before its file guard, and verifies the Brain against the
  same derived config.
- Only a measured profile derived from the frozen config is accepted. Absent or invalid file means the frozen config,
  and the reason is recorded in `worker-instance.json`.
- 17 new tests. Gates: `tests/oi`, `tests/ws`, `tests/assist`, `tests/web` and the worker isolation test give
  failure sets identical to canonical (25 pre-existing Chromium-dependent Assist failures/errors on this host).

The five accepted files are still byte-identical to `7c7a7776`.

## 3. UI V2 journeys (first-time = 68 driver checks, returning = 12)

| Profile | First-time | Returning | Brain at start (fit, calibration) |
|---|---|---|---|
| P1 64K + GPU vision | `p1c-main` 68/68, `s4-p1-main` 68/68; **`p1b-main` FAIL 52/57 (CRASH-1)** | `p1c-ret` 12/12, `s2-p1-ret` 12/12 (after a switch from P2) | AT_RISK +218 MiB, 102-104 tok/s |
| P2 64K main only | `p2-main` 68/68, `s1-p2-main` 68/68 | `s5-p2-ret` 12/12 (after a switch from P1) | FITS +1,324 MiB, 101-105 tok/s |
| P3 32K + GPU vision | `p3-main` 68/68 | `p3-ret` 12/12 | FITS +622 MiB, 103-105 tok/s |

Not counted:
- `p1-main`: superseded (code before the worker repair).
- `p2-ret`, `s3-p2-ret`: harness ordering artifact. A returning run that directly follows another returning run fails
  `R-companion-persisted` / `R-theme-persisted`, because the previous run ends with `R-restore-defaults`. Every
  other check passed, and the clean re-run `s5-p2-ret` passed 12/12.

Profile switch and context preservation:
- P2 first-time -> P1 returning, and P1 first-time -> P2 returning, both passed 12/12, including
  `R-conversation`.
- The switch is a host and app restart. The conversation is kept by URI; the KV cache is rebuilt.

## 4. Sustained operation (60 min each, URI app window + Chrome 6 tabs for minutes 20-40, a URI decision turn every 30 s)

| Soak | Turns OK / valid JSON | Decode median / min | Brain residency |
|---|---|---|---|
| `soak-p2` (P2) | 120 / 120 | 99.3 / 96.2 tok/s | never demoted (non-local 562 MiB throughout) |
| `soak-p1` (P1) | 120 / 120 | 99.2 / **20.5** tok/s | **demoted**: at minute 31 (11 min after Chrome opened) one 1 GiB block left VRAM (dedicated 14,985 -> 13,963, non-local 562 -> 1,584). Decode was 21 tok/s for about 12 min. The host raised its residency alert. The block came back about 3.5 min after Chrome closed. |

## 5. URI Assist (vision priority)

- Real-UI Assist: the Assist view opens (driver check `J2-ctrl-assist`, screenshot `j2-assist`). Assist cannot
  capture anything yet: no browser channel, UI Automation or screen-capture adapter exists (Assist owner checklist
  items 8-10), and the product worker keeps `vision_qualified=False` (item 7). **A real-UI Assist vision journey is
  BLOCKED by unbuilt, owner-gated components, not by the runtime.**
- Application path (checklist item 7) on the real Brain host, with the production `AssistCommands`, the test capture
  adapter and `vision_qualified=True` in the harness only (`evidence/assist/*`):
  - P1: 3/3 correct (error 401 and both toggles), cold ask 1.34 s, cached 0.5 s, decode 104 -> 103 tok/s;
  - P3: 3/3 correct, cold 1.37 s, decode 105 -> 103 tok/s.

## 6. Findings

- **CRASH-1 (open).**
  - What happened: llama-server b11425 exited with 0xC0000409 (fail-fast, no log message) in `p1b-main`, right
    after a cancelled 4-token task at 36 ms/token, when the next request was selected.
  - Rate: 1 crash in 8 P1-type Brain sessions; 0 in 9 P2/P3 sessions.
  - A 150-cycle cancel-then-request lab reproduction on P1 did not crash.
  - The frozen configuration's rate on the same pattern was not measured here.
  - The production host does not log at debug level, so the triggering request is unknown.
  - Next: a P1 soak with server debug logging in the lab, and the same journey sequence on the frozen config when it
    fits.
- **DEMOTE-P1 (open).** P1 leaves only about 200-300 MiB of real headroom next to the URI app on this desktop. An
  ordinary browser session pushed one 1 GiB block out after 11 min. This is the same mechanism found in the
  research (64K + MTP). P1 is therefore not a safe always-on profile on a 16 GB card during multitasking.
- **HARNESS-ORDER-1 (harness, not product).** Consecutive returning runs share and reset the preference fixture.
- **WORKER-PROFILE-1 (repaired in fa0a70e6, review pending).** Described in section 2.

## 7. Recommendation (no default change proposed yet)

| Owner item | Evidence-based answer |
|---|---|
| 7. 64K + GPU vision as the preferred future startup profile "when resources permit" | Functionally good: 4 of 5 journey runs and Assist 3/3. **Not yet reliable as a startup profile.** Its margin next to the app is AT_RISK, a browser demoted it in the soak, and CRASH-1 occurred on it once. Use it only when the lease fit says FITS. It needs CRASH-1 resolved, and the host's residency alert must become an actionable "restart Brain" prompt, before it can be preferred. |
| 8. 64K main only as fallback | **Strongest result:** 2 x 68/68 + 12/12, the switch test passed, a clean 60 min soak, FITS +1,324 MiB, accuracy parity with the frozen baseline (research). This is the candidate if the owner later decides to change the default. |
| 9. 32K + vision as the reduced-memory Assist alternative | 68/68 + 12/12, Assist 3/3, FITS +622 MiB. Not soaked yet (gap). This is the better Vision choice than P1 on this card. |
| 10. MTP optional with a VRAM warning | Kept optional; it was not used in these live runs. Research: 64K + MTP demotes next to Chrome; 32K + MTP coexisted once. |

Suggested next steps for the owner:
1. Make one reviewer available (`claude login`, or wait for Codex on 2026-10-22). Then the driver review round of
   candidate `fa0a70e6` plus this record's evidence commit can run.
2. Decide whether worker profile selection (`fa0a70e6`, beyond the accepted scope) may be part of the integration.
3. Approve a P3 soak, and a CRASH-1 investigation with debug logging.
4. Only after that, decide on a default.
