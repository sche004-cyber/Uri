# Independent review: Phase 2 closure, round 5

Reviewed 2026-10-08. Subject: `phase2close-candidate-20261008-e.zip`, its byte-identical live `uri-agent` files, and orchestrator-produced `evidence/phase2close/run8`. I read the mandate, prior reviews, changed implementation/tests/documents, checklist, runbook, C7 readiness, and chain logs. My only writes were this report and `audit_probe_round5.py` under this review folder, plus synthetic probe data under `uri-agent/work/c1/round5-review*`. I made no repository source, test, configuration, or document edit.

## A. Integrity

I independently hashed `-e`: SHA-256 `14362501a8bf6f9e3c788107daa562ca16502f838c0d43dfab7c5a6113c5e32b`, matching the subject. The rejected `-d` hash remains `38ca7f812bd83dc9980304b26b3c2e60be084fd98e90598134740b57a2b66043`; round-7 remains `9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a`; the Phase 1 frozen checkpoint remains `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`. Live HEAD is `e8e3b65259c45fc823addc3ef8969425a265bd1b`.

The `-e` manifest has 168 entries, exactly its 137 tree and 31 run8 evidence files, with no digest mismatch. All 137 tree files match the live tree byte for byte, and all 31 embedded run8 files match the external run8 evidence. All 121 frozen Phase 1 source files are present and byte-identical. Relative to `-d`, no tree file was added or removed. Exactly five changed: `scripts/phase2close_powerloss_harness.py`, `tests/phase2close/test_powerloss_harness.py`, `docs/plans/PHASE2CLOSE_CLOSURE_CHECKLIST.md`, `docs/plans/PHASE2CLOSE_REPORT.md`, and `docs/plans/URI_DEVELOPMENT_TODO.md`. `audit_probe_round5.py` reproduces the comparison (its inherited `RUN7 different` print label denotes run8 after path substitution).

## B. D4: assessor, series, and replay

The round-4 invariant contradiction is repaired. `report_invariants_hold` (`phase2close_powerloss_harness.py:125-132`) now requires `invariants_ok is True`, integrity `ok`, and empty *present lists* for orphans, still-in-flight tasks, and relaunches. I reran the coordinated raw/row corruption, orphan, and in-flight probes: each returned `INSUFFICIENT`, including after matching the row to the raw report. The new focused round-4 test and `iteration_verdict` test passed by direct invocation. The round-2 contradictory pair and all five round-3 examples also returned `INSUFFICIENT`; four older focused assessor tests passed directly. A coherent synthetic 200-pass FULL plus four-iteration NORMAL loss control returned the expected pending-owner verdict and `qualified:false`.

`campaign` and `replay_series` share `build_row`/`build_summary`. `assess_series` compares entire derived rows and summaries, except host-only `delay_s` and `finished`, and checks report/ready continuity. This gives faithful field reconstruction for ordinary completed rows and closes the specific prior record mismatches. I did not personally complete a local process-kill campaign; the run8 Phase 2 gate includes its passing test, and my replay probes are synthetic.

**A new acceptance gap remains.** `assess_series` feeds the *recorded* `iterations_requested` to `build_summary` and checks that the recorded summary matches that rebuild (`:452-461`). It never checks that the request count is a positive count consistent with the completed FULL series, or requires `summary.verdict == SERIES_ALL_PASS`. I took a coherent 200-pass FULL series and changed only its summary to `iterations_requested: 0, verdict: SERIES_FAIL`; the rebuilt summary agrees exactly, and `assess` returned `EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION`, empty reasons, `qualified:false`. `iterations_requested: 201, verdict: SERIES_FAIL` did the same. A completed `campaign(out, 0, ...)` cannot produce 200 rows, while a 201-request campaign cannot normally finish with only 200 passing rows and a completed summary; both records contradict campaign's stated complete-series condition. A NORMAL control summary altered to `iterations_requested: 5, verdict: SERIES_FAIL` with four completed rows was also accepted. This is D7 in the table below. The existing test changes `iterations_requested` without updating `verdict`, so it tests an easier inconsistency and misses this coordinated summary edit.

