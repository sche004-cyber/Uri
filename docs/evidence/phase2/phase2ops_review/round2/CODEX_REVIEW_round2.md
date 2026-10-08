# URI Phase 2 UI/operations independent review, round 2

Date: 2026-10-07. Candidate: `phase2ops-candidate-20261007-r1.zip`; live tree HEAD `e8e3b65`, uncommitted. I treated the repair report and orchestrator logs as claims. I changed no repository source, test, document or configuration. My synthetic probe and its state are under `uri-agent/work/c1/reviewer_ops_round2/`.

## A. Integrity and Phase 1 boundary

I computed the candidate SHA-256 as `bffa742ac9f8b4e6aadebde8bb91aa6c22638be6b4feeca6a5cfb7a0a1aa8ec7`, matching `ROUND2_SUBJECT.txt` and the sidecar. All **142** manifest digests match both ZIP members and the corresponding live tree/evidence files; the ZIP has three additional metadata members. Earlier candidate hashes are unchanged: Phase 2 ops round 1 `ce935c4be0e29c67d0d34772c9584e8ce3ac836e118e490ad167d8447d13d9d8`; Phase 2D r2 `cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d`. The Phase 1 checkpoint hashes to `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7` and all **121** checkpoint tree files are byte-identical. `uri_ui/lib/app.dart` is outside the checkpoint and is explicitly included in `ALLOWED_NEW` at `tests/phase2a/test_frozen_core.py:23-28`; this is a legitimate entry for the Tasks mount. This remains an uncommitted candidate, not a milestone release.

## B. OPS-1, OPS-2 and OPS-3 disposition

| ID | Disposition | Independent evidence |
|---|---|---|
| OPS-1 | **Partially repaired; still open.** The original fact-free `completed` record now becomes `uncertain`, and `status()` and `list()` call `corroborate`. A completed harness task can still be borrowed by another durable record if its turn and proposal fields are copied; the second `execution_id` is never tied to the task. A changed record-level `session_id` is also ignored when proposal and ledger agree. | Direct call to `corroborate()` with COMPLETE ledger, verified journal and reply server: genuine record, distinct `execution_id`, and wrong record-level `session_id` each returned `completed` with empty gaps. Source: `execution.py:148-160,297-321`. This is a false *record/receipt display*, not a route to execution authority. |
| OPS-2 | **Partially repaired; still open.** Missing/wrong `execution_id`, non-string state and non-object JSON now become `RECORD_SCHEMA` stubs. Other valid-JSON field shapes can still abort list and restart. | Direct register probe: `queued_at: [1]` raises `TypeError` in `list()` and `reconcile_restart()`; after removing that record, `proposal: [1]` raises `AttributeError` in controller `list()`. Source: `execution.py:201-225,233-237,318-321`. |
| OPS-3 | **Repaired on source inspection.** The card shows the complete arguments map as indented JSON plus the argument digest before the enabled button. The worker recomputes and checks both approval and proposal digests. | `execution.py:53-66,344-353`; `supervised_runtime.dart:49-64`; `supervised_execution_screen.dart:356-369,214-223`. Widget test was read in the candidate, not independently run. A physical Flutter click remains unverified. |

**Corroboration detail.** A harness record with a task requires ledger COMPLETE, request turn/operation/selection/digests, journal `verified`, and `SETTLED_VERIFIED`; an answering server that reports another state or another non-null operation is a gap (`execution.py:132-172`). A local record without a task requires server `reply`, compatible session and that code. Direct probes showed wrong server operation becomes `uncertain`, while an unreachable server leaves a harness completion `completed`; the latter is the documented offline policy and does not itself establish server settlement. A local unreachable server becomes `uncertain` by source inspection. `status()` returns `recorded_state`, a `corroboration` block and the live fact views. `list()` returns `recorded_state` but omits the corroboration block and does not consult the server for harness rows, so its `completed` is less informative than status. The direct probe also showed a reply with a *missing* server operation ID is accepted. Whether that omission is expected from the server contract was not independently established here; it is not counted separately as a defect.

The duplicate-record case is narrower than arbitrary task substitution: a different selection is rejected (`LEDGER_REQUEST_MISMATCH`), while copying all known fields from a genuine execution can produce an additional completed record. No second execution occurs, but the history can show a phantom success. The current regression test explicitly expects that faithful copy to remain `completed` (`tests/phase2ops/test_reconnect.py:144-150`). The record-level session mismatch is an additional inconsistency in what the displayed record claims.

## C. New defects and remaining failure scenarios

