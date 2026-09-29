# M39 Office Demonstrator — Implementation Report (R0 scope)

Status: `M39_IMPLEMENTED_PROVISIONAL_NOT_FROZEN`. Implementer self-qualification only;
independent closing audit **not performed**. Not frozen, not integration-authorized.

**CORRECTION (M39 repair round 1, preserving history per the auditable-correction
requirement rather than silently editing the claims below):** the internal audit at
`a9098e0` (`docs/plans/M39_INTERNAL_AUDIT_REPORT.md` / project files
`audits/M39_INTERNAL_AUDIT_REPORT.md`) found two claims in §6 below contradicted by its
probes, both since fixed by the M39 repair round 1 session (`uri_v1/office/flow.py`,
`uri_v1/office/writeback.py`):
- The claim that harness escalation is gated "on an explicit, non-negated
  `WritebackApproval`/consent intake" was false as originally built: the gate was a
  bag-of-words check (`_CONSENT_WORDS` substring match) that a question like "how long
  will it run?" or an unrelated new request could satisfy. Repair round 1 replaced it
  with `_is_consent()`, a whole-reply affirmative check that rejects any question and
  any reply containing a non-affirmative token, and records the consent decision in
  Memory.
- The claim that `acceptance_builder.py` guards "structurally" against a fabricated
  harness fix was true only for the empty-script variant (M38 D-4); a script rewritten
  to produce the right shape (`ws.title = "Summary"`, a hard-coded header list, no read
  of the real workbook) still passed. This is **not fixed** by repair round 1 -- it
  needs an input-dependence/recompute check shared with the M37 acceptance owner, out of
  this repair lane's bounded scope. What round 1 did fix: the `NO_OUTPUT_WARNING`
  ("URI can only check that the script runs") caveat was being dropped specifically on
  the harness-approved path, so a neutered fix could render as a bare "Verified." with
  no caveat at all; it is now carried through every path.

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

> **Correction (repair round 3, re-audit R2-4; the line above is kept as history).** Both
> "oracle_confirmed" tasks in that summary were the two `no_success` tasks, not
> successes: the scorer read a `summary.xlsx` that write-back never returns, so no success
> could ever match, and the driver exited 0 whatever the outcome. See §9 for the fixed
> driver and its current result.

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

## 8. Repair round 2 (R1 re-audit residuals: R1-A..R1-D)

A fresh, same-provider re-audit of repair round 1 (`915a1ac`,
`audits/M39_REPAIR1_REAUDIT_REPORT.md`) found repair round 1's own fixes for M39-2/3/4
each closed the audit's original reproduction but left a narrower residual path open
(R1-A..R1-C), plus one new regression (R1-D). This round closes all four, entirely
within `uri_v1/office/*` -- no `uri_core`, `uri_ui`, or M36/M37/M38 file touched.

- **R1-A (High, residual of M39-4):** `OfficeSession.pause(task_id, run_id=...)` stored
  whatever `run_id` its caller passed, with no check that this session had ever offered
  that run for approval. `approve_writeback`'s "only the offered run" check only holds if
  `pause()` cannot be used to forge what "offered" means, and the CLI is honest but the
  Python API (and any future caller, e.g. the planned `/ask` seam) is not bound by CLI
  behavior. Combined with a separate, disclosed M38-owned gap -- the harness runner's
  post-verification `ORIGINAL_MODIFIED_DURING_VERIFICATION` flag
  (`uri_v1/execution/harness/runner.py:98-99`) is computed only in-memory and never
  persisted to the run store -- a run URI itself reported `HARNESS_FAILED` could still be
  written back via `pause(run_id=<that run>)` if the original was restored first (user
  revert, or a `setsid`-escaped helper). Fix: `pause()` now accepts only a `run_id` equal
  to `self._run.get(task_id)`, the run this exact session already offered via
  `_offer_writeback`; anything else refuses `RUN_ID_NOT_OFFERED`, the same reason
  `approve_writeback` already used. Because `HarnessOutcome.verified` is computed
  synchronously inside `HarnessRunner.run()` and already accounts for this flag
  (`verified = lineage.verification_status == "VERIFIED" and not flags`),
  `confirm_escalation` never calls `_offer_writeback` for a flagged run in the first
  place -- the only way such a run_id could ever reach "offered" was through `pause()`
  accepting an out-of-band value, which this fix removes. The underlying M38 gap (the
  flag itself not being durable) remains open and is not fixable from this package
  without touching M38-owned `runner.py`; it is disclosed here and no longer reachable
  through `uri_v1/office/*`. Regression tests:
  `test_r1_a_pause_refuses_a_run_id_this_session_never_offered`,
  `test_r1_a_pause_refuses_another_tasks_run_id`,
  `test_r1_a_flagged_run_via_pause_after_restore_cannot_write_back` (the last exercises
  the real `HarnessRunner`/`ClaudeCodeAdapter` path against a new adversarial test-only
  fake, `fixtures/m39_office/evil_claude_office.py`, not a hand-written run-store record).

