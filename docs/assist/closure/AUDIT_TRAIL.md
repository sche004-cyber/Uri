# W1/A0 closure — independent audit and repair trail

Coordinator: Claude Code session `session_01P2p3uVP5b87uL5UMyWApaJ` (the session that implemented W1/A0; it does not
review). Started 2026-10-10. This file is append-only: corrections are added as new entries, never overwritten.

## 0. Pinned scope

| Item | Value | Verified |
|---|---|---|
| Canonical baseline | `ffdf534386a3d40cf9e1646ef1080bee28dd3aa9` = `integration/git-sync-20261008` = `integration/final-qualification-20261010` | `git ls-remote origin` 2026-10-10T23:55Z |
| Candidate (cycle R1) | `223e528c7040a7b34ceb05a4f4382c0b33891d61` on `origin/ccr-cab5ed06-9hwyc4`; tree `7e96e7b2…` identical to milestone A0 tip `6d60bee` (local) | `git rev-parse <c>^{tree}` |
| Review range | `ffdf534..223e528` (11 commits, 82 files, +9174/−7). `18daa9e` (REA research) out of scope | `git diff --stat` |

## 1. Acceptance criteria for closure (defined before R1)

1. A reviewer that did not write the code, in a separate process/container with fresh context, reviews the whole
   range read-only and returns a structured verdict.
2. Every HIGH and blocking MEDIUM finding is repaired by a separate implementation worker with a regression test that
   fails before the repair, gates re-run, and a FRESH reviewer session re-reviews the new commit.
3. Closure only at ACCEPT, or ACCEPT WITH FINDINGS whose remaining items are non-blocking and documented.
4. Gates: combined Python failure set ⊆ baseline failure set (known flake allowed); `tests/web`+`tests/assist` all
   pass; Flutter failures ⊆ baseline (`reference_render_test`); no protected path changed.
5. Stop conditions per owner directive (frozen-file or owner-only permission needed, credentials/hardware block a
   mandatory gate, same blocker after 3 repairs, security fix out of scope, destructive op/scope expansion).
6. Governance limit recorded up front: plan §6 and `CUTOVER_PLAN.md` §1 name **Codex** as auditor of record for
   integration onto canonical. An independent Claude ACCEPT is recorded as such; it does not by itself authorise
   pushing to `integration/*` (this session also has no push right there).

## 2. Cycles

### R1

| Item | Value |
|---|---|
| Reviewer | separate Claude Code cloud session `session_017GFBkin32NjEb6jYwvN6vS` (child of coordinator, own container `env_019oMSZsdjVgHcUiPWH5JJvr`, fresh context, source pinned to `223e528`, instructed read-only: no edits/commits/pushes, probes in `/tmp/audit_r1`) |
| Launched | 2026-10-10T23:55:49Z |
| Prompt | `reviewer_prompt_r1.md` (this directory) |
| Coordinator gate run on candidate (Linux) | `evidence/gates_candidate_6d60bee.txt`: combined Python 37 failed / 773 passed / 24 skipped / 161 errors — failure set = baseline minus the known flake `test_requests_are_marked_done_with_the_state_they_left`; web+assist 215 passed; Flutter 526 passed / 5 skipped / 1 failed (pre-existing `reference_render_test`); protected paths changed `[]`, Phase 1 zip check BLOCKED |
| Correction | the first gate run (`evidence/gates_candidate_6d60bee_INVALID_harness_-I.txt`) used `python -I`, which removed the repo root from `sys.path`; every module failed to import. Harness defect, not a code result; kept for the record and superseded by the rerun above |
| Result | completed 2026-10-11T00:14:18Z (92 turns). Verdict **REJECT**: 2 blocking MEDIUM (R1-01 citation number extraction misses `Rs.500`; R1-02 redaction misses `OTPCode`/`cvv2`/`MPIN`/`pwd1` in both layers — interim F5 repair incomplete), 2 non-blocking MEDIUM (R1-03 Ask stays disabled after Stop + re-grant, introduced by the F4 Dart repair; R1-04 in-page layer does not mask title/headings/labels — doc claim "MET in both layers" false), 6 LOW. No HIGH. SSRF corpus, pinned connect, mixed-answer redirect, access-control core held; frozen paths unchanged; reviewer checkout left clean |
| Record | `R1_reviewer_result.txt` — machine block transcribed by the coordinator from transcript event `5fd891d2-eda3-411d-b920-a477dfca83de`; findings verbatim, two note fields abridged (disclosed in the file). A first transcription added `category` fields and renamed one key; corrected before commit |
| Reviewer cross-check of coordinator claims | reviewer reproduced 772 passed / 24 skipped and the baseline failure set; noted that "reference_render_test is pre-existing" was not re-verified by it on the baseline (coordinator evidence: `evidence/baseline_flutter_linux_ffdf534.txt` and a fresh-worktree probe 2026-10-11: baseline Flutter 510 passed / 5 skipped / 1 failed = `render desktop dashboard`) |

### Process change (owner directive 2026-10-11)

From R2 on, W1/A0 closure runs under the `uri-development-lifecycle` skill (branch
`milestone/dev-lifecycle-20261011`), after that skill is itself independently reviewed. R1 enters the skill's state
through `import-review` (a relayed review may route findings to repair but never counts as an ACCEPT). Owner
directive: Codex may be used when available but is never a mandatory dependency; a separate-process Claude reviewer
is the independent reviewer. Integration into canonical still requires the owner's authorisation for the push
(this session has no push right to `integration/*`).

### Owner decisions D1-D6 (2026-10-11)

Recorded in `docs/governance/OWNER_DECISIONS_20261011.md`. Applied here: D3 — W1 now also reads `TAVILY_API_KEY`
(and `BRAVE_API_KEY`, `SEARXNG_URL`) from the development folder's `.env` (located through the runtime's
materialization receipt `candidate_source`, then the runtime source root), `search_keys.json` taking precedence;
nothing else in the file is kept, the process environment is not modified, values are never logged
(`uri_web/search.py` `load_env_keys`, worker hook, `tests/web/test_w1_env_keys.py`). Live search: NOT VERIFIED in
the cloud container (no `.env` here; the key lives on the owner's PC). This change is part of the W1/A0 candidate
reviewed from R2 on.

### Lifecycle run W1-A0-closure (driver pinned at the skill commit `39ed499`)

Imported R1 (relayed, not independent) → repairs P1-P6 by separate implementer processes, fresh independent reviews
R2-R8 (R7 interrupted by the coordinator at a safe point to move the driver to a detached process). Diagnoses D1-D4
before repeated repairs. Stopped **RETRY_LIMIT** at R8 (2026-10-11T05:25Z): R1-01 (citation number check) still
failing after 3 repairs; the redaction-by-name class (R1-02 → R2-01 → R3-01 → R8-01 `cv2`) likewise recurring.
Owner decisions D7 (quote numbers verbatim) and D8 (withhold field values by default) replace both mechanisms; the
implementation session implemented them (`tests/web/test_w1_d7_verbatim_numbers.py`, `tests/assist/
test_a0_d8_fail_closed.py`: 28 of 35 fail on `87720d6`, the 7 passing are intended controls; 2556 + 35 W1/A0 tests
pass after) and the run resumes for fresh independent review of the whole range.
