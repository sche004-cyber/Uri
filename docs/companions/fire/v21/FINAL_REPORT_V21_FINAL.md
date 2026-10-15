# Ember V2.1 - Final Qualification and Integration Report

## Pass details

| | |
|---|---|
| Owner task | "URI Ember V2.1 - Final Qualification and Integration" (2026-10-15) |
| Outcome | **B.** A preserved, qualified candidate with its remaining blockers stated. It is not integrated. |
| Branch | `phase/ember-v21-final-20261015`, local only. It was cut from V2.1 `28149905`, which stays on `phase/fire-companion-v21-20261015`. |
| Final commit | see the "Commits" table (the last row is the report commit) |
| Canonical | `sche004-cyber/Uri` `integration/git-sync-20261008` = `1b5423bc` (re-checked by `ls-remote`, unchanged) |
| UI V2 candidate | `316e6475`, still **BLOCKED** (`uri-ui-v2-final-qualification-20261013/FINAL_REPORT.md`) |

## 1. Phase 1: the reconciled starting state

| Item | Found |
|---|---|
| V2.1 branch | Clean at `28149905`, local only |
| V2.1 review R1/R2 findings | All repaired or disclosed (`evidence/review/`) |
| UI V2 | Candidate `316e6475`, BLOCKED: its strict frozen-integrity check fails on canonical as well (owner decision pending); formal lifecycle 0 rounds; native interaction and visual comparison not qualified. No newer UI V2 commit. |
| Canonical | `1b5423bc`; nothing from Ember published |
| Independent reviewer | Claude CLI `loggedIn: false`. The Codex sandbox probe (skill-mandated, run again in this pass on a clean clone at `28149905`) refused both `powershell` and `cmd` with "blocked by policy", the same driver limit already on record. |
| GPU lease | Free at the start. Later held by another session's FCV regression chain, which this pass waited for and never touched. |

## 2. Fidelity (Phase 2)

- **Rounds of record:**
  - FP-21 Q2 (`evidence/fidelity/Q2_RESULTS.md`, from the previous pass) is unchanged.
  - The new proposed protocol is FP-21R (`08_FIDELITY_PROTOCOL_V21R.md`). It was locked and committed before its
    pack was built.
- **R1 was INVALID.** One reviewer transposed two answers. It is reported as is in `R1_RESULTS.md`; nothing was
  edited or dropped.
- **R2 (the replacement round) is valid** (`R2_RESULTS.md`):

| Measure (R2, mean of 3 reviewers) | Dark surround | Light surround |
|---|---|---|
| Ember character % | idle 88.9, joyful 89.2, fierce 90.8, depleted 83.3 | 73.9-78.9 |
| Original painting under identical transparent treatment, character % | **identical** (88.9 / 89.2 / 90.8 / 83.3) | identical (73.9-78.9; joyful 78.1 vs 78.3) |
| Ember presentation % | 68.8-73.3 | 58.8-60.4 |
| V2 as the app showed it, character % | 79.4-83.6 | - |

- **AC-F3, character >= 90 (owner requirement): NOT MET.** Only fierce on the dark surround reaches 90.
- **AC-F1R, relative presentation (proposed):** R = 1.000-1.007 passes as computed. It is **not meaningful**: all six
  reviewers said they could not tell Ember from the painting, and scored the two identically, apart from one 0.5-point difference on two items (R2 reviewer 3, joyful, light surround; review R6-5).
- **FP-21 AC-F1, absolute visual >= 90 (rule of record):** NOT MET. Dark: 77.5-83.8.

**What the evidence supports (corrected after review R3-04):**
- In still frames, the reviewers saw no difference between Ember and the unanimated painting given the same cut-out
  and presentation.
  - That control is close to Ember by construction: it uses Ember's layer alpha, with a mean pixel difference of
    0.8-5.1/255.
  - So this is weak evidence, and it says nothing about motion. Motion was last judged in Q2 (AC-F2 met).
- With Ember's transparent cut-out and presentation, neither Ember nor the painting reaches 90 % character:
  - dark surround: 83-91, depleted lowest because its smoke vanishes on black;
  - light surround: 74-79.
