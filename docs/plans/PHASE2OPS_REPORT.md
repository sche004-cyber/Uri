# URI Phase 2 UI / operations slice, report

Date 2026-10-07. Author: Claude (implementer and self-auditor; NOT an independent audit). Worktree
`C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent`, detached at `e8e3b65`, everything uncommitted. Nothing was
committed, pushed, merged, frozen, cut over or activated; no login or re-authentication was performed; no credential file
was read, copied or forwarded; no account or global configuration was changed; the frozen Phase 1 checkpoint files are
byte-identical. The user is away (weeks); every step below ran without user interaction, and everything that needs the
user physically present is listed in section L as DEFERRED, not as passed.

Labels: IMPLEMENTED / TESTED (`COMPLETED_WITH_RESULT` automated run) / NATIVE RUN (real installed executor through the
full governed chain) / INDEPENDENTLY ACCEPTED / DEFERRED. REAL = installed CLI or real process; SYNTHETIC = fake NDJSON
harness; SIMULATED = process kill, not physical power loss.

## A. Starting authority

* Phase 2D candidate `C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2d-candidate-20261007-r2.zip`, SHA-256
  `cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d` (re-hashed before work started; sidecar matches);
  Codex CLI 0.158.0 / gpt-6-sol round 3: "PHASE 2D ACCEPTED — MORE PHASE 2 SLICES REMAIN".
* Frozen Phase 1 `final-closure-20261005-phase1.zip`, SHA-256 `31a34dcb...efeb98cf7` (re-verified by
  `tests/phase2a/test_frozen_core.py` inside the Phase 2 regression, 8 passed).
* Governing documents used: `PHASE2A_ARCHITECTURE.md`, `PHASE2B_INTEGRATION_BOUNDARY.md`,
  `PHASE2C_TASK_COMPILER_PLACEMENT.md`, `PHASE2C_NATIVE_QUALIFICATION_REPORT.md` (section P),
  `PHASE2D_COMPOSITION.md`, `PHASE2D_REPORT.md` (+ correction record), `C6_UI_INTEGRATION_CONTRACT.md`,
  `C7_CUTOVER_REQUIREMENTS.md`, and the Codex round-3 review (section D: UI/operations REQUIRED IN PHASE 2; Context /
  Task Package LATER PHASE; no official 2E/2F numbering).

## B. What was implemented (files)

New: `uri_supervisor_bridge/execution.py`, `uri_ui/lib/services/supervised_runtime.dart`,
`uri_ui/lib/screens/tasks/supervised_execution_screen.dart`, `uri_ui/test/supervised_execution_screen_test.dart`,
`uri_ui/test/supervised_runtime_live_test.dart`, `tests/phase2ops/` (conftest, test_lifecycle 12, test_cancel 6,
test_reconnect 5, test_worker_process 2 = 29 tests), `scripts/phase2ops_validate_ui_bridge.py`,
`scripts/phase2ops_native_execution.py`, `scripts/phase2ops_checkpoint.py`, `docs/architecture/PHASE2OPS_UI_OPERATIONS.md`,
this report.
Changed (Phase 2, not frozen): `uri_supervisor_bridge/worker_service.py` (four execution frames, proposal on
`approval_required`, `EXECUTION_IN_PROGRESS`), `uri_supervisor_bridge/runner.py` (three observation hooks; no new frozen
method overridden, `tests/phase2b/test_boundary.py` holds), `uri_supervisor_bridge/qualification.py` (R3-1/R3-2),
`scripts/run_uri_supervised_worker.py` (frames, preflight, close/EOF withdrawal), `tests/phase2d/conftest.py` (fixture
evidence names models; `server_status`), `tests/phase2d/test_qualification.py` (+2 R3 tests), `tests/phase2d/test_selfaudit.py`
(evidence models), `tests/phase2b/helpers/fake_harness.py` (in-band scenario marker for real-process tests),
`tests/phase2a/test_frozen_core.py` (`ALLOWED_NEW`), `scripts/phase2d_regression.py` (`tests/phase2ops`),
`docs/architecture/PHASE2D_COMPOSITION.md` (superseding notes, history kept).
Changed (Phase 1, NOT in the frozen checkpoint): `uri_ui/lib/app.dart` (Tasks destination mounts the opt-in entry).
Frozen Phase 1 checkpoint files changed: **none** (`paired_runtime.dart`, `paired_runtime_screen.dart`,
`settings_shell.dart` byte-identical).

