# Independent review: Ember V2.1 onto canonical feaabe3f (stage 2)

Reviewer: Claude (read-only subagent), 2026-10-18. Worktree `D:/uri-dev/uri-integ-ember`, branch
`integration-candidate/ember-on-canonical-20261018`. Nothing was edited, committed, pushed, or launched, and the GPU was not used.

## Verdict (combined code, licensing aside): ACCEPT WITH FINDINGS

There are 3 LOW and 2 INFO findings. None of them blocks. All gates are consistent at HEAD b07bd496.

## Acceptance criteria (set before review)
- AC1: The merge is clean. The merge-tree result equals the merge commit's tree, and Ember and QC change no file in common.
- AC2: IC1-03 follows D-1. A requested switch never shows ready/idle. A GPU wait shows "Waiting for GPU". A failure is never shown as calm or starting. The switch state cannot get stuck, and the test fails without the fix.
- AC3: The combined behaviour (success hold, disposal, turn refusal) is coherent, and no UI V2 or QC test was weakened.
- AC4: Every gate log is stamped HEAD=b07bd496, the numbers reconcile, and the only gate failure is T4 on depleted.
- AC5: The OD-2 status is stated, and it is shown whether the reference-art commits are in feaabe3f..b07bd496.

## 1. Merge cleanliness (ran)
- HEAD = `b07bd496c31004593ff6e508a054a739b43ef6d1`. Its parent `55405e7e` has parents `feaabe3f` and `0b853288`.
- `git merge-tree --write-tree feaabe3f 0b853288` gives `48d31e72e955926a01f41c5aa294774bddf75eda`, which equals `55405e7e^{tree}`. The command exited with rc 0 (no conflicts).
- The merge base is `cd4a7963`. QC changed 447 paths and Ember changed 843. **They share no path** (`comm -12` is empty).
- QC's Dart files are `brain_quick_controls.dart`, `oi_conversation.dart`, `living_composer.dart` and `brain_quick_controls_test.dart`. Ember touches none of them. QC does not touch `oi_sources.dart` or any Ember file.
- The cherry-pick `b07bd496` has the same patch-id as `582a2734` (`00b1ea24...`). It touches only the two named files (+73 lines).
- The art assets are the same at `0b853288` and HEAD (`git diff --stat` on assets is empty).

## 2. b07bd496 (IC1-03) (read and reasoned; tests ran)
**How `switching` is derived:** `brainControls['switch']['pending'] == true || brainStatus['switching'] == true`.
- `brainControls` is `brain_health.controls`.
- On the worker side (`worker_bridge.py:635-652`), `pending = _restart_pending() and _switch is not None`. The gate opens only on positive evidence: the host marked the request DONE or REFUSED_*, the host is not alive, or `RESTART_GATE_S` (600 s) expired. Opening the gate clears `_switch` (IC1-01). A restart/stop/start also clears `_switch` (line 734).
- The host's `reconfigure()` runs synchronously inside the loop, and `finish_request()` runs right after it (`ws_brain_host.py:566-574`). So DONE is written after the start or calibration completes, whether that ends in READY, DEGRADED or FAILED.
- Conclusion: the worker flag cannot stay stale for longer than one poll after the host finishes, and never longer than 600 s.

**D-1 consistency:**
- STOPPING, STOPPED, RELEASE_WAIT, LOADING and CALIBRATING show as Initializing "Switching Brain" while the worker confirms a user-requested switch the host has ACCEPTED. That reload is a genuine (re)start, and it is bounded by DONE or the gate. I judge this consistent with D-1.
- WAITING_FOR_GPU and WAITING_FOR_LEASE show the FCV-10 "Waiting for GPU" (unavailable). This is correct.
- A switch that ends FAILED: the host writes DONE, `pending` becomes false, and the next poll re-reads the masked status (R2-01), so the normal FCV-10 path applies. The failure is **not hidden** after the switch ends.
- Inside the short window before DONE, a FAILED host is presented wrongly (F-2 below).

**Interaction with the QC mask (`oi_conversation.dart:285-292`):**
- The mask rewrites READY to STARTING with `switching: true` only while `pending` is true. It is removed on the first poll after `pending` clears.
- The companion's switching branch runs before the readiness branch, so the mask never conflicts with it.
- The `brainStatus['switching']` term is redundant: `refreshStatus` always refreshes health after status, so `brainControls` is never older than the mask. The term can also stick (F-1).

