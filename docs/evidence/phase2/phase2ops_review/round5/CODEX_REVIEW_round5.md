# URI Phase 2 UI/operations independent review, round 5

Date: 2026-10-07. Subject: `phase2ops-candidate-20261007-r4.zip` and the matching live tree at HEAD `e8e3b65259c45fc823addc3ef8969425a265bd1b` plus uncommitted work. Implementer reports and orchestrator logs are claims, not my test results. I changed no repository source, test, document, configuration, account, or login state. My probe state is confined to `uri-agent/work/c1/reviewer_ops_round5_*`; this report is under `evidence/phase2ops_review/round5/`. Pytest and Flutter could not run in this sandbox.

## A. Integrity and Phase 1 frozen boundary

I independently hashed the round-5 subject ZIP: SHA-256 `fc9c96ec2b5b44a70f8486dccd9d0aa2b2eb28dafa01f9ac6f6e1594e251ed58`, matching `ROUND5_SUBJECT.txt` and the sidecar. It has 208 members: 205 manifest entries (113 tree, 92 evidence) and three metadata entries. Every manifest digest matches its ZIP member, and every member matches the corresponding live tree or evidence file: **zero mismatches**. Earlier archives remain unchanged: ops r3 `fdfb78edf9621ee8828d6a4a10c5a466fa3116f22e8c82cfea100a2e05937b64`, r2 `05127e2fe87ef869e83eeddcdcae47cc3eb804dd5bce791b34860b966b1cbead`, r1 `bffa742ac9f8b4e6aadebde8bb91aa6c22638be6b4feeca6a5cfb7a0a1aa8ec7`, original `ce935c4be0e29c67d0d34772c9584e8ce3ac836e118e490ad167d8447d13d9d8`, and Phase 2D r2 `cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d`.

The Phase 1 checkpoint SHA-256 is `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`. All **121** non-metadata checkpoint files are byte-identical in the current tree. `uri_ui/lib/app.dart` is outside the checkpoint and is an allowed Tasks mount (`tests/phase2a/test_frozen_core.py:22-29`). This remains uncommitted candidate work, not a released or frozen milestone.

## B. Earlier findings and repair attacks

### Disposition table

| Earlier finding | Round-5 disposition | Independent basis |
|---|---|---|
| OPS-1 | **Repaired within the local-state trust boundary.** A recorded completion is corroborated on status and list, including local executions. | `uri_supervisor_bridge/execution.py:137-206,423-449`; direct status/list probe: genuine-shaped local completed, duplicate uncertain. |
| OPS-2 | **Repaired for the reported crash.** Invalid record schema becomes an uncertain stub; ordinary malformed nested fields tested below are rejected. | `execution.py:216-261,315-352`; direct `_well_typed` probes. |
| OPS-3 | **Repaired on source inspection.** Approval card shows exact arguments JSON and digest before its approve button. Human interaction remains unverified. | `uri_ui/lib/screens/tasks/supervised_execution_screen.dart:331-370`. |
| OPS-1R | **Repaired within the local-state trust boundary.** An operation is create-once claimed for one execution; a second local record borrowing its operation is uncertain in status **and** list. Harness requests additionally bind the ledger execution ID. | `execution.py:152-200,278-313,423-449,528-534`; direct controller probe; preserved native ledger/index. |
| OPS-2R | **Repaired for the demonstrated nested-shape failure.** Wrong provider, evidence hash, or evidence byte type fails `_well_typed`; Dart readers and the card use checked `is` guards for those values. I found no remaining throwing read in the inspected status/list/card path. | `execution.py:235-260`; `supervised_runtime.dart:26-33,58-74,167-193,225-255`; `supervised_execution_screen.dart:274-434`; Python probes and source inspection, not Flutter execution. |
| OPS-4 | **Repaired on source and archived native path.** Both known `execute(work)` composition wrappers forward `**kw`; native Phase 2D lifecycle/cancel completed as claimed. Phase 2C wrapper was not itself rerun. | `scripts/phase2c_native_qualification.py:172-174`, `scripts/phase2d_composition_qualification.py:106-108`, `uri_supervisor_bridge/runner.py:65`; repository search and native artifacts. |
| OPS-5 | **Repaired.** Non-object or unreadable ledger `request_json` returns `REQUEST_UNREADABLE`, rather than raising at `.get`. | `execution.py:91-100`; direct source review; round-4 synthetic SQLite probe was not repeated. |
| VAL-1 | **Open validation observation.** Ten current bridge runs passed and `refusals.txt` is empty, but the earlier exact-candidate HTTP 403 still has no diagnosed cause. The new diagnostic itself has LOG-1 below. | Ten `phase2ops_r4/ui_bridge_live_*.json` and stdout files read; round-3 failed run; `scripts/run_uri_phase2_server.py:56-80,116-120`. |

