# Ember V2 - Plan and Acceptance Criteria

Milestone: FIRE-COMPANION-V2-20261015
Branch: `phase/fire-companion-v2-20261015` (worktree `C:\Users\cheta\Development\uri-fire-companion-v2`), cut from V1
`89ccf461` on `phase/fire-companion-20261014`. Local only. V1 is not merged, not pushed and not changed.
Merge / push / deploy: NOT authorised. Stop at the integration recommendation.

## Why V2

The owner rejected V1 (2026-10-15) on visual fidelity. V1 scored 41-51 % in independent critique against the
reference sheet. Its own report found that the 3D recreation approach could not reach 90 %: an AI redraw of the same
character scored only 63-67 %. V2 keeps V1's functional integration, which was proven: the identity, the settings
choice, the sprite player, frame suspension, the failure and retry logic, the tests and the live harness. V2 replaces
the art pipeline and fixes the V1 findings that fall in scope.

## Owner decisions carried over / needed

| ID | Decision | Status |
|----|----------|--------|
| OD-2 | Rights to the reference character | Carried over: "I hold rights / will license". Not verifiable by the implementer. The reference and all derived art stay local (see AC-12). |
| OD-4 | Reviewer | Carried over: the lifecycle driver needs the Claude CLI. It was logged out in V1. Checked again at the review stage. If the driver is unavailable, independent acceptance is reported **BLOCKED**, and fresh-subagent audit rounds still run as audit evidence only. |
| OD-6 | GPU override for a live Brain | Was "this run only" for V1. A V2 live run needs a new answer if Runtime v1 reports WAITING_FOR_GPU (AMBER: ask). |

## Acceptance criteria (defined before implementation)

AC-1 Research. A written comparison covers at least four approaches on fidelity, animation quality, GPU/VRAM, complexity,
compatibility and maintainability. It cites measured V1 data where it exists and selects the smallest sound
solution. A prototype is used as evidence where a claim is not otherwise measurable.

AC-2 Fidelity (owner threshold, not lowered). For each of idle, joyful, fierce and depleted:
- (a) An independent calibrated critique scores >= 90 % per state. The critique is blind, uses at least two fresh
  reviewers, and covers the seven dimensions of the brief: silhouette and proportions; head shape and surface;
  eyes and expression; flame density, shape, colour and motion; body proportions and movement; painterly lighting and
  material; emotional consistency. It is run on frames sampled across the whole animation loop, including the frame
  furthest from the reference, as the app shows them. The mean across reviewers must be >= 90 %, and no single
  reviewer may score a state below 85 %.
- (b) The calibration anchors are scored in the same blind session. They are the reference panel itself (expected
  near 100), V1 (prior 41-51 %) and the AI video redraw (prior 63-67 %). If the anchors land outside +-10 points of
  their priors, the session is reported as miscalibrated and repeated.
- (c) The automated V1 scorer is run on every sampled frame and reported (median and minimum). It is a regression
  check, not the acceptance measure: frames derived from the painting score high on pixel similarity by
  construction (see 03_FIDELITY_METHOD.md).
- (d) Evaluations run at checkpoints during development: after the cut-out, after the animation, and after
  integration. They are not only run at the end.

AC-3 Living animation. Every reference state is a seamless loop:
- Flames move organically: rising turbulence plus sway, never a rigid translate.
- The body breathes.
- Sparks live where the reference has them.
- Blinks are irregular, driven at runtime: random 2.5-7 s gaps, with an occasional double blink.
- Transitions never cut.
- Reduced motion holds a still frame.
- No frames are requested while the companion is static, hidden or frozen. This preserves V1's `wantsFrames`
  contract.

AC-4 Functional states. listening, thinking, speaking, working (focused), awaitingApproval, success, error and
unavailable each have an expression built from the reference character, not a new design. Fierce is produced and
scored, and it is not mapped to any operational state. Startup presentation and success signalling are
investigated. They are repaired in scope where they are UI-side; otherwise a finding is recorded.

AC-5 Integration. Everything V1's AC-5 required still holds: the companion is an additional choice, existing
companions are unchanged, the theme mapping is unchanged, and the companion reads `CompanionState` only. No
changes are made to frozen Core, Runtime v1 or the Brain. Changes to accepted UI files are listed file by file in
the report with their reason.

AC-6 Tests. `flutter analyze` reports nothing new for touched files. The full `flutter test` run has no new
failures against the V1 head, compared by test id. New or updated tests cover the clip table, the blink scheduler
(irregular, suspended when frozen or hidden, never while reduced motion), manifest integrity including blink data,
and transitions.

AC-7 Performance on RX 7900 GRE. The V1 harness (`tool/capture/ember_perf_app.dart`) is used for repeatable, controlled
measurements. It measures GPU utilisation, dedicated VRAM delta, process RSS, frame pacing (requested frames/s),
idle overhead and transition cost, for V2 against V1 and Solar. V2 must not exceed Solar's GPU cost, and its VRAM
delta must be bounded and stated. Brain token rate is measured with and without the companion if the Brain can be
run (OD-6).

AC-8 Live Windows qualification. The real app runs in a real window with real screenshots. The journeys are:
first-time user (select Ember, first impression, startup), returning user (Ember persisted across restart), and the
state journeys of V1. Real Core and Brain run if available; otherwise the item is BLOCKED with the reason.
Simulation alone never counts.

AC-9 Independent review. Whole-diff review of the exact final commit. If the lifecycle driver is unavailable,
acceptance is BLOCKED (OD-4) and the fresh-subagent audit and repair rounds are reported as audit only.

AC-10 Boundaries. Nothing is merged, pushed or deployed. There is no change in another worktree. V1 stays intact on
its own branch.

AC-11 Evidence. Scores, sheets, perf JSON, screenshots and logs are kept under `docs/companions/fire/v2/evidence/`.
Every positive claim cites a completed result.

AC-12 Assets and licence. Reference images and derived art are not added to any pushed history. The V2 branch is
local, and the report states that any push requires OD-2 to be resolved first.