## C. Architecture (summary; full note in `PHASE2OPS_UI_OPERATIONS.md`)

UI -> `SupervisedWorkerRuntime` spawns the Phase 2 worker profile (opt-in file in the client root, no manifest/launcher
change) -> frozen `turn_start/turn_intent` -> `approval_required` + `execution_proposal` -> approval card ->
`execution_begin {turn_id, approval_digest, proposal_digest}` (dispatch in a worker thread, returns at once) ->
`execution_status` (durable record + read-only ledger + read-only journal + server `GET .../status`) ->
`execution_cancel` at any non-terminal point -> receipt. Authority unchanged: Core approves/tickets/settles, the client
journal records, the supervisor ledger admits/fences/contains/reconciles; the worker owns an observation record; the UI
holds ids.

## D. UI execution path and approval semantics

* Entry: Tasks -> "Supervised execution (Phase 2, opt-in)" card, rendered only when
  `<client_root>/control/ui-supervised-profile.json` (`uri.phase2ops.ui_profile.v1`, `phase2d-supervised`) exists.
* Approval card: task text, result file, capability, executor (provider, model, kind), effect + reversibility,
  qualification (level, status, expiry), approval digest, proposal digest. Executor radios are locked while a card is
  pending; Send is disabled; typed text cannot approve (server `TURN_CAPACITY` + UI lock).
* `proposal_digest = sha256(canonical{client_id, session_id, turn_id, kind, provider, model, capability_id,
  argument_digest, approval_digest})`; `execution_begin` must echo it and the server's `approval_digest`; any mismatch
  drops the pending turn (`APPROVAL_DIGEST_MISMATCH` / `PROPOSAL_DIGEST_MISMATCH`). After begin the frozen ticket
  (`ARGUMENT_DIGEST_MISMATCH`) and the bound selection (`AUTHORITY_SELECTION_MISMATCH`) still apply.
* Frozen `turn_decide` kept (blocking; no mid-run cancel) for protocol parity.

## E. Lifecycle, cancellation, reconnect, receipt (behaviour)

| Topic | Behaviour | Evidence |
|---|---|---|
| Lifecycle | queued -> approving -> starting (ticket verified) -> running (bridge dispatch) -> completed / failed / cancelled / uncertain / quota_paused | `test_lifecycle.py` |
| Success | only `SETTLED_VERIFIED` -> `completed`; false claim / empty / wrong file -> `uncertain` (frozen server); exception after first server call -> `uncertain`; before -> `failed` | `test_failure_shapes_never_become_completed`, `test_server_unreachable_at_settle_is_uncertain_not_completed` |
| Cancel before approval | turn DENIED (`APPROVAL_DENIED`), server turn `cancelled`, zero tasks -> `cancelled/CANCELLED_BEFORE_APPROVAL` | `test_cancel_before_the_approval_is_posted_denies_the_turn` |
| Cancel between approval and dispatch | bridge refuses before submit: `NOT_STARTED:CANCELLED`, no task row -> `cancelled/CANCELLED_BEFORE_START` | `test_cancel_between_approval_and_dispatch_never_spawns` |
| Cancel while running | job kill (`cancelled_killed`), pid dead, descendants dead, one attempt, no re-admission, authority closed, journal + server `execution_uncertain` -> `uncertain/CANCELLED_AFTER_DISPATCH` | `test_cancel_while_running_*`, `test_cancel_kills_descendants_too`, real frames `test_worker_process.py`, REAL Codex (section G) |
| Cancel after terminal | `EXECUTION_TERMINAL`, record unchanged | `test_cancel_after_terminal_*` |
| Close / stdin EOF during a run | withdrawal (kill) and terminal record before the ledger closes | `test_close_during_execution_*`, real frames `close` reply |
| UI reconnect | `execution_list` on open; records durable; every status re-read from ledger/journal/server | `test_completed_execution_survives_a_worker_restart`, Dart live test part 3, widget test "reconnect" |
| Worker crash mid-run (REAL processes) | executor dies with the worker (job); next worker: frozen journal `recover()`, bridge revocation, record `uncertain/WORKER_RESTARTED` with ledger facts; nothing relaunched; held session refused, new session works | `test_worker_crash_mid_run_*` |
| Server unreachable at settle | `uncertain`; ledger COMPLETE / journal verified reported as facts; server turn `executing`; not called done | `test_server_unreachable_at_settle_*` |
| Stale UI | fresh status every time; cancel/begin/decide on terminal refused | `test_stale_ui_state_cannot_override_the_record`, widget test |
| Duplicate / replay | `TURN_NOT_PENDING` / `EXECUTION_IN_PROGRESS`; one attempt, one result | `test_duplicate_begin_and_replay_cannot_execute_twice` |
| One at a time | `EXECUTION_IN_PROGRESS` for turn frames, begin, snapshot/consent/commit; status/cancel/list/preflight open | `test_one_execution_at_a_time_*`, real frames |
| Receipt/status fields | execution/turn/session ids, provider, model, kind, capability, qualification, phase timestamps, state, reason, settlement code + message, bridge outcome, failure category, output sha256/bytes, ledger task/attempts/decision/open authorizations, journal state, server turn state, cancellation flag; no tickets/signatures/tokens | `test_record_never_contains_secrets_or_tickets`, widget receipt test |
| Provider choice | no fallback; `quota_paused` leaves the next choice to the user; unusable harness unselectable | `test_unqualified_provider_fails_closed_*`, widget tests |

