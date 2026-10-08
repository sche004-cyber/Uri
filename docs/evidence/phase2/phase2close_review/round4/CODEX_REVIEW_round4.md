# Independent review: Phase 2 closure, round 4

Reviewed 2026-10-08. Subject: `phase2close-candidate-20261008-d.zip`, the byte-identical candidate files in the live `uri-agent` tree, and orchestrator-produced run7 evidence. I read the earlier reviews and relevant implementation, tests, runbook, checklist, and readiness documents. I made no repository source, test, configuration, or document change. My writes were this report and audit script under the round4 review folder, plus synthetic probe state under `uri-agent/work/c1/round4-review`.

## A. Integrity

I independently hashed the `-d` archive: `38ca7f812bd83dc9980304b26b3c2e60be084fd98e90598134740b57a2b66043`, matching the subject and sidecar. The rejected `-c` archive remains `0cfc317562021f3fead97cd447e7c78db7b5d1a69f366b542879b6215fa8432c`; the round-7 accepted slice remains `9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a`; the Phase 1 checkpoint remains `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`. Live HEAD is `e8e3b65259c45fc823addc3ef8969425a265bd1b`.

The `-d` manifest's 168 entries exactly match the archive's 137 tree and 31 run7 evidence files, with no digest mismatch. All 137 tree files match live files byte for byte. All 31 embedded run7 files match the external run7 folder. The Phase 1 checkpoint's 121 source files are present and byte-identical in the live tree. Against `-c`, there is no added or removed tree file. Exactly four files changed: `scripts/phase2close_powerloss_harness.py`, `tests/phase2close/test_powerloss_harness.py`, `docs/plans/PHASE2CLOSE_REPORT.md`, and `docs/plans/URI_DEVELOPMENT_TODO.md`. The runbook and checklist did **not** change in this round. [audit_probe_round4.py](audit_probe_round4.py) reproduces these comparisons.

## B. D4: assessor and replay

The round-3 holes are repaired in the cases I reran. A failed/mislabeled FULL summary is refused; `{"simulated": ...}` as the power method is refused; a false lost-task identity in `iterations.json` is refused; a missing final `ready` line and wrong `previous_boot` are refused. The round-2 contradictory FULL/zero-iteration NORMAL pair is refused. Four focused assessor test functions also passed when directly invoked with probe paths. `build_row` and `build_summary` are shared between `campaign` and replay; `assess_series` compares whole derived rows and summaries, including `failed`, `verdict`, and `synchronous` (`phase2close_powerloss_harness.py:104-121, 394-454`). This is a material improvement in record reconciliation.

**D4 remains open.** `iteration_verdict` treats `report.invariants_ok == true` as conclusive when no acknowledged step is lost (`:124-129`). `build_row` also records `integrity`, `orphans`, `still_in_flight`, and `relaunched`, but neither `iteration_verdict` nor `assess_series` checks their consistency with `invariants_ok`. On a coherent synthetic 200-pass FULL and four-iteration NORMAL control pair, I changed the FULL raw report for boot 2 to say `integrity: "corrupt"` while leaving `invariants_ok: true`, and updated the corresponding `iterations.json` row to `integrity: "corrupt"`. All files then agreed under the shared builders, yet `assess` returned `EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION`, `reasons: []`, `qualified: false`. The same result occurred with a reported orphan attempt and with a reported task still in flight, after matching each row to the raw report. In each case the raw report itself contradicts the guest's `verify` invariant formula (`:152-154`), and a real `verify` finding of those conditions should fail that FULL iteration. A single-file alteration was refused; coordinated alteration of raw and derived records was not. This is precisely where replay of campaign's *row builder* falls short of validating the guest verification semantics.

`_real_power_method` checks only that the summary has nonempty `power_off` and `power_on` strings without the substring `simulat` (`:412-414`). A FULL summary changed to `{"power_off":"echo hello","power_on":"echo world"}` still received the sufficient verdict. This is a weaker recorded method than the function's error text ("hypervisor ... command pair") implies. The owner's later attestation is explicitly required and could reject it; the assessor itself cannot establish that any command is a physical cut. I count this as part of the D4 sufficiency limitation, not evidence that a process kill actually qualified. All probes retained `qualified:false`.

