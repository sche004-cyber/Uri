# M39 — Working Product Baseline: the Office Demonstrator through the real URI interface

- **Scope decision (2026-10-01, additive):** M39 is judged against **R0**, not R1/R1.1. Real-app integration moves to the Harness-first Edge track. See §14, which takes precedence over the R1/R1.1 target below; the status line below is kept as history.
- **Status:** `M39_PLAN_R1_1_DRAFTED_PROVISIONAL` (R1 plus amendment §13). Plan only. Nothing here is implemented, frozen or integrated.
- **Revision history:** R0 at `7363ba5` planned an *isolated* demonstrator (CLI, no production wiring) with the VG-1 benchmark as its main gate. **R1 (this file) supersedes R0** after the User's product completion target (2026-09-28 10:03). R0 is kept in git history and is not rewritten elsewhere. What changed and why is in §12.
- **Date:** 2026-09-28. **Author:** Claude Code, Planning lane. This session did not implement M37/M38.
- **Authority:**
  - User pipeline instruction, 2026-09-28 09:58.
  - User product completion target, 2026-09-28 10:03: reach `URI_WORKING_PRODUCT_BASELINE_REACHED` through the real URI interface, prefer end-to-end capability, and invent no prerequisite architecture.
  - Coordinator relay, 2026-09-28 10:07: proceed with the recommended defaults for the benchmark pass marks and the M37 scope guard; no real Claude Code spend until the User confirms the cap.
- **Governing rulings:** D-A/OD-1…OD-5, VG-1 and LF-1 (`docs/plans/PAPERCLIP_URI_ARCHITECTURE_RECONNAISSANCE.md` §24.1; `docs/plans/URI_EXTERNAL_HARNESS_VIABILITY_GATE.md`). The M31 rule that the Brain never shells out still holds. Frozen S6 is unchanged.

## 0. Acceptance criteria for this plan (defined before drafting)

| ID | Criterion |
|---|---|
| AC-P1 | Every item of the User's product target maps to concrete work and to a named piece of evidence that must be `COMPLETED_WITH_RESULT` before `URI_WORKING_PRODUCT_BASELINE_REACHED` may be reported. |
| AC-P2 | The plan reuses M36/M37/M38 and the existing server/UI as they are. New work is only what a gap in the current code requires, and each gap is cited to a file. |
| AC-P3 | The plan builds on the code at `610c8f8`. Composed APIs exist and their tests pass in this session. |
| AC-P4 | Frozen boundaries are preserved: hash-anchored M33.3 files, S6, the M31 Brain rule, and M36/M37/M38 files. The production-integration governance step (INT-*) is identified. |
| AC-P5 | Gates are objective and predeclared. Real-money steps are separated and gated on the User's spend confirmation. |
| AC-P6 | Defaults are marked as defaults; User decisions are listed. Risks are disclosed with their effect on the baseline claim. |

## 1. Baseline (verified in this session)

| Fact | Evidence |
|---|---|
| HEAD `610c8f8` on `claude/edge-harness-minimum-0oj7fe`. M36 `405db1f`, M37 `5460d64` and M38 `3501f85` are PROVISIONAL; `integration_authorized: false`; `integration_events: []` | `git log`; `docs/governance/URI_STATE.yaml` |
| M37 + M38 + governance tests: 90 passed. Validator VALID. Frozen anchors `ok=True` | run in this session |
| Real interface: FastAPI `uri_core/app/server.py` (`/ask` at line 1631, `/files` at 3096, `/files/{id}/content` at 3162). The Flutter app `uri_ui` posts to `/ask` (`uri_ui/lib/services/http_uri_client.dart:396`, 120 s timeout at :415) and uploads via `/files` (:1642). `/ask/stream` falls back to `/ask` for attachment turns (`server.py:2031-2036`) | source |
| `/ask` already has deterministic, model-free seams ahead of the Brain: approval resumption (M32.1) and lifecycle intent (M33.1 B4) at `server.py:1640-1700`. That is the pattern to reuse | source |
| The UI renders one generated file per response from `response.file` (`http_uri_client.dart:639-654`). The file picker applies no extension filter (`platform_file_picker.dart:16`) | source |
| **Gap:** `FileStore` refuses `.py` (`uri_core/core/file_store.py:55-78`), so a script cannot be attached today | source |
| **Gap:** `FileStore` stores uploads as `<uuid>.<ext>` (`file_store.py:231-232`), so a script's `load_workbook("sales.xlsx")` cannot find the uploaded workbook by name | source |
| **Gap:** the UI has no drag-and-drop (no `desktop_drop`/`DropTarget` in `uri_ui/lib`). The target says "drag/drop **or** select", and selection exists | grep |
| The hash-anchored M33.3 set is S1/S4 files plus `uri_core/capabilities/{wrong_binding,base,registry}.py` (`scripts/m33_3_r_anchors.py:21-47`). `server.py`, `orchestrator.py`, `file_store.py` and `uri_ui` are not anchored | source |
| Existing boundary tests forbid `uri_v1 → uri_core` imports only (`tests/test_m33_3_s1_governance_and_parity.py:47-54`, `tests/test_m33_3_s2_wrong_binding_impact.py:391`). `uri_core → uri_v1` is not forbidden | source |
| Claude Code 2.1.283 is installed in this container; Codex is not; Flutter is not | `claude --version`; `which` |