### Ownership and trust

`SupervisedTurnRunner._validate_ticket` first verifies the signed ticket, then calls `on_starting(operation_id)` (`uri_supervisor_bridge/runner.py:42-49`). The controller's hook calls `claim_operation` before the frozen runner reaches dispatch and before the bridge's `execute(work, context=...)` (`execution.py:528-534`; `runner.py:51-65`). The index uses exclusive `open(..., "x")`, flush and `fsync` (`execution.py:284-301`), then re-reads its owner. My direct probe confirmed first writer wins, a second claimant receives the first owner, and a corrupt existing file is not overwritten.

For **every** recorded completion, `corroborate` requires an operation, an index owner equal to this execution, a verified journal row for that operation, and `SETTLED_VERIFIED`. Harness rows also require `task_id == operation_id`, a COMPLETE task, matching ledger request and ledger `execution_id`; if the server answers, its operation ID must match. Local rows require an available server `reply` with matching session; its operation ID must also match. See `execution.py:137-206`. My direct probes produced `OPERATION_MISSING`, `OPERATION_NOT_OWNED`, `OPERATION_TASK_MISMATCH`, `SERVER_OPERATION_MISMATCH`, and `JOURNAL_NOT_VERIFIED` for the respective mutations. With a real `ExecutionController` and synthetic local rows, the first owner showed completed while a second record copying its reply and operation showed uncertain in **both** `status()` and `list()`; deleting the claim made both uncertain. I found no remaining borrowed-facts completed display without rewriting the ownership index along with other local facts.

A missing or unreadable claim fails closed as `OPERATION_NOT_OWNED`. A crash after exclusive file creation but before complete JSON leaves a permanent corrupt first-writer file; a later claim does not repair it, and even a genuine settled execution displays uncertain. A prior execution's intact claim likewise prevents a later claimant from being shown completed. This favors no false success but can lose a true success display and needs operator reconciliation, not automatic reuse. The index, execution register, journal, and ledger all reside in the local client root. A same-user process able to rewrite these together can make a false display internally consistent; this index is **not** cryptographic or external attestation, and the caller-supplied bridge `execution_id` is an observation label, not authority. Ticket validation, server claim, supervisor admission and settlement remain the execution authority.

### Archived execution evidence

I read commands and outcomes, not reran the suites. `phase2_all.log` ran isolated pytest on `tests/phase2a` through `tests/phase2ops`: **411 passed, 2 live opt-in skipped**, exit 0. `phase1_authority.log` ran the eight named authority files: **134 passed**, exit 0. `phase1_full.log` excluded the Phase 2 packages and ended **11 failed, 2675 passed, 12 skipped, 88 subtests passed**, exit 1. The 11 IDs are Drive step3/step4, privacy, M20 feasibility/recovery (2)/semantic resilience (2), session facts, usage newline, and workflow restart; they match prior review logs, but I did not independently establish their root causes. `flutter_all.log` ended **191 passed, 2 skipped**.

All ten `ui_bridge_live_1..10.json` artifacts report exit 0 and `All tests passed!`; each has one `completed/SETTLED_VERIFIED` record and one `uncertain/SETTLED_EXECUTION_UNCERTAIN` mid-run cancellation. I checked all 20 preserved operation-index files: each exists and names its corresponding record execution ID. `refusals.txt` is zero bytes; the artifacts contain no `CLIENT_REFUSAL` or `HTTP_403`. This is ten clean recorded repetitions, not a root-cause explanation for the earlier intermittent 403.

`codex_cli_lifecycle_224305.json` and native stdout agree: programmatic digest approval, direct CLI probe exit 0, live authentication reported true, persisted native qualification, lifecycle `completed/SETTLED_VERIFIED`, and mid-run cancellation `uncertain/SETTLED_EXECUTION_UNCERTAIN` with attempt PID reported dead. I independently opened its preserved SQLite ledger and journal in read-only immutable mode: the lifecycle task is COMPLETE, its journal operation verified with a receipt, and the cancel task is FAILED with journal `execution_uncertain`; each task request's `execution_id` and `operation_id` match its preserved record and operation claim. These checks corroborate persisted output of the orchestrator run; I did not launch the native executor.

## C. New defects and validation limits

### DEFECTS table

| ID | Severity | File:line | Failure and evidence | Reproduced? |
|---|---|---|---|---|
| LOG-1 (new in round-4 repair) | Medium | `scripts/run_uri_phase2_server.py:60-79,116-120` | `RefusalLog` prints the raw ASGI path and the first 64 characters of arbitrary JSON `detail`, without validating that `detail` is a refusal code. Its “codes only” claim is false as a wrapper invariant. A refusal whose detail or path contains a bearer-like string logs it. The actual inspected `/client/v1` handlers return fixed codes for expected errors; no real bearer disclosure was observed. Log a fixed allowlisted code and a route label rather than untrusted path/detail. | **Yes**, direct isolated ASGI wrapper probe: a synthetic 200 response printed nothing; synthetic 403 `detail="Bearer synthetic-body"` and a 404 path containing `Bearer-synthetic-path` were printed. No production endpoint or credential used. |

