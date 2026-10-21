# P0 audit 2026-10-21 - UI and companions evidence (scope 20)

Auditor: read-only subagent. Repository state was inspected without checkout, using `git show`, `git log`,
`git merge-base --is-ancestor`, `git diff` and `git merge-tree --write-tree` in `D:/uri-dev/uri-p0-audit`, plus a
read-only `git ls-remote uri-repo`. I ran no test suite, built nothing, started no app and did not use the GPU. The only
file written is this one.

`git ls-remote uri-repo` (80 refs, 2026-10-21) shows:
- **Canonical** `refs/heads/integration/git-sync-20261008` = `ec2fab5493578a4f5a805642153d56b4d5ea59fa`
- `refs/tags/accepted/ui-v2-freeze-20261017` = tag object `c5c84c08`, which points to `7893aaed`

No Ember or UI-controls ref exists on `uri-repo`, and no remote-tracking ref contains `8a1438ec` (the first Ember art
commit).

Evidence classes used below:
- **VERIFIED**: I checked it myself in git objects in this audit.
- **RECORDED**: a committed record states it. I did not re-run it.
- **REPORTED**: it comes from assistant memory or Antigravity notes. It is historical and was not checked against
  primary evidence.
- **UNKNOWN**: no evidence was found.

## (a) Acceptance criteria used

| ID | Criterion |
|---|---|
| AC1 | Each status separates implemented, tested, reviewed, live-verified, integrated (an ancestor of `ec2fab54`) and frozen. Each one is backed by a named record path and a SHA. |
| AC2 | A test count is used only when a log at a named HEAD shows it. Counts were checked against raw logs where I could do so cheaply. |
| AC3 | A review verdict is cited with its report path and the commit reviewed. It is never treated as owner approval or as driver-counted acceptance. |
| AC4 | The candidate content that reviews and live runs covered is compared byte-for-byte (by tree or diff) with the candidate tip. |
| AC5 | Impact on frozen files is checked against both the UI V2 freeze scope (shell, navigation, companions, settings, Brain wiring) and the protected or Runtime paths (`ws_frozen_check`, `model_lab`). |
| AC6 | Conflicts between candidates are checked with `git merge-tree --write-tree`. |
| AC7 | Each Antigravity claim is classed CONFIRMED, REFUTED, PARTIAL or UNVERIFIABLE, and each class cites evidence. |
| AC8 | Where evidence is missing, the report says so and says whether it affects the verdict. |

## (b) Capability table

### UIC-01: UI V2 desktop shell, the frozen milestone

- **Capability:** the UI V2 desktop shell: navigation, themes, companions, settings, conversation, approvals and Documents.
- **Objective:** UI V2 is qualified and frozen.
- **Location:** `uri_ui/` (frozen tree `3787090c`, `uri_ui` tree `ca6005bd`).
- **Branch@commit:** canonical `7893aaed`. VERIFIED: it is an ancestor of `ec2fab54`, and the tag object `c5c84c08` is on `uri-repo`.
- **Tests (RECORDED in the freeze receipt):**
  - On `7893aaed`: Flutter 758 passed, analyze 0 errors, Python 4597, scope tests 15/15 (`evidence_freeze_20261017/scope_7893aaed.log`).
  - Earlier: 738 on `25048709`; 636 post-integration on `2eff03d0`.
- **Review verdict:**
  - Codex ACCEPT on `25048709` (UI-V2-POSTINT-c6, driver).
  - Office review S2 ACCEPT WITH FINDINGS on `7893aaed`.
  - Sources: the freeze receipt `receipts/ui-v2-20261016@595c1a04:docs/ui_v2/postint/integration/FREEZE_RECEIPT_UI-V2_20261017.json`, and the tag message.
- **Live verification (RECORDED):**
  - pf1 main journey 68/68 on `7893aaed`, 2026-10-17.
  - Returning 12/12 and perf 3/3 were reused from `25048709` (pi5, pi6).
  - All of these ran under the owner's GPU override, with the frozen Brain and automation input only.
- **Canonical status:** FROZEN at `7893aaed`. INTEGRATED.
  - Canonical has since moved to `ec2fab54`, so canonical is no longer byte-identical to the freeze. See UIC-03.
  - No re-freeze receipt exists for `ec2fab54`.
- **Limitations:**
  - The Brain is over its GPU budget on this desktop (the live passes depended on the override).
  - Physical keyboard, mouse and microphone input are not qualified.
- **Remaining work:**
  - UIV2-F5 visual fidelity.
  - DRV-4.
  - An RenderFlex overflow at `oi_health_widgets.dart:94`. It was seen in UI V2 runs l11/l13 and in Ember run c-uiv2.
