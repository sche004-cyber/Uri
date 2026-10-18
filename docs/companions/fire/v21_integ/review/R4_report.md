# EMBER-V21-INTEG-20261018 - Independent review R4 (refresh onto canonical cd4a7963)

Reviewer: subagent, read-only. Repo D:/uri-dev/uri-ember-v21-integ. No edits, commits, app launches or GPU use.

## Verdict: ACCEPT WITH FINDINGS (no MEDIUM or higher; all LOW/INFO, disclosure-level)

## Acceptance criteria (set before reviewing)
- AC-1: HEAD = b6220852; canonical tip = cd4a7963; dcb5ebaa has parents 108be0d2 + cd4a7963.
- AC-2: dcb5ebaa is a clean merge (merge-tree tree == dcb5ebaa^{tree}); b6220852 changes docs only.
- AC-3: no canonical change since 348677b7 makes Ember/FCV-10 logic in oi_sources.dart show a wrong state (Initializing or idle).
- AC-4: every row of receipt section 8 is backed by an evidence file showing HEAD=dcb5ebaa (or the dcb5ebaa source head).
- AC-5: the disclosure of what was not re-run is complete and honest.

## Results

### 1. Merge integrity: MET (I ran these)
- `rev-parse HEAD` = b6220852; `ls-remote uri-repo refs/heads/integration/git-sync-20261008` = cd4a7963.
- dcb5ebaa parents = 108be0d2, cd4a7963. `merge-tree --write-tree 108be0d2 cd4a7963` = 4c714ac0, the same as `dcb5ebaa^{tree}`. The merge is clean and has no manual edits.
- `diff 108be0d2 dcb5ebaa -- uri_ui` is empty. The merge changed nothing in the UI.
- Outside uri_ui/ and docs/, `diff --numstat cd4a7963 dcb5ebaa` matches `348677b7 108be0d2` exactly: 22 Ember-only files (companion_art/fire_v2, rnd/companions, scripts/fire_companion). No backend or runtime path is touched.
- `diff dcb5ebaa b6220852` touches only docs/companions/fire/v21_integ/ (receipt, evidence, live/l7-returning-cd4a, and the two harness copies). The only harness change switches the runtime path from uri-ember-rt to uri-ember-rt2.

### 2. Canonical runtime-profile interaction with Ember/FCV-10: MET (read and reasoned)
- `brain_health.py` diff 348677b7..cd4a7963 adds one thing: `backend()["profile"]` = {id, frozen, qualified, ctx, vision, mtp}. `assess()`, `HOST_RECOVERING`, and the READY/BUSY/DEGRADED/UNAVAILABLE/RECOVERING set are unchanged. No readiness or health state is new.
- `ws_brain_host.py` adds `profile` to the host report, plus `required_mib` for the lease and fit checks and a `--profile` argument. Its state names are unchanged: STARTING_HOST, STARTING, LOADING, CALIBRATING, READY, DEGRADED, STOPPING, STOPPED, RELEASE_WAIT, WAITING_*.
- In `run_uri_integrated_worker.py`, `ProfileFollower.status()` hands off to `RuntimeManager.status()`. Readiness values are the same as before. A host whose profile does not match the selection reports the existing FOREIGN_INSTANCE (ARGV_MISMATCH).
- Mapping through oi_sources.dart:
  - **Profile switch, which is a host restart.** Host STOPPING is in `brainHostNotStarting`, so the companion shows unavailable "Brain stopping". STOPPED(HOST_EXIT) shows "Brain not running". The new host's STARTING_HOST/STARTING/LOADING/CALIBRATING reach Initializing through the existing rule, as a normal startup should. Nothing during the switch is mapped to idle, and STOPPING is never Initializing.
  - **FOREIGN_INSTANCE** during a selection/host mismatch fails both `brainStartingDetail` (runtimeState must be STOPPED/STARTING/LOADING) and the starting predicate. It shows the FCV-10 error presentation and fails closed.
  - **The new `backend.profile` key** is only read, as part of the Map, in the Brain card in oi_health_widgets.dart. It is not shown, and it does not reach Ember logic.
- No UI file changed in canonical (`diff --stat 348677b7 cd4a7963 -- uri_ui` is empty). The full suite and my focused tests pass at the merged tree.

