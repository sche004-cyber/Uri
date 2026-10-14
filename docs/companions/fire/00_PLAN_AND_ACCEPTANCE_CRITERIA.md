# URI Fire Companion ("Ember") - Plan and Acceptance Criteria

Milestone: FIRE-COMPANION-20261014
Branch: `phase/fire-companion-20261014` (worktree `C:\Users\cheta\Development\uri-fire-companion`)
Baseline: canonical `integration/git-sync-20261008` on `https://github.com/sche004-cyber/Uri` at `1b5423bc`
(verified by `git fetch uri-repo integration/git-sync-20261008` on 2026-10-14).
Merge: NOT authorised. Stop at the integration proposal.

## Owner decisions recorded before work (2026-10-14)

| ID | Question | Owner answer |
|----|----------|--------------|
| OD-1 | Install Blender | Install Blender 5.2.2 via winget |
| OD-2 | Licence of the reference art (Fiverr illustration; emotions sheet carries a Gemini mark) | "I hold rights / will license". Recorded as the provenance basis; not independently verifiable by the implementer. |
| OD-3 | The "supplied video" was not attached | Owner will attach it. Until it arrives, motion design uses the image and research only. |
| OD-4 | Independent reviewer (Claude CLI `loggedIn: false`) | Fresh Claude subagent reviewer only. Findings are real; the report must say the work is NOT lifecycle-driver ACCEPTED. |

## Discovery facts that shape the plan

- Companions are identities (`CompanionIdentity`: solar, sakura, lunar, moonlit) drawn by one fragment shader each
  (`CompanionOrb`) from six parameters per `CompanionState`. Classic `EnergyOrb` remains selectable.
- `LivingCompanion` is the single widget every surface uses (shell, onboarding, settings preview). Choice and
  appearance live in `CompanionPreferences`; the theme follows the identity through `CompanionTheme`.
- `CompanionState` (9 values) is driven only by authoritative facts in `companion_sources.dart`. The fire
  companion must consume that same enum and add no state of its own to the contract.
- Display sizes: companion mode 180-320 dp, workspace rail 64/132 dp, dashboard 128 dp, assist 84 dp,
  onboarding 150 dp.
- No wake-word recogniser exists in the canonical UI or voice service (`HOTWORDS="URI"` is recogniser bias for
  push-to-talk). Live journey step "wake phrase" cannot be exercised; it is reported NOT AVAILABLE, not simulated.
- Blender was not installed before OD-1. No 3D asset pipeline exists in the repository.

## Approach (to be confirmed by the measured comparison in Phase 1)

Offline Blender rendering of the character into short transparent sprite loops per expression, played by a
small Flutter widget inside the existing `LivingCompanion` seam. The character is a painted, eyed figure with a
face and limbs; the existing orb shaders cannot express it, and a hand-written shader recreation of a
painterly character is the weakest route to the fidelity target. Runtime work becomes one textured quad per
frame, which is cheaper than any existing companion shader.

Alternatives compared before freeze: (a) full procedural fragment shader, (b) pre-rendered sprite loops,
(c) layered 2.5D rig in Flutter (body / face / flame layers), (d) real-time 3D (glTF) in Flutter.

## Acceptance criteria

AC-1 Assets. A reusable `.blend` built by a committed Python build script (re-creatable from source), with an
armature, a control object exposing emotion and flame parameters, reusable materials, and named actions for
every implemented state. Blender asset validation test passes headless.

AC-2 Fidelity. A committed, reproducible scorer compares fixed-camera renders against each reference panel.
Calibrated automated score >= 90 for each of idle, joyful, fierce, depleted, AND an independent visual critique
(separate reviewer, rubric of nine dimensions) averaging >= 9.0/10 per state. Methodology and limits documented.
If missed, the report states the measured scores and the gaps; it never rounds up.

AC-3 State matrix. A documented animation/state matrix covering the 15 lifecycle situations in the brief,
mapped onto the existing 9 `CompanionState` values, stating for each whether a new animation is needed.

AC-4 Animation. Every `CompanionState` has a fire expression; transitions never cut (cross-fade or transition
clip); idle blinks at irregular intervals; reduced motion holds a still frame; reduced effects falls back to the
classic orb as other identities do.

AC-5 Integration. The fire companion is an additional `CompanionChoice`; existing choices, default (Solar),
persisted preferences, theme mapping, semantics labels, voice dock and mode geometry are unchanged. The
companion reads `CompanionState` only.

AC-6 Tests. `flutter analyze` clean for touched files; full `flutter test` has no new failures versus baseline
(compared by test id); new tests for identity mapping, clip selection for all 9 states, transition behaviour,
frame-clock suspension, asset manifest integrity.

AC-7 Performance (RX 7900 GRE). Measured in a real Windows build: frame time, CPU, GPU, process RSS and dedicated
VRAM for the fire companion versus Solar in the same harness. Fire must not exceed Solar's GPU cost and its
resident sprite memory must be bounded and stated. No Brain is launched by this work; if a Brain is resident,
the measurement records it.

AC-8 Live Windows qualification. Real app, real window, real screenshots and logs for the journeys in the brief
that the canonical build supports. Steps that cannot be performed are reported BLOCKED or NOT AVAILABLE with the
reason.

AC-9 Independent audit. A fresh reviewer that did not write the code reviews the whole diff, the fidelity
evidence and the performance claims; findings are repaired and re-reviewed until no blocking finding remains
or progress stalls. The report never calls the work lifecycle-ACCEPTED (OD-4).

AC-10 Boundaries. No frozen path, Core or Brain change; no merge; no deployment; no change in another worktree.