## 2. Product target → work → evidence

`URI_WORKING_PRODUCT_BASELINE_REACHED` is reported only when every row's evidence is `COMPLETED_WITH_RESULT`.

| # | Target item | Work (section) | Evidence required |
|---|---|---|---|
| T1 | Chat naturally with URI | Existing Brain chat unchanged. The Office seam claims only Office turns (§4.2) | B-UI run shows ordinary chat still answered in the same session; broad suite at baseline |
| T2 | Drag/drop or select files | Existing picker. `.py`/`.xlsm` accepted (§4.3). Drag-and-drop is post-baseline | B-UI: script and workbook attached through the app |
| T3 | Resolve correct task, files, Memory/context | Attachment import, request parser, two-role binding, task discovery (§4.1) | B1 battery; B2 D5/D10/D11 |
| T4 | Qualified local work | M37 Edge first (§4.4 rule 1) | B2 D1 through `/ask` |
| T5 | Harness escalation when required | M38 runner behind consent, in the background (§4.4 rules 2-3, §4.2) | B2 D2 (fake harness); B3 live |
| T6 | Harness results independently verified | M37 verifier through M36 `invoke_verifier`; the view reads only `VERIFIER_RESULT` | B2 D3/D4; B3 |
| T7 | Files returned with correct lineage | Returned as FileStore files, S11 versions and M36 `DERIVATIVE` records; approval-gated write-back for registered folders (§4.5) | B2 D1/D2 download bytes = verified candidate hashes; lineage records checked |
| T8 | Follow-ups continue the task/context | Session-bound Office task state in M36 plus pending-step handling (§4.4 rules 6-7) | B2 D7/D10/D11/D13; B-UI follow-up |
| T9 | Failures surfaced, never false success | Typed failures; seam errors are shown, never passed to the Brain as a fresh request (§4.2) | B2 D3/D4/D6/D8/D9/D14; hard gate `false_success_reported` = 0 |
| T10 | Office Demonstrator end-to-end on real files | All of the above on real `.py` and `.xlsx` in the real app | B-UI on the User's Windows machine |
| T11 | Relevant suite passes apart from documented limitations | B5 | B5 report vs the `610c8f8` baseline |

## 3. What is reused unchanged

| Step | API | File |
|---|---|---|
| Trusted intake with two spans; attachments | `URIIntake.capture`, `capture_attachments` | `uri_v1/memory/uri_adapter/envelope.py:18,26` |
| Retrieval per role | `Retriever.retrieve(MemoryQuery(ref_key=…))` | `uri_v1/memory/retrieval.py:70`; `contracts.py:442` |
| RAR, S1 binding, clarification rounds | `MemoryAdapter.project/register/respond_selection/respond_free_input`; frozen `resolve_rar_deterministic_extended`, `build_clarification`, `BindingService`; `capture_binding` | `envelope.py:120-176`; `uri_v1/turn/rar_deterministic.py:235`; `uri_v1/reference_clarification/builder.py:29`, `binding.py:37`; `links.py:6` |
| Task records, outcomes, verifier, context | `Recorder.*`, `build_context`, `record_derivative` | `uri_v1/memory/recorder.py`, `context_package.py:17`, `links.py:17` |
| Local-first completion | `EdgeService`, `LocalRunner`, `default_registry`, `verifier_entries`, `inspect_script` | `uri_v1/edge/*.py` |
| Acceptance, workspace, write-back | `AcceptanceCriteria`, `Workspace`, `WritebackApproval` | `uri_v1/execution/acceptance.py`, `workspace.py` |
| Harness | `HarnessRunner`, `ClaudeCodeAdapter`, `CodexAdapter`, `PermissionProfile`, `Limits` | `uri_v1/execution/harness/*.py` |
| Server plumbing | per-user `FileStore`, `_resolve_ask_context`, `_current_turn_attachment_references`, seam pattern | `uri_core/app/server.py:1556,1631-1700` |

No M36, M37, M38 or anchored M33.3 file changes (stop condition S-2).

## 4. Design

### 4.1 Backend package `uri_v1/office/` (new; imports `uri_v1.*` only, never `uri_core`)

