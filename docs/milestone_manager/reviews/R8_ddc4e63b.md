# Review R8 — Milestone Manager @ ddc4e63b3904ecccb81784a3cee2907cdda8c056

| Item | Value |
|---|---|
| Reviewer | fresh isolated Claude subagent (general-purpose), strict file-safety prompt (assurance SUBAGENT) |
| Date | 2026-10-22 (local) |
| Candidate | `ddc4e63b3904ecccb81784a3cee2907cdda8c056` (pre-checks passed; additions only) |
| Result class | COMPLETED_WITH_RESULT |
| Verdict | **REJECT** — 5 findings (3 MEDIUM, 2 LOW), BLOCKING_OPEN 3 |
| Tests run by reviewer | 129 passed in 24.97s |
| File-safety | everything under the reviewer's temp dir; repository clean afterwards |
| Experiments | `R8_experiments/` (`r8_torn.py` cuts every byte offset of several lines) |

Prior: R7-02 FIXED; R7-01 PARTIAL (R8-02); R7-03 FIXED as stated but introduced R8-03..R8-05. Core guarantees
re-confirmed; stress ~1,700 reads 0 alarms; real P0 import 93/85 idempotent; N3 rebuild 0.25 s, CLI status 0.44 s.

| ID | Sev | Defect |
|---|---|---|
| R8-01 | MEDIUM | `_torn_continues_batch` refused legitimate cuts between `"batch"` and the end of the id |
| R8-02 | MEDIUM | a byte-truncation of an applied batch past the batch id was "proven" harmless and hidden without review (genuine bytes, no forgery) |
| R8-03 | MEDIUM | `init-host` retry exception let a second machine take over another machine's registered segment |
| R8-04 | LOW | retry after a failed `init-host` impossible inside git (stray untracked segment) |
| R8-05 | LOW | failed `init-host` deleted a pre-existing anchors file |

Repair: `R8_REPAIR.md`.