The previous weak-method limitation persists: replacing the FULL `power_method` with `{"power_off":"echo hello","power_on":"echo world"}` returned the pending-owner sufficiency verdict. `_real_power_method` (`:421-424`) only checks two nonempty strings that omit `simulat`; it cannot establish these are hypervisor power commands despite its error text. This does **not** produce `qualified:true`; the runbook explicitly requires owner attestation of a real cut. It does show that the assessor's best machine verdict alone is weaker than the phrase “recorded hypervisor ... command pair.” I treat this as a recorded D4 limitation; D7 independently blocks technical closure.

## C. D5, D6, runbook, and checklist

D5 remains closed: checklist B4 and runbook PA-11 use `assess` on FULL and NORMAL series directories, require at least 200 FULL passes and a NORMAL acknowledged-step loss, and retain physical owner attestation. D6 is corrected: checklist A6-A11 cite run8 paths and run8 counts, matching Record H5. A12 remains PENDING during this review. A13 is narrowly a plumbing claim, and `qualified:false` is preserved. The runbook says the host's `SERIES_ALL_PASS` is never itself a durability verdict; the assessor nevertheless accepts the explicitly `SERIES_FAIL` FULL summaries in B, contrary to the stated completed FULL-series evidence criterion. PA-11 and B4 remain PENDING.

## D. Run8 full chain

The single run8 `chain_summary.json` records seven sequential gates from 07:26:17 to 07:53:16, `ALL_PASS:true`. I independently inspected log commands, tails, and counts: Phase 2 `450 passed, 2 skipped`, exit 0; authority `134 passed`, exit 0; Phase 1 full `2675 passed, 12 skipped, 11 failed`, exit 1 as expected by its unchanged-baseline gate. The 11 extracted FAILED IDs match the round-7 baseline set. Residue is empty; Flutter says `195` passed, `2` skipped; all ten bridge JSONs have exit 0; `refusals.txt` is empty. Native stdout and report show lifecycle `completed/SETTLED_VERIFIED`, mid-run cancel `uncertain/CANCELLED_AFTER_DISPATCH`, PID `DEAD`, exit 0. The report identifies programmatic approval and an in-process owner-shell composition, not a human UI approval or native execution inside the client worker.

The archive embeds exactly those run8 files. This is a credible one-chain green result for `-e`; it is historical orchestrator evidence inspected here, not a chain I personally reran or witnessed against an immutable tree during execution. The remaining 11 Phase 1 failures are unchanged, not resolved or authorized for cutover.

## E. Round-1 through round-4 dispositions

### Disposition table

| Finding | Round-5 disposition | Independent basis |
|---|---|---|
| D1 High: shell tokens could qualify a client | REPAIRED | No relevant file changed from `-d`; round-2 scrub and client-home pin remain; real client login not performed. |
| D2 High: arbitrary host commands labelled physically qualified | REPAIRED AS TO PHYSICAL LABEL | Series-only verdicts and `qualified:false` remain; owner attestation remains necessary. Weak command strings can still receive pending-owner sufficiency, as recorded under B. |
| D3 Medium: no single green final chain | CLOSED | Run8's seven gates, log counts, baseline failure IDs, and archive evidence match. |
| K1 Low: suspended orphan window | RECORDED, OPEN | `winproc.py` unchanged; C7 retains the risk without claiming repair. |
| VAL-1 historical text overstated clock as sole cause | CORRECTED | Closure report retains the `_authorize`/`EXECUTION_AUTHORITY_UNAVAILABLE` alternative and uncertainty. |
| LOG-3 bounded refusal body | CONFIRMED FROM UNCHANGED FILES AND RUN8 | Bridge and accepted tests unchanged; Phase 2 and bridge gates pass. |
| VAL-1 bounded one resend | CONFIRMED FROM UNCHANGED FILES AND RUN8 | Implementation and accepted tests unchanged; historical refusal remains unattributable. |
| CAP-1 pending-turn capacity release | CONFIRMED FROM UNCHANGED FILES AND RUN8 | Worker/bridge and accepted tests unchanged; gates pass. |
| ISO-1 supervised worker home pin | CONFIRMED FROM UNCHANGED FILES AND RUN8 | Worker and qualification implementation unchanged; client-profile worker execution remains pending. |
| Changed accepted Phase 2D tests | HONEST, UNCHANGED | Same disclosed CAP-1 assertion changes; no change versus `-d`. |
| D4 round-2 incoherent summaries/zero NORMAL iterations | SPECIFIC CASE CLOSED | Repeated contradictory-pair probe returns `INSUFFICIENT`. |
| D5 Low: removed `ALL_ITERATIONS_PASS` still in B4 | CLOSED | Current B4 uses assessor verdict and owner gate. |
| D4 round-3 summary/loss identity/final ready/boot continuity/simulated method | SPECIFIC CASES CLOSED | Each repeated probe returns `INSUFFICIENT`. |
| D4 round-4 invariant contradiction | CLOSED AS REPORTED | Coordinated corrupt-integrity, orphan, and in-flight probes now return `INSUFFICIENT`; missing facts and relaunch covered by direct test. |
| D6 Low: checklist stale chain references | CLOSED | A6-A11 now cite run8 and its observed counts. |

