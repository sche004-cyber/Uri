# Independent review R3: Ember V2.1 final, 28149905..0484afdc

Reviewer: Claude (independent; did not write this work). Worktree: `C:\uri-wt\ember-review-0484afdc`, HEAD verified as `0484afdcdcc563a79759c407ef840524fd637d6e`.
Scope: the whole diff 28149905..0484afdc (6 commits: e43e97a7, 6adf8fbf, 23fb2878, 7baefb17, 269821cd, 0484afdc), plus the code it touches.

## 0. Acceptance criteria (set before the review)

- **AC-1 Mapping.** Normal Brain startup maps to `initializing`. Stopped, failed, unknown, stopping and blocked states stay `unavailable`. The host-state path is consistent with what the Brain producers (`runtime_v1.py`, `brain_health.py`, `ws_brain_host.py`, `worker_bridge.py`) emit. No real failure is shown as initializing.
- **AC-2 Priority and exhaustiveness.** The composite places `initializing` below every failure, user-blocking and activity state. Every switch, map lookup (`!`) and `indexOf` covers the new value, so nothing can crash or silently pick the wrong rank.
- **AC-3 Tables.** `companion_orb.dart`, `registry.js` and `state_tables.json` match `state_tables.py` exactly. Solar, Sakura, Lunar, Moonlit and the classic orb keep their existing rows.
- **AC-4 Assets and exporter.** The manifest matches the shipped files (bytes, sha256, layout). The haze and `panel_feather` changes give true alpha, no rectangle and no grey patch outside the figure. The gates test what they claim.
- **AC-5 Fidelity integrity.** FP-21R is presented as PROPOSED only. Raw scores are not edited. The invalid R1 is reported. Decoded numbers match raw JSON plus key. Conclusions do not go beyond the evidence.
- **AC-6 Evidence.** Every evidence file a document cites exists at the commit, or its absence is stated.
- **AC-7 Protected paths.** No frozen or protected path is touched (Core, Runtime, `ws_frozen_check.py` PROTECTED list).

## 1. What I verified myself (primary evidence)

- **Protected paths (AC-7): PASS.**
  - `git diff --name-only 28149905 0484afdc` touches only `companion_art/fire_v2`, `docs/companions/fire/v21/**`, `rnd/companions`, `scripts/fire_companion`, `uri_ui/assets/companions/ember`, `uri_ui/lib/living/{companion,integration}` and `uri_ui/test/living`.
  - None of these is under the `scripts/ws_frozen_check.py` PROTECTED prefixes, and none is under `uri_operational_intelligence/` or `model_lab/`.
- **State tables (AC-3): PASS.** I loaded `state_tables.py` read-only and compared:
  - `dart_table()` output is present verbatim in `companion_orb.dart` for solar, sakura and lunar;
  - every `S(...)` row in `registry.js` equals the table;
  - `state_tables.json` equals `TABLES`, revision 3;
  - every family has all 10 states.
  - The Dart test `voice_presence_test.dart:633` pins the widget to the JSON. Moonlit reads lunar and Ember reads solar.
- **Exhaustiveness (AC-2): PASS.**
  - `label`, `EmberClips.forState` and `OrbParams.forState` are exhaustive switch expressions.
  - Every other switch over `CompanionState` in `lib/` has a `_` branch (`companion_mode_view.dart:188`, `companion_presence.dart:410`, the onboarding chips iterate `values`).
  - `CompanionParams.of` (`_tables[id]![state]!`) has the new row in all three families.
  - `_priority` in `CompositeCompanionSource` contains all 10 values. This matters: a missing value would give `indexOf == -1`, and that state would beat `error`.
  - No code persists or sends `CompanionState.index`. `main_living.dart` uses `name`.
