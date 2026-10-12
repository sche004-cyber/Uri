# URI Phase 2 UI/operations independent review, round 7

Date: 2026-10-08. Subject: `phase2ops-candidate-20261008-r6.zip`, SHA-256 `9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a`, uncommitted tree on `e8e3b65259c45fc823addc3ef8969425a265bd1b`. Implementer records and orchestrator logs were treated as claims. I changed no repository source, tests, documents, or configuration. The direct checks below used standard Python imports, ZIP/hash reads, and isolated ASGI probes; no pytest, Flutter, credential operation, account change, or live CLI login was performed. Probe script: `evidence/phase2ops_review/round7/check_round7.py`.

## A. Integrity and Phase 1 frozen boundary

The subject ZIP digest matches `ROUND7_SUBJECT.txt` and the sidecar. Its 269 manifest entries (117 tree, 152 evidence) match the archive member bytes and their corresponding live files; zero mismatches. The other three members are `GIT_HEAD.txt`, `GIT_STATUS.txt`, and `MANIFEST.json`. Compared bytewise with the preserved r5 ZIP (`1daa73f75f096ee039f9a039b96516cd821574724d8f663b8eea4acb46f6c047`), the only changed tree members are `uri_supervisor_bridge/refusal_log.py`, `tests/phase2ops/test_refusal_log.py`, `docs/plans/PHASE2OPS_REPORT.md`, and new `docs/plans/PHASE2OPS_REVIEW_REPAIR_ROUND6.md`. All other differences are newly archived r6 evidence; execution, worker, server, and Dart files are byte-identical. This is archive-to-archive evidence, not an inference from implementer prose.

I rehashed earlier archives: r4 `fc9c96ec2b5b44a70f8486dccd9d0aa2b2eb28dafa01f9ac6f6e1594e251ed58`; r3 `fdfb78edf9621ee8828d6a4a10c5a466fa3116f22e8c82cfea100a2e05937b64`; r2 `05127e2fe87ef869e83eeddcdcae47cc3eb804dd5bce791b34860b966b1cbead`; r1 `bffa742ac9f8b4e6aadebde8bb91aa6c22638be6b4feeca6a5cfb7a0a1aa8ec7`; original `ce935c4be0e29c67d0d34772c9584e8ce3ac836e118e490ad167d8447d13d9d8`; Phase 2D r2 `cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d`. The Phase 1 closure ZIP hashes to `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`; all 121 non-metadata checkpoint files match the live tree byte-for-byte. No milestone commit or freeze follows from these checks.

## B. LOG-1R, LOG-2, earlier findings, and VAL-1

`KNOWN_CODES` has 61 members. My independent extraction of static `ClientControlError`, `PairingError`, `ExecutionControlError`, `StatePortError`, `HTTPException.detail`, and response `detail` literals from the six frozen source files named at `uri_supervisor_bridge/refusal_log.py:18-21` also found 61, with no missing or extra members. This matches the actual static refusal vocabulary on this server path, including `CLIENT_SCHEMA_INVALID` and `REQUEST_LIMIT`. It does not prove that a future dynamic exception string could never differ; the logger maps any differing detail to `OTHER_CODE` safely. The allow-list is now a set membership check (`:22-36,51-56`), not the r5 format regex. Direct `refusal_line` probes mapped `SK_LIVE_SECRET_TOKEN`, `BEARER_ABC`, and `SESSION_SCOPE_EXTRA` to `OTHER_CODE`, while retaining `SESSION_SCOPE`; unknown method `BEARERX` mapped to `OTHER_METHOD`. `in_scope` matched exact `/client/v1` and slash descendants, excluding `/client/v1evil/x` and `/client/v10/x` (`:59-61`). Direct ASGI probes logged one in-scope 403, logged no out-of-scope 403 or in-scope 200, and passed all responses through.

