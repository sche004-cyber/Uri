# Independent review: Phase 2 closure, round 2

Reviewed 2026-10-08. Subject: `phase2close-candidate-20261008-b.zip` and its byte-identical live tree. I read the round-1 report, the repaired code and tests, governing closure documents, and run5 evidence; independently checked archive hashes and contents; and ran focused synthetic probes. I did not modify repository source, tests, configuration, or documents. My only writes were these review artifacts and probe runtime state under `uri-agent/work/c1`.

## A. Integrity

The subject SHA-256 is `3ab0a859799b626841ce1aec87f168b37e5d48a90ff80ed435d510f846fc121b`, matching `ROUND2_SUBJECT.txt` and the sidecar. I independently hashed the rejected `-a` archive (`8fc1d5e818dc99bb15511d7e29bb3786678cab85c69f6f8f17249329099e2470`), the round-7 archive (`9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a`), and the Phase 1 checkpoint (`31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`). The live HEAD is `e8e3b65259c45fc823addc3ef8969425a265bd1b`.

The `-b` manifest has exactly 168 names, matching all 137 tree files and 31 evidence files in the archive, with no bad digests. All 137 archived tree files exist and are byte-identical in the live tree. All 31 embedded run5 evidence files are byte-identical to `evidence/phase2close/run5`. The 121 Phase 1 checkpoint source files are present and byte-identical in the live tree. The full comparison and exact filename lists are reproducible with [audit_round2.py](audit_round2.py).

Relative to `-a`, `-b` adds only `tests/phase2close/test_acceptance_tooling.py` and changes eight files: `scripts/phase2close_acceptance.py`, `scripts/phase2close_powerloss_harness.py`, `tests/phase2close/test_powerloss_harness.py`, and five closure/development documents. No file was removed. Thus the regression scope, accepted tests outside the closure harness, and production paths confirmed in round 1 are byte-identical to `-a`. Relative to round 7, there are 20 added, 15 changed, and no removed tree files, exactly listed by the audit script.

## B. D1: client-profile qualification

`probe_environment` (`scripts/phase2close_acceptance.py:156-169`) removes every built-in executor `auth_env` credential except `CODEX_HOME`, both explicit never-forward variables, and names ending case-insensitively in `_API_KEY`, `_TOKEN`, `_SECRET`, or `_PASSWORD`. It overwrites the inherited `CODEX_HOME` with `<client_root>/home/.codex`; `HOME`, `USERPROFILE`, `APPDATA`, and `LOCALAPPDATA` are set to the client profile. The direct probe then uses `spec.build_env`, while `native_auth_probe` uses `harness_env`; both are allow-lists (`uri_supervisor/executors.py:114-116`, `uri_core/client_runtime/harness.py:46-49`). The probe uses `DEVNULL` for stdin and captures stdout/stderr (`phase2c_native_qualification.py:86-87`); auth status does the same (`qualification.py:326-328`). I found no inherited credential handle passed to those children in these calls.

My synthetic probe injected uppercase and lowercase provider-token names, other suffix forms, and a wrong `CODEX_HOME`. The returned environment excluded all injected tokens and pinned `CODEX_HOME` to the client root. A stubbed successful direct probe followed by `live_auth=False` observed no token in either call, returned exit 2, left no qualification record, and restored the caller's token variable. The output is reproducible with [probe_round2.py](probe_round2.py). `qualify` uses `try/finally` around the process-environment substitution (`:193-203`), and writes a signed record only when both direct probe and live auth are true (`:211-219`). An exception also reaches the restore block. There is no independent proof of a real client-profile login because I did not log in or read credentials; the code and synthetic probe support D1's repair for the built-in CLIs. `qualify` mutates process-global `os.environ` briefly, but this CLI is single-threaded in the reviewed path; no concurrent caller was found.

## C. D2: power-loss harness

`host` passes boolean shell-command results to `campaign`; a false power-off/on result stops with a failing row (`phase2close_powerloss_harness.py:278-285,325-336`). `iteration_verdict` refuses an iteration with no acknowledged work (`:97-101`). Host output is labelled `VM_SERIES` with `SERIES_ALL_PASS`/`SERIES_FAIL`; simulation is `SIMULATED_ONLY_NOT_A_QUALIFICATION` (`:306-320`). No machine-produced output says physically qualified. `assess` always returns `qualified:false`, and its best label explicitly awaits owner attestation (`:342-363`). The runbook requires a real hypervisor hard-off and owner confirmation (`PHASE2CLOSE_PHYSICAL_ACCEPTANCE_RUNBOOK.md:160-190`). This repairs round-1's physical-verdict ambiguity.

