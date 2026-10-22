# EMBER-V21-INTEG-20261018 - Independent review R1 (read-only subagent)

Reviewed commit: 0533d2a4ecfc6cba3ce41c98f62fe684c0f07208 (HEAD of D:/uri-dev/uri-ember-v21-integ, branch milestone/ember-v21-integ-20261018; HEAD verified). Merge ce972cc2 parents 348677b7 (1st) and d6a83131 (2nd), verified.
Reviewer type: independent Claude subagent, read-only. No tracked file changed (git status after the test run shows only the pre-existing untracked docs/companions/fire/v21_integ/evidence/).

## Verdict: ACCEPT WITH FINDINGS

No HIGH finding. The code merge is correct: auto-merged files match git's own 3-way merge exactly, Ember and canonical deltas both survive, protected paths are untouched, and the targeted tests pass. Two MEDIUM findings need action before integration: one is tree hygiene (reference artwork is in the tree), the other needs an owner ruling (D-1).

## Acceptance criteria used for this review
1. Conflict files: no unintended loss from either parent; Initializing never shown for stop, failure, GPU wait or a stale snapshot; D-1 and EI-1 described accurately.
2. Auto-merged files: Ember hunks (1b5423bc..d6a83131) and canonical hunks (1b5423bc..348677b7) both present in HEAD.
3. Repair: no double dispose, no wrong ordering, no listener leak; no similar leaks elsewhere.
4. Tests: assertions still test the behaviour; no Ember V2.1 coverage lost without notice.
5. Hygiene: excluded material absent; protected and frozen paths unchanged vs 348677b7.
6. Ember works on UI V2: dispatch, installed list, scale, transparency.

## Verified by running commands
- `git rev-parse HEAD` = 0533d2a4; parents of ce972cc2 = 348677b7, d6a83131; 62d564cf is not an ancestor; 348677b7..0533d2a4 adds only ce972cc2, 0533d2a4 and Ember history.
- `git merge-tree --write-tree 348677b7 d6a83131` gives tree d5120561 with conflicts in exactly oi_sources.dart, voice_input_settings.dart and ws_integration_test.dart. `git diff d5120561 ce972cc2`, leaving out the excluded paths, differs only in those 3 files. So every auto-merged file equals git's own auto-merge.
- For companion_preferences.dart, companion_state.dart, companion_settings_section.dart, companion_settings_test.dart, live_voice_test.dart and pubspec.yaml, the set of changed lines in d6a83131..0533d2a4 equals the set in 1b5423bc..348677b7 (sorted -U0 hash). Canonical changes are fully applied on top of Ember. companion_sources.dart differs only by the 0533d2a4 `owned` repair.
- Every other Ember non-doc file changed since 1b5423bc is byte-identical to d6a83131 in HEAD.
- voice_input_settings.dart equals 348677b7 (same post-frame fix on both sides). ws_integration_test.dart is 348677b7 plus Ember's 3 F-SUCCESS tests, with no other change.
- Excluded paths (docs/companions/fire/{reference,v2,evidence}/, v21/evidence/fidelity/, companion_art/fire/): 0 files in the HEAD tree.
- `git diff --stat 348677b7 0533d2a4` over the ws_frozen_check.py PROTECTED list, uri_operational_intelligence/, .gitignore, uri_ui/windows/, scripts/run_uri_*, *.ps1 and *.bat: the only changes are additions under scripts/fire_companion/ and uri_ui/tool/capture/ (Ember tooling, not protected). Protected files are unchanged.
- `flutter test --no-pub` on companion_initializing_test, ws_integration_test, fcv_brain_presentation_test, ui_v2_test, uiv2_postint_test, ember_companion_test, ember_transparency_test, companion_orb_test, companion_settings_test, fcv_context_rail_test and ws_hardening_test: 251 passed, exit 0 (log: ember_review_r1/test_run.log).
- I opened docs/companions/fire/v21/evidence/demos/before_after.jpg (see R1-01) and haze_candidates.jpg (derived atlas frames only).

