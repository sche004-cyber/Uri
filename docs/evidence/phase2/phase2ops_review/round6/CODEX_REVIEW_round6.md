# URI Phase 2 UI/operations independent review, round 6

Date: 2026-10-07. Subject: `phase2ops-candidate-20261007-r5.zip`, matching uncommitted tree at `e8e3b65259c45fc823addc3ef8969425a265bd1b`. Implementer records and orchestrator logs were treated as claims. I changed no repository source, test, document or configuration file, and did not touch account or credential state. I could not run pytest or Flutter in this sandbox. My own work was hashing, direct-import ASGI probes, source inspection and read-only SQLite queries.

## A. Integrity and Phase 1 frozen boundary

The subject ZIP hashes to `1daa73f75f096ee039f9a039b96516cd821574724d8f663b8eea4acb46f6c047`, matching `ROUND6_SUBJECT.txt` and its sidecar. Its 238 manifest entries (116 tree, 122 evidence) all match the archive bytes and corresponding live files; the other three members are `GIT_HEAD.txt`, `GIT_STATUS.txt` and `MANIFEST.json`. There were zero mismatches. Earlier archive hashes remain: r4 `fc9c96ec2b5b44a70f8486dccd9d0aa2b2eb28dafa01f9ac6f6e1594e251ed58`; r3 `fdfb78edf9621ee8828d6a4a10c5a466fa3116f22e8c82cfea100a2e05937b64`; r2 `05127e2fe87ef869e83eeddcdcae47cc3eb804dd5bce791b34860b966b1cbead`; r1 `bffa742ac9f8b4e6aadebde8bb91aa6c22638be6b4feeca6a5cfb7a0a1aa8ec7`; original `ce935c4be0e29c67d0d34772c9584e8ce3ac836e118e490ad167d8447d13d9d8`; Phase 2D r2 `cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d`.

The Phase 1 closure ZIP exists at the path pinned by `tests/phase2a/test_frozen_core.py`. I independently obtained SHA-256 `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`; all 121 non-metadata files are byte-identical in this tree. The execution path (`uri_supervisor_bridge/execution.py`, `runner.py`), both composition wrappers, and the supervised Dart runtime and screen are byte-identical between r4 and r5 ZIPs. This is still uncommitted candidate work, not a frozen milestone.

## B. Earlier findings, LOG-1 and VAL-1

### Disposition table

| Earlier finding | Round-6 disposition | Basis |
|---|---|---|
| OPS-1 | Repaired within the local-state trust boundary | Execution file digest equals r4; r5 native and live records show completed only with `SETTLED_VERIFIED`; round-5 direct corroboration probe remains applicable. |
| OPS-2 | Repaired for invalid record schema | Execution file digest equals r4; round-5 direct malformed-record probes remain applicable. |
| OPS-3 | Repaired on source inspection | Dart screen digest equals r4; exact arguments and argument digest precede Approve at `supervised_execution_screen.dart:356-370`. Human interaction unverified. |
| OPS-1R | Repaired within the local-state trust boundary | Execution and runner digests equal r4; operation ownership and journal/ledger corroboration remain. Preserved native ledger request IDs match execution and operation records. |
| OPS-2R | Repaired for demonstrated nested-shape failure | Python and Dart file digests equal r4; round-5 direct type probes and checked Dart reads remain applicable. Flutter not rerun here. |
| OPS-4 | Repaired on source and recorded native path | Both wrapper digests equal r4 and forward `**kw` (`phase2c_native_qualification.py:172-174`, `phase2d_composition_qualification.py:106-108`); r5 native run ended completed/uncertain as intended. Phase 2C wrapper was not independently rerun. |
| OPS-5 | Repaired on source | Execution digest equals r4; unreadable/non-object ledger request handling remains as reviewed in round 5. |
| LOG-1 | **Partially repaired; residual LOG-1R below** | Raw path and arbitrary free text are replaced, but the regex is a format check, not an allowlist. Synthetic uppercase response detail reaches the log. |
| VAL-1 | **Open observation, not by itself a blocker for this bounded slice** | Original approval `HTTP_403` cause remains unknown. Seventeen subsequent recorded bridge repetitions (2 + 5 + 10) were clean; the r5 diagnostic recorded zero refusals. Qualification owner must investigate any recurrence in physical use. |

The r5 `phase2_all.log` command targets `tests/phase2a` through `tests/phase2ops` under isolated Python and ends **414 passed, 2 skipped, exit 0**. `phase1_authority.log` names eight authority files and ends **134 passed, exit 0**. `phase1_full.log` ends **11 failed, 2675 passed, 12 skipped, 88 subtests passed, exit 1**; its eleven failure IDs are the same Drive step3/step4, privacy, M20 feasibility/recovery/semantic resilience, session-facts, usage-newline and workflow-restart IDs reported in round 5. That is a non-green full suite and their cause was not established here. `flutter_all.log` ends **191 passed, 2 skipped**. These are log reads, not test executions by this reviewer.

All ten `ui_bridge_live_1..10.json` files report exit 0; each corresponding stdout ends `All tests passed!`, and each has one `completed/SETTLED_VERIFIED` and one `uncertain/SETTLED_EXECUTION_UNCERTAIN` execution with matching operation owner. `refusals.txt` is empty. The native `codex_cli_lifecycle_233344.json` and stdout claim direct CLI OK, live auth true, persisted native qualification, completed lifecycle, and uncertain mid-run cancellation with dead attempt PID. I independently opened preserved `execution-journal.sqlite3` and supervisor `ledger.db` with SQLite `mode=ro&immutable=1`: the lifecycle task is COMPLETE with verified journal operation; the cancellation task is FAILED with `execution_uncertain`; each ledger request binds the matching execution and operation ID. This checks persisted state, not the live process or authentication.

