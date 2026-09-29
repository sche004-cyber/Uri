# Dynamic Planning Slice 1: Implementation Report

Status: **PROVISIONAL / NOT FROZEN.** Implementation of migration-plan Steps 3 and 4 (Stage 2 §8), for the fresh independent audit in Step 5. Same-provider self-report; every claim below is a lead for the audit, not evidence.
Plans: `docs/architecture/DYNAMIC_PLANNING_CANONICAL_ARCHITECTURE.md` (Stage 2), `docs/plans/DYNAMIC_PLANNING_MIGRATION_PLAN.md` (Stage 3). Decisions D1 to D3 (Chetan, 2026-09-29 01:10Z).

## 1. Base

- `BASE` = `4292528` (the two plan documents) on top of `21bcc63`, the tip of `claude/project-thread-2vamlf` when implementation started (D1 working line). Rollback point: `BASE`.

## 2. Frozen battery (recorded before the first qualifying run)

These digests were recorded and committed before `scripts/dynamic_planning_qualification.py` was first run against the battery. Digests are over LF-normalized bytes for the JSON files (the script uses the same normalization) and raw bytes for the workbooks.

| File | sha256 |
|---|---|
| `fixtures/dynamic_planning/qualification_cases.json` | `2c36641926db04e679fb937ce10d0fff141c7989e049618caf9759002fd0f419` |
| `fixtures/dynamic_planning/threshold_gate.json` | `f2dfc9371871eb994ff22f4e5a6d0802864980d9dab03e521a8dac04938c50ff` |
| `fixtures/dynamic_planning/capability_qualification.json` (pinned in `actions.py`) | `98c1d78e22138ce6f83c767f0524b4564f81658b3f99efda2bfaaa8b834e7c49` |
| `fixtures/dynamic_planning/make_workbooks.py` | `02079cbddad55c5c7efbbe6ee766ed3de986ff3d8860c450cd45ae78d1acf9f2` |
| `workbooks/wb_a.xlsx` and `wb_same_as_a.xlsx` | `cec400e4af19eb279a7ff4a76c8cde8cacad2ce86c5bd92abbeb67ba95e08bec` |
| `workbooks/wb_b.xlsx` | `7a360f54b71967a6efc7053e9ae9799796560367ee277a73fe768e8d414c0cc0` |
| `workbooks/wb_big_header.xlsx` | `87f890af7122ed25c1795867da4e72e10f10a0f8c8d4f658b84d74bd99346c5d` |
| `workbooks/wb_formula_err.xlsx` | `ce00b21bc0fbf59af0d679238d6ae6c1d76dd1306a877fe01c561f7e9a2c8e00` |
| `workbooks/wb_malformed.xlsx` | `a2299a934d0befe8931ddabf7672fa4467e0e0abc0034caa98e7908c19bf6015` |

`make_workbooks.py` regenerates byte-identical workbooks (fixed zip entry time, stored entries); two independent runs produced the digests above.

Battery notes, fixed at freeze time:
- C32 is split into `C32a` (malformed JSON) and `C32b` (timeout) so each has one typed expectation.
- C13 exercises the node limit. The edge and literal limits are covered by unit tests.
- The runner reads only `cases`; the scorer reads `expected` after every case has run.

(Sections 3 onward are completed after the checks run.)
