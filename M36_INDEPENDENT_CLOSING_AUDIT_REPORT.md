# M36 URI-Memory Minimum — Independent Closing Audit Report

**Verdict: PASS_WITH_BOUNDED_REPAIRS** (not freeze-ready until repairs R-1…R-4 land and are requalified; R-5/R-6 are documentation/advisory)

- Auditor: Claude Code, fresh independent session (not the implementer; Codex implemented). Read-only audit; the only file written in the repository is this untracked report. No repair, commit, push, freeze, or governance edit was performed.
- Date: 2026-09-28.
- Audit target: commit `be4451c6fda7803a742e0ad48c7fec63140ec30b` ("feat(memory): implement M36 minimum with grounded qualification").
- Evidence classes used below: **OBSERVED** (I ran it or read it at `be4451c`), **INFERENCE** (reasoned from observed code, not executed), **CLAIM** (stated by Codex/governance, not independently reproduced).

## 1. Acceptance criteria (defined before evaluation)

- AC-1 Repository identity: `be4451c` exists, HEAD equals it, dirty state recorded.
- AC-2 Every M36 requirement (plan §0 PA-*, §5 R1–R11, §7, §11 Q-*, §17 F-1…F-11 / Q-A2-1…11, §18 A3 A–G, §19 A4 H1–H3, §12/§14 exit criteria) classified VERIFIED / PARTIAL / CLAIMED_ONLY / MISSING with file:line evidence.
- AC-3 M36 tests, qualification driver, frozen/governance checks, and full tracked suite re-run; counts compared to Codex's claims; environment gaps separated from real failures.
- AC-4 `git diff` against the M36 base and frozen M33.3 baseline shows no frozen or unrelated file touched.
- AC-5 Memory durability/correctness risks checked: restart persistence, corruption, concurrent writes, schema, privacy, and harness claims staying CLAIMED_ONLY.
- AC-6 Every repair is bounded, names file / problem / minimal fix / acceptance check, and is not performed.

## 2. Repository state (OBSERVED)

| Item | Value |
|---|---|
| Worktree | `C:/Users/cheta/Development/Uri/_V1` (`git worktree list`; same repository as `uri-agent` master `e8e3b65`, plus two Codex audit worktrees and one preserved baseline) |
| Branch | `m35-uri-v1-parallel-architecture` |
| HEAD | `be4451c6fda7803a742e0ad48c7fec63140ec30b` — **HEAD == be4451c** |
| Parent (M36 implementation base) | `23f5cd9a5f1ac5d17d431c7a76a15533e5c570a4` (A4 plan commit) |
| Frozen M33.3 baseline | `291c9daa48435200c4b56857d0e3bc630016e82a` |
| `git status` | 158 entries: `M SKILL.md` (pre-existing, trailing whitespace at 581/582) and 157 untracked pre-existing M35/research paths. No tracked M36 file is dirty, so the working tree equals `be4451c` for all audited code. This report adds one untracked file. |

## 3. Frozen-boundary and scope check (OBSERVED)

