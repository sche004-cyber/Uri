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