- **Dependencies:** Runtime v1 (frozen).
- **Next action:** after the next UI integration, re-verify, or issue a delta receipt for the canonical tip.

### UIC-02: finding DRV-3 (Flutter gates that ran no tests)

- **Capability:** the lifecycle driver's Flutter gates.
- **Objective:** a gate must fail closed when no test actually runs.
- **Defect:** the driver passed Flutter gates vacuously. It ran `--no-pub` in a fresh worktree, so the baseline and the candidate failed identically and the identical failure was treated as "historical".
- **Location of the record:** `receipts/ui-v2-20261016:docs/ui_v2/completion/integration/FINDINGS_REGISTER_UI-V2_20261016.json` (DRV-3) and `.../INTEGRATION_RECEIPT_UI-V2_20261016.json:61`.
- **Repair branch:** DEV-LIFECYCLE-3B. Final `b0ca30e5`, integrated at `57f2d567`. VERIFIED: both are ancestors of `ec2fab54`.
- **Tests (RECORDED):** the plan `docs/dev_workflow/DEV_LIFECYCLE_3B_PLAN_AND_ACCEPTANCE.md` holds AC-1, which reproduces DRV-3.
- **Review verdict (RECORDED, same plan, line 96):** Codex ACCEPT WITH FINDINGS on `fd2b0713`.
- **Live verification:** not applicable.
- **Canonical status:** repair INTEGRATED.
- **Effect on UI V2 evidence:** the UI V2 r1/r2 driver gates carried no Flutter evidence. They were replaced by the independent run of 636 tests, recorded in `AUDIT_RECONCILIATION_20261016.json:24`.
- **Remaining work:** DRV-4 is open. Its control digest includes `.git/info/*` (REPORTED, memory).
- **Next action:** none needed for UI.

### UIC-03: UI V2 deltas that landed after the freeze

- **Capability:** Brain Quick Controls UI and its closure, plus the Office LOW follow-up.
- **Objective:** additive changes after the freeze, made only with owner authorization.
- **Location:** VERIFIED with `git diff 7893aaed ec2fab54 -- uri_ui`. Nine files changed:
  - new `brain_quick_controls.dart` (+500);
  - `oi_conversation.dart` (+100);
  - `living_composer.dart` (+37);
  - `a2ui_hub.dart`;
  - Office files and tests.
- **Branch@commit:** `7893aaed..ec2fab54`, through `feaabe3f` (Brain QC) and `ec2fab54` (QC closure).
- **Tests (RECORDED):**
  - `docs/integration/qc_ember_20261018/01_BRAIN_QC_INTEGRATION_RECEIPT.md` and its gates under `evidence/gates/`.
  - `test_frozen_core`: 3 of 8 fail, and the same set fails on `cd4a7963` (QC-F4).
- **Review verdict:** IC1, R2, QCC-R2 ACCEPT WITH FINDINGS (receipt, `BRAIN_QC_CLOSURE_REPORT.md`).
- **Live verification (RECORDED):**
  - integ-uiv2-2 68/68 at `4e827178`.
  - qcc-uiv2 68/68 and qcc-1 32/32 at the closure.
- **Canonical status:** INTEGRATED.
  - Authorization: "URI - Controlled Canonical Integration, Brain Quick Controls + Ember V2.1", 2026-10-18. This is RECORDED at receipt line 3 as a quote. I did not verify the owner's chat.
  - The freeze receipt listed the quick controls as a follow-up outside the freeze.
- **Limitations:**
  - UI V2 returning and perf journeys were not re-run after these deltas. I found no record of a re-run.
  - QC-F1, QC-F4 and QC-F7 are open. QC-F5 is addressed only by UIC-05.
- **Remaining work:** QC-F4 (governance guards are not updated).
- **Dependencies:** runtime profiles `cd4a7963`.
- **Next action:** fold into the next UI V2 re-freeze or a delta receipt.

### UIC-04: Ember V2.1 fire companion

- **Capability:** a painted 2.5D fire companion in a frameless, transparent window.
- **Objective:** integrate Ember into canonical as a 12th design.
- **Location:**
  - code: `uri_ui/lib/living/companion/ember_companion.dart` (+1065);
  - assets: `uri_ui/assets/companions/ember/` (12 files);
  - records: `docs/companions/fire/v21_integ/` and `docs/integration/qc_ember_20261018/`.
- **Branch@commit:** `integration-candidate/ember-on-canonical-20261018` @ `68061d85`.
  - The code is the merge `bb61e976`. VERIFIED: `git diff bb61e976 68061d85` changes only `docs/integration/qc_ember_20261018/**` (201 files), and the `uri_ui` trees are identical (`253d93a9`).
