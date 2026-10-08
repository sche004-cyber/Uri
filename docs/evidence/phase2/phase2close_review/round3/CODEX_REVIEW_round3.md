# Independent review: Phase 2 closure, round 3

Reviewed 2026-10-08. Subject: `phase2close-candidate-20261008-c.zip` and its byte-identical live candidate files. I inspected the candidate, implementation, tests, runbook, checklist, prior reviews, and run6 evidence, then ran independent archive checks and adversarial assessor probes. I did not edit repository source, tests, configuration, or documents. My writes are confined to this round-3 review folder and probe state under `uri-agent/work/c1`.

## A. Integrity

The subject archive hashes to `0cfc317562021f3fead97cd447e7c78db7b5d1a69f366b542879b6215fa8432c`, matching `ROUND3_SUBJECT.txt` and the sidecar. The rejected `-b` archive still hashes to `3ab0a859799b626841ce1aec87f168b37e5d48a90ff80ed435d510f846fc121b`; round-7 hashes to `9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a`; the Phase 1 frozen checkpoint hashes to `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`. Live HEAD is `e8e3b65259c45fc823addc3ef8969425a265bd1b`.

The `-c` manifest's 168 names exactly cover 137 tree files and 31 evidence files; every digest checks. All 137 candidate tree files match the live tree byte for byte. All 31 embedded run6 files match the external run6 folder byte for byte. All 121 Phase 1 checkpoint source files are present and byte-identical in the live tree. [audit_round3.py](audit_round3.py) reproduces these checks.

Compared with `-b`, `-c` adds and removes no tree file. Exactly six files changed: `scripts/phase2close_powerloss_harness.py`, `tests/phase2close/test_powerloss_harness.py`, `docs/plans/PHASE2CLOSE_CLOSURE_CHECKLIST.md`, `docs/plans/PHASE2CLOSE_PHYSICAL_ACCEPTANCE_RUNBOOK.md`, `docs/plans/PHASE2CLOSE_REPORT.md`, and `docs/plans/URI_DEVELOPMENT_TODO.md`. Production paths and the accepted tests discussed in rounds 1 and 2 are therefore unchanged from `-b`. The current worktree has broad pre-existing uncommitted files; the archive-to-tree comparison establishes the candidate scope.

## B. D4: power-loss assessment and replay

`replay_series` now reads `acks.jsonl`, computes the highest acknowledged step per boot, compares each boot with its successor report, and recomputes iteration verdicts (`phase2close_powerloss_harness.py:343-376`). `assess_series` checks the label, presence of a power method, guest and ledger synchronous modes, nonzero replay, selected iteration fields and selected summary counts (`:379-411`). `assess` requires at least 200 FULL replayed passes and a NORMAL loss, and always returns `qualified:false` (`:414-433`). This closes the exact round-2 example: a zero-iteration NORMAL record and conflicting FULL pass/loss counts are refused. A malformed truncated JSON line is also refused. [probe_round3.py](probe_round3.py) contains my inputs and observed verdicts.

The repair is incomplete. Starting with a coherent synthetic FULL 200-pass and NORMAL 4-iteration/one-loss pair, I changed the FULL `summary.json` to `verdict: SERIES_FAIL`, `failed: 200`, and `synchronous: [NORMAL]`, leaving the raw record and other derived fields intact. `assess` returned `EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION`, with no reasons. It does not compare those three campaign-produced fields. Thus an internally contradictory, explicitly failed/mislabeled series still receives the tool's best evidence verdict. The `summary.failed` omission is especially direct: `campaign` always computes `failed` from its rows and emits `SERIES_FAIL` when any iteration failed (`:310-321`). Such a summary cannot coexist with 200 passing rows in a coherent campaign.