**Is the test meaningful?** Yes, partly.
- Without the fix, its first post-switch assertion fails: READY plus pending would read as idle, and the test expects initializing. So it catches regressions.
- It checks STOPPING as Initializing, WAITING_FOR_GPU as "Waiting for GPU", and that the end of the switch returns to idle.
- Its fixture leaves out the real worker's `state: RECOVERING` and `explain` during a switch. As a result, the FAILED step goes down a different path than in production, and that step asserts only "not initializing / not idle" (F-2).
- It does not cover the `brainStatus['switching']`-only path.

## 3. Combined behaviour (read)
- **Success hold:** it only replaces an `idle` result, and the switching branch returns initializing or unavailable. A switch inside the 4 s hold therefore takes priority over the celebration, which is correct. A switch request also requires `!busy`.
- **BRAIN_RESTARTING turn refusal** (`oi_conversation.dart:586-598`): this adds a system message and sets `lastError`. It does not change `companionState` and creates no finished URI turn. The companion stays "Switching Brain" and does not celebrate. This is correct.
- **Owned disposal:** `OiCompanionSource.dispose` cancels the timer and removes its listener, and QC does not touch `living_app.dart`. The new test disposes its source.
- **Tests changed by the merge** (all on the Ember side relative to the base, and all already part of the Ember qualification):
  - `ui_v2_test.dart`: the installed design count goes from 11 to 12.
  - `companion_orb_test.dart`: the distinct-shader check now covers only shader identities, and asserts that Ember does not use a shader.
  - `voice_presence_test.dart`: Ember maps to the solar table.
  - `ws_integration_test.dart`: +85 lines (additions).
  - These follow from adding a 12th, non-shader design. None of them weakens an existing check for the other designs.
  - `brain_quick_controls_test.dart` is unchanged by Ember.

## 4. Gates evidence (read, `D:/uri-dev/uri-integ-live/gates-e/`)
Every file's first line is `HEAD=b07bd496c31004593ff6e508a054a739b43ef6d1`.

| Gate | Result |
|---|---|
| pytest oi+ws | 784 passed, 23 skipped (same as QC final) |
| ws_frozen_check | `"unapproved_protected_changes": []`. The file holds only the last 3 lines of the JSON (F-3) |
| flutter analyze | 5 issues, all info, 0 errors/warnings; rc=1 because infos are present. QC had 4; the extra one is Ember's `ember_transparency_test.dart:15` unnecessary_import |
| full flutter test | 846 passed, 5 skipped, rc 0. This reconciles: Ember 827 + QC 18 new tests + IC1-03 1 = 846 |
| release build | `uri_ui.exe` built, rc 0 |
| tgates | `all_pass: false`. The only failure is `clips/depleted/pass/T4_matte` (matte fringe 14 px). `clips` and `blink` are byte-equal to the Ember qualification's `evidence/tgates/transparency_gates.json`, so this is the carried owner decision |

**Ran myself:**
- `flutter test --no-pub test/living/companion_initializing_test.dart test/ws/ws_integration_test.dart test/living/brain_quick_controls_test.dart test/living/ui_v2_test.dart` gave **98 passed, "All tests passed!", exit 0** (`flutter_run.log` in this folder).

## 5. Licensing (OD-2)
- OD-2 is **OPEN**, according to `OD2_licensing_investigation.md`.
- The owner's recorded answer is "I hold rights / will license", and the repo cannot verify it.
- The reference sheet is probably Gemini-generated and appears to derive from a third-party Fiverr illustration. No licence, receipt or attribution exists in the repo.
- The shipped atlases are pixel derivatives of that sheet, with the artist signature and the Gemini mark inpainted out.
- **History check (ran):** all 15 of these commits are ancestors of b07bd496 and not of feaabe3f, so they lie in `feaabe3f..b07bd496` (54 commits): `8a1438ec` (the `docs/companions/fire/reference/**` sheet, the Fiverr screenshot, video frames and PROVENANCE), `8a585108`, `90f0f8a2`, `fce51708`, `a86ed350`, `1fcddab3`, `9933ca2b`, `90ae2248`, `73e84a6d`, `3a09d438`, `e792ddc8`, `6adf8fbf`, `23fb2878`, `269821cd` and `0484afdc` (the reviewer packs and `before_after.jpg`).
- The HEAD tree has no `docs/companions/fire/reference/` files (0).
- No remote-tracking branch contains `8a1438ec` or `b07bd496` (as of the last fetch).
- **Pushing b07bd496 would publish the reference art and the reviewer packs in history, plus the derived atlases in the tree.** This needs an OD-2 owner resolution, as AC-12 and handoff §11 require.