The new diagnostic is limited to the Phase 2 server profile. Its wrapper does not read request headers or log successful response bodies, as confirmed by source and the 200 probe. The synthetic failure shows a conditional logging hazard rather than evidence that the current client sent a bearer in a path or that Core's fixed-code handlers returned one. `access_log=True` is configured at `log_level="warning"`; I did not observe 2xx access lines in the archived logs. The earlier 403 cannot be assigned to `REQUEST_BINDING`, `TURN_SCOPE`, `SESSION_SCOPE`, or `CLIENT_BINDING` because it predated this diagnostic and did not recur in the ten recorded runs.

No new execution-authority bypass or user-visible nested-record crash was established. The corrupt-claim scenario above is a fail-closed availability limit, not a borrowed-completion proof. A synthetic `proposal=None` and unknown nested evidence keys pass the register, but the inspected Dart reads handle them or do not read them; I do not report an unproven crash.

## D. UI wiring, remaining work and research claims

| UI wiring question | Round-5 determination | Basis |
|---|---|---|
| (a) Worker protocol | **YES** | Execution proposal/begin/status/cancel/list framing is present in the supervised worker path; archived isolated and live runs exercise it. |
| (b) Programmatic composition | **YES for the exercised Phase 2D/native path; Phase 2C wrapper source-compatible, not rerun** | Both wrappers forward `**kw`; native lifecycle and cancellation ended as recorded. |
| (c) Opt-in profiles | **YES** | Per-installation `ui-supervised-profile.json`, pinned manifest-backed worker startup, and no production UI fixture flag. |
| (d) Real Flutter UI driving worker | **PARTIAL** | Tasks mount, screen/runtime, widget suite and ten live Dart-to-worker runs exist; human approve/cancel/reopen was not observed, and LOG-1 affects the opt-in server diagnostic. |
| (e) Cutover | **NO** | C7 owner authorization, pinned UI and Chat/voice decision, migration, launcher, rollback, and full-suite triage gates remain. |

USER-PHYSICAL / NOT VERIFIED: a human approval, cancellation, and reopen in the running Flutter app; client-profile native CLI authentication and execution inside the actual isolated worker process; controlled 200+ hard power-loss/write-ordering campaign. C7 cutover needs its independent gates and explicit owner authorization (`docs/plans/C7_CUTOVER_REQUIREMENTS.md:3-18`). Chat `/ask` migration and pinned UI release remain separate C6/C7 decisions. Context Capsule and Task Compiler remain **design only, later undated work** (`docs/architecture/PHASE2C_TASK_COMPILER_PLACEMENT.md:1-26`); no accepted 2E/2F numbering is evidenced.

The research ledger should not imply delivery from research: Strata/Paperclip researched and deferred; AG-UI/A2UI researched; MCP broker and Context Capsule/Task Compiler design only; model residency separate prototype; URI Memory exists in Core and is not a delivered harness capsule. Supervisor scheduling/recovery and Phase 2D have process-test/native-run evidence, not physical power-loss qualification. `PHASE2OPS_REPORT.md:177-188` correctly says candidate awaiting independent review and Phase 2 not complete, but the unqualified “IMPLEMENTED / TESTED” label should remain bounded to the recorded paths; it does not resolve VAL-1, LOG-1, physical qualification or cutover. The old Phase 2D report's UI statements must be read with its correction records, not as current whole-UI acceptance.

## E. Verdict

Candidate and frozen-boundary integrity hold. The earlier execution and UI-shape defects are repaired to the tested boundary, and the ten live bridge runs plus native persisted run ended as claimed. The earlier authorization 403 still lacks a cause and was specifically an unresolved validation blocker; ten clean repetitions do not explain it. The newly added refusal diagnostic also violates its codes-only logging invariant. I therefore do not accept this slice or infer Phase 2 completion from this candidate.

## NOT VERIFIED

- Independent pytest or Flutter execution; I read those commands, counts, failure IDs and artifacts. My own execution consisted of hashing, direct-import/ASGI probes, repository source tracing, and read-only immutable SQLite inspection.
- Full Phase 2C native qualification rerun; exhaustive cancellation races; native execution in the real client-profile worker; human Flutter interaction; controlled physical power-loss qualification.
- Root cause and recurrence rate of the earlier HTTP 403; a real-world bearer leak through the diagnostic; production migration or cutover.

## FINAL VERDICT

**UI/OPERATIONS SLICE REJECTED**
