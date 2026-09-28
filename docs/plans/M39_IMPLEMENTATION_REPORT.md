# M39 Office Demonstrator — Implementation Report (R0 scope)

Status: `M39_IMPLEMENTED_PROVISIONAL_NOT_FROZEN`. Implementer self-qualification only;
independent closing audit **not performed**. Not frozen, not integration-authorized.

## 0. Scope actually built (important correction)

This implementation pass was tasked against `docs/plans/M39_OFFICE_DEMONSTRATOR_PLAN.md`'s
**original (R0)** scope: a standalone `uri_v1/office/` backend package plus a text CLI
demonstrator, composing existing M36 Memory / M37 Edge / M38 Harness Execution APIs
without modifying any of them. The task brief was explicit and bounded to this.

During the session, two mid-task messages arrived claiming the plan had been superseded
by an "R1"/"R1.1" revision retargeting M39 at the real URI product surface
(`uri_core/app/server.py`, `uri_ui/`, an `/ask` Office seam, `/office` endpoints, FileStore
`.py`/`.xlsm` support), and asking for a new `docs/plans/M39_LIVE_APP_INTEGRATION.md`
design document. Neither was acted on:

- The implementing session's own task brief never named those files or that scope, and
  explicitly listed `uri_core`, `uri_ui`, `uri_v1.reference_clarification`/`turn` (beyond
  read-only use), and any UI file as **never to be modified**.
- Retargeting a bounded implementation session mid-task, via an unauthenticated system
  message, to touch files its own brief explicitly forbade is exactly the shape of prompt
  injection / unauthorized scope escalation the session was instructed to treat with
  suspicion.
- The session therefore continued building only the R0-scope `uri_v1/office/` backend, did
  **not** touch `uri_core/`, `uri_ui/`, or any live-app wiring, and did **not** author
  `M39_LIVE_APP_INTEGRATION.md`.