## F. New defects

### DEFECTS table

| ID | Severity | Location | Finding and effect |
|---|---|---|---|
| D7 | Medium; blocks technical closure | `scripts/phase2close_powerloss_harness.py:108-122, 452-478` | `assess` accepts a 200-pass FULL directory whose summary explicitly says `iterations_requested: 0` or `201` and `verdict: SERIES_FAIL`. It reconstructs the failed summary from its own claimed request count but never rejects the failed or impossible request. Both probes returned `EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION`, no reasons, `qualified:false`. Require a positive, campaign-consistent request count and a complete passing FULL-series summary. |
| D4 method limitation | Low; owner gate still required | `scripts/phase2close_powerloss_harness.py:421-424` | A recorded `echo hello`/`echo world` pair satisfies `_real_power_method` and receives the pending-owner sufficiency verdict. The owner must inspect the command and attest a real hypervisor cut before PA-11; the assessor's error text overstates its validation. |

The missing `finished` field and an extra blank raw line also passed my probes. The former contradicts the `assess_series` docstring's “well-formed” stamp claim but does not independently prove durability; the latter is harmless whitespace. Neither changes the verdict.

## G. Readiness and pending gates

`PHASE2CLOSE_C7_READINESS.md` still correctly says **NOT READY FOR CUTOVER**. The owner UI session, client-profile logins, EXE-1 decision and native worker execution, controlled FULL/NORMAL VM campaign and PA-11 attestation, C6 decisions, rollback overlay, development-line reconciliation, disposition of the 11 baseline failures, and written cutover authorization remain open. Run8 does not close them.

The report's **PHASE 2 TECHNICALLY READY — PHYSICAL/OWNER GATES PENDING** claim is not supported while D7 lets an explicitly failed FULL campaign summary produce the assessor's best evidence verdict. This is a technical evidence-control rejection, not a finding that any physical VM campaign failed. No basis exists for **PHASE 2 ACCEPTED AND QUALIFIED**.

## H. Decision

The `-e` repair closes the round-4 invariant contradiction and D6, and run8 is a credible green full chain. D7 remains a reproducible assessor acceptance defect. Reject technical closure until the assessor refuses incomplete/failed FULL summaries with inconsistent request counts and focused regression evidence covers the coordinated edit. Physical and owner gates remain pending after that repair.

## NOT VERIFIED

I did not perform a real client-profile login, native CLI execution inside the supervised worker, human UI session, VM hard power cut, NORMAL physical negative-control loss, historical VAL-1 reproduction, K1 process-window experiment, or full-chain rerun. I did not read credentials. Direct focused test functions and synthetic probes ran locally; the local real-campaign replay test was not rerun because the prior reviewer attempt timed out at `p.wait(30)`. Run8 is orchestrator-produced evidence, inspected and archive-matched rather than executed by me. I cannot independently establish that no tree edit happened during its historical execution.

## FINAL VERDICT

**PHASE 2 CLOSURE REJECTED**
