# Independent Phase 2 operational qualification review — round 7

Date: 2026-10-08. Subject: `evidence/phase2oq-candidate-20261008-g.zip`, SHA-256 `0b49d86d89b26d3332fcbfbc9b4b7b981cdc1075d5dc295588a5cef92a82c4cd`. I inspected the candidate, rejected predecessor, live tree, gate source, stored baseline, chain10 logs and artifacts, and prior reviews. I ran the direct checks recorded in `reviewer_checks.py` and `reviewer_results.json` in this directory. I changed no repository file.

## A. Integrity and exact change set

The subject hash matches `ROUND7_SUBJECT.txt`. Its 481 manifest entries are exactly its 481 payload members: 154 tree files and 327 evidence files. Every payload hash matches its manifest, and every archived tree and evidence file matches its live counterpart. HEAD is `e8e3b65259c45fc823addc3ef8969425a265bd1b` with uncommitted work. Against rejected `-f` (`69f999bea6e17110ea824fdc95d5538a67ab804ae2be33a7b5c998c336934b9e`), the exact manifest delta is **40 added, 3 changed, 0 removed**. All additions are chain10 evidence, including `chain10_stdout.txt`; their paths are listed in `reviewer_results.json`. The changed files are only `scripts/phase2close_chain.py`, `tests/phase2oq/test_chain_equivalence.py`, and `docs/plans/PHASE2OQ_REPORT.md`. No production source changed.

The accepted closure `-f` remains SHA-256 `fcd0d72e0cd91412c361edec9114e2edaebbf70ede052046b808f3c4fc571298`, round-7 remains `9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a`, and the frozen Phase 1 checkpoint remains `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`. All 121 frozen payloads match the live files. My independent `phase1_scope_check` found no outside-scope path or Phase 1 importer of Phase 2 packages, 98 checkpoint matches within that check, and runner argv equal to accepted `-f` plus exactly `--ignore=tests/phase2oq`. The pytest ini equals accepted `-f`.

## B. Phase 1 gate and adversarial probes

**OQ-R6-1 is repaired.** The `phase1-full` PASS expression now requires `code == PHASE1_EXPECTED_EXIT`, whose value is 1 for the accepted 11 test failures. In the direct predicate probe, 0, 2, 3, 4, 5, and `TIMED_OUT` are refused; 1 is accepted. Chain10 records exit 1. This check is part of the actual `record` predicate, not only a source-comment or test assertion.

**OQ-R6-2 is repaired.** The reviewed gate source pins SHA-256 for the baseline JSON, XML, and log. The actual files match all three pins. A copied baseline with a pass/skip swap still has valid JUnit integrity and unchanged category counts, but `baseline_pins_hold` returns false. The pin result is conjoined into `ok_ids` at every `phase1-full` gate. The baseline JSON still equals the baseline XML's per-ID map.

I rechecked the whole Phase 1 outcome gate. Both baseline and chain10 XML have 2,698 testcase records and 2,698 unique IDs; both XML category counts equal their logs: 2,676 passed, 11 failed, 11 skipped, zero errors. Chain10's outcome map equals the pinned baseline map for every ID, and its failed-ID set equals the accepted log's. Direct `outcome_identity` probes refuse a missing ID, added ID, lost pass, pass/skip swap, new failure, and new skip. `junit_integrity` refuses a duplicate ID and a two-record XML whose pass/skip counts disagree with the summary despite an equal total. The accepted runner source digest matches the baseline JSON's runner digest; current runner argv and ini match their accepted bindings. The scope check passes. I found no remaining way within these checked predicates for the specified missing, added, lost-pass, swapped, newly failing, newly skipped, or altered-baseline case to pass.

The focused `tests/phase2oq/test_chain_equivalence.py` invocation did not complete: pytest's temporary directory under `uri-agent/work/c1/oq_round7_pytest` raised `WinError 5` during setup and session cleanup. I do not count it as a product failure or as passing test evidence. The direct parser, identity, archive, scope, pin, and joint-tamper probes completed.

## C. Chain10 and previous findings

