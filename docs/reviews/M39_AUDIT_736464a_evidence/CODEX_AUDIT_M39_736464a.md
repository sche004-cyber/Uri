# Independent audit — URI M39 Office demonstrator

## 1. Scope and SHAs

**Verdict scope:** read-only audit of `736464aa317a3832f8592a02886047c6b2fc9f66` (`claude/project-thread-wb7tmm`) against frozen base `5bbf73856011fac7f8abad6970e664616a4c01ec`. M36/M37/M38 were frozen at `bd7c45068ed2f75cb68c9ea60f803e61a36dd7f2`. I inspected `git log`, `git diff --stat`, and `git diff --name-status` over the requested range. The checkout remained clean. M39 is PROVISIONAL and NOT FROZEN. Its plan, implementation/repair reports, User-decision record, commit messages, and internal re-audits are **CLAIMED_ONLY**; the observations below derive from diff, code, and executed probes.

## 2. Environment

Windows 11, Python 3.13.15, LF checkout (`core.autocrlf=false`); no network, model, live pilot, repair, or commit. Python ran through `audit_bootstrap_prev.py` with the working root on `PYTHONPATH` to handle denied private 0700 temp directories. The `tests/` and governance gates ran in `repo/`; qualification drivers that write result JSON ran in the same-SHA disposable `audit_driver_repo/` copy. Guard mutations ran only in `audit_guard_repo/`. Probe source and JSON results reside beside this report. Git's `clone --shared` cannot create a signal pipe here (`Win32 error 5`); the independent guard probe used a file copy.

## 3. Gate counts vs claims

| Gate | Independent result | Disposition |
|---|---|---|
| `python -m pytest tests/ -q` via bootstrap | **1,512 passed, 2 failed, 6 errors, 3 skipped; 130 subtests passed** (276.07 s) | Gate fails. One failure is sandbox PID liveness; one is M39's Windows `/dev/null` test defect. Six errors are Git clone setup failures, separately probed below. |
| `scripts/m36_memory_qualification.py --output ../audit_outputs` | 2 × 189 reference cases; wrong confirmations 0; deterministic true | **VERIFIED** offline gate. |
| `scripts/m37_edge_qualification.py` | 2 × 20 cases; gate passed, decision accuracy 1.0, false local successes 0 | **VERIFIED** offline gate. |
| `scripts/m38_harness_qualification.py` | 2 × 10 fake-harness scenarios; gate passed, false verified 0, unkilled processes 0 | **VERIFIED** offline gate, not a live harness result. |
| `scripts/m39_office_benchmark.py --dry-run --out ../m39_benchmark.json` | 12 tasks; dry-run gate PASS; 5 oracle-confirmed, 2 no-success refusals, 5 need a real harness; hard-gate counts 0 | **VERIFIED** dry run only. The mock Arm A and empty-fix fake Arm B do not measure VG-1. |
| `python -m pytest tests/governance -q` | **37 passed** | **VERIFIED**. |
| `python -m scripts.governance.uri_state_validator` via script bootstrap | `VALID`, exit 0 | **VERIFIED**. |
| `python scripts/m33_3_r_anchors.py` via bootstrap in `repo/` | `ok=True`, changed `[]`, 8 S4 and 24 LF anchors | **VERIFIED**. |

The other matching script, `scripts/m39_generate_benchmark.py`, generates fixtures rather than qualifying behavior. `scripts/m38_live_pilot.py` is a paid/live pilot driver and was not run under the no-network/no-model constraint. Implementer and internal-audit pass counts remain **CLAIMED_ONLY** wherever they exceed these independent observations.

## 4. Frozen line

`git diff --name-status 5bbf738 736464a` contains **no changes** under `uri_v1/memory`, `uri_v1/edge`, `uri_v1/execution`, `uri_v1/turn`, `uri_v1/reference_clarification`, `uri_v1/evaluation`, `uri_v1/results`, `uri_core`, or `uri_ui`, and none to M33.3 anchored implementation. Every changed frozen or frozen-owned path is listed here:

