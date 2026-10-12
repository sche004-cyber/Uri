# URI Phase 2 UI/operations independent review, round 3

Date: 2026-10-07. Subject: `phase2ops-candidate-20261007-r2.zip`, HEAD `e8e3b65` plus uncommitted files. I treated all implementer records and orchestrator logs as claims. I changed no repository source, tests, documents, configuration, login or account state. My synthetic probe state is confined to `uri-agent/work/c1/reviewer_ops_round3_*`. I did not run pytest or Flutter.

## A. Integrity and Phase 1 frozen boundary

I independently hashed the candidate to `05127e2fe87ef869e83eeddcdcae47cc3eb804dd5bce791b34860b966b1cbead`, matching `ROUND3_SUBJECT.txt` and the sidecar. The archive has 157 members: 154 manifest entries (111 tree, 43 evidence) and three metadata entries. Every manifest hash matches its ZIP member **and** its corresponding live tree/evidence file. Earlier archives still hash to round-2 subject `bffa742ac9f8b4e6aadebde8bb91aa6c22638be6b4feeca6a5cfb7a0a1aa8ec7`, original ops subject `ce935c4be0e29c67d0d34772c9584e8ce3ac836e118e490ad167d8447d13d9d8`, and Phase 2D r2 `cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d`.

The Phase 1 checkpoint at the path in `tests/phase2a/test_frozen_core.py:11` hashes to `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`; I compared all **121** checkpoint tree members byte for byte and found no mismatch. `uri_ui/lib/app.dart` is outside that checkpoint and is listed as an allowed new Tasks mount at `test_frozen_core.py:22-29`. The candidate is uncommitted and is not a milestone release.

## B. Earlier findings and repair attacks

| Finding | Round-3 disposition | Independent basis |
|---|---|---|
| OPS-1 | **Partly repaired; still open through OPS-1R.** A fact-free completed row becomes uncertain, but a duplicate row can take the no-task branch and borrow a genuine server reply. | Direct status/list probe below; `execution.py:132-180`. |
| OPS-2 | **Partly repaired; still open through OPS-2R.** Invalid top-level shapes become `RECORD_SCHEMA`; nested proposal/evidence types remain unchecked and can break Dart history/status decoding. | Direct Python shape probe and Dart parser source below. |
| OPS-3 | **Repaired on source inspection.** The approval card renders the arguments object as JSON with its digest before the approve action. | `supervised_execution_screen.dart:356-369`; worker digest checks at `execution.py:374-390`. No physical click. |
| OPS-1R | **Still open by task omission.** Matching an execution ID in a ledger row works when the displayed record retains `task_id`; the same record can claim no task and be accepted as a local completion against a harness reply. | Direct `ExecutionController.status()` and `list()` probe: both returned `completed`, empty gaps for a record with `kind=client_external_harness`, `task_id=None`, and a server reply carrying a non-null harness `operation_id`. |
| OPS-2R | **Still open end to end.** `_well_typed` handles top-level field types, including the round-2 `queued_at` and `proposal` examples. It does not validate fields inside proposal or evidence needed by Dart. | Direct Python probe: nested malformed shapes passed register and status/list; Dart casts at `supervised_runtime.dart:49-64,169-176,239-249` are incompatible with them. |

**Binding and trust.** `ExecutionController._run` sets `runner.dispatch_context={"execution_id": eid}` at `execution.py:435-437`; `SupervisedTurnRunner._run_harness` passes it to `bridge.execute(work, context=...)` at `runner.py:51-68`; the bridge writes `context.get("execution_id")` into task `request_json` at `bridge.py:230-248`. I read an actual COMPLETE task in the preserved `work/c1/p2ops_ui_2e56280a2fb74cd4a8904e1e894f89d4/c/control/supervisor/ledger.db` with SQLite immutable/read-only mode: its request's `execution_id=fc3a8286650749e19e9c30a5b34a361d` matches exactly that record's ID and its `task_id` points back to the task. I did not mutate that ledger. Direct synthetic corroboration rejects a copied record with another ID (`LEDGER_EXECUTION_MISMATCH`) and a changed record session (`LEDGER_REQUEST_MISMATCH,SERVER_SESSION_MISMATCH`).