- `git diff --name-status 291c9da be4451c -- . ':!docs' ':!PROJECT_MEMORY.md' ':!URI_MILESTONE_TRACKER.md'` → only **added** files: `uri_v1/memory/**` (12), `tests/test_m36_memory_*.py` (9), `scripts/m36_memory_qualification.py`, `fixtures/m36_memory/{battery,threshold_gate}.json`. No modification or deletion of any existing code, test, script or fixture.
- `git show --stat be4451c`: 44 files; the only modified pre-existing files are governance (`PROJECT_MEMORY.md`, `URI_MILESTONE_TRACKER.md`, `docs/governance/URI_ACTIVE_MILESTONE.md`, `docs/governance/URI_STATE.yaml`, `docs/plans/M36_STATE.md`). The M36 plan itself was not edited. No unrelated dirty/untracked work was included.
- `python scripts/m33_3_r_anchors.py` → `{'ok': True, 'changed': [], 's4_anchor_count': 8, 'frozen_lf_anchor_count': 24, 'current_rar_sha256': '4db77566…5e1b95'}` (matches Codex's claim).
- `git diff --check 23f5cd9 be4451c` → clean. Repository-wide `git diff --check` → only pre-existing `SKILL.md:581/582`.
- `python scripts/governance/uri_state_validator.py` → `VALID … no DCL violations`.
- **Result: AC-4 met.** No CLOSED_FROZEN file (M33.3 S1–S12, RAR contracts, `rar_deterministic.py`, `user_storage.py`, S4 script, Batch A battery) was touched.

## 4. Test evidence

| Command (cwd `_V1`, `PYTHONDONTWRITEBYTECODE=1`, Python 3.13.15, tzdata present) | My result (OBSERVED) | Codex claim | Match |
|---|---|---|---|
| `python -m pytest tests/test_m36_memory_{adversarial,contracts,grounding,qualification,retrieval,sources,storage,support,verifier}.py -q -p no:cacheprovider -rs` | **91 passed**, 0 skipped, 16.66 s | 91 passed, no skips | Yes |
| `python scripts/m36_memory_qualification.py --output <scratchpad>` (output redirected so tracked `docs/plans` files were not rewritten) | Exit 0. 45 cases/run × 2, **0 wrong CONFIRMED, 0 invented IDs**, deterministic=true, 22 S1 bindings, 1 S7 Change, 1 S11 version, 16 Memory records, correction pair [true,true], VERIFIED verifier outcome, DERIVATIVE_STALE after edit, forced worker kill + new-process discovery true. Retrieval p50 10.2 ms / p95 15.9 ms | Same aggregates; p50 10.49 / p95 14.34 ms | Yes (latency varies, not gated) |
| `python -m pytest <28 tracked files: tests/test_m33_3*.py tests/governance/*.py tests/test_uri_v1*.py tests/test_m36*.py> -q` | **559 passed**, 0 failed | (different scope: Codex "relevant" set 1,002 passed / 58 skipped) | Not directly comparable; no failure in frozen M33.3 / governance / M36 |
| `python -m pytest <all 258 tracked test_*.py files outside uri_ui> -q -p no:cacheprovider -rfE` | **3,351 passed, 11 failed, 65 skipped, 218 subtests**, 501.35 s | 3,260 passed, 11 failed, 65 skipped, 218 subtests (249 files) | Failures: identical 11 node IDs. Passed count differs by exactly +91 = the M36 suite (my inventory is 258 tracked files incl. the 9 M36 files; Codex's 249-file inventory evidently excluded them, which Codex covered separately). No new failure. |

The 11 failures (all outside `uri_v1/memory`, none importing it; Codex also reproduced them at the pre-M36 base `23f5cd9`): `test_capability_directory.py` credential-filename privacy test; five M20 feasibility/recovery/semantic-interpreter tests; two `test_m33_2_batch_b2_perception_benchmark.py` corpus SHA tests; `test_orchestrator_session_workflow.py::…session_facts…`; `test_usage_import_boundary.py::test_orchestrator_newline_count_does_not_increase`; `test_workflow_restart_recovery.py::…survives_restart…`. I did not independently re-run them at `23f5cd9`; since M36 commit adds files only and no test file outside `tests/test_m36_memory_*.py` references `uri_v1.memory` (OBSERVED by grep), they are classified pre-existing baseline failures, not M36 regressions. The full repository is **not green**.

Environment notes: `tzdata` is installed in this Python (Codex installed `tzdata==2026.4`; not a project dependency). Without it, temporal queries fail closed as `TIMEZONE_REQUIRED` (retrieval.py:53–54) — an environment gap, not a code failure.

## 5. Requirement table

Status key: VERIFIED = code read + test/driver/probe observed; PARTIAL = implemented but a concrete gap observed; CLAIMED_ONLY = only asserted; MISSING = absent.

| # | Requirement (plan §) | Status | Evidence (at `be4451c`) |
|---|---|---|---|
| 1 | PA-3/T-FROZEN: no frozen M33.3 change | VERIFIED | §3 above; anchors ok; AST+diff test `tests/test_m36_memory_adversarial.py:133-148` |
| 2 | PA-4/PA-5: no S13, `/ask`, agent loop, network, Office/Edge/Harness | VERIFIED | Only additive files (§3); banned-import AST check `adversarial.py:135-141`; `uri_v1/memory/__init__.py:1` |
| 3 | PA-6: no `uri_core` import; core imports only stdlib + `uri_v1.user_storage`; only `uri_adapter/` imports S1/RAR/S7/S11 | VERIFIED | `log.py:13`, `sources.py:12-13`, `envelope.py:7-9`, `links.py:2`; AST rule `adversarial.py:143-144` |
| 4 | PA-7: Memory never binds; tier copied from S1 | VERIFIED | `links.py:6-14` copies `binding.state` from S1 store; `recorder.py:90-96` requires capability-bearing `BoundReference`; `contracts.py:54-69` |
| 5 | PA-8 / D4-R1: history yes, learning no | VERIFIED | Ordering = tier, last-used time, source_id only (`retrieval.py:168-171`); no counts/weights anywhere in `uri_v1/memory` |
| 6 | §7.2 closed contracts, derived authority, SHAREABLE fail-closed, credential guard | VERIFIED | `contracts.py:221-224` (closed), `:267-286` (derive_authority), `:384` (sharing deferred), `:206-212` (credential guard), `:409-415` (forged authority rejected on load) |
| 7 | R4/R6/Q-6/Q-7: provenance, outcome honesty; harness claims stay CLAIMED_ONLY | VERIFIED | `contracts.py:271-279`; `recorder.py:137-144` rejects any extra kwargs; `index.py:143-144` claims cannot carry verifier fields |
| 8 | F-1 / Q-A2-1: exact-name collision completeness using frozen lexical semantics | **PARTIAL** | Stem normalizer drift: `retrieval.py:33-37` replaces only `[_\-]`; frozen `rar_deterministic.py:106-112` replaces `[_\.\-\/]`. Probe (below, P-6): files `a/budget-v2.xlsx` (in history) and `b/budget.v2.xlsx`; query "budget v2" → receipt `complete=True`, matching_ids = 1, candidates = `[a/budget-v2.xlsx]`, **TENTATIVE binding to a** under RECOVERABLE impact; the second frozen-stem match is hidden from clarification. No CONFIRMED (frozen `authority.py:35-43` requires verbatim title), so Q-3 holds. → R-3 |
| 9 | F-2 / Q-A2-2: causal task heads, closed transitions, no timestamp winner | **PARTIAL** | Index side VERIFIED (`index.py:85-137`, fork → CONFLICT `:31-38`). But "explicit user declaration" is a keyword bag: `recorder.py:114-119`. Probe P-2: raw "please do not mark this done yet" + status=COMPLETED → persisted, head = COMPLETED / USER_PROVIDED (terminal; only correction can undo). → R-2 |
| 10 | F-3 / Q-A2-3 / Q-10: live rediscovery, stale claims separated, missing excluded, cap/policy degraded | VERIFIED | `retrieval.py:87-102`; `context_package.py:30-53`; `sources.py:184-185`; driver DERIVATIVE_STALE + rediscovery |
| 11 | F-4 / Q-A2-4: attachment anchor only whole-turn single attachment, per-slot guard, trusted manifest | VERIFIED | `envelope.py:129-141`, `contracts.py:453-459`; tests `grounding.py:126-136,159-165`, `adversarial.py:92` |
| 12 | F-5 / Q-A2-5: structured temporal/task retrieval, no semantic search | VERIFIED | `retrieval.py:44-62,113-149`; tests `retrieval.py:35-89` (21 unrelated tasks, timezone boundaries) |
| 13 | F-6 / Q-A2-6: bootstrap-only verifier, protected receipts; negative verdicts protected; user cannot hide a verifier failure | **PARTIAL** | Registration/receipt VERIFIED (`recorder.py:35-41,146-175`; `index.py:145-157`). But `recorder.forget` (`recorder.py:236-241`) accepts any record id and `index.py:165-167,181` hides it. Probe P-1: verifier FAILED verdict tombstoned by user → `current()` empty, package `recent_outcomes` empty; a later harness claim then shows alone as the only outcome. Contradicts §17.6 ("cannot … hide a verifier failure"; "Every verdict … protected"). → R-1 |
| 14 | F-7 / Q-A2-7: containment, junction/reparse, handle identity | VERIFIED | `sources.py:33-36,92-101,111-143,153-206`; junction/symlink tests executed without skip (`sources.py` tests 25-46) |
| 15 | F-8 / Q-A2-8: framed append, fsync, exact read-back, quarantine, truthful `persisted` | VERIFIED | `log.py:152-198`, `:85-109`; fault-stage tests `storage.py:29-51`. Note (INFERENCE, plan-consistent): a failed write whose body landed fully becomes valid after the next separator repair (`log.py:164-166`); §17.8 treats this as an "uncertain" write, and same-ID retry is idempotent (`log.py:169-172`). |
| 16 | F-9 / Q-A2-9: immutable round snapshots, revalidation at use | VERIFIED | `envelope.py:97-115,151-154`; tests `retrieval.py:127`, `grounding.py:115-123` |
| 17 | F-10 / Q-A2-10 / Q-9 / R8: unknown-task discovery, HISTORICAL_BINDING, restart | VERIFIED | `index.py:183-202`; `context_package.py:42-45`; driver forced-kill + fresh process |
| 18 | F-11 / Q-A2-11 / Q-8 / R7: paired append-only corrections, pending on interruption, retry | VERIFIED | `recorder.py:184-234`; `index.py:96-118`; tests `storage.py:84-110` |
| 19 | A3 Q-A3-1 A–G: raw-turn grounding for exact title/ID projection | VERIFIED | `envelope.py:49-82,117-146`; tests `grounding.py:23-76` |
| 20 | A4 H1–H3: FREE_INPUT pre-call grounding through actual `BindingService.respond` | VERIFIED (adapter path) | `envelope.py:173-197`; `grounding.py:79-123` observes `respond()` args. Limitation (INFERENCE): frozen `BindingService.respond` remains directly callable; enforcement depends on future callers routing through the adapter (no production caller exists; S13 not authorized). |
| 21 | R2/Q-4: session tier first, durable skip | VERIFIED | `retrieval.py:103-105`; driver skip rate 100% |
| 22 | R10/Q-11: bounded package ≤8 KiB, authority labels | VERIFIED | `context_package.py:83-85`; driver max 3,2xx bytes |
| 23 | R11/Q-12: per-user isolation, task-scoped package | VERIFIED | `user_scoped_path` (`log.py:46`), cross-user rejection `log.py:104`, `index.py:69`; driver isolation check |
| 24 | Q-E2E / Q-DET | VERIFIED | Driver rerun (§4) |
| 25 | Q-LAT | PARTIAL (not a gate) | Retrieval p50/p95 reported; load/fingerprint UNMEASURED (as disclosed) |
| 26 | Hidden/system entries and usability on real folders (E-1 "real files") | **PARTIAL** | `sources.py:130-131` excludes any dot/hidden/system entry and marks the whole scan incomplete; `envelope.py:98` then withholds **every** projection, including non-exact expressions with no collision. Probe P-3: one `.hidden_cfg` in the root → "budget.xlsx" and "the notes file" both `COLLISION_SCOPE_INCOMPLETE`. Fail-closed (safe) but makes ordinary Windows folders (e.g. `desktop.ini`, `.git`) unusable. → R-4 |
| 27 | §12 item 4 freeze prerequisites (hash pins for `contracts.py`, `envelope.py`) | MISSING (expected pre-freeze) | Not recorded; correctly not claimed. Required at freeze. |
| 28 | PG-M1 final (A4) acceptance | CLAIMED_ONLY | No final A4 re-check report exists in the repo; `URI_STATE.yaml`/`M36_STATE.md` record it as User-supplied. This is User authority, not a code defect, but see R-5. |
| 29 | "Thresholds written before first qualification attempt" | CLAIMED_ONLY | Thresholds and driver land in the same commit; ordering cannot be verified from Git. Threshold SHA matches (`e5fdeff5…`). |
| 30 | E-5 Edge sufficiency / E-6 harness | Not verifiable (disclosed) | No Edge/harness plan exists; unchanged disclosure. |

## 6. Memory-specific durability and correctness checks (AC-5)

| Risk | Result |
|---|---|
| Persistence across restart | VERIFIED: forced-kill worker then fresh process restores exact head/refs/next-step/last outcome (driver); read-back before `persisted=True` (`log.py:183-195`). |
| Corruption / torn tails | VERIFIED: unterminated tail separated, never truncated; malformed lines quarantined by content-addressed id (`log.py:85-109,164-166`). |
| Concurrent writes | VERIFIED: per-user guard via frozen `locked_append` (process+thread); 4-process test (`adversarial.py:103-116`). INFERENCE (not probed): `msvcrt.LK_LOCK` gives up after ~10 s and raises; `MemoryLog.append`/recorder call `guard()` outside their `try`, so lock contention surfaces as an exception rather than `WriteResult(False, …)`. Also the frozen helper's module-global `threading.Lock` serializes every `locked_append` in the process while a guard is held (plan advisory A-3). |
| Schema / migration | VERIFIED: unknown `schema_version` rejected and quarantined (`contracts.py:380`); no migration needed (new storage). |
| Privacy / permission | VERIFIED: UUID-scoped paths; private store cannot be registered as a root (`sources.py:78`); telemetry ids/enums only. |
| Harness claims stay CLAIMED_ONLY | VERIFIED except the hide path in R-1. |
| Verifier registry across processes | VERIFIED as disclosed limitation: without bootstrap, verdicts are quarantined on load (probe P-5: `verdict_loaded_without_registry=False`, 1 quarantined). INFERENCE: a state write made in an un-bootstrapped process can fork the task head once the verdict-linked state reappears; recommend bootstrap-before-load be enforced at integration time. |

## 7. Independent probes (OBSERVED; temp directories only; scripts kept in the session scratchpad, not the repo)

| Probe | Input | Observed |
|---|---|---|
| P-1 forget verdict | FAILED verifier verdict, then `recorder.forget((verdict_id,), intake("forget that"))`, then new harness claim | `forget_persisted=True`, verdict not current, package outcomes `[]`, then only `CLAIMED_OUTCOME:CLAIMED_ONLY` shown |
| P-2 keyword transition | `task_state(status="COMPLETED", intake("please do not mark this done yet"))` | `(True, 'COMPLETED', 'USER_PROVIDED')` |
| P-3 hidden file | root with `budget.xlsx`, `notes.md`, `.hidden_cfg` | scan incomplete `HIDDEN_EXCLUDED`; exact and non-exact projections both withheld |
| P-4 tombstone head | forget the task's current `TASK_STATE` | `task()` → None, `open_tasks` → 0; task can no longer transition (no recovery path) |
| P-5 registry reload | reload with empty `_VERIFIERS` | verdict quarantined (expected, disclosed) |
| P-6 stem drift | `a/budget-v2.xlsx` in history + `b/budget.v2.xlsx`; "budget v2", RECOVERABLE | receipt complete with 1 match; TENTATIVE bound to `a`; `b` never offered |

## 8. Bounded repairs (not performed)

**R-1 (required) — User forget can hide verifier verdicts and task heads.**
- File: `uri_v1/memory/index.py:165-167` (TOMBSTONE acceptance); `uri_v1/memory/recorder.py:236-241`.
- Problem: any record id can be tombstoned, including `OUTCOME/VERIFIER_RESULT` (violates §17.6) and the current `TASK_STATE` head (wedges the task, P-4).
- Minimal fix: in `MemoryIndex.accept` for TOMBSTONE, reject targets whose kind is `OUTCOME` with provenance `VERIFIER_RESULT`, and reject `TASK_STATE` records (task-level forget should target `TASK_OPENED`, which already hides the whole task). Same check applies on load (quarantine).
- Acceptance: new test — forgetting a FAILED/PARTIAL/VERIFIED verdict returns `persisted=False` and the verdict stays in `current()` and in `build_context(...)["recent_outcomes"]`; forgetting a TASK_STATE head is rejected; forgetting TASK_OPENED still hides the task; all 91 existing tests pass.

**R-2 (required) — Explicit user transitions validated by keyword presence only.**
- File: `uri_v1/memory/recorder.py:114-119`.
- Problem: any occurrence of "done/complete/pause/cancel/…" in the raw turn, including negated or interrogative text, admits a USER_PROVIDED terminal transition chosen by the caller (P-2).
- Minimal fix: reuse the adapter's existing negation word set (`envelope.py:66`) and reject when the raw turn contains a negation word or ends with "?"; require the trigger word to appear in a trusted intake span keyed for the transition (e.g. `spans["transition"]`), not anywhere in the turn. No new parser.
- Acceptance: "please do not mark this done yet", "is it done?", "don't cancel it" → `ValueError("EXPLICIT_USER_TRANSITION_REQUIRED")`, head unchanged; "mark it done" / "pause" / "cancel this task" still accepted; transition-edge tests unchanged and passing.

**R-3 (required) — Collision stem normalizer differs from frozen RAR.**
- File: `uri_v1/memory/retrieval.py:33-37` (used by `exact_name`, which `envelope.py:102-106` also relies on).
- Problem: frozen `stem_title` also splits on `.` and `/`; Memory does not, so dotted-stem collisions are missed and the receipt is falsely COMPLETE (P-6), contrary to §17.1 "use the frozen resolver's lexical matching semantics by lineage".
- Minimal fix: change the delimiter regex to `[_\.\-\/]` and apply the extension-strip before it, byte-for-byte as `rar_deterministic.py:109-112`; add a parity test that compares Memory `stem_title` with the frozen function over a fixed title list (import of the frozen function is allowed in tests only).
- Acceptance: probe P-6 scenario yields both files in candidates and matching_ids, no TENTATIVE/CONFIRMED auto-binding; parity test passes; A3/A4 tests unchanged.

**R-4 (required for demonstrator readiness E-1; safety-neutral) — One hidden entry blocks all projection.**
- File: `uri_v1/memory/uri_adapter/envelope.py:98`; `uri_v1/memory/sources.py:130-131`.
- Problem: `_safe` withholds every projection whenever the scan is incomplete, even when the expression cannot lexically match any title/stem/ID. Plan §17.1/§18.3 require completeness only for certainty-bearing exact expressions.
- Minimal fix: in `_safe`, return `COLLISION_SCOPE_INCOMPLETE` only when the grounded expression matches (by the R-3 stem rule) any scanned title/stem or source id, or when an excluded entry is a hidden **file** whose name matches (its name is readable without following). Keep excluded directories/reparse points as incomplete for exact expressions.
- Acceptance: P-3 non-exact "the notes file" projects; P-3 exact "budget.xlsx" still withheld while a hidden directory exists; all Q-A2-1 incomplete-scan tests still pass.

**R-5 (documentation) — Governance history overwritten.**
- File: `docs/governance/URI_STATE.yaml` (M36 entry: `pg_m1_verdict`, `amendment_a4_scope`).
- Problem: `pg_m1_verdict` was changed from the original report's `PG_M1_ACCEPTED_WITH_BOUNDED_REPAIRS` to `PG_M1_ACCEPTED` while `pg_m1_report` still points to the original report; `amendment_a4_scope` still says "PG-M2 blocked". This violates the additive correction-history rule.
- Minimal fix: restore `pg_m1_verdict` to the original report's value and record the final User-supplied acceptance in a separate key (e.g. `pg_m1_final_verdict_source: USER_IMPLEMENTATION_PACKAGE`); mark the A4 scope sentence historical.
- Acceptance: validator `VALID`; governance tests pass; both verdicts visible.

**R-6 (advisory) — Lock-timeout surfacing.**
- File: `uri_v1/memory/log.py:125-126`, `recorder.py:79,101,150,188,239`.
- Problem (INFERENCE): guard acquisition failure raises instead of returning `WriteResult(False, reason)`.
- Minimal fix: catch `OSError` around `guard()` entry and return `WriteResult(False,"LOCK_UNAVAILABLE")`.
- Acceptance: a test holding the guard in a child process observes `persisted=False, reason="LOCK_UNAVAILABLE"`.

## 9. Self-review against AC-1…AC-6

- AC-1 met (§2). AC-2 met (§5; 30 rows). AC-3 met (§4; environment gap disclosed). AC-4 met (§3). AC-5 met (§6). AC-6 met (§8; nothing repaired).
- Checked for overstatement: no finding claims a wrong CONFIRMED binding — none was observed; P-6 produces TENTATIVE only. R-1/R-2 are plan-rule violations with observed reproductions, so the verdict cannot be a clean PASS. None requires redesign, a frozen-file change, or scope expansion, so FAIL is not warranted.
- Unverified: Codex's claim that thresholds preceded the first run; the final A4 PG-M1 acceptance (User-supplied); lock-timeout behaviour (R-6) and registry fork risk (§6) are inference, not reproduced; non-Windows code paths (`/proc/self/fd`) were not exercised on this Windows host.