## Findings

| ID | Sev | Location | Failure scenario | Fix |
|---|---|---|---|---|
| F-1 | LOW | `oi_sources.dart` `_derive`: `\|\| c.brainStatus['switching'] == true` | The masked status (`switching: true`) is replaced only by a successful `brain_status` re-read in `refreshHealth`. If that re-read keeps throwing or timing out while `brain_health` succeeds, the companion keeps showing "Switching Brain" (Initializing) after the worker reports `pending: false`, even if health says READY or STOPPED. The QC header has the same pre-existing exposure. The term adds nothing, because `brainControls` is always at least as fresh as the mask | Derive `switching` from `brainControls['switch']['pending']` only. Optionally add a test with a pending=false health and a stale masked status |
| F-2 | LOW | `oi_sources.dart` switching branch, `brainNotReadyPresentation(hs, ...)` for `hs == 'FAILED'`; fixture in `companion_initializing_test.dart` | `brainNotReadyPresentation` ignores the `hs` it is passed and uses `health['readiness']`. The host switch has no FAILED case. During a switch the real worker reports `state: RECOVERING` (`worker_bridge.py:637-641`), so a readiness of STOPPED or UNKNOWN is turned into STARTING. A FAILED host inside the switch window is therefore shown as working "Starting Brain", which reads as a start rather than a failure. The window is short because the host writes DONE immediately after `reconfigure()` returns. The test misses this: its fixture lacks `state: RECOVERING` and only asserts "not initializing, not idle" | Map `hs == 'FAILED'` explicitly, e.g. `brainNotReadyPresentation('FAILED', {...c.brainHealth, 'readiness': 'FAILED', 'state': null})`. Make the fixture emit `state: RECOVERING` and the switch explain while controls are pending. Assert `CompanionState.error` / "Brain failed to start" |
| F-3 | LOW (evidence) | `gates-e/ws_frozen_check.txt` | The file holds only the HEAD line and the last 3 lines of the JSON. The checked file set and overall verdict cannot be audited from it | Store the full frozen-check output |
| F-4 | INFO | Switching branch, GPU wait | The "Waiting for GPU" detail shows the worker's switch explain ("Switching the Brain to X. It reloads...") instead of the GPU text, because the worker overrides `explain`. Headline and state are correct | Optional |
| F-5 | INFO | Switching branch, STOPPING/RELEASE_WAIT | Outside a switch, FCV-10 shows "Brain stopping" or "Waiting for GPU memory" for these states. During a switch they show Initializing. I judge this D-1 consistent, since it is a requested, worker-confirmed reload bounded by DONE or the 600 s gate. Recorded so the owner can see the interpretation | None, unless the owner disagrees |

## Ran vs read
- **Ran:** the HEAD and parents check; merge-tree versus the tree; the overlap of the two changed-path lists; the patch-id comparison; the asset diff; the ancestry checks for the 15 OD-2 commits; the remote-branch containment check; the tgates JSON comparison with the Ember qualification; the QC test count; and the 4-file flutter test (98 passed).
- **Read:** the b07bd496 diff; `oi_sources.dart` (`_derive`, `brainNotReadyPresentation`); `oi_conversation.dart` (refreshStatus/refreshHealth, the mask, send refusal, brainControls); `worker_bridge.py` (gate, switch, controls); `ws_brain_host.py` (run loop, reconfigure/finish_request, failure states); the QC integration receipt; the Ember receipt; the gate logs; and the OD-2 report.
- **Not verified:**
  - Live switch behaviour. Per the instructions I launched nothing, and that affects only F-2's window size.
  - `brain_health.assess` readiness values during a failed switch. These were inferred from the code path, not run.
  - The full frozen-check content (F-3).
  - None of these changes the verdict.
