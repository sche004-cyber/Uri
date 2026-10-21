# EMBER-V21-INTEG-20261018 - Independent review R2 (read-only subagent)

Reviewed commit: d98873faa659e5d19e37517e40ca2ad6a823bc6b. It is HEAD of D:/uri-dev/uri-ember-v21-integ on branch milestone/ember-v21-integ-20261018 (verified). The worktree is clean: `git status --porcelain` shows only ignored build files.
Code candidate: 6bdaf86e (tree f61d9581, verified). Prior round: R1 at 0533d2a4.
Reviewer type: independent Claude subagent, read-only. I changed no tracked file, did not launch the app and did not use the GPU. Scratch files are in ember_review_r2/ (test_run.log, scripts/).

## Verdict: ACCEPT WITH FINDINGS

- No HIGH finding.
- The code repairs in 6bdaf86e are correct and introduce no new defect.
- The live evidence supports the AC-10..AC-14 PASS claims. My own pixel analysis independently confirms per-pixel alpha.
- One MEDIUM documentation-integrity finding (R2-01): the receipt's 1.25x numbers do not come from the run it cites. Repair it in the receipt before integration. It does not change any PASS: the same code passes in l2, l5 and l6.
- Six LOW findings: incomplete R1 repairs not recorded, two harness weak spots, and three disclosure/attribution gaps.

## Acceptance criteria used for this review
1. Every R1 finding is either repaired correctly or recorded/escalated, and the repairs add no new defect.
2. Every PASS or number in 01_QUALIFICATION_RECEIPT.md is supported by the evidence file it cites, and that file shows the check finished with a recorded result (COMPLETED_WITH_RESULT). The live runs ran on 6bdaf86e, and later commits change docs only.
3. The harness measures what the criteria say: per-pixel alpha, borderless, click-through, drag. No check can pass falsely in the evidence used, and the correction history is honest and preserved.
4. The table in 00_ACCEPTANCE_CRITERIA.md is unchanged; only D-1 text was added.
5. Hygiene: excluded paths are absent, there is no reference art, the added logs contain no secrets, and protected paths are unchanged vs 348677b7.

## Verified by running
- **HEAD and commit contents.** `git rev-parse HEAD` = d98873fa, and `6bdaf86e^{tree}` = f61d9581.
  - `git diff --name-only 6bdaf86e d98873fa` contains only paths under docs/companions/fire/v21_integ/.
  - 0533d2a4..6bdaf86e changes only oi_sources.dart, companion_gallery.dart, companion_initializing_test.dart, the acceptance file, and removals (V1 docs and before_after.jpg).
- **Targeted tests.** `flutter test --no-pub` on companion_initializing_test, ui_v2_test, ws_integration_test and uiv2_postint_test: 100 passed, rc 0. This includes the new owned-dispose test and the pinned R1-04/R1-08 assertions.
- **Acceptance criteria file history.**
  - The file was first committed in 0533d2a4 (09:00), before the live runs (10:05+).
  - 0533d2a4..6bdaf86e adds 2 lines (D-1 for ruling). 6bdaf86e..d98873fa adds 4 lines (D-1 APPROVED).
  - The criteria table is byte-unchanged.
- **Protected paths.** I evaluated the ws_frozen_check.py PROTECTED tuple against `git diff --name-only 348677b7 d98873fa`: empty.
  - uri_operational_intelligence/, .gitignore, uri_ui/windows/ and scripts/run_uri_* are unchanged.
  - The only *.ps1 additions are uri_ui/tool/capture/run_ember_perf*.ps1, which is Ember tooling (as in R1).
- **Excluded material and reference art.**
  - 0 tree paths under fire/{reference,v2,evidence}, v21/evidence/fidelity or companion_art/fire/.
  - 0 blobs shared between HEAD's tree and d6a83131:docs/companions/fire/reference (15 blobs).
  - I opened v21/evidence/final/size_crop.jpg: derived app renders only, no signature.
- **Secrets.** I grepped every added non-image evidence file for key, token, password, bearer, sk-, ghp_, AKIA, pairing and auth values. No hits, apart from one test file name in the runtime receipt.
- **Live run provenance.**
  - All six native-execution.json files have source_head 6bdaf86e, tree f61d9581 and rc 0.
  - For l1 and l6, session-start/final show `verified.ok`, 354 files, mismatched [].
  - Brain config sha e7d5de94 is the same before and after, override false, and the lease is FREE before and after.
  - The committed harness/ember_live_driver.dart sha256 (9de00bf3) equals the driver sha of l4-l6.