- This concerns this cut-out (matte, glow and haze). It does not show that no transparent artwork could reach 90.
- In the earlier opaque presentation, character was 92.2-93.1 (Q2).
  - Panel variance between rounds is about 5 points, so the size of the transparency cost is uncertain.
  - Its direction is consistent across P3, R1 and R2.

**Owner decision (not taken here).** Choose one:
- (a) measure character on the painted opaque view, which Q2 did and where it was met;
- (b) accept "equal to the painting under the same transparency" (the FP-21R proposal, or a variant of it); this panel cannot separate the two, so the evidence is weak;
- (c) fund a light-desktop treatment (F-LIGHT-1) and measure again.

The 90 % threshold was not changed, and no score was edited or removed.

## 3. Transparency (Phase 3)

Changes in this pass, all scoped to Ember:
- **Depleted haze** pool `[0.35, 0.95]` -> `[0.10, 0.60]`. The old pool read as a grey rounded rectangle on light
  desktops (`evidence/final/haze/`). New gates on the shipped stage:

  | Gate | Result |
  |---|---|
  | H1: nothing darkens a white desktop by 6 % or more outside the central circle | 0 px |
  | H2: corners | 0 |
  | H3: footprint | 11.4 % (was 44.7 %) |

- **`panel_feather` 20.** Painted light that reaches the panel edge (the ground glow under the feet) now fades instead
  of ending in a straight line.

Gates on the exported atlases (`evidence/final/transparency/transparency_gates.json`), every frame of all nine
shipped clips:

| Gate | Result |
|---|---|
| T0 painted, T1 border band, T2 ring, T3 opaque share, T5 blink patches | PASS, all clips |
| T4 dark-matte fringe | PASS for 8 of 9 clips. **depleted: 70 of 72 frames exceed the 5 px limit, at 7-14 px; the worst is 14 px at frame 8 (R4-N4). Gate unchanged.** Diagnosed: these pixels are the painted contact shadow under the feet. The source cut stores that shadow as near-black at alpha 0.2-0.4 (panel y 484-486), and the old wide haze used to cover it. It is not a premultiplication rim (`t4_depleted_contact_shadow_x6.png`). Recorded as a diagnosed gate failure for owner sign-off, not as a pass. |
| Flutter transparency test (real `EmberCompanion`, every clip including `kindling`) | PASS within the full suite |

- **Contrast sheets** over 7 backgrounds: `evidence/final/transparency/contrast_<clip>.jpg`.
- **F-LIGHT-1 (open, owner).** On light desktops, flames turn pale, painted outlines read hard and the robe's gaps show
  the desktop. This is shared by the painting itself under the same treatment. A real fix (for example a
  light-desktop backing) is a design decision and was not started.

## 4. Initializing state (Phase 4), owner-approved direction, implemented on this isolated branch

| Piece | Implementation |
|---|---|
| Shared state | `CompanionState.initializing`, label "Initializing"; not active and not waiting on the user |
| Mapping (`oi_sources.dart`; `brainStartingDetail` and `brainUnavailableDetail`; revised after reviews R3, R4 and R5) | **Which snapshot counts.** Two snapshots exist: the polled runtime state and the `brain_health` report. The worker stamps both with `checked_at`, and the newer one counts.<br>**Initializing** needs all of:<br>- the runtime is `STARTING`, `LOADING` or `STOPPED`;<br>- a newer health readiness is `STARTING`, `LOADING` or `READY`, or `STOPPED` with a running host in `STARTING_HOST`, `STARTING`, `LOADING`, `CALIBRATING` or `WAITING_FOR_LEASE`;<br>- no running host is `FAILED`, `STOPPED`, `STOPPING`, `RELEASE_WAIT` or `WAITING_FOR_GPU`.<br>**Health older than the status read:** only `STARTING` or `LOADING` count. **Either snapshot unstamped:** a `STOPPED` runtime counts only while a host is running.<br>**Details:** "Brain loading", or "Waiting for the GPU" for the lease queue.<br>**Everything else** that is not READY stays `unavailable`. Its detail names the newest known state; it never uses an older report, and never `UNKNOWN` over a known state. This covers FAILED, ARTIFACT_MISSING, IDENTITY_MISMATCH, FOREIGN_INSTANCE, DEGRADED, unknown states, GPU contention and a stopping host.<br>A failure in the newer snapshot is never shown as Initializing. |
| Priority | Composite: below `unavailable` and every activity, above `idle`. It never hides a failure or a request. |
| Ember | New clip `kindling` (calm, low flame, eyes half lowered), cross-fading normally into idle |
| Solar, Sakura, Lunar, Moonlit, classic orb | A dimmer, calmer idle, through the single-source `rnd/companions/state_tables.py` (revision 3) |
| Tests | `companion_initializing_test.dart` (11 tests: mapping through the real conversation; snapshots that disagree, stamped and unstamped; the unavailable detail; priority; look ordering) plus the existing every-state tests |
| Frozen Core / Runtime | Untouched (`evidence/final/boundary_check_final.txt`) |