| Path | Change and authority | Guarantee assessment |
|---|---|---|
| `docs/governance/URI_ACTIVE_MILESTONE.md` | Additive M39 planning history, authorized by M39 plan/history and governance update. | No frozen behavior changed. Its older “planned, not implemented” entry is explicitly dated history. |
| `docs/governance/URI_STATE.yaml` | Additive M39 record and M37 `authorized_frozen_edits` at line 219. The record attributes the M37 test edit to User Chetan, 2026-09-29 05:21 UTC. | M36–M38 stay `CLOSED_FROZEN`; no frozen guarantee is reclassified. The M39 record itself discloses the R0/R1 scope conflict. |
| `docs/plans/URI_BATCH_M36_M37_M38_FREEZE_RECORD.md` | New §6 logs that same User authorization and exact-file tightening. | Historical freeze verdict preserved. |
| `tests/test_m37_edge_resolution.py` | Authorized exception for M39-only paths in `test_m36_and_frozen_files_unchanged`, recorded in governance line 219 and freeze record §6. | It broadens the old scope guard for M39 paths, but does not permit M36 or M33.3 changes. Its pre-existing M37/M38 prefixes remain a limitation (finding F2). |

The diff's **two deleted lines** are the former `allowed = (...)` continuation and `assert all(p.startswith(allowed) ...)`. They were replaced by `allowed = (...) + M39_ALLOWED`, `ok = (p.startswith(allowed) or p in M39_ALLOWED_FILES) and '..' not in p.split('/')`, and `assert all(ok(...))`. No production line was deleted. The M39 prefixes are `uri_v1/office/`, `fixtures/m39_office/`, `tests/test_m39_`; the three single-file entries are exact membership checks, with no glob or `..` path segment allowance.

## 5. Allowlist verification

The actual guard passed on unmodified HEAD in the disposable copy. It **failed** for a modified frozen `uri_v1/memory/contracts.py`, nonallowlisted `scripts/m39_office_benchmark.pyx`, and nonallowlisted `uri_core/audit_probe.py`. It **passed** for the three M39 prefixes and modifications of the three exact named files. Thus the M39 addition itself is narrow; the frozen Memory and live-app paths tested remain rejected. The actual guard also **passed unexpectedly** for a new `uri_v1/edge/audit_probe.py` and modified `uri_v1/edge/service.py` and `uri_v1/execution/workspace.py`: its *pre-existing* `uri_v1/edge/` and `uri_v1/execution/` prefixes already allow those paths. The requested claim that the **whole guard** cannot mask any M37/M38-owned path is false. This commit's independent base-to-head diff, rather than that guard, establishes those implementations stayed unchanged.

`tests/test_m39_frozen_guard_allowlist.py` has appropriate prefix/lookalike assertions and clone-based mutation cases, but six mutation cases cannot set up here because `git clone --shared` fails. The file-copy probe in section 7 executes the real guard and supplies the missing evidence. Authorization for the frozen test edit is recorded in the two governance artifacts above; that text is an authorization record, not a substitute for this probe.

## 6. Plan acceptance dispositions

The current plan is R1.1 and explicitly says R1 superseded R0. Its product acceptance table requires the real `/ask` interface, FileStore uploads/downloads, UI selection/polling, B1/B2 HTTP, B3 live, B-UI, and B5. **Those R1 requirements are not met.** The diff adds only an isolated `uri_v1/office/` backend/CLI, fixtures, tests, scripts, and docs; `uri_core` and `uri_ui` are unchanged. Governance lines 268–269 and 285–287 also disclose that narrower R0 implementation. `URI_WORKING_PRODUCT_BASELINE_REACHED` cannot be claimed. This is a scope/acceptance gap, not an unauthorized frozen change.

