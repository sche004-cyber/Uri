# Independent Phase 2 operational qualification review — round 3

Date: 2026-10-08. Subject: `evidence/phase2oq-candidate-20261008-c.zip`, SHA-256 `a2c11441bb51975fcb3fbbec84f89760d13f24e9f815d2f13d9e88452f049602`. I inspected the archive, live tree, chain6 artifacts and gate source, and ran independent read-only checks and synthetic gate probes in `reviewer_checks.py`. I changed no repository file. Probe logs and this report are confined to this review directory. I did not log in, read credentials, change global settings, stop processes, or commit.

## A. Integrity, frozen boundary and exact change set

The subject hash matches `ROUND3_SUBJECT.txt`. Its 318 manifest entries comprise 154 tree files and 164 evidence files. Archive member names exactly match the manifest; every payload hash and every corresponding live file hash matches. HEAD is `e8e3b65259c45fc823addc3ef8969425a265bd1b`, uncommitted. The prior rejected `-b`, accepted closure `-f`, and round-7 archive hashes remain `5d5e111bf2377a6a09eb2a7d81c4d02fb11da710a4fe0a3e6aa2577aa55c5706`, `fcd0d72e0cd91412c361edec9114e2edaebbf70ede052046b808f3c4fc571298`, and `9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a`. The Phase 1 frozen checkpoint hash remains `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`; all of its tree payloads are byte-identical to live files. `GIT_DIFF.patch` is archive metadata, not a tree payload.

Against `-b`, the exact manifest delta is **55 added, 2 changed, 0 removed**. The two changed paths are `scripts/phase2close_chain.py` and `docs/plans/PHASE2OQ_REPORT.md`. The only added tree path is `tests/phase2oq/test_chain_equivalence.py`. The other 54 additions are `evidence/phase2oq/chain5/` (including its abort marker), `chain6/` and `chain6_stdout.txt`, `collection_baseline/`, `collection_baseline2/`, and `phase1_collection_baseline.txt`. The full path list is printed by `reviewer_checks.py`. The new collection baseline is candidate-created evidence, not a file from accepted `-f`.

## B. OQ-R2-1: equivalence gate and adversarial tests

The new rule rejects the straightforward offset in round 2 **when supplied a trustworthy collection baseline**: a missing ID replaced by an added ID yields `collection_missing` and `collection_added`; a new failure changes `failed_ids`; a new skip location or reason yields `skips_not_in_baseline`. My synthetic probes reproduced those refusals. The real chain6 log has 2,676 distinct `PASSED` IDs, 11 familiar `FAILED` IDs, 11 skips, no error, 2,698 collected IDs identical to the stored list, and the expected single Ollama skip disappearance. `phase1_equivalence` returns true for those inputs.

**The lost-pass guarantee still fails.** `passed_ids` records current IDs, but the accepted baseline log has no `PASSED` IDs, and `phase1_equivalence` never compares baseline and current pass-ID sets. `skip_multiset` records only the source *basename*, line, and normalized reason, not the skipped test ID. I constructed a baseline with 2,675 named passes, 12 skips at `live.py:10: unavailable`, and 11 named failures, then a current run with the **same 2,698 collection IDs** in which `live.py::test_pass` loses its pass and `live.py::test_s0` becomes a pass. The 12 skips retain the same summarized location and reason. The exact production predicate returns **`True`**, with no missing/added collection IDs, no extra skips, and 2,675 named passes. Parametrized tests or multiple skips at one call site can produce this summary shape. The probe is `probe_swap_base.log`/`probe_swap_now.log` and `probe_lost_pass_same_skip_location` in `reviewer_checks.py`. This establishes a rule-level bypass; it does not assert that this swap occurred in chain6.

The collection baseline has a separate provenance weakness. `--make-phase1-collection-baseline` runs `phase1_collection` against the current candidate, then writes its 2,698 IDs if `phase1_scope_check` passes. The scope check classifies `scripts/phase2d_regression.py` as Phase 2-only via the `scripts/phase2` prefix, although that runner defines the Phase 1 full target and ignore list. That runner's hash differs from `-f`; its observed delta only adds `tests/phase2oq` to Phase 2 ignores, so I found no actual lost accepted test from that delta. Nevertheless, the check cannot prove the claim that *every Phase 1 suite input* equals `-f`: an altered runner could select a different 2,698-test collection, then write it as its own baseline. The baseline file is sorted, unique, and matches chain6 collection, but its generation is not independent accepted-baseline evidence. `phase1_collection` also ignores its subprocess exit status; the size check offers some protection but does not establish successful collection.

The added adversarial tests exercise a missing/added collection offset and a **new skip kind**. They do not exercise a pass/skip swap under one existing skip-summary key. Several synthetic skip IDs are invented separately from the skip summary, so those tests do not establish a mapping from summarized skips to specific collected tests. The direct counterexample above covers this omitted case.

## C. Chain6

