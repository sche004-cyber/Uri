# Companion interaction options — 12 October 2026

Status: owner selected **Detached chat** on 2026-10-13; exact reference: [approved image](evidence/reference/companion-approved.jpg). Other directions are historical alternatives. The Flutter implementation is an isolated candidate; it is not independently accepted, integrated or deployed.

Open [the animated comparison](companion-options.html), or serve this directory with `python tools/serve_options.py` and visit `http://127.0.0.1:8137/companion-options.html`.

## Shared direction

The existing Solar Companion stays central. Resting Companion mode has no enclosing window decoration, menu container or chat box. Click reveals contextual floating actions. Chat, Dashboard, Voice and a review action are local navigation/interaction affordances; they never grant permissions or approve tasks. Voice is offered only when the real service supports it. Full Dashboard/Workspace is the first mode in V2. Double click opens Dashboard and suppresses the single-click acknowledgement.

The existing voice waveform and transcript are reused, below the Companion. Listening and speaking follow the existing voice session. They do not indicate task completion. “oii URI” wake activation is not implemented in the inspected accepted voice service; continuous microphone capture has not been added.

## Three visual options

| Direction | When Chat is clicked | Tradeoff |
|---|---|---|
| [Input pill](evidence/concepts/input-pill.png) | A small single-line input appears below the waveform | Smallest desktop footprint; history requires Workspace |
| [Reply ribbon](evidence/concepts/reply-ribbon.png) | Input plus the latest reply appears below the waveform | Retains immediate context without a full thread |
| [Detached chat](evidence/concepts/detached-chat.png) | A separate borderless short conversation opens | More context; occupies more desktop space |

All three use the same sample scenario and the approved Ivory Foundry, Snow Archive and Ash & Limestone interface themes. They are alternatives, not accepted implementations. The generated static concepts use an approximate rendition of the attached Solar reference; their sun imagery is a temporary visual representation. The HTML comparison uses a recorded frame from the [actual renderer](../../uri_ui/lib/living/companion/living_companion.dart), displayed with 2D rotation. It is not a live shader or a real 3D model.

## Orbital motion proposal and preview

- One revolution per 180 seconds; button labels remain upright.
- Solar recorded-frame display rotation takes 240 seconds. Actual Flutter Solar effects and shaders remain unchanged.
- Motion stops when the pointer enters the near zone, before reaching a button. Each button has a 90px proximity zone, with a larger shared approach zone around the orbit.
- Pointer presses, typing and keyboard-visible focus hold motion. Resume follows a 1.5-second departure delay; pressing holds for at least 2.5 seconds.
- Reduced motion uses fixed targets; hidden browser pages stop motion updates.
- The waveform sits below the whole orbital area. Chat disclosure sits farther below, outside every button path.
- The preview samples 259,200 button positions across full turns, 3–6 actions, 360/440 widths and 560/680 heights. No sampled button/button, button/Solar, bounds or waveform-path collision was found. This is sampled geometric evidence, not exhaustive native qualification.
- At constrained heights, the optional chat disclosure scrolls within its remaining space rather than covering the waveform or buttons.

The HTML buttons, chat text and audio are simulated. The page has no microphone, account, Brain or runtime access. The production A2UI service catalog is not altered by the HTML preview. Flutter has a separate trusted local A2UI producer for Companion controls, and the runtime hub continues to reject that local catalog.

## Implemented candidate

The approved detached chat now uses the same AppState or OI conversation and LivingComposer as Workspace. Chat toggles disclosure; closing it preserves the draft and conversation. Review navigates to the existing task review, with no automatic decision. Voice actions are generated only when the existing service supports them. Dashboard stays available. Idle listening draws short marks; actual RMS level drives bar height. This is a level visualization, not a frequency spectrum.

Floating controls now use circular icon-and-label buttons. Sparse brass arcs follow the approved image. Normal-size controls orbit once in 180 seconds, labels upright, on the existing Companion frame clock with geometry updates capped at 10Hz. The existing Solar renderer/shaders are unchanged. Proximity within 80 logical pixels of the orbit bounds, pointer interactions, open chat, composer focus, active voice, reduced motion and large text stop orbital travel. Departure holds it for 1.5 seconds. Hidden windows suspend the shared clock. At large text or more than four contextual actions, stationary readable controls replace orbiting circles.

Windows gets only own-window cursor coordinates; no global hook, desktop screenshot or microphone observation is added. The native region combines the actual Companion ellipse, circular buttons, narrow arc strokes, waveform region and the visible chat rectangle. Transparent gaps are excluded from the region. Native compositing/cross-application click-through and multi-DPI/monitor behavior remain NOT VERIFIED.

## Isolation and launch

Worktree: `C:\Users\cheta\Development\uri-ui-v2`; branch: `ui/companion-v2-visual-qualification`. Accepted base: `1b5423bc15fd7e5da9161c862cf839925da9f2eb`. A local candidate snapshot is separate from independent acceptance. No merge, push, deployment or live-server replacement.

From `uri_ui`:

```powershell
# Explicit offline fixture preview, no real authentication demonstration.
flutter run -d windows --no-pub -t lib/main_v2_preview.dart
# Real bootstrap/authentication entry. No owner-server live testing was done.
flutter run -d windows --no-pub -t lib/main_v2.dart
```

The offline entry does not open a microphone or fabricate voice availability; its Voice action is absent until a supported service exists. Capture fixtures separately exercise all three approved controls, with audio events injected and labelled simulated. Wake phrase “oii URI” is unsupported by the accepted voice baseline.

See [current evidence](CURRENT_UI_EVIDENCE.md), [visual comparison](companion-review.html) and [qualification details](VISUAL_QUALIFICATION.md). Full implementation verdict: **NOT READY — BLOCKERS**: native/runtime qualification, formal independent acceptance and visual discrepancy disposition remain outstanding. Owner approval of the supplied image resolves the design choice; it does not silently qualify code.