For the implemented **R0** subset, code and probes verify real M36 retrieval/RAR/S1 binding (`binding.py`), M37 Edge local-first routing (`flow.py`), M38 runner delegation after explicit consent (`flow.py`), and the shared `record_and_verify` path used by Edge/harness. `writeback.py` re-reads the exact run's M36 `VERIFIER_RESULT`, checks current source hashes, then invokes frozen `Workspace.write_back` with `WritebackApproval.from_user`; a failed or unoffered run and a changed original were refused. `execution/lineage.py` records the URI diff, S11 result-version hashes, M36 claimed outcome, and URI verifier record. The R1 FileStore returned-file and M36 `DERIVATIVE` chain is absent. The fake harness's false success claim became `HARNESS_FAILED/FAILED` and did not modify the original. The recorded User decision for two-filename requests is implemented: the initial request asks once for each role, each answer gets its own trusted turn, and frozen binding confirms both. A same-task paused run survived a new `OfficeSession`, resumed and wrote once; a later request created a new task.

R0 live Q-O3/Q-O4, R0 Windows Q-O6 on the User's machine, R1 B3/B-UI, real harness behavior, and product-level lineage remain **UNVERIFIED**. The current suite also fails as above. The CLI escalation view misleadingly says files copied to the harness are “never the network”; a real external Claude Code run necessarily sends file-derived content to its provider, contrary to the plan's consent disclosure (F3).

## 7. Every adversarial probe input and result

The following rows are the complete inputs/results from `audit_probes_m39.py`, `audit_flow_extra.py`, `audit_guard_probe.py`, and `audit_junction_probe.py`. `GRANTED` is a successful strict-grammar grant; `CLARIFY`, `ERROR`, and `WRITEBACK_REFUSED` are refusal/continuation results, not verification of a fix.

### Request, answer, consent, grant, path, and file flow probes

| Group | Exact input | Result |
|---|---|---|
| request | make report.py work with sales.xlsx | {"ok":true,"reason":null,"role":null} |
| request | make report.py.bak work with sales.xlsx | {"ok":false,"reason":"ROLE_AMBIGUOUS","role":"script"} |
| request | make ../report.py work with sales.xlsx | {"ok":false,"reason":"ROLE_AMBIGUOUS","role":"script"} |
| request | make C:\old\report.py work with sales.xlsx | {"ok":false,"reason":"ROLE_AMBIGUOUS","role":"script"} |
| request | make report.py work with sales.xlsx:evil | {"ok":true,"reason":null,"role":null} |
| request | make 'my report.py' work with 'sales 2024.xlsx' | {"ok":true,"reason":null,"role":null} |
| request | make report.py work with sales.xlsx and budget.xlsx | {"ok":false,"reason":"ROLE_AMBIGUOUS","role":"workbook"} |
| request | make old_report.py and report.py work with sales.xlsx | {"ok":false,"reason":"ROLE_AMBIGUOUS","role":"script"} |
| request | make report.py work with sales.xlsx~ | {"ok":false,"reason":"ROLE_AMBIGUOUS","role":"workbook"} |
| request | make report.py work with sales.xlsx​ | {"ok":false,"reason":"ROLE_AMBIGUOUS","role":"workbook"} |
| per_file_answer | report.py | [0,9] |
| per_file_answer | report.py and old_report.py | [0,27] |
| per_file_answer | ../report.py | [0,12] |
| per_file_answer | C:\old\report.py | [0,16] |
| per_file_answer | 'report.py' | [1,10] |
| per_file_answer | report.py for now | null |
| harness_consent | yes | true |
| harness_consent | go ahead | true |
| harness_consent | run it | true |
| harness_consent | yes for now | false |
| harness_consent | maybe yes | false |
| harness_consent | don't run it | false |
| harness_consent | nope, yes | false |
| harness_consent | yes? | false |
| harness_consent | yes ❌ | false |
| harness_consent | I approve | false |
| writeback_grant | apply the fix | GRANTED |
| writeback_grant | approve report.py | GRANTED |
| writeback_grant | yes, apply report.py | GRANTED |
| writeback_grant | maybe apply report.py | EXPLICIT_APPROVAL_REQUIRED |
| writeback_grant | don't apply report.py | EXPLICIT_APPROVAL_REQUIRED |
| writeback_grant | nope, apply report.py | EXPLICIT_APPROVAL_REQUIRED |
| writeback_grant | I approve report.py | EXPLICIT_APPROVAL_REQUIRED |
| writeback_grant | approve report.py for now | EXPLICIT_APPROVAL_REQUIRED |
| writeback_grant | can I apply report.py? | EXPLICIT_APPROVAL_REQUIRED |
| network_grant | allow network for this run | GRANTED |
| network_grant | maybe allow network | EXPLICIT_ELEVATION_REQUIRED |
| network_grant | don't allow network | EXPLICIT_ELEVATION_REQUIRED |
| network_grant | I allow network | EXPLICIT_ELEVATION_REQUIRED |
| network_grant | allow network for now | EXPLICIT_ELEVATION_REQUIRED |
| network_grant | can I allow network? | EXPLICIT_ELEVATION_REQUIRED |
| network_grant | allow network.server | EXPLICIT_ELEVATION_REQUIRED |
| network_grant | yes, allow network | GRANTED |
| workspace_path | ../report.py | INVALID_WORKSPACE_PATH |
| workspace_path | a/../report.py | INVALID_WORKSPACE_PATH |
| workspace_path | C:/report.py | INVALID_WORKSPACE_PATH |
| workspace_path | report.py:evil | INVALID_WORKSPACE_PATH |
| workspace_path | report.py | report.py |
| workspace_path | sales.xlsx | sales.xlsx |
| two_filename_flow | make report.py work with sales.xlsx | {"kind":"CLARIFY","asked":["script","workbook"]} |
| two_filename_answers | report.py; sales.xlsx | {"kind":"AWAITING_APPROVAL","reason":null,"run_id":"cf4c222db7e74955969f88d8956a12fd"} |
| wrong_run | run_id=ffffffffffffffffffffffffffffffff | {"kind":"ERROR","reason":"RUN_ID_NOT_OFFERED"} |
| changed_original | sales.xlsx overwritten after verification | {"kind":"WRITEBACK_REFUSED","reason":"WRITEBACK_SOURCE_NOT_CURRENT"} |
| no_verified_offer_or_stale | approve_writeback on task after previous step | {"kind":"WRITEBACK_REFUSED","reason":"WRITEBACK_SOURCE_NOT_CURRENT"} |
| resume_same_task | resume e595a75ded254348af86cca8d3d1332c | {"kind":"ERROR","reason":"NOT_PAUSED"} |
| malformed_workbook_flow | {"name":"bad.xlsx","bytes":14} | {"kind":"ESCALATION_PROPOSAL","reason":null} |
| malformed_workbook_flow | {"name":"broken.xlsx","bytes":10} | {"kind":"ESCALATION_PROPOSAL","reason":null} |
| malformed_workbook_flow | {"name":"oversize.xlsx","bytes":525312} | {"kind":"ESCALATION_PROPOSAL","reason":null} |
| symlink | authorized/linked.py -> outside/secret.py | {"found":false} |

