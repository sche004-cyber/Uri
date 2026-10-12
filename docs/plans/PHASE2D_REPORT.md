# URI Phase 2D: composition and closure slice, report

Date 2026-10-07. Author: Claude (implementer and self-auditor; NOT an independent audit). Worktree
`C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent`, detached at `e8e3b65`, everything uncommitted. Nothing was committed,
pushed, merged, cut over or activated; no login or re-authentication was performed; no credential file was read, copied or
forwarded; no account or global configuration was changed; the frozen Phase 1 checkpoint was not touched; the frozen
launcher, worker, server and UI still compose Phase 1 with nothing qualified. The user was away (phone only); every step
below ran without user interaction.

Labels: IMPLEMENTED / TESTED (`COMPLETED_WITH_RESULT` automated run) / NATIVE QUALIFIED (real installed executor through
the full governed chain to ledger COMPLETE and a verified receipt) / INTEGRATED / FROZEN / CUT OVER. REAL = installed CLI
executed; SYNTHETIC = fake NDJSON harness; SIMULATED = process kill, not physical power loss.

## A. Starting checkpoint and baseline

* Phase 2C candidate `C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2c-candidate-20261007.zip`,
  SHA-256 `4e8126539da1f0ede3989f6d307253b5b4267be4fe1ce4ae405d19e761840f71` (sidecar matches).
* Frozen Phase 1 `final-closure-20261005-phase1.zip`, SHA-256 `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`
  (re-verified by `tests/phase2a/test_frozen_core.py`, 8 passed).
* Baseline before any change: `tests/phase2c` + frozen-core 30 passed (`evidence\phase2d\baseline_phase2c_frozen.log`).
* Git: the same 11 tracked Phase 1 overlay modifications as in Phase 2A/2B/2C; no tracked file newly modified by this slice.

## B. Slice ledger reconstructed from the governing documents

| Slice | Before 2D | After 2D |
|---|---|---|
| 2A Durable Task Supervisor | IMPLEMENTED, TESTED, Codex NATIVE QUALIFIED (run-scoped), NOT INTEGRATED, NOT FROZEN | + F-C1 resume guard, cancel; same status |
| 2B Core <-> Supervisor bridge | same | + model pin, cancel, settlement mapping; same status |
| 2C native executor qualification | codex_cli QUALIFIED run-scoped; claude_code BLOCKED | unchanged (see G) |
| Production policy / persisted qualification | NOT DONE (decision) | IMPLEMENTED, TESTED, Codex record persisted and re-validated (REAL); NOT INTEGRATED into frozen launchers |
| F-C1 session persistence vs resume | OPEN | DECIDED, IMPLEMENTED, TESTED |
| Worker/UI composition + human approval path | PLANNED (`SupervisedTurnService` unused) | IMPLEMENTED, TESTED over the frozen UI frames (in-process REAL server; REAL worker + REAL Phase 2 server processes); human click USER INTERACTION REQUIRED |
| Claude Code native qualification | BLOCKED | USER INTERACTION REQUIRED; fail-closed path re-demonstrated through the composition |
| Power-loss qualification | PLANNED, NOT RUN | SIMULATED abrupt-termination test added; physical NOT EXECUTED |
| Task Compiler | DESIGN ONLY | DESIGN ONLY (governing plan places it after this slice; no code) |
| Strata / research-derived techniques | RESEARCHED, NOT IMPLEMENTED, NOT REQUIRED | unchanged |

## C. What was implemented