**Open, F-START-GAP.**
- The launcher starts the UI, waits for its window, and only then starts the Brain host. In that gap the companion
  is truthfully `unavailable`.
- Closing it needs a launcher change, which is shared and not made here.
- The live run measures the gap (section 6).

## 5. UI V2 integration preparation (Phase 5)

`09_UI_V2_INTEGRATION_PLAN_V21.md`: read-only inspection of `316e6475`, plus a rehearsal merge in an isolated
detached worktree. It is not a candidate, and no UI V2 branch was changed.
- **Merge:** one test-file conflict.
- **Analyze:** 0 errors.
- **Suite:** 630 passed, 5 skipped, 1 failed. The failure is UI V2's pinned design count (11 -> 12 with Ember), an
  expected integration edit.
- **Initializing** needs no UI V2 file change.
- **F-SIZE-1 (open).** At UI V2's maximum companion size of 1.25, the host disc cuts about 6.5 % of Ember (feet and
  flame tip). At sizes 0.8-1.0 the cut is 0.3 % or less.

## 6. Live Windows (Phase 6)

- **What was run.** Real Windows app (production `main()`), real Core worker and the real Runtime v1 Brain,
  driven by automation.
  - The build was the code at `d12e70ed`.
  - Interaction was automated: Flutter tester taps and text input. **This is not a human usability study.**
  - Evidence: `evidence/final/live/` (raw observations, screenshots, runner logs, lease and host records).
- **Host.** Today's UI V1 host. UI V2 Companion Mode, the transparent floating window, is not available for live
  qualification (section 5).
- **GPU lease (OD-V21-1 terms).**
  - The runner started our Brain host only when the lease was FREE and no other `llama-server` was resident. It
    waited about 3.5 minutes while another session held the lease.
  - The driver counted only our own Brain: the server pid matched our host record (`our_brain: true`).
  - Our hosts were stopped through their own stop file at the end. Nothing of another session's was touched.