## F. Tests and exact counts (all ORCHESTRATOR-PRODUCED, outside any reviewer sandbox)

Evidence directory `C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2ops\`.

| Suite | Command | Result | Log |
|---|---|---|---|
| Phase 2 (2A+2B+2C+2D+ops), final sequential run | `python -I scripts/phase2d_regression.py phase2` | **409 passed, 2 skipped** (skips: live opt-in tests) | `phase2_all_final.log` |
| of which `tests/phase2ops` | pytest `tests/phase2ops` | 29 passed | (also run alone: 29 passed) |
| of which `tests/phase2d` | within the above | 97 (95 + R3-1 + R3-2) | |
| Phase 1 authority suites | `... authority` | **134 passed** | `phase1_authority_final.log` |
| Phase 1 full (Phase 2 excluded) | `... phase1-full` | **2675 passed, 12 skipped, 11 failed, 88 subtests passed** = exact baseline IDs (`SAME_FAILURE_SET` vs `evidence\phase2d_r2\phase1_full.log`) | `phase1_full.log` |
| Flutter, whole `uri_ui/test` | `flutter test` | **189 passed, 2 skipped** (live tests without manifest) | `flutter_all_final.log` |
| Flutter, new widget tests | `flutter test test/supervised_execution_screen_test.dart` | 13 passed | within the above |
| Dart live bridge: REAL Dart runtime -> REAL Phase 2 worker process -> REAL Phase 2 server process (fixture executor) | `python scripts/phase2ops_validate_ui_bridge.py` | 1 passed (lifecycle completed; mid-run cancel `uncertain/CANCELLED_AFTER_DISPATCH`, `cancelled_killed`; reconnect from a fresh worker) | `ui_bridge_live.json` |
| `flutter analyze` on the new/changed Dart files | | No issues found | |

Contamination control unchanged (`scripts/phase2d_pytest.ini`, explicit ignores). Two concurrency artefacts were seen
and are recorded honestly: an earlier parallel Phase 1 authority run hit `SOURCE_MANIFEST_MISMATCH` twice because the
concurrently running Phase 1 full suite rewrites `uri_workspace/capabilities_registry.json` (part of the source pin);
the sequential rerun is clean (134). The Phase 1 full suite plants two zero-byte residue files at the tree root
(`STALE_BOOTSTRAP_EXECUTED`, `STALE_LAZY_EXECUTED`, from `test_c1_source_pin.py`) and `graphify update` writes
`graphify-out/converted/*.md`; both trip the frozen-boundary stray check and were removed before the final Phase 2 run.
First (parallel) Phase 2 run: 407 passed, 1 failed (`test_bridge_runner_overrides_only_the_harness_execution_seam`:
my first version overrode `_execute`; repaired by observing "starting" in the already-overridden `_validate_ticket`).

## G. Native Claude / Codex runs (REAL executors, run-scoped shell authentication, no login)

`scripts/phase2ops_native_execution.py`, evidence `codex_cli_lifecycle_190426.json`, `claude_code_lifecycle_190427.json`.

| Provider | Qualification | Run | Outcome |
|---|---|---|---|
| codex_cli 0.158.0, gpt-6-sol | direct probe OK, live auth OK -> NATIVE_QUALIFIED record persisted (expires 1793972081) | lifecycle: `execution_begin` returned in 0.004 s; `queued -> running (RUNNING) -> completed` in 16.2 s | `SETTLED_VERIFIED`, ledger COMPLETE (`POSTCONDITIONS_VERIFIED`), journal verified, server `reply`, result `pong.txt` = `PONG` |
| codex_cli | same record | REAL mid-run cancel: `execution_cancel` 12 s after RUNNING | kill granted; codex pid `ALIVE_MATCH -> DEAD`; settled 0.3 s later `uncertain/CANCELLED_AFTER_DISPATCH` (`SETTLED_EXECUTION_UNCERTAIN`); attempt `cancelled_killed`; ledger decision `RETRY_SAFE/RESUME_SESSION` recorded but NOT re-admitted (task FAILED `BRIDGE_SETTLED_CANCELLED`); journal + server `execution_uncertain`; cancel after terminal `EXECUTION_TERMINAL` |
| claude_code | direct probe `AUTH_REQUIRED`, live auth false -> NOT persisted | lifecycle through the same frames | `failed/NOT_STARTED:HARNESS_HARNESS_NOT_USABLE`, `SETTLED_FAILED`, execution closed, zero tasks, zero executor calls |

Native execution inside the real worker PROCESS still needs the CLI authenticated in the client profile (Phase 2D
limit; DEFERRED, see L).

## H. Phase 2D low findings (R3-1, R3-2)

FIXED, awaiting independent review (this candidate). `_check_evidence`: fixture evidence must carry `models`, a list
equal to the record's; missing or malformed -> `EVIDENCE_CONTENT_MISMATCH` (no crash, no wider set). Tests
`test_r3_1_malformed_fixture_evidence_models_is_refused_not_a_crash`, `test_r3_2_fixture_evidence_without_models_backs_nothing`;
every Phase 2D fixture now names its models; production (NATIVE) path unchanged.

## I. Self-audit: defects found and repaired before review

1. `_execute` override broke the Phase 2B boundary contract -> hook moved into `_validate_ticket` (ticket verified =
   starting). 2. `cancel` returned the bridge's whole reply nested under `kill` -> flattened. 3. Fake-harness scenario
   could not reach a REAL worker process (sanitized env) -> in-band `(fake scenario: X)` marker in the SYNTHETIC harness
   only. 4. Deterministic (no-Brain) row showed `NOT_QUALIFIED/NO_RECORD` on its proposal -> qualification only for
   harness rows; test added. 5. Widget: begin refused with `EXECUTION_IN_PROGRESS` dropped the card although the turn
   was still pending -> card kept in that one case. 6. Short execution ids crashed the card -> `_shortId`.
   7. Attempt rows end `FENCED`, not `ENDED` -> tests accept both. 8. `identity_state` returns `ALIVE_MATCH` ->
   tests use `startswith("ALIVE")`.

## J. Independent review

Candidate and mandate: see section N; the Codex CLI review runs after this report is cut into the candidate. Rounds,
findings and repairs are recorded in `evidence\phase2ops_review\` and appended to this report's correction record.

## K. Regression status

Phase 1: frozen checkpoint byte-identical; authority 134; full 2675/12/11 = baseline. Phase 2D: 97 passed inside the 409.
No gate weakened; no fixture flag reachable from the production UI path; no fallback added.

## L. DEFERRED — USER PHYSICAL PRESENCE REQUIRED

| Item | What remains | Why physical | Verified without it | Test to perform | Blocks |
|---|---|---|---|---|---|
| Human approval click on the real Flutter UI | a person presses "Approve and run" / "Cancel execution" on the running app | only the owner's finger proves the human path; automation cannot claim it | widget tests drive the real screen with a fake worker; the Dart live test drives the real runtime against real worker+server processes; proposal/approval binding tested at the worker | open Tasks -> Supervised execution with an opted-in client, approve, cancel mid-run, reopen the app and find the record | not this slice; owner acceptance before cutover (C7 gate 5) |
| Native login in the URI client profile (`codex login`, Claude Code sign-in) | the CLI must be authenticated under `<client_root>/home` | interactive browser/device login by the owner | in-process real Codex lifecycle + cancel (run-scoped auth); Claude fail-closed | run `scripts/phase2ops_native_execution.py` INSIDE the worker process profile after login | native execution inside the worker process; not the slice |
| Controlled physical power loss | 200+ hard power-offs with negative control on a throwaway VM (`PHASE2A_POWER_LOSS_TEST_PLAN.md`) | needs a machine the owner may kill | SIMULATED abrupt termination; real worker crash mid-run | the VM plan | any durability claim / Phase 2 freeze; not this slice |
| Cutover authorization | written authorization naming manifests, ports, launch entries (C7 gate 10) | owner decision | opt-in path works without touching any launcher | n/a | production cutover only |
| C6 owner decision 2 (Chat `/ask` on the paired runtime) | scope decision | owner decision | Tasks entry + screen wired; contract kept | n/a | nothing; a further UI slice if wanted |

## M. Research / implementation ledger

| Item | Status | Change this slice |
|---|---|---|
| Strata | RESEARCHED / DEFERRED | none |
| Paperclip | RESEARCHED / DEFERRED | none |
| AG-UI / A2UI | RESEARCHED | none (no transport adopted) |
| MCP broker | PLANNED / DESIGN ONLY | none |
| Context Capsule | DESIGN ONLY | none |
| Task Compiler | DESIGN ONLY | none; the only seam added is `execution_proposal` (display + binding), documented, not a compiler |
| Model residency | SEPARATE PROTOTYPE | none |
| Supervisor scheduling / recovery | IMPLEMENTED / TESTED (process level); physical power loss NOT QUALIFIED | real mid-run cancel + worker-crash reconciliation TESTED |
| Execution lifecycle, mid-run cancel, reconnect register, UI wiring (this slice) | IMPLEMENTED / TESTED / Codex NATIVE RUN; AWAITING INDEPENDENT REVIEW | new |
| Physical power-loss durability | NOT QUALIFIED | none |
| URI Memory | exists in Core; no harness context capsule | none |

## N. Candidate and verdict

Candidate cut by `scripts/phase2ops_checkpoint.py` into `C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\`
(`phase2ops-candidate-20261007.zip` + sidecar; SHA-256 in the sidecar and in `evidence\phase2ops_review\ROUND1_SUBJECT.txt`).
Status at cut time: **UI/OPERATIONS IMPLEMENTED — AWAITING INDEPENDENT REVIEW**. Phase 2 is NOT complete and NOT frozen.
Next remaining Phase 2 work (from the governing documents): the deferred user-physical qualifications above; the
Context Capsule / Task Compiler (LATER PHASE, design only, undated: `PHASE2C_TASK_COMPILER_PLACEMENT.md`); C7 cutover
items. No official 2E/2F numbering exists.

## Correction record (appended after independent review round 1; earlier text above is kept unchanged as history)

Codex CLI (gpt-6-sol) rejected candidate `ce935c4b...13d9d8` ("UI/OPERATIONS SLICE REJECTED") with three defects, all
reproduced or source-traced by the reviewer and all accepted by the implementer: OPS-1 (High) the durable register's
`completed` was relayed without being constrained by ledger/journal/server facts; OPS-2 (Medium) a valid-JSON record
missing `execution_id` raised `KeyError` in listing/restart; OPS-3 (Medium) the approval card omitted the verbatim
`approval_request.arguments` object required by C6. Repairs and their regression tests: `PHASE2OPS_REVIEW_REPAIR_ROUND1.md`.
Corrections to the text above: section E "Success: only SETTLED_VERIFIED -> completed" held for the execution thread
but NOT for a later status/list read of the record; it now holds for both (corroboration). Section E "Receipt/status
fields" gains `recorded_state` and `corroboration`. Section D "Approval card" now includes the exact arguments object
and the argument digest. Test counts after repair: `tests/phase2ops` 31 (29 + OPS-1 + OPS-2); widget tests 15 (13 + 2).
The UI truth-table determination (d) is the reviewer's: PARTIAL until a human click (DEFERRED). New candidate and
regressions: section N is superseded by the `-r1` candidate recorded in `PHASE2OPS_REVIEW_REPAIR_ROUND1.md` and
`evidence\phase2ops_review\ROUND2_SUBJECT.txt`.

## Correction record 2 (appended after independent review round 2; earlier text is kept unchanged as history)

Codex CLI (gpt-6-sol) rejected candidate `bffa742a...a8ec7` ("UI/OPERATIONS SLICE REJECTED"): OPS-1R (Medium) a record
copying every field of a genuine completed execution under another `execution_id` (or with a changed record-level
`session_id`) was still corroborated; OPS-2R (Medium) valid JSON with wrong field TYPES still crashed listing/restart.
Both reproduced by the reviewer and accepted. Repairs: the supervisor ledger's task request row now carries the
`execution_id` the bridge ran for (`SupervisorBridge.execute(work, context=...)`, no authority) and `corroborate()`
requires it, plus session/operation checks against the ledger row and the server; the register type-validates every
field it reads. Details and tests: `PHASE2OPS_REVIEW_REPAIR_ROUND2.md`. Section E "Receipt/status" and the
architecture note's corroboration row are superseded accordingly; `execution_list` now carries the `corroboration`
block and consults the server for completed rows. Candidate `-r2` and regressions: `evidence\phase2ops_r2\`,
`evidence\phase2ops_review\ROUND3_SUBJECT.txt`.

## Correction record 3 (appended after independent review round 3; earlier text is kept unchanged as history)

Codex CLI (gpt-6-sol) rejected candidate `05127e2f...1cbead`: OPS-4 (High, MY repair regression: the round-2
`context=` keyword broke the Phase 2D composition wrapper, so the archived native Codex run ended `EXCEPTION:TypeError`
— section G's native evidence for the `-r2` candidate was therefore NOT valid; the `-r1` and original runs stand);
OPS-1R residual (a harness record omitting its task took the local branch); OPS-2R residual (nested shapes vs Dart
casts); OPS-5 (array `request_json`); VAL-1 (one live Dart bridge run failed with `HTTP_403`, cause unresolved,
intermittent, not reproduced in two reruns). Repairs and honest status: `PHASE2OPS_REVIEW_REPAIR_ROUND3.md`.
Correction to section I: the self-audit list did not catch OPS-4 because the chained rerun checked suite counts but not
the native run's outcome before cutting the candidate; the chain now fails the candidate cut when the native run or the
live bridge does not end `completed`/exit 0.

## Correction record 4 (appended after independent review round 4; earlier text is kept unchanged as history)

Codex CLI (gpt-6-sol) rejected candidate `fdfb78ed...937b64`: OPS-4 residual (the Phase 2C qualification wrapper, missed
by my round-3 repair), OPS-1R residual (a LOCAL duplicate record could borrow a local server reply), OPS-2R residual
(evidence item contents vs a checked Dart cast), VAL-1 still unexplained. Repairs: `PHASE2OPS_REVIEW_REPAIR_ROUND4.md`
(per-execution OPERATION ownership index, journal required for local executions too, nested evidence validation,
tolerant Dart reads, the second wrapper, a refusal-code diagnostic in the Phase 2 server profile). Section E
"Receipt/status" gains `operation_id` / `operation_owner`. Candidate `-r4` and regressions: `evidence\phase2ops_r4\`.

## Correction record 5 (appended after independent review round 5; earlier text is kept unchanged as history)

Codex CLI (gpt-6-sol) disposed OPS-1, OPS-2, OPS-3, OPS-1R, OPS-2R, OPS-4 and OPS-5 as REPAIRED (within the stated
local-state trust boundary) on candidate `fc9c96ec...51ed58`, and rejected it on LOG-1 (new, Medium: the round-4 refusal
diagnostic logged unvalidated path/detail text) with VAL-1 still open. LOG-1 repair: `uri_supervisor_bridge/refusal_log.py`
(route shape + allow-listed code only; tests). VAL-1 analysis, recorded honestly: the single `HTTP_403` (candidate `-r2`
chain, second lifecycle, approval POST, server turn left at `approval_required` v0) is one of the frozen server's
pre-mutation refusals (`client_service._record`: `TURN_SCOPE` / `SESSION_SCOPE` / `check_binding` `REQUEST_BINDING`; or
`client_pairing.resolve`: `CLIENT_BINDING`); every input to those checks is constant for the worker's requests and the
frozen transport discards the reason by design, so no client-side cause was found; 17 later runs (2 + 5 + 10) passed and
0 refusal lines were logged once the diagnostic existed. It remains an OPEN observation for the owner's physical
qualification, not a PASS. Candidate `-r5` and regressions: `evidence\phase2ops_r5\`.

## Correction record 6 (appended after independent review round 6; earlier text is kept unchanged as history)

Codex CLI (gpt-6-sol) on candidate `1daa73f7...6c047`: every execution/UI finding remains REPAIRED; VAL-1 judged an open
physical-qualification item, not a slice blocker; rejected on LOG-1R (the refusal logger's code check was a format
check, not an allow-list) and LOG-2 (`/client/v1evil` treated as in scope). Repairs: `PHASE2OPS_REVIEW_REPAIR_ROUND6.md`
(`KNOWN_CODES` allow-list of the frozen server's refusal codes, GET/POST only, exact `/client/v1` scope). Candidate
`-r6` and regressions: `evidence\phase2ops_r6\`.
