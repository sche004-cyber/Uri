# Independent Phase 2 operational qualification review — round 4

Date: 2026-10-08. Subject: `evidence/phase2oq-candidate-20261008-d.zip`, SHA-256 `822c49be4e9841cacfe824d91d4a64fbb4c8da7f92f350dc27933cb9dedd0b8b`. I reviewed the archive, live tree, accepted `-f` runner, accepted log, outcome baseline, chain7 artifacts, and gate source. Independent read-only checks and synthetic probes are in this directory (`reviewer_checks.py`, `reviewer_results.json`, `collision_case.xml`). I changed no repository file, did not read credentials or change account settings, and did not log in, stop another process, commit, or push.

## A. Integrity, frozen boundary, exact change set

The subject hash matches `ROUND4_SUBJECT.txt`. The archive has 361 manifest entries: 154 tree files and 207 evidence files. Member names equal the manifest after excluding the four archive metadata files (`MANIFEST.json`, `GIT_DIFF.patch`, `GIT_HEAD.txt`, `GIT_STATUS.txt`); all 361 payload hashes match, and all 154 live tree files match their archive payloads. HEAD is `e8e3b65259c45fc823addc3ef8969425a265bd1b`, with uncommitted changes. The rejected `-c` hash remains `a2c11441bb51975fcb3fbbec84f89760d13f24e9f815d2f13d9e88452f049602`; accepted closure `-f` remains `fcd0d72e0cd91412c361edec9114e2edaebbf70ede052046b808f3c4fc571298`; round-7 `phase2ops-candidate-20261008-r6.zip` remains `9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a`. The frozen Phase 1 checkpoint hash is `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`; its 121 non-metadata tree payloads match the live tree byte for byte.

Against `-c`, the exact manifest delta is **43 added, 3 changed, 0 removed**. The changed files are `scripts/phase2close_chain.py`, `tests/phase2oq/test_chain_equivalence.py`, and `docs/plans/PHASE2OQ_REPORT.md`. All 43 additions are evidence: chain7 (including stdout), the outcome-baseline run's XML/log, and `phase1_outcome_baseline.json`. The complete added-path list is in `reviewer_results.json`. No production source or frozen payload changed from `-c`.

## B. OQ-R3-1: per-test outcomes and adversarial gate probes

The real outcome baseline and chain7 JUnit XML each contain **2,698 testcase records and 2,698 unique `classname::name` keys**, with no collisions. The baseline JSON is an exact outcome mapping of its archived XML. Chain7 has the same 2,698 keys and outcomes: 2,676 passed, 11 failed, 11 skipped. Re-running `outcome_identity` on the archived chain XML returns true with no missing, added, or changed IDs. Controlled map probes for missing and added IDs, a lost pass, a new failure, a new skip, and a pass/skip swap all return false. This repairs the round-3 counterexample for unique JUnit keys.

**New defect OQ-R4-1:** `junit_outcomes` stores testcase records in a dictionary keyed only by `classname::name`; another testcase with the same key and outcome overwrites the first. `outcome_identity` then compares only the dictionaries. The `phase1-full` pass predicate does not check raw JUnit testcase count or the pytest result counts. I created two distinct pytest files, `a.b/test_same.py` and `a/b/test_same.py`, under this review directory and ran them with pytest's `--import-mode=importlib`. Pytest reported two passes, but its real JUnit XML gave both the identical key `evidence.phase2oq_review.round4.collision_case.a.b.test_same::test_same`. A separate synthetic XML with two passes under one key plus one skip has three records, two dictionary keys, and `outcome_identity` **accepts** it against a two-test baseline. Thus an added test with a colliding JUnit key and the same outcome can pass the `phase1-full` gate. The actual chain7 XML does not have this defect's triggering collision. The Phase 1 scope gate would separately reject an added repository file outside its allowed scope; it does not make the per-test parser injective or check dynamically added testcases. The mandate asks the Phase 1 gate to reject any added test, so this is a blocking gate defect.

The parser does flag a duplicate key with a *different* outcome as `conflict` in the tested case. The defect is duplicate records with the same outcome. A repair must check raw testcase count and uniqueness of JUnit keys (or use an injective pytest node ID) for both baseline creation and every gate run, with a regression test using a real pytest collision. It should also compare parsed outcome totals with the pytest summary.

## C. OQ-R3-2: accepted-runner provenance and scope

The baseline records SHA-256 `33463411b5b704241ae76a71d67b4636dd78755ca18213592c0b9181629189d9`, which I recomputed from `scripts/phase2d_regression.py` inside accepted `-f`. Its recorded argv equals the accepted runner's captured `phase1-full` argv plus `--ignore=tests/phase2oq`, `-rfEsp`, and the JUnit output option. The current runner's captured Phase 1 argv equals the accepted argv plus exactly that ignore. A source diff between the two runners consists solely of appending `tests/phase2oq` to `PHASE2`; that directory was absent in `-f`. The current pytest ini equals the accepted ini byte for byte. Running `phase1_scope_check` independently reports zero outside-scope files, zero Phase 1 importers of Phase 2 packages, 98 checkpoint matches in the scope check, and runner argv equality. A modified current runner selecting another Phase 1 input or a modified ini fails the current special-case logic; the actual tree has neither change.

