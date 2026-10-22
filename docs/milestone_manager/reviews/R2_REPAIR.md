# Repair of review R2 findings (2026-10-21)

Pre-repair candidate `4a54ebe1`. All 14 findings and the 4 partial R1 repairs were accepted as valid; none disputed.
Regression proof: the new `test_r2_*` tests run against the pre-repair code in a separate detached worktree
(`4a54ebe1` + new test file): **16 failed, 0 passed**. After repair the whole MM file passes: 93 passed.

| Finding | Repair | Test(s) |
|---|---|---|
| R2-01 HIGH resolve bound to another host's record | resolve/supersede/correct events carry `target` (creation-event hash); fold `_find` binds by hash; DUPLICATE_ID conflicts carry both `subjects`; `CONFLICT_OPEN` guard and RED indicator use them | `test_r2_01_*` |
| R2-02 anchors replace failed under a reader | `atomic_write_bytes` retries `PermissionError` with backoff; anchor refresh failure after the append is a warning in the result (`warnings`), never a failed write | `test_r2_02_*` (2; one Windows-only) |
| R2-03 missing/corrupt anchors disabled detection | missing/unreadable anchors while events exist = integrity error; `reanchor --reason` appends `ANCHORS_RESET` and re-bases | `test_r2_03_*` |
| R2-04 tracked anchors/host id broke multi-host git use | `local/host.json` + `local/anchors.json`, `.gitignore` ignores `local/`; `init-host` for clones refuses an existing segment name and adopts verified anchors; autocommit adds only `events/`, `mm.json`, `.gitignore`; architecture claim corrected, second-host procedure documented | `test_r2_04_*` |
| R2-05 resolution covered later-arriving conflicts | `CONFLICT_RESOLVED.conflicts` lists the conflict event hashes seen; fold resolves only those | `test_r2_05_*` |
| R2-06 clock step-back reordered a segment | append clamps `ts` to ≥ the segment's last event; `ordered()` is a heap merge that never reorders within a segment; acceptance rule no longer clock-ordered: any completed negative review on the candidate blocks (`NEGATIVE_REVIEW`) | `test_r2_06_*`, updated `test_f7_*`, `test_r1_03_*` |
| R2-07 DEC id collision with future register rows | ledger-native ids `LDEC-NNN` (config `dec_namespace`, `DEC` only after promotion); explicit `DEC-` refused (`DEC_NAMESPACE`); importer reports `collisions` and writes nothing for them; CLI exit 1 `ID_COLLISION`; rehearsal uses LDEC-001..003 | `test_r2_07_*`, `test_f10_*` |
| R2-08 approval not bound to commit | INTEGRATION request requires and records the candidate commit; INTEGRATED guard requires `approval.commit == candidate_commit` | `test_r2_08_*` |
| R2-09 DEC-030 full links | links from a row whose own status is PARTIALLY_SUPERSEDED or UNCLEAR are partial; real-file assertion for DEC-030 | `test_r2_09_*` |
| R2-10 stale plan figures | plan §2/§3 figures labelled with the commit they were measured on; "accepted candidate" wording removed | doc |
| R2-11 stale docstring | service docstring describes the verified fold | source |
| R2-12 `log` without integrity | `log` includes `integrity_errors` and exits 3 | `test_r2_12_*` |
| R2-13 false positives | numeric values and state words exempt | `test_r2_13_*` (4) |
| R2-14 permanent warning | `recover` appends `BATCH_ABANDONED` for pending batches; warning cleared, batch stays unapplied | `test_r2_14_*` |

Other evidence recorded with this repair:
- Full `tests/dev_workflow` (N5) at `7ab9263c` completed: 365 passed, 5 skipped (Linux-only, platform-gated), 0 failed
  in 31 min (`evidence/devworkflow_7ab9263c.log`). A re-run on the R2 repair commit is started (see handoff).
- `scripts/ws_frozen_check.py` on the R2 repair tree: exit 0, `unapproved_drift: []`.
- Lifecycle V3.1 contract check against real V3.1 output (`5ee7e5c7`): compatible (`evidence/v31_contract_check_5ee7e5c7.txt`).
- Rehearsal re-run: 217 events, verify ok.