There is a new evidence-validation defect: `assess` trusts the summary's `SERIES_ALL_PASS`, `iterations_run`, `synchronous`, `power_method`, and `lost_acknowledged_steps` fields independently. It does not compare `passed`/`failed`/`iterations_requested`, load `iterations.json` or `acks.jsonl`, or check that the NORMAL control ran any iteration. My probe supplied a purported FULL series with `iterations_run=200`, `passed=0`, `failed=200`, `lost_acknowledged_steps=200`, and `verdict=SERIES_ALL_PASS`, plus a purported NORMAL control with `iterations_run=0`, `passed=0`, `failed=0`, and `lost_acknowledged_steps=1`. `assess` returned `EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION`, no reasons, and `qualified:false`. Such summaries could not be produced by a coherent campaign. The tool nevertheless tells an owner the evidence is sufficient. This conflicts with the runbook statement that `assess` *requires* every FULL iteration to pass and a NORMAL control that actually detected loss. See D4 below. The new tests cover selected single-field refusals but not contradictory fields or underlying iteration evidence.

The closure checklist's B4 criterion still says `ALL_ITERATIONS_PASS`, which the repaired harness no longer emits (`SERIES_ALL_PASS` is the new series label). The physical runbook uses the new labels. See D5.

## D. D3: one green full chain

Run5 contains one `chain_summary.json` with all seven ordered gates, started 05:45:35 and finished 06:12:23, `ALL_PASS:true`. I read the logs, not just the summary. Phase 2: 445 passed, 2 skipped, exit 0. Phase 1 authority: 134 passed, exit 0. Phase 1 full: 2675 passed, 12 skipped, 11 failed, exit 1 as expected by the gate; its 11 failure IDs equal the round-7 baseline's 11 IDs, independently compared from the two logs. Residue: none. Flutter: 195 passed, 2 skipped, exit 0. Ten live bridge JSONs report exit 0 and `refusals.txt` is empty. Native stdout reports lifecycle `completed/SETTLED_VERIFIED`, mid-run cancel `uncertain/CANCELLED_AFTER_DISPATCH`, executor `DEAD`; the native report identifies programmatic approval and the owner-shell in-process composition, not a client-profile worker run. The 31 run5 evidence files embedded in `-b` match the external run5 folder byte for byte. This closes D3 as an evidence gap. The assertion that no edit occurred *during* the run is an orchestrator claim; the final archive and embedded log consistency support the final-tree association, but I could not observe the historical process in real time.

## E. K1 and VAL-1 correction

K1/SUP-1 remains in `uri_supervisor/winproc.py:256-261`: a kill during or just after suspended process creation can leave an unassigned suspended child. The C7 readiness document records this as Low, says it had two simulated occurrences, and does not claim it is repaired. Low is proportionate to the observed orphan window and absence of a resumed effect; that does not prove a physical test has closed it. The widened wording is honest.

The closure report now explicitly states the historical VAL-1 incident is unattributable and names the other varying 403 path, `_authorize` -> `EXECUTION_AUTHORITY_UNAVAILABLE` (`PHASE2CLOSE_REPORT.md:40`). It keeps the deterministic clock-boundary reproduction as a *mechanism*, not historical proof. This corrects the round-1 text overstatement.

## F. New defects and round-1 confirmations

| ID | Severity | Location | Finding and independent basis | Effect |
|---|---|---|---|---|
| D4 | Medium, blocking technical closure | `scripts/phase2close_powerloss_harness.py:342-363`; runbook `:183-186` | `assess` accepts internally contradictory FULL and zero-iteration NORMAL summaries as `EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION`; synthetic call reproduced. It validates neither counts nor raw iteration evidence. | A weak or mislabeled series can be presented as sufficient to an owner, although `qualified` stays false. Validate coherent counts and per-iteration/source evidence, or explicitly downgrade the assessment to an unverified summary check. |
| D5 | Low, documentation | `docs/plans/PHASE2CLOSE_CLOSURE_CHECKLIST.md:34` | B4 still requires `ALL_ITERATIONS_PASS`, a verdict removed by the D2 repair. | The written acceptance criterion cannot be satisfied literally; update it to the new series and assessment terms. |