The recorded clean repetitions make the isolated 403 a monitoring/physical-qualification item, not evidence of a presently failing bounded flow. They do not identify the original refusal reason or prove it cannot recur. The r5 logger's intended diagnostic would help only after its residual disclosure path is fixed.

## C. New defects introduced by the repair

### DEFECTS table

| ID | Severity | File:line | Failure and evidence | Reproduced? |
|---|---|---|---|---|
| LOG-1R | Medium | `uri_supervisor_bridge/refusal_log.py:19,34-44` | `_CODE` accepts **any** uppercase identifier up to 48 characters; it is not a set of approved refusal codes. The response body's arbitrary `detail` `SECRET_CANARY_987` was printed verbatim in `CLIENT_REFUSAL`. `_METHOD` similarly accepts any 3–8 uppercase request method, so synthetic `SECRETX` also printed. A real secret leak was not observed. Replace these with explicit approved values (or a fixed method label) before claiming that only allowed codes/shape/status are logged. | **Yes**, direct-import `refusal_line` probe with synthetic canaries. |
| LOG-2 | Low | `uri_supervisor_bridge/refusal_log.py:53` | `startswith('/client/v1')` includes `/client/v1evil/secret`, an outside route. A synthetic 403 on that path logged a line. `/other` 403 and `/client/v1/session` 200 passed through without logging, with response status preserved. Match `/client/v1` exactly or its `/`-delimited descendants. | **Yes**, direct isolated ASGI wrapper probe. |

The wrapper does not inspect request headers or request bodies. It masks non-literal path segments and drops query text. Arbitrary mixed-case/free-text response details become `NON_CODE_DETAIL`; a non-JSON or non-object body becomes `NON_JSON_BODY`. Those properties hold for the probes and inspected source, but do not make the claimed allowlist true. I did not observe a production endpoint returning a secret-shaped uppercase detail or a client calling `/client/v1evil`; the findings establish an unsafe diagnostic invariant and an incorrect route boundary.

## D. UI wiring, physical qualification, remaining slices and research ledger

| UI wiring question | Determination | Basis |
|---|---|---|
| (a) Worker protocol | YES | Supervised proposal/begin/status/cancel/list path remains byte-identical to r4; recorded suites and bridge artifacts exercised it. |
| (b) Programmatic composition | YES for exercised Phase 2D/native path; Phase 2C source-compatible but not rerun | Both wrappers forward `**kw`; r5 native persisted path corroborated. |
| (c) Opt-in profiles | YES | Per-installation supervised profile and manifest-backed startup remain; no cutover evidenced. |
| (d) Real Flutter UI driving worker | PARTIAL | Tasks mount and screen/runtime exist; widget tests and ten live Dart-to-worker records are archived. Human approve/cancel/reopen in a running app was not observed. The profile diagnostic still has LOG-1R/LOG-2. |
| (e) Cutover | NO | C7 owner authorization, pinned UI and Chat/voice decision, migration/launcher/rollback, and full-suite triage remain. |

USER-PHYSICAL / NOT VERIFIED: human approve, cancel and reopen in the running Flutter app; client-profile native CLI authentication and execution inside the actual isolated worker; controlled 200+ hard power-loss/write-ordering qualification. C7 requires separate owner authorization and its independent gates. Context Capsule and Task Compiler remain design-only, later undated work; there is no accepted 2E/2F numbering. Chat `/ask` migration and pinned UI release remain C6/C7 decisions.

Research ledger wording must distinguish research from delivery: Strata/Paperclip and AG-UI/A2UI are research/deferred; MCP broker and Context Capsule/Task Compiler are design only; model residency is a separate prototype; URI Memory in Core is not a delivered harness capsule. Supervisor recovery and Phase 2D have process/native evidence but no physical power-loss qualification. `PHASE2OPS_REPORT.md` correction record 5 acknowledges candidate status and VAL-1; its claim of an allow-listed refusal code is overstated by LOG-1R. Earlier `IMPLEMENTED / TESTED` wording applies only to recorded paths, not whole Phase 2 or C7.

## E. Verdict

Integrity and the Phase 1 frozen boundary hold. The earlier execution/UI findings remain repaired within the reviewed boundary; the r5 recorded bridge and native runs ended as claimed. VAL-1 remains an unexplained isolated observation for the owner's physical qualification and would not alone reject this bounded slice after the clean repetitions. The new refusal diagnostic still logs arbitrary uppercase response detail and short uppercase request methods, and includes routes outside `/client/v1`. Its safety claim is a security property of this repair and remains false, so this candidate is rejected. Phase 2 implementation and freeze are not established.

## NOT VERIFIED

- Independent pytest or Flutter execution; full-suite failure root causes; Phase 2C native rerun; exhaustive cancellation races.
- Human Flutter interaction, actual client-profile native worker authentication, controlled physical power-loss campaign, production migration or cutover.
- Root cause or recurrence probability of the original HTTP 403; a real secret disclosure through the logger.

## FINAL VERDICT

**UI/OPERATIONS SLICE REJECTED**