I did not rerun a real local process-kill campaign: round 3's direct attempt timed out in `p.wait(30)` and this round's focused verification used synthetic records. The shared builders and run7 test result support campaign/replay parity for the successful local test path, but I have not personally observed a complete real campaign replay. The synthetic cases demonstrate a concrete acceptance gap regardless of that limit.

## C. D5, runbook, and checklist

D5's literal stale `ALL_ITERATIONS_PASS` label remains corrected. Checklist B4 and runbook PA-11 both call `assess` on the two series directories, require at least 200 FULL passes and a NORMAL loss, and retain owner hypervisor attestation and PA-11. The runbook's statement that summaries and iteration files agree with the raw record is implemented as a field comparison. Its stronger implication that every FULL pass represents good ledger integrity and recovery invariants is not enforced against a contradictory raw report, as shown above.

The checklist also has a separate low-severity traceability defect: A6-A11 still say `see run5` while citing `run4` paths (`PHASE2CLOSE_CLOSURE_CHECKLIST.md:17-22`). The closure report's Record H4 and the `-d` archive instead use run7. The historical paths exist, but these checklist cells do not identify the final-candidate chain. B4 remains PENDING; A12 remains PENDING while this review runs. A13's narrow statement that `assess` never returns `qualified:true` is true, but it is insufficient to substantiate the broad technical-readiness claim while D4 is open.

## D. Run7 full chain

Run7 has one `chain_summary.json` with seven gates in sequence from 06:54:06 to 07:21:07 and `ALL_PASS:true`. I checked log commands, result lines, and independent counts: Phase 2 `449 passed, 2 skipped`, exit 0; authority `134 passed`, exit 0; Phase 1 full `2675 passed, 12 skipped, 11 failed`, exit 1 as expected by that gate. I extracted its 11 `FAILED` IDs from the log and compared them with the round-7 baseline log: the sets match. Residue says none; Flutter reports `195 passed, 2 skipped`, exit 0. All ten bridge JSONs report exit 0; `refusals.txt` has zero bytes. Native stdout reports lifecycle `completed/SETTLED_VERIFIED` and mid-run cancel `uncertain/CANCELLED_AFTER_DISPATCH`, executor `DEAD`, exit 0. Its report identifies programmatic approval, not a human UI approval. The native run is the in-process owner-shell composition described in the closure record, not client-profile execution inside the worker.

The archive embeds the exact run7 evidence files I read. This makes run7 a credible single green full-chain record associated with `-d`. It is orchestrator-produced history; I cannot independently witness that the tree was unedited throughout its execution. I did not rerun the roughly 27-minute chain.

## E. Earlier finding dispositions

### Disposition table

| Finding | Round-4 disposition | Basis |
|---|---|---|
| D1 High: shell tokens could qualify a client profile | REPAIRED | Round-2 environment scrub and client `CODEX_HOME` pin unchanged from `-c`; no real client login verified. |
| D2 High: arbitrary host commands labelled physically qualified | REPAIRED AS TO PHYSICAL LABEL | `VM_SERIES`/series verdicts, power-command failure and acknowledged-work checks, `qualified:false` unchanged; D4 still limits sufficiency. |
| D3 Medium: no single green final chain | CLOSED | Run7 summary, logs, failure IDs and byte-identical archive evidence checked. |
| K1 Low: suspended orphan window | RECORDED, OPEN | `winproc.py` unchanged; C7 still records it and makes no repair claim. |
| VAL-1 historical text overclaimed clock as sole 403 cause | CORRECTED | Closure report retains `_authorize`/`EXECUTION_AUTHORITY_UNAVAILABLE` alternative and historical uncertainty. |
| LOG-3 bounded refusal body | CONFIRMED FROM UNCHANGED FILES AND RUN7 | Bridge implementation and accepted tests unchanged from earlier reviewed candidate; Phase 2 and bridge gates pass. |
| VAL-1 bounded one resend | CONFIRMED FROM UNCHANGED FILES AND RUN7 | Same implementation/tests and passing gates; historical incident remains unattributable. |
| CAP-1 pending-turn capacity release | CONFIRMED FROM UNCHANGED FILES AND RUN7 | Same implementation/tests and passing gates. |
| ISO-1 supervised worker home pin | CONFIRMED FROM UNCHANGED FILES AND RUN7 | Same worker and qualification code; actual client-profile worker execution remains pending. |
| Changed accepted Phase 2D tests | HONEST, UNCHANGED | Same disclosed CAP-1 assertion changes as prior rounds. |
| D4 Medium: incoherent evidence accepted (round 2) | PARTIALLY REPAIRED; OPEN | Round-2 and round-3 examples now refused; coordinated contradictory raw report and row still accepted. |
| D5 Low: checklist `ALL_ITERATIONS_PASS` | CLOSED | B4 uses current assessor verdict, series directories, and owner gate. |
| D4 residual Medium: summary, lost identity, final ready, continuity, simulated method (round 3) | SPECIFIC CASES REPAIRED; D4 OPEN | All five probes now return `INSUFFICIENT`; new invariant contradiction and weak-command probes expose remaining limits. |