Round-1 confirmations still hold on `-b` because their implementation and accepted-test files are unchanged from `-a`: LOG-3 bounds the retained ASGI body prefix; VAL-1's bounded resend is restricted to an unchanged approving turn; CAP-1 releases only an undispatched pending turn through the frozen cancel route; ISO-1 pins Codex home in the supervised worker; and the changed Phase 2D assertions remain disclosed. I did not rerun the full implementations independently. The run5 Phase 2, authority, full-suite, Flutter, bridge, and native logs give corroborating executed evidence for this exact `-b` archive. The 11 Phase 1 failures remain unresolved and not accepted for cutover.

### Round-1 finding disposition

| Round-1 finding | Round-2 disposition | Basis |
|---|---|---|
| D1 High: shell tokens could qualify a client | REPAIRED | Environment stripping, client `CODEX_HOME` pin, restored caller, synthetic no-login fail-closed probe. |
| D2 High: host could report a physical pass from arbitrary commands | REPAIRED AS TO PHYSICAL LABEL; NEW D4 | Host now emits series-only labels and checks power-command return and acknowledged work; `assess` never qualifies. Assessment can still call contradictory evidence sufficient. |
| D3 Medium: no single green full chain | CLOSED | Run5 seven-gate `ALL_PASS:true`, logs and embedded archive evidence checked. |
| K1 Low: suspended orphan window | RECORDED, OPEN | Unchanged `winproc` window; C7 document keeps it open with appropriate severity. |
| VAL-1 text: clock overstated as sole varying 403 cause | CORRECTED | Report names `_authorize` and preserves uncertainty about the historical incident. |
| LOG-3 bound | CONFIRMED FROM UNCHANGED FILES AND RUN5 | Same bridge file/test bytes as `-a`; Phase 2 gate passes. |
| VAL-1 mechanism and one resend | CONFIRMED FROM UNCHANGED FILES AND RUN5 | Same bridge and test bytes; historical event remains unattributable. |
| CAP-1 release | CONFIRMED FROM UNCHANGED FILES AND RUN5 | Same bridge, worker and test bytes. |
| ISO-1 worker home pin | CONFIRMED FROM UNCHANGED FILES AND RUN5 | Same worker/qualification files and test bytes; D1 probe adds a direct pin check. |
| Changed accepted Phase 2D tests | HONEST, UNCHANGED | Same tests as `-a`, with the CAP-1 behavior change still disclosed. |

## G. Readiness claim and C7

`PHASE2CLOSE_C7_READINESS.md` correctly says **NOT READY FOR CUTOVER**. EXE-1 (node-based CLI in the worker), client-profile login, owner UI session, physical power loss, C6 decisions, rollback overlay, development-line reconciliation, the 11 baseline failures, and written cutover authorization remain open. Run5's native path is explicitly in-process under the owner's shell login. No physical or owner gate is shown passed. The report's “PHASE 2 TECHNICALLY READY — PHYSICAL/OWNER GATES PENDING” is premature while D4 lets the power-loss assessor call contradictory evidence sufficient, and the checklist's B4 statement is stale. A13's narrow wording (“`assess` never returns qualified”) is true, but the runbook promises more than that. There is no basis for “accepted and qualified.”

## H. Decision

Repair D4 by making `assess` reject incoherent counts and requiring traceable iteration evidence for the FULL and NORMAL series, then correct B4 and obtain focused regression evidence on the repaired candidate. D1-D3 are closed. Physical and owner gates remain separate and pending. The present `-b` candidate does not meet its own technical power-loss evidence criterion.

## NOT VERIFIED

I did not perform a client-profile CLI login, execute native Codex in the actual supervised worker process, click the real UI, power-cycle a VM, witness a NORMAL control lose an acknowledged commit, reproduce the historical VAL-1 event, or rerun the full 25-minute chain. I did not read credential files. Two pure harness tests ran locally and passed (`2 passed, 8 deselected`). The two acceptance-tooling pytest tests errored at fixture/setup because this sandbox denied enumeration of `work/c1/round2-pytest` (`WinError 5`); my direct synthetic probe of the same critical logic completed. Run5 is orchestrator-produced evidence inspected and archive-matched, not personally executed by this reviewer. I did not experimentally exercise K1.

## FINAL VERDICT

**PHASE 2 CLOSURE REJECTED**
