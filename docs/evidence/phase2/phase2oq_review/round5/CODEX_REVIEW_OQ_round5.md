# Independent Phase 2 operational qualification review — round 5

Date: 2026-10-08. Subject: `evidence/phase2oq-candidate-20261008-e.zip`, SHA-256 `a914d086eda82b3d4e6fd45d7430a08099354a4cb3c2d4e512fc10743552ea3f`. I examined the archive, live tree, gate code, baseline run, chain8 artifacts, earlier review findings, and my own probes. Probe files and machine-readable results are in this review directory. I did not modify the repository.

## A. Integrity and change set

The subject hash matches `ROUND5_SUBJECT.txt`. Its 401 manifest entries comprise 154 tree files and 247 evidence files. Archive payload names exactly match the manifest, all payload hashes match, and all 401 corresponding live files match their archived bytes. HEAD is `e8e3b65259c45fc823addc3ef8969425a265bd1b` with uncommitted changes. The rejected `-d` hash matches `822c49be4e9841cacfe824d91d4a64fbb4c8da7f92f350dc27933cb9dedd0b8b`. The accepted closure `-f` remains `fcd0d72e0cd91412c361edec9114e2edaebbf70ede052046b808f3c4fc571298`; round-7 remains `9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a`. The frozen Phase 1 checkpoint remains `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`, and its 121 non-metadata tree payloads equal the live tree.

Against `-d`, the exact manifest delta is **40 added, 3 changed, 0 removed**. The changed paths are `scripts/phase2close_chain.py`, `tests/phase2oq/test_chain_equivalence.py`, and `docs/plans/PHASE2OQ_REPORT.md`; the 40 additions are chain8 evidence. The full added-path list is in `reviewer_results.json`. No production source or frozen payload changed from `-d`. The independently run Phase 1 scope check reports zero outside-scope changes, zero Phase 1 importers of Phase 2 packages, 98 checkpoint matches within that check, accepted-runner argv equality plus exactly the `tests/phase2oq` ignore, and an unchanged pytest ini.

## B. OQ-R4-1 and outcome gate attacks

The new `junit_records` retains each testcase; `junit_outcomes` marks duplicate keys `conflict`; `junit_integrity` rejects duplicate keys and a testcase **total** different from the pytest summary total. I reran the real pytest collision with distinct `a.b/test_same.py` and `a/b/test_same.py`. Pytest passed both and emitted two records with one `a.b.test_same::test_same` key; the current integrity check returned false and outcome identity returned false. A duplicate-same-outcome synthetic XML, missing/added IDs, and a pass/skip swap were likewise refused. Malformed XML raises `ParseError`, so the gate cannot record a pass. OQ-R4-1's original counterexample is repaired.

The stored baseline XML and chain8 XML each have 2,698 testcase records, 2,698 unique keys, no duplicates, and totals matching their logs. The baseline JSON equals the parsed baseline XML outcome map. Chain8's map equals it exactly: 2,676 passed, 11 failed, 11 skipped, with no missing, added, changed, or conflicting ID. The baseline runner hash equals the runner bytes in accepted `-f`, and its provenance and accepted-log anchors remain as reviewed in round 4.

**New OQ-R5-1:** `junit_integrity` compares only the *sum* of the four pytest summary counts with the number of XML records. It never compares the four outcome counts separately. My two-record XML has one pass and one skip, while a supplied pytest summary says two passes and zero skips. It has unique keys, and both `junit_integrity.ok` and `outcome_identity` return true. Applying the same alteration to chain8's summary (2,677 passed, 11 failed, 10 skipped) leaves the Phase 1 gate's identity, integrity, and accepted failure-ID predicates true although XML and log disagree about one skipped test. This is a controlled inconsistency probe, **not** a claim that the archived pytest run had one. The actual archived log and XML agree. The gate does not enforce the requested count consistency in every outcome category.

**New OQ-R5-2:** At each Phase 1 gate, the stored baseline XML is checked for unique IDs and total count, but its parsed outcome map is not compared with `phase1_outcome_baseline.json`. The baseline maker made the two equal, and I verified their equality in this archive; nevertheless the gate would accept a changed JSON outcome map paired with a current run matching that map while the stored baseline XML still documents the original outcomes. The baseline run is therefore rechecked for structural integrity at every gate, but its outcome binding is not rechecked. This is a source-level counterexample for subsequent runs, not evidence of baseline alteration in this candidate.

## C. Chain8 and earlier findings