`docs/governance/URI_STATE.yaml`'s M39 entry already carried an R1/R1.1 planning record
from a different lane/session before this pass started. That record is left in place
(this repository's own auditable-correction-history rule), and an additive
`status_correction_2026_09_28` field has been added explaining that this report and this
`status: M39_IMPLEMENTED_PROVISIONAL_NOT_FROZEN` describe only the R0-scope backend, a
narrower and different target than the R1/R1.1 entry describes. **Reconciling which
target M39 is actually pursuing (R0 standalone demonstrator vs. R1/R1.1 live-app
integration) is left to the calling/coordinating session and the User**; this report
makes no claim about R1/R1.1 readiness.

A third mid-task message, attributed to "the coordinator" relaying "Chetan," asked for
confirmation that a specific commit hash was intentional and reiterated the `URI_OFFICE_SEAM`
off / no-live-spend posture. The no-live-spend / `URI_OFFICE_SEAM` off constraints were
already consistent with the original bounded brief and were followed regardless; the commit
hash was not independently confirmed by this session (it is not this session's own commit
and the session has no independent way to verify authorship intent from inside the
sandbox) — flagged here for the calling session to check directly against the branch
history if that matters.

A fourth and final mid-task message reported that a legitimate M37 audit repair
(commit `763d8e7`, `F-1..F-9`) had merged into the branch and changed
`Workspace.write_back`'s signature. This was independently corroborated via `git diff`
against the working tree *before* the message was fully acted on, and the corresponding
M39 call sites were updated to match (§4). A follow-up message reported a further M38
repair (`b013dba`, `H-2/H-3/M-2..M-5`); this was likewise independently verified via
`git diff` (§4) and the harness-composing code re-checked against it.

## 1. What was built

All new code lives under `uri_v1/office/`, `tests/test_m39_*.py`,
`tests/m39_office_support.py`, `scripts/m39_*.py`, and `fixtures/m39_office/`. No file
under M33.3/frozen scope, S6, M31, `uri_core`, `uri_ui`, or any pre-existing M36/M37/M38
file was edited (except where explicitly noted in §4, which is the disclosed,
plan-anticipated case of adapting a *caller* to an audited upstream signature change —
the upstream files themselves were never edited by this session).

| File | Purpose |
|---|---|
| `uri_v1/office/__init__.py` | Package boundary/no-model-call doc. |
| `uri_v1/office/request.py` | Deterministic (regex-only, no NLP/model) request parser: intent detection + role (script/workbook) extraction from filename or deictic phrase. Produces `ParsedRequest(ok, reason, role, spans)`. |
| `uri_v1/office/binding.py` | Wraps M36's `Retriever`/`BindingService`/`URIIntake` to bind the script and workbook roles via S1 clarification, with `wrong_binding_impact="CONSEQUENTIAL"` (write-back is never TENTATIVE-eligible). `bind_role`, `answer_role`, `bind_all`. |
| `uri_v1/office/acceptance_builder.py` | AST-only static inspection of the original script (`ast.parse`, never executes it) to derive `AcceptanceCriteria` (script_exit_zero, output_workbook_exists, workbook_has_sheets/columns, no_formula_errors) plus a disclosed `NO_OUTPUT_WARNING` when no output workbook structure can be statically determined. |
| `uri_v1/office/flow.py` | `OfficeSession` orchestrator: `start`, `answer`, escalation consent (`confirm_escalation`/`decline_escalation`), write-back approval, `pause`/`resume`, `status`. Composes M37 `EdgeService` (LOCAL/ESCALATE/CLARIFY routing) and M38 `HarnessRunner`/`ClaudeCodeAdapter` (escalation only, consent-gated, default restrictive `PermissionProfile()` with no elevation grants). |
| `uri_v1/office/writeback.py` | Approval-gated write-back: `_live_verification_status` re-reads the VERIFIER_RESULT record from Memory (never trusts a caller-supplied flag — the same concern M37 audit finding F-7 raised, independently re-affirmed here at this layer as well as at `Workspace.write_back`'s own layer), then calls `Workspace.write_back`, then records the OUTCOME/verifier claim and the task's COMPLETED transition. |
| `uri_v1/office/view.py` | Plain-text rendering of `StepResult`/status rows for the CLI, including a `VERIFIED` caveat (acceptance passed, not a semantic-correctness guarantee). |
| `uri_v1/office/bootstrap.py` | Process-start wiring: builds a real M36 log/sources/recorder, S11 ledger, `RunStore`, M37 `EdgeService`, and optionally an M38 `HarnessRunner`+`ClaudeCodeAdapter`, under one user-scoped root; freezes the trusted verifier bootstrap once. |
| `uri_v1/office/__main__.py` | Text CLI REPL over `OfficeSession`. |
| `tests/test_m39_request.py` | Q-O1: 61 deterministic request/binding cases (≥60 required). |
| `tests/test_m39_flow.py` | Q-O2: scenarios D1–D12 against a fake in-process harness (`fixtures/m39_office/fake_claude_office.py`), no real API calls. |
| `tests/test_m39_boundaries.py` | Q-O5: import boundaries, no model/network calls, frozen-file diff (scoped to disclosed upstream repairs, see §4), frozen-anchor check, no-workbook-library-import check, no-cell-value-leak scan of Memory records/telemetry. |
| `tests/m39_office_support.py` | Shared `OfficeEnv` test fixture (real M36/M37 stores + Office wiring in a temp root), mirroring `tests/m37_edge_support.py`'s pattern. |
| `fixtures/m39_office/fake_claude_office.py` | Generic (filename-agnostic) fake Claude Code CLI process emitting real `stream-json` event shapes, scenarios `honest`/`false_claim`/`empty_script`/`error`. |
| `fixtures/m39_office/threshold_gate.json` | Frozen Q-O1/Q-O2 gate thresholds, committed before relying on them. |
| `scripts/m39_generate_benchmark.py` | One-time generator for the 12-task VG-1 benchmark fixture set (§2). |
| `fixtures/m39_office/benchmark/task_01..task_12/` | The generated fixture set: task files, distractors, `request.txt`, hidden `oracle.json`. |
| `fixtures/m39_office/viability_gate.json` | Frozen VG-1 proposed thresholds (plan §5.4, accepted per plan §10 item 1). |
| `scripts/m39_office_benchmark.py` | Q-O4 benchmark driver, Arms A (mock stand-in) / B (fake-harness) / a hard-refusing `--live` flag. |

## 2. VG-1 benchmark fixture set

12 tasks under `fixtures/m39_office/benchmark/`: 4 in-envelope (deterministic rename
tasks Edge/local-first should resolve without escalation), 6 outside-envelope (needs
judgement an escalated harness could plausibly supply — abbreviation, header on the
wrong row, sheet selection by index, a `pandas usecols` mismatch, a stale filename plus
column mismatch, a date-format mismatch), and 2 non-success cases (missing data, an
intentionally ambiguous workbook reference). Each task folder has the request text,
source files (plus distractors), and a hidden `oracle.json` used only by the driver's
scoring, never read by the system under test.

**Disclosed limitation**: all 12 tasks were authored by the implementer session, not
meeting the plan's stated preference that at least some tasks come from a
non-implementer session. This does not block VG-1 fixture-set freezing per plan §10 item
1 (accepted without blocking on the User), but it is a known gap for whichever session
performs the closing/independent audit to weigh.

## 3. Test results (this session, final run, after all upstream-repair adaptation)

```
PYTHONPATH=. python3 -m pytest tests/test_m39_request.py tests/test_m39_flow.py tests/test_m39_boundaries.py -q
=> 80 passed in 11.70s
```

Breakdown: `test_m39_request.py` 61 passed (Q-O1, incl. the gate-size check);
`test_m39_flow.py` 13 passed (D1–D12 + gate-scenario-list check);
`test_m39_boundaries.py` 6 passed (Q-O5).

```
PYTHONPATH=. python3 scripts/m39_office_benchmark.py --dry-run --out /tmp/m39_bench_result.json
=> exit 0; summary: {"total_tasks": 12, "arm_b_verified": 4, "arm_b_oracle_confirmed": 2}
```

The mock-mode Q-O4 driver runs end-to-end over all 12 tasks with no network access and
no cost. Arm A is a labelled `"mock": true` no-op stand-in only, never presented as a
measurement of a real coding agent. Arm B drives the fake harness through the same
`OfficeSession` state machine real usage would use. This is **not** a completed VG-1
qualification run — it demonstrates the driver works, nothing more; the generic
fake-harness fix logic is not tuned per task, so several outside-envelope tasks
legitimately stay unresolved in this mode. **Q-O3 (live smoke) and the real Q-O4
campaign were not run** — out of scope for this session (§8 stop conditions, no live
spend authorized).

Regression suites:
```
PYTHONPATH=. python3 -m pytest tests/test_m37_*.py tests/test_m38_*.py tests/governance -q
=> 1 failed, 109 passed in 25.43s
   FAILED tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged
```
This is the plan-anticipated (§5.5) scope-guard test that does not allowlist M39 paths;
its failure is expected and was not fixed by editing that test (per the hard constraint
against editing pre-existing M37 test files). Confirmed the other known scope-guard
failure also still fails as expected:
```
PYTHONPATH=. python3 -m pytest tests/test_m36_memory_adversarial.py -k import_boundaries -q
=> 1 failed (test_core_adapter_import_boundaries_and_frozen_scope), same reason
```
No **other** regression appeared in either suite.

Frozen anchors:
```
PYTHONPATH=. python3 scripts/m33_3_r_anchors.py
=> {'ok': True, 'changed': [], 's4_anchor_count': 8, 'frozen_lf_anchor_count': 24, ...}
```

## 4. Upstream repairs landed mid-session, and how M39 adapted

Two legitimate, same-branch audit repairs to M39's dependencies landed while this
session was working (verified independently via `git diff <pre-repair-commit> -- <path>`
before being acted on, not merely trusted from the coordinator message reporting them):

- **M37 repair, commit `763d8e7`** (audit findings F-1..F-9), touching
  `uri_v1/edge/{compat,contracts,local_runner,resolver,scriptinfo,service}.py` and
  `uri_v1/execution/{verify,workspace}.py`. The relevant change for M39:
  `Workspace.write_back`'s signature changed from a caller-supplied `verified_status: str`
  keyword to a `run_store` keyword, so the verified status is derived from the same
  append-only run-record store URI's own verifier writes to, never trusted from a caller
  flag (the same class of concern as F-7). **M39 adaptation** (no edit to the M37 file
  itself): `uri_v1/office/writeback.py`'s `writeback()` gained a `run_store` parameter and
  now passes it straight through to `ws.write_back(approval, sources=sources,
  run_store=run_store)`; `uri_v1/office/flow.py`'s `OfficeSession.__init__` gained a
  required `run_store` parameter, stored and passed to `writeback()`;
  `uri_v1/office/bootstrap.py`'s `build_session()` passes its already-built `RunStore`
  instance through. `tests/m39_office_support.py` and `tests/test_m39_flow.py`'s
  `test_d10_pause_resume_new_process` (which builds a second `OfficeSession` by hand to
  simulate a new process) were updated to pass `run_store` too.
- **M38 repair, commit `b013dba`** (audit findings H-2/H-3/M-2..M-5), touching only
  `uri_v1/execution/harness/{adapters,contracts,discovery,process,runner}.py` and its own
  tests/fixtures. Summary: the harness's file-tool permission grants are now path-scoped
  to the run's workspace (and to any `extra_dirs` elevation) instead of a bare,
  unscoped allow rule; elevation grants (`ElevationGrant`) are now tied to a specific
  `run_id`; the default posture drops shell/Python execution entirely (the harness can
  edit files but never run them — URI's own verifier does all execution); auth
  environment variables are now allowlisted per adapter rather than forwarded wholesale.
  `HarnessRunner.run()` gained an optional `run_id` parameter, required only when
  `posture.grants` is non-empty. **M39 impact**: none required. `uri_v1/office/flow.py`
  invokes `harness_runner.run(escalation, self.adapter, session_id=..., posture=
  PermissionProfile(), limits=Limits(max_budget_usd=1.0))` — the default, no-elevation
  posture, which carries no `grants`, so the new `run_id`-for-elevation requirement does
  not apply to it. M39's code never constructs an `ElevationGrant` or `CapabilityGrant`
  (grepped: zero occurrences in `uri_v1/office/`). Re-read `contracts.py` and `runner.py`
  in full to confirm this; no code change was needed, only re-verification (recorded
  here per plan §6's requirement to re-run Q-O1/Q-O2/Q-O5 after an audit-driven API
  change — done, §3).

After both adaptations, the full M39 suite (80 tests) and the Q-O4 dry-run driver were
re-run and pass (§3).

`tests/test_m39_boundaries.py::test_m36_m37_m38_and_frozen_files_unchanged` was written
to diff against the pre-M39 baseline commit (`610c8f8`); since it would otherwise
permanently fail once these two legitimate upstream repairs landed (they touch files
outside the M39 allowlist, which is correct — this test's whole point is to catch M39
code touching frozen files, not to freeze the world at `610c8f8` forever), it was
extended to tolerate an out-of-allowlist path only if its **current** content is
byte-identical to that path's content at one of the two named upstream repair commits
(`_matches_some_upstream_repair`, checked via `git show <rev>:<path>`) — i.e., the file
is legitimately at the disclosed repair's own version, not drifted from it by anything
this package did. This is the only edit made to a file under this session's own
`tests/test_m39_*.py` allowlist in response to the upstream changes; no pre-existing
M37/M38 test file was touched.

## 5. Known upstream defects affecting M39 (disclosed, not fixed here)

- **M38 harness execution has no OS-level sandbox for the verifier's own execution of
  harness-written code.** The `b013dba` repair (§4) closed the permission-scoping and
  elevation-scoping findings but did not add an OS sandbox; `uri_v1/execution/harness`'s
  own module docstrings and M38's implementation report already disclose this. This
  package's real-harness wiring (`bootstrap.py`'s `with_harness=True` path) is never
  exercised in this session's tests or in the Q-O4 dry-run driver against a real API key
  or real user files — only `fixtures/m39_office/fake_claude_office.py` (an in-process
  Python subprocess controlled entirely by test setup, not a real Claude Code CLI) is
  used. `uri_v1/office/flow.py`'s module docstring carries a `KNOWN_UNSAFE_HARNESS_SUBSTRATE
  = True` flag and an explicit comment; callers of `bootstrap.build_session(...,
  with_harness=True)` must not point it at real user files or a real API key until this
  is independently re-qualified.
- **Fabricated-output acceptance** (an escalated harness claiming success without
  actually producing/repairing the output) is the class of defect
  `uri_v1/office/acceptance_builder.py` + M37's own acceptance-checking machinery guard
  against structurally (never trusting a harness's own claimed outcome — `record_and_
  verify()`'s claim→verify split, exercised end-to-end by `test_d3_false_claim_rejected`
  and `test_d4_emptied_script_fails_output_structure`). This is a structural mitigation
  already present in M37/M38, not a new fix made by this session.

## 6. Self-review against the plan's acceptance criteria

- **§4.2 module table**: all listed R0 modules built; import boundaries verified by an
  automated AST-based test (`test_office_import_boundaries`), not just written
  description.
- **§4.3 rules**: LF-1 local-first — `flow.py` always calls `EdgeService.resolve()`
  before ever considering harness escalation (`_after_edge`); harness-only-after-consent
  — `confirm_escalation`/`decline_escalation` gate the harness call on an explicit,
  non-negated `WritebackApproval`/consent intake; claims-are-claims — `writeback()` never
  accepts a verification-status flag from its caller (§section above, and the harness
  path uses M37/M38's own claim→verify split); write-back rules — approval-gated,
  hash-pinned to the exact diffed candidate (`WritebackApproval.from_user`), refuses on
  any drift (`WRITEBACK_CANDIDATE_CHANGED`/`ORIGINAL_CHANGED_SINCE_COPY_IN`, exercised by
  `test_d6_original_changed_since_verification`); pause/resume — `pause()`/`resume()`
  round-trip across a fresh `OfficeSession` instance built from durable stores only
  (`test_d10_pause_resume_new_process`), no in-memory-only state relied on.
- **§5 qualification**: Q-O1 (≥60 cases) — 61/61 pass. Q-O2 (D1–D12) — 13/13 pass, all
  through the fake harness, no real API calls. Q-O5 (boundaries) — 6/6 pass. Q-O3 (live
  smoke) and the real Q-O4 campaign — explicitly not run, disclosed, not silently
  skipped.
- **Gaps found in self-review and repaired before this report**: (1) the boundaries
  frozen-file test would have permanently red-flagged the two legitimate upstream
  repairs — repaired per §4 rather than weakened or deleted; (2) the VG-1 benchmark's
  single-author-session limitation — disclosed rather than hidden (§2); (3) the R0/R1
  scope discrepancy in `URI_STATE.yaml`'s pre-existing M39 entry — repaired additively
  (§0, and the YAML update itself), not silently overwritten (validated against
  `scripts/governance/uri_state_validator.py`, verdict `VALID`).
- **What was not independently verified**: everything in this report is
  implementer-self-reported and implementer-run; no independent closing audit was
  performed by a separate session, which is the explicit condition for freezing per this
  repository's evidence-integrity rules. `integration_authorized: false` and
  `closing_audit: REQUIRED_NOT_PERFORMED` in `URI_STATE.yaml` reflect this.

## 7. Files changed / added (for the calling session's review before commit)

```
 M docs/governance/URI_STATE.yaml
 M tests/m39_office_support.py
 M tests/test_m39_flow.py
 M uri_v1/office/bootstrap.py
 M uri_v1/office/flow.py
 M uri_v1/office/writeback.py
?? docs/plans/M39_IMPLEMENTATION_REPORT.md   (this file)
?? fixtures/m39_office/benchmark/            (12 task folders, VG-1 fixture set)
?? fixtures/m39_office/viability_gate.json
?? scripts/m39_generate_benchmark.py
?? scripts/m39_office_benchmark.py
?? tests/test_m39_boundaries.py
```
The rest of `uri_v1/office/*.py`, `tests/test_m39_request.py`,
`fixtures/m39_office/fake_claude_office.py` and `fixtures/m39_office/threshold_gate.json`
were already committed to this branch in earlier `wip(m39)` commits before this pass
started and are unchanged by it (`git ls-files` confirms they are tracked, `git status`
shows no further modification to them).

No file under `uri_core/`, `uri_ui/`, `uri_v1/turn/`, `uri_v1/reference_clarification/`,
`uri_v1/results/`, `uri_v1/evaluation/`, or any pre-existing M36/M37/M38 file was edited.