- **Evidence checks against receipt claims.**
  - full_flutter_test_6bdaf86e.log: header HEAD=6bdaf86e, tail "+827 ~5: All tests passed!", rc=0, 0 `[E]`.
  - analyze_6bdaf86e.log: 5 infos, 0 errors.
  - ws_frozen_check.txt: identical output for 6bdaf86e and 348677b7.
  - full_flutter_test.log: exactly 4 `[E]` (2 companion_initializing, 2 uiv2_postint UIV2-F3).
  - tgates/transparency_gates.json `clips` equals v21/evidence/final/transparency/transparency_gates.json. Only T4 depleted fails (fringe 14).
  - l1 observations and timeline: unavailable "Brain not running", then initializing "Loading model", then idle at READY. Turns are ok with states [thinking, speaking, success], replies "Hello there, friend!" and "15". J3 shows unavailable and no Initializing. J4 shows Initializing during restart. J5 stored "ember".
  - brain-ready.json: decode_tps 155.7, load_s 56.69.
  - resource-samples: uri_ui.exe dedicated median 172.7 MiB (l1) and 179.0 MiB (l6); adapter max 15765 MiB.
  - l6 observations: all checks PASS, failures [], chat_control_visible true after the Ember click.
  - l6 probe-*.done.json: borderless true (client = window 440x680, shadow frame 0). Transparent-1.0: 0.9083 / 0.0714 / 0.0203, edge max 0. Click-through: backdrop clicks [0,1,1], root at Ember = companion. Drag: delta [0,57].
- **Independent alpha cross-check (my own script).** I recovered alpha a second way, from the black/white pair, and compared it with the probe's magenta/green alpha.
  - transparent-1.0 and 1.25 (l6, l2): |diff| max 0 over all 299,200 pixels, and all intermediate-alpha pixels agree. The blended pixels are real per-pixel alpha, not motion or capture noise.
  - Pixels with alpha <= 5 equal the backdrop within 5/255 on all four backdrops.
  - Outside a ~170x220 box around Ember, all four captures are exactly the backdrop, so there is no box, matte or fringe. This also holds for the animated `returning` capture.
  - No transparent pixel touches a pixel with alpha >= 80, so the window region does not hard-cut the silhouette at 1.0 or 1.25.
- **Input diagnosis (l3/l4).** l3: 0 Flutter pointer events, no backdrop click, window not moved. l4: 8 events, chat controls visible, window moved.

## Verified by reading only
- The R1-04 condition and its interaction with FCV-10, traced case by case.
- The owned-dispose test semantics.
- The gallery caption branch.
- harness/win_probe.py, ember_live_driver.dart, run_live_ui.py and go.sh.
- uri_ui/windows/runner/flutter_window.cpp region code (canonical, unchanged).

Not verified:
- The Windows release build at 6bdaf86e (see R2-07).
- The claim that uiv2_postint passes on clean 348677b7 (21/21): no evidence file is cited.
- The SHA of full_flutter_test.log, which has no HEAD header.

None of these changes the verdict.

## 1. R1 findings - disposition

| R1 | Disposition | Assessment |
|---|---|---|
| R1-01 reference art | before_after.jpg removed | Correct. No reference blob in the tree. |
| R1-02 D-1 | Recorded; owner APPROVED | Correct. The criteria table is unchanged. |
| R1-03 EI-1 | Recorded in receipt sections 4 and 7 | Correct. The description is accurate. |
| R1-04 stale RELEASE_WAIT | `!brainHostNotStarting.contains(hostState)` added before brainStartingDetail; test pins working "Waiting for GPU memory" | Correct. hostState uses the same `running == true` gate as FCV-10. For host FAILED/STOPPED with readiness LOADING (EI-1), the result stays FCV-10's `working`, which is no regression. No new defect. |
| R1-05 priority | Recorded in section 7 | Correct. |
| R1-06 owned disposal | (a) recorded in section 5; (c) unit test added and passing | Partly done: (b) is not done and not recorded. See R2-02. |
| R1-07 stale comments | Header fixed; "kept as tested rules" note added | Partly done: companion_orb.dart:35 and pubspec.yaml:93 still say "rendered in Blender (companion_art/fire/)". See R2-02. |
| R1-08 loose asserts | :116 and :232 now pin state and headline | Correct. The brain.status idle case is covered by EI-1's wording. |
| R1-09 gallery caption | Caption branches on CompanionIdentity.ember | Correct. Non-Ember designs are unchanged. No test pins the caption (minor). |
| R1-10 V1 docs | Removed (docs/companions/fire/00-05, FINAL_QUALIFICATION_REPORT.md, live/) | Correct. |

## Findings