| File | Responsibility |
|---|---|
| `inbox.py` | Imports current-turn attachments into a per-user Office inbox, `<user data>/office/inbox/<session_id>/<original filename>`, and verifies the hash of each copied file. The inbox is an M36 authorized root, so attachments get real names and M36 `source_id`s, and they enter `capture_attachments`. Two attachments with the same name → `ROLE_AMBIGUOUS` clarification, never an overwrite. The server hands over bytes and filenames; `uri_v1` never imports `FileStore`. |
| `request.py` | Deterministic parser for the Office task family. It returns `None` for anything else, which leaves the turn to the unchanged chain. Signals: (a) current-turn attachments containing a `.py` and an `.xlsx`/`.xlsm`; (b) filename tokens; (c) role phrases ("this/the script", "the spreadsheet/workbook/sheet"); plus an Office verb family (make/get/fix/update … work/run with …, "it fails on", "doesn't work with"). A negated request (M36 `negated`) is not a request. Claiming a turn requires (a), or (b)/(c) together with a verb. The parser returns role spans for `URIIntake.capture`. |
| `binding.py` | Per role: M36 retrieval → projection → RAR → S1 (`CONSEQUENTIAL`). A role binds only when S1 returns `CONFIRMED`; otherwise the turn gets a clarification round. Type check: script is `.py`, workbook is `.xlsx`/`.xlsm`, and they are different sources. Records `open_task`, `observe` and `task_state(bindings=…)` in the session. |
| `acceptance_builder.py` | Acceptance from the original bound files, before any execution. Items: `script_exit_zero`. For each workspace-relative output literal found by `inspect_script`: `output_workbook_exists`, `no_formula_errors`, and `workbook_has_sheets`/`workbook_has_columns` from the original script's sheet-title and header literals. `only_changed` covers the script plus the declared outputs. If the script has no detectable output, the reply says "URI can only check that it runs". |
| `flow.py` | `OfficeFlow.handle_turn(ctx, text, attachments) -> OfficeReply | None`, a state machine persisted in M36 task state plus a small per-user `office/sessions.json` index (session → active task id, pending step, run id). Steps: bind → acceptance → Edge → (escalation proposal → consent → background harness run) → result → return/apply. |
| `worker.py` | Runs `HarnessRunner.run` in a background thread, one per workspace (M37 lock). Records `RUNNING`/`DONE` with the run id in the index. Survives the 120 s UI timeout because `/ask` returns immediately. If the server restarts mid-run, the next turn reports `outcome_unknown` for that run and offers a retry. It never guesses success. |
| `deliver.py` | Two delivery modes. **Attached files:** the verified candidate files are returned as new downloadable files. The seam stores them through `FileStore`; lineage is the S11 versions already written by `record_and_verify` plus an M36 `DERIVATIVE` (`derived_from` = input hashes, `derivative_kind` `office_repair`/`office_output`). The originals in the inbox are untouched. **Registered folder** (the User's own working folder, added in settings): approval-gated `Workspace.write_back`, then an M36 outcome checked by a new registered verifier `uri.verifier.office.writeback.v1`. It confirms the live original equals the verified hash, using post-write hashes as inputs, because `invoke_verifier` re-checks inputs live (`recorder.py:156-157`). |
| `view.py` | Reply text, and a `files` list of returned files. It states the route (done locally / sent to Claude Code / needs your answer), each acceptance item PASS/FAIL, a short URI-computed diff of the script, and the returned files. `VERIFIED` is shown only from the Memory `VERIFIER_RESULT` record, with the sentence "URI checked these items; it did not prove the numbers are right". |
| `bootstrap.py` | Per-process wiring: one `_bootstrap_verifiers` call (M37 entries plus the write-back verifier), user-scoped roots, `default_registry()`, harness probe. |

### 4.2 Server wiring (`uri_core`, not anchored)

- **Office seam in `/ask`**, placed after approval resumption and before the lifecycle seam, following the same pattern: default on, with env flag `URI_OFFICE_SEAM=0` to turn it off, and authenticated users only. If `handle_turn` returns `None`, the chain continues unchanged. If it claimed the turn and then raised, it returns an error envelope stating what failed. It never falls through to the Brain after claiming, because the Brain could then narrate a success that did not happen. Envelope: the existing `{"status", "session_id", "execution", "response"}` shape (`server.py:1602`), with `response.message`, `response.file` (first file, for the current UI) and `response.files` (all).
- **`GET /office/runs/{run_id}`**: status of a background run (`RUNNING`, `DONE` + reply, `OUTCOME_UNKNOWN`), scoped to the user.
- **`POST /office/folders`, `GET /office/folders`**: register or list the User's working folders as M36 authorized roots. This enables write-back to real originals (OD-3 `COPY_IN_COPY_OUT` still applies).
- **`FileStore`**: add `.py` and `.xlsm` to `ALLOWED_EXTENSIONS`. Update `test_file_store.py` expectations to match.
- No change to the orchestrator, Brain, S6, M31, the capability registry or canonical execution.

**Governance: production integration.** `URI_STATE.yaml` has `integration_events: []`, and INT-* events are "explicitly authorized production-integration transitions". This plan reads the User's product target ("through the real URI interface") as the authorization for exactly this integration. The implementation lane registers `INT-001` (Office seam and endpoints; components M36/M37/M38/M39; `status: AUTHORIZED_BY_USER_PRODUCT_TARGET_2026-09-28`) in the same commit that wires the seam, and sets `integration_authorized: true` only for M39. This is an inference from the User's words, not a separate ruling, and it is listed in §10.

### 4.3 UI (`uri_ui`, small)

- Render `response.files` as a list of downloadable attachment chips, falling back to `response.file`.
- While a response carries `execution.office_run_id` with status `RUNNING`, poll `GET /office/runs/{id}` every 3 s (at most 15 minutes) and replace the pending bubble with the result.
- No drag-and-drop before baseline (the target is satisfied by selection); it is the first usability item after it.
- Flutter tests for both changes. Flutter is not installed in this container, so the tests run on the User's machine (B-UI).

### 4.4 Rules the flow enforces

1. **Local first (LF-1).** The Edge decides first; `LOCAL_VERIFIED` never contacts a harness. A local attempt that does not verify escalates with its evidence.
2. **Consent before any harness run** (default). Escalation copies file contents to an external provider and spends the User's usage. The reply says why URI could not do it locally, which files would be sent, and to which harness. The run starts only after a trusted, non-negated yes in the same session. "No" leaves the task open.
3. **Harness choice.** Claude Code by default (the only adapter with a live run). Codex is offered when installed and is labelled unqualified. Restrictive posture; no elevation unless the User grants it for that run (OD-4).
4. **Claims are claims.** Only the M36 `VERIFIER_RESULT` makes a reply say verified. A harness `FAILED`, `PARTIALLY_VERIFIED`, `UNVERIFIABLE` or `outcome_unknown` is reported as such, and no files are returned as the fix.
5. **Write-back** (registered folders only): `VERIFIED` run, explicit approval naming the action, original unchanged since copy-in. Negated wording is not approval.
6. **Follow-ups in the session:** "yes"/"go ahead" (consent), "apply it" (write-back), "what did you change?" (diff from the run record), "try again" (new run on the same bound inputs), "pause". A follow-up that changes the files ("use sales_2024.xlsx instead") goes through M36 `correction` and re-binds.
7. **Across sessions:** the Office index plus M36 paused-task discovery. "continue the sales report" in a new session finds the task through M36 retrieval, re-checks the workspace diff and the originals, and restates the pending step.
8. **After a delivery or write-back the task is complete.** M36 refuses a same-key reference with a new hash (`recorder.py:127`), so a later request on the changed files opens a new task linked by the `derived_from` hashes.

### 4.5 What "returned with correct lineage" means (checked in B2)

For every returned file: the FileStore bytes hash equals the verified candidate hash in the run record, equals the S11 version hash, and equals the M36 `DERIVATIVE.content_sha256`. `derived_from` lists the exact input hashes, and the verifier record's `assessed_outcome_record_id` points to the harness or local claim.

## 5. Qualification

Gate files `fixtures/m39_office/threshold_gate.json` (B1/B2) and `fixtures/m39_office/viability_gate.json` (VG-1) are committed before the first measured run.

- **B1 Request/binding battery** (offline, 2 runs, ≥ 60 cases). Covers attachments, filenames, role phrases, typos, two candidate workbooks, same-stem files, negation, three references, non-Office chat that must return `None`, moved files and stale hashes. Gate: `wrong_binding_acted_on` = 0; `invented_source` = 0; `non_office_turn_claimed` = 0; expected outcome 100 %; deterministic.
- **B2 End-to-end through HTTP** (FastAPI `TestClient` on the real `server.py`, real FileStore/M36/M37/M38, fake harness from `tests/m38_harness_support.py`; 2 runs). Uploads go via `/files`, turns via `/ask`, downloads via `/files/{id}/content`.

| ID | Scenario | Expected |
|---|---|---|
| D1 | Attach `report.py` + `sales.xlsx`; the column differs only by case/separator | local fix, verified; two files returned; lineage checks of §4.5 pass; no harness process |
| D2 | Abbreviated column | escalation proposal → "yes" → background run → poll `DONE` → verified → files returned |
| D3 | Harness claims success but did not fix it | reply says the fix was rejected; no files returned as a fix |
| D4 | Harness strips the script's logic and exits 0 | `FAILED` on output-structure items |
| D5 | Two workbooks attached plus a script | clarification; pick one; continue |
| D6 | Registered folder: original edited between verification and "apply it" | write-back refused; nothing written |
| D7 | "don't apply it" | nothing written |
| D8 | "no" to escalation | no harness process; task open |
| D9 | Harness not installed | honest message; nothing started |
| D10 | "pause"; server restarted; new session: "continue the sales report" | pending step rediscovered; checks re-run; completes once |
| D11 | A new request on the returned script | new task binds the new hash; no `STALE_INPUT` |
| D12 | Script already works | says so; nothing returned |
| D13 | "what did you change?" after D2 | diff from the run record, no harness call |
| D14 | Server restart during a background run | next turn reports `OUTCOME_UNKNOWN`, offers retry |
| D15 | Ordinary chat in the same session between Office turns | handled by the existing chain, unchanged |

Gate: 100 % expected; `false_success_reported` = 0; `original_modified_without_approval` = 0; `harness_started_without_consent` = 0; lineage mismatches = 0; deterministic.

- **B3 Live.** D2 through `/ask` with the real Claude Code CLI, 2 runs, `max_budget_usd` 1.0 per run (about $0.2 expected per run). **Blocked until the User confirms spend.** Pass: the reply matches the URI verifier's verdict; nothing is modified without approval. An honest harness failure is a valid result, but the baseline needs at least one verified live escalation (T5/T6).
- **B-UI Real interface** (the User's Windows machine, via Remote Control or the User). `Launch URI.bat` → sign in → attach real files → run D1 and D2 in the app → download the returned files and run the script → ordinary chat in the same session → follow-up "what did you change?" → new session "continue …" (D10). Flutter tests for §4.3 pass there. Screenshots or a transcript, and the file hashes, are kept as evidence. D2 needs the spend confirmation.
- **B5 Regression.** `tests/`, the broad root suite (`python -m pytest test_*.py`), the governance suite, anchors and `flutter test`, compared against `610c8f8`. Allowed failures: the 15 root failures listed in `docs/plans/URI_BATCH_BROAD_REGRESSION.md`, and the two disclosed scope guards: M36 `test_core_adapter_import_boundaries_and_frozen_scope` and M37 `test_m36_and_frozen_files_unchanged`. The M37 guard is left and disclosed, matching the M36 precedent, per the coordinator relay. New `tests/test_m39_boundaries.py` checks: `uri_v1/office` imports no `uri_core`/network client; paths changed since `610c8f8` are M39 paths plus the listed `uri_core`/`uri_ui` files; M36/M37/M38 and anchored files are unchanged; `require_anchors()` passes.

### 5.1 VG-1 viability benchmark (post-baseline lane; does not gate the baseline)

It is kept from R0 unchanged in design:
- 12 tasks, at least 4 authored outside the implementer session;
- Arms A/B/C × 3 repeats, judged by the verifier and a hidden oracle;
- the thresholds proposed in R0 §5.4, now accepted as the defaults per the coordinator relay;
- outcomes `VG1_PASS`/`VG1_FAIL`/`VG1_INCOMPLETE`;
- $40 cap, pending the User's confirmation.

Arm B now runs through `/ask`. It starts after B2 passes. It measures URI's advantage; it is not a prerequisite for a working product.

## 6. Dependencies and re-qualification

M39 depends on PROVISIONAL M36 `405db1f`, M37 `5460d64` and M38 `3501f85`, and on two private M36 symbols (`_bootstrap_verifiers`, `_runtime_observation`). If a running audit changes any API in §3, or `negated`, `WritebackApproval`, `verify_source`, the verifier or the harness posture, B1, B2 and B5 are re-run on the repaired commit before the baseline is claimed. The baseline may be reported while M36-M38 remain PROVISIONAL (it is a product state, not a freeze), but not while any of their audits has an open blocking finding on an API in §3. The report must say which audits were open.

## 7. Implementation lanes

| Wave | Work | Needs |
|---|---|---|
| W1 | `inbox.py`, `request.py`, `binding.py`, B1 battery | none |
| W2 | `acceptance_builder.py`, `flow.py`, `worker.py`, `deliver.py`, `view.py`, `bootstrap.py`; server seam and endpoints; FileStore extensions; INT-001; B2 | W1 |
| W3 | UI changes (§4.3) and their Flutter tests (written here, run on the User's machine) | W2 envelope shape (can start once §4.2 is fixed) |
| W4 | B5 regression; B3 live (after spend OK); B-UI on Windows (after W3, spend OK for D2) | W2, W3 |
| W5 | Report; `URI_WORKING_PRODUCT_BASELINE_REACHED` if every §2 row holds; fresh Opus audit | W4 |
| after | VG-1 benchmark (§5.1); drag-and-drop; broader phrasing via a Brain tool if B-UI shows the deterministic parser is too narrow | baseline |

## 8. Stop conditions

- S-1: any anchored M33.3, S6 or M31 file would change.
- S-2: any M36, M37 or M38 file would change. Report the need; do not patch.
- S-3: an M36-M38 audit reports a blocking defect in a §3 API. Pause the affected wave.
- S-4: a gate threshold would change after its first measured run.
- S-5: real Claude Code spend without the User's confirmation.
- S-6: the seam would need to change orchestrator/Brain behavior for non-Office turns.

## 9. Risks and limitations

1. **No OS sandbox.** Claude Code's shell can run Python on the machine, and URI's verifier runs the candidate script unsandboxed (M38 limitation 1, M37 limitation 4). On the User's machine the product inherits both. It is disclosed in the baseline report.
2. **Verified is bounded by acceptance.** Output structure comes from the original script, and the diff is shown; wrong numbers with the right structure can still verify. The VG-1 oracle measures this later.
3. **Deterministic phrasing.** Requests outside the parser's family go to normal chat, where the Brain has no Office tool. It can talk about the files but cannot run the Office flow. B-UI checks whether real phrasing is covered; if not, a Brain tool that calls the same flow is the first post-baseline item.
4. **Background runs.** A server restart loses the harness process; the run is reported `OUTCOME_UNKNOWN`, never success.
5. **Windows.** M37/M38 were never run on Windows. B-UI is their first Windows exercise, and Windows-only defects may appear there.
6. **Same-provider audits.** The planner, implementer and auditor are all Claude sessions.

## 10. Decisions

- **Accepted per coordinator relay (10:07):** the VG-1 thresholds from R0 §5.4 as defaults; the M37 scope guard left and disclosed.
- **Waiting on the User:** confirmation of real Claude Code spend (the $40 benchmark cap; B3/B-UI need about $1).
- **Inference to confirm or overrule:** the User's product target is read as authorization for production integration INT-001 (§4.2).
- **Default choices, not rulings:** F-B only (F-A summarizing stays with the Brain path); deterministic Office seam rather than a Brain tool; consent before each task's first harness run; attached files returned as new files, write-back only for registered folders; no drag-and-drop before baseline.

## 11. Self-review (R1)

Problems found in the R1 draft and repaired:
- **`.py` uploads refused.** The draft assumed files could simply be attached. `file_store.py:55-78` has no `.py`, so §4.2 now adds it.
- **Filenames lost on upload.** The draft bound FileStore uploads directly. Stored names are `<uuid>.<ext>` (`file_store.py:231-232`), so scripts could not open the workbook by name. §4.1 adds `inbox.py`.
- **Harness runs exceed the UI timeout.** The draft ran the harness inside `/ask`, but the client times out at 120 s (`http_uri_client.dart:415`). §4.1 adds `worker.py`, and §4.3 adds UI polling.
- **Fall-through after a failure.** The draft fell through to the Brain on any seam error, which could produce a narrated false success. §4.2 now falls through only on `None`.
- **Integration governance.** The draft did not mention INT-*, although `URI_STATE.yaml` requires an explicit INT-* event for production integration. §4.2 now does, and §10 lists it as an inference.
- **UI shows one file.** The UI reads only `response.file`, but D1/D2 return two files. §4.3 adds `files`.

Re-check: AC-P1 §2 (every target row has evidence); AC-P2 §3 and the gaps in §1; AC-P3 §1; AC-P4 §3, §4.2, §5 B5, §8; AC-P5 §5, B3 and S-5; AC-P6 §9 and §10.

**Not verified here, and effect.**
- (a) Flutter behavior and Windows behavior. They are verified only in B-UI, which is required for the baseline.
- (b) Whether `SourceRegistry` keeps `source_id` stable across a content change. D11 checks it; if it does not, only rule 4.4.8's wording changes.
- (c) Whether the `/ask` context exposes a user data dir suitable for the Office inbox. Expected via `user_scoped_path` as other stores use it (`server.py:418,435`); confirmed at W1.

## 12. R0 → R1 change record

| R0 | R1 | Reason |
|---|---|---|
| Isolated CLI, no production wiring | `/ask` seam, endpoints, FileStore and UI changes | User product target: "through the real URI interface" |
| VG-1 benchmark was the main gate | Baseline gated on §2; VG-1 moved to a post-baseline lane | Target lists end-to-end capability and the regression suite, not the benchmark; "do not keep inventing prerequisite architecture" |
| Write-back to originals only | Return files to the user (attachments) plus write-back for registered folders | Target item T7; uploads are copies, not originals |
| Open decisions: thresholds, M37 guard | Both accepted as defaults | Coordinator relay 10:07 |

## 13. Amendment R1.1 (2026-09-28 10:24): User rulings on spend and integration; audit results

Additive. Sections 0-12 stand except where this section says otherwise.

### 13.1 User rulings (Chetan, 2026-09-28 10:24, verbatim in substance)

- **SP-1 Spend.** No separate paid Claude/API spend. All live baseline and comparison runs use the User's existing subscription-authenticated Claude Code. If a specific test genuinely needs separately metered API usage, stop and tell the User why, which capability needs it, and the estimated cost before spending anything.
- **INT-001 approved.** Connect the experimental M38 harness path to the real URI app. Keep it isolated, reversible and provisional. Do not modify frozen components, and do not treat the experimental adapter as production architecture because it works.

### 13.2 Effect on the plan

- **Spend.** Checked in this container: Claude Code authenticates through the host-managed session of the User's account (`CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST` is set; no `ANTHROPIC_API_KEY`; no credentials file). On the User's Windows machine it uses the User's own Claude Code login. No step in this plan needs metered API access.
  - `--max-budget-usd` stays as a per-run usage limiter.
  - `cost_usd` is recorded as Claude Code's own reported estimate, labelled "notional (subscription)", not as billing. The $40 cap in §5.1 becomes a cap on that notional figure.
  - If a run reports that it is using API-key auth, the driver stops before starting (new gate `metered_auth_runs` = 0; the adapter probe's `auth_mode` is checked on every run).
  - Codex, if ever used, must also be subscription-authenticated, or the same stop rule applies.
- **Isolated.** Everything new lives in `uri_v1/office/`. `uri_core` gets exactly one `/ask` seam block, the `/office/*` endpoints, and a flag-gated FileStore extension list. No orchestrator, Brain, S6, M31 or anchored-file change (S-1, S-6 unchanged).
- **Reversible.** One flag, `URI_OFFICE_SEAM`, **default off in the repository**. It is switched on in the User's launch environment.
  - With it off, `/ask` behaves exactly as at `610c8f8`, the `/office/*` endpoints return 404, and `.py`/`.xlsm` uploads are refused as before.
  - New B5 test `test_office_flag_off_is_byte_identical_behavior`: with the flag off, `/ask` responses for the existing server test corpus are unchanged.
  - Removing the flag and `uri_v1/office/` restores the prior app.
- **Provisional.**
  - Replies that used the harness say it was an experimental harness run.
  - `/office/runs` reports `experimental: true`.
  - `URI_STATE.yaml` records `INT-001` with `status: "AUTHORIZED_PROVISIONAL_EXPERIMENTAL"`, which is not a production-architecture adoption. M38 stays `PROVISIONAL` whatever B3/B-UI show.

### 13.3 Audit results received since R1 (from project audit reports; treated as leads, not re-verified by this planning session)

| Audit | Verdict | Findings that hit the M39 path |
|---|---|---|
| M36 repair re-audit (`/mnt/project-files/audits/M36_REPAIR_REAUDIT_REPORT.md`) | REPAIRS_REQUIRED | R-1/R-2: `negated()` misses Unicode apostrophes and "anything but / ignore / stop using X" → wrong `CONFIRMED` binding. R-3: the same gaps in task transitions. Used by `request.py`, `binding.py` and write-back approval |
| M37 internal audit (`M37_INTERNAL_AUDIT_REPORT.md`) | REPAIRS_REQUIRED | F-1/F-2 High (wrong local remap; the path check lets a script read an outside file); F-3 no per-class minimum acceptance; F-5 cell data in escalation; F-7 `write_back` trusts a caller's "VERIFIED" string; F-8 a verification run can tamper with the candidate |
| M38 internal audit (`M38_INTERNAL_AUDIT_REPORT.md`) | REPAIRS_REQUIRED | H-1 the real Claude Code escapes `files/` under the default posture and reads originals; H-2 orphan processes can overwrite originals after `VERIFIED`; H-3 elevations need no grant; H-4 fabricated output passes acceptance. Open User decision: drop `Bash(python *)` from the default posture |

These trigger stop condition **S-3** for anything that runs on real user files. Sequencing:
- **Proceeds now (no dependency on the repairs for building):** W1 code (`inbox.py`, `request.py`, `binding.py`), W2 code, the server seam behind the default-off flag, W3 UI code, and B1/B2 offline tests against the current commits. Their results are recorded as pre-repair evidence and re-run after the repairs.
- **Waits for M36 R-1..R-3 and M37 F-1/F-2/F-7/F-8 repairs plus re-audit:** turning the flag on for the User's real files, the local path in B-UI, and write-back.
- **Waits for M38 H-1..H-4 (and M37 F-3/F-5) repairs plus re-audit, and the User's decision on `Bash(python *)`:** any live harness run on real files (B3 in the real app, B-UI D2). A B3 run in this container on generated fixture files is allowed before then, because nothing of the User's is exposed. Its result is labelled pre-repair.
- `URI_WORKING_PRODUCT_BASELINE_REACHED` cannot be reported while any of these findings is open on a path the baseline uses.
- The acceptance builder's output-structure items (§4.1) address the same failure class as M38 H-4 / M37 F-3 at the Office layer. They do not replace the M37 repair.

### 13.4 Posture decision (2026-09-28 10:26, relayed by the coordinator as the User's decision)

`Bash(python *)` is dropped from the default harness posture. Claude Code does not run scripts; URI's own verifier does all execution. The M38 repair lane implements this in `uri_v1/execution/harness/adapters.py`. M39 builds no workaround and relies on the repaired posture. The §13.3 wait on "the User's decision on `Bash(python *)`" is resolved; the wait on the M38 repairs and re-audit remains.

## 14. Scope decision: R0 + Office capability (2026-10-01)

Additive. This section takes precedence over §§0-13 wherever they set the R1/R1.1 target. Those sections are kept as history.

### 14.1 Decision

User decision (Chetan, 2026-10-01 08:05 UTC): "I explicitly approve Option A: M39 R0 + Office capability, with real-app integration owned by Harness-first." Also: preserve all frozen boundaries; do not introduce R1.1 application features into M39; one thread owns M39 closure; Harness-first consumes the accepted Office capability rather than duplicating it. The options were compared in `/mnt/project-files/decisions/M39_SCOPE_R0_vs_R1_1.md`.

### 14.2 What M39 is

The isolated R0 product, as planned at `7363ba5`:
- `uri_v1/office/`: `request`, `binding`, `acceptance_builder`, `flow`, `writeback`, `view`, `bootstrap`, `__main__`.
- The CLI demonstrator `python -m uri_v1.office --root <folder>`.
- The design decisions recorded since: per-file answers for requests naming two files (2026-09-29 05:16); the minimal M39 entry in the frozen M37 guard (2026-09-29 05:21).

It stays on the frozen line (`5bbf738`, code `bd7c450`), and no M36, M37, M38, anchored or live-app file changes.

### 14.3 Not in M39 (owned by the Harness-first Edge track)

Everything in §4.1-§4.3 that R0 does not have:
- `inbox.py`, `worker.py`, `deliver.py`;
- the `/ask` Office seam, `/office/runs` and `/office/folders` endpoints;
- `.py`/`.xlsm` in `FileStore`, UI file chips and run polling;
- INT-001 registration;
- the B2/B3/B-UI/B5 real-app evidence.

`docs/plans/M39_LIVE_APP_INTEGRATION.md` stays as a design reference for that track and is not an M39 deliverable.

The Office capability that track consumes is `OfficeSession` (`uri_v1/office/flow.py`):
- turn methods `start`, `answer`, `confirm_escalation`, `decline_escalation`, `approve_writeback`, `cancel`, `pause`, `resume`, `status`;
- their typed `StepResult`;
- `view.render`;
- `bootstrap.build_session`.

Real-harness wiring there still needs `acknowledge_unsafe_harness=True` and refuses when `ANTHROPIC_API_KEY` is set.

### 14.4 R0 closing gates

| Gate | Source | State at this amendment |
|---|---|---|
| Q-O1 request/binding battery | R0 §5.1 | Passes in the Linux suite (`tests/test_m39_request.py`) |
| Q-O2 end-to-end scenarios D1-D12 (fake harness, 2 runs) | R0 §5.2 | Passes in the Linux suite (`tests/test_m39_flow.py`) |
| Q-O5 boundaries and regression | R0 §5.5 | Passes on Linux: M39 guard against `5bbf738` with no exemptions, frozen M37 guard with the authorized entry, anchors, governance |
| Independent audit | pipeline rule | ACCEPT at `0d690ea`. Later commits (R5-1, D9 CRLF fix, opt-in live smoke test, these docs) need an independent re-check before closure |
| **Q-O6 Windows** | R0 §5.6 | **NOT RUN.** Full `tests/` suite plus governance and anchors on the User's Windows PC; D1, D6, D10, D12 are inside that suite |
| **Q-O3 live smoke** | R0 §5.3 | **NOT RUN.** One D2 run with the real, subscription-authenticated Claude Code (`tests/test_m39_live_smoke.py`, opt-in `URI_M39_LIVE_SMOKE=1`). An honest harness failure is a valid result |

The two NOT RUN gates are mandatory and can only run on the User's PC (runbook `/mnt/project-files/decisions/M39_R0_PC_RUNBOOK.md`). Until both have run with a result, M39 stays provisionally accepted, not closed and not frozen. Neither is recorded as passed before it has actually run there.

**Not a closing gate:** the Q-O4 VG-1 viability benchmark. This follows R1 §5.1, which moved it after the product baseline. It needs a live campaign of about 60-70 Claude Code runs. The dry-run driver measures 5 of 12 tasks; tasks 05, 06, 08, 09 and 10 need a real harness. It stays a later measurement of URI's advantage.
