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
