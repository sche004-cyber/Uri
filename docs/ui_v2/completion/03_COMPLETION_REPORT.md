# URI UI V2 completion — report

Short version: UI V2 now opens in the real app, works end to end with the real Core and Brain on this PC, and is
lighter on the GPU than the earlier screen. Five integration defects were found and fixed; three blockers turned out
to be environment or governance issues that are now gone. Independent review and canonical integration are recorded
in the lifecycle receipt; integration still needs the owner's approval.

Code commit tested live: `d4a48317` (see the record for the full SHA) (branch `milestone/ui-v2-completion-20261015`,
canonical base `85f6a0ec`). Live record: [UI_QUALIFICATION_UI_V2.json](UI_QUALIFICATION_UI_V2.json) (authoritative).

## A. Existing URI preserved

- All 35 rows of the earlier screen inventory stay (see [inventory A–E](02_INVENTORY_A_TO_E.md)). Nothing removed or
  disabled.
- The earlier living screen stays one switch away (`URI_UI_VISUAL=living`); the classic interface entry is still in
  Settings (live J13); unpaired installations still open the classic app.
- Companions, shaders, orbit, single/double click, detached chat, voice states, gallery, theme independence: kept.
- No frozen file changed. After the canonical merge the strict frozen check passes (`ok: true`).
- No new dependency.

## B. Cosmetic and usability changes (small, local)

| ID | Change | Evidence |
|---|---|---|
| V-2 | Medium Dashboard layout when the content area is at least 900×640 and below the tall layout (live: windows 1366×768, 1280×800, 1024×768): six destinations beside a smaller companion, composer kept in view, rail from 1100 px. Smaller content areas (live: 900×640 and 800×600 windows, 601 and 561 px high) keep the scrolling column by design | before `evidence/visual/before/dashboard-1024x768.png`, after `evidence/visual/after/dashboard-1024x768.png`, `dashboard-1366x768.png`, `dashboard-1536x864.png`; live J11 |
| V-1 | "Nothing to review" / "1 review needed" / "N reviews needed"; "1 pending decision" | live J9 screenshot |
| V-3 | Detached chat fades earlier messages under its header (no thin cut bubble) | before/after `companion-detached-chat.png` |
| V-4 | One-line hover hints on Dashboard navigation (Companion: click for Chat, double-click to return) | widget tests |
| — | V2 status lines use the same Brain startup headline as the rest of the app | merge commit |

## C. Integration blockers

| ID | Cause | Result |
|---|---|---|
| BLK-ENV-1 GetFinalPathNameByHandleW access denied | Environment of the 2026-10-13 session | Not reproducible today, in a normal shell and in the Codex restricted-token sandbox; no repair needed, no check weakened |
| BLK-GOV-1 strict frozen check failed | Inherited canonical condition (approved security repairs) | Resolved by canonical 85f6a0ec (FCV-R governance); passes on this candidate |
| BLK-REV-1 two Codex CLIs on PATH | Environment | One CLI; probes pass |
| BLK-NAT-1 no native interaction evidence | Old automation could not click the window | Native runs of the production app pass (synthesized input) |
| BLK-INT-1 V2 not reachable from the real app | Unfinished integration | Fixed; live J1 |
| BLK-INT-2 "Start new work" made simulated items | V2 defect | Fixed; live J6 |
| BLK-INT-3 Dashboard said "0 review needed" while approval waited | V2 defect | Fixed; live J9 |
| LV-2 Ctrl+1..4 / Escape dead after sending a message | Focus fell above the shell (found live) | Fixed; live J2/J7/J9/J11 |
| LV-1 14 framework errors on opening Settings | Voice status changed during build (found live) | Fixed |
| DEP-FCVR-1 conflicts with FCV-R | Two pending candidates | FCV-R reached canonical first; merged and resolved here |
| R1-01 Connections showed made-up accounts (Codex) | Classic account screens on the integrated path's placeholder client | Plain 'not managed here yet' page with Open Settings / classic interface; live R2 |
| R1-02 size claim (Codex) | Report overstated the medium layout range | Corrected; J11 now checks the composer where medium applies |
| R1-03 native regions unchecked (Codex) | Doubles cast to int without checks | Malformed boxes rejected with INVALID_LAYOUT, region kept; live J7 |
| R1-04 ready colour (Codex, LOW) | Plain label compared with raw code | Compares the raw code |

