# Independent review: Phase 2 closure, round 6

Reviewed 2026-10-08. Subject: `phase2close-candidate-20261008-f.zip`, live `uri-agent` tree at `e8e3b65259c45fc823addc3ef8969425a265bd1b`, and orchestrator-produced `evidence/phase2close/run9`. I read the round-1..5 reports, changed harness and tests, report corrections, checklist, runbook, C7 readiness, and run9 records. I wrote only this report and `audit_probe_round6.py` under the round-6 review folder; its synthetic records and attempted local replay were under `uri-agent/work/c1/round6-review`. No repository source, tests, or documents were changed.

## A. Integrity

I independently hashed `-f`: SHA-256 `fcd0d72e0cd91412c361edec9114e2edaebbf70ede052046b808f3c4fc571298`, matching the subject. The accepted round-7 archive remains `9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a`; the frozen Phase 1 checkpoint remains `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`.

The `-f` manifest names 168 entries: 137 tree files and 31 run9 evidence files. Every digest matches, every tree file is byte-identical to the live tree, every embedded run9 file matches external run9, and all 121 frozen Phase 1 files are present and byte-identical. Relative to `-e`, no tree file was added or removed; exactly five changed: `scripts/phase2close_powerloss_harness.py`, `tests/phase2close/test_powerloss_harness.py`, `docs/plans/PHASE2CLOSE_CLOSURE_CHECKLIST.md`, `docs/plans/PHASE2CLOSE_REPORT.md`, and `docs/plans/URI_DEVELOPMENT_TODO.md`. The executable audit is `audit_probe_round6.py`.

## B. D4: assess, assess_series, replay_series

The round-5 D7 defect is closed. `assess_series` now requires `iterations_requested` and recorded row count to equal replayed row count (`phase2close_powerloss_harness.py:457-459`); `assess` requires the FULL recorded verdict to be `SERIES_ALL_PASS` (`:495-496`). My coherent 200-pass FULL control was sufficient with `qualified:false`; changing only its summary to requested 0 or 201 and `SERIES_FAIL` returned `INSUFFICIENT` with both incomplete-series and failed-verdict reasons. A four-row NORMAL control claiming five requested returned `INSUFFICIENT`. The plain `echo hello`/`echo world` pair was refused.

I repeated prior attacks: missing final ready, incorrect `previous_boot`, altered loss identity, corrupted integrity, orphan attempt, and still-in-flight task each returned `INSUFFICIENT`. The original round-2 contradictory-pair test and focused round-3, round-4, round-5, and recognised-form tests passed by direct invocation from my audit script. `campaign` and `replay_series` still use the same row and summary builders; `assess_series` compares reconstructed rows and summary to recorded files. A synthetic extra report after the final ready was rejected as truncated/incomplete. I did not find another route by which an incoherent completed FULL/NORMAL record yields the pending-owner verdict.

The power-method predicate has a remaining limitation: it searches for a recognised hard-off token sequence *anywhere* in the string. A FULL summary with `power_off: "echo Stop-VM -Name URI-PL -TurnOff"` and `power_on: "echo world"`, with otherwise coherent synthetic evidence, returned `EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION`, empty reasons, `qualified:false`. This is a no-cut command pair despite the claimed recognised hypervisor hard-off form. It does not confer qualification or PASS at PA-11, which explicitly requires owner attestation of the actual cut. I record it as a Low limitation, not a technical-closure blocker; the assessor's machine verdict must not be read as verification that the command operated a hypervisor.

The run9 Phase 2 gate includes the local campaign/replay test. My direct local process-kill replay attempt did not complete: `local_power` timed out at `p.wait(30)` while stopping the spawned guest, the same sandbox-limited outcome reported in round 5. I distinguish that failed local reproduction from the synthetic probes above and the inspected run9 gate.

## C. D5, D6, method rule, runbook/checklist

D5 remains closed: checklist B4 and runbook PA-11 pass FULL/NORMAL series directories to `assess`, require >=200 passing FULL iterations and a NORMAL acknowledged-step loss, and leave owner attestation mandatory. D6 remains closed: A6-A11 cite run9 and match the observed counts. A12 is PENDING during review; A13 is a plumbing-only PASS. The script always returns `qualified:false` and `power_method_attestation_required:true`. The runbook correctly says a host `SERIES_ALL_PASS` is not a durability verdict. Its required attestation also covers the substring-matching method limitation above. PA-11 and B4 remain PENDING, with no physical campaign claimed.

## D. Run9 chain

`chain_summary.json` records one sequential chain from 07:58:17 to 08:25:18, `ALL_PASS:true`. The recorded commands and log tails show Phase 2 `452 passed, 2 skipped`, exit 0; authority `134 passed`, exit 0; Phase 1 full `2675 passed, 12 skipped, 11 failed`, exit 1 accepted by the unchanged-baseline gate. I compared the 11 `FAILED` lines with the round-7 baseline log: same set. The residue gate passed; Flutter finished `195` passed, `2` skipped; all ten bridge JSON exits are 0 and `refusals.txt` is empty. Native stdout and report record lifecycle `completed/SETTLED_VERIFIED`, mid-run cancellation `uncertain/CANCELLED_AFTER_DISPATCH`, executor `DEAD`, exit 0. Native evidence uses in-process composition and owner-shell authentication, not native execution inside the client worker. Archive evidence is byte-identical to external run9. This is a credible one-chain green result on the `-f` files, inspected rather than personally witnessed or rerun.