- **Tests (RECORDED, log heads VERIFIED):** at `bb61e976`:
  - Flutter 855 passed, 5 skipped. VERIFIED from the log: `HEAD=bb61e976`, `+855 ~5: All tests passed!`.
  - pytest oi/ws 793 passed, 23 skipped.
  - analyze 0 errors, 5 info.
  - Release build rc 0.
  - `ws_frozen_check` `[]`.
  - T0-T5 at `b07bd496`: T4 depleted fails.
- **Review verdicts:**
  - Source rounds R1-R4 (all ACCEPT WITH FINDINGS): `docs/companions/fire/v21_integ/review/R1..R4_report.md`.
  - Stage-2 review at `b07bd496`, ACCEPT WITH FINDINGS: `.../ember_stage2/review/EMBER_INTEG_report.md`.
  - FINAL review at `74e7f7ba`, ACCEPT WITH FINDINGS (4 LOW, 3 INFO): `.../FINAL_EMBER_report.md`.
  - OD-2 provenance review at `401a2964`, ACCEPT WITH FINDINGS (1 MEDIUM, 4 LOW): `.../od2_ncc/OD2_VERIFY2_report.md`.
  - All reviewers were subagents. None of these is driver-counted or owner approval.
- **Live verification (RECORDED):**
  - e-first ALL PASS at `8f883bbf` (frozen Brain).
  - p3-ember-switch window and switch checks pass at `bb61e976` (P3 profile).
  - c-uiv2 68/68 at `8f883bbf` and p3-uiv2 68/68 at `bb61e976`.
  - e-returning-switch was INVALID for the switch journey.
  - c-qc never got a Brain (GPU contended).
  - All runs were on 2026-10-18.
- **Canonical status:** NOT INTEGRATED.
  - The candidate is 63 commits ahead and 0 behind, so a fast-forward is possible.
  - Ember is not pushed (VERIFIED, see the header).
  - Status per the receipt: "READY FOR OWNER INTEGRATION AUTHORIZATION".
- **Limitations:**
  - Fidelity AC-F1 and AC-F3 are NOT MET.
  - Also open: F-LIGHT-1, T4 depleted, F-SIZE-1, F-START-GAP, AC-P1, HARN-2 and PERF-1 (Debug runner VRAM only).
  - Brain throughput on an uncontended desktop was not verified at `bb61e976`.
- **Remaining work:**
  - These owner decisions.
  - The UI V2 returning and perf journeys were not re-run with Ember.
  - The e-run and c-qc drivers are not archived (R-7).
- **Dependencies:**
  - Owner authorization.
  - OD-2 as a distribution gate.
  - Ordering against UIC-05.
- **Next action:** an owner decision to integrate. See (c).

### UIC-05: UI Controls and Typography

- **Capability:** push-to-enable Brain controls (`QcToggle`, `QcSegmented`), automatic restore after a failed switch (the fix for QC-F5), and one typography system (Segoe UI and Consolas, the 12-step `UriType` scale).
- **Objective:** improve interaction and typography without a redesign.
- **Location:**
  - `uri_ui/lib/living/integration/qc_toggle.dart`, `brain_quick_controls.dart` and `uri_theme.dart`, plus 43 files;
  - `scripts/ws_brain_host.py`, `worker_bridge.py` and `brain_quick_controls.py`;
  - `docs/ui/controls_typography_20261018/` and `docs/ui/UIdevelopment.md`.
- **Branch@commit:** `milestone/ui-controls-typography-20261018` @ `e9ee7409`. The code is `22b53b78`, and `22b53b78..e9ee7409` is docs only (per R1).
- **Tests:** at `22b53b78`:
  - Flutter 799 passed, 5 skipped. VERIFIED: the log ends `+799 ~5: All tests passed!`.
  - pytest 805 passed, 23 skipped (RECORDED).
  - analyze 0 errors, build OK, `ws_frozen_check` ok (RECORDED).
- **Review verdict:** R1 ACCEPT WITH FINDINGS. 0 HIGH, 1 MEDIUM (R1-01), 5 LOW (R1-02..R1-06), 2 INFO.
  - The record is **untracked and uncommitted**: `D:/uri-dev/uri-ui-controls-typo/docs/ui/controls_typography_20261018/review/R1_report.md` (mtime 2026-10-18 19:29).
  - **There is no re-review, and no repair commit after `e9ee7409`.**
- **Live verification:**
  - ui-2 at `22b53b78`, 2026-10-18. The report claims "30/30". VERIFIED: the raw `observations.json` holds **26 checks, 26 PASS**, and `failures: []`.
  - uiv2-1 68/68 at `22b53b78` (RECORDED).
  - The P3 start profile was used. Draft switching was not exercised live.
