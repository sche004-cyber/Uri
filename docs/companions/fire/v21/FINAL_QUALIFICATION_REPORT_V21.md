# Ember V2.1 - Final Qualification Report

Branch `phase/fire-companion-v21-20261015` (local only), cut from V2 `b73bd26c`. Plan and criteria:
`00_PLAN_AND_ACCEPTANCE_V21.md`.

## Verdict

**NOT MET on the >= 90 % visual-fidelity target. Formal lifecycle acceptance BLOCKED.**
Everything else that was asked for is delivered and measured.

- **Fidelity, Q1 (valid, 3 fresh blind reviewers):** V2.1 scored 85.7-86.3 % against >= 90 %.
- **The ceiling is the presentation.** The **unmodified painting shown the same way in the app scores the same,
  85.7-86.8 %**. V2.1 equals that control in every valid round (P1, P2, Q1).
  - No in-app presentation tested reaches 90: the current disc, a wider disc and a soft square card all stay at
    84.5-86.3.
  - The gap is not in Ember. It is the cost of showing a painting inside the app at all: a dark surround, a smaller
    figure and soft margins.
- **The threshold is unchanged.** Under the rules, reaching 90 needs one of three things: an owner decision, a
  different presentation that has not been found, or a change to what the target compares.
- **V2.1 against V2, as users see it:** about 73 -> 86 visual (+12 to +14 points), 77 -> 91 character.
- **Character identity:** met (91.1-91.4 % >= 90).
- **Animation:** no regression (76.7-78.3 % against V2's 73.8-76.7 %).
- **Performance:** unchanged from V2.
  - GPU 0.27-0.28 % (Solar 6.9-7.4 %).
  - VRAM 147 MB (+41 MB over Solar, the same as V2).
  - Atlases 3.3 MiB on disk (V2: 9.7 MiB).
- **Brain coexistence:** our own Brain under the lease, 3 alternating pairs. No material slowdown with Ember on
  screen.
- **Live Windows, real Core and Brain:** first-time and returning users PASS. Every journey ran; recovery is no
  longer BLOCKED.
  - Known pre-existing items: PRE-2 (teardown race) and F-STARTUP (sad face while loading).
- **Regression:** 580 passed, 5 skipped, 0 failed (same as V2). No Dart source, Core, Runtime or shared-host file
  changed.
- **Lifecycle acceptance:** BLOCKED. The Claude CLI is still logged out
  (`claude auth status`: `"loggedIn": false`).

## 1. What changed (smallest proven change)

| Change | Where | Why |
|---|---|---|
| The painting behind the character, with its brushwork, recovered as `(src - F*a) / (1 - a)` | `companion_art/fire_v2/animate.py` (`Panel.backdrop`) | The cut-out had thrown away the brush strokes, glow and smoke context reviewers kept naming |
| Optional `stage` (textured backdrop) and panel-centred `frame` in the exporter | `companion_art/fire_v2/export_v2.py`, `expressions.json` | The host's SoftDisc cut off Ember's feet and crest; the frame now puts the whole painting composition inside the disc |
| Re-exported atlases | `uri_ui/assets/companions/ember/` | Same cell size, frames, clips and runtime format |
| Unshipped `kindling` startup clip | `expressions.json` (`"ship": false`) | Ready for the shared `starting` state, if approved |

The nine clips, all motion, blinks and every runtime file are unchanged. Without `stage`, the exporter reproduces V2
(checked against the shipped V2 atlas: mean difference 0.0022, WebP noise).

## 2. Diagnosis (`01_DIAGNOSIS_V21.md`)

1. **Presentation, not character or animation.** V2 evidence already showed that a frozen cut-out scored the same
   as the animation.
2. **New: V2 was measured on a kinder view than users see.** The companion host zooms Ember 1.19x and fades it to a
   disc. In the app, V2 showed only 79-91 % of the character's area; V2.1 shows 95-98 %. V2 in the app view scores
   72-78, not the 82 reported for V2.
3. **New: the method had no presentation control.** FP-21 adds the unmodified painting in the app presentation, and
   it caps every candidate.

## 3. Fidelity method (`03_FIDELITY_PROTOCOL_V21.md`, FP-21)

- Locked before scoring.
- App-true rendering: the atlas cell, WebP, presence scale, SoftDisc and canvas, exactly as the host computes them.
- Ten dimensions, separated into character and presentation, plus four animation dimensions.
- Three fresh blind reviewers per round, with fixed-seed shuffles and file hashes in the keys.
- Raw evidence: each reviewer writes its own answer file, and its full transcript is preserved locally with
  SHA-256s. Access audits from the transcripts confirm each reviewer read only its own pack.
- Validity rule and pass rule written down before decoding. Every round is reported, and no score is removed.
- One recorded change, C-1: the exploratory host-presentation round P2. It did not alter the qualification rules.

| Round | Purpose | Valid | V2.1 visual | Painting control | V2 in the app |
|---|---|---|---|---|---|
| P1 | baseline and candidate | yes | 89.0-89.2 | 89.0-89.2 | 78.0-78.2 |
| P2 | host presentation probe | yes | 84.5-86.3 (by host) | 85.3-86.3 | - |
| **Q1** | **qualification** | **yes** | **85.7-86.3** | **85.7-86.8** | **72.3-73.5** |

Panels move by about 3-4 points between rounds. The control never reaches 90.

## 4. Performance (`05_MEASUREMENTS_V21.md`)

All six runs were measured inside our own GPU lease, with ownership and no-Brain checks before and after each run.
- One earlier attempt had a build-script defect (frame-timing files overwritten). It is kept and disclosed.
- One attempt was refused while the FCV session held the lease.

## 5. Live (`06_LIVE_QUALIFICATION_V21.md`)

Every journey from V2's list ran on the real system. Results:
- The success state and blinks are shown live.
- The recoverable-error journey and recovery pass.
- The wake phrase does not exist in URI (NOT AVAILABLE).

The UI interaction was automated; this is not a human usability study.

## 6. Startup (`04_STARTUP_PROPOSAL_V21.md`), AMBER

Ember cannot tell "loading" from "failed", because both arrive as `unavailable`. The fix is a shared
`CompanionState.starting` that touches every companion. It is proposed with its file list, mapping and tests, and is
not implemented. Ember's `kindling` clip is ready (`evidence/demos/kindling.gif`).

## 7. Independent review

See `evidence/review/`. Lifecycle acceptance of the exact final commit: **BLOCKED** (CLI logged out). An informal
reviewer verdict is not a substitute for it.

## 8. Reference assets and git history

- The reference sheet and derived art first entered history in V1 commit `8a1438ec`, on top of canonical
  `1b5423bc`. The V1, V2 and V2.1 branches are local. `git branch -r --contains 8a1438ec` is empty, so nothing is
  published and **no shared history needs rewriting**.
- If the art cannot be redistributed, publication needs a branch re-cut from canonical with only licensed files, or
  a `git filter-repo` pass on a disposable copy. This is an owner and licensing decision (OD-2, carried from V2).
- Reviewer transcripts, about 15 MB each and mostly images, are kept local only (gitignored, hashes committed).

## 9. Remaining limitations and risks

1. AC-F1 NOT MET under FP-21. The cap is the in-app presentation itself, as measured.
2. Reviewers are language models judging stills; motion is judged from six frames.
3. The Brain coexistence result rests on 3 pairs; a 2-5 % effect cannot be excluded.
4. The Brain was partially demoted (CONTENDED residency) during the live run because of other GPU users.
5. Two pre-existing defects remain outside scope: F-STARTUP and PRE-2. The launcher still attaches to any running
   Runtime v1 server; the harness guards against this, the launcher does not.
6. The 320 px atlas, upscaled by the host, is slightly soft. Reviewers mentioned softening. A larger cell would cost
   VRAM, and P1/P2 give no evidence that it would lift the control above 90.

## 10. Recommendation for the owner

1. **Decide on AC-F1.** Either:
   - accept V2.1 under an owner waiver, on the evidence that it equals the painting itself in the app; or
   - redefine the target as "fidelity relative to the painting in the app presentation". In Q1 that would be
     98.7-100 % of the control. This is an owner change to the criterion; I have not applied it.
2. **Approve or decline the shared `starting` state** (AMBER).
3. **Licensing (OD-2)** before any publication.
4. **Lifecycle acceptance:** log in the Claude CLI and run the lifecycle on the exact final commit. Until then, no
   merge.