- **R1-B (High, residual of M39-3):** `_PY_QUOTED`/`_XLSX_QUOTED` recognised only ASCII
  `"`/`'`, so a name auto-corrected to smart quotes (Word/macOS/iOS), wrapped in
  backticks (chat/markdown), or left unquoted still parsed as only its trailing
  `.py`/`.xlsx` fragment and silently bound the wrong, shorter file. Fix: the quote
  character classes now also recognise `“ ” ‘ ’` and backtick
  (mismatched pairs are still tolerated, as the original ASCII-only pattern already did,
  since this module has no way to know which side is "wrong"). For the genuinely
  unquoted case, an unquoted filename match immediately preceded by a single word that
  isn't one of this request grammar's own function words (`make`/`get`/`with`/`the`/etc.)
  is now refused as `ROLE_AMBIGUOUS` rather than silently bound -- `request.py` has no
  access to the real file list, so it cannot tell "my report.py" (a real file) apart from
  "my" (possessive) plus the distinct file "report.py", and refusing rather than guessing
  is the module's existing design principle (see its own docstring). Every unquoted
  phrasing already exercised by the M39 test suite (`make`/`get`/`fix`/`have report.py
  work/run with sales.xlsx`, `... or/and backup_report.py ...`, `... with the
  sales.xlsx`) keeps parsing exactly as before. Regression tests:
  `test_r1_b_quote_variants_bind_the_full_space_containing_name`,
  `test_r1_b_unquoted_space_name_is_ambiguous_not_silently_wrong`,
  `test_r1_b_smart_quote_end_to_end_never_writes_the_plain_file`.