## F. New defects

### DEFECTS table

| ID | Severity | Location | Finding and effect |
|---|---|---|---|
| D4 residual | Medium; blocks technical closure | `scripts/phase2close_powerloss_harness.py:124-129, 394-454, 457-476` | A raw report and matching row can say `integrity="corrupt"`, contain an orphan attempt, or retain a running task while `invariants_ok=true`; replay and `assess` still count it as a FULL PASS and return evidence sufficient. Validate the report's integrity/recovery fields independently of its boolean and reject contradictory records. |
| D6 | Low; evidence traceability | `docs/plans/PHASE2CLOSE_CLOSURE_CHECKLIST.md:17-22` | A6-A11 point to run4 and say `see run5`, rather than identifying run7 as the final `-d` chain. Update the checklist's result and evidence cells. |

The arbitrary `echo` power-method probe is additional evidence of the D4 sufficiency limit. It does not replace the owner attestation or prove a physical cut did not occur in any real campaign.

## G. Readiness and pending gates

`PHASE2CLOSE_C7_READINESS.md` correctly says **NOT READY FOR CUTOVER**. The owner UI session, client-profile logins, EXE-1 decision and native worker execution, controlled FULL/NORMAL VM campaigns and PA-11 attestation, C6 decisions, Phase 2 rollback overlay, development-line reconciliation, explicit handling of the 11 baseline failures, and written cutover authorization remain open. Run7's native result does not close those gates.

The report's **PHASE 2 TECHNICALLY READY — PHYSICAL/OWNER GATES PENDING** claim is not supported while the assessor can call an internally invalid FULL series sufficient and the final-chain checklist references stale runs. This review is a technical evidence-control rejection. It is not a claim that physical power-loss testing failed; it has not been performed here. No basis exists for **PHASE 2 ACCEPTED AND QUALIFIED**.

## H. Decision

The `-d` repair closes the exact round-3 examples and has a credible run7 green regression chain. It does not make a passing replay depend on the ledger integrity and recovery facts recorded in the raw report. D4 therefore still blocks technical closure. Reconcile those facts with `invariants_ok` and the FULL pass condition, add the demonstrated adversarial cases to the focused tests, and update the checklist chain references before re-review. Physical and owner gates remain pending after any technical repair.

## NOT VERIFIED

I did not perform a real client-profile login, a native CLI run inside the supervised worker, a human UI session, a VM hard power cut, a NORMAL negative-control loss, historical VAL-1 reproduction, K1 process-window experiment, or full-chain rerun. I did not read credentials. A focused pytest invocation was unable to finish because Windows denied pytest access to its temporary directory under `work/c1/round4-review/pytest` (`WinError 5`); four assessor test functions were invoked directly and passed, and the audit/probe script completed. Run7 is orchestrator-produced evidence inspected and archive-matched, not my own execution. I cannot independently establish that no edit occurred during the historical chain.

## FINAL VERDICT

**PHASE 2 CLOSURE REJECTED**
