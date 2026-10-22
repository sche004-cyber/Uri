# Review R22 — Milestone Manager @ aa70a5ba4ba610cad21b9727ab1d2d96207766f2

| Item | Value |
|---|---|
| Reviewer | fresh isolated Claude subagent (general-purpose), strict file-safety prompt (assurance SUBAGENT) |
| Date | 2026-10-22 (local) |
| Candidate | `aa70a5ba4ba610cad21b9727ab1d2d96207766f2` (pre-checks passed; additions only) |
| Result class | COMPLETED_WITH_RESULT |
| Verdict | **REJECT** — 5 findings (1 HIGH, 2 MEDIUM, 2 LOW), BLOCKING_OPEN 3 |
| Tests run by reviewer | 189 passed in 35.07s |
| File-safety | no breach (all writes under the reviewer's own temp directory) |
| Experiments | `R22_experiments/` (`r22_sec*.py`, `r22_cand*.py`, `r22_ac.py`, `r22_resume.py`, `r22_scan2.py`, `r22_tamper.py`) |

Prior: R21-01, R21-02, R21-03 FIXED. Core guarantees re-confirmed (guards, no cache, tamper detection, crash and
recover, record-then-refuse, duplicate ids across hosts, git three-host round trip, real P0 import read-only,
lifecycle snapshot, secret refusal through `_write`, status JSON schema, output-path id sweep). N3: rebuild 0.174 s,
CLI status 0.44 s at 10,000 events. Stress: 1,449 reads, 0 false alarms.

| ID | Sev | Defect |
|---|---|---|
| R22-01 | HIGH | `reanchor` and `recover` appended actor/session/reason without the secret check (F16); a secret landed in the append-only segment |
| R22-02 | MEDIUM | a concurrent candidate change on another host left a milestone ACCEPTED/INTEGRATED (BLUE/GREEN) on an unreviewed commit once the VERSION conflict was resolved |
| R22-03 | MEDIUM | `autocommit` committed the whole index, sweeping unrelated staged files into an `mm:` commit |
| R22-04 | LOW | `resume --max-chars` below 60 produced a negative slice and printed nearly the whole brief |
| R22-05 | LOW | `resolve-conflict --id` help still named `status` as showing ids |

Repair: `R22_REPAIR.md`.