`route_shape` (`:42-48`) strips a query, replaces non-literal segments, and caps output at eight segments. `refusal_line` (`:64-70`) prints only GET/POST or `OTHER_METHOD`, and an integer status from 100 through 599 or `0`; I reproduced bad-status handling with the added test's direct call behavior. The wrapper inspects response bodies only for in-scope status >=400. It never accesses request headers, request body, query string, or 2xx body (`:78-91`). It slices the *joined* response body to 4096 bytes before JSON parsing. The output is bounded, but buffering before that slice is not; see C. Non-JSON error output maps to `NON_JSON_BODY` in my multi-chunk probe.

### Disposition table

| Earlier finding | Round-7 disposition | Basis |
|---|---|---|
| OPS-1 | Repaired within local-state trust boundary | Execution file byte-identical to r5/r4; ten archived bridge runs report completed only with `SETTLED_VERIFIED`; earlier direct corroboration probe applies. |
| OPS-2 | Repaired for invalid record schema | Execution byte-identical; earlier malformed-record probes apply. |
| OPS-3 | Repaired on source | Dart screen byte-identical; exact arguments and argument digest precede Approve. Human interaction remains unverified. |
| OPS-1R | Repaired within local-state trust boundary | Execution/runner byte-identical; operation ownership and journal/ledger corroboration remain; archived records bind owners to execution IDs. |
| OPS-2R | Repaired for reviewed nested shapes | Python/Dart files byte-identical; previous type probes remain applicable. Flutter not rerun here. |
| OPS-4 | Repaired on source and archived native path | Both qualification wrappers remain byte-identical and forward `**kw`; r6 native artifact reports intended lifecycle. Phase 2C wrapper not independently rerun. |
| OPS-5 | Repaired on source | Execution byte-identical; unreadable/non-object ledger handling remains. |
| LOG-1 | Repaired, with LOG-1R repaired | Raw path and arbitrary detail no longer printed; direct canary probes passed. |
| LOG-1R | Repaired | Explicit 61-code allow-list matches static server code extraction; unknown uppercase details and method masked in direct probes. |
| LOG-2 | Repaired | Slash-delimited scope and direct out-of-scope ASGI probe. |
| VAL-1 | Open observation; physical-qualification item, not this slice blocker | Original isolated approval `HTTP_403` remains unexplained. The archived r6 diagnostic has zero refusal lines and ten additional clean bridge runs. This neither identifies the original cause nor establishes nonrecurrence. |

I read, but did not run, the orchestrator logs. `phase2_all.log` explicitly invokes isolated pytest on `tests/phase2a` through `tests/phase2ops` and ends **415 passed, 2 skipped, exit 0**. `phase1_authority.log` names the eight authority tests and ends **134 passed, exit 0**. `phase1_full.log` ends **11 failed, 2675 passed, 12 skipped, 88 subtests passed, exit 1**. Its failure IDs are the same Drive step3/step4, privacy, M20 feasibility/recovery/semantic resilience, session facts, usage newline, and workflow restart IDs identified in round 6; their root causes remain unestablished. `flutter_all.log` ends `+191 ~2: All tests passed!`. These are archived run claims, not reviewer executions.

I independently parsed all ten `ui_bridge_live_1..10.json` files and matching stdout: every JSON reports exit 0, every stdout ends `All tests passed!`, and each has one `completed/SETTLED_VERIFIED` and one `uncertain/SETTLED_EXECUTION_UNCERTAIN` with matching operation owner and execution ID. `refusals.txt` is empty. The archived `codex_cli_lifecycle_000547.json` and stdout report a direct CLI probe exit 0/OK, live-auth status true, persisted native qualification, a completed `SETTLED_VERIFIED` lifecycle, and an uncertain `SETTLED_EXECUTION_UNCERTAIN` mid-run cancel with dead attempt PID. I checked the artifact's nested `final` fields, not only its summary. I did not reproduce the native process or inspect live authentication. The ten additional clean runs strengthen the round-6 VAL-1 disposition without resolving its cause.

## C. New defects introduced by the repair

### DEFECTS table