- **Composite priority: PASS.** `initializing` sits after `unavailable` and before `idle` (`companion_sources.dart:432-443`). A real `unavailable` or any activity from another source wins over it. `resolvePresence` does not treat `initializing` as blocking, which is correct.
- **Manifest and assets (AC-4, integrity): PASS.**
  - For all 9 clips, the bytes and sha256 in `manifest.json` match the files.
  - Each clip has `frames == len(eye_offsets)` and `cols*rows >= frames`.
  - The blink atlas bytes and sha256 match.
  - `kindling` is 96 frames, 12x8 cells of 320 px: about 39.3 MB decoded, the largest atlas. Budget check: kindling + idle + thinking = about 102 MiB, under the test's 160 MiB bound.
- **Shipped haze, measured on the shipped atlases:** I composited every frame of every clip over white. This is my own script, not `haze_probe_v21.py`.
  - `depleted`:
    - 0 px darkened by 6 % or more outside r = 0.45 of the side;
    - corner darkening 0;
    - alpha 0 in the 2 % border band and outside r = 0.45.
  - On white, the share of the depleted cell darkened by 6 % or more fell from **61.1 %** (28149905) to **25.9 %** (0484afdc, character included). The haze repair is real.
  - The other clips have alpha 0 in the border band and at most 5 px darkened by 6 % or more outside the circle (warm glow, ring alpha at most 0.251). That is within the transparency test's `ringMax <= 128`.
- **Fidelity numbers (AC-5): PASS.** I recomputed R1 and R2 from `r*_raw/reviewer*.json` plus `r*_key/key.json` with my own code:
  - Pack integrity: the hashes of all 132 files per round match the key, and there are no extra files.
  - Every reviewer answered every letter and every dimension (C1-C6, P1-P4), all in 0..10.
  - The R1 and R2 images are byte-identical per (state, candidate) (same 120 candidates). This confirms the R2_RESULTS claim.
  - R2 character means match `R2_RESULTS.md` (dark 88.9 / 89.2 / 90.8 / 83.3; light 76.9 / 78.3 / 78.9 / 73.9), and so do R (1.000, or 1.020 for joyful light reviewer 3).
  - R2 validity: `ref_reframed` 96-98 for every reviewer and state, and v1 < ref_copy everywhere.
  - R1 is invalid as reported: reviewer 2 scored depleted `ref_reframed` (B) at 64.0. Its B note describes a light-surround image, and C (`v21_mid_light`) is described as "the painting inset in a dark frame", so the transposition claim holds.
  - The R2 deltas against V2 (+6.4 to +7.2 character, depleted +3.9; visual +5.3 to +6.0, depleted +2.3) recompute exactly.
  - The general notes of all six reviewers state that same-surround copies looked identical. This confirms the "all six reviewers said so" claim.
  - No sign of score manipulation: R1 is kept in full and labelled INVALID, and the R2 gates are reported as computed, including the NOT MET.
- **Rehearsal merge claim: PASS.** `git merge-tree --write-tree 316e6475 7baefb17` gives exactly one conflict (`test/ws/ws_integration_test.dart`), plus auto-merges in `companion_preferences.dart`, `companion_settings_section.dart` and `pubspec.yaml`. This matches `09_...md` section 2. Commits 73aa3bd2, 67bce88b, 316e6475 and 7baefb17 all exist.

## 2. Findings

### HIGH

**R3-01 (HIGH): the companion reads two snapshots of different ages, so a failed load can show "Brain loading" and a ready Brain can flash depleted.**
- **Where:** `uri_ui/lib/living/integration/oi_sources.dart:110-126`.
- **The two snapshots:**
  - Runtime state comes from `c.brainStatus['state']`, refreshed only by `refreshStatus` every **15 s** (`working_system_app.dart:48,119`).
  - Host state comes from `c.brainHealth['host']`, refreshed by the monitor every **5 s** (`working_system_app.dart:49,120`; `oi_conversation.dart:259-268` calls `refreshHealth` only).