- **Canonical status:** NOT INTEGRATED. Local branch only, not pushed. It is 5 commits ahead of canonical and 0 behind.
- **Limitations:**
  - R1-01 is open. VERIFIED in code: `qc_toggle.dart:111-140` and `:269-289` are a bare `GestureDetector` inside `Semantics(button, excludeSemantics: true)` with no `onTap`. There is no `Focus`, `InkWell` or `Shortcuts`. The controls cannot be reached by keyboard or activated by a screen reader. This is a regression from the `PopupMenuButton` controls in `ec2fab54`.
  - Contrast was not measured. Light themes were not tested live. D7 performance is PARTIAL.
- **Remaining work:**
  - R1-01 (MEDIUM) and R1-02 (wrong count) are marked "fix before integration".
  - R1-03..R1-06 (LOW) and F-1 (MEDIUM, an owner product decision) are open.
  - The R1 report should be committed.
- **Dependencies:** canonical `ec2fab54`, and ordering against UIC-04.
- **Next action:** repair R1-01 and R1-02, commit R1, run a re-review (R2), then re-run ui-2 and uiv2-1 on the repaired code.

### UIC-06: Solar orb R&D (four shader directions)

- **Objective:** R&D on a solar orb, comparing four real-time shader directions.
- **Location:** `docs/orb_solar/ORB_SOLAR_RND_REPORT.md`, `uri_ui/shaders/orb_solar.frag` and `solar_orb.dart`.
- **Branch@commit:** `phase/orb-solar-rnd` @ `07a2f380`.
- **Tests:** UNKNOWN for this commit.
- **Review verdict:** none recorded at this commit.
- **Live verification:**
  - The report says (line 159): "The Flutter orb has never been rendered."
  - Line 6 says "not merged and not wired into the app".
- **Canonical status:** the content is INTEGRATED indirectly.
  - `07a2f380` is an ancestor of canonical.
  - It entered through the companion-voice line merge `ab8f8227` (UIC-09).
  - `orb_solar.frag` is in the pubspec `shaders:` list in `ec2fab54`.
- **Limitations:** this commit holds R&D only.
- **Remaining work:** none here. Superseded by UIC-08 and UIC-09.

### UIC-07: UI Living Companion

- **Objective:** a Living Companion UI candidate (7 orb styles x 10 palettes).
- **Location:** worktree `uri-ui-phase`.
- **Branch@commit:** `phase/ui-living-companion` @ `569cf7c6`.
- **Tests:** 277 at `4aef264` (REPORTED in the commit message).
- **Review verdict:** Codex r6 ACCEPT WITH FINDINGS (per the merge message `ddaf67bb`).
- **Live verification:** UNKNOWN.
- **Canonical status:** INTEGRATED. It is an ancestor through `ddaf67bb` (working-system integration).
- **Next action:** none. Superseded by UI V2 as the default visual: `URI_UI_VISUAL=living` keeps the old one (REPORTED, memory).

### UIC-08: Living companions (Solar, Sakura, Lunar, Moonlit)

- **Objective:** a set of companion shaders.
- **Location:** `uri_ui/shaders/companion_*.frag`, and `docs/companions/COMPANIONS_RND_REPORT.md`.
- **Branch@commit:** `phase/living-companions` @ `d7a052f8`.
- **Tests:** RECORDED in UIC-09's integration gates.
- **Review verdict:** covered by the UIC-09 Codex rounds.
- **Live verification:** UNKNOWN on its own. The Flutter render gap was closed at 294 tests (REPORTED, memory).
- **Canonical status:** INTEGRATED. It is an ancestor through `ab8f8227`.
- **Limitations:** an Unreal runtime was rejected (report §9).
- **Next action:** none.

### UIC-09: Companion visual, voice and settings

- **Objective:** integrate companion visuals, voice presence and settings.
- **Location:** `docs/companions/settings/INTEGRATION_RECEIPT.md` and `docs/companions/voice/`.
- **Branch@commit:** `phase/companion-voice` @ `c0fc8b90`. Merged as `ab8f8227` and `6f06c312`; the receipt is canonical `f24d57ab`.
- **Tests (RECORDED, receipt §3):** at `6f06c31`: Flutter 427 passed, 3 skipped; pytest 226 passed, 20 skipped; `ws_frozen_check` ok.
- **Review verdict:**
  - Codex R4 ACCEPT on `417cd26`.
  - Integration round 2 ACCEPT WITH FINDINGS on `6f06c31`.
  - Source: the receipt.
