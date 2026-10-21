# Repair of review R1 findings (2026-10-21)

Pre-repair candidate `2ae7a79f`. Every finding was accepted as valid (the reviewer's experiments reproduced each one);
none was disputed. Regression proof: the new tests named below were run against the pre-repair code in a separate
detached worktree (`2ae7a79f` + new test file): **23 failed, 5 passed** for `-k r1_`; after repair the full MM file
passes (see handoff for the counts on the repaired commit).

| Finding | Repair | Test(s) | Fails before repair? |
|---|---|---|---|
| R1-01 HIGH candidate swap after ACCEPTED | `update_milestone` refuses a new `candidate_commit` while ACCEPTED/INTEGRATED/DONE (`CANDIDATE_LOCKED`); INTEGRATED requires `integration.candidate_commit == candidate_commit` and re-runs the independent-accept check | `test_r1_01_*` (2) | yes |
| R1-02 HIGH guards trusted an unbound cache | cache removed; reads and writes fold the verified log; fold flags BASIS_INVALID when a positive status names no supporting review/approval | `test_r1_02_*`, `test_f17_*` | yes |
| R1-03 HIGH later REJECT ignored by DONE/INTEGRATED | `_independent_accept` (latest review on the candidate wins) used by ACCEPTED, INTEGRATED and DONE; indicator RED when the latest review contradicts a positive status | `test_r1_03_*` | yes |
| R1-04 HIGH tampered events folded, no warning | `Segment.valid_events` (prefix before the first error) is the only input to the fold; integrity banner and exit 3 for status/show/resume/ready/rebuild | `test_r1_04_*` | yes |
| R1-05 HIGH id collision across hosts overwrote records | fold never replaces a record created by another event; later duplicate kept as `<id>@<seg>.<seq>` with a DUPLICATE_ID conflict; positive status refused while a conflict touching the milestone is open (`CONFLICT_OPEN`) | `test_r1_05_*` | yes |
| R1-06 MEDIUM other segment tampered, writes continued | `_write` verifies all segments + anchors before validating | `test_r1_06_*` | yes |
| R1-07 MEDIUM deleting newest events unseen | `anchors.json` high-water marks checked by `verify`, `projection` and `_write`; docstring corrected | `test_r1_07_*` | yes |
| R1-08 MEDIUM cache offsets vs folded events | structural: no cache exists any more | `test_r1_08_*` (passes before and after; it does not reproduce the in-lock race, so the proof here is the removal of the cache) | no (stated) |
| R1-09 MEDIUM secret false negatives/positives | added Stripe, Hugging Face, JWT, URL-userinfo patterns; assignment rule moved to code covering password/token/client_secret/... with exemptions for paths, env-var names, `$VAR`, placeholders | `test_r1_09_*` (13 cases) | yes (9 of 13) |
| R1-10 MEDIUM secret row text copied into a supersession note | supersession pass skips refused rows; note is `source line N, column C` | `test_r1_10_*` | yes |
| R1-11 MEDIUM partial supersessions read as full | `source_status` applies the limiting-phrase rule ("in part", "for later phases", "run-scoped", "only", ...); the link partial flag looks 60 characters before the match too | `test_r1_11_*` (incl. real `decisions.md`) | yes |
| R1-12 MEDIUM tracebacks with exit 1 | CLI maps OSError to `IO` and malformed input to `INPUT`, exit 2; lifecycle snapshot reader tolerates non-object lines, missing keys and bad history | `test_r1_12_*` | yes |
| R1-13 MEDIUM stale handoff; N5 not completed | handoff rewritten with current state; N5 reported with its exact status (see handoff) | doc | n/a |
| R1-14 LOW case-variant self review | `norm_id` (casefold, whitespace) for implementer/reviewer comparison | `test_r1_14_*` | yes |
| R1-15 LOW multi-event writes not atomic | `append_many`: one write + fsync per command; `batch {id,n,i}`; fold applies complete batches only; incomplete batch reported as a warning; retry succeeds | `test_r1_15_*` | yes |

Docs updated: architecture §13 (change log), data model §1/§2/§10, acceptance criterion F17 amended (logged).
Migration rehearsal re-run on the repaired code: 217 events, verify ok, decision statuses now ACTIVE 74,
PARTIALLY_SUPERSEDED 7, SUPERSEDED 4, UNCLEAR 7, NOT_OWNER_DECISION 1 (was SUPERSEDED 8 / PARTIALLY 2 before R1-11).
