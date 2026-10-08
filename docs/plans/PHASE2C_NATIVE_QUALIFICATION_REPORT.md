# URI Phase 2C: native executor qualification through the governed chain, slice report

Date 2026-10-07. Author: Claude (implementer and self-auditor; NOT an independent audit). Worktree
`C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent`, detached at `e8e3b65`, everything uncommitted. Nothing was committed,
pushed, merged, cut over or activated; no login or re-authentication was performed; no credential file was read, copied or
forwarded; no configuration file was changed; the frozen Phase 1 checkpoint was not touched; the production launcher and
worker still compose the Phase 1 `TurnService` with nothing qualified.

Labels: IMPLEMENTED / TESTED (automated test `COMPLETED_WITH_RESULT`) / NATIVE QUALIFIED (real installed executor ran the
full governed chain to ledger COMPLETE and a verified bridge receipt) / INTEGRATED / FROZEN / CUT OVER. REAL = the installed
CLI executed; SYNTHETIC = the fake NDJSON harness; INDUCED = a real executor interrupted by a harness-injected supervisor
timeout or crash point. Every real run record is a JSON file under `evidence\phase2c\` (paths below are relative to
`C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2c\`).

## A. Starting checkpoint

`C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2b-candidate-20261007.zip`, SHA-256 recomputed with `certutil`:
`55ed7f98d2fe2298dac6174e42c2469aa362565142e945e3fc2de69107fba972` (matches the brief and the sidecar). Read first:
`PHASE2B_REPORT.md`, `PHASE2B_INTEGRATION_BOUNDARY.md`, `PHASE2A_ARCHITECTURE.md`, `PHASE2A_REPORT.md`, the Phase 1
`harness.py` registry, `paired_coordinator.py` (approval, ticket, claim, settle), `client_execution_control.py`,
`turn_runner.py`. Baseline before any change: `tests/phase2b` 93 passed (`phase2b_baseline_before.log`).

## B. Authentication / configuration state observed (no credentials read)

| Item | Observation | Source |
|---|---|---|
| Codex CLI | `codex-cli 0.158.0`, resolved by `shutil.which` to the npm shim `C:\Users\cheta\AppData\Roaming\npm\codex.CMD` | `probe_codex_cli.json` |
| Codex auth | WORKS. A direct `codex exec --json --ephemeral --sandbox read-only -m gpt-6-sol` answered `OK`, exit 0, `turn.completed` | `probe_codex_cli/stdout.ndjson` |
| Codex default model | the account's configured default `gpt-6.1-sol` is rejected server-side: `The 'gpt-6.1-sol' model is not supported when using Codex with a ChatGPT account` (HTTP 400, after a successful authenticated request) | scratch probe `codex_direct.ndjson`; `codex_badmodel1.json` |
| Claude Code | `2.1.287`; `claude auth status` -> `loggedIn: false, authMethod: none`; every `-p` call ends `result{subtype:"success", is_error:true, result:"Failed to authenticate: OAuth session expired and could not be refreshed"}` in about 1 s | `probe_claude_code.json`, `claude_run1.json` |
| Credential files | NOT inspected. The session's auto-mode classifier refused the one command that would have listed `~/.codex`/`~/.claude` contents and keys; I did not retry by other means. Conclusions rest on CLI behaviour only. | this report |
| Environment forwarded by URI to executors | `COMSPEC, HOME, PATH, PATHEXT, SHELL, SYSTEMDRIVE, SYSTEMROOT, TEMP, TERM, TMP, USERNAME, USERPROFILE, WINDIR` (13 keys; `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` never; `CODEX_HOME`/`CODEX_API_KEY`/`CLAUDE_CODE_OAUTH_TOKEN` only if set, none was) | `probe_*.json: forwarded_env_keys` |

### Diagnosis of the two previous failures

* **Codex "configured model rejected"**: NOT an authentication failure and NOT a URI adapter defect. The CLI authenticates and
  reaches the API; the account's default model is unsupported for ChatGPT-account Codex. Phase 2A/2B ran without a model
  argument, so the default applied. The Phase 1/2 chain already carries the user's explicit model (`reasoning.model` ->
  `-m`), so an explicit, supported model is an invocation parameter of the governed path, not a configuration repair.
* **Claude "OAuth/session expiry"**: GENUINE for the standalone `claude` CLI on this machine. Identical result with the full
  user environment and with the URI-filtered environment, with and without `--setting-sources ""`, with `--output-format
  json` and `stream-json`; `claude auth status` confirms no login. Not caused by URI adapter assumptions, invocation
  parameters or environment filtering. The Claude Code *desktop* session that ran this slice authenticates separately; its
  session is not available to, and was not extracted for, the CLI.

## C. Codex CLI: direct and URI-path results

| Surface | Status | Evidence |
|---|---|---|
| DIRECT CLI STATUS | **OK** (explicit `-m gpt-6-sol`; default model rejected) | `probe_codex_cli.json`, `probe_codex_cli/stdout.ndjson` sha `c8da4f84...` |
| URI ADAPTER STATUS | **USABLE** in the qualification composition: Phase 1 `HarnessRegistry` row `installed, AUTHENTICATED, NATIVE_QUALIFIED, usable=True` (run-scoped: auth evidence = the direct probe observed by the same process; `qualify(NATIVE_QUALIFIED, sha256(probe file))`). The production worker is unchanged (`default_registry()`, nothing qualified). | `codex_run2_final.json: registry_discover` |
| BRIDGE / SUPERVISOR STATUS | **COMPLETE** through `SupervisedTurnRunner -> verify_authority -> SupervisorBridge -> admit_next(only_task_id) -> run_attempt (job-contained real `codex.CMD`) -> reconcile` | `codex_run1.json`, `codex_run2_final.json` |
| LEDGER TERMINAL STATE | **COMPLETE**, reason `POSTCONDITIONS_VERIFIED`, completion record `verified` citing `uri_verified postcondition_check` | same |
| VERIFIED RECEIPT STATUS | **verified**: receipt evidence `basis=uri_supervisor_postcondition_verified`, `supervisor_task == operation_id`, output sha `95784973cc639977bff93619700168505cb8f7855e44fa643d34622a43706c87` (4 bytes, `PONG`); server `SETTLED_VERIFIED`, turn `reply`, `execution_outcome=verified` | same |

Task used (every real run): text `use the harness to write the single word PONG into pong.txt`; Intent Discovery compiled
`{instruction: "write the single word PONG into pong.txt", expected_file: "pong.txt"}`; approval request shown with that
argument set and the confirmed-intent digest; the approval decision was supplied by the qualification harness (programmatic
`approve -> True`), the ticket is REAL (server-signed, Ed25519, generation-bound). The executor wrote one 4-byte file into a
fresh URI-owned run directory under `work\c1\p2c_*\client\workspace\<run_id>\` (git-ignored); no repository or project
file was modified (`test_frozen_core.py` passes). Codex did so with one PowerShell `command_execution` inside its
`workspace-write` sandbox (tool activity recorded as `executor_report/tool_result`).

## D. Claude Code: direct and URI-path results

| Surface | Status | Evidence |
|---|---|---|
| DIRECT CLI STATUS | **BLOCKED — USER INTERACTION REQUIRED** (`loggedIn:false`; `Failed to authenticate: OAuth session expired and could not be refreshed`). Remedy is an interactive `claude` login or `claude setup-token` (browser), out of scope. | `probe_claude_code.json` |
| URI ADAPTER STATUS | **NOT USABLE**, honestly: registry row `installed, NOT_AUTHENTICATED, NATIVE_UNQUALIFIED, usable=False`; no qualification was recorded | `claude_run1.json: registry_discover` |
| BRIDGE / SUPERVISOR STATUS | **REFUSED BEFORE ANY TASK**: `NOT_STARTED:HARNESS_HARNESS_NOT_USABLE`; zero ledger tasks; no process spawned | `claude_run1.json` |
| LEDGER TERMINAL STATE | none (no task created) | same |
| VERIFIED RECEIPT STATUS | receipt `failed`, `NOT_STARTED:...`; server `SETTLED_FAILED`, `execution_closed=True` (frozen rule: a NOT_STARTED refusal closes the turn) | same |

Claude Code is **NOT NATIVE QUALIFIED**. Nothing in Phase 2 was weakened to change that.

## E. Configuration repairs

**None.** No file under `~/.codex` or `~/.claude` was read or written. The Codex model problem is handled by the governed
path's existing explicit-model parameter; the qualification policy rows include `("client_external_harness", "codex_cli",
"gpt-6-sol")`. For production, the same row must be an explicit composition decision (`ReasoningSelectionPolicy`), not a
change to the user's Codex configuration. Nothing was changed "to make a test pass".

## F. Real successful execution evidence (REAL executor, REAL chain)

`codex_run2_final.json` (final code, executable pinned) and `codex_run1.json` (pre-pin code):

* server calls in order: `POST /client/v1/turns` -> `/approval` -> `/claim` -> `/settle`; approval before claim before settle.
* ledger: task `COMPLETE`, 1 attempt, `admission.auth_id=1`, authorization row 1 `issued_by=uri_core.execution_ticket`,
  `valid_from=issued_at`, `valid_until=deadline`, scope `allowed_executors=["codex_cli"]`, `allowed_op_classes=[read,
  local_write]`, workspace = the run directory, ticket/approval/argument digests; superseded at settlement by row 2
  `issued_by=uri_supervisor_bridge` with an empty validity window.
* attempt: `executor_version 0.158.0`, `pid` + creation time + named job (`Local\uri-sup-<ledger>-1-<nonce>`), `exit_code 0`,
  `end_reason exited_after_terminal_success_claim`, `session_id` = Codex `thread_id`; `argv_sha256` equals the SHA-256 of
  `CODEX_CLI.build_argv(workspace, model="gpt-6-sol", resolved_executable=<codex.CMD>)` (recomputed independently for every
  attempt of every real run: all match, `-m gpt-6-sol` present).
* raw stream persisted first (7 stdout lines: `thread.started`, `turn.started`, `agent_message`, `command_execution`
  started/completed, `agent_message`, `turn.completed` with usage), interpreted into `session`, `agent_message`,
  `tool_result`, `terminal_success_claim`; `fence_current=1` on every line.
* URI evidence: `uri_observed/process_identity` (DEAD_CONFIRMED), `uri_verified/postcondition_check` PASS
  (`file_regular_nonempty` on `<run>/pong.txt`); completion record `verified`; one copied-out result file (4 bytes `PONG`).
* receipt evidence (as sent to `/settle`): `check=harness_output_check`, `verifier_id=uri.client.harness_output_check.v1`,
  `matched=True`, `basis=uri_supervisor_postcondition_verified`, `supervisor_task/attempt/decision/ledger_id` cited.

## G. Real resume / retry evidence

| Claim | Status | Evidence |
|---|---|---|
| **REAL RESUME DEMONSTRATED (Codex, INDUCED interruption)** | yes | `codex_resume1.json`: attempt 1 killed by a harness-injected 4 s supervisor timeout after `thread.started` (`exit 1`, `timeout_killed`, no terminal event, no file; `uri_verified/effect_absent`, fingerprints equal) -> decision `RETRY_SAFE / RESUME_SESSION / EXECUTOR_INTERRUPTED_NO_TERMINAL_EVENT_RETRY_SAFE` -> attempt 2 `resume_of=1`, argv = `codex exec resume <thread_id> --json --skip-git-repo-check -c approval_policy="never" -c sandbox_mode="workspace-write" -m gpt-6-sol -` (sha recomputed and matched), Codex re-emitted the SAME `thread_id`, wrote `pong.txt`, `turn.completed`, exit 0 -> `COMPLETE`; both admissions under `auth_id=1`; final `SETTLED_VERIFIED`. The interruption is INDUCED (not a natural failure); the executor, the resume command and the resumed thread are REAL. |
| **RETRY DEMONSTRATED (Codex, REAL failure)** | yes | `codex_badmodel1.json`: model `gpt-6.1-sol` (rejected by the account) -> attempt 1 `turn.failed` + `error` (`terminal_error_claim`, `warning` for the metadata notice), exit 1, absence proven -> `RETRY_SAFE / RETRY_FRESH` (a terminal claim is not an interruption, so no resume) -> attempt 2 same `auth_id=1`, same failure -> `FAILED / RETRY_BUDGET_EXHAUSTED` -> bridge `failed SUPERVISOR_FAILED:RETRY_BUDGET_EXHAUSTED` -> frozen server: dispatched + failed = `SETTLED_EXECUTION_UNCERTAIN` (Phase 1 rule), `execution_reported=failed`. No new authority at any point. |
| Claude resume / retry | **SYNTHETIC ONLY** (Phase 2B fake harness); real: BLOCKED (auth) | `tests/phase2b`, `tests/phase2c/test_resume_mode.py` |

Enabling the Codex resume needed one Phase 2A data-model addition: `ExecutorSpec.resume_mode = "append" | "replace"`
(`codex exec resume <id>` is a different subcommand grammar, and `exec resume` has no `--sandbox`/`-C` flags, so the sandbox
is a config override and the cwd is the supervised workspace, which `run_attempt` already checks against the authorization
scope). Claude keeps `append` (`--resume <id>`). Session ids are validated before either mode builds argv.

## H. Authority and adversarial results (real path)

Post-run checks executed against the REAL ticket of each successful run with no further executor call
(`authority_checks` in `codex_run1.json`, `codex_resume1.json`, `codex_badmodel1.json`, `codex_run2_final.json`); the
selection swap is its own real-server run (`codex_swap.json`).

| Requirement | Result | How |
|---|---|---|
| Only the executor named by the ticket's selection can run | PASS | ledger scope `allowed_executors=[codex_cli]`; registry `selectable(provider)`; D-B3 same-file check; new D-C2 hash pin; `codex_swap`: begin under Codex, decide under Claude -> `NOT_STARTED:AUTHORITY_SELECTION_MISMATCH`, zero tasks, zero processes |
| Changing provider invalidates/refuses authority | PASS after repair **D-C1** | the frozen ticket does NOT bind the selection (`provider_change_at_ticket_level: ACCEPTED` by `verify_authority`); the runner now binds `digest(reasoning)` at `begin` and refuses a different one at `_run_harness` (real swap run + 6 synthetic tests) |
| Changing task arguments invalidates authority | PASS | `ARGUMENT_DIGEST_MISMATCH` on the real ticket |
| Changing confirmed-intent binding invalidates authority | PASS | `APPROVAL_DIGEST_MISMATCH` on the real ticket |
| Replay of the same operation is rejected | PASS | `bridge.execute(same work)` -> `execution_uncertain / DUPLICATE_OPERATION`, attempt count unchanged (4 real runs) |
| Completion closes authority | PASS | latest authorization row `valid_until_us <= now`, `issued_by uri_supervisor_bridge` |
| Failed / retry-safe execution does not manufacture authority | PASS | `codex_badmodel1`: two attempts, one `auth_id`; after FAILED the authority is closed |
| Restart does not revive revoked authority | PASS | fresh `SupervisorBridge` on the same root: empty startup report, state unchanged, zero open authorizations, no launch (4 runs); `codex_crash1`: RETRY_SAFE leftover -> `FAILED AUTHORITY_REVOKED_RESTART` |
| Executor output cannot declare itself verified | PASS | Codex `agent_message` "Wrote `PONG` ..." is `executor_report` only; `verified` derived from `uri_verified postcondition_check`; completion basis cites the postcondition, not the claim (Phase 2A rules + Phase 2B tests) |
| Only ledger COMPLETE can produce a verified receipt | PASS | `_settle` returns `verified` only on `state == COMPLETE`; `codex_badmodel1` (FAILED) produced `failed`; receipt evidence `basis=uri_supervisor_postcondition_verified`; `_verify_receipt` (frozen server) requires matching check/verifier/argument digest |

Adversarial review of the real path (code + evidence; items without a dedicated new test cite the existing one):

| Threat | Finding |
|---|---|
| Executable substitution | path identity (D-B3) holds; **observed weakness**: `which("codex")` resolves to the npm shim `codex.CMD`, so a same-path replacement or a PATH-order shim would pass D-B3. Repaired in part by **D-C2**: optional `ExecutorBinding.executable_sha256` pin, refused `EXECUTOR_BINARY_HASH_MISMATCH` before any task (3 tests); the qualification harness pins the probed file. Limit: pins the shim, not node or the package it starts. |
| Model/config substitution | the model reaches argv only from the bound reasoning selection (`fullmatch` pattern, `-m <model>`); recomputed argv hashes match for every real attempt; a model rejected by the account fails closed (`codex_badmodel1`) |
| Environment-variable leakage | 13 allow-listed keys forwarded, never `OPENAI_API_KEY`/`ANTHROPIC_API_KEY`; fixture prefix `URI_FAKE_` is forwarded by design (tests); `URI_ATTEMPT_FENCE`/`URI_TASK_ID` added |
| Argument injection | instruction only on stdin (`-` positional); `expected_file` bare-safe-name `fullmatch`; workspace path from the bridge, not from arguments |
| Session-id injection | `valid_session_id` before either resume mode; `replace` mode refuses `--yolo`, embedded bypass flags, spaces, `-m evil`, `../x` (parametrised test) |
| Provider substitution | D-C1 (above) |
| Misleading success events | Codex `item.completed{type:error}` is `warning`; `turn.failed` is `terminal_error_claim`; Claude `result{subtype:success,is_error:true}` is an error claim (Phase 2A fixtures) |
| Non-zero exit with success-shaped stream | Phase 2A D3 + Phase 2B `done_ok_exit3`; real attempt 1 of `codex_resume1` (exit 1, no terminal) was not completed |
| Partial output followed by failure | Phase 2B `partial_then_die` -> NEEDS_USER; real path: absence proofs by fingerprint worked on every interrupted/failed attempt |
| Duplicate effects | `task_id == operation_id` (UNIQUE), `DUPLICATE_OPERATION` on real replay; one result file per verified run |
| Retry authority widening | same `auth_id` across attempts in both multi-attempt real runs |
| Stale authorization | restart revocation on real crash; `generation_change -> TICKET_REFUSED`; `after_deadline -> TICKET_REFUSED` |
| Receipt forgery | receipt evidence is built by the bridge from ledger rows; frozen server `_verify_receipt` checks check/verifier/argument digest/matched; a client cannot settle `verified` for a different operation (`RECEIPT_SCOPE`) |
| Executor claiming COMPLETE without ledger COMPLETE | structural (`_settle`), plus Phase 2B false-claim tests |

Additional observations (not defects, recorded for the user's judgement):

* **Codex session persistence (F-C1).** The Phase 2A Codex spec deliberately omits `--ephemeral` so a thread can be
  resumed. Consequence: every governed Codex attempt leaves a thread (instruction text, workspace path, tool output) in the
  user's own Codex session store outside URI's ledger. Six such threads were created by this slice (ids in the run
  records). Resume capability and no-persistence are mutually exclusive on Codex 0.158.0; this is a product decision.
* **Restart abandons a resumable thread (F-C2).** After the real crash, recovery decided `RESUME_SESSION` but the bridge's
  restart rule revoked authority and failed the task. Correct per Phase 2B ("restart never relaunches"); the user needs a new
  ticket. Worth stating in UI copy later.
* **NOT_STARTED closes a turn with `dispatched=True`** (frozen Phase 1 behaviour): `codex_swap` and `claude_run1` show
  `dispatched: True, execution_outcome: failed, execution_closed: True`. Consistent with the Phase 1 rule that only the
  client's own pre-launch refusal may close after dispatch; noted because the record looks contradictory at first glance.

## I. Crash / restart results (REAL executor, INDUCED crash)

`codex_crash1.json`: a child process ran the full stack with `URI_SUPERVISOR_CRASH_AT=mid_stream`; the supervisor died
(`os._exit(137)`, 3.5 s in) right after persisting Codex's first stdout line (`thread.started`), while the real Codex process
(pid 6528) was running. Before restart: the ledger showed task RUNNING, attempt RUNNING with pid/creation time/job name;
`psutil` found **no** process with that identity (the named kill-on-close job took the real executor down with the
supervisor). Restart (fresh `SupervisorBridge`, 0.01 s): recovery fenced the attempt, confirmed the process DEAD, observed
the postcondition absent, proved the effect absent by fingerprint, decided `RETRY_SAFE / RESUME_SESSION`; the bridge then
revoked the authorization and failed the task `AUTHORITY_REVOKED_RESTART`; zero open authorizations; nothing relaunched;
`before_restart.executor_processes_alive == []`.

Power loss / OS write reordering: **NOT EXECUTED** (no throwaway VM available without user interaction; plan unchanged in
`PHASE2A_POWER_LOSS_TEST_PLAN.md`). Machine restart was not performed (user away).

## J. Synthetic vs real, kept apart

| REAL | INDUCED (real executor, harness-injected interruption) | SYNTHETIC |
|---|---|---|
| direct Codex probe; `codex_run1`, `codex_run2_final` (success chain); `codex_badmodel1` (real failure, real retry); `codex_swap` (real server refusal, no executor); `claude_run1` (real auth failure, real registry refusal); all authority checks on real tickets; argv hash recomputation; executable hash pin on the real shim | `codex_resume1` (4 s timeout on attempt 1); `codex_crash1` (`os._exit` at `mid_stream`) | `tests/phase2b` (93) and `tests/phase2c` (22): fake NDJSON harness; D-C1 regression through the real paired server; `replace`-mode resume with a `-c` Python executor; binary pin tests |

The approval decision in every real run came from the qualification harness, not from a human on the UI. The ticket,
server, client persistence, DPAPI credentials, supervisor, ledger, job containment and executor are real.

## K. Regression results vs known baseline

| Run | Result | Baseline comparison |
|---|---|---|
| `tests/phase2b` before any change | 93 passed | = Phase 2B report |
| `tests/phase2c` (new) | 22 passed (`phase2c_tests_run3.log`) | two test-authoring bugs fixed in run 1/2 (a name typo; `""` is "no session", not an id) |
| `tests/phase2a` + `tests/phase2b` on final code | 261 passed, 2 skipped (`phase2a_phase2b_after_slice.log`); frozen-core 8 included | identical counts to Phase 2B (168 + 93) |
| all Phase 2 suites on final code | 283 passed, 2 skipped (`phase2_all_final.log`) | 261 + 22 |
| Phase 1 authority suites (`-I`) | 134 passed (`phase1_authority_after_slice.log`) | identical |
| Phase 1 full repository suite (`-I`, excludes `tests/phase2*`) | see `phase1_full_after_slice.log`; summary in section K-1 below | Phase 2B: 2674 passed, 12 skipped, 12 failed (11 known IDs + 1 environmental) |

### K-1. Full suite outcome

Two attempts of the Phase 2B command (`python -I -m pytest -q --ignore=tests/phase2a --ignore=tests/phase2b
--ignore=tests/phase2c`) never left collection: the first ran 3 h 20 min with no output and was killed, the second was
killed after 4 min at `collecting ...` (`phase1_full_after_slice_HUNG_run1.log`, `..._HUNG_run2.log`). Diagnosis
(`collect_bisect.log`): every root test module collects alone in 0-14 s; the hang is pytest's recursive collection of
`work\c1
ollback_*` (Phase 1 rollback-test residue: 3,096 `.py` files, 11 `test_*.py`, nested `tests/` trees, 334 MB)
left by the `test_c7_rollback_boundary` run earlier in this slice. `work/` is git-ignored runtime state, not source. With
`--ignore=work` collection takes 23 s and yields exactly the baseline 2,698 tests. Classified ENVIRONMENTAL (collection
residue), not a code result; the Phase 2B baseline run did not have these directories present at collection time.

Final run (`--ignore=work` added, otherwise the Phase 2B command): **2675 passed, 12 skipped, 11 failed, 867 s** (`phase1_full_after_slice.log`). The eleven failures are exactly
the eleven known baseline IDs (`step3_test::test_drive`, `step4_test::test_download`, `test_capability_directory` privacy,
`test_m20_feasibility_validation`, 2x `test_m20_recovery_loop`, 2x `test_m20_semantic_interpreter_resilience`,
`test_orchestrator_session_workflow`, `test_usage_import_boundary`, `test_workflow_restart_recovery`). The Phase 2B
environmental twelfth (`test_c1_source_pin`, concurrent importer) did not recur because nothing else imported the tree during
this run; passed count is therefore 2674 + 1. No new failure; no Core file changed in this slice.

## L. Defects discovered and repairs

| ID | Severity | Where | Root cause | Repair | Regression test | Failed before repair? |
|---|---|---|---|---|---|---|
| D-C1 | High (provider/model substitution after approval) | `uri_supervisor_bridge/runner.py` | the frozen ticket binds turn/op/capability/args/intent, not the reasoning selection; the server stores the selection only in memory and never re-checks it at claim/settle; the client's `_run_harness` used whatever `reasoning` the caller passed at `decide` | `SupervisedTurnRunner.begin` records `digest(reasoning)` per approval_required turn; `_run_harness` pops and compares, refusing `NOT_STARTED:AUTHORITY_SELECTION_MISMATCH` before registry/executor; `continue_waiting` re-binds via its fresh `begin` | `tests/phase2c/test_selection_binding.py` (6), real `codex_swap.json` | Not executed on pre-repair code (the repair was written before the swap run). Inferred from two observed facts: `verify_authority` ACCEPTS a changed provider on the real ticket (`provider_change_at_ticket_level: ACCEPTED`), and the frozen `_run_harness`/bridge take `reasoning` from the `decide` call. The swap test fails if the `begin` binding is removed (checked by reading the refusal path, not by a recorded run). |
| D-C2 | Medium (hardening: executable identity) | `uri_supervisor_bridge/bridge.py` | D-B3 compares resolved paths; the real resolution is an npm `.CMD` shim | optional `ExecutorBinding.executable_sha256`; mismatch -> `NOT_STARTED:EXECUTOR_BINARY_HASH_MISMATCH` before any task | `tests/phase2c/test_binary_pin.py` (3) | n/a (missing control; the wrong-pin test fails without the check) |
| E-C1 | Enhancement (resume grammar) | `uri_supervisor/executors.py` | `resume_argv` could only be appended; Codex resumes via a different subcommand | `resume_mode` `append`/`replace`, validated session id in both, JSON round trip, Codex template | `tests/phase2c/test_resume_mode.py` (13), real `codex_resume1.json` | n/a (capability) |

Boundary test `test_bridge_runner_overrides_only_the_harness_execution_seam` now also allows `begin` (it calls the frozen
`begin` unchanged and only records a digest). `test_frozen_core.ALLOWED_NEW` gains the Phase 2C paths. No Phase 1 file
changed (frozen-core suite passes).

## M. Remaining NOT DEMONSTRATED / BLOCKED

* Claude Code native path: **BLOCKED — USER INTERACTION REQUIRED** (CLI login / setup-token in a browser).
* Codex natural (non-induced) interruption + resume: NOT DEMONSTRATED (only induced); Codex resume after a *supervisor*
  restart: by design never attempted (authority revoked).
* Power loss / OS write reordering: NOT EXECUTED.
* Human approval through the UI on the real path: NOT DEMONSTRATED (harness-supplied approval); worker/UI composition on
  the bridge: NOT INTEGRATED (`SupervisedTurnService` still unused by any launcher).
* Production policy row for `(codex_cli, gpt-6-sol)` and production `qualify()` with persisted evidence: NOT DONE (decision).
* Executable pin beyond the npm shim (node binary, package contents): NOT DONE.
* Local-model executors: unchanged (RESEARCHED, NOT IMPLEMENTED, NOT REQUIRED).

## N. Updated Phase 2 status ledger

| Slice | Status |
|---|---|
| 2A Durable Task Supervisor (`uri_supervisor`) | IMPLEMENTED, TESTED (168 + crash points), **NATIVE QUALIFIED with Codex CLI on this machine (run-scoped, 2026-10-07)** for: contained spawn, raw stream, reconciliation, resume (induced), crash recovery (induced); NOT QUALIFIED for power loss; NOT INTEGRATED; NOT FROZEN |
| 2B Core <-> Supervisor boundary (`uri_supervisor_bridge`) | IMPLEMENTED, TESTED (93 + 22), **NATIVE QUALIFIED with Codex CLI (run-scoped)**: real ticket -> real executor -> ledger COMPLETE -> verified receipt -> server `SETTLED_VERIFIED`; NOT INTEGRATED (no launcher); NOT FROZEN |
| Executor qualification: `codex_cli` | **NATIVE QUALIFIED (run-scoped qualification composed by the harness; production registry unchanged)** |
| Executor qualification: `claude_code` | **BLOCKED — USER INTERACTION REQUIRED**; path verified to fail closed |
| Worker/UI composition on the bridge | PLANNED (unchanged) |
| Task Compiler | DESIGN NOTE only (`PHASE2C_TASK_COMPILER_PLACEMENT.md`); NOT IMPLEMENTED |
| Power-loss qualification | PLANNED, NOT RUN |

Nothing is promoted to INTEGRATED, FROZEN or CUT OVER by this slice.

## O. Task Compiler architecture note

`docs/architecture/PHASE2C_TASK_COMPILER_PLACEMENT.md`: the compiler sits between the confirmed intent and the approval
(so the user approves the compiled package's digest), may optimise/translate/package, must not create authority, widen
permissions, change confirmed slots, select an executor or add objectives; deterministic vs model-generated fields are
tabulated; `IntentDiscovery.conflicts` is the enforcement point. Design only; no new model.

## P. Recommendation for the next slice

1. **Decide production composition** (owner decision, no code needed yet): add the policy row `(client_external_harness,
   codex_cli, gpt-6-sol)` and a persisted `qualify("codex_cli", "NATIVE_QUALIFIED", <evidence sha>)` fed by a stored probe
   record, or keep harnesses off. Decide F-C1 (Codex session persistence vs resume).
2. **Worker/UI composition slice**: switch one explicit launcher profile to `SupervisedTurnService` with a human approval on
   the real path (the only UNDEMONSTRATED part of the chain); keep the Phase 1 worker as the default until cutover.
3. Unblock Claude Code only by the owner's interactive login; then rerun `scripts/phase2c_native_qualification.py
   --provider claude_code` (the harness is ready; expected first finding: Claude's `--resume` through `append` mode).
4. Power-loss plan on a throwaway VM when one exists.
5. Task Compiler stays design-only until 1-2 are done.

## Q. New checkpoint

`C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2c-candidate-20261007.zip`
SHA-256 `4e8126539da1f0ede3989f6d307253b5b4267be4fe1ce4ae405d19e761840f71` (recomputed with `certutil`, matches the sidecar
`phase2c-candidate-20261007.json`). 68 tree files (Phase 2A + 2B + 2C packages, tests, reports, scripts) + 30 evidence files
(`evidence/phase2c/`: run records, probe streams, test logs, hung-run logs, bisect log) + `MANIFEST.json` (per-file SHA-256),
`GIT_HEAD.txt`, `GIT_STATUS.txt`; base `e8e3b65`; cut by `scripts/phase2c_checkpoint.py`. The copy of this report inside the
zip predates this section Q (a zip cannot contain its own hash); the sidecar is authoritative. Frozen-core suite re-run after the
last edit: 8 passed. Git: the same 11 tracked Phase 1 overlay modifications as before the slice; no frozen file changed.
Status: CANDIDATE, NOT FROZEN. Phase 2B checkpoint `55ed7f98...` remains the previous checkpoint.
