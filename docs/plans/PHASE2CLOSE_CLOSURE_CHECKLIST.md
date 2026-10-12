# Phase 2 closure checklist

Date 2026-10-08. Each line has a binary criterion. "Result" is filled only from cited evidence; PENDING means the
evidence does not exist yet. Phase 2 is ACCEPTED AND QUALIFIED only when every line is PASS.

The final chain is `E:phase2close\run9\` (report record H6); its results are entered below.

Evidence root `E:` = `C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\`.

## A. Technical closure (automatable)

| # | Criterion | Pass when | Result | Evidence |
|---|---|---|---|---|
| A1 | Tree starts from the accepted candidate | every tree file of `phase2ops-candidate-20261008-r6.zip` (SHA-256 `9a0be52c...affb50a`) byte-identical before closure work, except the report's appended acceptance record | PASS | closure report section A |
| A2 | Frozen Phase 1 untouched | `tests/phase2a/test_frozen_core.py` passes (checkpoint hash + byte-identity + no stray file) | see A6 | phase2 gate log |
| A3 | LOG-3 repaired | an error body of any size/chunking retains <= 4096 bytes; negative control on r6 code exceeds the bound | PASS (r6 peak 4,209,676 B; repaired < 1 MiB including the test's own allocations) | `test_log3_*`; closure report section C |
| A4 | VAL-1 cause established or uncertainty preserved | a deterministic reproduction yields the historical signature, and the residual uncertainty is stated | PASS (mechanism); historical instance UNATTRIBUTABLE (stated) | `test_val1_clock_boundary.py` |
| A5 | New defects found during closure are repaired or recorded | CAP-1, ISO-1 repaired with regression tests that fail on the incoming code; EXE-1 recorded as BLOCKED with options | PASS | closure report section C |
| A6 | Phase 2 regression | `phase2d_regression.py phase2`: 0 failed, 0 errors, inside ONE green sequential full chain on the final tree (review round 1, D3) | PASS (452 passed, 2 skipped, 0 failed) | `E:phase2close\run9\phase2_all.log`, `chain_summary.json` |
| A7 | Phase 1 authority | 134 passed (same final chain) | PASS (134) | `E:phase2close\run9\phase1_authority.log` |
| A8 | Phase 1 full | 2675 passed / 12 skipped / 11 failed with the SAME failure IDs as the round-7 baseline (same final chain) | PASS (2675 / 12 / 11, SAME_FAILURE_SET) | `E:phase2close\run9\phase1_full.log` |
| A9 | Flutter | all tests pass (same final chain) | PASS (195 / 2) | `E:phase2close\run9\flutter_all.log` |
| A10 | Live Dart -> worker -> server | 10/10 runs pass; refusal lines collected (same final chain) | PASS (10/10, 0 refusal lines) | `E:phase2close\run9\ui_bridge_live_*.json`, `refusals.txt` |
| A11 | Native Codex lifecycle + mid-run cancel (in-process, owner shell login; NOT the worker process) | lifecycle `completed/SETTLED_VERIFIED`; cancel `uncertain/CANCELLED_AFTER_DISPATCH`, executor `DEAD` (same final chain) | PASS (completed/SETTLED_VERIFIED; uncertain/CANCELLED_AFTER_DISPATCH, DEAD) | `E:phase2close\run9\native\`, `native_codex_stdout.txt` |
| A12 | Independent review of the closure changes | Codex (or another independent reviewer) accepts, or every finding is repaired and re-reviewed | PASS: Codex round 6 `PHASE 2 CLOSURE ACCEPTED — PHYSICAL/OWNER GATES PENDING` on `-f` (`fcd0d72e...71298`); open Low: K1/SUP-1, D8 | `E:phase2close_review\round6\CODEX_REVIEW_round6.md` |
| A13 | Power-loss harness ready (plumbing only; never a physical verdict) | unit tests + SIMULATED end-to-end pass; SIMULATED output labelled so; host writes SERIES verdicts only; `assess` never returns qualified (review round 1, D2) | PASS (tests in the final chain; plumbing only) | `tests/phase2close/test_powerloss_harness.py` |
| A14 | Acceptance tooling ready | preflight `ready_for_session: true`; provision works; qualify fails closed without client-profile login | PASS | `E:phase2close\acceptance_preflight.json`; campaign `acceptance-20261008-045345` |

## B. Physical and owner gates (cannot be automated)

| # | Criterion | Pass when | Result |
|---|---|---|---|
| B1 | PA-1..PA-7 human acceptance | owner records PASS for each in the campaign ledger | PENDING |
| B2 | PA-8/PA-9 client-profile logins | `qualify` returns `persisted: true` for the owner's chosen providers | PENDING |
| B3 | PA-10 native execution inside the worker | EXE-1 decided and implemented; PA-5 performed from the real app | BLOCKED (EXE-1) |
| B4 | PA-11 power loss | `phase2close_powerloss_harness.py assess` over the FULL and NORMAL series DIRECTORIES returns `EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION` (recomputed from raw `acks.jsonl`: FULL >= 200 replayed iterations all PASS; NORMAL control loses >= 1 acknowledged step), AND the owner attests the power method was a real hypervisor power cut and records PA-11 PASS | PENDING |
| B5 | C6 owner decisions 1-3 | decisions recorded | PENDING |
| B6 | Freeze authorization for Phase 2 | owner authorizes a Phase 2 freeze of a named candidate | PENDING |

## C. Verdict rule

* All A PASS, any B PENDING/BLOCKED -> `PHASE 2 TECHNICALLY READY — PHYSICAL/OWNER GATES PENDING`.
* Any A FAIL or PENDING (other than A12 while a review runs) -> `PHASE 2 PARTIAL / BLOCKED` with the failing lines.
* All A and all B PASS -> `PHASE 2 ACCEPTED AND QUALIFIED`.

A12 rule: a technically-ready verdict may be given while A12 is PENDING only if the report says so explicitly; it is
not an independent acceptance.

## D. Operational qualification (2026-10-08, `PHASE2OQ_REPORT.md`; sections A-C above unchanged)

Final chain `E:phase2oq\chain2\` + environmental control `E:phase2oq\chain2b_phase1_ollama_unreachable\`.

| # | Criterion | Pass when | Result | Evidence |
|---|---|---|---|---|
| D1 | Baseline preserved | `-f` hash matches; frozen-core passes; closure review rounds present | PASS | report section B |
| D2 | EXE-1 native Codex in the real worker | native record composes in the REAL worker; no interpreter / PATH widening / name resolution; `.cmd` record and missing sandbox mode fail closed; worker-env lifecycle + cancel pass | PASS (scripted model; PA-10 separate) | chain2 `native-worker`; `tests/phase2oq/test_exe1_native.py` |
| D3 | No silent CODEX_HOME fallback in the worker | absent / foreign / changed CODEX_HOME refused at composition and before each execution | PASS | `test_worker_codex_home_invariant`, `test_codex_home_is_rechecked_before_every_execution` |
| D4 | Failed qualification -> explicit refusal | not-logged-in profile: Approve refused `HARNESS_NOT_USABLE` before the server | PASS | chain2 `native-worker` W |
| D5 | C6 Option B | draft only; no frame, executor, approval; abandonment/restart/stale/too-long/back covered | PASS (widget) | Flutter gate 205/2 |
| D6 | SUP-1 | negative control orphans; contained host kills the suspended child | PASS | `test_sup1_self_containment.py` |
| D7 | D8 | VM iteration without guest unclean-shutdown witness -> INSUFFICIENT | PASS | `test_d8_*` |
| D8 | Phase 2 regression | 0 failed | PASS (470 / 2) | chain2 `phase2_all.log` |
| D9 | Phase 1 authority | 134 | PASS | chain2 |
| D10 | Phase 1 full | 2675 / 12 / 11 same IDs | **FAIL as recorded (17 failed: Ollama service started 09:42 outside this work); control with Ollama unreachable: 2676 / 11 / 11, SAME_FAILURE_SET; residual +1 pass = hard-coded-URL live test** | chain2, chain2b |
| D11 | Flutter, bridge x10, native in-process | all pass | PASS (205/2; 10/10, 0 refusals; SETTLED_VERIFIED + cancel DEAD) | chain2 |
| D12 | Independent review of this slice | accepted, or findings repaired and re-reviewed | PENDING | `E:phase2oq_review\` |

Physical/owner lines replacing B3 and adding new ones: B3 PA-10 -> PENDING (EXE-1 resolved; needs PA-8 + EXE-1b);
B7 PA-13 Chat handoff -> PENDING; B8 EXE-1b sandbox backend -> PENDING (owner); B9 shipping line -> PENDING (owner);
B5 C6 decisions -> 1 resolved as definition, 2 decided (B), 3 PENDING.

D-update (after independent review round 1, `PHASE2OQ_REPORT.md` sections K-L): OQ-R1-1..3 repaired with regression
tests; final chain is now `E:phase2oq\chain4\` (ALL_PASS): D8 472/2/0, D9 134, D10 PASS (2676 / 11 / 11, same IDs,
total 2698, Ollama isolated, disclosed equivalence rule), D11 PASS (205/2; 10/10; native). D12 PENDING (review round 2).

D-final: D12 PASS - Codex OQ round 7 accepted `phase2oq-candidate-20261008-g.zip` (`0b49d86d...c4cd`), final chain
`E:phase2oq\chain10\` ALL_PASS. Section B (physical/owner) unchanged: all PENDING.