New: `uri_supervisor_bridge/qualification.py`, `uri_supervisor_bridge/composition.py`, `uri_supervisor_bridge/worker_service.py`,
`scripts/run_uri_supervised_worker.py`, `scripts/run_uri_phase2_server.py`, `scripts/phase2d_composition_qualification.py`,
`scripts/phase2d_pytest.ini`, `scripts/phase2d_regression.py`, `scripts/phase2d_checkpoint.py`, `tests/phase2d/` (81 tests: abrupt_termination 10, cancel 4, policy_composition 10, qualification 21, selfaudit 13, session_resume 10, worker_process 2, worker_service 11),
`docs/architecture/PHASE2D_COMPOSITION.md`, this report.
Changed (Phase 2, not frozen): `uri_supervisor/supervisor.py` (resume guard: same task, same executor registration, validated
id; `request_cancel`; `cancelled_killed` end reason), `uri_supervisor_bridge/bridge.py` (`ExecutorBinding.qualified_models`,
`MODEL_NOT_QUALIFIED`, `cancel()`, `CANCELLED` settlement), `tests/phase2a/test_frozen_core.py` (`ALLOWED_NEW`).
Frozen Phase 1 files changed: **none** (frozen-core suite passes; the Phase 2 worker/server are separate opt-in profiles).
Architecture and decisions: `docs/architecture/PHASE2D_COMPOSITION.md`.

## D. Session/resume decision (F-C1)

Decided and implemented as described in the architecture document: the harness thread id is execution metadata on the
attempt row only; reused only for a `RESUME_SESSION` retry of the same task under the same authorization row (validity
re-checked by admission), the same executor registration and the same model; invalid/stale sessions take the governed retry
path (`RETRY_FRESH` / `RETRY_BUDGET_EXHAUSTED`), never COMPLETE from a claim; settled tasks and supervisor restarts never
resume. Codex-side thread persistence kept (resume is a qualified capability; URI correctness does not depend on it).
Tests `tests/phase2d/test_session_resume.py` (10): normal continuation, cross-task reuse refused, re-registered executor runs
fresh (`attempt.resume_refused` event), stale session -> `RETRY_FRESH` -> fresh attempt COMPLETE, exhausted budget -> FAILED,
revoked authority blocks resume, expired window blocks resume, completed task never re-admitted, bridge keeps one auth row
and the bound model, restart fails the leftover (`AUTHORITY_REVOKED_RESTART`) and the same ticket is `DUPLICATE_OPERATION`.
REAL resume evidence remains the Phase 2C record `evidence\phase2c\codex_resume1.json` (induced interruption).

## E. Production policy and persisted qualification

* Server: explicit policy FILE (`<state_root>/control/phase2_reasoning_policy.json`), only `client_external_harness` rows,
  deterministic row always implied, malformed file refuses all rows (`tests/phase2d/test_policy_composition.py`, 10).
  The frozen `default_composition()` is unchanged (deterministic only); the Phase 2 server profile reads the file.
* Client: qualification records re-validated on every load (binary path identity, SHA-256, `--version`, record digest,
  level, provider), live auth status probe (never persisted, never a login), model pin at the bridge
  (`tests/phase2d/test_qualification.py`, 21, including the D-D1 regression).
* REAL: `evidence\phase2d\codex_composition4.json` (see G) persisted a `NATIVE_QUALIFIED` record for
  `(codex_cli, C:\Users\cheta\AppData\Roaming\npm\codex.cmd, 0.158.0, gpt-6-sol)` from the direct probe + live status, and the
  governed turn ran from that record. Codex is one qualified row, not a permanent Main Brain; click-to-choose unchanged.
* NOT INTEGRATED: the frozen launchers/manifests pin the frozen entrypoints and the frozen `default_composition`; switching is
  cutover (C7 gates 4, 5, 10). Production integration is therefore NOT complete; the composition profiles are ready for it.

## F. UI / worker composition and the human approval path

`SupervisedWorkerService` serves the frozen worker protocol over the supervised runner; `turn_decide` optionally digest-bound;
`turn_cancel` for pending turns. Tested:
* in-process, REAL paired server, persisted FIXTURE record, SYNTHETIC executor (`tests/phase2d/test_worker_service.py`, 11):
  full path `SETTLED_VERIFIED` with the exact UI frames, frozen frame shape, wrong digest drops the turn, duplicate decide,
  decline/cancel, reconnect (restarted worker) refuses the stale turn and a fresh approval executes exactly once, typed text
  never confirms/approves, smuggled `ticket`/`reasoning`/`arguments` keys refused, unqualified model refused before any task,
  unqualified provider offered by policy fails closed with zero tasks, provider outside the policy refused by the server;