- **Precedence:** the runtime state is tested first. If it is in `brainStartingStates`, the host state is never consulted.
- **Case 1, failure shown as initializing.** The last `brain_status` read `LOADING` (server reachable, HTTP 503). The host's `ensure_ready` then fails: `ws_brain_host.py:287-292` sets `FAILED` and stops the server. For up to 15 s the companion shows `initializing` / "Brain loading" while `brainHealth` already says the host has FAILED. This breaks the owner's rule "must not misreport a real failure as initializing". Before this change the same stale `LOADING` showed `unavailable`.
- **Case 2, ready Brain shown as depleted.** The last `brain_status` read `STOPPED` (before the server listened; the worker does not own the host's process, so `runtime_v1.py:268-271` returns STOPPED). The host then reaches `READY` (`ws_brain_host.py:338`) before the next 15 s refresh. `hostState == 'READY'` is not a starting state, so the companion drops from `initializing` to `unavailable` "Brain STOPPED" (depleted) just as the Brain becomes ready. That is the sad face this change exists to remove.
- **Test gap:** `companion_initializing_test.dart` drives both snapshots from one variable (`brainState`), so this cannot be caught. The live driver calls `refreshStatus` in a tight loop (`fire_v21_live_driver.dart:268`), so live runs do not reproduce the app's 15 s cadence either.
- **Repair (any of):**
  - Decide from one snapshot: `brain_health` already returns a fresh `readiness` (runtime state) next to `host` (`brain_health.py:68`). Use `brainHealth['readiness']` and `brainHealth['host']` together, falling back to `brainStatus` only when health is absent.
  - Or let a running host whose state is `FAILED`, `STOPPED`, `STOPPING` or `READY` override a stale runtime starting state.
  - Or refresh `brain_status` inside `refreshHealth`.
  - In every case, add a test where `brainStatus` and `brainHealth` disagree.

### MEDIUM

**R3-02 (MEDIUM): `WAITING_FOR_GPU` is treated as a normal startup, which contradicts the Brain's own health classification and the reviewed proposal.**
- **Where:** `oi_sources.dart:26-33,123-124`.
- **What `ws_brain_host.py` sets `WAITING_FOR_GPU` for (`:224-247`):**
  - `GPU_UNMEASURED`: memory cannot be measured;
  - `GPU_CONTENDED`: another app holds the VRAM;
  - `VRAM_RELEASE_TIMEOUT`: memory not released after the timeout, and "URI keeps waiting";
  - `GPU_QUIET_WINDOW`: a short settle after contention.
- **What `brain_health.py:126-129` does with it:** reports `UNAVAILABLE` with recovery options `close_gpu_apps`/`wait`. It treats only `HOST_RECOVERING` as recovering.
- **Effect in the UI:** the companion shows a calm `initializing` "Waiting for the GPU" for as long as another application blocks the GPU, possibly indefinitely, while the health surface says UNAVAILABLE and asks the user to act.
- **Inverted states:** `RELEASE_WAIT` (the normal release wait during a restart, `RECOVERING` in `brain_health`) maps to `unavailable`. Its timed-out form `WAITING_FOR_GPU`/`VRAM_RELEASE_TIMEOUT` maps to `initializing`.
- **Scope drift:** `04_STARTUP_PROPOSAL_V21.md:26-27`, the proposal the owner was asked to approve, lists `STARTING`, `STARTING_HOST`, `LOADING` and `WAITING_FOR_LEASE` only. `WAITING_FOR_GPU` and `CALIBRATING` were added without a recorded decision.
- **Repair:** pick one of these and record the owner decision:
  - follow `brain_health`: initializing iff the health state is `RECOVERING` and the host is not `STOPPING`, with `WAITING_FOR_LEASE` per the proposal;
  - or expose the host `detail` and treat only `GPU_QUIET_WINDOW` as normal;
  - or cap how long a GPU wait may read as initializing.

**R3-03 (MEDIUM, evidence integrity): documents cite evidence that is not in the commit.**
- **The citations:**
  - `companion_art/fire_v2/expressions.json:141` cites `evidence/final/haze/` (haze gates H1-H3).
  - `08_FIDELITY_PROTOCOL_V21R.md:132` relies on "haze H1-H3" gates.
  - `09_UI_V2_INTEGRATION_PLAN_V21.md:50` cites `evidence/final/size_crop.json` and `size_crop.jpg` (the 85.7 % / 6.5 % / 2.8 % / 2.9 % / 0.3 % numbers).
  - `09_...md:99-100` cites `evidence/final/rehearsal/analyze.log` and `full_flutter_test.log` (630 passed / 5 skipped / 1 failed; 32/32 after the edit).
- **What the commit holds:** `git ls-tree -r 0484afdc` has no `docs/companions/fire/v21/evidence/final/` at all. The path is not git-ignored (`git check-ignore` is empty). Only the generating scripts are committed (`haze_probe_v21.py`, `size_crop_v21.py`).
- **Effect:** the size-crop numbers and the rehearsal test counts cannot be verified from the repository.
  - I independently confirmed the depleted haze outcome on the shipped atlas (section 1), so the haze claim is substantively true. Its cited evidence is still absent.
  - There is also no committed test log for 0484afdc or 7baefb17. 7baefb17's own message says the full suite failed at e43e97a7 (see R3-08).
- **Repair:** commit `evidence/final/` (haze_probe.json and jpg, size_crop.json and jpg, rehearsal logs, and a full-suite log at the final SHA), or reword the citations as "local, not committed".

**R3-04 (MEDIUM): the R2 conclusions go beyond what the control can show.**
- **Where:** `R2_RESULTS.md:39-46,47-58,63-69`.
- **How the control is built:** `painting_t` is the painting cut out with **Ember's own layer alpha and, in the soft edge, Ember's own layer colours** (`critique_pack_v21r.py:48-59`, from `rgba` of the layer model). It shares Ember's matte and edge colours by construction. Pixel check on the R2 reviewer 1 pack: mean |painting_t - v21_worst| is 0.8-5.1 / 255 per state and surround, so the images are near-identical.
- **What R2 nevertheless asserts:**
  - "Ember is as faithful as the original painting can be in this presentation."
  - "Character 90 % is not reachable by the painting itself in the transparent presentation."
  - "cannot be met by any artwork under the mandated transparent presentation ... including the original painting itself."
  - The light-surround defects (hard head rim, robe gaps, foot blob) are called "properties of a transparent painted character on a light desktop".
- **Why that does not follow:** the defects may equally come from Ember's matte, which the control shares; the protocol's own weakness 1 (`08_...md:130-133`) says exactly this. Further:
  - all reviewers said differences "may exist below what I could see";
  - only two still frames were scored, so "animation ... cost nothing measurable" is not established by this round;
  - R1 (invalid, but with otherwise-valid reviewers) put dark-surround character for idle, joyful and fierce at 90.3 / 91.7 / 91.9, so R2's 83.3-90.8 sits inside the stated about 5-point between-round variance.
- **Repair:** restate the readings as:
  - "this panel could not distinguish Ember from the painting cut out with Ember's matte";
  - "the light-surround loss is shared by Ember and this matte; whether a better matte or another artwork would recover it is untested".
  Keep option (b) but describe its control accurately.

**R3-05 (MEDIUM, disclosed but open): requirement 1 is not met on a real launch, and no live evidence of `initializing` exists.**
- **Where:** `09_...md:61-68` (F-START-GAP).
- The launcher starts the UI before the Brain host. The first `refreshStatus` (`working_system_app.dart:117`) therefore usually reads `STOPPED` with no host, and a first-time user sees depleted until the next health tick (5 s or more). The finding is disclosed, which is correct.
- The driver adds a `brain-initializing` shot (`fire_v21_live_driver.dart:270-275`), but no live run at this commit is committed. "The live run measures the gap (`06b`)" refers to nothing in the repository.
- Combined with R3-01 case 2, the real startup sequence can be depleted, then initializing, then depleted, then idle.
- **Repair:** fix R3-01, then run and commit a live startup journey with the 15 s and 5 s cadences, recording the state sequence with timestamps. Track the launcher change as an owner decision.

### LOW

**R3-06 (LOW): the live driver drops the first state of every cleared sequence.**
- **Where:** `fire_v21_live_driver.dart:234-246`.
- `sample()` now records only when `s != lastState`, but `states.clear()` (`:314, :405, :450`) does not reset `lastState`.
- After a clear, the starting state (for example `idle` before a turn, or before the stop in step 9) is no longer recorded, and the list stays empty if the state never changes. Before this change it was recorded (`states.isEmpty || ...`). Turn records (`companion_states`, `states_through_recovery`) lose their first element.
- **Repair:** reset `lastState = ''` wherever `states.clear()` is called (or wrap clear+reset in one helper).

**R3-07 (LOW): a doc comment moved onto the wrong declaration.**
- **Where:** `oi_sources.dart:9-35`.
- The new `///` block for `brainStartingStates` directly follows the existing `///` block of `OiCompanionSource`. The class's documentation (W9, success semantics, F-SUCCESS) now documents the `const`, and the class has none.
- **Repair:** put a blank line or the constant above the class doc, or move the constant below the class.

**R3-08 (LOW, history): intermediate commit e43e97a7 fails the suite.**
- e43e97a7 hand-edited the orb tables without `state_tables.json`, so `voice_presence_test.dart:633` fails there. 7baefb17's message confirms "The full suite caught the hand-edited orb tables".
- The final state is consistent (verified in section 1). Do not cite e43e97a7 as a tested build; the R1 and R2 packs name it only as the asset build, and the assets are unchanged since.

**R3-09 (LOW): stale qualification documents.**
- `04_STARTUP_PROPOSAL_V21.md` still says "AMBER - needs owner approval" and names the state `starting`/"Starting".
- `FINAL_QUALIFICATION_REPORT_V21.md:170-172,209` still says the state is "proposed, not implemented".
- `expressions.json` now calls `kindling` "owner-approved direction", but no repository document records that approval.
- **Repair:** add a dated owner-decision record, update 04 and the final report to `initializing` as implemented, and note the deviations from 04 (R3-02).

**R3-10 (LOW): wording in the FP-21R protocol, the decoder and the R1/R2 reports.**
- **AC-F3 label (`08_...md:106`, `R2_RESULTS.md:33`):** AC-F3 is labelled "owner's 90 % requirement, unchanged/kept", but it newly requires 90 on a **light** surround as well. That is a stricter, proposed rule. Label it so.
- **Painting_t description (`08_...md:34`):** "Where the alpha is below 0.85, the layer colour is used." The code (`critique_pack_v21r.py:55`) blends linearly between 0.60 and 0.85 and uses the pure layer colour only below 0.60.
- **Decoder output (`decode_v21r.py`):**
  - `:88` prints "lowest" with `:.0f`, so 84.6 would display as "85" while failing the >= 85 gate. Use one decimal.
  - `r2_decoded.md` prints "AC-F1R ... : PASS" on its own line. `R2_RESULTS.md` correctly calls it not meaningful; adding the same caveat in the decoder output would stop a standalone reader taking it as a pass.
- **Access audit description:**
  - R2: reviewer 1's audit path list includes the parent `...\fp21r\r2` (which holds all three reviewers' folders), not only its own folder as `R2_RESULTS.md:10-11` says.
  - R1: reviewer 1's list includes `.`.
  - With no key in the scratch folders, neither affects blinding. Still, the descriptions should match the audit, and the transcripts (hashes only in the repository) cannot be checked independently.