- **Live verification:** the voice evidence was simulated (SAPI audio). REPORTED, memory.
- **Canonical status:** INTEGRATED (2026-10-09).
- **Remaining work:** a human live-voice run (REPORTED).

### UIC-10: A2UI

- **Objective:** an A2UI renderer driven by scheduler authority.
- **Location:** `uri_ui/lib/living/a2ui/`.
- **Branch@commit:** `phase/a2ui` @ `cdcffe38` and `integration/a2ui-20261009` @ `15874496`.
- **Tests and review verdict:** Codex 7 rounds, ACCEPT WITH FINDINGS (REPORTED, memory). Not re-checked.
- **Live verification:** staging a2ui_live evidence exists under `docs/integration/final_20261010/evidence/staging/a2ui_live/` (RECORDED; I did not read its content).
- **Canonical status:** INTEGRATED. It is an ancestor through `5432eece`.
- **Limitations:** R6-2 is left for the owner (REPORTED).

### UIC-11: Innovation lab

- **Objective:** lab candidates, including a GenUI proof of concept.
- **Location:** `innovation_lab/`.
- **Branch@commit:** `phase/innovation-lab` @ `47b63f62` (11 commits ahead, 764 behind).
- **Tests:** UNKNOWN.
- **Review verdict:** Codex re-check 2, "all findings resolved" (commit message). The report itself says "No candidate is integrated".
- **Live verification:** none.
- **Canonical status:** NOT INTEGRATED. It is not an ancestor of canonical.
- **Superseded in part:** A2UI built its own renderer and rejected GenUI (REPORTED, memory `uri-a2ui-phase`).
- **Next action:** owner triage, keep or archive.

### UIC-12: Onboarding and usability

- **Location:** `living_onboarding_flow.dart`, `onboarding_screen.dart` and `brain_onboarding_screen.dart`.
- **Branch@commit:** canonical `ec2fab54`.
- **Tests:** UNKNOWN for onboarding as a separate area.
- **Live verification:** UI V2 journey J1 "onboarding-first" (`pf1/main-j1-onboarding-first.png`) on `7893aaed`. Automation only.
- **Canonical status:** INTEGRATED.
- **Limitations:** **no human usability study or user-test record was found.**
- **Remaining work:** a usability test with a real user.
- **Next action:** an owner decision.

## (c) Candidates pending integration

### C1: Ember V2.1, `integration-candidate/ember-on-canonical-20261018` @ `68061d85`

**Source and base**
- Worktree: `D:\uri-dev\uri-integ-ember`.
- Canonical base: `ec2fab54`. It is the second parent of the merge `bb61e976`. The branch is 63 ahead and 0 behind.

**The candidate that is acceptance-qualified**
- The code is `bb61e976`. The tip `68061d85` has the same code (VERIFIED: the only diff is records).
- Ember source line: `milestone/ember-v21-integ-20261018` @ `0b853288`, with code `67d61d3a` → `55405e7e` (merge onto `feaabe3f`) → `b07bd496` (IC1-03) → `8f883bbf` (F-1/F-2) → `bb61e976` (merge of `ec2fab54`).
- VERIFIED ancestors of `68061d85`: `0b853288`, `67d61d3a` and `d6a83131`.
- **Superseded, and not candidates:**
  - `582a2734` (`ember-on-qc`; its IC1-03 patch is the same patch as `b07bd496`; 10 behind);
  - `0b853288` (40 behind);
  - `phase/ember-v21-final-20261015` @ `4a70d9e7` (closure docs, not an ancestor);
  - the tag `preserve/ember-v21-final-20261015`, which points to `d6a83131`, an ancestor of `68061d85`.

**Acceptance evidence**
- Verdicts: R1-R4, stage-2 and FINAL, all ACCEPT WITH FINDINGS, plus the gates listed in UIC-04.
- Records after the FINAL review, all docs only:
  - `a299bd06`: R-1..R-7 applied;
  - `0a0cddbe` and `401a2964`: OD-2 record (`401a2964` was reviewed by OD2_VERIFY2);
  - `a6f47902`: status;
  - `6561e0b4`: OD2_VERIFY2 repairs. **These repairs were not re-reviewed** (a docs-only gap, low impact).
  - `68061d85`: removes 14 `od2_ncc` review PNGs.

**OD-2 artwork provenance**
- Record: `docs/integration/qc_ember_20261018/03_EMBER_OD2_PROVENANCE.md` revision 2. Status: DEFERRED DISTRIBUTION-RELEASE GATE.
- The owner's reclassification wording is quoted there as a record. The chat was not verified.
- The same policy is in memory `uri-generated-art-distribution-gate.md`.
- The chain ChatGPT (Fiverr source card) → Gemini sheet → atlases is UNRESOLVED at its first link.