* REAL processes (`tests/phase2d/test_worker_process.py`, 2): `scripts/run_uri_phase2_server.py` + `scripts/run_uri_supervised_worker.py`
  under the frozen manifests, framed stdio: preflight (`worker_profile=phase2d-supervised`, `production_cutover=False`),
  `harness_discover` with the qualification report, `turn_start` -> `turn_decide` (digest) -> `SETTLED_VERIFIED`, result file,
  ledger COMPLETE, wrong digest refused, smuggled key refused, clean close; a worker without `--allow-fixture-qualification`
  invalidates the fixture record (`LEVEL_NOT_ALLOWED`) and the same turn settles `SETTLED_FAILED` with nothing executed.
* The frozen UI is byte-identical and still spawns the frozen worker; a human click on the physical UI against the supervised
  worker is USER INTERACTION REQUIRED, and connecting the UI to the Phase 2 worker is a cutover item.
* Known frozen-server property surfaced by the tests: a dropped `approval_required` turn holds its session (`TURN_CAPACITY`,
  HTTP 429 over the transport) until the server expires it (15 min idle / 60 min absolute); a new session continues meanwhile.

## G. Native harness qualification matrix

| Harness | Direct CLI | Live auth status probe | Persisted record | Through the composition | Status |
|---|---|---|---|---|---|
| Codex CLI 0.158.0 (`gpt-6-sol`) | OK (`probe_codex_cli.json`, answer `OK`) | `codex login status` -> logged in (stderr, exit 0) | `NATIVE_QUALIFIED`, hash `c54db675...4323c3`, models `[gpt-6-sol]` | REAL run `codex_composition4.json` (14.5 s): `SETTLED_VERIFIED`, ledger COMPLETE `POSTCONDITIONS_VERIFIED`, 1 attempt exit 0, argv sha recomputed and matched, `uri_verified postcondition_check`, 4-byte `PONG` sha `95784973...706c87`, receipt basis `uri_supervisor_postcondition_verified` | **NATIVE QUALIFIED, run-scoped authentication** (shell environment; not yet inside the worker-process profile, see M) |
| Claude Code 2.1.287 | `claude auth status` -> `loggedIn:false`; `-p` -> `Failed to authenticate` | False | none persisted (refused: probe failed) | `claude_composition1.json`: `SETTLED_FAILED`, `execution_closed`, 0 tasks, registry `NATIVE_UNQUALIFIED`/not usable | **NOT NATIVE QUALIFIED, USER INTERACTION REQUIRED** |
| Antigravity | n/a | n/a | refused by record loader | `EXECUTE_REFUSED` | REFUSED (unchanged) |

Four REAL Codex runs, all kept: run 1 (`codex_composition1.json`) is the evidence of defect D-D1 (status read from stdout only
-> no record persisted -> `SETTLED_FAILED`, 0 tasks: the fail-closed path with a missing record); run 2 verified end to end but
its post-run harness checks crashed (H-D1); run 3 verified end to end with one harness check mis-built (H-D2: wrapper not
rehashed; the control answered `EXECUTABLE_HASH_MISMATCH` correctly); run 4 (`codex_composition4.json`) is the final record:
`SETTLED_VERIFIED`, persisted record `record_sha256 0c991c27...99023f`, executable sha `c54db675...4323c3`, argv sha
recomputed and matched, and all 12 post-run adversarial checks PASS (unqualified model offered by policy -> `SETTLED_FAILED`
with no new task; tampered record -> `RECORD_DIGEST_MISMATCH`; wrapper qualifies then modified wrapper -> `EXECUTABLE_HASH_MISMATCH`;
replay -> `DUPLICATE_OPERATION`; authority closed after settlement; tampered arguments -> `ARGUMENT_DIGEST_MISMATCH`; other
confirmed intent -> `APPROVAL_DIGEST_MISMATCH`; generation change / after deadline -> `TICKET_REFUSED`; receipt basis is the
ledger; restart revives nothing). Each run left one Codex thread in the user's own Codex store (F-C1 trade-off, documented).

