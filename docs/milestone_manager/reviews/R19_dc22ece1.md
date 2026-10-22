# Review R19 — Milestone Manager @ dc22ece1c1c69b9a253e19d0413134928fb841dc

| Item | Value |
|---|---|
| Reviewer | fresh isolated Claude subagent (general-purpose), strict file-safety prompt (assurance SUBAGENT) |
| Date | 2026-10-22 (local) |
| Candidate | `dc22ece1c1c69b9a253e19d0413134928fb841dc` (pre-checks passed; additions only) |
| Result class | COMPLETED_WITH_RESULT |
| Verdict | **REJECT** — 2 findings (1 MEDIUM, 1 LOW), BLOCKING_OPEN 1 |
| Tests run by reviewer | 182 passed in 34.45s |
| File-safety | no write outside its temp dir; one `sed -i` on its own scratch script inside that dir (reported) |
| Experiments | `R19_experiments/` |

Prior: R18-01, R18-02, R18-03 FIXED (fold still O(resolutions × conflicts) but within N3 at realistic sizes; not
claimed linear). Display ids identical across hosts and hash seeds; same id in every display; `_fp` never written or
shown. Core guarantees, git round trip to INTEGRATED, real P0 import re-confirmed. N3: rebuild 0.17 s, CLI status
0.45 s; 2,000 open + 2,000 resolved conflicts: projection 0.68 s, CLI status 0.96 s without the task query. Stress:
410 reads, 0 false alarms.

| ID | Sev | Defect |
|---|---|---|
| R19-01 | MEDIUM | `status` showed one conflict per milestone but printed a ready-to-run `--id` whose check covered all conflicts of that event (e.g. a BASIS_INVALID behind a VERSION line); following it closed the unshown conflict |
| R19-02 | LOW | `resolve_conflict` docstring and §26 still described 12-hex ids |

Repair: `R19_REPAIR.md`.
