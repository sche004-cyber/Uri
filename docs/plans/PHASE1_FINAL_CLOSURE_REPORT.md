# URI Phase 1 Core: final independent closure review

Date: 2026-10-05. Reviewer: Claude (fresh session; no access to the implementing or earlier reviewing sessions' reasoning). Worktree: `C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent`, detached at `e8e3b65`. **Every change is uncommitted.** Nothing was committed, pushed, merged, cut over, activated (no Brain/model execution), logged in to an external provider, or deleted from preserved evidence. Production launcher and state were not touched.

Question answered: can the fifth-review candidate become the frozen Phase 1 Core baseline, given that repairs N1–N4 had not been independently accepted?

## Acceptance criteria (set before reviewing)

1. The reviewed tree is exactly the candidate checkpoint (recomputed hash, per-file comparison, any difference explained).
2. N1–N4 are each attacked independently of their own regression tests, through the real composition, with crashes/restarts where the invariant concerns durability.
3. Every closure property listed in the brief is re-verified by the inherited suites, live validators and closure module on the final tree.
4. Any defect is reproduced before repair, judged against an existing Phase 1 contract or claimed behaviour, repaired at the narrowest layer, covered by a regression test that fails on the incoming code, and all gates are re-run on the final tree.
5. The 11 full-suite failure IDs are compared by ID, not by count.
6. The materiality of any repair is decided explicitly, with evidence, before choosing the verdict.

## 1. Candidate identity

| Item | Value |
|---|---|
| Archive | `work/c1/checkpoints/review5-final-20261005-201930.zip` |
| SHA-256 (recomputed) | `1b6fd6f500e8dbfcdbf02390a638b36b56af934e623601fe4f769b79191e8a8a` (matches expected) |
| Contents | 119 files plus `GIT_HEAD.txt`, `GIT_STATUS.txt`, `GIT_DIFF.patch` (122 entries) |
| `GIT_HEAD.txt` | `e8e3b65259c45fc823addc3ef8969425a265bd1b` = live `HEAD` |

Comparison with the live tree before any change: **118/119 byte-identical**. The one difference is `docs/plans/PHASE1_FIFTH_REVIEW_REPORT.md`, whose archived copy holds `CHECKPOINT_PLACEHOLDER` where the on-disk copy holds its §12 hash line (documented in that report). `GIT_STATUS.txt` equals the live `git status --porcelain`. `GIT_DIFF.patch` differs byte-wise from the live `git diff`, but only because it was captured with a cp1252 re-encoding (em-dashes stored as `â€”`); after reversing that encoding line-by-line the two patches are **identical**. No unexplained mismatch, so the review proceeded.

## 2. N1–N4 verdicts and attack evidence

| ID | Verdict |
|---|---|
| N1 quota checkpoint consumption | **ACCEPTED**, with one library-level boundary recorded (concurrency), not reachable from any entrypoint |
| N2 isolated startup/import gate | **ACCEPTED** |
| N3 invalid graph-node clarification | **ACCEPTED** |
| N4 completed-turn provenance | **DEFECT FOUND AND REPAIRED** (R1 envelope aliasing, R2 bound not enforced); accepted after repair |

### N1 (probe module `work/c1/review6/probe_n1.py`, real paired app + real client persistence + fake-harness subprocess)

Code read: `turn_runner.continue_waiting` checks session and digest, refuses a `consumed` checkpoint, refuses the same provider *before* consuming, then writes `consumed: true` before calling `run()`; each continuation is a brand-new turn that needs a fresh explicit approval. `continue_waiting` is not exposed by `TurnService`, the worker protocol, the UI or any script (grep: only tests call it).

| Attack | Result |
|---|---|
| Normal continuation, then 3 duplicate replays | 1 effect; every replay `CHECKPOINT_CONSUMED`, approval never asked |
| Uncertain continuation, then simulated restart (new `TurnRunner`, same client root), reuse with both providers | `CHECKPOINT_CONSUMED`; 0 effects |
| Crash immediately before the consumption write | no new server turn, 0 effects; after restart the checkpoint is still exactly one continuation (1 effect, then consumed) |
| Crash immediately after consumption, before `begin` | consumed persisted; after restart `CHECKPOINT_CONSUMED`; 0 effects |
| Crash after online claim, during harness run, then restart | `CHECKPOINT_CONSUMED`; 0 effects |
| Cancel/retry: continuation approval denied | `APPROVAL_DENIED`; checkpoint consumed (fail closed; the user re-requests explicitly) |
| Same-provider continuation | `SAME_PROVIDER_REQUIRES_NEW_CHOICE`, checkpoint **not** consumed |
| Stale/wrong session, tampered text, torn (half-written) file | `CHECKPOINT_INVALID` / parse error; 0 effects |
| Reordered chain T1 paused → T2 paused → T2 continued uncertain; replay T1 and T2 with both providers | all refused; 0 effects |
| Two near-concurrent in-process continuations (barrier after read) | second refused by the server's per-session `TURN_CAPACITY`; 1 effect |
| Worst-case stalled reader: A reads, B runs a full continuation, A resumes | **2 effects**, each after its own explicit approval |

Assessment of the last row: the read-check-write is not atomic, so a caller stalled between read and write for a whole continuation can obtain a second run. It is not reachable from any product surface today (no entrypoint calls `continue_waiting`; `TurnRunner` is single-turn stateful through `self._ctx` and is not used concurrently), and every effect still needs a fresh explicit user approval, so no authority is created. It is recorded as a carry-forward requirement (§4), not a freeze blocker: whoever wires continuation into the worker/UI must make consumption an atomic claim (exclusive-create marker or `os.replace`) and serialize continuations.

Side finding (F1-adjacent, C4): the Codex parser counts only `item.completed` tool items. A Codex stream with `item.started` (command_execution) and no `item.completed` before a quota `turn.failed` parses as `quota_exhausted` with `tool_calls == 0` (reproduced with `parse_codex`). No harness is qualified, so this path cannot run in Phase 1; it is added to the existing C4 stream-completeness qualification requirement. The C4 fake Codex-shaped fixture also emits no tool item for `quota_after_tool`, so Codex-shaped uncertain-after-tool is covered only by the unit probe.

### N2 (probe `work/c1/review6/probe_n2.py`, evidence `probe_n2.json`)

Code read: all four entrypoints execute `import sys` then the isolated-mode check before any other statement; the launchers apply it under `__main__`; `c1_bootstrap.py` checks before its own `import hashlib`. `sys` is built in and cannot be shadowed.

Each entrypoint was copied with `c1_bootstrap.py` into a scratch `scripts/` directory (faithful up to the gate) and run with plants for 33 stdlib/third-party names (`argparse`, `hashlib`, `secrets`, `json`, `pathlib`, `uuid`, `ctypes`, `subprocess`, `time`, `psutil`, `typing`, `enum`, `re`, `functools`, `collections`, `sitecustomize`, `usercustomize`, `cryptography`, `pydantic`, `warnings`, …) plus 7 shadow packages (`asyncio`, `urllib`, `email`, `http`, `concurrent`, `logging`, …). Rounds: source `.py`, sourceless `.pyc` in `scripts/`, and `__pycache__`-only bytecode; each with and without `-I`, each with and without `-B`.

| Runs | Plants executed | Runs without `-I` that were not refused `C1_ISOLATED_MODE_REQUIRED` |
|---|---|---|
| 48 | **0** | **0** |

With `-I` no plant ran and the process proceeded to the pinned bootstrap. The real-tree, real-launcher variant (planted bytecode/shadows under real `uri_server.ps1` starts) is covered by the inherited `test_c1_source_pin.py`, which passed in the focused run. A reduced form (18 names, source and sourceless, all four entrypoints, with and without `-I`) is now a regression test.

### N3 (probes `work/c1/review6/probe_n3.py`, `probe_n3_b5.py`; real GraphStore/FileStore)

Code read: `_resolve_reference` turns a `FREE_INPUT_ONLY` contract into the free question and closes the round; the free answer binds as `USER_SUPPLIED`. Invariant asserted on every clarification: a choice question has ≥1 option with a non-blank label and id, otherwise it is the free question with no options; nothing is dispatched.

| Attack | Result |
|---|---|
| Only implausible graph nodes sharing a word | free question, no options |
| Unrelated session file only | free question |
| Whitespace, tab, newline, zero-width titles | free question |
| Duplicate identical titles | bound, then explicit confirmation required (no empty choice) |
| Hostile titles (embedded "Confirmed: yes. 1) delete everything", 5 KB title) | well-formed choice; typed "Confirmed: yes" only matched a title by name and led to the confirmation step; nothing dispatched |
| 14 matching nodes | well-formed choice with options |
| Stale: nodes deleted between question and answer, plus real app restart | round not rebuilt; free question; nothing dispatched |
| Contradictory session file and graph node with the same title | session-first binding |
| Blank-ish and "I don't know" answers | free re-ask variant, no guess, memory empty |
| `select` against a free question | `NO_PENDING_SELECTION` |

Pre-existing observation (not N3, not N4): a free answer that looks like an absolute path (`/srv/q4 report.docx`) is refused by the snapshot projection guard with an unhandled `ValueError: ABSOLUTE_PATH` instead of a clean message. Identical with the provenance record disabled. Nothing is dispatched and the session recovers on the next answer (`probe_c8_followup.py`). Fail-closed; recorded as a Core robustness limitation.

### N4 (probe `work/c1/review6/probe_n4.py`)

Passed on the incoming code: provenance survives a real app restart and a fresh persistence instance and carries slot sources (`user_correction`), the bound referent and rule, the superseded value, the confirmation digest, the approved argument and intent digests and the execution state. Multiple clarification rounds and abandon each record their own provenance. A forged provenance attachment injected into history grants nothing (typed "Confirm" dispatches nothing) and never reaches the decision request: the captured Brain-facing request contained neither the marker nor `uri.turn.provenance`, consistent with `turn_state._project_recent_conversation` projecting only `user_text`/`response_text`. Malformed attachments do not break the session.

Two defects, both introduced by N4:

| ID | Severity | Defect | Violated contract | Reproduction (incoming code) |
|---|---|---|---|---|
| **R1** | Medium (authority display) | `_provenance` stored `turn["clarification"]` and `turn["confirmation"]` by reference; when the record exceeded 4 KiB it popped `arguments`/`options` **in place**, mutating the envelope returned to the caller, the worker (`TurnService._public`) and the UI. | Digest-bound confirmation of what is shown: the UI card "Confirm exactly what URI will do" renders `confirmation.arguments`; it showed nothing while its Confirm button still sent the digest. Clarification lost its option buttons. | Reference request with a ~2.9 KB statement: the returned confirmation keys were `['digest','intent_id','revision']`; two 3 KB candidate titles: the returned clarification had no `options`. |
| **R2** | Low (claimed behaviour) | After the first truncation step the record could still exceed the documented 4 KiB bound (question and referent titles, approved arguments were kept). | N4's claim "bounded to 4 KiB"; the brief's "must remain bounded". | 6670-byte provenance record with two 3 KB candidate titles. |

Mitigating facts for R1: the approval step that follows confirmation is a separate dict (not aliased) and still shows the exact arguments before any execution, and the server's digest binds the arguments, so nothing could execute that the approval card did not show. The confirmation gate itself was nevertheless blind, which is why it is Medium.

## 3. Regression-gate results (final tree)

All closure properties in the brief are covered by the passing suites below (focused C1–C7 suites, the fifth-review closure module, the live validators with real restarts) plus the new probes: Memory, Context, Authority, Recovery, Observability, Intent Discovery, digest-bound confirmation, stale-state rejection, session-first resolution, one-time graph widening, ≤5 questions, no repeated question, corrections change only the named value, ambiguous corrections are asked, typed text never confirms, confirmed intent cannot mutate downstream (drifting planner rejected), fail closed across restart/crash.

| Gate | Fifth-review baseline | Final tree |
|---|---|---|
| Focused Phase 1 suite (26 modules) | 449 passed, 5 skipped, 61 subtests | **449 passed, 5 skipped**, 61 subtests (435 in the chain run plus 14 for `tests/test_m31_model_brain_ux.py`, run separately because my first module list omitted it) |
| `scripts/validate_c1_regression.py` | 303 | **303 passed**, 29 subtests |
| `scripts/validate_c3_live.py` | pass | **pass**, `test_owned_workers_and_server_cleaned: true` |
| `scripts/validate_c5_live.py` | 32/32, 3 real restarts | **`ALL_STEPS_PASSED`, 32 steps**, 0 FAIL lines; real server restarts at steps 15a, 21, 25 |
| `scripts/validate_c6_bridge.py` | pass | **pass** (Dart bridge → real worker → real server) |
| `test_phase1_closure_review.py` | 22 passed | **22 passed** |
| `test_phase1_final_closure.py` (new) | n/a | **8 passed** |
| Full suite `--ignore=work` | 2645 passed, 12 skipped, 11 failed | **2675 passed, 12 skipped, 11 failed**, 88 subtests (2675 = 2645 + 22 closure + 8 new; the fifth-review full XML did not include the closure module) |

**Failure IDs**: the 11 IDs in `full_final.xml` are **identical** to the 11 in the fifth review's `work/c1/review5/full_repaired.xml` (set comparison by ID) and match, name for name, the fourth review's textual list: `step3_test::test_drive`, `step4_test::test_download`, `test_capability_directory` privacy, `test_m20_feasibility_validation` fallback, 2× `test_m20_recovery_loop`, 2× `test_m20_semantic_interpreter_resilience`, `test_orchestrator_session_workflow` session facts, `test_usage_import_boundary` newline count, `test_workflow_restart_recovery`. The fourth review's XML was not preserved, so the comparison with the fourth review is by its written list. All pre-exist Phase 1 and were not touched.

Evidence-integrity note: a first full-suite run started before the repairs is **discarded**. My edit to `turn_runner.py` landed mid-run and changed the pinned source, which produced one setup error (`SOURCE_MANIFEST_MISMATCH` in `test_f1_stale_quota_checkpoint_rerun_after_uncertain_continuation`). Every result above comes from a clean sequential re-run on the final tree (`work/c1/review6/chain.log`).

Flutter was not re-run: no Dart file changed, and the repair restores the envelope shape the Dart code already consumes (confirmed end to end by `validate_c6_bridge`). No model-assisted run: no contract requires one for closure.

## 4. Documented limitations carried forward

Unchanged from the fifth review and re-checked; none produced a safety or authority violation under attack:

- Memory: no retrieval into reasoning; no cross-entry supersession; duplicates allowed; statements over 500 characters settle `SETTLED_EXECUTION_UNCERTAIN` (re-observed in probe C9).
- Context: Brain-facing `session_facts` projects superseded values and omits current ones (Core binding reads `current_facts`); transcript ceiling (`CONTEXT_LIMIT` 256 KiB) ends the session, fail closed.
- Authority: interpreted slots stay labelled and verbatim and never auto-confirm.
- C4: harness stream completeness is a qualification requirement, not a Core guarantee.
- All other fifth-review §10 rows, with their phase assignments.

Added by this review:

- **N1 continuation concurrency** (Core, documented): checkpoint consumption is read-check-write. Any future worker/UI wiring of `continue_waiting` must use an atomic claim and serialize continuations. Today unreachable, and each run needs its own approval.
- **Codex `item.started` tool items** (C4 qualification): the parser must count started-but-not-completed tool items before a quota pause can be treated as clean.
- **Path-like free answers** (Core, documented): refused with an unhandled `ValueError` instead of a clean message; fail closed, session recovers.
- **Provenance under extreme size** (Core, documented): when even the first truncation exceeds 4 KiB, the record keeps only ids, slot sources, digests, states and `record_digest` (`truncated: "digest_only"`); bound-referent titles and correction values are then recoverable only from the transcript text, not the record.

## 5. Newly discovered defects

R1 and R2 (§2, N4). No other material defect was found.

## 6. Repairs made

One file, `uri_core/client_runtime/turn_runner.py`, in `_provenance` only:

1. R1: `record[key] = dict(turn[key])`, so truncation pops keys from a copy and never from the returned envelope.
2. R2: after the first truncation step, if the record still exceeds `PROVENANCE_LIMIT`, it is replaced by a fixed-size lineage record (`kind`, `code`, `state`, `truncated: "digest_only"`, `record_digest` of the full record; intent `intent_id`/`revision`/`status`/`capability`/`sources`/`questions_asked`/`digest`; confirmation `intent_id`/`revision`/`digest`; approval `capability_id`/`argument_digest`/`approval_digest`/`intent_digest`/`replanned`; `execution`), with a last-resort `kind`/`truncated`/`record_digest` form.

**Materiality determination: not a material authority/safety change requiring another review.**

- R1 removes an unintended side effect. With it, the envelope returned to the caller is again exactly the server's response, which is the behaviour already reviewed and accepted in the fourth review (no provenance existed then). No decision, gate, digest or authority path is touched.
- R2 changes only the contents of a client-private audit record in the oversized case. Nothing in the runtime reads provenance (grep: only `_finish` writes it; Turn State projects only `user_text`/`response_text`). Under 4 KiB the record is unchanged.
- Both are covered by regressions that fail on the incoming code and pass on the final tree, and every gate above was re-run after them.

A reviewer who considers any change to the confirmation path material may still want to check R1. The diff is three lines.

## 7. Exact tests and results

| Item | Result |
|---|---|
| `work/c1/review6/probe_n1.py` (11 attacks) | 11 passed; outputs `INTERLEAVE_RESULTS ['TurnError:SERVER_REFUSED:TURN_CAPACITY','SETTLED_VERIFIED'] EFFECTS 1` and `STALLED_READER_RESULTS {B,A both SETTLED_VERIFIED} EFFECTS 2` |
| `work/c1/review6/probe_n2.py` | 48 runs, 0 violations (`probe_n2.json`) |
| `work/c1/review6/probe_n3.py`, `probe_n3_b5.py` | 10 passed, 1 passed |
| `work/c1/review6/probe_n4.py` | incoming code: 3 failed (C1 alias confirmation, C2 alias options, C8 pre-existing path answer), 5 passed (`probe_n4_incoming.xml`); final tree: all pass except C8/C8b, which pin the pre-existing path-answer refusal (`probes_final.xml`) |
| `parse_codex` with `item.started` only, then quota | `quota_exhausted`, `tool_calls 0` |
| `test_phase1_final_closure.py` on the final tree | 8 passed |
| Same module with the incoming `_provenance` patched in (`-p incoming_patch`) | the 3 provenance tests fail (`KeyError: 'arguments'`, `KeyError: 'options'`, bound assertion) |
| Gate chain | §3 (`work/c1/review6/chain.log`, `focused_final.xml`, `closure5_final.xml`, `closure6_final.xml`, `c5_live.log`, `full_final.xml`/`.log`) |

New regression tests in `test_phase1_final_closure.py`:

- `test_truncated_provenance_does_not_strip_the_confirmation_the_user_must_see` (R1).
- `test_truncated_provenance_does_not_strip_clarification_options` (R1).
- `test_provenance_stays_within_its_bound_under_pressure` (R2, plus audit fields kept).
- `test_checkpoint_crash_before_consumption_dispatches_nothing_and_stays_one_continuation` (N1).
- `test_checkpoint_crash_after_consumption_or_claim_then_restart_is_consumed[after_consumption|after_claim]` (N1).
- `test_wide_shadow_set_never_runs_before_the_isolated_mode_gate[source|sourceless]` (N2).

## 8. Final working-tree state

`HEAD` is `e8e3b65` (detached), with every change uncommitted. Relative to the candidate checkpoint:

- `uri_core/client_runtime/turn_runner.py` is modified (R1, R2).
- `test_phase1_final_closure.py` is added.
- `docs/plans/PHASE1_FINAL_CLOSURE_REPORT.md` (this report) is added.
- `docs/plans/PHASE1_FIFTH_REVIEW_REPORT.md` is unchanged from its on-disk state (its §12 line predates this review).

Probe modules and logs are under `work/c1/review6/` (git-ignored, preserved). No preserved evidence was deleted; scratch plant directories created by the N2 probe were removed by the probe itself.

## 9. Final checkpoint

See §11. It was written after the archive was built, so the on-disk report differs from the archived copy only by that section, as in earlier reviews.

## 10. Verdict

**A. PHASE 1 CORE FREEZE ACCEPTED.**

Phase 1 Core is independently accepted for freeze, subject only to the documented limitations (§4 and the fifth review's §10). N1, N2 and N3 survived independent attack. N4 had two defects introduced by the fifth review: an aliasing bug that blanked the confirmation the user must see, and an unenforced size bound. Both were reproduced, repaired at one function, covered by regressions that fail on the incoming code, and every gate was re-run clean. The repair restores previously accepted envelope behaviour and touches only a client-private record that nothing reads, so it does not need another review cycle.

## 11. Final checkpoint identity

CHECKPOINT_PLACEHOLDER
