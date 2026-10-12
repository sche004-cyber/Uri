# URI Phase 1 Core: fifth review (independent closure review for the Core freeze)

Date: 2026-10-05. Reviewer: Claude, a fresh session with no access to the implementing or earlier reviewing sessions' reasoning. Worktree: `C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent`, detached at `e8e3b65`. **Every change is uncommitted.** Nothing was committed, pushed, merged, cut over, deleted from historical artifacts, activated in the launched server (still `model_policy: lazy-not-selected`, deterministic row only) or logged in to any external provider. No Brain, Edge, UI, Skills or deployment work was started.

Question answered: **is URI Core complete enough to freeze as the stable baseline for the intelligence phase?** Previous reports were treated as claims. Every verdict below rests on code read in full plus a probe or run I executed myself in this session (probe modules are listed in §9).

## Acceptance criteria (set before reviewing)

1. The reviewed tree is exactly the candidate checkpoint, proven by archive hash and per-file comparison.
2. F1–F3 are each attacked independently of their regression tests, through the real composition, with restarts where the invariant concerns durability.
3. Each closure gate is exercised through the real paired composition (real app, real client persistence, real stores, real restarts), not by re-running unit suites, and every gap is classified as Core / C4 / Brain / Edge / UI / Skills / C7.
4. Any defect is reproduced before repair, repaired at the narrowest layer, covered by a regression test that fails on the incoming code, and the affected validation plus the gate scenarios are re-run; repairs are marked provisional.
5. The 11 pre-existing full-suite failures are confirmed by failure-ID comparison against the fourth review's list.
6. Live validation uses the real launcher, real server process and real restarts.

## 1. Candidate identity