### Harness claim and follow-up probes

| Group | Exact input | Result |
|---|---|---|
| flow | false claim setup | ESCALATION_PROPOSAL |
| flow | fake harness claims success, changes nothing | {"kind":"HARNESS_FAILED","verification":"FAILED","original_unchanged":true,"view":"[HARNESS_FAILED]\nThe harness's claim was checked and rejected (status: FAILED).\nNothing was written to your files."} |
| flow | approve failed harness run | {"kind":"ERROR","reason":"NO_PENDING_RUN"} |
| flow | ADS-looking workbook request | {"parse_ok":true,"step_kind":"CLARIFY","asked":["script","workbook"]} |
| flow | two filenames in one per-file answer | {"kind":"CLARIFY","script_state":"PENDING","script_ask":false} |
| flow | pause, new session, resume same task | {"pause":"PAUSED","stored_status":"PAUSED","resume":"AWAITING_APPROVAL","same_run":true} |
| flow | approve resumed verified run | {"kind":"COMPLETED","written":["report.py"]} |
| flow | new follow-up after completed task | {"kind":"NOTHING_TO_WRITE","new_task":true} |

### Actual frozen guard in disposable copy

| Group | Exact input | Result |
|---|---|---|
| guard | unaltered M39 HEAD | PASS |
| guard | modified frozen uri_v1/memory/contracts.py | FAIL:['uri_v1/memory/contracts.py'] |
| guard | new frozen uri_v1/edge/audit_probe.py | PASS |
| guard | modified frozen uri_v1/edge/service.py | PASS |
| guard | modified frozen uri_v1/execution/workspace.py | PASS |
| guard | new nonallowlisted scripts/m39_office_benchmark.pyx | FAIL:['scripts/m39_office_benchmark.pyx'] |
| guard | new nonallowlisted uri_core/audit_probe.py | FAIL:['uri_core/audit_probe.py'] |
| guard | new exact uri_v1/office/audit_probe.py | PASS |
| guard | new exact fixtures/m39_office/audit_probe.txt | PASS |
| guard | new exact tests/test_m39_audit_probe.py | PASS |
| guard | modified exact tests/m39_office_support.py | PASS |
| guard | modified exact scripts/m39_office_benchmark.py | PASS |
| guard | modified exact scripts/m39_generate_benchmark.py | PASS |

