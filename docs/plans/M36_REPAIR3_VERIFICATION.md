# M36 repair round 3: positive-allowlist certainty gate

State: `M36_REPAIRED_AWAITING_INDEPENDENT_REAUDIT`. NOT FROZEN. Date: 2026-09-28.
Base: `410d1b8` (repair round 2), which is on top of `610c8f8` / `405db1f`. Frozen baseline: `291c9da`.

**Independence disclosure.** This repair was made by the Claude session that ran the first internal re-audit of `405db1f`. Every result below is self-verification by the repairing session. It is not an independent audit, and freeze is not authorized. An independent re-audit (Codex or a fresh audit thread) is required.

## Why

Two same-provider internal re-audits returned REPAIRS_REQUIRED:
- at `405db1f`: R-1..R-3 (negation gaps) and A-1 (whole-task forget);
- at `410d1b8`: further glyph and idiom gaps, and a forget-then-verify ordering bypass.

The User then chose, on 2026-09-28, to replace the growing negation blocklist with a positive allowlist. Exact-title CONFIRMED binds only when the rest of the message is plainly affirmative about that file; anything else asks a clarifying question.

## What changed (all inside the authorized M36 scope)

| Area | Change |
|---|---|
| `uri_v1/memory/contracts.py` | `affirmative_words()` / `affirmative_context()`. The check passes only if every character is ASCII alphanumeric, whitespace or `.,!?:;"'()“”‘’`, and every word is in a closed affirmative vocabulary (`AFFIRMATIVE_FILLERS`, `AFFIRMATIVE_ACTIONS`, `STATUS_FILLERS`). Contractions split at the apostrophe, so `it's` passes but `don't` → `don` `t` never does. There is no Unicode normalization to get wrong: any glyph, fullwidth, zero-width or soft-hyphen form is outside the allowed character set. `negated()` is unchanged from `410d1b8` and is no longer extended. |
| `uri_v1/memory/uri_adapter/envelope.py` | `affirmative_around()` checks the trusted raw turn with the grounded expression removed. It gates every certainty path: `project()` (exact title/ID → `NON_AFFIRMATIVE_CONTEXT`, and the single-attachment deterministic anchor), `register()`, and `respond_free_input()` (answer turn). Explicit UI selections (`respond_selection`) are not gated, because they are the user's own click. Non-exact phrase references still project for clarification as before. |
| `uri_v1/memory/recorder.py` | A user status transition must be the status keyword plus `STATUS_FILLERS` only. Questions (`?`, or a leading is/are/am) are not declarations. The `negated()` check is kept as well. |
| `uri_v1/memory/index.py` | Ordering bypass: when writing, nothing except a tombstone may be recorded against a task whose `TASK_OPENED` is hidden (`TASK_HIDDEN`). Whole-task forget is also blocked while the task has a visible claim with no verdict, as well as when it has a FAILED verdict (the A-1 rule from `410d1b8`). A stale claim can be forgotten first, then the task. |
| Tests | `tests/test_m36_memory_audit_repairs.py`: 28 unlisted non-affirmative forms × 2 spans, 12 affirmative controls, explicit ID, attachment anchor, free input, 10 status negatives, 8 status positives, 3 ordering tests. |
| Battery | 6 new predeclared case forms (4 NO_CONFIRMED, 2 CONFIRMED_CORRECT). The driver now passes the decoder's filename proposal for every negated and affirmative form, so the gate itself is exercised. Thresholds unchanged (`e5fdeff5…af24af`). |
| Governance | `URI_STATE.yaml` and `M36_STATE.md`: status set to repaired / awaiting independent re-audit. History is appended, not overwritten. |
| Evidence | `docs/plans/m36_audit_probes/reaudit1_probes.py` and `reaudit2_probes.py`: both internal re-audits' probe files, unchanged. |

## Verification (Linux, Python 3.11.15)

| Check | Result |
|---|---|
| M36 tests + governance tests | 276 passed, 1 skipped (Windows junction), 1 failed: `test_core_adapter_import_boundaries_and_frozen_scope`. That test fails for any successor-milestone file, and the failure is already disclosed. |
| Re-audit 1 probes (`reaudit1_probes.py`) | 73/73 pass (40 failed at `405db1f`). |
| Re-audit 2 probes (`reaudit2_probes.py`) | 70/70 pass (55 failed at `410d1b8`, per that audit's draft report). |
| Qualification driver | 189 reference cases × 2 runs, `wrong_confirmed=0`, `invented_ids=0`, deterministic, and every CONFIRMED_CORRECT form confirmed. |
| Frozen anchors | ok=True, changed=[], RAR SHA `4db77566…5e1b95`. |
| Frozen scope vs `291c9da` (`uri_v1/turn`, `reference_clarification`, `evaluation`, `results`, `uri_core`) | No change. |
| Governance validator | VALID. |
| M37/M38 tests | 52 passed, 1 failed: `test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged`. It pins M36 at `405db1f`, so it fails for any M36 repair, and it already fails at `410d1b8`. It is a cross-milestone guard, not a behaviour regression. |
| Full repository suite vs `410d1b8` | Same host and dependencies, root run excluding `step*_test.py`. `410d1b8`: 3,454 passed / 17 failed / 67 skipped. This repair: 3,546 passed / 17 failed / 67 skipped. **Identical failure node IDs**: the 15 pre-existing baseline failures (M20, M33.1, orchestrator and usage tests outside Memory) plus the two cross-milestone guards above. The +92 passes are the new tests. Node IDs are in `M36_REPAIR3_BROAD_FAILURES.txt`. |
| `git diff --check` | Clean. |

## Accepted costs (User-accepted tradeoff; measured)

Plain requests such as `open budget.xlsx please`, `I'd like to review budget.xlsx` and `could you fix budget.xlsx?` still confirm. These now ask a clarifying question instead of confirming:
- anything with words outside the vocabulary: `fix the totals in budget.xlsx`, `summarize budget.xlsx in 3 bullets`;
- turns naming a second file: `open budget.xlsx and report.docx`, `update budget.xlsx using worker.py`;
- contrastive turns: `update budget.xlsx but keep the format`;
- emoji and non-English turns.

A status change needs a plain declaration (`done`, `it's done`, `please cancel this task`, `pause for a moment`). Whole-task forget is refused while a visible claim awaits its verdict.

## Not verified here

- Windows-only paths (junction, reparse, `MoveFileExW`). No change touched them.
- `negated()` is still imported by M37/M38 (`uri_v1/execution/workspace.py`, `uri_v1/execution/harness/contracts.py`) for approval gates, and it keeps the `410d1b8` list's gaps. That is outside M36 scope and is flagged for the M38 lane.
