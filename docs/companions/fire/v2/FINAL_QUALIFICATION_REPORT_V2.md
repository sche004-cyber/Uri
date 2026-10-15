# Ember V2 - Final Qualification Report

Milestone FIRE-COMPANION-V2-20261015. Branch `phase/fire-companion-v2-20261015` (worktree
`C:\Users\cheta\Development\uri-fire-companion-v2`), cut from V1 `89ccf461`. **Local only: not merged, not pushed,
not deployed.** V1 is unchanged on its own branch.

## 1. Summary

| Area | Result |
|---|---|
| Approach | **Painting-derived 2.5D.** The four reference panels are cut into layers and animated: flame flow and sway, breathing, smoke, rising painted sparks, and a face rig (lids, gaze, borrowed mouths). The result plays through V1's proven sprite player. Blinks are added at runtime. |
| Visual fidelity (>= 90 %, AC-2) | **NOT MET.** The final blind critique (CP8, 2 fresh reviewers) gives means of 83.5 / 82.0 / 80.5 / 82.5 (idle / joyful / fierce / depleted). For comparison: V1 30-36, the AI redraw of the same character 40-55, the painting blurred 81-83, the painting itself 100. The threshold was not lowered. |
| Living animation | Done. Seamless loops for 9 clips. Irregular runtime blinks are verified live (gaps 0.5-6.5 s, including double blinks). Painted sparks rise. Animation costs no measurable fidelity (CP7/CP8). |
| Functional states | All 9 `CompanionState`s mapped (table unchanged). Fierce is animated and scored but not shipped. |
| Success signalling (F-SUCCESS) | **Repaired** (`oi_sources.dart`). Live: greeting -> success; approved task SETTLED_VERIFIED -> success -> idle. |
| Voice-settings errors (PRE-1) | **Repaired** (`voice_input_settings.dart`). The regression test failed before the fix and passes after it. Live: 0 framework assertions, against 12 in V1. |
| Startup presentation (F-STARTUP) | **Not repaired; owner decision.** It needs a shared `CompanionState.starting`. See section 7. |
| GPU / VRAM (AC-7) | GPU 3D 0.14-0.29 %, against Solar's 3.8-11 % (MET). VRAM +33-36 MB over Solar and 3-6 MB under V1 (bounded). Atlases 9.7 MB on disk (V1: 14 MB). |
| Brain coexistence | No evidence that Ember slows the Brain. A clean A/B comparison is **INCONCLUSIVE**: the Brain was demoted, 2 samples each, and another session's processes were present. |
| Live Windows qualification | First-time user, returning user and journeys 1-9 **PASS** on the real app with our own Brain under the GPU lease. Journey 10 (recovery) is **BLOCKED**: a parallel session took the lease. The wake phrase is NOT AVAILABLE. |
| Tests | Full `flutter test`: **578 pass / 5 skip / 0 fail** (V1 head: 567/5/0). |
| Independent acceptance | **BLOCKED.** The lifecycle driver needs the Claude CLI, which is logged out (`evidence/review/claude_cli_auth_status.txt`). Fresh-subagent audit rounds: section 9. |

## 2. Research and selected architecture

`01_RESEARCH_AND_APPROACH.md` compares five approaches:
- A: V1-style 3D, improved;
- B: painting-derived 2.5D, pre-rendered;
- C: the same as B, real-time in Flutter;
- D: Live2D, Spine or Rive;
- E: AI video.

B was selected as the smallest sound solution:
- no new dependencies (numpy/scipy/Pillow, already installed);
- no new runtime rendering path;
- V1's player, manifest format, failure/retry logic, frame suspension and tests reused;
- one small addition, the runtime blink overlay.

C was rejected because it would move GPU cost towards Solar's level for no fidelity gain. D was rejected for its
dependency, licence and GUI authoring. E was rejected on its measured redraw fidelity.

## 3. Implementation (diff `89ccf461..HEAD`)

**Art pipeline (`companion_art/fire_v2/`, new):**
- `layers.py`: background plate, minimum-alpha matte, solid head, eyes and body, spark-safe smoothing, inpainting of
  the signature and generator mark.
- `animate.py`: flame turbulence, sway and smoke, all capped together; breathing or rigid hop; head tilt; puppet
  handles; face rig; rising sparks.
- `rig.json`, `expressions.json`, `render_clips.py`, `export_v2.py`: export in the V1 atlas format, plus eye offsets
  and the blink atlas.

**App (`uri_ui/`):**
- `ember_companion.dart`: manifest blink data and eye offsets, `EmberBlinker`, `EmberOverlay`, blink-atlas
  lifecycle in `EmberLibrary`.
- Assets replaced: 8 atlases, a new `blink.webp` and the thumbnail.
- **Accepted files changed, with reasons:**
  - `integration/oi_sources.dart` (F-SUCCESS). This affects every companion, because any companion can show
    `success`.
  - `screens/settings/voice_input_settings.dart` (PRE-1).
- Tests: `ember_companion_test.dart` (+blink timing, manifest and widget tests), `ws_integration_test.dart`
  (+F-SUCCESS), `live_voice_test.dart` (+PRE-1).

**Scorer (`scripts/fire_companion/`):**
- `fidelity_score.py` gains `--aligned`;
- new `score_v2.py` and `critique_pack_v2.py`.

**Unchanged:** frozen Core, Runtime v1 and Brain. No change in any other worktree.