Claude qualification procedure (for the user, later; nothing here was run):
1. In a terminal: `claude` (interactive login) or `claude setup-token`; confirm `claude auth status` shows `loggedIn:true`.
2. `python -I scripts/phase2d_composition_qualification.py --provider claude_code --evidence <dir>`; expected: probe `OK`,
   live status `True`, record persisted, `SETTLED_VERIFIED`; expected first finding: Claude resume through `append` mode.
3. For the worker-process profile, the login must be performed in the URI client profile (`HOME=<client_root>\home`): same for Codex.

## H. Power-loss status

`tests/phase2d/test_abrupt_termination.py` (10): SIMULATED abrupt termination (`os._exit` at 8 transition points while a real
child executor runs): every committed fact present afterwards, `PRAGMA integrity_check` ok, WAL + `synchronous=FULL` in force
on the next writer (and the ledger refuses to run without them), one recovery decision per in-flight attempt, invariants hold,
second restart changes nothing. Physical power loss and OS write reordering: **NOT EXECUTED** (plan unchanged; needs a VM;
no shutdown/reboot/power-cycle was performed). The Phase 2B report listed power loss among the reasons not to freeze; that
reason stands unless the owner rules the VM test out of this milestone.

## I. Strata / research-derived techniques ledger

| Capability | RESEARCHED | PLANNED | PROTOTYPED | IMPLEMENTED | TESTED | QUALIFIED | FROZEN |
|---|---|---|---|---|---|---|---|
| Strata (resident model optimisation) | yes (Phase 1/engine research, `uri-resident-runtime-v1-frozen` memory: optimisation CLOSED) | no (not in the Phase 2 plan) | no | no | no | no | no |
| Local-model executors in the supervisor | yes | no | no (data shape only) | no | no | no | no |
| Task Compiler | yes (`PHASE2C_TASK_COMPILER_PLACEMENT.md`) | design note, undated | no | no | no | no | no |

Nothing research-derived was added to Phase 2; the governing plan does not require it.

## J. Regression results and contamination control

Canonical scope: `scripts/phase2d_pytest.ini` + `scripts/phase2d_regression.py` (never recurses `work/`, `evidence/`, rollback
residue; collection pinned by `test_phase2_test_scope_cannot_collect_preserved_runtime_state`). Nothing under `work/` or
`evidence/` was deleted.

| Run | Result | Log |
|---|---|---|
| `tests/phase2d` focused (final code) | 81 passed, 83 s | `evidence\phase2d\phase2d_focused_final.log` |
| All Phase 2 suites, run 1 (before D-D1 repair; code otherwise final) | 358 passed, 2 skipped (opt-in live), 225 s | `phase2_all_run1.log` |
| All Phase 2 suites, run 2 (final code, concurrent with the REAL Codex run 4) | 363 passed, 1 failed, 2 skipped, 227 s. The failure, `tests/phase2b/test_bridge_e2e.py::test_quota_pause_preserves_task_and_only_an_explicit_other_provider_continues`, is `SERVER_REFUSED:TICKET_CLOCK_OR_GENERATION`: the frozen 60 s ticket freshness window elapsed before the claim while the machine ran the Codex composition and this suite at once. Nothing in this slice touches ticket timing or the quota path; the module alone re-ran 15 passed (setups 1.6 s). Classified ENVIRONMENTAL (load). | `phase2_all_run2.log` |
| All Phase 2 suites, run 3 (final code, nothing else running) | 364 passed, 2 skipped (opt-in live), 0 failed, 225 s (168 + 93 + 22 + 81; frozen-core 8 included) | `phase2_all_run3.log` |
| Phase 1 authority suites (`-I`) | 134 passed, 158 s (identical to the 2B/2C baseline) | `phase1_authority_run1.log` |
| Phase 1 full repository suite (`-I`, Phase 2 suites excluded, scoped) | 2675 passed, 12 skipped, 11 failed, 88 subtests passed, 873 s; collection 2,698 tests, no `work/` residue collected | `phase1_full_run1.log` |