Full list with evidence: [blocker register](01_BLOCKER_REGISTER.json).

## D. Functional verification (real Windows app)

Production `main()` of the candidate, real integrated worker, paired Core and Runtime v1 Brain under the GPU lease
(no override). Input synthesized by the test framework. First-time run (with onboarding) and returning run.

J1 start · J2 navigation · J3 real conversation · J4 clarification and confirmation · J5 remember_fact tool with
approval and recall · J6 Documents start work · J7 Companion window 440×680, shaped region, chat, Escape, double click
back · J8 gallery and theme · J9 approval count, review, deny · J10 navigation while the Brain works · J11 five window
sizes · J12 Brain stopped: plain message and recovery options · J13 classic entry · R1 returning user: all **PASS**.

Not verified: physical mouse/keyboard and window drag, microphone/speaker, other DPI and a second monitor.

## E. Performance (same commit, same view, same prompt ×5, alternating runs)

| | Earlier living screen | UI V2 |
|---|---|---|
| Brain speed (median tokens/s) | 148.8 | 149.8 |
| UI GPU memory (median) | 308 MiB | 208 MiB |
| UI CPU (one core, harness forces continuous frames) | 62 % | 62 % |
| UI RAM | 342 MiB | 345 MiB |
| Frame time p95 (idle Companion) | 4.3 ms | 3.4 ms |

Data: `evidence/perf_summary.json`, `evidence/live/p5-living`, `evidence/live/p6-v2` (measured at 56dbc003; the later repairs touch no rendering path: a new page, native argument checks and one colour condition). Earlier rounds p1–p4 agree.

## F. Regression

Full Flutter suite after the round 1 repairs: 636 passed, 5 skipped (the same five opt-in live suites). Python
ssrf/web/a2ui/ws suites: driver gates (receipt). Earlier accepted workflows (conversation, clarification,
approval, memory, recall, Brain-unavailable handling) pass live.

## G. Independent review

Codex (`gpt-6-sol`) through the lifecycle driver. Round 1 (state `lifecycle/r1`, commit 0263e61b): REJECT with R1-01..R1-04; the
driver's repair worker failed three times, so the coordinator repaired them (d4a48317). The revision run
`UI-V2-COMPLETION-r2` (state `lifecycle/r2`) reviews the whole candidate again from round 1; its verdict is in that
receipt, not in this report.

## H. Integration status

Not integrated. After a driver-counted independent ACCEPT the run stops at "ready for owner approval"
(`integration.authorized: false`). Canonical integration needs the owner's approval; production deployment is not
part of this milestone.

## I. Deferred (owned elsewhere or owner choice)

- MINOR: transient one-frame overflows while the window shrinks into Companion; conversation header overflow when a
  draft and the Brain-unavailable banner stack (UX-D1).
- MINOR: Lunar renderer's faint 1 px square edge on light themes (companion renderer milestone, UX-D2).
- MINOR: composer shows testing affordances (simulated transcript, dictation) to every user (owner choice, UX-D3).
- MINOR: an open Text Intelligence draft takes Companion-chat messages as edits without showing the draft there
  (UX-D4).
- Core: one-shot "Remember that …" sometimes refused as `INTENT_UNGROUNDED_VALUE` (OUT-CORE-3).
- Owner: visual-reference similarity (BLK-VIS-1); Ember into UI V2 next; URI Office stays with the Office thread.