## 4. Four-state visual comparison

See `evidence/demos/four_state_comparison.jpg`: the reference, V2 in app presentation, and V1, for each state.
Animation demonstrations (GIF, 12 fps preview, all 9 clips): `evidence/demos/*.gif`.

## 5. Fidelity (AC-2): method and results

The method (`03_FIDELITY_METHOD.md`) was defined before scoring:
- blind packs, with fresh reviewers each checkpoint;
- 7 dimensions;
- calibration anchors;
- V2 scored as its weakest frame;
- pass rule: mean >= 90 % and no reviewer below 85.

| Checkpoint | What changed | V2 mean range | Notes |
|---|---|---|---|
| CP1 | Cut-out only, automated scorer | - | Exposed the scorer's registration fragility; `--aligned` added |
| CP2 | First animation | 74-85 | Miscalibrated: no top anchor |
| CP3 | Matte, sparks, feet, pool repairs | 77-80 | Top anchor added (99-100) |
| CP4 | Larger pool, cap, breathing | 74-78 | Two reviewer claims checked and refuted |
| CP5 | Diagnostic: unanimated cut-out | 72-77 (cut-out alone 69-81) | |
| CP6 | Card presentation | 70-79 | Card gave no gain; the CP5 explanation was corrected |
| CP7 | Single full-resolution frames; rigid hop; one cap | **84-86** | The format confound was real |
| CP8 | Crisp sparks, solid robe | **80.5-83.5** | Final |

Findings (`evidence/fidelity/cp8_RESULTS.md`):
1. V2 sits at the level of "the painting, blurred".
2. Every V2 frame scores the same as the unanimated cut-out, so the animation itself costs nothing measurable.
3. The remaining gap is the cost of lifting the character out of its painting and showing it on the app's
   near-black canvas. Reviewers named:
   - the darker surround;
   - the crest swirl reading dark;
   - a paler robe;
   - fewer sparks visible in any one frame;
   - the removed signature.
4. The automated scorer (regression only) gives V2 frames 88-128 on V1's scale, by construction.

Further tuning was judged to be tuning to reviewer noise: CP7 to CP8, with almost unchanged art, moved -1 to -4.

## 6. Performance (AC-7)

`03_MEASUREMENTS_V2.md`: controlled harness, 2 runs each, with Brain residency recorded.

| | GPU 3D median | Dedicated VRAM median | Frames/s |
|---|---|---|---|
| V2 | 0.14-0.29 % | 142-143 MB | 46-48 |
| V1 | 0.14-5.5 % | 145-149 MB | 44 |
| Solar | 3.8-11 % | 107-109 MB | 137-148 |

## 7. Live Windows qualification (AC-8)

`05_LIVE_QUALIFICATION_V2.md`. Four runs, all kept: one aborted, one returning-user run, one blocked by a harness
defect, and one full run.

The GPU-lease instruction (OD-8) was followed:
- We never sent a turn to another session's Brain. Run 1 and the recovery step of run 4 were stopped as soon as our
  launcher attached to the parallel session's Brain.
- Our own Brain host was always stopped gracefully, releasing the lease.
- Harness guards were added after these events.

## 8. Findings and limitations

| ID | Finding | Status |
|---|---|---|
| AC-2 | Fidelity >= 90 % not met (80.5-83.5) | **Open: owner decision** |
| F-STARTUP | During Brain loading a first-time user sees the depleted, sad Ember ("Unavailable - Brain LOADING") | Open. Proposal: add `CompanionState.starting`, derived from Brain LOADING/STARTING, with a kindling clip. This changes the shared contract, so it is an owner decision. |
| PRE-2 | `OiConversation.monitorTick` notifies after dispose when a status probe is in flight at teardown (`oi_conversation.dart:269`) | Open: canonical, pre-existing. Seen only at test teardown. |
| HARNESS-1 | The launcher attaches to any running Runtime v1 server, so in a shared machine a test run can reach another session's Brain | Open: guarded in this harness; the launcher itself is unchanged |
| J10 | Live recovery journey | BLOCKED (lease contention) |
| COEX | Brain A/B comparison | INCONCLUSIVE |
| UX-1 | The prompt bubble overlaps the status label | Pre-existing, not in scope |
| Wake word | No recogniser exists in canonical URI | NOT AVAILABLE |
| Licence (OD-2) | The reference and all derived art are committed on local branches only. Any push needs OD-2 settled, and possibly history surgery. | Open |
| Presentation | V2 shows a soft painted backdrop pool behind Ember (a visual-identity choice made for fidelity on the dark canvas) | For owner review |

## 9. Independent review

(see addendum)

## 10. Recommendation

Do **not** integrate as "meets spec": AC-2 is not met, and independent acceptance is BLOCKED.

V2 is a large step from V1:
- blind fidelity of about 82 against about 40;
- every functional, performance and live check passes, except the blocked or not-available items above;
- two lifecycle defects fixed.

Options for the owner:
1. **Accept V2's measured fidelity (about 82 %) and integrate as Ember**, after deciding OD-2 (licence and git
   history) and the presentation (backdrop pool). This needs an explicit owner waiver of AC-2, and a lifecycle
   acceptance once the Claude CLI is logged in.
2. **Keep on the branch.** Commission a contract change for F-STARTUP and a "painting card" presentation study at
   full resolution in the single-frame format. CP6 tested the card only in strips.
3. **Keep V1 and V2 as research.**