Known baseline: 11 failures (`step3_test::test_drive`, `step4_test::test_download`, `test_capability_directory` privacy,
`test_m20_feasibility_validation`, 2x `test_m20_recovery_loop`, 2x `test_m20_semantic_interpreter_resilience`,
`test_orchestrator_session_workflow`, `test_usage_import_boundary`, `test_workflow_restart_recovery`), 12 skipped.
Comparison, ID by ID: the eleven failures in `phase1_full_run1.log` are exactly the eleven baseline IDs above; passed count 2675 equals the Phase 2C final run; no new failure, no new skip. No frozen Core file changed in this slice (frozen-core suite passes inside every Phase 2 run).

## K. Self-audit: defects found and repaired

| ID | Severity | Where | Root cause | Repair | Regression test | Failed before repair? |
|---|---|---|---|---|---|---|
| D-D1 | High (false NOT_AUTHENTICATED: qualified Codex unusable) | `qualification.native_auth_probe` | Codex 0.158.0 prints `Logged in using ChatGPT` on **stderr**; the probe read stdout only | inspect both streams; exit status and "not logged in" decide first | `test_codex_status_probe_reads_both_streams_and_exit_status` (5 cases) | Yes (REAL: `codex_composition1.json` live_auth False; test case `[2-...-0-True]` fails on the old code) |
| H-D1 | harness (evidence script) | `phase2d_composition_qualification.py` | post-run checks ran after a second governed turn had overwritten the captured ticket; argv recomputed with the `PATHEXT` spelling (`codex.CMD`) instead of the record's resolved path (`codex.cmd`); the binary-swap check copied the npm shim, which cannot find its `node_modules` elsewhere | snapshot captures before further turns; recompute with the binding's executable; use a `.cmd` wrapper | n/a (harness); offline recomputation matched (`True`) | n/a |
| H-D2 | harness (evidence script) | `phase2d_composition_qualification.py` check (c) | the `.cmd` wrapper record kept the original executable hash, so the "wrapper qualifies" precondition failed in run 3 (the control itself answered `EXECUTABLE_HASH_MISMATCH`, i.e. correctly) | rehash the wrapper | run 4: check PASS; offline `revalidate` of the wrapper record OK | n/a |
| T-D1 | test design | `test_worker_service.py`, `test_worker_process.py` | tests assumed a new turn in a session with a dropped `approval_required` turn; frozen server answers `TURN_CAPACITY` | tests pin the frozen rule and continue in a new session | same tests | n/a (frozen behaviour, documented) |
| T-D2 | test design | `test_selfaudit.py` binary swap | a copied interpreter cannot report its version from a temp dir (skip) | `.cmd` shim mirroring the real npm shim | same test (no skip) | n/a |