`context` is an optional, caller-supplied observation label, **not authority**. An older bridge caller may omit it, producing a null ledger ID; a caller able to supply the bridge's context may forge it. Ticket validation, server claim, supervisor admission and settlement remain the execution authority. The ID check helps detect a damaged register row against an unchanged supervisor ledger. It is not cryptographic attestation: a process able to rewrite both local record and ledger can make them agree. My synthetic `corroborate()` probe with both facts changed returned `completed`; that is the local-state trust limit, not a demonstrated Core execution bypass. The supervisor schema's task identity trigger prevented an ordinary SQL UPDATE in a copied production ledger, but a same-user replacement/corruption of local state is outside this display check.

**Corroboration policy.** With a task, `corroborate` requires ledger COMPLETE; matching request turn, operation, session, selection and digests; matching execution ID; journal `verified`; `SETTLED_VERIFIED`; and, when the server answers, server `reply` with the exact task operation and record session (`execution.py:143-168,176-180`). An unreachable server is tolerated for a harness completion if ledger and journal agree. With no task, it requires an available `reply` server and matching session/proposal session, but it does **not** require local kind or an absent server operation (`:169-175`). I reproduced a forged no-task harness record with a server reply that named an actual harness operation: both `status()` and `list()` reported `completed` with no gap. This is a phantom display receipt, not another execution. `status()` and `list()` now both call corroboration and consult the server for completed rows (`:334-359`), so their policy is aligned.

**Register shapes.** `_well_typed` validates top-level state, IDs, text, timestamps, proposal/restart-ledger containers, evidence container and cancel flag (`execution.py:183-209`). Direct-import probes showed `queued_at:[1]` and `proposal:[1]` become `RECORD_SCHEMA` stubs; listing, status and restart did not raise. Nested `proposal.provider:[1]`, `proposal.session_id:{...}`, `evidence:[[1]]`, and `restart_ledger.request:[1]` pass `get()`; Python listing/status/restart completed without an exception in my probe. Cancel reads only top-level state/ID and close reads top-level state, so I found no nested-shape Python exception there. The Dart status parser requires `proposal_digest as String` and proposal strings and maps every evidence member `as Map`; its listing parser requires provider/model `as String?` (`supervised_runtime.dart:49-64,169-176,239-249`). A damaged valid-JSON record with `proposal.provider:[1]` yields a list-valued provider from `ExecutionController.list()` (`execution.py:355-358`), which will throw at the Dart cast; a list evidence member or missing/non-string proposal digest similarly breaks status. I source-traced the Dart failure because Flutter cannot run here. Nested `restart_ledger` is not dereferenced by these paths, so I found no crash from its nested values.

## C. Defects and post-repair validation

| ID | Severity | File:line | Failure and evidence | Reproduced? |
|---|---|---|---|---|
| OPS-1R | Medium, blocks | `uri_supervisor_bridge/execution.py:143-175` | Dropping `task_id` from a duplicate harness record selects the local branch; a real harness `reply` with a non-null operation is enough to display `completed` under a second ID. | **Yes**, direct-import status and list with synthetic record/server facts under `work/c1`. |
| OPS-2R | Medium, blocks | `uri_supervisor_bridge/execution.py:190-209,355-358`; `uri_ui/lib/services/supervised_runtime.dart:49-64,169-176,239-249` | Nested valid-JSON proposal/evidence shapes pass the register; the worker relays them and Dart's typed casts can throw, hiding history or status. | **Python path reproduced**; Dart cast failure source-traced, not Flutter-run. |
| OPS-4 | High, blocks; introduced by round-2 API change | `uri_supervisor_bridge/runner.py:65`; `scripts/phase2d_composition_qualification.py:104-109` | Runner now calls `bridge.execute(work, context=...)`, but the Phase 2D `CompositionStack` wrapper still defines `execute(work)`. The post-repair native Codex lifecycle stopped after dispatch with `EXCEPTION:TypeError`, no supervisor task or result. | **Source-traced**; exact-candidate orchestrator JSON read, not independently rerun. |
| OPS-5 | Low/Medium, newly found; malformed ledger | `uri_supervisor_bridge/execution.py:91-97` | A valid JSON array in ledger `request_json` raises uncaught `AttributeError` at `req.get`, so completed status/list can fail rather than report an unreadable ledger. | **Yes**, direct `ledger_view` probe on synthetic SQLite under `work/c1`; not observed in a production ledger. |
| VAL-1 | Validation blocker; cause unresolved | `uri_ui/test/supervised_runtime_live_test.dart:14-23,54-85` | The exact-candidate live Dart bridge run exited 1: a lifecycle timed out at `uncertain EXCEPTION:SERVER_REFUSED:HTTP_403`. A later record in the preserved state was COMPLETE, but the scripted lifecycle/cancel/reconnect gate did not pass. | **Log and records read only**; no independent Flutter run or established code root cause. |

