# Fallback review FB3 — Milestone Manager @ 4aa3d40bce462c4024fcb7d22fad507dcd0be022

Basis: driver run MILESTONE-MANAGER-d4 BLOCKED NO_INDEPENDENT_REVIEWER on 4aa3d40b (codex_cli QUOTA, claude_cli AUTH).
Reviewer: fresh isolated Claude subagent (SUBAGENT), COMPLETED_WITH_RESULT, judged against the bounded F16 contract.
Verdict: REJECT, BLOCKING_OPEN 5, FINDINGS_TOTAL 13. Tests: 405 passed. N3: rebuild 0.178 s, CLI status 0.451 s.
Stress: 0 errors. P0 import: 95 + 85 recorded, 0 skipped as secrets. Prior: all ids FIXED or documented out of contract.

| ID | Sev | Defect | Disposition |
|---|---|---|---|
| FB3-01 | HIGH | multi-word bare keys ("API key: x") not recognised | fixed |
| FB3-02 | HIGH | table rows with multi-word key, quoted key or multi-word value | fixed (multi-word key + multi-word value stays prose) |
| FB3-03 | HIGH | `__password__`, `~~password~~` emphasis | fixed |
| FB3-04 | MEDIUM | YAML block: only the first line checked | fixed |
| FB3-05 | MEDIUM | regression: ids with credential words (PASSWORD-RESET) refused via `base` | fixed |
| FB3-06 | LOW | one-word compound keys (PGPASSWORD, accesstoken) | fixed |
| FB3-07 | LOW | crafted edge cases (value starting with '-', key > 60 chars, nested placeholder chains) | open, documented |
| FB3-08 | LOW | malformed but hash-valid events make the fold raise instead of reporting integrity | open |
| FB3-09 | LOW | handoff/reviews in the candidate tree stopped at R22 | fixed (776241c5 cherry-picked, review records added) |
| FB3-10 | LOW | prose false positives (known FB2-07 class) | documented |

Repair commit: see `git log` (fix FB3-01..FB3-06); 29 of 36 new tests fail on 4aa3d40b.