## E. Round-1..5 dispositions

### Disposition table

| Finding | Round-6 disposition | Independent basis |
|---|---|---|
| D1 High: shell tokens could qualify a client | REPAIRED | Relevant files unchanged from `-e`; scrub and client-home pin remain; no owner login performed here. |
| D2 High: arbitrary host commands labelled physically qualified | REPAIRED AS TO PHYSICAL LABEL | Series verdicts and `qualified:false` remain; owner must attest actual cut. Method-string weakness recorded below. |
| D3 Medium: no single green final chain | CLOSED | Run9 seven gates, log counts, 11 baseline failure IDs, and archived evidence agree. |
| K1 Low: suspended orphan window | RECORDED, OPEN | Process code unchanged; C7 records risk; no process-window experiment here. |
| VAL-1 historical text overstated clock as sole cause | CORRECTED | Report retains `_authorize` / `EXECUTION_AUTHORITY_UNAVAILABLE` alternative and uncertainty. |
| LOG-3 bounded refusal body | CONFIRMED FROM UNCHANGED FILES AND RUN9 | Accepted implementation/tests unchanged; Phase 2 and bridge gates pass. |
| VAL-1 bounded one resend | CONFIRMED FROM UNCHANGED FILES AND RUN9 | Accepted implementation/tests unchanged; historical refusal remains unattributable. |
| CAP-1 pending-turn capacity release | CONFIRMED FROM UNCHANGED FILES AND RUN9 | Worker/bridge and accepted tests unchanged; gates pass. |
| ISO-1 supervised worker home pin | CONFIRMED FROM UNCHANGED FILES AND RUN9 | Worker/qualification implementation unchanged; client-profile worker execution remains pending. |
| Changed accepted Phase 2D tests | HONEST, UNCHANGED | Same disclosed CAP-1 assertion changes; no change versus `-e`. |
| D4 round-2 contradictory summaries/zero NORMAL iterations | SPECIFIC CASE CLOSED | Direct focused test passes; raw replay and loss requirements remain. |
| D5 removed `ALL_ITERATIONS_PASS` in B4 | CLOSED | B4 uses assessor verdict plus owner gate. |
| D4 round-3 summary/loss identity/final ready/boot continuity/simulated method | SPECIFIC CASES CLOSED | Direct focused test and repeated probes reject these cases. |
| D4 round-4 invariant contradiction | CLOSED | Direct focused test and corrupt/orphan/in-flight probes reject these cases. |
| D6 stale checklist chain references | CLOSED | A6-A11 cite run9, matching logs. |
| D7 round-5 self-consistent incomplete FULL series | CLOSED | Requested 0/201 FULL and requested 5 NORMAL returned `INSUFFICIENT`; focused test passes. |
| Round-5 weak power method | PARTIALLY NARROWED, OWNER GATE REQUIRED | Plain `echo` pair refused, but `echo Stop-VM ... -TurnOff` passes substring predicate; `qualified:false` and PA-11 attestation prevent physical qualification. |

## F. New defects

### DEFECTS table

| ID | Severity | Location | Finding and effect |
|---|---|---|---|
| D8 | Low; physical owner gate remains mandatory | `scripts/phase2close_powerloss_harness.py:424-435` | `_real_power_method` searches a string for a hard-off-looking substring. `echo Stop-VM -Name URI-PL -TurnOff` plus `echo world` receives pending-owner sufficiency on an otherwise coherent synthetic pair. The predicate validates text presence, not an executable hard-off form. `qualified:false`, `power_method_attestation_required:true`, and PA-11 still require the owner to establish an actual cut. |

I found no new blocker in the tested scope. The assessor cannot authenticate that raw host lines or VM commands reflect physical events; this is why the separate owner gate remains substantive.

## G. Readiness and remaining gates

The report's **PHASE 2 TECHNICALLY READY — PHYSICAL/OWNER GATES PENDING** claim is supportable for the tested technical closure: D7 is repaired, run9 is a green final chain, and D8 cannot mark a physical qualification. Checklist A12 can be completed by this independent acceptance. The record must continue to describe method-form validation as limited and PA-11 as PENDING. `PHASE2CLOSE_C7_READINESS.md` correctly says **NOT READY FOR CUTOVER**. Human UI gates, client-profile logins, EXE-1 and worker-process native execution, the controlled FULL/NORMAL VM campaign and PA-11 attestation, C6 decisions, rollback overlay, development-line reconciliation, disposition of 11 Phase 1 failures, and written authorization remain open. There is no basis for **PHASE 2 ACCEPTED AND QUALIFIED**.

## H. Decision

Accept technical closure with physical and owner gates pending. Record D8 as a Low limitation to be handled by the existing PA-11 command and physical-cut attestation. No cutover or physical qualification is authorized by this review.

## NOT VERIFIED

I did not perform a client-profile login, native CLI execution inside the supervised worker, human UI session, actual VM hard power cut, NORMAL physical loss control, historical VAL-1 reproduction, K1 process-window experiment, or full-chain rerun. I did not read credentials. My local process-kill replay attempt timed out at `p.wait(30)`; I did not count it as a passing reproduction. Run9 was produced by the orchestrator and inspected here, including archive byte matching; I cannot independently prove no tree edit occurred during its historical execution. The apparent hypervisor command can only be checked against the real VM and owner operation at PA-11.

## FINAL VERDICT

**PHASE 2 CLOSURE ACCEPTED — PHYSICAL/OWNER GATES PENDING**