`chain6_stdout.txt` and the archived summary show one sequential invocation ending `ALL_PASS`. The individual logs agree with phase2 **477 passed, 2 skipped**; authority **134 passed**; phase1-full **2,676 passed, 11 skipped, 11 pre-existing failures**; Flutter **205 passed, 2 skipped**; ten successful bridge runs with zero recorded `CLIENT_REFUSAL` lines; native lifecycle verified and cancel PID dead; and native-worker W refusal, W2/W3 invalidations, verified scripted lifecycle and cancel with zero survivors. The phase1-scope gate also records `PASS`. Chain5 is explicitly aborted and is not counted. The 11 Phase 1 failures are not newly green tests. The archive contains the chain6 artifacts and matches the present `-c` tree; the runner did not emit source digests at each gate, so exact source bytes at each historical execution step are not independently attested. Chain6 is green under the current, inadequate predicate.

## D. Prior findings and round-1 B–K

OQ-R1-1 through OQ-R1-3 remain repaired on the inspected paths: recognized vendored Codex layout and descriptor pins are required in worker composition; both worker approval forms check live usability before approval; Windows supervisor construction fails closed if self-containment is unavailable. No changed source in `-c` touches those production repairs, and chain6 phase2/native-worker results are consistent with them. OQ-R1-4 has a single recorded green chain but its required Phase 1 non-regression proof is still incomplete because OQ-R2-1 remains open.

The prior B–K dispositions otherwise hold: client-profile authentication and sandbox-mode invalidation remain demonstrated only to the recorded extent; the in-process native run is not worker PA-10; the guest power-loss witness is not a physical cut; Chat handoff remains widget-tested, not device accepted; login/acceptance tooling does not perform login; and shipping/voice decisions remain plans. I found no new production approval or containment bypass. The frozen boundary and earlier regression suites are represented by the same passing phase2/authority gates, but I did not independently replay each historical adversarial case.

## E. New defects and impact

OQ-R3-1 is the concrete remaining equivalence-rule defect: a lost pass can be hidden by a pass/skip swap when skip summaries collide. The candidate-created collection baseline also does not independently establish accepted `-f` collection identity; the scope check exempts its own Phase 1 runner. These are release-evidence defects, not observed evidence of a current production regression. The direct probe makes the first one blocking under the mandate's explicit “any lost pass” requirement.

## F. Decision

The subject is internally consistent and chain6 is one recorded green chain. The Phase 1 equivalence rule still admits a lost pass, and the accepted collection baseline is not independently bound. Therefore the operational candidate is not ready for owner physical acceptance. The gate needs an independently anchored baseline with per-test outcome identity (including skipped IDs) or an equivalent proof that prevents the demonstrated swap, followed by a new attributable full chain. This review does not claim physical qualification.

## DEFECTS

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| OQ-R3-1 | Gate | A baseline pass can become a skip while a baseline skip becomes a pass at the same summarized skip location/reason; the gate returns `PASS` despite the lost pass. | `scripts/phase2close_chain.py` `skip_multiset`, `passed_ids`, `phase1_equivalence`; `reviewer_checks.py` `probe_lost_pass_same_skip_location=True`. |
| OQ-R3-2 | Gate provenance | The stored collection is made on the candidate, while `phase1_scope_check` exempts the Phase 1 selection runner as Phase 2-only; its equality to chain6 cannot by itself prove identity to accepted `-f`. | `scripts/phase2close_chain.py` `PHASE2_SCOPE`, `phase1_scope_check`, `--make-phase1-collection-baseline`; changed `scripts/phase2d_regression.py` hash versus `-f`. |

## OQ DISPOSITION

| ID | Disposition | Basis |
|---|---|---|
| OQ-R1-1 | REPAIRED | Descriptor/layout pins and worker composition requirement unchanged from round 2; native-worker evidence remains consistent. |
| OQ-R1-2 | REPAIRED | Both approval forms retain pre-approval live usability checks; W refuses before approval. |
| OQ-R1-3 | REPAIRED | Windows constructor still fails closed when containment is unavailable; host-wide descendant effect remains documented. |
| OQ-R1-4 | OPEN | Chain6 is one recorded `ALL_PASS` chain, but its Phase 1 gate does not enforce the required lost-pass condition. |
| OQ-R2-1 | OPEN | Collection equality repairs the simple missing/added offset, but the same-key pass/skip swap passes; baseline provenance is insufficient. |

## NOT VERIFIED

I did not rerun the roughly 25-minute full chain, authenticate a client profile, read auth files, run a real-model worker PA-10, test an elevated sandbox, perform owner UI/device acceptance, power-cut a VM, inspect a shipping remote, or attest historical source bytes at each chain6 gate. The synthetic predicate probes are direct executions of the candidate function with controlled logs; they are not observations of an actual chain6 lost pass. Chain6's archived results and current archive/tree integrity were independently checked.

## FINAL VERDICT

PHASE 2 OPERATIONAL CANDIDATE REJECTED
