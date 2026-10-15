# Ember V2 - Final Qualification Report

Milestone FIRE-COMPANION-V2-20261015.

- **Branch:** `phase/fire-companion-v2-20261015`, in worktree `C:\Users\cheta\Development\uri-fire-companion-v2`.
- **Base:** cut from V1 `89ccf461`.
- **Status:** local only. Not merged, not pushed, not deployed.
- **V1:** unchanged on its own branch.

## 1. Summary

| Area | Result |
|---|---|
| Approach | Painting-derived 2.5D. The four reference panels are cut into layers and animated: flame flow and sway, breathing, smoke, rising painted sparks, and a face rig (lids, gaze, borrowed mouths). The result plays through V1's proven sprite player. Blinks are added at runtime. |
| Visual fidelity (>= 90 %, AC-2) | **NOT MET.** Final blind critique (CP8, two fresh reviewers), means: idle 83.5, joyful 82.0, fierce 80.5, depleted 82.5. Anchors in the same CP8 session: V1 33-36, the painting blurred 81-83, the painting itself 100. The owner's AI redraw was last scored in CP2-CP4, at about 37-60 per reviewer (means about 42-56). The threshold was not lowered. AC-2b was refined during the work; under the original rule every session is miscalibrated (section 5). |
| Living animation | Done. There are 9 clips; 8 ship, and fierce is rendered but not shipped. Every clip loops seamlessly: the last-to-first step is the size of a normal frame step (checked by reviewer R2 on the shipped atlases). Runtime blinks are irregular, verified live (gaps 0.5-6.5 s, including double blinks). Painted sparks rise. The animation itself costs no measurable fidelity (CP7/CP8). |
| Functional states | All 9 `CompanionState`s are mapped; the mapping table is unchanged. Fierce is animated and scored but not mapped to any state. |
| Success signalling (F-SUCCESS) | **Repaired** in `oi_sources.dart`. Live run at `a86ed350`: greeting -> success; approved task SETTLED_VERIFIED -> success -> idle. The later refinement (review R1-01) ends the hold on a failed or new turn; it is covered by a test that fails on the pre-repair code, and was not re-run live. |
| Voice-settings errors (PRE-1) | **Repaired** in `voice_input_settings.dart`. The regression test failed before the fix and passes after it. Live: 0 framework assertions in V2 runs 1-3, which have complete logs, against 12 in V1. |
| Startup presentation (F-STARTUP) | **Not repaired; owner decision.** A shared `CompanionState.starting` is needed (section 8). |
| GPU / VRAM (AC-7) | GPU 3D is 0.14-0.29 % against Solar's 3.8-11 %, i.e. 1.3-7.7 % of Solar: MET. VRAM is +33-36 MB over Solar and 2.5-6.9 MB under V1: bounded. Atlases are 9.7 MB on disk (V1: 14 MB). |
| Brain coexistence | No evidence that Ember slows the Brain. A clean A/B comparison is **INCONCLUSIVE**: the Brain was demoted, there were 2 samples each, and another session's processes were present. |
| Live Windows qualification | Real app, with our own Brain under the GPU lease. PASS: first-time user, returning user, journeys 1-3 and 5-9. Journey 4 (wake phrase) is NOT AVAILABLE. Journey 10 (recovery) is **BLOCKED**: a parallel session took the lease. |
| Tests | Full `flutter test` on the working tree after the R1 repairs (`evidence/tests/full_flutter_test_summary_r1.txt`): **580 pass / 5 skip / 0 fail**. V1 head: 567/5/0. R2 re-ran the targeted suites on commit `1fcddab3`: 99/99. |
| Independent review | Fresh-subagent audit. R1: ACCEPT WITH FINDINGS, 9 findings, all repaired. R2: ACCEPT WITH FINDINGS, documentation findings only, repaired in this revision (section 9). |
| Independent acceptance | **BLOCKED.** The lifecycle driver needs the Claude CLI, which is logged out (`evidence/review/claude_cli_auth_status.txt`). |

## 2. Research and selected architecture

`01_RESEARCH_AND_APPROACH.md` compares five approaches:
- A: V1-style 3D, improved;
- B: painting-derived 2.5D, pre-rendered;
- C: B, but real-time in Flutter;
- D: Live2D, Spine or Rive;
- E: AI video.

**B was selected** as the smallest sound solution:
- no new dependencies;
- no new runtime rendering path;
- V1's player, manifest, failure/retry logic, frame suspension and tests reused;
- one small addition, the runtime blink overlay.

The others were rejected:
- **C** would move GPU cost towards Solar's level for no fidelity gain.
- **D** brings a dependency, licensing and GUI-only authoring.
- **E** was measured: its redraw fidelity is low.

