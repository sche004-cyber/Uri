# EMBER-V21-INTEG-20261018 - Independent review R3 (focused, read-only subagent)

Reviewed: HEAD 4053bf69e7a751be8d4edaf8672fe59cd96f604b (verified), worktree clean. Scope: R2 repairs d98873fa..4053bf69 only.
No file edited, no app launched, no GPU used.

## Verdict: ACCEPT WITH FINDINGS (0 HIGH, 0 MEDIUM, 3 LOW)

## Acceptance criteria
1. 6bdaf86e..67d61d3a changes only comments in uri_ui; d98873fa..4053bf69 adds no other code.
2. Each R2-01..R2-07 is corrected accurately or recorded honestly in 01_QUALIFICATION_RECEIPT.md.
3. Every newly cited evidence file exists, has the stated HEAD header and rc, and contains the numbers the receipt quotes.
4. No remaining overstated or contradictory claim in the receipt.

## 1. Code diff (criterion 1) - MET
- `git diff 6bdaf86e 67d61d3a --stat -- uri_ui`: only companion_orb.dart (2 lines, inside a `///` doc comment on enum value `ember`) and pubspec.yaml (1 `#` comment line above the unchanged `assets/companions/ember/` entry). No behavioural effect.
- Full `git diff 6bdaf86e 67d61d3a` also contains d98873fa's docs/evidence (318 files); every non-uri_ui path is under docs/companions/fire/v21_integ/.
- d98873fa..4053bf69 uri_ui stat equals the same two files; all other paths are receipt, review reports and evidence logs.
- New comment names `companion_art/fire_v2/`, which exists in the tree; `companion_art/fire/` has 0 tree files.
- Boundary at 4053bf69 vs 348677b7: no change under uri_operational_intelligence/, scripts/run_uri_*, .gitignore, ws_frozen_check.py, uri_ui/windows/; only .ps1 additions are uri_ui/tool/capture/run_ember_perf*.ps1 (as before).

## 2. R2 dispositions and cited evidence (criteria 2, 3)

| R2 | Receipt change | Evidence check | Assessment |
|---|---|---|---|
| R2-01 MEDIUM | AC-13 row: l6 1.25x = 87.6 / 7.1 / 5.4 %, bbox [21,91,418,353], taken after the Ember click, not an Ember-only measurement; Ember-only 1.25x from l2/l5: bbox 142-319 x 155-354, 87.8 / 9.3 % | l6 probe-transparent-1.25.done.json: 0.8756 / 0.0705 / 0.0539, bbox [21,91,418,353], per_pixel_transparent true, utc 04:53:38 after click-through 04:53:20 (ember_click_reached_uri true; chat_control_visible true). l5 file: 0.8779 / 0.093 / 0.0291, bbox [142,155,319,354]; l2 identical. l2/l5 chat_control_visible false (controls closed) | Corrected accurately (7.05 % shown as 7.1 is acceptable rounding) |
| R2-02 LOW | Comments fixed in 67d61d3a; R1-06(b) tests recorded in section 7 ("R2-02 tests") | diff above | Corrected / recorded. See R3-01 for the stale R1 row |
| R2-03 LOW | HARN-2 | n/a | Recorded honestly |
| R2-04 LOW | HARN-2 | n/a | Recorded honestly |
| R2-05 LOW | AC-11 row now states COMPLEXREGION region clipping, reduced-motion still frames, animated clips not alpha-measured | probes report region_kind COMPLEXREGION | Corrected accurately |
| R2-06 LOW | Item 3 now attributes only the l2 drag to dropped device events; l2 click same cause as l5; original kept as history note | l2 probe-click-through backdrop_clicks [0,1,2], ember_click_reached_uri false | Corrected accurately |
| R2-07 LOW | Gate rows name SHAs; release build and analyze/full suite re-run at 67d61d3a; merge-log missing header disclosed; boundary attributed to ce972cc2 + R2 re-check; AT_RISK added; probe hash / l1 driver in HARN-2 | see below | Mostly corrected; see R3-02, R3-03 |

Newly cited evidence:
- evidence/analyze_67d61d3a.log: `HEAD=67d61d3a`, 5 info, 0 errors, rc=1 - matches.
- evidence/full_flutter_test_67d61d3a.log: `HEAD=67d61d3a`, final "+827 ~5: All tests passed!", rc=0, 0 `[E]` - matches 827/5/0.
- evidence/build_windows_release_main_67d61d3a.log: `HEAD=67d61d3a`, built Release uri_ui.exe, rc=0 - matches. Old log header HEAD=0533d2a4 - matches "rc 0 at 0533d2a4".
- evidence/baseline_348677b7_uiv2_postint.log: `HEAD=348677b7 (clean canonical baseline worktree)`, run from D:/uri-dev/uri-ember-baseline-348677b7, "+21: All tests passed!", rc=0 - matches 21/21.
- live/l1-first/brain-ready.json: host.gpu.fit.verdict AT_RISK, margin_mib -210.4, override null, calibration decode_tps 155.7 (threshold 60), state READY, explain "Brain ready (156 tok/s)" - matches except the word "healthy" (R3-02).

## 3. Findings

### R3-01 LOW - Section 6 R1 row still says R1 was repaired in 6bdaf86e with only R1-02/03/05 excepted
- Location: 01_QUALIFICATION_RECEIPT.md:111.
- R2-02 showed R1-06(b) and part of R1-07 were not done in 6bdaf86e. They are now handled (R1-07 comments in 67d61d3a, R1-06(b) recorded in section 7), but the R1 row was not updated and still reads as if 6bdaf86e completed them. The R2 row partly compensates.
- Fix: "repaired in 6bdaf86e (R1-07 remainder in 67d61d3a) except R1-02 ..., recorded R1-03, R1-05, R1-06(b) (section 7)".

### R3-02 LOW - Performance row: "calibration classified it healthy" is not literal evidence, and the post-load AT_RISK residency is omitted
- Location: 01_QUALIFICATION_RECEIPT.md performance row (section 3.1).
- brain-ready.json has no "healthy" classification. It shows calibration 155.7 tok/s vs threshold 60 and READY "Brain ready (156 tok/s)". The calibration residency sample after load still reports verdict_now AT_RISK, with non_local_mib 1730.1 (R2-07 mentioned the 1.73 GiB non-local residency).
- Effect: none on any PASS; wording only.
- Fix: "calibration passed (155.7 tok/s vs 60 threshold, READY); post-load residency still AT_RISK, 1.73 GiB non-local".

### R3-03 LOW - One R2-07 sub-item is neither corrected nor recorded
- R2-07 also said run_live_ui.py records `git status --untracked-files=no`, so an untracked lib file during a run would not be recorded. The R2 row says R2-07 was "corrected", but this item appears nowhere in the receipt (HARN-2 lists only probe hash and l1 driver).
- Effect: none on the verdict (runtime files are re-verified byte-identical per run; tree clean now).
- Fix: add it to HARN-2.

## 4. Other checks (criterion 4)
- No contradiction found between the gate table, section 1 commit list, the live table and the correction history.
- Header "Independent review pending re-review at the exact receipt commit" is consistent with this R3 round.
- The claim that the merge-time log ran on ce972cc2 plus the uncommitted 11->12 pin edit cannot be verified from the log (no header), and the receipt says so; it is consistent with the 4 failures listed (no ui_v2 design-count failure). Does not affect the verdict.

Subagent acceptance is not owner approval and not driver-counted lifecycle acceptance.