Adversarial probes and where each is pinned (all `COMPLETED_WITH_RESULT` in the runs above):
forged ticket (2B authority tests; schema refusal at the worker: `test_forged_ticket_handed_to_the_worker_is_a_schema_violation`);
modified intent after confirmation (frozen guards + `test_rogue_ui_editing_the_approval_envelope_cannot_change_what_runs`);
modified approval digest (`..._approval_digest_is_refused_by_the_server`, `test_wrong_approval_digest_drops_the_pending_turn...`);
provider swap (`test_provider_swap_inside_the_pending_record...`, 2C swap tests + REAL `codex_swap.json`); model swap
(`test_model_pin_refuses_an_unqualified_model_before_any_task`, `test_model_outside_the_qualified_set...`, REAL check
`unqualified_model_offered_by_policy`); executable swap (`test_executable_replaced_after_qualification...`, `test_replaced_executable_invalidates`,
REAL check `binary_swap_invalidates`); stale qualification (version/hash/record-digest tests; REAL `tampered_record_invalidated`);
stale session (`test_stale_session_resume_failure...`); cross-task session reuse (`test_session_from_another_task_is_never_reused`);
revoked authority (`test_revoked_authority_blocks_the_resume`); cancelled task (`test_cancel.py`, `test_declined_and_cancelled_turns...`);
duplicate submit (`test_duplicate_submit_of_a_verified_intent...`, `DUPLICATE_OPERATION` replay in 2B/2C and REAL check);
duplicate resume (`test_completed_task_is_never_readmitted_or_resumed`, `test_supervisor_restart_never_resumes_a_leftover_session`);
crash between admission and spawn / mid-stream / after COMPLETE before settlement (2B restart suite, 11 points; 2D abrupt-termination,
8 points; REAL `codex_crash1.json`); corrupted persisted state (`test_corrupted_ledger_refuses_the_bridge...`, `test_corrupted_qualification_record_runs_nothing`,
corrupt policy file); retry exhaustion (`test_stale_session_with_exhausted_budget_fails_closed`, REAL `codex_badmodel1.json`);
unqualified provider (`test_unqualified_provider_offered_by_policy_fails_closed...`); unavailable Claude CLI (REAL `claude_composition1.json`);
permission expansion (frozen scope + `test_ui_cannot_smuggle_authority_into_a_frame`); client/UI becoming authority (same + frame
schema; UI never receives a ticket).

## L. Remaining USER INTERACTION REQUIRED items

1. Claude Code native login (`claude` / `claude setup-token`), then the qualification procedure in G.
2. A human approval click on the physical UI against the supervised worker (the frames are identical; only the finger is missing).
3. Native CLI login inside the URI client profile (`codex login` with `HOME=<client_root>\home`) for real execution inside the
   worker-process profile; forwarding the global `CODEX_HOME` was not done (C7 stop condition: shared client authentication).
4. Physical power-loss test on a throwaway VM (plan in `PHASE2A_POWER_LOSS_TEST_PLAN.md`).
5. Owner decisions: F-C1 Codex-side thread persistence (kept) vs `--ephemeral`; cutover authorization (C7 gate 10).

## M. NOT IMPLEMENTED / NOT VERIFIED

* NOT IMPLEMENTED: Task Compiler (design only, by plan); mid-run cancel frame over the single-threaded worker protocol
  (bridge-level cancel exists); UI connection to the supervised worker (cutover); executable pin beyond the npm shim;
  local-model executors; Strata.
* NOT VERIFIED: physical power loss / write reordering; real Codex execution inside the worker-process profile (needs
  client-profile login); Claude native path; natural (non-induced) Codex interruption + resume (Phase 2C limit).
* Production integration: NOT complete (frozen launchers unchanged). Cutover: did NOT occur.

## N. Closure candidate