## 3. Implementation (diff `89ccf461..HEAD`)

**Art pipeline** (`companion_art/fire_v2/`, new):
- `layers.py`: background plate; minimum-alpha matte; solid head, eyes and body; spark-safe smoothing; inpainting of the
  signature and the generator mark.
- `animate.py`: flame turbulence, sway and smoke under one cap; breathing or a rigid hop; head tilt; puppet handles;
  face rig; rising sparks.
- Also new: `rig.json`, `expressions.json`, `render_clips.py`, `export_v2.py`. Output is in V1's atlas format, plus
  eye offsets and a blink atlas.

**App** (`uri_ui/`):
- `ember_companion.dart`:
  - manifest blink data and eye offsets, with per-clip validation;
  - `EmberBlinker` and `EmberOverlay`;
  - the blink-atlas lifecycle;
  - no overlay during cross-fades;
  - the still tile never loads lid patches.
- Assets: 8 atlases, `blink.webp` and the thumbnail.
- **Accepted files changed, with reasons:**
  - `integration/oi_sources.dart` (F-SUCCESS). This affects every companion, because any companion can show `success`.
  - `screens/settings/voice_input_settings.dart` (PRE-1).
- Tests updated: `ember_companion_test.dart`, `ws_integration_test.dart`, `live_voice_test.dart`.

**Scorer** (`scripts/fire_companion/`):
- `fidelity_score.py --aligned`;
- `score_v2.py`;
- `critique_pack_v2.py`.

**Unchanged:** frozen Core, Runtime v1 and the Brain. No change was made in any other worktree.

## 4. Four-state visual comparison and animation

- **Comparison:** `evidence/demos/four_state_comparison.jpg`, showing the reference, V2 as the app shows it, and V1
  for each state.
- **GIF demos:** `evidence/demos/*.gif`, all 9 clips, 12 fps previews.
- **Real app:** screenshots in `evidence/live/run4_first/`.

## 5. Fidelity (AC-2)

**Method** (`03_FIDELITY_METHOD.md`):
- blind packs, with new fresh reviewers each checkpoint (14 in total);
- 7 dimensions;
- calibration anchors;
- V2 scored as its weakest frame;
- pass rule: mean >= 90 % and no reviewer below 85.

**Calibration rule (AC-2b) was refined during the work.**
- The pre-registered rule required every anchor within +-10 of priors taken from V1's rubric (V1 41-51, video
  63-67). Under that rule, **every session CP2-CP8 is miscalibrated**: both weak anchors scored 15-25 lower under
  the new rubric.
- From CP3 onward, validity was checked against a top anchor instead (the sharp painting scored 98.6-100 every
  time).
- This change is recorded in `03_FIDELITY_METHOD.md` ("Refinement of AC-2b"). The pass threshold for V2 never
  changed, and the verdict is NOT MET under either rule.

**Results** (two-reviewer means, recomputed from the raw scores by `evidence/fidelity/decode_raw_scores.py`):

| Checkpoint | Change | V2 mean range | Notes |
|---|---|---|---|
| CP1 | Cut-out only, automated scorer | - | Exposed registration fragility; `--aligned` added |
| CP2 | First animation | 74-85 | No top anchor |
| CP3 | Matte, sparks, feet and pool repairs | 77-80 | Top anchor added |
| CP4 | Larger pool, motion cap, breathing | 74-78 | Two reviewer claims checked and refuted |
| CP5 | Diagnostic: unanimated cut-out | 71-75 (cut-out alone 69-81 per reviewer) | |
| CP6 | Card presentation | 72-79 | No gain; CP5's explanation corrected |
| CP7 | Single full-resolution frames; rigid hop; one motion cap | **83.5-85.8** | The format confound was real |
| CP8 | Crisp sparks, solid robe | **80.5-83.5** | Final |

**Findings:**
1. V2 sits at the level of "the painting, blurred".
2. Every V2 frame scores the same as the unanimated cut-out: the animation costs nothing measurable.
3. The remaining gap is the cut-out shown on the app's near-black canvas. Reviewers named:
   - a darker surround;
   - the crest swirl reading dark;
   - a paler robe;
   - fewer sparks in any one frame;
   - the removed signature.
4. The automated scorer, used for regression only, gives V2 frames 89.8-128.4 on V1's scale. That range comes from
   construction, not from fidelity.

**Integrity notes:**
- Raw letter-level scores are kept in `raw_letter_scores.json`, transcribed from the reviewers' hand-back messages.
  The transcripts were not kept by the harness.
- Three reviewer label mix-ups affected anchors only. They are disclosed in `cp3_RESULTS.md` and `cp4_RESULTS.md`.
- Earlier range errors are corrected, with notes, in `cp5`, `cp6` and `cp8_RESULTS.md`.

