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
  reviewers said they could not tell Ember from the painting, and scored the two identically.
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
| Mapping (`oi_sources.dart`, `brainStartingDetail`; revised after review R3-01/R3-02) | Initializing only when both Brain snapshots agree on a normal startup:<br>- the polled runtime state is `STARTING`, `LOADING` or `STOPPED`;<br>- the newer `brain_health` readiness is `STARTING`, `LOADING` or `READY`, or `STOPPED` with a running host in `STARTING_HOST`, `STARTING`, `LOADING`, `CALIBRATING` or `WAITING_FOR_LEASE`;<br>- no running host reports `FAILED`, `STOPPED`, `STOPPING`, `RELEASE_WAIT` or `WAITING_FOR_GPU`.<br>Detail: "Brain loading", or "Waiting for the GPU" for the lease queue. Everything else that is not READY stays `unavailable` with "Brain <state>": FAILED, ARTIFACT_MISSING, IDENTITY_MISMATCH, FOREIGN_INSTANCE, DEGRADED, unknown states, GPU contention (`WAITING_FOR_GPU`, which needs the user) and a host that is stopping. A failure in either snapshot is never shown as Initializing. |
| Priority | Composite: below `unavailable` and every activity, above `idle`. It never hides a failure or a request. |
| Ember | New clip `kindling` (calm, low flame, eyes half lowered), cross-fading normally into idle |
| Solar, Sakura, Lunar, Moonlit, classic orb | A dimmer, calmer idle, through the single-source `rnd/companions/state_tables.py` (revision 3) |
| Tests | `companion_initializing_test.dart` (8 tests: mapping through the real conversation, snapshots that disagree, priority, look ordering) plus the existing every-state tests |
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

TBD-LIVE

## 7. Performance and regression (Phase 7)

TBD-PERF

## 8. Independent acceptance (Phase 8)

TBD-REVIEW

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