**Where the reference art lives**
- The reference art is **not in the tip tree**. VERIFIED: 0 files under `docs/companions/fire/reference/` at `68061d85`.
- **It is in history** from `8a1438ec`, which holds `idle_source_screenshot.jpg`, `uri_emotions_sheet.png` and `video_frames/*`. 15 commits carry it, and it is reachable from `68061d85`.
- **Pushing `68061d85` therefore publishes the reference art** to the private `uri-repo`. Owner policy says that is not external distribution.
- The tip tree still holds derived Ember imagery: the 12 shipped assets and evidence screenshots (FINAL R-4).

**Required repairs**
- None blocking.
- The carried owner decisions are AC-F1, AC-F3, T4, F-SIZE-1, F-LIGHT-1, F-START-GAP, AC-P1 and F-5.

**Risk: MEDIUM.** Ember changes UI V2 frozen surfaces and changes one UI V2 test.

**Frozen-file impact (VERIFIED, `git diff ec2fab54 68061d85`)**
- UI V2 frozen-scope surfaces it touches:
  - `companion_orb.dart` (+55/-), `living_app.dart`, `oi_sources.dart` (+177, Brain-state wiring);
  - `companion_settings_section.dart`, `companion_gallery.dart`;
  - `companion_state`, `companion_theme`, `companion_preferences` and `companion_sources`;
  - `pubspec.yaml` (+2 assets);
  - the tests `ui_v2_test.dart` (11 → 12 designs), `companion_orb_test.dart` and `voice_presence_test.dart`.
- Runtime frozen paths: no change under `model_lab`, `core` or `uri_operational_intelligence`, and `ws_frozen_check` is `[]`.
- Under freeze-plan criterion 5, these companion and settings changes mean the affected UI V2 journeys must be re-run.
  - The main journey was re-run: 68/68 twice.
  - Returning 12/12 and perf were **not** re-run.

**Conflicts with UI Controls (`e9ee7409`)**
- `git merge-tree --write-tree 68061d85 e9ee7409` gives tree `e68da43c`, rc 0, **no textual conflict**.
- The one file both sides changed is `companion_settings_section.dart`, which auto-merged.
- Static check of the merged tree: 0 numeric `fontSize` or `fontFamily` literals in the 11 Ember Dart files, so the typography guard should hold. This is not run.

**Required regression tests after any combined integration**
- The full Flutter suite.
- The typography guard.
- pytest oi/ws.
- `ws_frozen_check` and `test_frozen_core` in a materialized runtime.
- Ember T0-T5.

**Live requirements**
- UI V2 main, returning and perf journeys.
- Ember e-first, run on the frozen Standard profile in an uncontended desktop if possible.
- A Brain-switch journey under Ember with the new toggles. The Ember driver relies on the old chip text (R1-07), so it needs an update.

**Expected result:** gates as at `bb61e976` (855/5/0) plus the UI-controls tests, and 68/68.

**Rollback**
- Nothing is pushed today.
- After a fast-forward: revert the range `ec2fab54..68061d85`, or reset the ref with owner approval.
- The art stays in remote history after a revert, so a revert does not take it back.

### C2: UI Controls and Typography, `milestone/ui-controls-typography-20261018` @ `e9ee7409`

**Source and base**
- Worktree: `D:\uri-dev\uri-ui-controls-typo`, which has untracked `review/` and `REFERENCE_confirm_dialog_before.png`.
- Base: canonical `ec2fab54`, merged at `a4935c2b`. The branch is 5 ahead and 0 behind.

**Acceptance evidence**
- R1 ACCEPT WITH FINDINGS (uncommitted).
- Gates at `22b53b78`.
- Live runs ui-2 (26/26, not 30/30) and uiv2-1 68/68.

**Required repairs, before integration as R1 itself states**
- **R1-01 MEDIUM:** the controls cannot be reached by keyboard or screen reader. The fix needs a widget test that tabs to a control and presses Enter.
- **R1-02:** correct the live count to 26/26.
- Recommended: R1-03 (a false "failed too" notice after the 600 s gate), R1-04 (a superseded restore leaves no record), R1-05 ("frozen" is the wrong label for `reference_dashboard.dart`) and R1-06 (the dialog leaves out the case where memory is taken after the stop).
- Then: commit R1, run the R2 re-review, and re-run live.

**Risk: MEDIUM.**
- The branch changes Brain host and worker Python (`ws_brain_host.py`, `worker_bridge.py`), adding a restore path.
- It also re-styles 43 Dart files across UI V2 frozen surfaces: `main.dart`, `living_shell.dart`, dashboard, workspace, settings, onboarding, voice and Office.