The accepted log anchor has the same 11 failure IDs and 2,698 total tests. The baseline run has 2,676 passed, 11 skipped, 11 failed; it introduces no skip-summary kind. The one accepted skip that disappears is `test_gemma_worker_mcp.py:329`, with a named pass in the baseline run. The baseline was made by a **new** run of the accepted runner on verified current inputs, not by extracting per-test outcomes from the accepted closure run (which did not retain JUnit outcomes). This disclosed residual limitation is acceptable as provenance for the 2,698 recorded unique outcomes, subject to the collision defect in B. The `--ignore=tests/phase2oq` addition is justified by that directory's absence in `-f` and the runner diff.

## D. Chain7 and prior dispositions

`chain7_stdout.txt` is one sequential invocation ending `ALL_PASS`; `chain7/chain_summary.json` has all gates passing. Individual logs and XML agree with phase2 **480 passed, 2 skipped**; authority **134 passed**; Phase 1 **2,676 passed, 11 skipped, the same 11 pre-existing failures**, and exact outcome identity with the new baseline; Flutter **205 passed, 2 skipped**; bridge **10/10** with zero recorded refusal lines; native lifecycle `SETTLED_VERIFIED` and cancellation PID `DEAD`; and native-worker W refusal, W2/W3 invalidation, verified scripted lifecycle, cancelled PID `DEAD`, zero survivors. The 11 Phase 1 failures remain accepted historical failures; chain7 is green under its recorded predicate, which has OQ-R4-1. The archive and present tree match, though the chain lacks a source digest at each historical gate step.

OQ-R1-1 through OQ-R1-3 production repairs are unchanged from `-c`; no new production file changed here. The archived native-worker evidence is consistent with their earlier dispositions. Round-1 B–K limitations still hold: in-process native execution does not substitute for worker PA-10; the client-profile W record is unauthenticated; sandbox backend and owner physical checks remain pending; D8 has a guest witness but needs physical cut attestation; Chat handoff is widget-tested, not device-accepted; voice and shipping-line items are plans. I found no new production approval or containment bypass. OQ-R1-4 has a single recorded green chain, but the gate proof required to close it is incomplete because of OQ-R4-1.

## E. New defects

OQ-R4-1 is a release-evidence defect. It is demonstrated with real pytest output and a direct function probe; it is not evidence that chain7 actually omitted or added a test. It invalidates the unconditional claim that the Phase 1 gate rejects every added test. The archived run has no colliding keys, which narrows the immediate risk, but the gate currently accepts such a case and has no guard against future collisions.

## F. Decision

The subject is internally consistent, and the recorded chain is one green full chain on the archived tree. The per-test gate fixes the round-3 pass/skip swap but still allows an added testcase when JUnit identity collides. Under the mandate's explicit added-test condition, the candidate is not ready for owner physical acceptance. Fix the parser or identity and rerun an attributable full chain. This review does not claim physical qualification.

## DEFECTS

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| OQ-R4-1 | Gate | Duplicate JUnit `classname::name` records with the same outcome collapse to one dictionary entry; an added colliding testcase passes `outcome_identity`, and `phase1-full` does not check raw testcase count. | `scripts/phase2close_chain.py` `junit_outcomes`, `outcome_identity`, `phase1-full`; `collision_case.xml` from two real pytest node IDs; `reviewer_results.json` `collision_probe.gate_accepts_extra_same_id=true`. |

## OQ DISPOSITION

| ID | Disposition | Basis |
|---|---|---|
| OQ-R1-1 | REPAIRED | Vendored native layout and descriptor pins unchanged from prior reviewed production code; W3 invalidation persists. |
| OQ-R1-2 | REPAIRED | Both approval paths retain pre-approval usability gating; W refuses `HARNESS_NOT_USABLE`. |
| OQ-R1-3 | REPAIRED | Windows supervisor still fails closed when self-containment is unavailable. |
| OQ-R1-4 | OPEN | One green chain exists, but its Phase 1 gate has OQ-R4-1. |
| OQ-R2-1 | PARTIALLY REPAIRED | Exact unique-key outcome identity prevents the prior missing/lost-pass offsets; duplicate JUnit keys can hide an added testcase. |
| OQ-R3-1 | REPAIRED | Per-test identity rejects the round-3 same-key pass/skip swap; actual XML has unique keys. |
| OQ-R3-2 | REPAIRED | Baseline runner hash and argv bind to accepted `-f`; current runner and ini check against `-f`; residual new-run limitation disclosed. |

## NOT VERIFIED

I did not rerun the roughly 25-minute full chain, log in, inspect credentials, run real-model worker PA-10, use an elevated sandbox, perform owner UI/device acceptance, power-cut a VM, inspect a shipping remote, or attest exact source bytes at each historical chain7 gate. The synthetic collision probe is a gate counterexample, not a claim that chain7 had a collision. All actual archived Phase 1 JUnit records were checked for uniqueness.

## FINAL VERDICT

PHASE 2 OPERATIONAL CANDIDATE REJECTED