`work/c1/checkpoints/review4-final-20261005-191527.zip`, sha256 recomputed `0883022f6d67f3f62836a6557758fbded6a6314d80f718236976d26ea7758469` (matches). 117 files plus `GIT_HEAD.txt`/`GIT_STATUS.txt`/`GIT_DIFF.patch` (`GIT_HEAD` = `e8e3b65259c45fc823addc3ef8969425a265bd1b`, `GIT_STATUS`/`GIT_DIFF` empty). Extracted and compared byte-for-byte with the live tree: **116/117 identical**; the one difference is `docs/plans/PHASE1_FOURTH_REVIEW_REPORT.md`, whose on-disk copy adds only its §12 checkpoint hash line (as that report states). Baseline on the unmodified tree, run by me: focused Phase 1 suite (the fourth review's 30 modules) **447 passed, 5 skipped, 61 subtests** (identical to the fourth review).

## 2. F1–F3 independent verdicts

| ID | Verdict | Independent basis |
|---|---|---|
| F1 quota after tool activity | **ACCEPTED**, with one composition defect found beside it (N1, repaired) and one C4 requirement recorded (§10) | Read `_run_harness`, `claim()`, both adapters' parsers, the server `wait`/`settle` paths. Attacks through the real server with the fake harness subprocess: `tool_calls` reported as `UNAVAILABLE` → `SETTLED_EXECUTION_UNCERTAIN` (fails closed, not treated as zero); `tool_calls == 0` but process not contained → uncertain (`CONTAINMENT_UNCONFIRMED` precedes the quota check); genuine first-call quota → `WAITING_FOR_MODEL`. Codex-shaped stream with a `command_execution` item before `turn.failed` quota → `tool_calls == 1` (unit). Claude-shaped quota error with no assistant events → `tool_calls == 0`: the count is of *visible* `tool_use` blocks, so the "no effect" claim is exactly as good as the harness stream (§10). Composition gap found: the quota checkpoint of an earlier clean pause stayed usable after a later continuation became uncertain (N1). |
| F2 isolated bootstrap | **DEFECT REMAINED (now repaired, provisional)** | The gate was placed inside `c1_bootstrap.install()`, which runs after every entrypoint's own stdlib imports and after the bootstrap's own `import hashlib`. Without `-I` the script directory is `sys.path[0]`, so a planted `scripts/argparse.py`, `scripts/hashlib.py` or a sourceless `scripts/secrets.pyc` executed inside all four entrypoints **before** `C1_ISOLATED_MODE_REQUIRED` (reproduced: marker written, `ImportError: planted`). With `-I` (the launched path, enforced by `process_identity` and both `.ps1` wrappers) none of them ran; root shadowing, package-vs-module and `__pycache__` tricks were re-read and the existing attacks re-run. Repair: N2. |
| F3 abandon/stop revision | **ACCEPTED** | Read `_bump`, `_stop`, `handle()`, the coordinator's `_ledger_revision` check (runs before `handle`, so it covers confirm, select and plain-text answers) and the pruning tombstone. Attacks through the real app with a **real app restart** between abandon and replay: pre-abandon state replayed via confirm, via a text answer, and an even older pre-answer state replayed via `select` and via a text answer → all `INTENT_STATE_STALE`, nothing dispatched, pointer cleared. Budget-stopped intent replayed from pre-stop state after restart → stale. An abandon decision carrying a stale revision changes nothing (`INTENT_DECISION_STALE`, live record intact). |

## 3. Memory closure verdict: **PASS WITH DOCUMENTED LIMITATIONS**

What URI Memory v1 (Core) guarantees, each point exercised through the real composition (`test_phase1_closure_review.py::test_g1_*`):

- **Learn/store**: only an explicitly confirmed, digest-bound `remember_fact` intent, approved against exact arguments, writes a `MemoryStore` entry; the write is a consented C3 commit (journal + CAS, rollback on failure) and is independently read back before the receipt says `verified`.
- **Persist / restart / new session**: entries survive server restart and are visible from a fresh client persistence instance and from a new session (the store is principal-scoped, not session-scoped). A pronoun in a new session never binds to the previous session's referent (asked, not guessed).
- **Provenance on the entry**: `consent = user_provided`, `fact.source = user_explicit`, `status = CONFIRMED`, timestamps. The transcript turn now carries the intent lineage (N4) and the history/ledger link by `intent_id`/`operation_id`.
- **Correction before execution**: handled inside the intent (superseded values kept in the record, old digest refused).
- **Session facts** (`reference.recent_subject`): supersede through `update_fact` with append-only `fact_history`; after a restart a follow-up "it" binds to the **current** value, never the superseded one.
- **Forgetting**: the client-local `memory.delete`/`update` ports exist and work through a consented commit; there is **no Core intent path** (no schema) for forgetting or editing. Documented, not invented.

Documented limitations (all Core, none blocking the freeze; see §10 for phase assignment):

- L1 **No retrieval into reasoning.** No Core path projects `MemoryStore` entries into the decision request or into intent discovery (`durable_memory_relevant` is never supplied in the paired composition). Memory v1 is store-and-verify; recall is a Brain-phase capability (the recorded benchmark "What did I ask you to remember?").
- L2 **No supersession or conflict handling across entries.** A later "correction" after execution is a new entry; the old entry stays `CONFIRMED`; duplicates are allowed (same statement twice → two entries). Nothing marks an entry invalidated, so a future Brain that reads the store would see both. Core never relies on entries today, so nothing stale can return *through Core*.
- L3 **No per-entry turn/intent linkage** on the memory entry itself (the linkage lives in the transcript provenance record, N4).
- L4 Statements longer than 500 characters are refused by `MemoryStore` inside the commit (rolled back) and settle `SETTLED_EXECUTION_UNCERTAIN` (pre-existing; identical on the incoming code). Honest fail-closed, mislabelled.

## 4. Context closure verdict: **PASS WITH DOCUMENTED LIMITATIONS**

What Core context resolution guarantees (`test_g1_session_fact_*`, `test_g2_*`, inherited C5 tests, live steps):

- Reference binding is session-first (this session's files plus the session's confirmed recent subject), deterministic (RAR), then widened **exactly once** to the graph store, then asked. Every bound value is the user's words or a candidate title; graph-derived bindings always need explicit confirmation; a bound session file must still exist with the same title at confirmation (else stale and re-asked).
- Multiple entities → asked with the displayed options only; a choice that was never displayed is refused; ambiguous, stale and conflicting candidates were exercised (inherited and new). A session file and a graph node with the same title: session-first wins, no widening.
- The decision request a Brain receives is bounded: `user_text`, last ≤6 transcript turns, `active_pointer` (pending intent slots), preselected `capability_summaries`, `session_facts`, `attempt_history`; no memory dump, no graph dump (observed payload < 20 KB after 10 turns).
- Corrections never guess (bare negation asks; explicit old→new replaces only the named value).

Documented limitations:

- L5 **Session-fact projection shows superseded values, not current ones.** Turn State's `session_facts` is projected from `fact_history` (`turn_state._project_session_facts`), so a Brain sees `reference.recent_subject = Budget report Q4.docx (SUPERSEDED)` while the current `Q3` value is absent. Core's own binding reads `current_facts`, so this cannot misbind Core; it under-supplies and mislabels context for a future Brain. Classified Core (Turn State projection), to fix in the Brain-activation review, not a freeze blocker.
- L6 **Transcript ceiling.** Every turn sends the whole session transcript in the client snapshot (`CONTEXT_LIMIT` 256 KiB); the server uses six turns. A session fails closed (`CONTEXT_LIMIT`, deterministic) once its transcript exceeds the limit (observed at turn 32 of 8 KB texts) and cannot continue; a new session works. Classified Core (listed storage-growth limitation), not silent truncation.
- L7 Graph widening uses the longest non-stop token of the expression (e.g. `report`), so unrelated nodes sharing that word become candidates; RAR found none plausible and Core asked an unanswerable empty "Which one…?" (N3, repaired: it now asks freely and the user's answer is bound as `USER_SUPPLIED`).

## 5. Authority / Execution closure verdict: **PASS WITH DOCUMENTED LIMITATIONS**

Exercised end to end (inherited suites re-run, the live sequence with 3 real restarts, and new probes): user words → deterministic extraction / interpreter → intent discovery → explicit confirmation (digest-bound, text never confirms) → approval bound to the Confirmed Intent Contract digest and exact arguments → signed ticket → claim → execution → independent verification → settle. Verified in this session: interpreted slots are labelled `interpreted_from_request`, never auto-confirm, must be verbatim (a paraphrasing interpreter is dropped and the user is asked), and compile to exactly the confirmed words; confirmation replay after execution is refused; stale client state never restores authority (§2 F3); executable arguments equal `compile(confirmed intent)` (drifting planner rejected and recompiled); uncertain execution is never re-run by re-confirming, after a restart, or by cancel; quota-after-tool is uncertain (F1); cancellation keeps uncertainty (`EXECUTION_UNCERTAIN_NOT_CANCELLED`, also after a real restart with no live context).

Limitations: the client runtime's `NOT_STARTED:` tag and receipt evidence are client assertions (documented trust, unchanged); L4; the Brain benchmark "What did I ask you to remember?" is contained by Core (clarification, nothing executes) and is a Brain-phase quality issue.

## 6. Recovery / Integrity closure verdict: **PASS**

Exercised: real server-process restarts (live steps 15a/21/25, 32/32 passed); app restarts around clarification, before confirmation, after confirmation (fresh approval required), around the execution handoff (exactly one effect, then `INTENT_EXECUTION_UNCERTAIN`), after a client crash between claim and settle (journal `execution_uncertain`, `dispatch=False`); corrupted server turn ledger → `CONTROL_STORE_UNAVAILABLE` (restored ledger resumes the pending question); corrupted execution-control ledger between approval and claim → `EXECUTION_CONTROL_UNAVAILABLE`, journal keeps the intent uncertain, nothing written; tampered signed intent → `INTENT_STATE_INVALID`; altered pinned source / invalid catalogue / wrong signing key → refused at validation (inherited `test_c1_*`, `test_phase1_fail_closed`); rollback restoration refuses aliasing and authority-widening catalogues (inherited `test_c7_rollback_boundary`). In every case URI recovered to an honest state or failed closed; nothing manufactured certainty.

## 7. Observability / Provenance closure verdict: **PASS WITH DOCUMENTED LIMITATIONS** (after repair N4; FAIL on the incoming checkpoint)

On the incoming checkpoint the after-the-fact reconstruction of a completed request was: user words ✓ (client history), confirmation ✓ only as rendered reply text, outcome ✓ (history, server ledger `execution_outcome`, control ledger, journal, memory entry). **Missing**: the interpreted intent (slot sources: user words vs interpreter vs correction), the bound referent and its rule, the correction/supersession history, the confirmed digest, the approved argument digest and arguments, and the receipt evidence. The signed intent record is cleared from the session on completion (by design), the server ledgers hold digests and states only (by design: no private content), and no client store kept the lineage. So a wrong memory entry could not be attributed to Brain interpretation versus user words versus binding. Repair N4 records a bounded, client-private provenance record with each transcript turn; after it, every item in the gate's list is reconstructible for `remember_fact` and harness tasks (`test_g5_*` verifies the chain: history ↔ provenance ↔ server turn `intent_id`/`operation_id` ↔ control ledger ↔ journal ↔ memory).

Limitations: server-side ledgers deliberately carry no content (digests, states, ids): cross-checking content requires the client's private stores; receipt evidence itself is still not persisted (its digest is, in both ledgers); the exact snapshot sent to the server is not persisted (only `request_digest`); records are truncated to digests beyond 4 KiB.

## 8. New defects (all reproduced before repair; all repairs PROVISIONAL)

| ID | Severity | Defect | Violated invariant | Reproduction | Repair | Regression test (fails on incoming code) |
|---|---|---|---|---|---|---|
| **N1** | Medium | A quota checkpoint stayed usable after a continuation dispatched from it became `execution_uncertain`: T1 paused cleanly (first-call quota), `continue_waiting(T1, B)` hit quota after tool activity (uncertain), `continue_waiting(T1, B)` again ran the task a third time (`SETTLED_VERIFIED`, a real effect) with only a fresh approval; the server saw a new intent, so the intent guards did not apply. | "uncertain execution cannot be casually retried"; C6 contract "offer no retry for that request". | `test_review5_f1_f3.py::test_f1_stale_quota_checkpoint_rerun_after_uncertain_continuation` on the incoming code → third run verified. | `turn_runner.continue_waiting`: a checkpoint is consumed (marked before dispatch) by its first continuation; a later use is `CHECKPOINT_CONSUMED`. A continuation that pauses cleanly leaves its own checkpoint. | `test_c5_loop.py::test_quota_checkpoint_is_one_continuation_not_a_standing_retry` |
| **N2** | Low (completes F2) | See §2 F2. | C1: no code before verification. | planted `scripts/argparse.py`, `scripts/hashlib.py`, `scripts/secrets.pyc` ran in all four entrypoints without `-I`. | The isolated-mode check is the first statement after `import sys` in `c1_bootstrap.py`, both entrypoints, and (under `__main__`) both launchers. | `test_c1_source_pin.py::test_entrypoints_refuse_without_isolated_mode_before_importing_anything` now plants all four. |
| **N3** | Low | Graph widening found nodes sharing a word, RAR found none plausible, and the `FREE_INPUT_ONLY` contract was rendered as "Which one do you mean by 'the Q4 report'? ." with no options; every answer then ended in `CLARIFICATION_REPEAT_BLOCKED`. Nothing was guessed. | Clarification must be answerable; "ask, never guess" must be usable. | `test_g2_unrelated_graph_nodes_*` on the incoming code (evidence file kept). | `intent_discovery._resolve_reference`: a `FREE_INPUT_ONLY` contract asks the free question (round closed). | `test_c5_intent_adversarial.py::test_graph_nodes_sharing_a_word_but_implausible_ask_freely_not_an_empty_choice` |
| **N4** | Medium (observability) | See §7. | Diagnostic accountability (Gate 5). | `test_g5_*` on the incoming code: argument digest, intent digest, slot sources and correction history absent from every durable store after completion. | `turn_runner._finish` records `uri.turn.provenance.v1` in the transcript turn's `attachments` (intent public projection without the duplicated request text, clarification/confirmation shown, approved arguments and digests, execution state), bounded to 4 KiB (values dropped, digests kept) and `capability` on execution turns. Client-private; never sent to a model (Turn State projects only `user_text`/`response_text`). | `test_phase1_closure_review.py::test_g5_*` (fails on incoming code) |

No gate was weakened. No fixture changed. `_finish` now takes `approval`/`intent` keyword arguments (internal); the decline, execute and quota paths pass them.

## 9. Validation results

All runs executed by me in this session on the same `.venv` interpreter (Python 3.13.15) with a synthetic `URI_EXTERNAL_CREDENTIAL_SECRET`. Logs: `work/c1/review5/` (`focused_incoming.log`, `chain.log`, `c5_live.log`, JUnit XML files, `closure_evidence/*.json`).

**Inherited tests**

| Run | Incoming checkpoint (unmodified) | Repaired tree |
|---|---|---|
| Focused Phase 1 suite (the fourth review's 30 modules) | **447 passed, 5 skipped**, 61 subtests (6:43) | **449 passed, 5 skipped**, 61 subtests (6:34); +2 = the N1 and N3 regressions |
| `scripts/validate_c1_regression.py` | (not re-run before repairs) | 303 passed, 29 subtests |
| `scripts/validate_c3_live.py` (two real workers, real server, replay, pinned handshake) | | passed, `test_owned_workers_and_server_cleaned: true` |
| `scripts/validate_c6_bridge.py` (Dart bridge → real worker → real server) | | passed |
| Full Python suite, `--ignore=work` | (fourth review: 2643 passed, 12 skipped, 11 failed) | **2645 passed, 12 skipped, 11 failed**, 88 subtests (14:12) |
| Flutter `flutter test` / `flutter analyze` | not re-run: no Dart file changed (fourth review: 176 passed, 1 skipped) | |

The 11 full-suite failure IDs are **identical** to the fourth review's list: `step3_test::test_drive`, `step4_test::test_download`, `test_capability_directory::PrivacyTests::test_no_credentials_tokens_or_secrets_appear_in_serialized_output`, `test_m20_feasibility_validation::…falls_back`, 2× `test_m20_recovery_loop`, 2× `test_m20_semantic_interpreter_resilience`, `test_orchestrator_session_workflow::…test_session_facts_are_used_for_clarification`, `test_usage_import_boundary::test_orchestrator_newline_count_does_not_increase`, `test_workflow_restart_recovery::…test_workflow_survives_restart_and_resumes`. They pre-exist Phase 1 (confirmed on pristine exports by the third and fourth reviews) and were not repaired (review scope).

**New closure tests** (`test_phase1_closure_review.py`, 22 tests; also run as the three probe modules under `work/c1/review5/` during the review): **22 passed** on the repaired tree. On the incoming tree, the same probes gave: 16 passed, 3 failed for the reasons recorded (N1 third run verified; N3 empty question; N4 digests/sources absent) plus the long-statement limitation L4. Regressions added to inherited modules: `test_c5_loop.py::test_quota_checkpoint_is_one_continuation_not_a_standing_retry` (N1), `test_c1_source_pin.py::test_entrypoints_refuse_without_isolated_mode_before_importing_anything` extended (N2), `test_c5_intent_adversarial.py::test_graph_nodes_sharing_a_word_but_implausible_ask_freely_not_an_empty_choice` (N3).

**Real-process / restart tests**: `scripts/validate_c5_live.py` with the real launcher, real server process and **3 real restarts**: **32/32 `ALL_STEPS_PASSED`**, 0 FAIL lines; evidence `work/c1/c5_live_b1180bf97d7048c387692d4ef9e0c54a/server/control/c5-live-evidence.json`. `test_c1_source_pin.py` (real `uri_server.ps1` starts with planted bytecode/shadows), `test_c1_runtime_identity.py`, `test_c6_worker_turns.py`, `test_c3_client_worker.py` (real worker/server processes) all passed in the focused run. My F2 probe (planted `scripts/argparse.py`, `scripts/hashlib.py`, `scripts/psutil.py`, sourceless `scripts/secrets.pyc`; each entrypoint without `-I`): incoming code ran the plants (marker written) in all four entrypoints; repaired code refuses `C1_ISOLATED_MODE_REQUIRED` with no marker.

**Model-assisted tests**: none run (`test_c5_brain_live.py` is opt-in and skipped; no provider login, no local model started). The Brain seams are covered by the inherited transport tests and the third review's recorded live evidence; Brain quality is out of scope.

**Known pre-existing failures**: the 11 above, unchanged.

## 10. Remaining limitations and phase assignment

| Limitation | Assigned to |
|---|---|
| C4 native Claude/Codex login not completed; harness containment beyond the workspace not qualified; Antigravity refused | C4 HARNESS QUALIFICATION |
| **Harness stream completeness**: F1's `tool_calls == 0` is a claim about the harness's event stream. A harness that acts without emitting a visible tool event (hooks, subagents, MCP, settings-driven tools) would still be misclassified as a clean pause. Core must not solve this (no Core contract requires it; Core has no evidence source); it is a qualification evidence requirement: before `NATIVE_QUALIFIED`, show that the argv (`--tools`, `--allowedTools`, `--setting-sources ""`, `--strict-mcp-config`, Codex `--sandbox workspace-write`) makes every effect-capable action appear as a stream event, or extend review decision 3 to every quota outcome for that harness. | C4 HARNESS QUALIFICATION |
| Launched-server Brain lazy-not-selected; Brain quality not qualified; "What did I ask you to remember?" recall; L1 retrieval into reasoning; L5 session-fact projection | BRAIN (L5's code fix is Core-owned, scheduled with the Brain activation review) |
| Edge model selection/benchmarking | EDGE |
| C6 polished UI, Chat wiring, pinned UI build, Companion/Intelligence definitions, Memory Graph visualization, 3D/avatars | VISUALS/UI |
| Skills | SKILLS |
| C7 cutover, owner/key mapping, copy-first migration, reconciliation of uncertain turns, gates 1–10 | DEPLOYMENT/C7 |
| L2 memory supersession/duplicates across entries; L3 entry-level linkage; L4 >500-char statements; L6 transcript ceiling; long-term storage growth/pruning; non-live non-terminal turns never expired; same-user hostile process out of scope; ledger rollback resets guards; Graphify regeneration not performed | CORE (documented; none blocks the freeze) |
| Receipt evidence and the request snapshot not persisted (digests only) | CORE (documented) |

Each existing limitation listed in the brief was checked against the code and is correctly assigned above.

## 11. Core freeze recommendation

**FREEZE CORE WITH DOCUMENTED LIMITATIONS** — on the repaired checkpoint in §12, conditional on an independent review of N1–N4 (they are mine). On the incoming checkpoint `0883022f…8469` alone the verdict would be REPAIR AND RE-REVIEW, for N1 (a real third effect while an attempt was uncertain) and N4 (Gate 5 FAIL); N2 and N3 are low.

Freeze means: Core identity, execution-uncertainty, authority chain, persistence/recovery and provenance boundaries are coherent, fail closed under independent attack through the real composition, and are sufficient as the baseline the intelligence phase builds on. It does not mean any later-phase capability (§10) is complete.

Another reviewer is needed before the freeze is final: N1 and N4 materially change client-runtime behaviour (checkpoint consumption; a new provenance record in the transcript store).

## 12. Repaired checkpoint

`work/c1/checkpoints/review5-final-20261005-201930.zip`, sha256 `1b6fd6f500e8dbfcdbf02390a638b36b56af934e623601fe4f769b79191e8a8a`, **119 files** plus `GIT_HEAD.txt`/`GIT_STATUS.txt`/`GIT_DIFF.patch` (`GIT_HEAD` = `e8e3b65`). `testzip` is clean and the inventory was re-hashed 119/119 against the live tree (`work/c1/review5/checkpoint.json`). The 119 files are the incoming 117 plus this report and `test_phase1_closure_review.py`. Changed relative to the incoming checkpoint: `scripts/c1_bootstrap.py`, `scripts/run_uri_isolated_server.py`, `scripts/run_uri_client_worker.py`, `scripts/uri_server_launcher.py`, `scripts/uri_client_launcher.py` (N2); `uri_core/client_runtime/turn_runner.py` (N1, N4); `uri_core/core/intent_discovery.py` (N3); `test_c1_source_pin.py`, `test_c5_loop.py`, `test_c5_intent_adversarial.py` (regressions); `docs/plans/PHASE1_FOURTH_REVIEW_REPORT.md` (its own §12 line, already on disk before this review). As with the earlier reviews, this section was written after the archive, so the on-disk report differs from the archived copy only by this section. Every change remains uncommitted. **The incoming checkpoint `0883022f…8469` is therefore not the frozen baseline; the candidate baseline is `1b6fd6f5…8a8a`, provisional until N1–N4 are independently reviewed.**