## Verified by reading only
- The merged _derive rule, brainNotReadyPresentation and brainStartingDetail, traced case by case.
- Composite priority list; the dispose chain LivingServices.dispose (living_scope.dart:231) and working_system_app.dart:161-163 (services disposed before the conversation).
- companion_orb dispatch, CompanionDesign.installed (enum-driven), LivingCompanion scale (presenceScale(ember) = 0.5/0.42 = 1.19; presentationScale 1.85 only for Solar, living_shell.dart:723-728) and the Ember painter blend.

Not verified: full suite, analyze, build, T0-T5 gates and live Windows behaviour. I did not run them. The worktree's untracked evidence logs (full suite +826 ~5 at 0533d2a4; analyze 5 infos, 0 errors) were read but are the author's evidence. None of this changes the code-review verdict. AC-8 to AC-14 remain for the author's qualification.

## Findings

### R1-01 MEDIUM - Reference artwork is in the tree (AC-3, handoff sections 3 and 11, OD-2)
- File: docs/companions/fire/v21/evidence/demos/before_after.jpg (added by 3a09d438, carried into the tree by ce972cc2).
- Scenario: the left column of this image is the original reference paintings in four expressions, with the artist's signature visible in the first panel. The commit message and AC-3 say reference artwork is excluded, and the boundary check only tests path prefixes (fire/reference/), so it misses this. If the tree is integrated or the branch is pushed after OD-2 is resolved for atlases only, unlicensed reference art ships in canonical.
- Fix: remove the file from the tree in a new commit (history stays as OD-2 allows locally), or replace it with a derived-only comparison. Then check every other image under docs/companions/fire/v21/evidence/ (demos/*.gif, final/size_crop.jpg, transparency/*, live/*) for reference content. Add a content check to the boundary script, not only path prefixes. I checked only before_after.jpg and haze_candidates.jpg.

### R1-02 MEDIUM - D-1 reverses Ember owner-decision behaviour without an owner ruling
- Files: uri_ui/lib/living/integration/oi_sources.dart:172-191 (merged rule), :233-236 (FCV-10 WAITING_FOR_LEASE is unavailable); test/living/companion_initializing_test.dart:105-108.
- The description is accurate. FCV-10 maps host WAITING_FOR_LEASE to `unavailable` "Waiting for GPU", so the merged `p.state == working` gate never allows Initializing there. Ember (handoff section 6; brainHostStarting; brainStartingDetail returns 'Waiting for the GPU') wanted the calm look.
- Scenario: a first-time user whose Brain waits for URI's own GPU lease sees the dim unavailable look with the text "Another program is using the GPU memory...". That is the "normal startup read as a fault" case the Ember owner decision addressed. For a lease wait, FCV-10's wording is also arguably inaccurate.
- Keeping canonical FCV-10 is the right default for a candidate, since AC-5 requires it. However, D-1 does not appear in 00_ACCEPTANCE_CRITERIA.md's list of carried owner decisions.
- Fix: add D-1 to the acceptance or receipt document as an owner decision: (a) keep FCV-10, or (b) show WAITING_FOR_LEASE as Initializing with FCV-10 text. Update the oi_sources.dart doc comments (see R1-07).

### R1-03 LOW - EI-1: a failed or stopped Brain can be presented as `working` (pre-existing canonical; regression against Ember's guarantees)
- Files: oi_sources.dart:209-260 (brainNotReadyPresentation ignores snapshot ages and checks host FAILED/STOPPED only through readiness); test/living/companion_initializing_test.dart:213-216, 226-232.
- Scenarios:
  - Newer health has host FAILED (or a running host in STOPPED) with readiness LOADING. The companion shows `working` "Loading model" (Ember: focused clip) instead of unavailable/error.
  - Older health (host STARTING, readiness LOADING) next to a fresh status STOPPED. The companion shows `working` "Starting Brain" for a stopped Brain until the next health refresh.
- Ember V2.1 showed unavailable "Brain FAILED" / "Brain STOPPED" in these cases (R3-01, R5-N2). The merge keeps "never Initializing" but loses "shown as unavailable".
- Both behaviours exist on 348677b7, so this is not a regression against canonical. EI-1 describes them accurately.
- Fix: record EI-1 in the receipt as an open UI V2/FCV-10 finding. Later, apply brainHostNotStarting and the checked_at ordering inside brainNotReadyPresentation.

### R1-04 LOW - The claim "GPU wait never looks like Initializing" is false for one stale-snapshot path
- File: oi_sources.dart:67 (the `newer == false` early return skips the host check) with :231-232 (RELEASE_WAIT is `working` in FCV-10).
- Scenario: health is older than status and reports host RELEASE_WAIT, while the fresh status says LOADING/STARTING. FCV-10 returns working "Waiting for GPU memory", brainStartingDetail returns 'Brain loading', and the result is Initializing with headline "Waiting for GPU memory". Impact is benign, since the Brain has likely moved on, but the commit message and test comments overstate the guarantee.
- Fix: correct the claim, or also require `hostState` not in brainHostNotStarting before the `newer == false` return.

### R1-05 LOW - Composite priority change alters UI V2 behaviour during Brain startup (not recorded against AC-5)
- Files: companion_sources.dart:436-447; intelligence_overview_view.dart:77, 119.
- Scenario: on canonical, Brain startup was `working` (rank 3), which beat thinking, speaking, listening, success and unavailable from other sources. Initializing now ranks 9th, above only idle. While the Brain loads, an active voice session (VoiceCompanionSource listening/speaking), VoiceInteractionController thinking or error, or a demo mock state now hides the FCV-10 "Loading model" headline.
- The Intelligence overview "execution" stage was `active` with the startup detail during Brain load on canonical. It is now idle, "not observed". (Arguably more correct, but it is a UI V2 behaviour change.)
- Fix: record both changes as accepted consequences of the handoff's priority rule (section 6), or rank initializing next to working if FCV-10 visibility must be preserved.

### R1-06 LOW - Repair: correct, but AC-4 wording and remaining unowned constructions
- Files: living_app.dart:168-178; companion_sources.dart:412-475.
- The `owned` disposal is correct:
  - The composite removes its listener from every source first, then disposes the owned source.
  - oiCompanion is referenced nowhere else, so there is no double dispose.
  - LivingServices disposes before OiConversation (working_system_app.dart:161-163), so OiCompanionSource.dispose removes its listener from a live notifier.
  - The cancelled timer cannot fire _update after dispose.
- Issues:
  - (a) living_app.dart is a UI V2-owned file that the handoff does not name. AC-4 allows only the handoff-named design-count edit, so this edit should be recorded as a deviation.
  - (b) test/ws/fcv_context_rail_test.dart:68 and test/ws/ws_hardening_test.dart:480 still construct OiCompanionSource inline in a composite with no owner. A future test that finishes an `ok` turn there fails with a pending 4 s timer.
  - (c) No unit test asserts that the composite disposes owned sources. The only coverage is indirect (uiv2_postint UIV2-F3).
- Other lib constructions (main_v2.dart:73, main_v2_preview.dart:42, office_*_live_check.dart, tool/capture/ui_v2_capture.dart:157) do not use OiCompanionSource, so the Ember timer does not apply to them.
- Fix: record (a); pass `owned:` in the two tests; add a dispose test.

### R1-07 LOW - Dead code and stale comments after the resolution
- oi_sources.dart:9-11: says everything brainStartingDetail rejects "stays `unavailable` with the real state named". This is false now; FCV-10 decides and may return working or error.
- oi_sources.dart:30: brainUnavailableDetail is unused in lib/ and referenced only by tests.
- oi_sources.dart:81: the 'Waiting for the GPU' return can no longer reach the UI (D-1).
- companion_orb.dart:35 and pubspec.yaml:93: say Ember is "rendered in Blender (companion_art/fire/)". V2.1 is painting-derived (companion_art/fire_v2), and companion_art/fire is excluded from the tree.
- Fix: update the comments; remove brainUnavailableDetail or mark it as kept for a future FCV-10 fix (R1-03).

### R1-08 LOW - Test edits: mostly sound, two assertions do not pin the shown state
- File: test/living/companion_initializing_test.dart.
- What holds up:
  - :78-100 compares with brainNotReadyPresentation, which is stronger than before.
  - :216-218 (`working`) and :224 (`idle`) pin concrete states.
- What is weak:
  - :116 (`FAILED` with host STARTING_HOST) and :232 (older health with fresh STOPPED) assert only `isNot(initializing)`, which a regression to `success` or `idle` would also pass.
  - :120-128 now expects `idle` while a streamed brain.status says LOADING and health still says READY. This encodes canonical FCV-R staleness of up to one health interval instead of testing Ember's "event takes the same path".
- Coverage lost from Ember V2.1: the integrated source showing unavailable with the newer failure named (R4-N2/R5-N2) is now tested only on the unused helper.
- Fix: pin `p.state` and `p.headline` at :116 and :232. Keep the brain.status case, but name it as canonical behaviour in the receipt.

### R1-09 LOW - The UI V2 gallery describes Ember wrongly
- File: lib/living/screens/settings/companion_gallery.dart:252.
- Scenario: when Ember is selected, the viewer caption reads "Ember · live procedural 2D renderer". Ember plays pre-rendered painted sprite clips, so this is an inaccurate capability statement.
- rendererReference ('shaders/companion_ember.unused') is not displayed anywhere in lib (grep), so the handoff's rendererReference item is cosmetic only.
- Fix: make the caption depend on `identity.usesShader` (e.g. "animated painted clips").

### R1-10 LOW - V1 history docs kept while V2 history is excluded; dangling links
- Files: docs/companions/fire/00_PLAN_AND_ACCEPTANCE_CRITERIA.md .. 05_LIVE_QUALIFICATION.md, FINAL_QUALIFICATION_REPORT.md, live/.
- Handoff section 3 says to exclude "V1/V2 history docs beyond the qualification record". 01_RESEARCH_AND_APPROACH.md and 04_FIDELITY.md link to the excluded `reference/` paths, so those links are dead in this tree.
- Fix: state which V1 docs count as "the qualification record", or exclude them consistently.

## Answers to the review questions
1. Conflict resolution: no unintended loss.
   - voice_input_settings.dart: identical fix on both sides, so taking canonical is correct.
   - ws_integration_test.dart: canonical plus all 3 Ember tests; the dropped approval test was Ember's copy of the pre-existing test.
   - oi_sources.dart keeps all of Ember's F-SUCCESS logic and helpers, and all of canonical's FCV-10/FCV-R logic.
   - The merged Initializing rule never shows Initializing for stop, failure, FCV-10 GPU wait or a stale STOPPED. The one exception is the benign stale RELEASE_WAIT path (R1-04).
   - Keeping FCV-10 is the right default. D-1 is described correctly but needs an owner ruling (R1-02). EI-1 is described correctly (R1-03).
2. Auto-merged files: verified mechanically. Both sides' hunks survive.
3. Repair: correct. See R1-06 for the AC-4 wording, the remaining test constructions and the missing unit test.
4. Tests: not weakened to pass in general. Two assertions are loose and one Ember behaviour is now only unit-tested on dead code (R1-08).
5. Hygiene: path-based exclusions and protected paths are clean. Reference art is present via before_after.jpg (R1-01).
6. Ember on UI V2:
   - Dispatch happens before shader loading (`usesShader`), and reduced effects falls back.
   - CompanionDesign.installed is enum-driven, giving 12 entries; the pin was updated.
   - Scale is 1.19 with presentationScale 1.
   - The painter cross-fades with BlendMode.plus only inside an isolated saveLayer, which composites source-over onto the destination. No opaque backing was added.
   - No correctness defect found. Live transparency is not verified by this review.
