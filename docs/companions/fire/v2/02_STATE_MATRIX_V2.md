# Ember V2 - State and Animation Matrix

Source of truth for each clip: `companion_art/fire_v2/expressions.json`. The mapping lives in
`EmberClips.forState` and is unchanged from V1. Every clip is built from one reference panel. "Derived" clips
re-compose that panel's own pixels: lids, gaze and head tilt, plus a mouth taken from another panel of the same
sheet. None of them is a new drawing.

| CompanionState | Clip | Panel | Loop | What moves | Blink |
|---|---|---|---|---|---|
| idle | idle | 01 IDLE | 72 f (3 s) | Flame turbulence and sway, breathing, painted sparks rising | yes |
| success | joyful | 02 JOYFUL | 48 f | Bouncing hop (2 per loop), waving hands, livelier flame, the painted spark cloud rising plus 10 extra sparks | no (smiling eyes) |
| unavailable | depleted | 04 DEPLETED | 72 f | Small flickering flames, curling smoke, slow breathing | yes (from the painted half-lids) |
| listening, awaitingApproval | listening | 01 IDLE | 48 f | Head tilted 4°, eyes 5 % larger, calmer flame | yes |
| thinking | thinking | 01 IDLE | 72 f | Gaze up and to the side, a light lid, slow sweeping flame | yes |
| speaking | speaking | 01 IDLE plus the mouth from 02 JOYFUL | 48 f | Mouth opens and closes (3/5/7 cycles mixed), brighter flame | yes |
| working | focused | 01 IDLE | 48 f | Stern lids (24 %, inner corners lower), brighter and faster flame, sparks | yes |
| error | concerned | 01 IDLE plus the mouth from 04 DEPLETED | 48 f | Worried lids (inner corners raised), small frown, dimmer flame, slight tilt | yes |
| (none) | fierce | 03 FIERCE | 48 f | Animated and scored, **not shipped** (`ship: false`): an angry face aimed at the user would misreport URI | - |

**Transitions.** The player is V1's, unchanged: an additive cross-fade, 450 ms, or 1,100 ms into or out of
depleted so the fire visibly dies down or rekindles.

**Reduced motion.** Frame 0 is held. There are no blinks and no frames requested.

**Blinks.** Runtime blinks (`EmberBlinker`) come 2.5-7 s apart, at random, with a 15 % chance of a double blink.
Each blink is a 6-step close-hold-open sequence, about 250 ms. A blink is drawn only on sprite frames the player
already draws, and never during a cross-fade.

## Lifecycle findings investigated in V2

| ID | Finding (V1) | V2 result |
|---|---|---|
| F-SUCCESS | `OiCompanionSource` never emitted `success` | **Repaired** in `integration/oi_sources.dart`: `success` is held for 4 s after a turn whose `turn.finished` status is `ok`. The orchestrator allowlists `ok`: a complete Brain answer, or Core `SETTLED_VERIFIED` (`core_turn_status`). Turns that finished before the source existed never celebrate. Covered by tests in `test/ws/ws_integration_test.dart`. This changes an accepted integration file, which is why it is listed here and in the report. It affects every companion, because any companion can show `success`. |
| Blink | Blinks were baked into the loops at fixed frames, so they repeated every 4 s | **Repaired**: blinks now come at runtime at irregular times (above). |
| F-STARTUP | While the Brain loads, the integrated source reports `unavailable` ("Brain LOADING"), so Ember greets a new user with the depleted, sad face | **Not repaired; finding recorded.** `CompanionState` has no "starting" value, and the companion may read `CompanionState` only (AC-5). Telling "warming up" apart from "unavailable" needs a contract change shared by every companion, which is an owner decision. Within scope, V2 makes the rekindle visible: depleted to idle is a slow 1.1 s cross-fade, from a smoking ember to full flame. Proposal: add `CompanionState.starting`, derived from Brain `LOADING`/`STARTING`, and map Ember to a kindling clip. |
| PRE-1 | `VoiceInputSettings` notified listeners during build (12 framework assertions in the V1 live run) | **Repaired** in `screens/settings/voice_input_settings.dart`: the voice check starts after the first frame. Regression test `live_voice_test.dart` "opening voice settings does not notify listeners during build (PRE-1)": it failed before the fix with "setState() or markNeedsBuild() called during build" (`evidence/tests/pre1_before.log`) and passes after it (`pre1_after.log`, 43/43). This changes an accepted file and is listed in the report. |
| UX-1 | The prompt bubble overlaps the status label | Pre-existing layout outside the companion; not changed (scope). |