| ID | Severity | File:line | Finding and evidence | Reproduced? | Slice effect |
|---|---|---|---|---|---|
| None introduced in r6 | — | — | Only the logger, its test, and documents changed from r5; LOG-1R and LOG-2 are repaired and no new functional or disclosure regression was found. | Direct probes and archive comparison | None |
| LOG-3 observation, pre-existing since the diagnostic | Low | `uri_supervisor_bridge/refusal_log.py:81,86-89` | `chunks.append` retains every error response chunk and `b"".join(chunks)` runs before `[:4096]`. Thus the 4096-byte *log/parse* cap is not a memory cap. My 10 KB two-chunk ASGI probe passed through and logged only `NON_JSON_BODY`; source establishes that larger error bodies consume proportionate memory. The frozen normal refusal bodies are small, and I did not demonstrate an attacker-controlled large error response on the production route. Bound collection to the first 4096 bytes as a later hardening fix. | Yes for multi-chunk path; unbounded allocation from source | Does not reject this bounded slice on current evidence. |

## D. UI wiring, USER-PHYSICAL, remaining work, and research ledger

| UI wiring question | Determination | Evidence / limit |
|---|---|---|
| (a) Worker protocol | YES | Proposal/begin/status/cancel/list implementation byte-identical to r5 and archived tests/bridge records exercise it. |
| (b) Programmatic composition | YES for exercised Phase 2D/native path; Phase 2C source-compatible but not rerun | Both wrappers forward `**kw`; native lifecycle archive records verified and uncertain paths. |
| (c) Opt-in profiles | YES | Manifest-backed supervised profile and per-installation opt-in remain; no cutover shown. |
| (d) Real Flutter UI driving worker | PARTIAL | Tasks mount, screen/runtime, widget tests, and ten archived live Dart-to-worker records exist. No observed human approve/cancel/reopen in a running app. |
| (e) Cutover | NO | C7 owner authorization, pinned UI and Chat/voice decision, migration/launcher/rollback, and full-suite triage remain. |

USER-PHYSICAL / NOT VERIFIED: human Approve, Cancel, and reopen on a running Flutter app; client-profile native CLI authentication and execution inside the actual isolated worker; controlled 200+ hard power-loss/write-ordering campaign. The archived native run uses run-scoped auth and programmatic approval, as its own record says. C7 requires separate owner authorization and independent gates. Context Capsule and Task Compiler remain design-only, later undated work; there is no accepted 2E/2F numbering. Chat `/ask` migration and pinned UI release remain C6/C7 decisions.

Research ledger wording must remain scoped: Strata/Paperclip and AG-UI/A2UI are research/deferred; MCP broker and Context Capsule/Task Compiler are design only; model residency is a separate prototype; URI Memory in Core is not a delivered harness capsule. Supervisor recovery and Phase 2D have process/native evidence, without physical power-loss qualification. `PHASE2OPS_REPORT.md` correction record 6 accurately reports the r6 repair, but earlier `IMPLEMENTED / TESTED` headings describe recorded paths, not whole Phase 2, C7, or physical durability. The Phase 1 full suite is not green.

## E. Verdict

The r6 archive and Phase 1 frozen boundary pass direct hash checks. LOG-1R and LOG-2 are repaired in direct probes, and the earlier execution/UI findings have no changed implementation bytes. The only additional logger issue found is a pre-existing low-severity unbounded error-body buffer without a demonstrated production large-body route. VAL-1 remains open for physical qualification. The bounded UI/operations slice is acceptable; Phase 2 implementation, owner qualification, cutover, and freeze are not complete.

## NOT VERIFIED

- Independent pytest or Flutter execution, full-suite failure causes, Phase 2C native rerun, and exhaustive cancellation races.
- Human Flutter interaction, native CLI authentication within the actual client worker profile, controlled physical power loss, and production migration/cutover.
- Original `HTTP_403` cause or recurrence probability, and production reachability of a large error body for LOG-3.

## FINAL VERDICT

**UI/OPERATIONS SLICE ACCEPTED — MORE PHASE 2 WORK REMAINS**