### 3. Receipt section 8 vs evidence: MET, with R4-01 and R4-04
| Claim | Evidence | Check |
|---|---|---|
| Analyze 0 errors, 5 info | analyze_dcb5ebaa.log: HEAD=dcb5ebaa, 5 info, rc=1 | consistent. `flutter analyze` exits 1 on infos (fatal-infos), and every earlier analyze log also has rc=1 |
| 827 passed, 5 skipped | full_flutter_test_dcb5ebaa.log: HEAD=dcb5ebaa, `+827 ~5 All tests passed`, rc=0 | consistent |
| Release build rc 0 | build log: HEAD=dcb5ebaa, Built Release uri_ui.exe, rc=0 | consistent |
| ws_frozen_check | HEAD=dcb5ebaa, `unapproved_protected_changes: []` | consistent |
| Boundary vs cd4a7963 | file holds only `HEAD=dcb5ebaa` | claim true by my own diff, but the file records neither command nor output (R4-01) |
| Runtime rt2 from dcb5ebaa | materialization receipt: candidate_head dcb5ebaa, tree 4c714ac0; oi_files_copied (358) includes runtime_profile_selection, runtime_profiles, brain_health, ws_brain_host, run_uri_integrated_worker, runtime_v1 | consistent |
| Live l7 PASS | native-execution.json: source_head dcb5ebaa, tree 4c714ac0, status clean before and after, rc 0, 185.2 s. session-start/final: verified ok, 358 files, materialized_from dcb5ebaa, lease FREE before and after, no override, Brain config sha unchanged, host profile `frozen`. ui-finished: `failures: []`. flutter-test.log: All tests passed. brain-ready: READY, load_s 53.72, decode_tps 135.0. Timeline: unavailable, then initializing (LOADING), then idle (READY). Probes: borderless; per_pixel_transparent at returning/1.0/1.25; outside_reached_backdrop; ember_click_reached_uri; drag moved [0,57] | consistent |

server_exit 1 matches all of l1..l6 (the harness terminates the server). It is not a regression.

### 4. Disclosure honesty: mostly MET (R4-03)
The receipt discloses that first-time-user journeys (conversation, stop, recovery) were not re-run and lists the harness path change. It does not mention two further gaps:
- Python OI and backend tests were not run at dcb5ebaa. Mitigation: the backend tree is identical to canonical cd4a7963 per my boundary diff.
- Only the frozen profile was exercised live. No live or widget test covers Ember during a non-frozen profile or a profile switch.

## Findings
- **R4-01 (LOW, evidence)**: `evidence/boundary_vs_cd4a7963_dcb5ebaa.txt` contains only a HEAD line. An empty diff output cannot be told apart from a check that never ran. Fix: record the command, e.g. `git diff --stat cd4a7963 dcb5ebaa -- . ':!uri_ui' ':!docs'`, with its output (the 22 Ember files) and a comparison to 348677b7..108be0d2. The claim itself is independently verified true.
- **R4-02 (INFO, evidence)**: the still-frame window captures are byte-identical across runs. win-click-through-pre-alpha.png has sha 2ddae867 in l5, l6 and l7. win-drag-pre-black and win-transparent-1_25-alpha are identical in l6 and l7. Within l7, the click-through-pre set equals the transparent-1_0 set. This fits deterministic rendering under reduced motion, and each probe JSON has a fresh pid 5828, hwnd and timestamp. Still, these images are not independent visual evidence per run. Fix: note this in the receipt, or record per-capture hashes with pid and timestamp.
- **R4-03 (LOW, disclosure)**: the "Not re-run" line omits two things: the Python OI tests at dcb5ebaa, and the fact that Ember was never exercised under a non-frozen profile or during a profile switch. By reasoning (section 2), the switch maps to unavailable, then Initializing, and FOREIGN_INSTANCE maps to error. This is untested. Fix: add both to the disclosure. Optionally add a widget test for host STOPPING, then STARTING_HOST, then LOADING, then READY with `backend.profile` non-frozen.
- **R4-04 (INFO, disclosure)**: section 8 reports 135.0 tok/s without noting the change from 155.7 in l6. It also omits that the start was AT_RISK (margin -237.9 MiB, non-local 1730.1 MiB). Both are recorded in brain-ready.json, and the speed is above the 60 tok/s threshold. Fix: add one clause to the live row.

## Ran vs read
- **Ran**: rev-parse/ls-remote/log/merge-tree/diff checks listed above. Hash comparisons of the PNGs. JSON inspection of the l7 artifacts and the materialization receipt. `flutter test --no-pub test/living/companion_initializing_test.dart test/ws/ws_integration_test.dart` in uri_ui: rc 0, +38 All tests passed, worktree porcelain 0 before and after (log: focused_tests.log in this folder).
- **Read (not re-run)**: analyze, full test, build and frozen-check logs. The live run artifacts. The brain_health/ws_brain_host/worker/runtime_v1 diffs and runtime_profile_selection.py. The relevant parts of oi_sources.dart and oi_health_widgets.dart.
- **Not verified**: the screenshots were not examined visually. I did not re-run the Python OI tests or the full Flutter suite. I did not test profile-switch behaviour live. None of these changes the verdict.