| # | Owner journey | Result | Evidence |
|---|---|---|---|
| 1 | Fresh install / first-time user | **PASS.** Fresh preferences (none stored), default Solar, shell in 14.8 s | `first-01` |
| 2 | Companion selection | **PASS.** Ember selected in Settings and stored | `first-02`, `first-03` |
| 3 | Preference persistence | **PASS.** Returning run: stored choice `ember`, Ember shown, blinks (5 in 25 s), Settings opened with no framework errors; flutter rc=0 | `run_returning_d12e70ed/` |
| 4-7 | Transparent floating window, dragging, click-through, scaling including 1.25x | **PENDING.** These need UI V2 Companion Mode. Static evidence only: transparency gates (section 3) and F-SIZE-1 | sections 3, 5 |
| 8 | Companion to Workspace | **PASS** (double click) | `first-10` |
| 9 | Companion to Dashboard | **PASS** | `first-11` |
| 10 | Idle, listening, thinking, speaking | **Partly.** Idle, thinking and speaking were observed on every reply. Listening has no source in this integration (no voice layer), so it was not exercised. | observations |
| 11 | Task completion and the joyful expression | **PASS.** Greeting reply: thinking -> speaking -> success. Approval -> task `SETTLED_VERIFIED` -> success -> idle after the hold | `first-09`, `first-13`, `first-14`, `first-15` |
| 12 | Brain initializing and ready | **PASS.** Unavailable while no Brain had started (the runner was waiting for the lease) -> **Initializing, "Brain loading"** about 12-13 s after our host started (launcher event 10:11:28.7; host override 10:11:29.0; first Initializing sample 10:11:41.0; review R6-1) (runtime `LOADING`, host `STARTING`) -> idle when ready, after 97 s of Initializing | `first-04`, `first-05`, `first-06`; `3c brain initializing` |
| 13 | Brain unavailable and recovery | **PASS.** Brain stopped -> depleted, "Brain STOPPED" -> request -> error shown -> host restarted -> reply "15" -> success. The look during the restart window was not captured, because the driver resets the sequence when it sends; this is disclosed, not rerun. | `first-16`, `first-17`, `first-18` |
| 14 | Returning user | **PASS** (as row 3) | `run_returning_d12e70ed/` |
| 15 | Switching between Ember and existing companions | **PASS.** Three alternating Ember / Solar pairs, each with a completed answer | observations |

**Limits of this live evidence (review R5-N5):**
- **Provenance.** The runner prints the commit before it starts (`d12e70ed`, kept as `runner_task_output.txt`).
  The flutter log and the runner log record no SHA themselves.
- **Code tested.** The run tested `d12e70ed`. The later R4 and R5 repairs change only the mapping for stale or
  unstamped snapshots. The recorded startup pairs map the same way under the final code (R5 section 3.3). Those
  repairs are proven by unit tests, not live.
- **The host-only path to Initializing was not demonstrated.** Our host process started at 10:11:28.7. The companion
  stayed depleted until the first Initializing sample at 10:11:41.0, about 12-13 s later, when the runtime already read
  `STARTING` or `LOADING`. The driver samples about every 2 s.
  - The likely cause is that the host had not yet written its first report (Python start plus a GPU census of about
    3.7 s).
  - This is not proven from the files. It is part of F-START-GAP.
- **Recovery was not fully healthy.** After the restart, the recovered reply took 7.6 s (about 2 s earlier). The
  restarted host ended `DEGRADED` (`DECODE_THROUGHPUT_LOW`) under GPU contention:
  - our UI, plus another session's `uri_ui.exe`;
  - the owner-authorized `-OverrideGpu`.
  The companion showed success, then idle, because the mapping follows the runtime state, which was `READY`. The
  journey passes for recovery and messaging, not for Brain speed. This is pre-existing behaviour.
- **A label overstates the state.** The record "10 recovered to idle" and `first-18-recovered-idle.png` actually show
  **success** ("Done"), within the success hold.

**Observations:**
- **The returning run saw another session's Brain.** The FCV recovery session's live run started its own Brain at
  10:17:27 UTC, on the shared Runtime v1 port, after our run had released the lease. Our returning run sends no
  turns. Its "initializing" reading reflected that foreign Brain loading. It is not evidence about our startup. This
  is the known pre-existing behaviour: Runtime v1 attaches to any server on its port.
- **F-START-GAP is real.** In both live sequences the companion was unavailable until a Brain host was running, then
  became Initializing.
- **Code version.** The live run used `d12e70ed`. Repair R4-N1/N2 (`5d05f4dc`) changes only the corner cases of stale
  snapshots, and is covered by unit tests. The normal startup path recorded here maps the same way: runtime `LOADING`
  with a running `STARTING` host is still Initializing.

## 7. Performance and regression (Phase 7)

**Performance**, under our own GPU lease. Evidence in `evidence/final/perf/series/` (`summary_table.md`,
`lease_checks.txt`).
- **Lease checks:** 12 of 12 passed, before and after each run: the lease was held by our process tree and no Brain
  was resident.
