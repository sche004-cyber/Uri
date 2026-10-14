# Ember - Animation and State Matrix

Status: IMPLEMENTED in `uri_ui/lib/living/companion/ember_companion.dart` (`EmberClips.forState`) and rendered from
`companion_art/fire/states.json`. Asserted by `uri_ui/test/living/ember_companion_test.dart`.

## Principle

Ember shows what URI is doing; it never decides it. The only input is the existing `CompanionState`, which is
derived from authoritative facts (`companion_sources.dart`, `voice_session.dart`, `oi_sources.dart`). Ember adds no
state to that contract. The text label ("Needs your approval", "Attention needed", ...) and the voice waveform stay
the operational message; the expression is a cue on top of them.

Eight shipped clips cover nine states. Three come from the reference sheet (idle, joyful, depleted); five are derived
from the same rig with different control values, so they cost rendering time and disk, not modelling work. The fourth
reference expression (`fierce`) is rendered from the rig and scored for fidelity but NOT shipped: no operational state
may show it, because an angry face directed at the user would misreport an error or a refusal as hostility. `focused`
carries its energy (hand fireballs, stance) with a calm face for `working`.
(Correction 2026-10-15, review R1-02: an earlier version of this page said fierce was "qualified for fidelity, shown
in the settings preview". Neither was true; it is now removed from the app and described as above.)

## Lifecycle situations (from the brief) mapped to states and clips

| # | Situation | `CompanionState` (source) | Clip | New animation? | Why |
|---|-----------|---------------------------|------|----------------|-----|
| 1 | Waiting for user interaction | idle | `idle` | Reference 01 | Calm breathing, sway, flame mane, tail flame, two blinks per 4 s loop (gaps 1.4 s and 2.6 s; the pattern repeats every 4 s, so blinking is not truly irregular - limitation). |
| 2 | Wake-word recognition | none: no wake-word recogniser exists in canonical URI | `listening` (when push-to-talk opens the mic) | No | Building a wake-word engine is outside this milestone. Reported NOT AVAILABLE. |
| 3 | Listening to the user | listening (`voice_session.dart`) | `listening` | Yes (derived) | Leans in, eyes wider, flames gathered and calm. Must look different from idle so the user knows the mic is open. |
| 4 | Processing speech | listening until the transcript is final, then thinking | `listening` -> `thinking` | No | Uses the two clips either side. |
| 5 | Thinking / reasoning | thinking (`AppState.isSendingAsk`, `TurnStage.understanding`) | `thinking` | Yes (derived) | Eyes up and aside, flames swirl inward, slow embers. |
| 6 | Responding through text | speaking (`oi_sources.dart` streamed reply) | `speaking` | Yes (derived) | Mouth moves at syllable rate, warmer glow. |
| 7 | Speaking (TTS) | speaking (`voice_session.dart`) | `speaking` | Shared with 6 | Same expression; the voice waveform beside the companion carries the audio level. |
| 8 | Successful task completion | success (held 4 s by the source) | `joyful` | Reference 02 | Hop, arms up, bright flame, many sparks; then back to idle. FINDING: only the legacy `AppStateCompanionSource` emits `success`; the integrated-profile `OiCompanionSource` never does, so in the working system `joyful` is not reached after a settled task. Changing that source is outside this milestone (follow-up proposed). |
| 9 | Clarification request | awaitingApproval (proposal / clarification needs the user) | `listening` + attention pulse | No | Attentive pose reused; a slow brightness pulse plus the label ask for the user. |
| 10 | Errors / unavailable capability | error | `concerned` | Yes (derived) | Sad brows and lids, flame lowered but lit, a little smoke. Distinct from "no power". |
| 11 | Pending user approval | awaitingApproval | `listening` + attention pulse | No | As 9. Typed or spoken words never approve; the companion only shows the wait. |
| 12 | Background activity | working (`TurnStage.executing`, supervised execution) | `focused` | Yes (derived from fierce) | Fierce energy in the hands and stance, but a calm determined face. |
| 13 | Connection loss | unavailable (`connectionStatus == unreachable`) | `depleted` | Reference 04 | Fire out: ash-grey head, smoke, slump. |
| 14 | Recovery | unavailable -> idle | `depleted` -> `idle`, 1.1 s fade | No | Slower cross-fade reads as the flame rekindling. A rendered "reignite" clip is a possible later improvement. |
| 15 | Sleep / reduced activity | (no state) reduced motion setting; minimised window | frame 0 of the current clip; no frames while minimised | No | Reduced motion holds a still frame; the shared frame clock already stops when the window is hidden. |
| - | Reference "Fierce" | none | none (not shipped) | Reference 03 | Rendered from the rig and scored for fidelity only. |

## Clip table (rendered from `companion_art/fire/states.json`)

| Clip | Loop | Expression | Body | Flame | Particles | Transition in |
|------|------|------------|------|-------|-----------|---------------|
| idle | 96 f (4 s) | Big black eyes, blinks at f30 and f64 | Bob + sway, arms out with hand flames | Sideways mane, plume, tail flame | Sparse embers | 0.45 s fade |
| joyful | 48 f (2 s) | Brown iris, open smile, blush | Hops twice per loop, arms up | Taller, brighter, turbulent | Dense, fast sparks | 0.45 s |
| fierce (not shipped) | 48 f | Slanted lids, angry brows, frown | Wide stance, arms out | Tall, swept, turbulent | Many sparks | - |
| depleted | 96 f | Half-closed sad eyes, sad brows, frown | Slumped, arms hanging, slow | Few short flickers, smoke columns | Very few | 1.1 s |
| listening | 48 f | Eyes 8% larger, one blink | Leans forward, head tilt | Calm, gathered | Few | 0.45 s |
| thinking | 96 f | Eyes up-left, one blink | Small head tilt | Slow inward swirl | Slow orbit | 0.45 s |
| speaking | 48 f | Mouth opens and closes (4 Hz) | Livelier bob | Warmer | Some | 0.45 s |
| focused | 48 f | Calm, slightly lowered lids | Firm stance, arms out | Swept | Moderate | 0.45 s |
| concerned | 48 f | Sad lids and brows, small frown | Slight slump | Lowered, lit, wisps of smoke | Few | 0.45 s |

## Transition rules

- Changing state never cuts: both clips play during a cross-fade (0.45 s; 1.1 s into or out of `depleted`). The fade
  starts only once the incoming clip is decoded; until then the outgoing clip keeps playing. The two frames are added
  in their own layer ((1 - e) * old + e * new), so the character does not turn translucent mid-fade.
- The outgoing clip keeps playing from where it was; the incoming clip starts at its frame 0.
- `awaitingApproval` adds a 2.8 s brightness pulse (up to +14%), faded in and out over ~1 s, as the shader
  companions do.
- Reduced motion: frame 0 of the clip, no pulse movement, no frames requested once settled.
- Reduced effects: the classic orb (same rule as every living companion).
- Minimised window: the shared `CompanionFrameClock` stops; Ember requests no frames.

## Resource rules

- Each clip is one WebP atlas. Only clips on screen are pinned; at most `capacity` (2) atlases stay decoded while
  Ember is shown, and every atlas is disposed when no Ember widget remains (switching to another companion frees them).
- Between sprite frames Ember stops asking the frame clock for frames and a timer wakes it for the next one, so it
  requests about 24 frames per second instead of one per vsync; fades and the approval pulse run at the clock rate.
- The companion picker shows a 192 px still (`thumbnail.webp`, about 15 KB), never a decoded atlas.
- Measured sizes and memory: see `03_MEASUREMENTS.md`.