- **R1-C (Medium, residual of M39-2):** `_is_consent`'s tokeniser (`[a-z']+`) silently
  dropped every character outside ASCII letters, so a reply mixing an English
  affirmative word with an emoji, another script, or full-width punctuation (`ok
  ❌ 不要`, `okay‽`, `¿yes`, `ok, run it？`) kept only its
  recognised English words and passed as consent. Fix: the question-mark check now also
  matches full-width `？`, interrobang `‽`, inverted `¿`/`؟`, and
  `⸮`; tokens are now taken from whitespace-splitting the whole reply (stripping
  each token's own leading/trailing ASCII punctuation), and every token must both be in
  the affirmative vocabulary and match `[a-z']+` in full -- so a token containing any
  non-ASCII-letter character (an emoji, CJK/Cyrillic text, a bare digit) refuses consent
  instead of being silently ignored. Regression tests:
  `test_r1_c_non_ascii_and_symbolic_replies_are_not_consent` (10 cases from the re-audit),
  `test_r1_c_non_ascii_decline_never_starts_the_harness`.

- **R1-D (Medium, new regression introduced by repair round 1):** the M39-3 fix's
  continuation check (`_CONTINUATION`, which includes `.`) treated a sentence-final `.`
  or `...` the same as a mid-token `.`, so `"make report.py work with sales.xlsx."`,
  `"Please fix report.py. It should work with sales.xlsx"`, and `"make ./report.py work
  with sales.xlsx"` all regressed to `ROLE_AMBIGUOUS` (all three parsed fine before
  repair round 1). Fix: a run of one or more `.` at the end of a match is a continuation
  only when something token-like follows once the dots are skipped (`report.py.bak`
  still refuses); a `.`/`...` followed by whitespace or end-of-text is ordinary sentence
  punctuation. A leading `./` is now recognised as a normal, unambiguous script-in-its-
  own-directory prefix rather than a continuation of the text before it. `report.py.bak`
  and `data.xlsx.py` (M39-3's own original cases) are still refused, verified by the same
  regression test file. Regression tests: `test_r1_d_sentence_final_punctuation_still_parses`,
  `test_r1_d_fix_does_not_reopen_m39_3_longer_token_refusal`.

**Disclosed, not fixed (out of this bounded round's scope):**
- The M38-owned root cause behind R1-A (the post-verification safety flag never reaching
  the run store) is unchanged; R1-A's fix closes every path reachable through
  `uri_v1/office/*`, but the flag itself still is not durable outside this package. Any
  future caller with direct run-store/Memory access (bypassing `OfficeSession` entirely)
  is not covered by this fix.
- R1-E (Low, UX): a clarifying question during escalation consent still discards the
  pending proposal (`ESCALATION_DECLINED`, proposal deleted) rather than keeping it
  available for a later "yes". This is unchanged from repair round 1, is exercised by an
  existing, still-passing test (`test_m39_2_question_never_starts_harness`, which asserts
  the proposal is cleared), and the re-audit flagged it as a product/UX choice for the
  project owner, not a defect -- left as is rather than reversed without that decision.
- R1-F (Low, disclosure): the M39-7 CLI delivery gap (generated/ADDED-output delivery,
  disclosed since R0) remains disclosed only in commit messages, not in this report or
  `URI_STATE.yaml`, for repair round 1's part of the gap; this repair round adds no new
  instance of it and does not attempt the M36-owned fix it needs.

**Verification (this round, independently re-run, not merely claimed):**
- All 60 of the re-audit's own probes (`audits/m39_reaudit/test_m39_r1_reaudit_probes.py`)
  pass against this repair, including every R1-A..D reproduction, confirmed by direct
  re-run of that exact file (not a rewritten copy).
- All 37 of the original R0 audit's probes (`audits/m39_audit/test_m39_audit_probes.py`)
  still pass -- no regression in what repair round 1 already fixed.
- `pytest tests/test_m39_request.py tests/test_m39_flow.py tests/test_m39_boundaries.py
  tests/test_m39_repair1_regressions.py tests/test_m39_repair2_regressions.py`: 132
  passed.
- `pytest tests/test_m37_*.py tests/test_m38_*.py tests/governance`: 109 passed, 1 failed
  (the same pre-existing, disclosed scope-guard failure as every prior M39 commit --
  `test_m36_and_frozen_files_unchanged` flags M39's own files, which is expected and not
  new).
- `pytest tests/ --ignore=tests/test_m31_model_brain_ux.py`: 923 passed, 1 skipped, 2
  failed (the same two disclosed scope-guard failures as the R0/R1 audit baselines, none
  new).
- `scripts/m33_3_r_anchors.py`: `ok: True, changed: []`.
- `scripts/governance/uri_state_validator.py`: `VALID`.
- Diff scope (`git diff a9098e0 HEAD --name-only` for this round's own changes):
  `uri_v1/office/flow.py`, `uri_v1/office/request.py`,
  `fixtures/m39_office/evil_claude_office.py` (new, test-only),
  `tests/test_m39_repair2_regressions.py` (new), and this section of this report. No
  `uri_core`, `uri_ui`, or M36/M37/M38 file appears in the diff.

## 9. Repair round 3 (re-audit of 7bcbbee on the frozen M36-M38 line: R2-1..R2-5)

Base: `7bcbbee` merged onto the freeze commit `5bbf738` (code frozen at `bd7c450`). The
merge had one additive doc conflict (`docs/governance/URI_ACTIVE_MILESTONE.md`, both
notes kept). No frozen (M33.x, M36-M38) or live-app file differs from `5bbf738`. Status
stays **PROVISIONAL, NOT FROZEN**; a fresh audit follows.

**Fixed:**
- **R2-2 (High).** `writeback.py` no longer fabricates a "write-back complete" user turn.
  Completion goes through frozen M36's runtime path
  (`task_state(..., runtime_action=_runtime_observation(intake, "VERIFIED_COMPLETE"))`),
  linked to the run's own VERIFIED verdict (whose inputs are the task's pre-write
  references, as `index.py:145-149` requires); the write-back verifier's independent
  verdict is named in the checkpoint text. Any failure after the originals were written,
  including an unexpected exception, is now a `WritebackRefused` carrying `written`, and
  the task is moved to `FAILED` through M36's runtime `FAILURE` path with the files named
  (falling back to a checkpoint note, and reporting if even that cannot persist).
  `_runtime_observation` is a private M36 hook; M39 is trusted URI runtime code calling it
  with the real trusted approval turn, which is the use its docstring describes.
- **R2-1 (High), per-file answers (the User's chosen design, 2026-09-29; see §11).** A two-filename request
  still cannot bind in one turn on the frozen line. That rejection used to be a dead end;
  `binding.py` now turns exactly that rejection (`NON_AFFIRMATIVE_CONTEXT`, no Memory
  round) into an M39 per-file question ("which file is the script?"), answered in a fresh
  turn holding just the file name, which frozen M36 grounds and binds on its own terms. A
  bad answer is asked again; a name collision opens the normal Memory round. The REPL now
  routes the next line to a pending question unless it is itself a new request. This
  was written as an interim fix; the User has since chosen it as the design (§11), and
  frozen M36 stays unchanged.
- **R2-3 (Medium).** `request.py` treats any non-whitespace, non-punctuation character
  touching an unquoted name (digits, CJK, `\`, `~`, `..`) as part of a longer name, and
  any preceding token outside the safe function words as possibly part of the name. "Q1
  sales.xlsx", "2024 report.py", "报告 report.py", "2024-Q1 sales.xlsx",
  `C:\old\report.py`, `..\report.py`, `../report.py` and `sales.xlsx~` are refused as
  ambiguous; quoting disambiguates. `OfficeSession.start` returns a typed `UNSUPPORTED`
  for a refused parse instead of crashing.
- **R2-4 (Medium).** The benchmark copies the folder as it stands after write-back, runs
  the returned `report.py` offline, and scores its `summary.xlsx`; `NOTHING_TO_WRITE` is
  scored by running the unchanged script. Hard gates (false verified, originals modified
  without approval, wrong file bound) are measured from live files and Memory. It exits 1
  when a hard gate fires, an in-envelope task is not oracle-confirmed, or a no_success task
  is not refused.
- **R2-5 (Low).** `test_r1_a_flagged_run...` now expects frozen M38's `FAILED`; the M39
  boundary guard's baseline moved from `610c8f8` to `5bbf738`. Q-O1 labels for the 28
  two-filename cases are now `ASK_THEN_BOUND` / `ASK_THEN_CLARIFY`, which is the
  intended behaviour under the chosen design (§11).

**Still open:**
- ~~R2-1 route choice (User)~~ Decided 2026-09-29: per-file answers (§11).
- ~~R2-6 (User): frozen `tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged`
  fails, and only because of the 86 M39 paths it does not allowlist. Not edited.~~ Resolved
  2026-09-29 by the User's authorized minimal allowlist entry (§12).
- R1-E and R1-F unchanged (see §8).

**Verification (Linux, this round):** M39 tests 170 passed (`tests/test_m39_*.py`,
including 38 new in `test_m39_repair3_regressions.py`); `tests/` 1,472 passed, 1 failed
(the frozen M37 guard above), 9 skipped (Windows paths); M36/M37/M38 quals exit 0 and
gates pass; anchors `ok: True, changed: []`, RAR `4db77566...`; governance `VALID`.
Benchmark dry run: gate PASS, exit 0; 4 completed and oracle-confirmed by running the
returned script (task_01-04), 1 verified already working (task_07), both no_success
tasks refused, hard gates 0; the outside-envelope tasks end `HARNESS_FAILED` because the
dry-run fake harness applies an empty fix. Re-audit probes: 39 OK, 1 `FINDING` (F1, which
expected a two-filename request to bind in one turn; under the chosen per-file design
(§11) that expectation no longer applies). The R0 and R1 audit
probes (97) pass once the per-file questions are answered; run unmodified they stop at
that first question. Not verified: Windows, Chetan's machine, any live harness run.

## 10. Repair round 4 (re-audit of 7838479: LOW items F-1..F-4)

The re-audit of `7838479` found no blocking findings and four LOW items. All four are
fixed inside `uri_v1/office/` and `scripts/m39_office_benchmark.py`, with regressions in
`tests/test_m39_repair4_regressions.py`. No frozen or live-app file changed, and the
frozen M37 guard was not touched. Status stays **PROVISIONAL, NOT FROZEN**.

- **F-1:** `_record_partial_write` re-reads the task's current head before each attempt
  (with one retry on CONFLICT), because the record states what already happened on disk
  and is not conditional on the head the approval saw. A concurrent checkpoint no longer
  leaves the task silently OPEN. Remaining limit: if another writer moved the task to a
  terminal state, M36 refuses the FAILED transition; the note is tried, and otherwise the
  refusal reports `NOT_RECORDED`. A `VERIFIED_COMPLETE` that races a concurrent writer
  still fails on the stale head by design and is then recorded as FAILED.
- **F-2:** an interrupt (`KeyboardInterrupt`, `SystemExit`) during or after the write is
  re-raised unchanged, after any files already on disk are recorded (task FAILED, note
  `INTERRUPTED:<type>`). Remaining limit: a second interrupt while recording, or a hard
  kill, leaves no record.
- **F-3:** the benchmark summary and its stderr line list
  `not_measured_needs_real_harness` (task_05, 06, 08, 09, 10) and state that the dry-run
  fake harness applies an empty fix, Arm A is a mock, and VG-1 is not measured.
- **F-4:** "cancel" (or "abandon") while a question is pending moves the task to ABANDONED
  through frozen M36's explicit user transition, using the user's own words; words M36
  does not accept as a declaration (e.g. "stop") change nothing and the REPL says to type
  "cancel". Questions now mention "cancel", and a Memory round no longer renders an empty
  reason. Not changed: a new request typed mid-question starts a new task and leaves the
  first one OPEN; a relative-path answer such as "sub/report2.py" opens a Memory round
  rather than binding.

## 11. Decision: per-file answers for requests naming two files (2026-09-29)

The User chose **per-file answers** (Chetan, 2026-09-29 05:16 UTC) over a narrow
amendment to frozen M36. The ask-per-file flow added in repair round 3 (§9, R2-1) is
therefore the intended M39 design, not a stopgap. Frozen M36 stays unchanged.

What that means in the product: when a request names both files ("make report.py work
with sales.xlsx"), frozen M36 does not grant exact-filename certainty in that turn,
because each file's context contains the other name. URI then asks for each file in its
own turn ("which file is the script?"), and the user replies with just the name, which
M36 grounds and binds on its own terms. A request naming one file plus a phrase ("make
report.py work with the spreadsheet") still binds in one turn. The cost is two extra
turns for a two-filename request; "cancel" leaves the task (§10, F-4).

Not changed by this decision: no code (the behaviour already shipped in `7838479` /
`9290594`); the frozen M37 allowlist test (R2-6) is still an open User decision and was
not edited.

## 12. Authorized frozen-test edit: M39 entry in the M37 scope guard (2026-09-29)

The User authorized (Chetan, 05:21 UTC) the minimum M39-specific allowlist entry in
frozen `tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged`, and
asked that dynamic planning not be allowlisted across the execution-to-memory.sources
boundary. The entry is `M39_ALLOWED` = `uri_v1/office/`, `fixtures/m39_office/`,
`tests/test_m39_`, `tests/m39_office_support.py`, and the two exact M39 scripts; the
guard also rejects any `..` path segment. Nothing else in the frozen test changed, and no
M37 code changed. `tests/test_m39_boundaries.py` pins the edited file by content hash, so
any further change to it fails again. `tests/test_m39_frozen_guard_allowlist.py` proves
the guard still fails for a modified frozen file (`uri_v1/memory/contracts.py`), for new
files in frozen M36 and live-app scope, and for M39 look-alike paths; that
`uri_v1/office` does no direct file I/O (all user-file access goes through frozen
M36/M37); and that a file outside the authorized folder is never bound. With this, the
full suite has no failing test on Linux.

  Tightened the same day after the recheck of `ba0db5e` (LOW items): the three
  single-file entries (`tests/m39_office_support.py` and the two scripts) are now exact
  matches (`M39_ALLOWED_FILES`), so a longer name such as `scripts/m39_office_benchmark.pyx`
  is rejected, and the guard probes run on a disposable clone instead of editing frozen
  files in the working checkout.

## 13. Repair round 5 (independent audit of 736464a: F3, N3, F4, N1, N2, F2)

Audit: `/mnt/project-files/audits/M39_INDEPENDENT_AUDIT_736464a.md` (REPAIRS_REQUIRED).
All repairs stay inside M39's own files and docs; no frozen or live-app file changed.
R1.1 scope work (F1) is not started; it waits on the User's scope decision.

- **F3 (MED).** The escalation consent screen said files are copied to the harness
  "never the network". It now names the harness (`StepResult.harness`, from the configured
  adapter's `harness_type`) and says the file contents are sent to it and passed over the
  network to its external model provider. The posture line now says it limits the
  harness's own tools and does not stop the file contents reaching the provider. With no
  harness configured, the screen says so.
- **N3 (MED).** The HARNESS_FAILED reply said "Nothing was written to your files" even
  when the harness wrote an original (flag `ORIGINAL_MODIFIED_DURING_RUN`). It now says
  the original was changed during the harness run (or during verification of its output,
  for `ORIGINAL_MODIFIED_DURING_VERIFICATION`), not by URI's write-back, names the files
  from the run store's `uri_observations.originals_changed`, says URI did not undo it,
  and says the task stays open. "Nothing was written" appears only with no safety flag;
  any other flag reads "URI wrote nothing back". New fixture scenario `write_original`
  in `fixtures/m39_office/evil_claude_office.py` reproduces the audit's probe.
- **F4 (LOW).** `tests/test_m39_repair4_regressions.py` writes the benchmark output to a
  temporary file instead of `/dev/null`. Windows not run here.
- **N1 (LOW).** `tests/test_m39_boundaries.py` drops `KNOWN_UPSTREAM_REPAIRS`
  (763d8e7, b013dba). With the baseline at the freeze commit `5bbf738`, every frozen file
  must match it exactly; only M39 paths and the hash-pinned authorized edit may differ.
- **N2 (LOW).** Additive correction `status_correction_2026_09_29_audit_736464a` and
  `repair_round_5_2026_09_29` in the M39 entry of `docs/governance/URI_STATE.yaml`.
- **F2.** Recorded as M37-L3, a frozen-line limitation (freeze record section 7; M37
  `retained_limitation_addendum_2026_09_29`). No code change. User acceptance not yet
  recorded.

Regression tests: `tests/test_m39_repair5_regressions.py` (F3 x2, N3 x6, N1 x6). All 14
fail against the 736464a code and pass after the repair. The N1 probes restore
`uri_v1/execution/{workspace,verify}.py` and `uri_v1/edge/resolver.py` (from 763d8e7)
and `uri_v1/execution/harness/{runner,contracts}.py` (from b013dba) on a disposable clone.
