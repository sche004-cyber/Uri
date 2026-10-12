# Independent Phase 2 operational qualification review — round 6

Date: 2026-10-08. Subject: `evidence/phase2oq-candidate-20261008-f.zip`, SHA-256 `69f999bea6e17110ea824fdc95d5538a67ab804ae2be33a7b5c998c336934b9e`. I inspected the candidate and predecessor archives, live tree, gate source, stored baseline, chain9 logs and artifacts, earlier reviews, and ran the probes recorded in `reviewer_checks.py` and `reviewer_results.json` in this directory. I changed no repository file.

## A. Integrity, frozen boundary, and exact change set

The subject hash matches `ROUND6_SUBJECT.txt`. Its 441 manifest entries are exactly its 441 payload members: 154 tree files and 287 evidence files. Every payload hash matches its manifest entry, and every corresponding live tree and evidence file matches the archived bytes. HEAD is `e8e3b65259c45fc823addc3ef8969425a265bd1b` with uncommitted work. The predecessor `-e` hash is `a914d086eda82b3d4e6fd45d7430a08099354a4cb3c2d4e512fc10743552ea3f`.

Against `-e`, the exact manifest delta is **40 added, 3 changed, 0 removed**. All additions are chain9 evidence, including `chain9_stdout.txt`; their exact paths are in `reviewer_results.json`. The only changed paths are `scripts/phase2close_chain.py`, `tests/phase2oq/test_chain_equivalence.py`, and `docs/plans/PHASE2OQ_REPORT.md`. No production source changed. The accepted closure `-f` hash remains `fcd0d72e0cd91412c361edec9114e2edaebbf70ede052046b808f3c4fc571298`, round-7 remains `9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a`, and the frozen Phase 1 checkpoint remains `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`. Its 121 non-metadata payloads match live files. My independent `phase1_scope_check` found no outside-scope path or Phase 1 importer of Phase 2 packages, 98 checkpoint matches within that check, and runner argv equal to accepted `-f` plus exactly the `tests/phase2oq` ignore. The pytest ini matches accepted `-f`.

## B. Phase 1 gate and adversarial probes

**OQ-R5-1 is repaired.** `junit_integrity` now counts passed, failed, skipped, and error testcase records independently and compares all four with the parsed pytest summary. My two-record XML (one pass, one skip) is refused against a two-pass summary despite the equal total; it passes against the truthful one-pass/one-skip summary. Applying the balanced 2,677-pass/10-skip false summary to chain9's actual XML is refused. Duplicate same-outcome IDs are refused; `outcome_identity` refuses missing, added, swapped, newly failed, and newly skipped IDs.

**OQ-R5-2's specific JSON/XML binding is repaired.** At each Phase 1 gate, the baseline XML's outcomes must equal the baseline JSON map, in addition to both baseline and current XML integrity checks. The stored baseline and chain9 each have 2,698 records and 2,698 unique IDs, with 2,676 passed, 11 failed, 11 skipped, and zero errors in both their XML and logs. The stored baseline JSON equals its XML; changing only one JSON outcome breaks that equality. The current chain9 outcome map equals the baseline map for every ID. The baseline JSON's runner digest matches the accepted `-f` runner bytes; the current runner argv and ini also match their accepted bindings.

**OQ-R6-1: the Phase 1 gate ignores the pytest process exit code.** `phase2close_chain.py` records `code` but the `phase1-full` PASS expression is only `ok_ids and same_fail and c["errors"] == 0`. A process returning an internal-error or interrupted exit (for example 3) after writing a complete, otherwise matching XML and summary would be marked PASS just as exit 1 is. This is a gate counterexample, not a claim that chain9 did so; chain9 records the expected exit 1. Require the expected exit status for the historical 11 failures.

**OQ-R6-2: the gate still has no immutable baseline anchor.** I copied the baseline XML into this review directory, moved a `<skipped>` outcome from one ID to a previously passed ID, and formed a JSON map with the same two changes. The altered baseline XML still passes `junit_integrity` against the unchanged baseline log (all four category counts remain equal); its map equals the altered JSON. A current XML with those same two outcomes also passes integrity and `outcome_identity`; the current log's accepted failure IDs remain equal. Thus the Phase 1 predicates can accept a jointly altered baseline XML/JSON and corresponding run, even while a baseline pass has been lost. The actual archived baseline has **not** been altered: its bytes match this candidate and `-e`. An independent archive comparison detects this hypothetical drift, but `phase1-full` and `phase1-scope` do not bind the baseline files to that trusted digest at each gate. Pin the accepted baseline XML/JSON digests or equivalent immutable reference in the gate.

The focused `tests/phase2oq/test_chain_equivalence.py` pytest invocation could not complete under this filesystem sandbox: pytest's temporary directory under `uri-agent/work/c1/` raised `WinError 5` during test setup and session cleanup. This is not counted as a product failure. The direct parser, identity, scope, archive, and joint-tamper probes completed.

## C. Chain9 and prior dispositions

