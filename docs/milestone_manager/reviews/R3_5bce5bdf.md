# Review R3 — Milestone Manager @ 5bce5bdf77b7e391805614a8f7841e2157f14eb8

| Item | Value |
|---|---|
| Reviewer | fresh isolated Claude subagent (general-purpose), self-contained prompt, read-only (assurance SUBAGENT) |
| Date | 2026-10-21 |
| Candidate | `5bce5bdf77b7e391805614a8f7841e2157f14eb8` (pre-checks passed; additions only) |
| Result class | COMPLETED_WITH_RESULT |
| Verdict | **REJECT** — 8 findings (5 MEDIUM, 3 LOW), BLOCKING_OPEN 5 |
| Tests run by reviewer | 93 passed in 20.85s; independently re-ran the R2 pre-repair proof via `git archive` of `4a54ebe1`: 16/16 failed (matches R2_REPAIR) |
| Experiments | `R3_experiments/` (adapted R2 scripts + `x1`..`x14`) |

Prior findings: R2-01..R2-14 FIXED (R2-06 within a segment; cross-host see R3-04); R1-05 PARTIAL (R3-02); R1-07,
R1-11, R1-13 FIXED.

| ID | Sev | Defect | Evidence |
|---|---|---|---|
| R3-01 | MEDIUM | `reanchor` can re-base over a detected truncation silently; `{}` anchors or a removed entry disable detection | x1 (a)(b)(c) |
| R3-02 | MEDIUM | decision supersede links not hash-bound (`by_target: None`, plain ids stored, importer links without target) | x3, x3b |
| R3-03 | MEDIUM | import collision test compares path strings: same file via another path = 90 collisions, exit 1 | x4 |
| R3-04 | MEDIUM | cross-host causal order depends on clocks: a host behind writes events that sort before what they answer (fail-closed, visible) | x2 |
| R3-05 | MEDIUM | lock-free readers on Windows intermittently report "anchors missing" during a writer's replace (1-6 of ~165 reads) | n2b/n2c |
| R3-06 | LOW | BATCH_ABANDONED sorted before the batch is a no-op; recover keeps reporting | x8 |
| R3-07 | LOW | all-digit values exempt: numeric keys/passwords not refused | x12 |
| R3-08 | LOW | doc says "latest review"; size estimate 4-5 MB vs 6.89 MB; dead helper | source, n6 |

Checked without defect: NEGATIVE_REVIEW not bypassable via duplicate keys; commit-bound approvals; heap merge
deterministic across hosts (identical projections); real P0 registers: 90/85 recorded, 0 collisions, 0 secret skips,
re-import unchanged; CLI exit codes as documented. Performance under load: rebuild 0.34-0.39 s; `status_json`
0.84-1.01 s in-process (borderline under load, not counted as a finding).

Repair: `R3_REPAIR.md`.