### Windows junction

| Exact input | Result |
|---|---|
| authorized/linked junction -> outside/secret.py | {"creation_returncode":0,"creation_output":"Junction created for .audit_tmp\\junction_probe\\authorized\\linked <<===>> .audit_tmp\\junction_probe\\outside","outside_file_found":false} |

## 8. Findings

| ID / severity | Location | Reproduction; expected vs observed |
|---|---|---|
| F1 **HIGH** | `docs/plans/M39_OFFICE_DEMONSTRATOR_PLAN.md:1-5, 43-67`; `uri_v1/office/__main__.py:3`; `docs/governance/URI_STATE.yaml:268-269` | Compare R1.1 T1–T11/B1–B-UI requirements with the base-to-head diff. Expected: Office flow through `/ask`, FileStore and UI, with return-file lineage. Observed: isolated CLI/R0 backend only; no `uri_core` or `uri_ui` changes. The current M39 acceptance target is incomplete. |
| F2 **MEDIUM** | `tests/test_m37_edge_resolution.py:279-281` | Add/modify `uri_v1/edge/audit_probe.py`, `edge/service.py`, or `execution/workspace.py` in disposable copy; run the actual guard. Expected under the requested frozen-path protection: fail. Observed: pass due pre-existing M37/M38 prefixes. M39's new allowlist did not cause this, and the base-to-head diff independently shows no such change. |
| F3 **MEDIUM** | `uri_v1/office/view.py:41-44` | Render an `ESCALATION_PROPOSAL`. Expected: plainly disclose that real external harness use sends file-derived content to the provider, as plan §4.4 requires. Observed: “Files that will be copied to the harness (never the network)” and “no network”; misleading for an external model call. |
| F4 **MEDIUM** | `tests/test_m39_repair4_regressions.py:113` | Run full `tests/` gate on Windows. Expected: portable test output sink and pass. Observed: `bench.main(..., '--out', '/dev/null')` raises `FileNotFoundError` for `\\dev\\null`; one of the two suite failures. |

## 9. Environment-limited and unverified items

**ENVIRONMENT_LIMITED:** `tests/dev_workflow/test_visible_worker.py::...test_second_launch_for_same_task_is_refused` did not raise because sandbox PID-liveness handling differs; classified as the known artifact specified in the task. Six `test_m39_frozen_guard_allowlist.py` setup errors stem from Git for Windows `clone --shared` signal-pipe denial (`Win32 error 5`); the real guard was independently exercised via file copy. No live pilot or paid/model run was authorized. The M39 dry run confirms only offline behavior; its five outside-envelope tasks need a real harness. No user-machine UI test, HTTP Office seam test, or real-provider containment test is available at this SHA. Existing harness/verifier OS sandbox limitations remain documented; this audit made no claim to resolve them.

## 10. Verdict

**REPAIRS_REQUIRED. M39 is not ready for a User freeze decision on the current R1.1 plan.** The frozen implementation line is intact and the authorized M39 allowlist addition is narrow. The current product acceptance scope is materially unfinished, the full test gate fails on Windows, and the escalation disclosure needs correction. The inherited M37/M38 guard limitation should be documented or independently enforced before using that guard as proof of frozen-path integrity.