`chain9_stdout.txt` records one sequential invocation ending `ALL_PASS`; `chain_summary.json` has nine PASS gates from 13:40:41 to 14:06:25. I independently compared the archived Phase 1 XML, log, and baseline outcomes and checked the hashes of every archived chain9 file. Recorded results are phase2 **484 passed / 2 skipped**, authority **134 passed**, Phase 1 **2,676 passed / 11 skipped / the same 11 accepted failures**, Flutter **205 passed / 2 skipped**, bridge **10/10** with zero refusal lines, native completed `SETTLED_VERIFIED` with cancelled PID `DEAD`, and native-worker W refusal (`HARNESS_NOT_USABLE`), W2/W3 invalidation, scripted lifecycle completion, cancellation PID `DEAD`, and zero survivors. Phase 1 exit 1 is expected for its accepted failure set. This is a single green **recorded** full chain on the candidate's Phase 1 frozen input boundary, under the implemented predicate. The archive does not independently attest source bytes at every historical gate instant.

OQ-R1-1 through OQ-R1-3 production repairs remain byte-identical to the previous review; chain9's native-worker evidence remains consistent with them. Round-1 B–K qualifications still apply: in-process native execution is not worker PA-10; W is an unauthenticated client-profile refusal; sandbox backend choice and elevated testing belong to the owner; D8's guest witness needs physical cut attestation; Chat handoff has widget rather than device acceptance; acceptance tooling does not itself establish PA-8 through PA-13; and voice/shipping-line documents are plans, not release authority. I found no new production approval or containment bypass.

## D. Owner physical acceptance readiness

The actual chain9 artifacts are internally consistent and the two round-5 defects are fixed. The candidate is **not yet ready** as an operational candidate for owner physical acceptance because OQ-R6-1 and OQ-R6-2 leave its Phase 1 acceptance predicate incomplete. Owner PA gates and backend/shipping decisions remain open by design; I do not mark any physical gate passed.

## E. New defects

OQ-R6-1 and OQ-R6-2 are evidence-gate defects. Neither shows that chain9 actually lost a pass or used a changed baseline. They show that a later gate could pass despite an abnormal test-process exit or a jointly changed outcome baseline. Repair these predicates, add focused adversarial cases, then produce a new attributable full chain.

## F. Decision

I reject `-f` as the Phase 2 operational candidate. The recorded chain is green and the round-5 repairs work, but the whole Phase 1 gate does not yet prove the required invariant. This is not a physical qualification decision.

## DEFECTS

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| OQ-R6-1 | Gate | `phase1-full` can PASS with a non-expected pytest process exit if its XML/log predicates pass. | `scripts/phase2close_chain.py` `phase1-full` `record` expression; `reviewer_results.json` `phase1_exit_ignored`. |
| OQ-R6-2 | Gate | A jointly altered baseline XML/JSON outcome map, paired with a matching current run, passes all Phase 1 outcome checks because no accepted baseline digest is checked at the gate. | `reviewer_results.json` `joint_baseline_tamper`; `joint_tamper.xml`; `scripts/phase2close_chain.py` `phase1-full` and `phase1_scope_check`. |

## OQ DISPOSITION

| ID | Disposition | Basis |
|---|---|---|
| OQ-R1-1 | REPAIRED | Native launch layout and descriptor pins unchanged from prior repair; W3 invalidation persists. |
| OQ-R1-2 | REPAIRED | Both approval routes retain usability gating; W refuses `HARNESS_NOT_USABLE`. |
| OQ-R1-3 | REPAIRED | Windows supervisor still fails closed if self-containment is unavailable. |
| OQ-R1-4 | OPEN | One green recorded full chain exists, but OQ-R6-1 and OQ-R6-2 leave its gate proof incomplete. |
| OQ-R2-1 | PARTIALLY REPAIRED | Per-test and XML integrity checks work; abnormal exit and jointly altered baseline remain admissible. |
| OQ-R3-1 | REPAIRED | Per-ID outcome changes are refused against a fixed baseline. |
| OQ-R3-2 | REPAIRED | Accepted runner argv and ini bindings hold; the previously disclosed historical provenance limit remains. |
| OQ-R4-1 | REPAIRED | Duplicate IDs and missing XML records are refused; stored XML IDs are unique. |
| OQ-R5-1 | REPAIRED | XML and summary counts now match category by category. |
| OQ-R5-2 | REPAIRED | At each gate the baseline JSON map is rebound to its XML; OQ-R6-2 concerns the pair's independent immutability. |

## NOT VERIFIED

I did not rerun the approximately 25-minute full chain, log in or out, inspect credential files, run real-model worker PA-10, use an elevated sandbox, perform owner UI/device acceptance, power-cut a VM, inspect a shipping remote, or attest exact source bytes during each past chain9 step. The failed focused pytest invocation is a sandbox temporary-directory failure, not product evidence. The joint-tamper and alternate-exit probes are controlled counterexamples, not claims about chain9's actual run. I made no repository edit, global configuration change, commit, push, merge, or process kill.

## FINAL VERDICT

PHASE 2 OPERATIONAL CANDIDATE REJECTED