| ID | Severity | File:line | Failure scenario | Evidence / reproduced? | Blocks verdict? |
|---|---|---|---|---|---|
| OPS-1R | Medium | `uri_supervisor_bridge/execution.py:148-160,297-321` | A second valid-schema record borrows another execution's genuinely COMPLETE task, verified journal and reply turn, copies the proposal, but has a different execution ID or record-level session. It is displayed as completed. | **Reproduced** by direct `corroborate()` probe with synthetic fact views; matching behavior also encoded in `test_reconnect.py:149-150`. Real ledger process not rerun. | **Yes** |
| OPS-2R | Medium | `uri_supervisor_bridge/execution.py:201-225,233-237,318-321` | A valid JSON record with a truthy nonnumeric `queued_at` crashes register listing and startup reconciliation. A truthy non-map `proposal` crashes controller listing. One damaged history row can hide all histories or prevent worker startup. | **Reproduced** with direct register/controller probes on files under `work/c1/reviewer_ops_round2/state`. | **Yes** |

No additional execution-authority bypass was found in this focused review. `begin()` still checks the pending turn and both digests before launching its worker thread (`execution.py:337-368`). The defects above concern truth of the displayed history and recovery availability.

## D. UI wiring, remaining work and evidence provenance

| Question | Round-2 determination | Evidence |
|---|---|---|
| (a) Worker protocol | **YES** | Existing worker service and frame handling; unchanged from round 1. |
| (b) Programmatic composition | **YES, orchestrator-tested; partly source/direct-probed here** | `ui_bridge_live.json` records the Dart runtime driving real worker/server processes with a fixture, cancellation and reconnect. I read that log; I did not run the process test. |
| (c) Opt-in profiles | **YES** | Manifest-backed entry and worker profile path; no production cutover. |
| (d) Real Flutter UI driving worker | **PARTIAL** | Real Tasks mount at `uri_ui/lib/app.dart:344-349`, screen and widget tests, but no human click on a running Flutter app. OPS-1R/OPS-2R still impair displayed history. |
| (e) Cutover | **NO** | `docs/plans/C7_CUTOVER_REQUIREMENTS.md:3-18` says gates and owner authorization are outstanding. |

I read the exact-candidate orchestrator command and outcomes in `phase2ops_r1/phase2_all_final.log`: isolated Phase 2 pytest scope, **411 passed, 2 opt-in live skips**. `phase1_authority.log` says **134 passed**. `phase1_full.log` says **2675 passed, 12 skipped, 11 failed, 88 subtests passed**; the failure IDs are the same eleven listed in round 1 (Drive step3/4, privacy, M20 feasibility/recovery/semantic resilience, session facts, usage newline, workflow restart). This is an ID comparison, not my rerun. `flutter_all.log` ends at **191 passed, 2 skipped**. `ui_bridge_live.json` reports fixture lifecycle, cancellation and reconnect through real processes. `codex_cli_lifecycle_195130.json` reports native Codex execution and cancellation with **programmatic** approval under run-scoped shell authentication, not a human UI click. I independently ran only the Python direct-import probe and integrity checks; I did not run pytest or Flutter in this sandbox.

USER-PHYSICAL / NOT VERIFIED: human approval/cancel/reopen in a running Flutter app; native login and execution inside the actual client-profile worker process; controlled 200+ physical power-loss campaign. C6 Chat integration, a pinned UI release, historical migration and C7 cutover gates remain. Context Capsule and Task Compiler remain **design only, later undated work**, not the next mandatory Phase 2 slice (`docs/architecture/PHASE2C_TASK_COMPILER_PLACEMENT.md`). The research ledger's researched/deferred Strata and Paperclip, researched AG-UI/A2UI, designed MCP broker, separate model-residency prototype and existing Core memory are not delivered harness features. The repaired report's broad “reconnect register IMPLEMENTED / TESTED” claim is overstated while OPS-2R persists; “status truth” is overstated while OPS-1R persists. Process-test and native claims in the logs are evidence of those runs, not independent acceptance or physical durability qualification.

## E. Verdict

The archive and frozen boundary are intact, and the approval card now shows the bound arguments. Two remaining history/reconnect defects prevent accepting this UI/operations slice. Phase 2 also has deferred user qualification and cutover work, so it cannot be called complete or ready to freeze.

## NOT VERIFIED

- Independent pytest or Flutter suite execution, and a human running the Flutter approval path.
- Native login/execution from the real client-profile worker and controlled physical power loss.
- Exhaustive cancellation interleavings, Windows descendant containment and Phase 2D launch-chain races.
- Production Chat migration, pinned UI release, historical data migration or owner-authorized cutover.

## FINAL VERDICT

**UI/OPERATIONS SLICE REJECTED**
