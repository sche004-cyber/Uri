# URI Phase 2 UI/operations independent review, round 4

Date: 2026-10-07. Subject: `phase2ops-candidate-20261007-r3.zip`, HEAD `e8e3b65` plus uncommitted work. I treated implementer documents and orchestrator output as claims. I changed no repository source, test, document, configuration, account or login state. My synthetic state is under `uri-agent/work/c1/reviewer_ops_round4/`. Pytest and Flutter were unavailable in this sandbox.

## A. Integrity and frozen boundary

I independently computed SHA-256 `fdfb78edf9621ee8828d6a4a10c5a466fa3116f22e8c82cfea100a2e05937b64`, matching the round-4 subject and sidecar. The archive has 177 members: 174 manifest entries (112 tree, 62 evidence) and three metadata entries. I hashed every manifest member and compared its bytes with the live tree/evidence file: zero mismatches or missing files. Earlier candidates remain unchanged: ops r2 `05127e2fe87ef869e83eeddcdcae47cc3eb804dd5bce791b34860b966b1cbead`, ops r1 `bffa742ac9f8b4e6aadebde8bb91aa6c22638be6b4feeca6a5cfb7a0a1aa8ec7`, original ops `ce935c4be0e29c67d0d34772c9584e8ce3ac836e118e490ad167d8447d13d9d8`, Phase 2D r2 `cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d`.

The Phase 1 checkpoint itself hashes to `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`; all 121 checkpoint files are byte-identical to this tree. `uri_ui/lib/app.dart` is outside the checkpoint and is explicitly allowed for the Tasks mount by `tests/phase2a/test_frozen_core.py:22-29`. This is still uncommitted candidate work, not a released milestone.

## B. Earlier findings and adversarial repair checks

| Earlier finding | Round-4 disposition | Independent basis |
|---|---|---|
| OPS-1 | **Partly repaired; residual open.** Fact-free completed records become uncertain, and task-bearing rows are bound to the ledger execution ID. No-task local records can still copy another local turn's reply. | `execution.py:134-193`; direct `ExecutionController.status()` and `list()` probe below. |
| OPS-2 | **Partly repaired; residual open.** Top-level and several nested corruptions become `RECORD_SCHEMA`; nested evidence values can still crash screen rendering. | Direct register probe; Dart screen cast at `supervised_execution_screen.dart:410`. |
| OPS-3 | **Repaired on source inspection.** The approval card shows the arguments object and digest before approval. Human click unverified. | `supervised_execution_screen.dart:356-369`; worker digest binding. |
| OPS-1R | **Still open for local records.** Harness kind with omitted task is refused, and a server operation naming an existing local supervisor task is refused. A second no-task `server_local_model` record with the same turn/session can borrow a legitimate local server reply; the check does not bind the reply or journal operation to this execution ID. | Direct controller status/list probe: synthetic record with `kind=server_local_model`, `capability_id=remember_fact`, `task_id=None`, `code=SETTLED_VERIFIED`, and a borrowed `reply`/session/operation returned `completed`, gaps `[]`. `execution.py:169-185,387-389`. |
| OPS-2R | **Still open in the user-visible path.** `_well_typed` rejects the earlier provider-list, evidence-list-member and timestamp-list examples, and Dart's top-level readers tolerate wrong shapes. But it accepts a dict evidence member with `output_sha256:[1]`; the screen casts that field `as String?` when rendering status. | Direct register probe accepted that valid JSON and listing survived; Dart failure source-traced at `supervised_execution_screen.dart:410`, not Flutter-run. |
| OPS-4 | **Still open at another composition seam.** Phase 2D wrapper now forwards `**kw`; Phase 2C native qualification's `Stack` still monkeypatches `bridge.execute` with `def execute(work)` and then drives `SupervisedTurnRunner.run/decide`. The runner always calls `bridge.execute(work, context=self.dispatch_context)`, even when context is `None`. | `scripts/phase2c_native_qualification.py:172-175,418-423`; `uri_supervisor_bridge/runner.py:65`. Source-traced, not a full Phase 2C native rerun. |
| OPS-5 | **Repaired for the reported and other ordinary JSON shapes.** Non-object `request_json` becomes `REQUEST_UNREADABLE`, then a request mismatch. | Direct synthetic SQLite probes with `[]` and invalid UTF-8 BLOB both returned error views without raising; `execution.py:90-100`. No other raising ledger shape established. |
| VAL-1 | **Intermittent failure unresolved; new runs pass.** The prior HTTP 403 has no established root cause. Five repaired live bridge artifacts report exit 0 and both lifecycle and mid-run cancel outcomes. This is useful repeatability evidence but does not establish why authorization intermittently refused. | Read orchestrator JSON/stdout, not independently Flutter-run. `scripts/run_uri_phase2_server.py:91` enables access logging only in this profile. |

