# URI Phase 1 Core: fourth review (independent final acceptance audit)

Date: 2026-10-05. Reviewer: Claude, a fresh session with no access to the implementing or earlier reviewing sessions' reasoning. Worktree: `C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent`, detached at `e8e3b65`. **Every change is uncommitted.** Nothing was committed, pushed, merged, cut over, logged in, deleted from historical worktrees, or activated in the launched server (the launched composition still carries `model_policy: lazy-not-selected` and composes only the deterministic row).

All previous reports, repairs and passing tests were treated as claims. Every verdict below rests on code read in full plus an attack or run I executed myself in this session.

## Acceptance criteria (set before reviewing)

1. The reviewed tree is exactly the candidate checkpoint, proven by archive hash and per-file comparison.
2. Each R1–R16 and N1–N5 verdict is based on the code and on an independent attack, not on the regression test alone.
3. Any defect is reproduced before repair, repaired at the narrowest layer, covered by a regression test, and the affected validation plus the Phase 1 gates are re-run.
4. No gate is weakened; a fixture or test changes only when the contract it encodes is deliberately tightened, and that change is listed.
5. The 11 pre-existing full-suite failures are confirmed on a pristine `git archive e8e3b65` export that I made myself, by full-suite failure-ID set comparison.
6. Live validation uses the real launcher, real server process and real restarts.

## 1. Checkpoint reviewed