**R3-11 (LOW): size and merge-surface details in the integration plan.**
- **Size-crop metric (`size_crop_v21.py:36-50`):** `total` counts the alpha of the whole panel, but `a` counts only what `place()` keeps in the square frame. Alpha cropped by the frame itself is neither "visible" nor "cut", so `cut` understates the loss at the frame edge.
- **File count (`09_...md:28`):** "19 files under `uri_ui`". `git diff --name-only 1b5423bc 7baefb17 -- uri_ui` gives 23 non-asset files (19 plus 4 under `tool/capture`).

**R3-12 (LOW, residual art defect, disclosed as F-LIGHT-1).** In both rounds, reviewers on the light surround flagged a dark blob by the depleted feet and a hard head rim.
- These sit inside the character's alpha, so the haze probe's "away from the character" mask cannot detect them by design.
- The haze itself passes (section 1). The "no distracting grey patches" part of requirement 2 on light desktops therefore rests on the owner's visual sign-off, which is pending.
- No repair is needed in this change beyond keeping F-LIGHT-1 open.

## 3. Requirement verdicts

| Requirement | Verdict |
|---|---|
| 1. Shared Initializing state, no failure shown as initializing | **Partly met.** The state, labels, tables, the Ember `kindling` clip and the composite priority are correct and exhaustive. The mapping has a snapshot-consistency defect (R3-01, HIGH) and a disputed `WAITING_FOR_GPU` mapping (R3-02). The real launch still shows depleted first (R3-05). Frozen Core and Runtime are untouched. |
| 2. Transparent, borderless, no grey haze patches | **Met for the haze and edges on the shipped atlases** (independently measured). The cited gate evidence is not committed (R3-03). The residual light-desktop character artefacts are disclosed (R3-12). |
| 3. FP-21R proposed, not accepted; no manipulation; invalid round reported | **Met on integrity:** the numbers recompute exactly, R1 is reported, and the status is PROPOSED throughout. The conclusions overreach (R3-04). |
| 4. No regressions to Solar, Sakura, Lunar, Moonlit, classic orb | **Met statically:** the tables are unchanged apart from the added rows, generator-consistent, and every switch is covered. The test suite was not run by me (see section 4). |

