# Repair of review R3 findings (2026-10-21)

Pre-repair candidate `5bce5bdf`. All 8 findings accepted; none disputed. Regression proof: `test_r3_*` against the
pre-repair code in a detached worktree (`5bce5bdf` + new test file): **8 failed, 0 passed**. After repair: 101 passed.

| Finding | Repair | Test |
|---|---|---|
| R3-01 | `reanchor` computes the loss against the previous anchors (shorter or different segment, or unknown history) and refuses with `LOSS_NOT_ACKNOWLEDGED` unless `--acknowledge-loss`; the event records `lost`/`unknown_previous`; the fold opens an ANCHOR_LOSS conflict (entity LEDGER) that turns every milestone RED and blocks ACCEPTED/INTEGRATED/DONE until `resolve-conflict LEDGER`; anchors lacking this machine's own non-empty segment = integrity error | `test_r3_01_*` (2), updated `test_r2_03_*` |
| R3-02 | creation events in a batch register `batch_keys`; references may target `"BATCH"`; `record_decision --supersedes` uses it; `superseded_by.by` and `supersedes.id` store the actual keys; UNBOUND_REFERENCE for decision links and corrections; importer links carry `target`/`by_target` | `test_r3_02_*` |
| R3-03 | `source.register` (file name) identifies the source; collision only when the existing record is not imported or comes from another register | `test_r3_03_*` |
| R3-04 | `_write` passes a Lamport floor (newest `ts` among all verified events read) to `append_many`; a clock behind that floor is reported in `warnings` | `test_r3_04_*` |
| R3-05 | anchors read before segments in `projection`, `_write`, `verify`; `read_anchors` retries `PermissionError` | `test_r3_05_*` |
| R3-06 | `abandoned_ids` set; batch events whose id is abandoned are dropped in any order; `recover` reports only batches still pending | `test_r3_06_*` |
| R3-07 | numeric exemption only for `token`/`secret` values of ≤ 7 digits | `test_r3_07_*` |
| R3-08 | architecture wording and size figures corrected; `latest_review_on_candidate` removed | doc/source |

Performance re-measured on the repaired code (10,001 events, 4.43 MB, same machine while the full regression suite
was also running): rebuild median 0.220 s; `status_lines` 0.231 s; `status_json` 0.215 s (in-process, incl. fold);
CLI `status` 0.418 s and `status --json` 0.412 s wall incl. process start. Script: session scratchpad `perf.py`
(5/3 samples).