OPS-4 is a concrete repair regression: the new bridge call broke an existing programmatic composition seam. OPS-5 is newly discovered in the repaired candidate but predates the added context parameter; I do not attribute its origin to this repair. VAL-1 is a failed validation result, not a proven source defect.

The archived logs are not my test runs. `phase2ops_r2/phase2_all.log` invokes isolated pytest on `tests/phase2a` through `phase2ops` and reports **411 passed, 2 live opt-in skipped**. `phase1_authority.log` invokes the eight authority files and reports **134 passed**. `phase1_full.log` reports **2675 passed, 12 skipped, 11 failed, 88 subtests passed**; its eleven failure IDs match the prior round's Drive step3/4, privacy, M20 feasibility/recovery/semantic resilience, session facts, usage newline and workflow restart IDs. `flutter_all.log` ends **191 passed, 2 skipped**. Separately, `ui_bridge_live.json` reports **exit 1** with the HTTP 403 timeout above; `codex_cli_lifecycle_211838.json` reports a successful direct CLI probe and persisted qualification, but the lifecycle ends `uncertain/EXCEPTION:TypeError`, and its mid-run cancellation never starts. Those failed post-repair gates cannot be replaced by the unit-suite counts.

## D. UI wiring, remaining work and ledger claims

| UI question | Determination | Basis |
|---|---|---|
| (a) Worker protocol | **YES** | Four execution frames in worker service and supervised worker dispatcher, source inspected; the isolated suite reports coverage. |
| (b) Programmatic composition | **PARTIAL this candidate** | Source composition exists and the archived live run completed one record, but the required live Dart run exited 1 and the native composition wrapper is incompatible with `context=`. |
| (c) Opt-in profiles | **YES** | Manifest-backed supervised entry and explicit per-installation opt-in; no fixture flag from the production UI path. |
| (d) Real Flutter UI driving worker | **PARTIAL** | Real Tasks mount, screen/runtime and widget tests; no human click, and the exact-candidate live bridge run failed. |
| (e) Cutover | **NO** | C7 authorization, pinned UI build, migration and launcher gates remain open. |

USER-PHYSICAL / NOT VERIFIED: a human approval/cancel/reopen in a running Flutter app; native CLI login and execution inside the actual isolated client-profile worker process; and the controlled 200+ hard power-loss campaign. Chat `/ask` integration and a pinned UI release remain separate C6/C7 decisions. Context Capsule and Task Compiler are **design only, later undated work**, not the next mandatory Phase 2 slice (`docs/architecture/PHASE2C_TASK_COMPILER_PLACEMENT.md:1-26`). No accepted 2E/2F numbering was found.

The researched/deferred Strata and Paperclip, researched AG-UI/A2UI, designed MCP broker and separate model-residency prototype are not delivered harness features; URI Memory in Core is not a harness context capsule. Supervisor scheduling/recovery and the Phase 2D chain have test evidence, not physical power-loss qualification. The report's corrected claim that register history is type-safe and status-truth complete is overstated by OPS-1R/OPS-2R. Its blanket “execution lifecycle, mid-run cancel, reconnect, UI wiring IMPLEMENTED / TESTED” status is also overstated for this exact candidate because the two post-repair live validations failed. Earlier passing logs belong to earlier candidates.

## E. Verdict

The frozen boundary and archive integrity are intact. The round-2 binding works for a task-bearing genuine record, but a no-task duplicate still borrows a harness reply. Nested valid JSON can break UI decoding, the new bridge signature breaks the native composition wrapper, and the exact-candidate live bridge validation failed. This slice is not independently acceptable.

## NOT VERIFIED

- Independent pytest or Flutter suite results; I read orchestrator commands, counts, failure IDs and JSON, and ran only direct-import/SQLite/integrity probes.
- A live human Flutter approval, cancel and reopen; native login and execution inside the client profile; physical power-loss durability.
- Root cause of the live Dart HTTP 403; exhaustive cancel timing, Windows descendant kill and Phase 2D launch-chain races.
- Chat migration, pinned UI release, historical migration and production cutover.

## FINAL VERDICT

**UI/OPERATIONS SLICE REJECTED**