For the local no-task probe, I created a valid-schema completed record under `work/c1/reviewer_ops_round4`, supplied a server callback with `state=reply`, matching session and a non-null operation absent from the local supervisor ledger, and used the real controller's `status()` and `list()`. Both displayed `completed`; `status()` had `corroboration.gaps=[]`. The genuine local deterministic row uses `kind=server_local_model`, `capability_id=remember_fact`, no supervisor task, and a server reply (`tests/phase2ops/test_lifecycle.py:207-220`). A duplicate can copy those fields. This is a phantom display receipt, not evidence of another execution or Core authority bypass. The supervisor-task check cannot establish whether a non-null operation belongs to this execution when no supervisor task is recorded.

The malformed evidence probe stored `evidence:[{"output_sha256":[1]}]` in a valid JSON register row; `ExecutionRegister.get()` returned it without `RECORD_SCHEMA`. `ExecutionStatus.fromJson` accepts it through `_maps` (`supervised_runtime.dart:31-33,181`), then the status card evaluates `ev['output_sha256'] as String?` (`supervised_execution_screen.dart:410`). Dart's checked cast rejects the list. The tolerant reader repair is therefore incomplete at the rendering boundary. Other nested map fields could deserve a separate audit; I did not claim an exhaustive shape proof.

The archived repaired native run is credible for its own path. `codex_cli_lifecycle_220006.json` reports a programmatic approval, live auth, persisted native qualification, a `completed/SETTLED_VERIFIED` lifecycle and a `uncertain/SETTLED_EXECUTION_UNCERTAIN` mid-run cancellation with a dead attempt PID. Its stdout summary agrees. I opened the preserved ledger with SQLite `mode=ro&immutable=1`: lifecycle task is `COMPLETE` and cancel task `FAILED`; each request's `execution_id` matches the corresponding run record and `operation_id` matches the task ID. This is read-only corroboration of persisted facts, not my own native execution. The Phase 2C wrapper is a different path and is still incompatible.

## C. Defects and validation

| ID | Severity | File:line | Failure and evidence | Reproduced? |
|---|---|---|---|---|
| OPS-4 residual | High, blocks | `scripts/phase2c_native_qualification.py:172-175,418-423`; `uri_supervisor_bridge/runner.py:65` | Phase 2C qualification wrapper takes only `work`; runner always supplies `context=`, so a harness run through that stack reaches `TypeError` before bridge execution. The Phase 2D wrapper was fixed, but this separate composition seam was missed. | Source-traced; full Phase 2C native script not rerun. |
| OPS-1R residual | Medium, blocks | `uri_supervisor_bridge/execution.py:169-185,387-389` | A no-task local record can borrow another local completion's server reply and be shown `completed` in status and list without a journal receipt or per-execution binding. | **Yes**, direct-import controller probe with synthetic state. |
| OPS-2R residual | Medium, blocks | `uri_supervisor_bridge/execution.py:234-247`; `uri_ui/lib/services/supervised_runtime.dart:31-33,181`; `uri_ui/lib/screens/tasks/supervised_execution_screen.dart:410` | A valid JSON evidence map with non-string `output_sha256` passes the register and decoder, then the status card's checked cast throws. | Python acceptance **reproduced**; Dart rendering source-traced, not Flutter-run. |

No new authority bypass was found. OPS-5's malformed request is contained. The earlier `provider:[1]`, evidence member `[1]`, and `queued_at:[1]` rows all became `uncertain/RECORD_SCHEMA` in my direct register probe, and listing/restart did not raise. A synthetic ledger `request_json=[]` returned `request.error=REQUEST_UNREADABLE`; an invalid UTF-8 BLOB also returned that error. The valid local deterministic row remains supported in the normal implementation; the defect is its duplicate-record display binding.