`work/c1/checkpoints/review3-final-20261005-174139.zip`, sha256 `480ae22f21064e437a35b38b4d83fcbc28f550867642664d306f88527f8a5412` (recomputed). 116 files plus `GIT_HEAD.txt`/`GIT_DIFF.patch`. Extracted and compared byte-for-byte with the live tree: **116/116 identical**, `GIT_HEAD` = `e8e3b65259c45fc823addc3ef8969425a265bd1b`. Baseline runs on this unmodified tree: focused Phase 1 suite (the third review's 25 modules plus 5 legacy authority modules) **444 passed, 61 subtests**; full suite **2640 passed, 12 skipped, 11 failed** (identical counts to the third review).

## 2. Verdicts on R1–R16

| ID | Verdict | Independent basis |
|---|---|---|
| R1 source pinning | ACCEPTED (with N1) and **hardened (F2, provisional)** | Read `c1_bootstrap.py`, `install_source_pin`, `PinnedSourceFinder`, all four entrypoints and both `.ps1`. Under the launched flags (`-B -I`) the root is never on `sys.path`, pinned packages compile only from plain source (no `__pycache__`, no extension, no sourceless `.pyc`; module+package same name refused), each loader records the digest of the bytes it compiled, and the pin requires that recorded digest. My attack: a planted `scripts/psutil.py` (inside a pinned directory but not a pinned file). With `-B -I` it never ran. **Without `-I` (direct developer invocation) it ran before any validation.** See F2. Miscased imports, namespace portions from pywin32's `win32/scripts`, and post-validation drift were re-checked by reading and by the existing attacks, which I re-ran. |
| R2 catalogue pin | ACCEPTED | Both seeded copies validated; `PinnedCapabilityRegistry` permits nothing after drift. Residual: legacy composition's copy pinned at start only (same-user, out of scope). Also noted: `uri_core/config/modes.py` reads a cwd-relative `uri_workspace/modes.json` at every call; absent in the state root, and it can only narrow (`registry ∩ grants ∩ mode`), so it cannot widen authority. |
| R3 DPAPI | ACCEPTED | Line-by-line: `DATA_BLOB` layout, 7-argument prototypes on private `WinDLL` handles, `CRYPTPROTECT_UI_FORBIDDEN`, free-on-success only, best-effort zeroing. |
| R4 idle expiry | ACCEPTED | `_expire` keeps `executing`/`execution_uncertain` uncertain and never prunes them. Note: the first loop walks `self.live` only, so non-live non-terminal turns after a restart are never expired (ledger growth, no authority effect). |
| R5 cancel receipt | ACCEPTED | `RECEIPT_CANCEL_AFTER_DISPATCH` outside `waiting_for_model`; `RECEIPT_WITHOUT_CLAIM` for an unclaimed ticket. |
| R6 wait/settle crash | ACCEPTED | Durable `dispatched`/`execution_closed`; `/wait` limited to `PROVIDER_EXECUTED`; `cancel` keeps uncertainty and releases the session. |
| R7 replay | ACCEPTED | Ledger guards `INTENT_ALREADY_EXECUTED`, `INTENT_EXECUTION_UNCERTAIN`, `INTENT_STATE_STALE`; tombstone survives pruning. Gap found in the stale guard for abandoned/stopped intents: F3. |
| R8 graph shape | ACCEPTED | `entity_id`/`canonical_name` match `GraphNode`. |
| R9 stale referent | ACCEPTED | `_stale_references` at confirmation. |
| R10 graph confirmation | ACCEPTED | `graph:` candidates excluded from the explicit path. |
| R11 unconfirmed arguments | ACCEPTED | `compile()` is the only translation; `conflicts()` compares capability, action and exact inputs; anything unconfirmed is `REFUSED_UNCONFIRMED_ACTION`. Action names are validated against the directory at proposal time (`_validate_contract`) and again at the gate (my probe P5: `wipe_all` → `BRAIN_OUTPUT_INVALID`). |
| R12 answer relabelled | ACCEPTED | Superseding needs the schema's own extraction of the user's words. |
| R13 bare negation | ACCEPTED | |
| R14 rollback aliasing | ACCEPTED | Up-front refusal plus exact re-read of the finished tree. |
| R15 catalogue substitution | ACCEPTED (with N2) | Top-level keys, `planned_capabilities` and canonical-JSON equality all checked. Observation: a new `paired_client` entry may carry any `permissions`/`effect_type`; it still cannot execute anywhere (server dispatcher refuses the surface; paired composition executes only `qualified` ids with verifiers). |
| R16 dispatcher refusal | ACCEPTED | `execute_tool` refuses `execution_surface: paired_client` before the dynamic import; fresh-interpreter test confirms no client module loads. |

## 3. Verdicts on N1–N5

| ID | Verdict | Basis |
|---|---|---|
| N1 bootstrap gate | ACCEPTED, hardened (F2) | See R1. |
| N2 planned/top-level catalogue | ACCEPTED | See R15. |
| N3 uncertain turn and session capacity | ACCEPTED | `start()` excludes `execution_uncertain` from the active set; nothing can advance it. |
| N4 uncertain intent set aside | ACCEPTED | Plain text sets it aside and clears; only a new explicit request supersedes. |
| N5 interpreted slots | ACCEPTED | `interpreted_from_request` always requires confirmation; the interpreter is consulted only for slots the deterministic extraction left empty, and its values must occur verbatim in the user's text. Verified in the Brain live evidence for both models and in the Flutter widget test. |

## 4. New defects found (all reproduced before repair)

| ID | Severity | Defect | Violated invariant | Reproduction |
|---|---|---|---|---|
| **F1** | Material | **Quota pause after harness tool activity closed as "no effect".** In `TurnRunner._run_harness`, any `quota_exhausted` claim became a clean `/wait` + `cancelled` receipt, so the server recorded `execution_closed`/`execution_outcome: cancelled` and told the user "Nothing was changed", and `continue_waiting` re-ran the same task on another provider. The client runtime already knew the harness had requested a tool action (`claim.usage.tool_calls`). The existing fixture's `quota` scenario even emitted a `tool_use` before the quota error, so the passing test was proving the unsafe behaviour. | Execution-uncertainty invariant and the plan's "truthful quota/recovery": if execution may have started and absence of effects cannot be established, uncertainty must be preserved. Harness containment beyond the workspace is not qualified. | Probe through the real paired app with the fake harness: claim `tool_calls: 1`, server `WAITING_FOR_MODEL ... Nothing was changed.`, ledger `execution_closed: True, execution_outcome: cancelled`. |
| **F2** | Low (hardening) | The C1 import gate depended on the caller passing `-I`. Without it (direct developer invocation of any entrypoint) the script directory is `sys.path[0]` and a planted `scripts/psutil.py` ran inside the entrypoint before any validation. The launched path always passes `-I`, and `process_identity` would refuse such a listener, so this is outside the launched path. | C1: no code before verification. | `c1_flags_probe.py`: `-B -I` → planted module did not run; `-B` only → planted module ran (`ImportError: planted` from `scripts\psutil.py`). |
| **F3** | Low | Abandoning or stopping an intent did not advance its revision, so a client that replays its pre-abandon session state could re-present the abandoned request for confirmation and reach `approval_required`. Execution still required the user's digest-bound confirmation and a fresh approval, so this is not a silent path. | The stated replay guard: "a validly signed but older revision must never resurrect superseded meaning". | Probe P7: abandon, restore the pre-abandon session, confirm → `approval_required`. |

Verified sound under independent attack (no change): a `select` for a candidate never displayed (a real later session file, and a bogus id) never binds; a tampered signed intent record is `INTENT_STATE_INVALID`; forged approval digests and replayed claims are refused; a `cancelled` receipt after dispatch is refused; a failed receipt after dispatch is uncertain across a real restart.

## 5. Repairs (mine; provisional, locally validated)

| ID | Repair | Regression test (fails on the incoming code: the probes above show the old behaviour) |
|---|---|---|
| F1 | `uri_core/client_runtime/turn_runner.py`: a quota claim is a clean pause only when `claim["usage"]["tool_calls"] == 0`; otherwise the attempt is `execution_uncertain` with `QUOTA_AFTER_TOOL_ACTIVITY` (an unavailable count also fails closed). `fixtures/c4_harness/fake_harness.py`: the `quota` scenario now hits the limit before any tool request (the realistic first-call quota); a new `quota_after_tool` scenario emits a `Write` request and then the quota error. | `test_c5_loop.py::test_quota_after_tool_activity_is_uncertain_not_a_clean_pause`: `SETTLED_EXECUTION_UNCERTAIN`, attempt not closed, no checkpoint, no copy-out, `continue_waiting` impossible. The existing quota-pause and C4 quota-classification tests still pass with the no-tool scenario. |
| F2 | `scripts/c1_bootstrap.py::install`: `raise SystemExit("C1_ISOLATED_MODE_REQUIRED")` unless `sys.flags.isolated`, before the entrypoint's first import. | `test_c1_source_pin.py::test_entrypoints_refuse_without_isolated_mode_before_importing_anything`: all four entrypoints without `-I`, planted `scripts/psutil.py` never runs. |
| F3 | `uri_core/core/intent_discovery.py`: `_bump` on abandon; `_stop` advances the revision. | `test_c5_intent_adversarial.py::test_abandoned_intent_replayed_from_older_client_state_is_stale` → `INTENT_STATE_STALE`, nothing dispatched, pointer cleared. |

No gate was weakened. The only fixture change is listed above (F1) and tightens the contract.

## 6. Validation results

All runs executed by me in this session, with a synthetic `URI_EXTERNAL_CREDENTIAL_SECRET`, on the same `.venv` interpreter (Python 3.13.15).

| Run | Incoming checkpoint (unmodified) | Repaired tree |
|---|---|---|
| Focused Phase 1 suite: the third review's 25 modules plus `test_m22_3_route_authorization`, `test_m32_capability_effect_classification`, `test_modes_endpoints_isolation`, `test_capability_registry`, `test_workflow_continuation` | **444 passed**, 61 subtests | **447 passed**, 61 subtests (the 3 new regressions) |
| `validate_c1_regression.py` | (not re-run before repairs) | 303 passed, 29 subtests |
| `validate_c3_live.py` (two clients, private roots, replay, pinned handshake) | | passed |
| `validate_c5_live.py`: real launcher, real server process, **3 real restarts** | | **32/32 `ALL_STEPS_PASSED`**, 0 FAIL lines. Evidence: `work/c1/c5_live_de39df896b7d4d81a3c36128730b5d1a/server/control/c5-live-evidence.json` |
| `validate_c6_bridge.py` (Dart bridge → real worker → real server) | | passed |
| Flutter `flutter test` / `flutter analyze` (`uri_ui`) | 176 passed, 1 skipped / 1 pre-existing deprecation info (`providers_screen.dart:730`) | unchanged (no Dart file changed) |
| Full Python suite, `--ignore=work` | **2640 passed, 12 skipped, 11 failed** (13:43) | **2643 passed, 12 skipped, 11 failed** (13:55); failure-ID set identical to the incoming run (diffed) |
| Full suite on my own fresh `git archive e8e3b65` export (`work/c1/review4_pristine_e8e3b65`, 265 entries), same interpreter | **2257 passed, 7 skipped, 11 failed** (8:11) | |

The 11 failure IDs and their one-line failure messages are **identical** between the incoming checkpoint and the pristine export (diffed): `step3_test::test_drive`, `step4_test::test_download`, `test_capability_directory` privacy, 2× `test_m20_recovery_loop`, 2× `test_m20_semantic_interpreter_resilience`, `test_m20_feasibility_validation`, `test_orchestrator_session_workflow`, `test_usage_import_boundary`, `test_workflow_restart_recovery`. They pre-exist Phase 1 and were not repaired (review scope). Independent probes (scratchpad, not part of the tree): the quota probe against the incoming code showed `tool_calls: 1` closed as `cancelled`; against the repaired code the realistic no-tool quota still pauses cleanly and `quota_after_tool` is uncertain. The `-I` probe: incoming code ran the planted module without `-I`; repaired code refuses `C1_ISOLATED_MODE_REQUIRED` with nothing imported. Not run: `graphify update` (no claim here depends on it); no alternative-model benchmarking (not required for acceptance).

## 7. Cross-component findings

- **C4 → C2 (F1)** was the one composition path where individually "correct" parts produced an unsafe claim: the harness runtime classified honestly (`quota_exhausted`, `tool_calls: 1`), the server honoured the only legal quota path, and the composition still asserted "no effect" without evidence. Repaired at the client runtime, which is the only layer that has the evidence.
- **C1 ↔ C3 ↔ C4**: `uri_harness_adapters` is pinned and composed only by the worker; Core never imports it (fresh-interpreter checks). The launched server's `default_composition()` lists no harness row and `qualified` defaults to `remember_fact` only, so the `/wait` path is unreachable in the launched server until a C4 qualification change.
- **C5 → C3**: the server never writes client stores; it returns a signed `session_update` that the client persists through its own consented commit, and `Mutation.replacement` is allowed only for `sessions/save_session` with `SessionState` fields and the bound `session_id`.
- **C2 trust boundary (NOT_STARTED)**: the server cannot verify a client's `failure_category`. Probe P6 (a client that writes, then reports `NOT_STARTED:`) closes the attempt as `failed` and an explicit re-confirmation plus a second approval executes again. This is the same trust already placed in the client's `verified` evidence: the paired client is the executor and holds the key. It is a documented assumption, not a Core defect; a hostile or defective client runtime is outside the paired-client model.
- **Restart composition**: pending approval state is memory-only; after a restart approvals fail with `CONTEXT_REQUIRED_AFTER_RESTART`, tickets fail on generation, `executing` turns stay durable and uncertain. A client that completed a write but lost the settle keeps a `claimed` journal row (`recover()` marks it uncertain) while the server guard refuses the intent: fail closed, reconciliation is the C7 gate 7 procedure.
- **Legacy composition**: the legacy server gains only the two runtime routes and the strict `/client/v1/*` surface (classified; count 89), and the dispatcher's surface refusal. No accepted authority semantics changed.

## 8. Brain boundary (C5 seams)

Read `paired_brain.py` and `paired_reasoning.py`; re-ran the transport tests and reviewed the three Brain live evidence files. No model is built in (`default_composition()` has no `proposer`); rows are exact `(kind, provider, model)` tuples supplied by trusted composition; the same selected row serves proposer, interpreter and planner; `SELECTED_MODEL_UNAVAILABLE`/`BRAIN_OUTPUT_INVALID` cause no execution and no substitution; planner output that changes WHAT was confirmed is rejected and recompiled; executable arguments come only from `compile(confirmed intent)`; interpreted slots are labelled and need confirmation; the prompt-injection request stopped at confirmation with source `interpreted_from_request` on both `qwen3.5:9b` and `gemma4:12b`. The launched server was **not** changed and the Brain was **not** activated in it.

Recorded Brain-qualification case for later work: **"What did I ask you to remember?"** Both tested models labelled it `remember_fact`; the deterministic extraction found no statement, the interpreter returned nothing usable, and Intent Discovery asked a clarification question. Nothing executed. The authority boundary contained the misunderstanding, so it is not a Core defect; the user experience is wrong and recall is not served by this path. This belongs to the Brain phase.

## 9. Remaining assumptions and limitations

- A malicious process running as the same Windows user is out of scope (DPAPI same-user scope; source, `.venv`, manifests and ledgers are writable). Tree code verifies itself; there is no external pre-hash.
- Third-party packages and `.venv` are bound by METADATA/RECORD digests plus `.pth` hashes; package contents, `sitecustomize` and a stdlib-named module planted in `scripts/` ahead of the bootstrap line are not bound. Within the stated threat model this is adequate; a stronger model was not invented.
- `.json`/`.yaml` data files under `uri_core` are hashed at validation but not re-verified when read.
- `NOT_STARTED:` and all receipt evidence are client-runtime assertions (see §7).
- The quota "no effect" claim now requires `tool_calls == 0`; a harness that acts without emitting a tool event in its stream would still be misclassified. C4 qualification must establish that the harness stream is complete, or extend decision 3 to every quota outcome.
- Deleting or rolling back the server control ledger resets the replay/duplicate guards (same user).
- `FIXTURE_ONLY` qualification is reachable only from tests; nothing in production calls `qualify`.
- Non-live non-terminal turns after a restart are never expired or pruned (ledger growth only).
- The legacy composition's `uri_workspace` catalogue copy is pinned at start only.

## 10. C1–C7 status

| Slice | Status after this review |
|---|---|
| C1 | ACCEPTED as Core identity/launcher authority, with F2 hardening provisional. |
| C2 | ACCEPTED (uncertainty model, ledger guards, strict surface). |
| C3 | ACCEPTED (persistence, journal, private stores, worker). |
| C4 | PARTIAL by design: provider-neutral runtime and adapters accepted as boundary code; native qualification, login and containment evidence remain blocked (owner action). F1 repaired in the runtime. Antigravity refused. |
| C5 | ACCEPTED for the deterministic no-Brain loop and the Brain seams; launched-server Brain activation is a separate policy change; Brain quality is not qualified. |
| C6 | PARTIAL: one Settings screen plus contract; Chat wiring, pinned UI build, voice parity and the "Companion"/"Intelligence" definitions remain owner decisions. |
| C7 | Prepared only: rollback tool accepted; nothing executed; cutover not authorized. |

## 11. Acceptance classification

**Verdict on the incoming checkpoint (`480ae22f…a412`): REPAIR REQUIRED**, for F1 alone. F1 is a material violation of the execution-uncertainty invariant on a path that is unreachable in the launched server today (no harness is qualified, no harness row is composed) but would become live with the first C4 qualification, and the regression suite was asserting the unsafe behaviour. F2 and F3 are low-severity and would not by themselves have blocked acceptance.

**Status of the repaired checkpoint (below): ACCEPT WITH DOCUMENTED LIMITATIONS, provisional.** The repairs are mine and locally validated; I do not call them independently accepted. Someone other than me must review the three changes (`turn_runner.py` quota gating plus fixture, `c1_bootstrap.py` isolated-mode guard, `intent_discovery.py` revision bumps) and their tests. If that review accepts them, Phase 1 Core is suitable to freeze as the baseline for the Brain phase, with the limitations in §9 carried forward.

Acceptance here means: the Core's identity, execution-uncertainty, authority-chain, persistence and rollback boundaries are coherent and fail closed under independent attack. It does **not** mean: C4 native harness qualification is complete; C7 production cutover is authorized; Brain quality is qualified; UI/visuals, skills, Companion/Intelligence roles, memory graph, voice or migration are complete. Those remain separate, as the C7 requirements document lists.

Recommendations carried to the next phases (not Phase 1 acceptance conditions): (a) C4 qualification must include evidence that a harness's event stream is complete (every tool action appears) before the quota pause may claim "no effect", or decision 3 is extended to every quota outcome; (b) the launched-server Brain activation review should keep `brain_composition` as the only composition path and keep the deterministic row available; (c) the "What did I ask you to remember?" case is a Brain-phase recall requirement, not a Core change.

## 12. Repaired checkpoint

`work/c1/checkpoints/review4-final-20261005-191527.zip`, sha256 `0883022f6d67f3f62836a6557758fbded6a6314d80f718236976d26ea7758469`, 117 files plus `GIT_HEAD`/`GIT_STATUS`/`GIT_DIFF` (`GIT_HEAD` = `e8e3b65`). `testzip` is clean and the inventory was re-hashed 117/117 against the live tree. The 117 files are the incoming 116 plus this report. Changed relative to the incoming checkpoint: `uri_core/client_runtime/turn_runner.py`, `uri_core/core/intent_discovery.py`, `scripts/c1_bootstrap.py`, `fixtures/c4_harness/fake_harness.py`, `test_c5_loop.py`, `test_c5_intent_adversarial.py`, `test_c1_source_pin.py`, and this new report. As with the earlier reviews, this section was written after the archive, so the on-disk report differs from the archived copy only by this section. Every change remains uncommitted.