### R2-01 MEDIUM - The receipt's 1.25x figures come from l2/l5, not from the cited final run l6
- Location: 01_QUALIFICATION_RECEIPT.md:61 (AC-13 row), citing `probe-transparent-1.25.done.json`, in a section that names l6-returning as the final window run.
- What the receipt states: 1.25x "87.8 % / 9.3 % blended" and "silhouette inside the window (bbox 142-319 x 155-354)".
- Those values are in l2-returning and l5-returning (0.8779 / 0.093, bbox [142,155,319,354]).
- What l6 actually shows: live/l6-returning/probe-transparent-1.25.done.json has 0.8756 / 0.0705 / 0.0539 opaque, bbox [21,91,418,353], transparent_frac_inside_bbox 0.64.
  - In l6 the 1.25x probe runs after the successful Ember click, so the Chat and Dashboard controls are on screen (win-transparent-1_25-black.png).
  - The l6 F-SIZE-1 "crop" measurement therefore measures Ember plus the controls, not Ember.
- Failure scenario: an auditor opening the cited file finds numbers that contradict the receipt. The l6 F-SIZE-1 record (observations-returning.json "F-SIZE-1 measurement") is not a measurement of the silhouette.
- The PASS itself holds:
  - l6 at 1.25x is per_pixel_transparent true.
  - The l2/l5 1.25x captures completed with a result, and my black/white cross-check confirms them.
- Fix:
  - Cite `live/l2-returning/` (or l5) for the 1.25x silhouette numbers. State that the l6 1.25x capture includes the controls, so its bbox is not the F-SIZE-1 measurement.
  - In the driver, take the 1.25x capture before the Ember click, or hide the controls first.

### R2-02 LOW - Two R1 items are only partly repaired, and the receipt says they were repaired
- Receipt section 6 says R1 was "repaired in 6bdaf86e except R1-02 ... and recorded items R1-03, R1-05". Two items are neither repaired nor recorded:
  - **R1-06(b).** test/ws/fcv_context_rail_test.dart:68 and test/ws/ws_hardening_test.dart:480 still build `CompositeCompanionSource([... OiCompanionSource(conv) ...])` with no `owned:`. A future test there that finishes an `ok` turn leaks the 4 s success timer, as UIV2-F3 did.
  - **R1-07.** uri_ui/lib/living/companion/companion_orb.dart:35 and uri_ui/pubspec.yaml:93 still say Ember is rendered in Blender from companion_art/fire. That folder is excluded from the tree, and V2.1 is painting-derived (companion_art/fire_v2).
- Fix: pass `owned:` in those two tests and correct the two comments. Alternatively, list both as open LOW items in receipt section 7.

### R2-03 LOW - The harness gate "Ember click reaches URI" can pass when Flutter received nothing
- Location: harness/win_probe.py:288-289 (`ember_click_reached_uri = n2 == n1 and root_at_ember == hwnd`); ember_live_driver.dart:165-169, where `chat_control_visible` is recorded but not part of the check.
- Failure scenario: in l3-input, Flutter received 0 pointer events, the backdrop got no click and the root under the point was the companion. By the l6 criterion that is a PASS, even though the click reached no Flutter code.
- In l6 the claim is still true, because the recorded chat_control_visible is true and the receipt cites the observations.
- Fix: make W-click-on-ember-reaches-uri also require `chat_control_visible == true`, or a logged Flutter pointer event.

### R2-04 LOW - The per-pixel transparency gate does not check that the frame was stable, and its thresholds are loose
- Location: harness/win_probe.py:231-235.
- `ok` uses only the magenta/green recovery, with thresholds transparent >= 20 %, opaque >= 0.5 %, blended >= 0.2 % and edge alpha <= 12.
- Failure scenario: if Ember animates between captures, motion produces intermediate "alpha" even for a binary (region-clipped) window, and the gate still passes.
  - This is shown by the `returning` probe, which is taken before reduced motion is set. It reports per_pixel_transparent true, but its black/white alpha disagrees with magenta/green by up to 156/255, and 4.6 % of its intermediate pixels are inconsistent.
  - The thresholds would also accept a uniform tint of up to about 2 % (or 4.7 % at the edges).
- The AC-11 evidence is not affected: transparent-1.0 and 1.25 were taken with reduced motion, and the two recoveries agree exactly.
- Fix:
  - Add the black/white recovery and require |alpha_mg - alpha_bw| <= a small tolerance. This gives frame stability and a second measurement.
  - Tighten the transparency threshold to "backdrop unchanged within 1-2/255", which matches AC-11's wording.

### R2-05 LOW - The receipt omits reduced motion and the window region when describing AC-11
- The driver sets `services.effects.setReducedMotion(true)` before every window check (ember_live_driver.dart:158). AC-11 PASS is therefore measured on the reduced-motion still frame, not on the animated clip path (the saveLayer/plus cross-fade).
  - The animated `returning` capture shows no box or matte outside the silhouette (I checked), but its alpha values are not a valid measurement (R2-04).