- **Waiting:** the series waited about 10 minutes (617 s, from `census_queued.json` to the ACQUIRED event in the machine lease history) for another session's Brain run to release the lease. It held the lease for 6.6 minutes.
- **Builds:** the final Ember and Solar perf executables were built from `0484afdc`, whose atlases and companion
  tables equal the final ones. The perf app does not use the Brain mapping. V2 Ember is the earlier build from
  `b73bd26c`.

| Run (no Brain) | GPU 3D median (max) | Dedicated VRAM median (max) | Frames/s | Frame p50 / p99 |
|---|---|---|---|---|
| Ember final r1 / r2 | 0.28 % (0.60 / 1.16) | 147.2 MB (183.5) | 45.2 / 48.9 | 1.67 / 3.15 ms; 1.57 / 2.94 ms |
| Ember V2 r1 / r2 | 0.28-0.29 % (1.53 / 1.01) | 147.4 MB (175.4) | r2: 48.4 | r2: 1.61 / 2.89 ms (r1 timings were overwritten, see below) |
| Solar r1 / r2 | 6.54 / 7.11 % (8.9) | 110.7 / 108.7 MB | 154.6 / 160.0 | 1.69 / 2.93 ms; 1.71 / 3.11 ms |

- **AC-P1 met.** Ember uses about 1/25 of Solar's GPU, and its median VRAM equals V2's. Ember's VRAM peak is 8 MB
  higher than V2's (183.5 against 175.4), from the extra `kindling` clip. Decoded atlases are capped at about 42.5
  MiB by the existing cache.
- **State transitions** (frames in the first 10 after each state change, Ember r1 / r2):
  - The app's cold start (frame 0) is excluded (review R6-2).
  - p99 8.7 / 4.6 ms; worst frame 8.7 ms (r1, entering `speaking`) and 4.6 ms (r2). Steady-state p99 is
    3.1 / 2.9 ms.
  - The cold start itself, frame 0 of each run, takes 53 / 34 ms.
  - Initializing frames: p50 1.6-1.7 ms, p99 2.8-3.0 ms.
  - So a state change costs at most a few milliseconds on one frame, not a sustained cost.
- **Defect in the measurement script.** The V2 build's frame timings for r1 were overwritten by r2: that old build
  writes to a fixed folder. r1's GPU samples are valid. Its output folder (`evidence/perf/_incoming$3`) was untracked. Its contents (r2's timings and screenshots) were moved
  into `series/v2_ember_r2/` and are now committed there. No tracked file was changed (review R6-8).

**Brain throughput** (live run, our own Brain, alternating, `evidence/final/live/`):

| Pair | Ember on screen | Solar on screen |
|---|---|---|
| 1 | 112.2 tok/s (draft acceptance 48/78) | 142.9 |
| 2 | 138.6 | 141.1 |
| 3 | 132.4 | 135.8 |

- Excluding Ember's first turn, whose lower draft acceptance was also seen in V2.1 run 1, Ember averages 135.5 and
  Solar 139.9. That is no material difference, but 3 pairs cannot exclude 2-5 %.
- **Memory demotion:** the Brain's dedicated VRAM stayed at 14,982-15,009 MB while it was ready. No demotion was
  observed in the samples.
- The restarted Brain later ran DEGRADED under GPU contention (section 6, limits).
- No stress test was run.

**Regression:**
- Full Flutter suite at the final commit: **603 passed, 5 skipped, 0 failed** (602 at `06370431`; R6 added one test) (`evidence/final/full_flutter_test.log`;
  the header records the base commit and working tree).
- Rehearsal on UI V2: section 5.
- Boundary check: no frozen or protected path changed in `1b5423bc..HEAD` (`evidence/final/boundary_check_final.txt`,
  regenerated at the final commit).
- **History disclosure (review R3-08).** The intermediate commit `e43e97a7` fails the full suite: the hand-edited
  orb tables disagreed with `rnd/companions/state_tables.json`. `7baefb17` repaired it through the single-source
  generator. Every later commit passes.

## 8. Independent acceptance (Phase 8)