I checked test commands and outcomes in `evidence/phase2ops_r3`, without running those suites. Isolated Phase 2A/B/C/D/ops command: **411 passed, 2 live opt-in skipped**, exit 0. Eight-file Phase 1 authority command: **134 passed**, exit 0. Full Phase 1 command excluding Phase 2 packages: **2675 passed, 12 skipped, 11 failed, 88 subtests passed**, exit 1. Its failure IDs are the same eleven reported in round 3: Drive step3/step4, privacy, M20 feasibility/recovery/semantic resilience, session facts, usage newline, workflow restart. Flutter log ends **191 passed, 2 skipped**. Five separate `ui_bridge_live_1..5.json` artifacts each report exit 0 and stdout `All tests passed!`; each has one completed settlement and one uncertain post-dispatch cancellation. None is my test run.

VAL-1 remains an unexplained intermittent approval HTTP 403, observed in the previous exact-candidate run and absent in seven later runs (two immediate reruns and these five). An unexplained authorization refusal is not acceptable as a closed validation finding for this slice, even though its current frequency and consequence are uncertain. The access-log change is narrow in the Phase 2 server profile: uvicorn access lines contain method, URL path/query and status, not request bodies or Authorization headers. The literal claim that logs can *never* contain a bearer is too broad because an ill-advised bearer in a query string would be logged; the inspected client protocol uses headers. I found no body or header logging introduced by this change.

## D. UI wiring, remaining work and claim boundaries

| UI wiring question | Determination | Basis |
|---|---|---|
| (a) Worker protocol | **YES** | Four execution frames exist in supervised worker and service; isolated tests claim coverage. |
| (b) Programmatic composition | **PARTIAL** | Repaired Phase 2D and native Codex paths ran to terminal states; the Phase 2C qualification wrapper is still incompatible. |
| (c) Opt-in profiles | **YES** | Manifest-backed supervised worker and per-installation UI opt-in; no production UI fixture flag. |
| (d) Real Flutter UI driving worker | **PARTIAL** | Tasks mount, screen/runtime and automated live bridge artifacts exist; no human click, and malformed evidence can break the status card. |
| (e) Cutover | **NO** | C7 owner authorization, pinned UI, migration, launcher and qualification gates remain. |

USER-PHYSICAL / NOT VERIFIED: human approval/cancel/reopen in a running Flutter app; native CLI login and native execution inside the actual isolated client-profile worker; controlled 200+ hard power-loss campaign. Chat `/ask` migration, pinned UI build and C7 cutover are separate remaining decisions/gates. Context Capsule and Task Compiler are design-only, later undated work, not an accepted next mandatory Phase 2 slice. No accepted 2E/2F numbering was found.

The research ledger should retain Strata/Paperclip as researched/deferred; AG-UI/A2UI researched; MCP broker and Context Capsule/Task Compiler design-only; model residency a separate prototype; URI Memory an existing Core feature, not a delivered harness context capsule. Supervisor scheduling/recovery and Phase 2D have process-test evidence, not physical durability qualification. The report's current lifecycle/native-run claim is supported by artifacts for the repaired Phase 2D path, but an unqualified blanket claim of completed UI status truth or all composition seams is overstated by the defects above. Phase 2 is neither fully implemented nor ready to freeze.

## E. Verdict

Archive and Phase 1 integrity hold. The repaired native Phase 2D lifecycle and five live bridge runs ended as claimed, but another native composition wrapper still breaks on `context=`, no-task local history can display a borrowed completion, and malformed evidence still breaks the user-visible status card. The intermittent HTTP 403 remains unexplained. The slice fails independent acceptance.

## NOT VERIFIED

- Independent pytest or Flutter counts; I read the commands, outputs and JSON, ran direct-import probes, and read preserved SQLite in immutable mode.
- Full Phase 2C native script, live human Flutter clicks, native authentication inside the client profile, physical power-loss durability, and all cancellation interleavings.
- Root cause of the intermittent HTTP 403; production cutover and historical migration.

## FINAL VERDICT

**UI/OPERATIONS SLICE REJECTED**