Other probes of the same gap also returned evidence sufficient without reasons: changing `power_method` to `{'simulated':'local process kill'}` while keeping `label: VM_SERIES`; replacing the NORMAL row's lost task with a different task while preserving list length; deleting the final `ready` line from an otherwise complete raw FULL record; and changing a successor report's `previous_boot` from 1 to 999. `assess_series` checks only that a power method is truthy, only the *length* of each row's `lost` list, and neither the final ready record nor `previous_boot`. `campaign` waits for successor ready after each report, including its last iteration (`:297-305`), so a successful, complete campaign with 200 rows would have that final ready record. The missing record is a clean line-boundary truncation, not a malformed JSON file. These inputs demonstrate that replay is not a full reconstruction or consistency check of what `campaign` records. Owner attestation is still required for an actual qualification, which limits the effect; the machine-generated statement that the evidence is sufficient remains misleading.

I attempted a two-iteration local process-kill campaign to compare replay with a real campaign record. It did not complete: `local_power`'s `taskkill` path reached `p.wait(30)` and raised `TimeoutExpired`; the guest stderr later showed a connection-reset exception after the host exited. I do not count this as a harness product defect or as a faithful-replay verification in this sandbox. The implementer's focused test claims a successful local campaign, and run6 passes that test; my own direct replay evidence is synthetic.

## C. D5 and documentation

Checklist B4 now names `assess` over the two directories, a 200-iteration FULL replay, NORMAL loss, owner hypervisor attestation and PA-11 PASS. The stale `ALL_ITERATIONS_PASS` criterion is removed. The runbook steps 4-5 now pass directories and retain physical owner confirmation (`PHASE2CLOSE_PHYSICAL_ACCEPTANCE_RUNBOOK.md:176-188`). D5's literal mismatch is closed.

The runbook at `:183-185` says summary and iterations files *must agree* with the raw record. The assessor actually ignores `summary.failed`, `summary.verdict`, `summary.synchronous`, the content of each row's `lost` list, and several raw-record continuity fields. The checklist's B4 evidence criterion inherits this weaker assessor. The documents correctly keep PA-11 and physical power loss pending, but their claimed validation strength is not implemented.

## D. Run6 chain

Run6 has one `chain_summary.json`, started 06:18:45 and finished 06:45:37, with the seven expected gates in sequence and `ALL_PASS:true`. I checked its log commands and tails independently: Phase 2 448 passed/2 skipped, exit 0; authority 134 passed, exit 0; Phase 1 full 2675 passed/12 skipped/11 failed, exit 1 as expected by this gate. I independently extracted the 11 `FAILED` IDs from the run6 and round-7 baseline logs; the sets match and match the summary. Residue reports none. Flutter reports 195 passed/2 skipped, exit 0. All ten bridge JSONs report exit 0 and `refusals.txt` is zero bytes. Native stdout reports lifecycle `completed/SETTLED_VERIFIED`, mid-run cancel `uncertain/CANCELLED_AFTER_DISPATCH`, and executor `DEAD`; its report calls the approval programmatic and describes in-process owner-shell composition. These are orchestrator-produced logs, not executions I personally reran. Their byte-identical archive embedding associates them with `-c`; I cannot independently witness the historical claim that no edit happened while the chain ran.

## E. Earlier findings and accepted work