**Formal lifecycle acceptance: BLOCKED.** No driver-counted independent reviewer is available:
- **Codex (primary):** the skill's sandbox probe on a clean clone failed. `powershell` and `cmd` were both "blocked
  by policy", which is the known Windows driver limit.
- **Claude CLI (fallback):** `loggedIn: false`.
- No authentication was bypassed and no session was created on someone else's credentials.

**Imported independent reviews.** These are separate read-only Claude agents with no implementation authority,
given requirements and repository state. They are not counted by the driver, and under owner decision D1 they
cannot give VERIFIED or permit canonical integration.

| Round | Commit | Verdict | Outcome |
|---|---|---|---|
| R3 (whole diff since V2.1) | `0484afdc` | REVISE (1 HIGH, 4 MEDIUM, 7 LOW) | The HIGH (Initializing from inconsistent Brain snapshots) and the MEDIUMs repaired or disclosed. R3-05 (F-START-GAP) stays open as an owner decision (`R3_repairs.md`; review R6-3). |
| R4 (recheck) | `d12e70ed` | ACCEPT WITH FINDINGS (9 LOW) | Repaired (`R4_repairs.md`). Three rows were marked repaired before the work was done; R5 found this, and the history is kept. |
| R5 (recheck) | `5d05f4dc` | REVISE (1 MEDIUM: false repair claims; 5 LOW) | Repaired (`R5_repairs.md`) |
| R6 (final recheck) | `b4ff2ed2` | ACCEPT WITH FINDINGS (8 LOW, no HIGH or MEDIUM) | Repaired in the following commit (`R6_recheck_b4ff2ed2.md`, `R6_repairs.md`) |

Blind fidelity reviewers (FP-21R R1, R2) are separate agents and appear in section 2.

## 9. Licensing and publication

- **OD-2 is unresolved.** The reference art entered history in V1 `8a1438ec`. It is on no remote; everything stays
  local.
- The derived atlases and reviewer packs also stay local.
- Nothing was pushed.

## 10. Integration readiness (Phase 9)

**NOT ELIGIBLE.** Integration is blocked by:
1. UI V2 is not independently qualified.
2. The fidelity criteria are not satisfied or approved.
3. Licensing (OD-2) is unresolved.
4. There is no driver-counted independent acceptance.
5. The UI V2 live compatibility checks have not been run.

No integration candidate was cut, and there is no integration receipt.

## 11. Owner decisions needed

1. **Fidelity:** option (a), (b) or (c) in section 2.
2. **F-LIGHT-1:** whether to invest in a light-desktop treatment.
3. **Depleted:** sign off the contact shadow (T4) and the tighter haze, or adjust them.
4. **F-SIZE-1:** the size cap for model companions in UI V2.
5. **F-START-GAP:** allow the launcher change.
6. **OD-2 licensing.**
7. **Reviewer access:** log in the Claude CLI, or choose a Codex sandbox configuration, so that a driver-counted
   independent acceptance can run.
8. **UI V2:** its own frozen-integrity decision and qualification. Ember's Stage 2 waits on this.

## Commits (branch `phase/ember-v21-final-20261015`, local only)

| Commit | Content |
|---|---|
| `e43e97a7` | Initializing state, `kindling`, haze pool, `panel_feather`, atlases. Fails the suite (orb tables; review R3-08). |
| `6adf8fbf` | FP-21R protocol locked before its pack |
| `23fb2878` | R1 prompts, stored before the round |
| `7baefb17` | Initializing rows through the single-source state tables (suite passes from here on) |
| `269821cd` | R1 INVALID, recorded; R2 prompts and key |
| `0484afdc` | R2 results; UI V2 integration plan and rehearsal |
| `d12e70ed` | Review R3 repairs (the live runs used this code) |
| `5d05f4dc` | Recheck R4 repairs; live evidence |
| `06370431` | Recheck R5 repairs; final report sections 6-8; perf series. **The final code is this commit.** |
| `b4ff2ed2` | Docs only: boundary check at `06370431`, and this table |
| final (R6 repairs) | A stamped end-to-end test (R6-7, test only); R6 wording repairs; the R6 record |
