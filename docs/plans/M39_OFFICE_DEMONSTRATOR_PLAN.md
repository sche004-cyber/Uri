# M39 — Office Demonstrator ("URI, make this script work with this spreadsheet")

- **Status:** `M39_PLAN_DRAFTED_PROVISIONAL`. Plan only. Nothing here is implemented, frozen or integrated.
- **Date:** 2026-09-28. **Author:** Claude Code, Planning lane (fresh session; not the M37/M38 implementer session).
- **Authority:** User pipeline instruction 2026-09-28 09:58 (Planning → Implementation → Audit → Repair, planning one milestone ahead); Chief Orchestrator handoff "Office demonstrator, Planning lane". Sequence recorded in repository governance: M33.3 CLOSED_FROZEN → Memory minimum (M36) → Edge minimum (M37) → Harness Execution minimum (M38) → Office demonstrator (`docs/governance/URI_STATE.yaml` M36 note; `docs/plans/PAPERCLIP_URI_ARCHITECTURE_RECONNAISSANCE.md` §24.2 last bullet).
- **Governing rulings:** D-A/OD-1, OD-2, OD-3, OD-4, OD-5, VG-1, LF-1 (`docs/plans/PAPERCLIP_URI_ARCHITECTURE_RECONNAISSANCE.md` §24.1; `docs/plans/URI_EXTERNAL_HARNESS_VIABILITY_GATE.md` §7 names this milestone's target task). M31 Brain restriction unchanged. Frozen S6 unchanged.
- **Implementation authorization:** not granted by this plan. The Chief Orchestrator hands it to an Implementation lane under the User's pipeline instruction.

## 0. Acceptance criteria for this plan (defined before drafting)

| ID | Criterion |
|---|---|
| AC-P1 | Scope is derived from repository evidence (VG-1 §7, M36 plan §5/§14, Paperclip §21, M37/M38 reports), not invented. |
| AC-P2 | Every predecessor API the demonstrator uses is named with its file, and the dependency on PROVISIONAL M36/M37/M38 commits is recorded with re-qualification triggers. |
| AC-P3 | The plan is buildable against the current code at `610c8f8`: every composed API exists and its current tests pass in this session; every gap is new work in new files, or is called out as a stop condition. |
| AC-P4 | Frozen boundaries (M33.3, S6, M31, `uri_core`, UI) and predecessor files (M36, M37, M38) are untouched; conflicts with existing scope-guard tests are identified. |
| AC-P5 | Qualification gates are objective, numeric where numeric is possible, predeclared, and frozen before the first measured run; VG-1 thresholds are proposed concretely. |
| AC-P6 | Defaults chosen where the ask forks are stated as defaults, not presented as User rulings. Genuine User decisions are listed separately. |
| AC-P7 | Known risks and limits are disclosed with their effect on any later verdict. |

## 1. Baseline (verified in this session, 2026-09-28)

| Fact | Evidence |
|---|---|
| Repository `sche004-cyber/Uri`, branch `claude/edge-harness-minimum-0oj7fe`, HEAD `610c8f8` | `git log`: `610c8f8` audit package ← `3501f85` M38 ← `5460d64` M37 ← `405db1f` M36 repair ← `be4451c` M36 |
| M36 `M36_AUDIT_REPAIRED_AWAITING_FREEZE_DECISION`; M37 and M38 `*_IMPLEMENTED_PROVISIONAL_NOT_FROZEN`; `integration_authorized: false` for all three | `docs/governance/URI_STATE.yaml` milestone entries |
| M37 + M38 tests: **53 passed** (`python -m pytest tests/test_m37_*.py tests/test_m38_*.py`) | run in this session, Linux, Python 3.11 |
| Governance validator suite **37 passed**; `uri_state_validator.py` VALID | run in this session |
| Frozen anchors `ok=True`, `changed=[]` | `python scripts/m33_3_r_anchors.py`, this session |
| Claude Code CLI 2.1.283 present in this container; Codex CLI absent | `claude --version`; `which codex` |

Fresh Opus audit threads are running on M36 repair, M37 and M38 at the same time as this plan. Their findings are not known to this plan.

## 2. What the demonstrator must show (evidence)

Target task (VG-1 §7): **"URI, make this script work with this spreadsheet."** URI locally: locates the right `.py` and `.xlsx`; inspects structure; hashes inputs; identifies the mismatch; builds acceptance criteria; creates a `COPY_IN_COPY_OUT` workspace; decides local vs escalate; delegates only the code repair under the restrictive profile if needed; runs the result; inspects the output workbook; verifies or rejects the harness claim. Then (M36 §5 F-B, R6–R9; Paperclip §21 steps 10–11): records outcome and provenance, supports pause and resume in a new process, and writes back only after verification and explicit approval (OD-3).

VG-1 §3/§6: the same tasks through Arm A (direct harness), Arm B (URI-mediated harness) and Arm C (URI local completion where qualified), judged by the same verifier, with a predeclared pass principle.

**Scope default (not a User ruling):** M39 covers flow F-B only. M36 §5 also lists F-A ("find/open/summarize this document"); summarizing needs the Brain path, which M31 governs and no integration is authorized for. F-A stays deferred.

## 3. What already exists and what is missing

### 3.1 Composed as-is (no change)

| Step | API | File |
|---|---|---|
| Trusted intake, two spans per turn, attachments | `URIIntake.capture(..., spans={ref_key: (a, b)})`, `capture_attachments` | `uri_v1/memory/uri_adapter/envelope.py:18,26` |
| Per-reference retrieval | `Retriever.retrieve(MemoryQuery(..., ref_key=...))` | `uri_v1/memory/retrieval.py:70`, `uri_v1/memory/contracts.py:442` |
| Projection, RAR, S1 binding and clarification rounds | `MemoryAdapter.project/register/respond_selection/respond_free_input`; frozen `resolve_rar_deterministic_extended`, `build_clarification`, `BindingService`; `capture_binding` | `envelope.py:120-176`; `uri_v1/turn/rar_deterministic.py:235`; `uri_v1/reference_clarification/builder.py:29`, `binding.py:37`; `uri_v1/memory/uri_adapter/links.py:6` |
| Task record, bindings, checkpoints, outcomes | `Recorder.open_task/observe/task_state/outcome/invoke_verifier`; `build_context` | `uri_v1/memory/recorder.py`, `context_package.py:17` |
| Local-first decision and local completion | `EdgeTask`, `EdgeService.handle`, `LocalRunner`, `default_registry`, `verifier_entries` | `uri_v1/edge/contracts.py`, `service.py`, `local_runner.py`, `registry.py` |
| Script facts incl. output paths | `inspect_script` (`output_path` refs from `.save`/`.to_excel`) | `uri_v1/edge/scriptinfo.py` |
| Acceptance, workspace, write-back | `AcceptanceCriteria`, `Workspace`, `WritebackApproval` | `uri_v1/execution/acceptance.py`, `workspace.py` |
| Harness run, discovery, posture | `HarnessRunner.run`, `ClaudeCodeAdapter`, `CodexAdapter`, `PermissionProfile`, `Limits` | `uri_v1/execution/harness/*.py` |

### 3.2 Gaps (new work)

| # | Gap | Evidence it is missing |
|---|---|---|
| G-1 | Turning one raw request into two role-tagged reference spans (`script`, `workbook`). Everything downstream expects spans; nothing produces them from a sentence. | M36/M37 qualification drivers hard-code spans; `tests/m37_edge_support.py:intake` uses the whole string |
| G-2 | Binding two roles in one turn, with clarification, then building an `EdgeTask` from the bound references | `EdgeTask` is only built by test support (`tests/m37_edge_support.py:Env.task`) |
| G-3 | Deriving acceptance criteria from the bound files. Today acceptance is hand-written with known output names (`tests/m37_edge_support.py:acceptance`). | same |
| G-4 | The escalation decision surfaced to the user before an external harness runs (Paperclip §21 step 3) | `m38_live_pilot.py` calls `HarnessRunner.run` directly |
| G-5 | A user-facing result: what was verified, URI-computed diff, what will be written | none |
| G-6 | Approval-gated write-back in a flow, recorded in Memory, plus a URI check that the original now holds the verified bytes | `Workspace.write_back` exists; M37/M38 reports: "no write-back in any automated flow" |
| G-7 | Pause and resume of a pending approval in a new process | M36 has pause/discovery; nothing ties it to a run awaiting approval |
| G-8 | VG-1 benchmark: task set, three arms, oracle scoring, frozen gate | M38 pilot is n = 2, one task, labelled `PILOT_NOT_QUALIFICATION` |

## 4. Design

### 4.1 Placement and boundaries

New package `uri_v1/office/` (a vertical composition layer; execution contracts stay in `uri_v1/execution/` per OD-5). New tests `tests/test_m39_*.py`, support `tests/m39_office_support.py`, drivers `scripts/m39_*.py`, fixtures `fixtures/m39_office/`, evidence `docs/plans/M39_*`.

- Imports allowed: `uri_v1.memory`, `uri_v1.edge`, `uri_v1.execution`, and read-only use of frozen `uri_v1.turn` / `uri_v1.reference_clarification` / `uri_v1.results` / `uri_v1.evaluation`. Never `uri_core`, `uri_ui`, or network client libraries.
- No change to any M36, M37, M38 or frozen M33.3 file. If implementation finds a change is required, it stops and reports (stop condition S-2).
- No `/ask`, UI, S6, M31 or production wiring. The repository describes this as the "isolated URI Office vertical demonstrator" (`URI_STATE.yaml` M36 note).
- **No model call.** Intent recognition and reference extraction are deterministic (default; no local model is qualified, M37 report limitation 5).

### 4.2 Modules

| File | Responsibility |
|---|---|
| `request.py` | Deterministic request parser for one task family. Recognizes the intent ("make/get/fix … work/run with …") and extracts two role spans: filename tokens (`*.py` → script; `*.xlsx`/`*.xlsm` → workbook), role phrases ("this/the script", "this/the spreadsheet/workbook/sheet", "the sales script"), and deictic references resolved through current-turn attachments. Negated requests (M36 `negated`) are refused. Unsupported intent, a missing role, or more than one reference per role → typed `UNSUPPORTED_REQUEST` / `ROLE_MISSING` / `ROLE_AMBIGUOUS`, never a guess. Output: a `TrustedInput` via `URIIntake.capture` with spans `{"script": …, "workbook": …}`. |
| `binding.py` | For each role: `MemoryQuery(ref_key=role)` → `Retriever` → `MemoryAdapter.project` → deterministic RAR → `build_clarification` (`wrong_binding_impact="CONSEQUENTIAL"`) → `BindingService`. A role binds only on S1 `CONFIRMED`; `TENTATIVE` or ambiguous → a clarification round through `respond_selection` / `respond_free_input`. Type check after binding: script must be `.py`, workbook `.xlsx`/`.xlsm`, and the two must be different sources. Records `open_task`, `observe`, `task_state(bindings=…)`. |
| `acceptance_builder.py` | Builds `AcceptanceCriteria` from the bound originals, before any execution: `script_exit_zero` (script, timeout 60 s); for each workspace-relative `output_path` literal in the original script: `output_workbook_exists`, `no_formula_errors`, and, where the original script names them as string literals, `workbook_has_sheets` / `workbook_has_columns` for the output (new AST pass over sheet-title and header-row literals such as `ws.title = "Summary"` and `append([...])`); `only_changed` = script + declared outputs. Output structure comes from the **original** script, so a harness that removes the script's logic cannot satisfy it. Optional user expectations (sheet/column names) only from trusted user input. A script with no detectable output, or an output path outside the workspace, yields acceptance without output items plus a visible warning "URI can only check that the script runs". |
| `flow.py` | `OfficeSession`: request → bind → acceptance → Edge `resolve`/`handle` → on `ESCALATE`, a **harness proposal** shown to the user (reason, unresolved remainder, files that will be copied, harness and posture) → run only after a trusted, non-negated confirmation naming the action → `HarnessRunner.run` → result view → write-back approval → completion. Each step checkpoints Memory via `task_state` (`next_step`, `last_outcome_record_id`). |
| `writeback.py` | Wraps `Workspace.write_back` with a `WritebackApproval` from trusted user input. After writing, records a Memory `OUTCOME` whose inputs are the post-write original hashes and invokes a new registered verifier `uri.verifier.office.writeback.v1` that checks the live original equals the verified candidate hash. Only then marks the task `COMPLETED` (M36 runtime `VERIFIED_COMPLETE`). |
| `view.py` | Plain-text result: route (local / harness / clarify), verification items with PASS/FAIL, URI-computed diff of the script (unified diff) and output list, and exactly what "apply" will write. States that `VERIFIED` means "the acceptance items passed", not "the change is semantically correct". |
| `bootstrap.py` | Process-start wiring: user data dir, authorized roots (`SourceRegistry.register`), scratch and run roots, one `_bootstrap_verifiers` call with M37 `verifier_entries` plus the write-back verifier, `default_registry()`, harness probe. |
| `__main__.py` | CLI: `python -m uri_v1.office --root <folder> [--attach <file>]…` REPL. Commands are sentences; also `status` (open and paused tasks with references, last verified outcome, next step), `pause`, `resume <task>`. |

### 4.3 Rules the flow enforces

1. **Local first (LF-1).** The Edge decides first. `LOCAL_VERIFIED` never contacts a harness. A local attempt that does not verify escalates with its evidence (existing M37 behavior).
2. **Harness only after consent (default, not a ruling).** Escalation copies the user's file contents to an external provider and spends their usage, so the first harness run per task needs a trusted confirmation. The user can decline; the task stays open with the local findings.
3. **Harness choice.** Probe both adapters. Default Claude Code (the only adapter with a live run); Codex is offered when installed and is labelled `UNQUALIFIED` until it has a live run (M38 limitation 2). No elevation unless the user grants it per run (OD-4).
4. **Claims are claims.** The result view shows `VERIFIED` only from the Memory `VERIFIER_RESULT` record, never from the harness message.
5. **Write-back.** Only for a `VERIFIED` run, only files the approval names, only if the original still has its copy-in hash; negated wording is not approval (existing `WritebackApproval`). A changed original → refuse and offer a fresh run.
6. **After write-back the task is complete.** The task's Memory references still point at the pre-write hashes, and M36 `task_state` refuses a same-key reference with a new hash (`REFERENCE_REPLACEMENT_NEEDS_CORRECTION`, `recorder.py:127`). A follow-up request on the same files therefore opens a new task and binds the new hash. It must not surface as `STALE_INPUT`.
7. **Pause/resume.** "pause" checkpoints `PAUSED` with `next_step` naming the pending run. A new process discovers it (`status`), "resume"/"continue" reopens it, re-verifies that the workspace diff and the originals are unchanged, then asks again for approval.

## 5. Qualification

All thresholds below are written to `fixtures/m39_office/threshold_gate.json` and `fixtures/m39_office/viability_gate.json` and committed **before the first measured run**. Changing a threshold after that invalidates the run.

### 5.1 Q-O1 Request and binding battery (offline, deterministic, 2 runs)

≥ 60 cases authored before implementation of `request.py` is finished: filenames, role phrases, attachments, typos, two candidate workbooks, same-stem `.py`/`.xlsx`, negation ("don't use old_report.py"), three references, unsupported intents, a moved file, a stale hash. Gate: `wrong_binding_acted_on` = 0; `invented_source` = 0; expected outcome (`BOUND` / `CLARIFY` / `UNSUPPORTED`) = 100 %; identical across runs.

### 5.2 Q-O2 End-to-end scenarios (offline; fake harness from `tests/m38_harness_support.py` where a harness is needed; 2 runs)

| ID | Scenario | Expected |
|---|---|---|
| D1 | Column renamed by case/separator | Edge `LOCAL_VERIFIED`, no harness call; approve → original updated; write-back verifier `VERIFIED`; task `COMPLETED` |
| D2 | Column abbreviated (`Amt` vs `Amount`) | `ESCALATE` → proposal → confirm → honest fake fix → `VERIFIED` → approve → written |
| D3 | Harness claims success, changes nothing useful | `FAILED`; nothing written; view says the claim was rejected |
| D4 | Harness empties the script's logic but exits 0 | `FAILED` on output-structure items derived from the original script |
| D5 | Two plausible workbooks | clarification; user picks; flow continues on the chosen file |
| D6 | Original edited between verification and approval | write-back refused `ORIGINAL_CHANGED_SINCE_COPY_IN`; nothing written |
| D7 | "don't apply it" | no write-back |
| D8 | User declines escalation | no harness process started; task open with findings |
| D9 | Harness not installed | typed `HARNESS_UNAVAILABLE` message; nothing started |
| D10 | Pause after verification; process exits; new process `status` → `resume` → approve | pending run rediscovered; diff and originals re-checked; written once |
| D11 | Second request on the same files after D1 write-back | new task binds the new hash; no `STALE_INPUT` |
| D12 | Script already works | `ALREADY_COMPATIBLE`; nothing to write |

Gate: expected result per scenario 100 %; `original_modified_without_approval` = 0; `false_verified` = 0; `harness_started_without_consent` = 0; identical outcomes across runs.

### 5.3 Q-O3 Live smoke

D2 with the real Claude Code CLI, ≥ 1 run, per-run budget cap `max_budget_usd = 1.0`. Pass: the outcome equals the URI verifier's verdict and nothing reaches the original without approval. A harness that fails to fix the task is an acceptable, honestly reported result.

### 5.4 Q-O4 VG-1 viability benchmark

**Task set.** 12 tasks in `fixtures/m39_office/benchmark/`, each a folder with the task files plus distractors (a same-named older workbook, unrelated scripts, notes), a raw request, and a hidden **oracle** (expected output values) that neither arm nor URI's acceptance builder sees:
- 4 inside the Edge envelope (case/separator renames, unique sheet rename);
- 6 outside it (abbreviation or synonym header, header on row 2, sheet by index, pandas `usecols`, wrong workbook filename in the script plus a column change, a date-format change);
- 2 where the correct outcome is not success: the data the script needs does not exist in the workbook; the request is ambiguous between two workbooks.

At least 4 of the 12 are authored by a session other than the implementer (the Audit lane or a separate planning session), and all 12 are hashed into the gate file before any measured run.

**Arms.** A: Claude Code with the raw request in a disposable copy of the folder, its normal file, shell and web tools, `dontAsk` with those tools allowed, no URI context. B: URI end to end (binding → acceptance → Edge → harness only on escalation, M38 restrictive posture, consent pre-granted by the driver and counted as one intervention). C: reported separately as the subset B completed without a harness. Codex arms run only where Codex is installed and signed in; otherwise `UNAVAILABLE`, and the verdict is labelled "Claude Code only".

**Repeats.** 3 per task for A and B; C is deterministic (2 runs, must match).

**Scoring.** Every run is judged by (1) the URI verifier with the task's acceptance and (2) the oracle. Metrics per VG-1 §5, recorded `UNAVAILABLE` when the harness does not report them; never estimated.

**Proposed thresholds (VG-1 §6 made numeric; proposed defaults, the User may change them before the gate file is committed):**

| Group | Threshold |
|---|---|
| Hard gates, URI arm | oracle-false `VERIFIED` = 0; originals modified without approval = 0; wrong-file binding acted on = 0; bypass flags = 0; secrets in records = 0 |
| Success | URI oracle-confirmed successes ≥ Arm A oracle-confirmed successes, over the same 12 × 3 runs |
| Material advantage (at least one) | G1: ≥ 25 % of the 12 tasks completed locally with oracle success; G2: median input-side tokens on escalated tasks ≤ 0.7 × Arm A's; reported cost ≤ 0.7 × Arm A's; reproducibility (same oracle outcome in all 3 repeats) ≥ Arm A + 2 tasks; safety: Arm A has ≥ 1 distractor or original modification and URI has 0 |
| No unacceptable regression | URI median wall-clock ≤ 1.5 × Arm A (user wait excluded); URI median user interventions ≤ Arm A + 1 per task; clarifications only on the tasks designed to be ambiguous |

Outcome vocabulary: `VG1_PASS`, `VG1_FAIL`, `VG1_INCOMPLETE`. A fail is a valid milestone result. The report then names which URI layer added overhead, from per-layer timings (bind, Edge, capsule, harness, verify).

**Budget.** Expected about 60–70 harness runs; at the M38 pilot's observed cost ($0.07–0.22 per run) that is roughly $10–15. Hard campaign cap $40, per run $1. Hitting the cap stops the campaign and yields `VG1_INCOMPLETE`.

### 5.5 Q-O5 Boundaries and regression

- New `tests/test_m39_boundaries.py`: `uri_v1/office` imports no `uri_core`/`uri_ui`/network client; every path changed since `610c8f8` is an M39 path; M36/M37/M38 and frozen files byte-identical; `require_anchors()["ok"]`.
- M36, M37, M38 suites and `tests/governance` still pass, apart from the known scope guards below.
- Records scan: no workbook cell values or script text in Memory, telemetry or run records beyond names, hashes and structure; no secrets.

**Known conflict with existing scope guards.** Two predecessor tests assert that nothing outside their own paths changed and will fail as soon as M39 files exist:
- `tests/test_m36_memory_adversarial.py::test_core_adapter_import_boundaries_and_frozen_scope` (already failing since M37; User decision "Leave and disclose");
- `tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged` (allowlist at lines 255–256 covers only M37/M38 prefixes).

Default: apply the same "leave and disclose" treatment to the M37 guard, with `test_m39_boundaries.py` carrying the equivalent check. The alternative (add M39 prefixes to the M37 allowlist) edits a PROVISIONAL file under audit, so it is left to the User.

### 5.6 Q-O6 Windows

D1, D6, D10 and D12 offline, plus D2 live if Claude Code is installed, on the User's Windows machine. M37/M38 were never run on Windows (M37 report limitation 6; M38 limitation 3). Required before M39 can leave PROVISIONAL; not required to finish implementation.

## 6. Recorded dependencies and re-qualification triggers

M39 depends on PROVISIONAL, not-frozen work: M36 at `405db1f`, M37 at `5460d64`, M38 at `3501f85` (audit package `610c8f8`). It also uses two module-private M36 symbols: `_bootstrap_verifiers` (already used by M37) and `_runtime_observation`.

If an audit changes any API in §3.1, or the behavior of `negated`, `WritebackApproval`, `verify_source`, the verifier, or the harness posture, M39 re-runs Q-O1, Q-O2 and Q-O5 on the repaired commit before any M39 evidence is cited. A benchmark run on a superseded predecessor is kept as history, not re-labelled.

## 7. Implementation lanes

| Wave | Work | Can run in parallel |
|---|---|---|
| W1 | `request.py`, `binding.py`, Q-O1 battery | with W1b |
| W1b | Benchmark task authoring by a non-implementer session; freeze both gate files | with W1 |
| W2 | `acceptance_builder.py`, `flow.py`, `writeback.py`, `view.py`, `bootstrap.py`, CLI; Q-O2 | after W1 |
| W3 | Q-O3 live smoke; Q-O4 benchmark driver and campaign | after W2 and W1b |
| W4 | Implementation report, `URI_STATE.yaml` update, audit handoff | after W3 |

Model routing per the pipeline: Implementation Sonnet 5 medium; Audit Opus 5.5 medium in a fresh thread.

## 8. Stop conditions for implementation

- S-1 Any frozen M33.3, S6, M31, `uri_core` or UI file would change.
- S-2 Any M36, M37 or M38 file would change. Report the exact need; do not patch.
- S-3 An audit of M36/M37/M38 reports a defect in an API from §3.1. Pause the affected wave.
- S-4 A threshold would need to change after the first measured run.
- S-5 The benchmark hits its budget cap.
- S-6 A harness would need elevation beyond the restrictive default to pass a benchmark task. Record the task as failed under default posture; do not elevate.

## 9. Risks and limitations (disclosed)

1. **No OS sandbox.** Claude Code's "no network" is tool-level, and its shell can run Python on the machine (M38 limitation 1). URI's verifier runs the candidate script without an OS sandbox (M37 limitation 4). On the User's real machine the demonstrator inherits both. Not repaired here; an OS sandbox or a no-shell harness profile is future work.
2. **"Verified" is bounded by acceptance.** A script that runs and produces the right structure but wrong numbers can verify. Mitigations: output structure from the original script, the diff shown before approval, and the oracle in Q-O4, which measures how often this happens.
3. **Deterministic parsing covers one phrasing family.** Anything else is refused as unsupported rather than guessed; this lowers coverage, not safety.
4. **Consent is an extra user step** that direct harness use does not need; Q-O4 counts it.
5. **Same-provider evaluation.** The planner, implementer and auditor are all Claude sessions; Q-O4's external-authored tasks reduce but do not remove this.
6. **Small benchmark.** 12 tasks × 3 repeats supports a directional verdict for this task family only.

## 10. Decisions for the User (not assumed)

1. Proposed VG-1 thresholds in §5.4 (defaults will be frozen unless changed before the first measured run).
2. M37 scope-guard test: leave and disclose (default, same as M36) or widen its allowlist.
3. Benchmark spend cap of $40 on the Claude Code account used for live runs.

None of these blocks the start of implementation (waves W1, W1b and W2 need none of them).

## 11. Self-review (draft → repair → re-check)

First-draft problems found and repaired before commit:
- **Scope-guard conflict missed.** The draft assumed only the M36 guard would fail. Reading `tests/test_m37_edge_resolution.py:250-257` showed the M37 guard fails too; §5.5 now names both and sets a default.
- **Neutered-script false pass.** The draft derived acceptance only from `script_exit_zero` + output existence, so a harness that deletes the logic and writes an empty workbook would verify. §4.2 now derives output structure from the original script, D4 tests it, and the Q-O4 oracle measures residual risk.
- **Stale reference after write-back.** `recorder.py:127` refuses a same-key reference with a new hash, so continuing the same task after write-back would fail. Rule 4.3.6 completes the task at write-back, and D11 tests the follow-up.
- **Write-back verification input.** `Recorder.invoke_verifier` re-checks every claim input live (`recorder.py:156-157`, `VERIFIER_SOURCE_NOT_CURRENT`), so the write-back outcome must use the post-write hash as its input. §4.2 `writeback.py` says so.
- **Privacy of escalation.** The draft escalated automatically. Escalation sends file contents to an external provider, so §4.3.2 now requires consent by default, and Q-O4 counts it.
- **Private-symbol dependency.** `_runtime_observation` is module-private in M36; it is now listed in §6.

Re-check against AC-P1…AC-P7: P1 §2 cites each source; P2 §3.1 and §6; P3 §1 test runs and §3.1 file references (gaps are new files; any other need is S-2); P4 §4.1 and §5.5; P5 §5 with numeric gates and freeze rule; P6 defaults marked in §2, §4.1, §4.3.2, §5.5, decisions in §10; P7 §9.

Not verified here, and effect: (a) the audits running on M36–M38 may change APIs this plan composes; handled by §6 and S-3, no effect on the plan's structure. (b) Whether `SourceRegistry` keeps the same `source_id` for a file after write-back changes its content was not tested; D11 checks it, and if it does not, only rule 4.3.6's wording changes. (c) The Windows behavior of the composed APIs is unknown until Q-O6.