- Every probe reports `region_kind: COMPLEXREGION`. The canonical runner applies an elliptical orb + controls window region (flutter_window.cpp:96-138), so the transparency outside the orb region is region clipping.
  - The receipt's wording "7.1 % blended (intermediate alpha, not region clipping)" is true for the blended pixels only.
  - The click-through outside is the canonical hit region working as designed.
- Fix: in the receipt, state that the window checks used reduced motion, and that the window carries the canonical complex hit region. Per-pixel alpha is proven inside that region; the animated path is checked for "no matte" only.

### R2-06 LOW - Correction history item 3 misattributes the l2 Ember-click failure
- Location: receipt section 3.2 item 3; live/l2-returning/probe-click-through.done.json.
- In l2, `backdrop_clicks` went [0,1,2]: the click aimed at Ember went to the backdrop window, which was raised above the companion after the first click. That is the l5 mechanism (item 4), not dropped device events.
- Dropped device events (l3) explain the l2 drag failure, not the click.
- Fix: correct item 3 so that only the drag is attributed to dropped device events, and add that the l2 click had the same cause as the l5 click. Keep the original text as history if desired.

### R2-07 LOW - Provenance gaps in the receipt's gate table and harness
- **Release build.** The Windows release build logs (evidence/build_windows_release_*.log) are at HEAD=0533d2a4, not at the code candidate. 0533d2a4..6bdaf86e changes two lib files.
  - The debug build compiled 6bdaf86e for the live runs (rc 0), so compilation is shown.
  - The receipt's AC-9 row names no SHA.
- **Boundary check.** boundary_check.txt was run at ce972cc2. I re-verified the boundary at d98873fa (clean).
- **Full-suite log at the merge.** full_flutter_test.log carries no HEAD line.
- **Probe versions.** win_probe.py has no hash recorded per run. The committed version matches only by the stderr line numbers (149/161) seen in l1 probe2 and l6. The l1 driver (sha efbaf913) that produced the J0-J5 journey evidence is not preserved in the tree.
- **Runner status check.** run_live_ui.py records `git status --untracked-files=no`, so an untracked lib file present during a run would go unrecorded. The tree is clean now.
- **Memory headroom.** The receipt omits that brain-ready.json reports GPU fit `AT_RISK` (margin -210 MiB, 1.73 GiB non-local residency) with the Ember window open. Calibration still passed at 155.7 tok/s. This is a pre-existing canonical runtime condition, but it belongs in the performance row.
- Fix:
  - Name the SHA for every gate row, and re-run the release build at 6bdaf86e (or record it at 0533d2a4).
  - Record the win_probe sha256 in native-execution.json, and keep the l1 driver or record its diff.
  - Add the AT_RISK fit verdict to the performance row.

## Answers to the review questions
1. **R1 repairs.** R1-01, 04, 08, 09 and 10 are repaired correctly. R1-02 is owner-approved and recorded, and R1-03 and R1-05 are recorded. R1-06(b) and part of R1-07 are not done and not recorded (R2-02). The repairs introduce no new defect.
2. **Receipt integrity.**
   - All PASS claims are backed by COMPLETED_WITH_RESULT evidence from 6bdaf86e: the full suite (827/5/0), analyze, T-gates, ws_frozen_check, l1 journeys and l6 window checks.
   - The 1.25x figures are cited from the wrong run (R2-01). Attribution and SHA gaps: R2-06, R2-07.
   - The live runs ran on 6bdaf86e, and d98873fa changes docs only.
3. **Harness validity.**
   - The magenta/green alpha recovery is mathematically sound (|C_m - C_g| = (1-a)*255 per channel). With reduced motion it is exact, and the black/white pair confirms it.
   - The borderless check by rendered result (client = window, DWM frame = window rect) is sound.
   - Click-through via an OS click, a backdrop click counter and WindowFromPoint is sound.
   - Drag is app-driven: it did not move without Flutter events in l3.
   - Remaining false-pass paths: the Ember-click gate (R2-03) and the frame-stability check (R2-04).
   - The correction history is honest. Attempt-1 evidence is preserved (probe_attempt1_INVALID_occluded/, and the l1 observations keep the FAILs), and HARN-1 discloses the stray click and drag. One attribution is wrong (R2-06).
4. **Acceptance criteria.** Unchanged; only the D-1 lines were added.
5. **Hygiene.** It holds: excluded paths are absent, there is no reference blob, there are no secrets, and protected paths are unchanged vs 348677b7.

Subagent acceptance is not owner approval and is not lifecycle (driver-counted) acceptance.