**Frozen-file impact**
- `ws_frozen_check` is ok (RECORDED). The protected `settings_shell.dart` is untouched.
- The Runtime v1 config and the `runtime_profile*` files are unchanged (RECORDED, report §2).
- UI V2 frozen-scope visuals change app-wide, for example `bodyMedium` goes from 13.5 to 14. The main journey was re-run (68/68); returning and perf were not.

**Conflicts:** none textual with C1 (see above).

**Required regression tests**
- The full Flutter and pytest suites.
- `test_ui_controls_switch_fallback.py`.
- A new keyboard and semantics test.
- A contrast check on four palettes, which has not been done anywhere.

**Live requirements**
- ui-2 and uiv2-1 on the repaired code.
- Preferably the Standard profile and a Draft switch.

**Expected result:** all checks pass, and controls can be operated from the keyboard.

**Rollback:** local only. After integration, revert the range.

### Recommended order (owner decision)

Either order is free of textual conflicts. C1 is ready now and needs only owner authorization. C2 needs repairs and a re-review first.

If C2 lands second, it must re-run the Ember live journey, because the Ember switch driver depends on the old controls (R1-07).

## (d) Verdicts on Antigravity claims

Sources:
- `C:/Users/cheta/.gemini/antigravity/brain/2f49f16d-03d7-44e2-8bf8-777a43b24ac1/URI_DEV_AUDIT_20261020.md` (DEV)
- `URI_HISTORICAL_RECOVERY_AUDIT_20261020.md` (HIST)
- `URI_AUTHORITATIVE_MASTER_REGISTER.md` (REG)

### G1: "Solar Companion & Shaders | Implemented & Verified | Yes (`07a2f380`) | Pass | Pass | Accepted | Approved" (DEV:132)

**PARTIAL.**
- The solar shaders are in canonical: `orb_solar.frag` and `companion_solar.frag` are in the pubspec `shaders:` list in `ec2fab54`.
- But `07a2f380` is R&D that was "not merged and not wired into the app", and its Flutter orb was "never rendered" (`ORB_SOLAR_RND_REPORT.md:6,159`).
- That content reached canonical later, through merge `ab8f8227` (the companion-voice line, Codex R4 ACCEPT on `417cd26`). It was not integrated "at 07a2f380".
- There is no test, live or acceptance record for `07a2f380` itself.
- The names "Glacier, Forest" are UNVERIFIABLE: grep found no match in `uri_ui/lib` at `ec2fab54`.

### G2: "UI Controls & Typography ... Pass (30/30)" and "Accepted" / "Accepted (UI-1/UI-2)" / "Passes all gates" (DEV:134,165,272)

**REFUTED on the count and on acceptance.**
- ui-2 records 26 checks, not 30.
- ui-1 was a stopped run with 1 FAIL (a driver defect), not an acceptance.
- The only review is R1 ACCEPT WITH FINDINGS. It is uncommitted, its MEDIUM R1-01 is unrepaired, and it asks for fixes before integration.
- The gates themselves passed: **CONFIRMED** at `22b53b78`.

### G3: "UI V2 App Shell ... Yes (`2eff03d0`) | Pass (788 dart) | Pass (68/68)" (DEV:131)

**PARTIAL.**
- UI V2 is integrated and frozen at `7893aaed`, not `2eff03d0`.
- The Flutter counts I can find are 636 (`2eff03d0`), 738 (`25048709`) and 758 (`7893aaed`). The figure "788" is UNVERIFIABLE.
- 68/68 is CONFIRMED (pf1, RECORDED).

### G4: "Ember ... 855 Flutter tests pass; live transparent window and Brain switching verified; merges cleanly onto ec2fab54; Accepted w/ findings (FINAL-R)" (DEV:133,164,270)

**CONFIRMED, with caveats.**
- 855 is VERIFIED in the log at `bb61e976`.
- The candidate contains `ec2fab54` and is 0 behind, so a fast-forward is possible.
- FINAL ACCEPT WITH FINDINGS is RECORDED.
- Caveats:
  - Brain switching was verified on P3 only.
  - e-returning-switch was INVALID.
  - Fidelity AC-F1 is NOT MET, and T4 fails.
  - "All technical gates pass" (DEV:220) is therefore **PARTIAL**.

### G5: "Ember Companion V2.1 Transparent Shaders" / "Transparent Sprite Shaders" (REG:120, HIST:155)

**REFUTED.** Ember uses painted atlas clips, not a shader. The test `companion_orb_test.dart` asserts that Ember does not use a shader (`EMBER_INTEG_report.md` §3).