## 4. What I could not verify, and whether it matters

- **Flutter tests and analysis.** I did not run `flutter test` or `flutter analyze` (read-only review; build caches avoided). No committed log exists for 0484afdc. This leaves the compile and test status of the final SHA unverified. My static review found no compile risk, but the verdict does not rely on tests passing.
- **Missing evidence files.** `haze_probe_v21.py` and `size_crop_v21.py` were not re-run, and their outputs are absent (R3-03). The depleted haze claim was checked independently; the size-crop numbers were not.
- **Reviewer transcripts.** They are not in the repository (hashes only), so the access-audit and "fresh reviewer" claims cannot be checked. This does not change the recomputed numbers.
- **Live behaviour.** No live run was performed. R3-01 is established from the code and the producers' state machines, not from a reproduction.
- **Side effects of this review:**
  - I wrote helper files only in the session scratchpad (`verify_r3.py`, `haze_check_r3.py`, `depleted_old.webp`, plus this report).
  - `git merge-tree --write-tree` wrote unreferenced tree and blob objects into the shared object store. These are harmless and removed by GC, but they are not strictly zero-write.
  - Nothing in the worktree's files, index or refs was changed.

## 5. Self-review against the criteria

- **AC-1.** Checked against all four producers. Two defects found (R3-01, R3-02). The STOPPING, RELEASE_WAIT, FAILED, unknown and foreign cases stay unavailable, which is correct.
- **AC-2 and AC-3.** Fully checked. No defect.
- **AC-4.** The manifest and haze were verified on the shipped files. The gate evidence is missing (R3-03), and the gate's blind spot is noted (R3-12).
- **AC-5.** Numbers recomputed and integrity confirmed. Overreach flagged (R3-04), with wording issues in R3-10.
- **AC-6.** Failed for `evidence/final` (R3-03) and `06b` (R3-05).
- **AC-7.** Pass.

**R3-01 severity.** Under the stated severity rule ("misreport"), R3-01 is HIGH. It is bounded to one status interval (15 s or less) and needs only a small repair. No finding depends on an unverified claim by another agent.

VERDICT: REVISE