`chain10_stdout.txt` records one sequential invocation ending `ALL_PASS`; `chain_summary.json` has all nine gates PASS from 14:12:09 to 14:37:52. The manifest hashes and live bytes of every archived chain10 file agree. Recorded results are phase2 **486 passed / 2 skipped**, authority **134 passed**, Phase 1 **2,676 passed / 11 skipped / the same 11 accepted failures** with expected exit 1, Flutter **205 passed / 2 skipped**, bridge **10/10** with zero refusal lines, native completed `SETTLED_VERIFIED` with cancelled PID `DEAD`, and native-worker W refusal (`HARNESS_NOT_USABLE`), W2/W3 invalidation, scripted lifecycle completion, cancellation PID `DEAD`, and zero survivors. This is a single green **recorded** full chain on the `-g` candidate's pinned Phase 1 input boundary. The archive does not independently attest source bytes at every historical gate instant.

OQ-R1-1 through OQ-R1-3 production repairs remain byte-identical to the previous review; chain10's native-worker evidence remains consistent with them. The round-1 B–K qualifications still hold: in-process native execution does not establish worker PA-10; W is an unauthenticated client-profile refusal; sandbox backend choice and elevated testing remain the owner's; D8's guest witness needs physical cut attestation; Chat handoff has widget rather than device acceptance; acceptance tooling does not establish PA-8 through PA-13; and voice/shipping-line documents remain plans, not release authority. I found no new production approval or containment bypass.

## D. Owner physical acceptance readiness

The candidate is **ready for owner physical acceptance** as an operational candidate. The evidence gate repairs are effective, the final recorded chain is green, and the frozen boundary and accepted closure anchors hold. PA-8 through PA-13, backend choice, physical VM cut, device checks, client-profile authentication, real-model worker qualification, and shipping decisions remain open for the owner by design. This review grants no physical qualification or release authority.

## E. New defects

None found in this review. The focused pytest temporary-directory denial limits that one independent test invocation; it does not contradict the direct probes or the archived phase2 run.

## F. Decision

I accept `-g` as the Phase 2 operational candidate for owner physical acceptance. This is not Phase 2 physical acceptance or qualification.

## DEFECTS

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| None | — | No new or remaining operational candidate defect found. | `reviewer_results.json`; chain10 archive and logs. |

## OQ DISPOSITION

| ID | Disposition | Basis |
|---|---|---|
| OQ-R1-1 | REPAIRED | Native layout/descriptor pins unchanged from prior repair; W3 invalidation persists. |
| OQ-R1-2 | REPAIRED | Both approval routes retain usability gating; W refuses `HARNESS_NOT_USABLE`. |
| OQ-R1-3 | REPAIRED | Windows supervisor still fails closed if self-containment is unavailable. |
| OQ-R1-4 | REPAIRED | One sequential full chain records all nine gates PASS under the repaired Phase 1 predicate. |
| OQ-R2-1 | REPAIRED | Per-test outcomes, summary categories, expected exit, pinned baseline, scope, and runner checks hold. |
| OQ-R3-1 | REPAIRED | Per-ID outcome changes, including a balanced pass/skip swap, are refused. |
| OQ-R3-2 | REPAIRED | Accepted runner digest/argv and ini bindings hold; disclosed new-run baseline provenance limit remains. |
| OQ-R4-1 | REPAIRED | Duplicate IDs and missing XML records are refused; stored XML IDs are unique. |
| OQ-R5-1 | REPAIRED | XML and summary counts agree category by category. |
| OQ-R5-2 | REPAIRED | Baseline JSON is rebound to XML at each gate. |
| OQ-R6-1 | REPAIRED | `phase1-full` PASS requires exit 1; abnormal exits fail. |
| OQ-R6-2 | REPAIRED | Baseline JSON, XML, and log digests are pinned in reviewed gate source and checked at each run. |

## NOT VERIFIED

I did not rerun the approximately 25-minute full chain, authenticate or read credential files, run real-model worker PA-10, use an elevated sandbox, perform owner UI/device acceptance, power-cut a VM, inspect a shipping remote, or attest exact source bytes during each past chain10 step. The focused pytest invocation was blocked by sandbox temporary-directory access and provides no test verdict. The hypothetical exit and joint-tamper probes are controlled counterexamples, not claims about chain10's actual run. I made no repository edit, global configuration change, commit, push, merge, login/logout, or process kill.

## FINAL VERDICT

PHASE 2 OPERATIONAL CANDIDATE ACCEPTED — READY FOR OWNER PHYSICAL ACCEPTANCE
