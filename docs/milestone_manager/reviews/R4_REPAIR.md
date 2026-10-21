# Repair of review R4 findings (2026-10-21)

Pre-repair candidate `c992b5ae`. All 7 findings accepted; none disputed. Regression proof: `test_r4_*` against the
pre-repair code in a detached worktree (`c992b5ae` + new test file): **10 failed, 0 passed**. After repair: 111 passed.

| Finding | Repair | Test |
|---|---|---|
| R4-01 | `reanchor` collects `anchor_errors` + `anchor_warnings` against the previous anchors; any problem without a computed loss counts as unknown history → `LOSS_NOT_ACKNOWLEDGED` unless acknowledged; acknowledged problems are recorded in `anchor_problems` → ANCHOR_LOSS | `test_r4_01_*` (remove own entry, `{}`, own count 0) |
| R4-02 | floor = newest verified event `ts` + 1 µs (strict); warnings name the newest event's segment and both possible causes; segments stamped > 5 min ahead of this clock named in `integrity_warnings` | `test_r4_02_*` (host "a" behind sorting first; future-stamped segment) |
| R4-03 | `abandon_batches` only abandons pending batches of this machine's own segment; the fold keeps abandoned incomplete batches unapplied but applies a batch that becomes complete and opens ABANDONED_BATCH_COMPLETED (RED) | `test_r4_03_*` (2) |
| R4-04 | `register_identity`: explicit `--register` or the document's first `# ` heading; collision when the existing record is not imported or from another register | `test_r4_04_*` |
| R4-05 | `write_anchors` always writes this host's entry (count 0 until refreshed); own count 0 with events = warning; missing own entry stays an error | `test_r4_05_*` |
| R4-06 | `_conflict_index` built once per projection; `perf_n3.py` committed with output `perf_n3_r4repair.json` | `test_r4_06_*` (500 milestones × 5,000 conflicts < 1 s) |
| R4-07 | `_independent_accept` docstring; handoff verification table per commit | doc/source |

Also found by the implementing session while re-running the rehearsal: the P0 worktree now has uncommitted edits to
`decisions.md` (93 DEC rows vs 90 at `8e1d6324`) and `developmental.md`. The rehearsal previously passed the commit
label unconditionally; it now records `8e1d6324` only when the file bytes equal that commit's blob, else `None`
(the file SHA-256 is always recorded). Earlier rehearsal outputs (90 decisions) match the committed blob count.

Performance (`evidence/perf_n3.py`, 10,001 events, 4.43 MB, machine also running other sessions): rebuild 0.257 s;
`status_lines` 0.223 s; `status_json` 0.246 s; CLI `status` 0.409 s, `status --json` 0.411 s.