| Finding | Round-3 disposition | Basis |
|---|---|---|
| D1 High: shared shell tokens could qualify client profile | REPAIRED | The `-b` environment scrub, client `CODEX_HOME` pin and fail-closed synthetic probe from round 2 apply unchanged; `-c` changed none of those files. Real client-profile login remains unverified. |
| D2 High: host could label arbitrary commands physically qualified | REPAIRED AS TO PHYSICAL LABEL | Host uses `VM_SERIES`/series verdicts, checks power-command false and acknowledged work, while `assess` never sets `qualified:true`; unchanged from `-b`. Assessor sufficiency remains defective under D4. |
| D3 Medium: no single green final chain | CLOSED | Run6 seven-gate summary, corresponding logs, 11-ID baseline match and archive embedding checked. |
| D4 Medium: assessment trusted incoherent evidence | PARTIALLY REPAIRED; OPEN | Exact round-2 contradiction now refused, but new contradictory, truncated and mislabeled examples still receive evidence sufficient. |
| D5 Low: stale B4 `ALL_ITERATIONS_PASS` | CLOSED | B4 now states the current assessor and owner gate. The runbook's stronger consistency promise remains inaccurate under D4. |
| K1 Low: suspended orphan window | RECORDED, OPEN | `uri_supervisor/winproc.py:256-261` unchanged; C7 records the window and does not claim repair. |
| VAL-1 historical text | CORRECTED | Closure report still names the other `_authorize` 403 path and does not attribute the historical incident solely to the clock. |
| LOG-3 bounded refusal body | CONFIRMED FROM UNCHANGED FILES AND RUN6 | Bridge and accepted test bytes unchanged from `-b`; Phase 2 and bridge gates passed. |
| VAL-1 one resend | CONFIRMED FROM UNCHANGED FILES AND RUN6 | Same bounded resend and tests as `-b`; historical cause remains unattributable. |
| CAP-1 release | CONFIRMED FROM UNCHANGED FILES AND RUN6 | Same frozen cancel-route use and changed accepted tests as `-b`. |
| ISO-1 worker home pin | CONFIRMED FROM UNCHANGED FILES AND RUN6 | Same worker and qualification paths as `-b`; actual supervised client-profile native execution remains pending. |
| Changed accepted Phase 2D tests | HONEST, UNCHANGED | Same assertions as `-b`; the CAP-1 behavior change remains disclosed. |

## F. New defects

| ID | Severity | Location | Independent finding and effect |
|---|---|---|---|
| D4 residual | Medium, blocks technical closure | `scripts/phase2close_powerloss_harness.py:389-411,419-430` | `assess` can call a failed, internally contradictory FULL summary sufficient because `failed`, `verdict`, and `synchronous` are ignored. It also accepts false lost-task details, incomplete final-ready raw records, and wrong `previous_boot`. The assessment can mislead an owner about the strength and coherence of physical evidence. Reconcile all campaign-derived fields and boot/order continuity with the raw messages, then test these cases. |

No separate production-path regression appeared in the six-file diff. The simulated-method probe illustrates the D4 evidence/label problem; it does not prove an actual physical power cut was skipped, because owner attestation is explicitly pending. `qualified:false` held in all my probes.

## G. Readiness and pending gates

`PHASE2CLOSE_C7_READINESS.md` says **NOT READY FOR CUTOVER**, consistent with the evidence. The owner UI session, client-profile logins, physical FULL and NORMAL campaigns, PA-11 attestation, EXE-1 native worker decision and execution, C6 decisions, rollback overlay, reconciliation with the other development line, the 11 baseline failures, and written cutover authorization remain open. Run6 native evidence uses an in-process composition with programmatic approval under the owner's shell login. None of those pending gates is converted to PASS by run6 or this review.

The phrase “PHASE 2 TECHNICALLY READY — PHYSICAL/OWNER GATES PENDING” in the closure report is unsupported while D4 permits contradictory and incomplete evidence to receive the assessor's best sufficiency verdict. This is a technical evidence-control issue, distinct from the deliberately pending physical and owner steps. There is no basis for “accepted and qualified.”

## H. Decision

The `-c` repair improves replay and closes the exact round-2 probe and D5 typo, but it does not enforce the candidate's own requirement that the summary, rows and raw campaign record agree. D4 remains a blocking technical-closure defect. Run6 is a credible single green regression chain for this archive. Fix the remaining assessment consistency gaps and obtain focused regression evidence before another closure review; physical and owner gates will still be pending afterward.

## NOT VERIFIED

I did not perform a real client-profile login, native Codex execution inside the supervised worker process, a human UI click session, a VM hard power cut, a NORMAL negative-control loss, historical VAL-1 reproduction, a full chain rerun, or an experimental K1 probe. I did not read credentials. My local process-kill campaign failed at `p.wait(30)`, so I cannot personally confirm replay fidelity on a complete real campaign record. Run6 is orchestrator-produced evidence I inspected and archive-matched, not my own execution. I cannot independently establish that the tree was unedited during that historical run.

## FINAL VERDICT

**PHASE 2 CLOSURE REJECTED**