## 6. Performance (AC-7)

`03_MEASUREMENTS_V2.md`: controlled harness, two runs each, with Brain residency recorded.

| | GPU 3D median | Dedicated VRAM median | Frames/s |
|---|---|---|---|
| V2 | 0.14-0.29 % | 142-143 MB | 46-48 |
| V1 | 0.14-5.5 % | 145-149 MB | 44 |
| Solar | 3.8-11 % | 107-109 MB | 137-148 |

The high ends of the V1 and Solar ranges occurred while another session's Brain was serving.

## 7. Live Windows qualification (AC-8)

`05_LIVE_QUALIFICATION_V2.md` covers four runs, all kept: aborted, returning user, blocked by a harness defect, and
full.

GPU-lease instruction (OD-8):
- No turn was ever sent to another session's Brain. Run 1 and run 4's recovery step were stopped when our launcher
  attached to the parallel session's Brain.
- Our own Brain host was always stopped gracefully, releasing the lease.
- Harness guards were added: the lease must be FREE and no other llama-server running, and ownership is proven by
  the server pid.

## 8. Findings and limitations

| ID | Finding | Status |
|---|---|---|
| AC-2 | Fidelity >= 90 % not met (80.5-83.5) | **Open: owner decision** |
| F-STARTUP | During Brain loading, a first-time user sees the depleted, sad Ember ("Unavailable - Brain LOADING") | Open. Proposal: add `CompanionState.starting`, derived from Brain LOADING/STARTING, plus a kindling clip. This changes the shared contract, so it is an owner decision. |
| PRE-2 | `OiConversation.monitorTick` notifies after dispose when a status probe is in flight at teardown (`oi_conversation.dart:269`) | Open. Canonical code, pre-existing, seen only at test teardown. |
| HARNESS-1 | The launcher attaches to any running Runtime v1 server, so on a shared machine a test run can reach another session's Brain | Open. Guarded in this harness; the launcher itself is unchanged. |
| J10 | Live recovery journey | BLOCKED (lease contention) |
| COEX | Brain A/B comparison | INCONCLUSIVE |
| R1-01 live | The success-hold refinement is test-covered but not re-run live | Open (low) |
| UX-1 | The prompt bubble overlaps the status label | Pre-existing; not in scope |
| Wake word | No recogniser exists in canonical URI | NOT AVAILABLE |
| Licence (OD-2) | The reference and all derived art are committed on local branches only. Any push needs OD-2 settled, and possibly history surgery. | Open |
| Presentation | V2 shows a soft painted backdrop pool behind Ember, chosen for fidelity on the dark canvas | For owner review |

## 9. Independent review

There were two rounds, each by a fresh general-purpose subagent that worked read-only on the exact commit given.
Both ran tests and checked evidence themselves.

| Round | Commit | Verdict | Findings | Disposition |
|---|---|---|---|---|
| R1 | `279a961e` | ACCEPT WITH FINDINGS | 4 MEDIUM, 5 LOW: success hold; partial export; raw scores; AC-2b disclosure; overlay during fade; blink validation; evidence wording; ranges; tests | All repaired in `1fcddab3`. Verified by R2. `evidence/review/R1_findings_and_repairs.md` |
| R2 | `1fcddab3` | ACCEPT WITH FINDINGS | 1 MEDIUM, 5 LOW, all in documentation: AC-2b missing from this report; stale numbers; wrong checkpoint ranges; mixed-source summary claims; live F-SUCCESS predating R1-01; this section unfinished | Repaired in this revision. No code defects. |

The final commit has not been re-reviewed after the R2 documentation repairs. **Lifecycle acceptance is BLOCKED
(OD-4)**: the Claude CLI is logged out. These audits are not a substitute for it.

## 10. Recommendation

Do **not** integrate as "meets spec":
- AC-2 is not met;
- independent lifecycle acceptance is BLOCKED.

V2 is still a large step from V1:
- blind fidelity of about 82, against about 40;
- the functional, performance and live checks pass, apart from the BLOCKED, NOT AVAILABLE and INCONCLUSIVE items above;
- two lifecycle defects fixed (F-SUCCESS and PRE-1).

Options for the owner:
1. **Accept V2's measured fidelity (about 82 %) and integrate as Ember.** This first needs:
   - an explicit owner waiver of AC-2;
   - decisions on OD-2 (licence and git history) and on the backdrop-pool presentation;
   - lifecycle acceptance once the Claude CLI is logged in.
2. **Keep it on the branch and commission a follow-up:**
   - F-STARTUP: a `CompanionState.starting` contract change;
   - a full-resolution, single-frame study of a "painting card" presentation (CP6 tested it only in strips).
3. **Keep V1 and V2 as research.**
