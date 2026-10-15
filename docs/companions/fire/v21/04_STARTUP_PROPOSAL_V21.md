# Ember V2.1 - Phase 4: Startup state (scoped proposal, NOT implemented)

Status: **AMBER - needs owner approval.** The fix crosses into shared, accepted companion code. Following the brief, it
is prepared here as a proposal and not implemented silently.

## The defect (F-STARTUP, carried from V2)

While the Runtime v1 Brain loads, `OiCompanionSource._derive` (`uri_ui/lib/living/integration/oi_sources.dart`)
maps every Brain status other than `READY` to `CompanionState.unavailable` with the detail `Brain <state>`.
`EmberClips.forState` maps `unavailable` to the `depleted` clip. So a new user's first sight of Ember is the grey,
smoking, sad figure, which reads as failure, during a normal startup of up to about a minute. Every other companion
shows its dim "unavailable" look in the same moment.

Evidence: V2 live screenshot `docs/companions/fire/v2/evidence/live/run4_first/first-04-companion-before-brain.jpg`.

## Why it cannot be fixed inside Ember

`EmberCompanion` receives only a `CompanionState`. It cannot tell "the Brain is loading" from "the Brain failed",
because both arrive as `unavailable`. Reading the detail text would be a fragile string contract. The distinction
belongs in the shared state.

## Proposal

1. **Shared state.** Add `CompanionState.starting` to `companion_state.dart` (label "Starting", not active, not
   needing the user).
2. **Mapping.** In `OiCompanionSource._derive`, Brain states `STARTING`, `STARTING_HOST`, `LOADING` and
   `WAITING_FOR_LEASE` map to `starting` (details "Brain loading" or "Waiting for the GPU"). `FAILED*`, `STOPPED*`,
   `UNAVAILABLE` and unknown states keep mapping to `unavailable`. The detail stays truthful.
3. **Each companion.** The Dart switches over `CompanionState` are exhaustive, so the compiler lists every place that
   needs a value:
   - Solar, Sakura, Lunar, Moonlit (`companion_orb.dart`): `starting` = the `idle` parameters at lower energy and
     exposure (a calm, dim version of themselves).
   - Classic orb (`energy_orb.dart`): the idle breathing, dimmer.
   - Status line (`companion_presence.dart`, `companion_mode_view.dart`): accent dot, "Starting".
   - Ember: `starting -> kindling`, a new clip already rendered on this branch (see below). `kindling -> idle` uses the
     normal cross-fade, so Ember brightens and its flame grows as URI becomes ready.
4. **Tests.** Mapping tests for each Brain state; a widget test per companion that `starting` renders; the onboarding
   flow test for the first-time path.

Files touched (all outside Ember's own scope): `companion_state.dart`, `oi_sources.dart`, `companion_orb.dart`,
`energy_orb.dart`, `companion_presence.dart`, `companion_mode_view.dart`, `companion_sources.dart`, possibly
`living_onboarding_flow.dart` and `companion_settings_section.dart`, plus their tests. Estimated size: about 60-100
lines of code and 80-120 lines of tests.

Risks: other companions change appearance during startup (an owner visual decision); external consumers of the
companion state, if any, see a new value.

## Done on this branch (Ember scope only)

- `kindling` clip in `companion_art/fire_v2/expressions.json`: the idle panel, low slow flame (flow 0.6-4 px, sway
  2.5 px), flicker 0.05, brightness 0.8, eyes calmly half-lowered (lid 0.35), slow loop (4 s). It is marked
  `"ship": false`, so it is not exported to the app and changes nothing at runtime until the proposal is approved.
- A demonstration GIF: `evidence/demos/kindling.gif`.

## Decision needed

Approve the shared `starting` state (as above, or with changes), or keep the current behaviour.