### G6: Ember and UI-typo are "awaiting reviewer gate clearance" / "Pipeline ... halting canonical merges" (HIST:21,99,198,217)

**REFUTED for Ember, PARTIAL for UI-typo.**
- Ember has its reviews: subagent reviews were used because Codex was quota-blocked. Its receipt says "READY FOR OWNER INTEGRATION AUTHORIZATION". The blocker is owner authorization.
- UI-typo needs repairs and a re-review, not reviewer unblocking.

### G7: "UI-V2-POSTINT receipts/ui-v2-20261016 ... 74044f77 ... Receipt Pushed" (DEV:163)

**CONFIRMED.** `74044f77` is an ancestor of `uri-repo/receipts/ui-v2-20261016` (`64e74109`).

### G8: Ember "Fully qualified in worktree uri-integ-ember (`68061d85`)" (DEV:85, HIST:39 "Partially developed (Staged)")

**CONFIRMED as qualified, not integrated.** The code at `68061d85` equals the reviewed `bb61e976`.
- The HIST class "Partially developed" understates it.
- "Fully qualified" overstates it: the fidelity decisions are still open.

### G9: OD-2 "Policy Settled (Deferred)" (DEV:271)

**CONFIRMED** as a record (`03_EMBER_OD2_PROVENANCE.md`). The owner chat was not verified.
- Missing from the claim: the art is in the branch history, so a push carries it.

### G10: "Approve fast-forward merge of 68061d85 and e9ee7409 into canonical" (REG:199)

**PARTIAL.**
- They cannot both be fast-forwarded: they are siblings on `ec2fab54`, so the second needs a merge. The merge is textually clean.
- `e9ee7409` is not ready (see C2).

### G11: A2UI integrated (HIST:63)

**CONFIRMED** as integrated: `cdcffe38` is an ancestor through `5432eece`. "Accessibility tree inspection" was not checked; it is out of scope.

## (e) Evidence gaps

1. **The UI-controls R1 review is uncommitted** (an untracked file in the worktree). Nothing records repairs or a re-review. This affects the C2 verdict: C2 is not ready.
2. The UI V2 **returning (12) and perf (3) journeys** were not re-run after the post-freeze QC deltas, nor on the C1 or C2 candidates. The main journey (68) was re-run each time. This affects a re-freeze, not the integration decision.
3. No re-freeze or delta receipt exists for canonical `ec2fab54` against the freeze `7893aaed`. Canonical UI is the frozen UI plus authorized QC and Office deltas.
4. Ember:
   - The drivers for the e-runs (`bcdce2a1`) and c-qc (`c2f23a11`) are not archived (R-7).
   - Throughput on an uncontended desktop at `bb61e976` was not verified.
   - The OD2_VERIFY2 repairs (`6561e0b4`) were not re-reviewed.
   - Docs only, so none of this changes the qualification status.
5. **Accessibility:**
   - No contrast measurement exists for any palette.
   - The keyboard and semantics regression R1-01 is confirmed in code.
   - `UIdevelopment.md` (90 lines; it covers typography tokens, push-to-enable controls and their states, dialogs and a verification checklist) has **no accessibility guidance**: no keyboard, focus, semantics or contrast rules.
   - This affects C2.
6. **Usability:** no human usability or onboarding study was found. All live evidence uses automation input, and no physical keyboard, mouse or microphone was qualified.
7. Owner authorizations are cited as quotes in receipts and memory. The owner's chat itself was not verified.
8. Records I did not open: the A2UI and innovation-lab verdicts and the UI-living test counts. They are marked REPORTED, so they are not primary evidence.
9. I viewed no screenshot.

## Self-review

| Criterion | Result |
|---|---|
| AC1 | Each row separates its statuses and its evidence classes. |
| AC2 | 855, 799 and 26/26 were verified in raw logs. Other counts are marked RECORDED. |
| AC3 | Each verdict has a path and a commit, and the text says none is owner approval. |
| AC4 | `bb61e976` and `68061d85` have identical code (verified). `22b53b78..e9ee7409` is docs only according to R1 (not re-run by me). |
| AC5 | Covered in C1 and C2. |
| AC6 | merge-tree was run. |
| AC7 | Eleven claims were classified. |
| AC8 | Gaps are listed with their impact. |

Corrections made during the self-review:
- G1 was first drafted as REFUTED. I changed it to PARTIAL after confirming that the solar shaders are in canonical through `ab8f8227`.
- The C1 "images kept out of tree" statement now separates the tip tree, which has no reference art, from history, which has it from `8a1438ec`.