`chain8_stdout.txt` shows one sequential invocation ending `ALL_PASS`, and `chain_summary.json` marks all nine gates PASS. The archived logs and summary record phase2 **482 passed / 2 skipped**; authority **134 passed**; Phase 1 **2,676 passed / 11 skipped / the same 11 accepted failures**, with exact archived outcome identity and both JUnit structural checks true; Flutter **205 passed / 2 skipped**; bridge **10/10**, zero refusal lines; native completed `SETTLED_VERIFIED`, cancellation PID `DEAD`; and native-worker W refusal, W2/W3 invalidation, verified scripted lifecycle, cancelled PID `DEAD`, zero survivors. Phase 1's process exit 1 is expected under the historical 11-failure equivalence rule. The chain is green **under the implemented predicate**, which has OQ-R5-1 and OQ-R5-2. The archive does not provide an independently attested source digest at each historical gate step.

OQ-R1-1 through OQ-R1-3 production repairs remain byte-identical to round 4; chain8's native-worker observations remain consistent with them. OQ-R3-1's per-key outcome check and OQ-R3-2's accepted-runner binding still work for the actual recorded inputs. Round-1 B–K qualifications remain: in-process native execution is not worker PA-10; W is a not-authenticated client-profile refusal; sandbox backend choice and physical owner tests remain open; D8 guest witness still needs physical cut attestation; Chat handoff has widget evidence but not device acceptance; voice and shipping-line documents do not authorize release. I found no new production approval or containment bypass.

## D. Owner physical acceptance readiness

The candidate has a single recorded green full chain and its archived test outcomes are internally consistent. It is **not ready** for owner physical acceptance as an operational candidate while the Phase 1 gate can accept inconsistent outcome counts and fails to bind the stored baseline outcome map at each gate. The owner PA gates and backend/shipping decisions remain open by design; this review does not treat any of them as passed.

## E. New defects

OQ-R5-1 and OQ-R5-2 are evidence-gate defects. They do not establish an actual regression in chain8. They prevent the gate from proving the stated invariants for a future run or for a baseline map that differs from its stored XML. Correct the per-outcome count comparison and baseline XML/JSON binding, add adversarial tests, then produce a new attributable full chain.

## F. Decision

The OQ-R4-1 collision repair is effective and the archived chain8 records are consistent. The new gate defects leave the qualification predicate incomplete. I reject `-e` as an operational candidate pending gate repair and a new full chain. This is not physical qualification.

## DEFECTS

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| OQ-R5-1 | Gate | XML and pytest summary can disagree on passed/skipped/failed/error counts while their totals match; `phase1-full` still passes its outcome checks. | `scripts/phase2close_chain.py` `junit_integrity` and `phase1-full`; `reviewer_results.json` `outcome_count_mismatch` and `full_gate_changed_skip_count`. |
| OQ-R5-2 | Gate | Each gate rechecks baseline XML structure but not equality of its outcome map with the stored baseline JSON. | `scripts/phase2close_chain.py` `phase1-full`; independently verified present equality in `reviewer_results.json` `baseline`, while the gate source has no mapping comparison. |

## OQ DISPOSITION

| ID | Disposition | Basis |
|---|---|---|
| OQ-R1-1 | REPAIRED | Native layout/descriptor pins unchanged from round 4; W3 invalidation persists. |
| OQ-R1-2 | REPAIRED | Both approval paths retain usability gating; W refuses `HARNESS_NOT_USABLE`. |
| OQ-R1-3 | REPAIRED | Windows supervisor still fails closed when self-containment is unavailable. |
| OQ-R1-4 | OPEN | One green recorded chain exists, but its Phase 1 predicate has OQ-R5-1 and OQ-R5-2. |
| OQ-R2-1 | PARTIALLY REPAIRED | Per-test identity and injectivity work; the gate lacks per-outcome summary consistency and baseline-map binding. |
| OQ-R3-1 | REPAIRED | Same-key pass/skip swaps are refused on consistent records. |
| OQ-R3-2 | REPAIRED | Baseline runner hash/argv, current runner, and ini remain bound to accepted `-f`; the disclosed new-run provenance limit remains. |
| OQ-R4-1 | REPAIRED | Real pytest collision and same-outcome duplicate are now refused; archived XML has unique keys. |

## NOT VERIFIED

I did not rerun the roughly 25-minute full chain, authenticate a client profile, read credentials, run real-model worker PA-10, use an elevated sandbox, perform owner UI/device acceptance, power-cut a VM, inspect a shipping remote, or attest the exact source bytes during each past chain8 step. My focused repository pytest invocation could not use pytest's temporary directory under this sandbox (`WinError 5`); its errors are not counted as product test failures. The separate real-pytest collision and direct parser/gate probes completed. I did not edit the repository, log in or out, change global configuration, kill other processes, commit, push, or merge.

## FINAL VERDICT

PHASE 2 OPERATIONAL CANDIDATE REJECTED