`C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2d-candidate-20261007.zip`, cut by `scripts/phase2d_checkpoint.py`
OUTSIDE the tree: 90 tree files (Phase 2A + 2B + 2C + 2D packages, tests, scripts, reports; `__pycache__`/ledgers excluded)
+ 25 evidence files (`evidence/phase2d/`: four REAL Codex run records, the Claude fail-closed record, raw probe streams, every
test log) + `MANIFEST.json` (per-file SHA-256), `GIT_HEAD.txt`, `GIT_STATUS.txt`. Base `e8e3b65`, HEAD
`e8e3b65259c45fc823addc3ef8969425a265bd1b`. The SHA-256 of the zip is in the sidecar `phase2d-candidate-20261007.json`
(a zip cannot contain its own hash; the copy of this report inside the zip predates the hash line appended below). The
Phase 2C candidate `phase2c-candidate-20261007.zip` (`4e812653...1840f71`, re-verified with `certutil` after the cut) is
untouched and remains the previous checkpoint.
Changed relative to the Phase 2C candidate: `uri_supervisor/supervisor.py`, `uri_supervisor_bridge/bridge.py`,
`tests/phase2a/test_frozen_core.py` (edited); `uri_supervisor_bridge/{qualification,composition,worker_service}.py`,
`scripts/run_uri_supervised_worker.py`, `scripts/run_uri_phase2_server.py`, `scripts/phase2d_*`, `tests/phase2d/`,
`docs/architecture/PHASE2D_COMPOSITION.md`, `docs/plans/PHASE2D_REPORT.md` (new). Tracked git modifications: the same 11
Phase 1 overlay files as before; none added by this slice. Skipped tests: 2 (opt-in live executors, `URI_PHASE2A_LIVE=1`) in
the Phase 2 suites; 12 in the Phase 1 suite (baseline). Status: CLOSURE CANDIDATE, NOT FROZEN, NOT CUT OVER.

## O. Recommendation

**READY FOR INDEPENDENT FINAL REVIEW. NOT READY TO FREEZE.**

Why not freeze: (1) physical power-loss qualification NOT EXECUTED (the Phase 2B report named it a freeze blocker; only the
owner can waive it for this milestone); (2) real native execution inside the worker-process profile needs the client-profile
CLI login (USER INTERACTION REQUIRED); (3) the human approval click on the real UI and the UI-to-supervised-worker connection
are owner/cutover items; (4) Claude Code remains NOT NATIVE QUALIFIED. Everything else in the Phase 2 plan is implemented,
tested, self-audited (two defects repaired: D-D1 product, H-D1/H-D2 harness), regression-clean against the known baseline,
and captured in an immutable candidate. Production integration: NOT complete (frozen launchers unchanged). Cutover: did NOT occur.


SHA-256 of `phase2d-candidate-20261007.zip` (appended after the cut; recomputed with `certutil`, matches the sidecar):
`6c7cb4f87d82d45c97bdea2bf16c439f9ffe327dfa5591417af15d055d3c6785` (118 zip entries: 90 tree + 25 evidence + MANIFEST/GIT_HEAD/GIT_STATUS).

## Correction record (appended after independent review round 1; earlier text above is kept unchanged as history)

The independent reviewer (Codex CLI, gpt-6-sol) rejected candidate `6c7cb4f8...3c6785`
(`evidence\phase2d_review\CODEX_REVIEW_round1.md`). Corrections to statements in this report:

1. Sections B/E/G call the Codex record "NATIVE QUALIFIED". That record (schema v1) was forgeable by recomputing an unkeyed
   digest, did not re-read its evidence, was not bound to a client, and pinned only the npm shim. Those statements were
   overstated. Repairs: `docs/plans/PHASE2D_REVIEW_REPAIR_ROUND1.md` (schema v2).
2. Section O said "Everything else in the Phase 2 plan is implemented". Incorrect: the actual URI Flutter UI is NOT wired to the
   supervised worker, mid-run cancellation over the worker protocol is NOT implemented, and the UI/operations work is open.
   Precise status: worker protocol implemented; composition path tested (in-process and real processes, programmatic
   approval); opt-in Phase 2 worker/server profiles implemented; actual URI UI wiring NOT implemented; production cutover NOT
   performed.
3. Section B "Worker/UI composition + human approval path: IMPLEMENTED, TESTED" is narrowed to "worker-side composition
   IMPLEMENTED/TESTED; UI side NOT IMPLEMENTED".
4. Section N: this report file was modified (hash line appended) after the candidate was cut, so the candidate MANIFEST did not
   match the live tree for this file. Procedure changed: hashes go only to sidecars.
