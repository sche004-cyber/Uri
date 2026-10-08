# Energy Orb options (owner choice)

Date: 2026-10-08 (revised the same day after the owner's references). Author: Claude. Status: seven styles and ten palettes IMPLEMENTED on one state engine; default style `nebula` (Fluid Plasma) with its own palette; owner choice PENDING. Switch at runtime in Workspace > Settings > Orb style / Orb palette, or start the preview with `URI_LIVING_ORB_VARIANT=<style>` and `URI_LIVING_ORB_PALETTE=<palette>`.

## Owner references (saved under `docs/ui_phase/references/`)

| File | Content | What it changed |
|---|---|---|
| `owner_orb_reference_2026-10-08.jpg` | six concept renders: Particle Intelligence ("my first choice"), Liquid Energy, Neural Mesh, Liquid Glass, Plasma Core, Ethereal Orb | the first variant set |
| `owner_flowing_energy_reference_2026-10-08.jpg` | Fluid plasma, Particle intelligence (ribbon streams of particles), Neural filaments (threads leaving a translucent blob), Electric core, Holographic atmosphere, Aurora vortex | the second rework: energy as glowing ribbons under a translucent surface; each style its own structure |
| `owner_style_palette_state_board_2026-10-08.jpg` | 1 orb styles, 2 colour variations ("the same style in different palettes"), 3 state examples, 4 palette collections | palettes decoupled from styles; ten palettes named after the board |

Owner notes applied: "particles flowing out of the core" (Sun / Flow), cursor gust reaction, click response with a question, "different character and structure to each orb" and "why all the same colour". Suggested inspiration beyond stills (Blender particle energy orbs, TouchDesigner audio-reactive energy, real-time shader spheres): explored as technique references only. Blender is not installed here and a baked animation cannot react to live state; the audio-reactive idea maps directly onto the Listening/Speaking states once a voice source exists (amplitude would drive `OrbParams.energy`); the real-time shader approach is what the core already uses (`shaders/orb_core.frag`, three styles).

## Styles (`OrbVariant`, labels as on the owner's board)

Screenshots from the real Windows release build (`docs/ui_phase/screenshots/orb_*.png`, `palette_*.png`, `orb_variants_sheet.png`).

| Style | Enum | Structure | Energy behaviour | Default palette |
|---|---|---|---|---|
| Fluid Plasma | `nebula` | translucent sphere; five wide glowing ribbons circulating beneath the surface over a liquid-vein shader base; rim light and specular | slow circulation; thinking speeds and brightens the ribbons | Signature (cyan / blue / violet) |
| Particle Intelligence | `swarm` | 360 particles riding four ribbon streams inside the sphere, plus a loose mist | gather / disperse with the breath; thinking tightens the streams; error scatters | Aurora (cyan / violet / pink) |
| Neural Filaments | `mesh` | pale translucent body with a dim shader swirl; fourteen delicate light threads leaving the sphere, bright at the tips | threads drift slowly; working/thinking lengthen and brighten them; error makes them tremble | Soft Pastel (ice / pink / lavender) |
| Electric Core | `energy` | concentrated hot centre; bolts passing outward to the surface; six fast thin ribbons | bolts flicker 6-16x per second with energy; the core pulses | Royal (blue / purple) |
| Holographic Atmosphere | `glass` | three concentric translucent shells with coloured rims turning in opposite directions; dim inner ribbons; chromatic rim; big specular | calm; layers turn faster when working | Deep Ocean (teal / blue) |
| Aurora Vortex | `halo` | nine ribbons orbiting a tilted axis, wide and soft, under a surface | continuous orbital motion; thinking speeds it; approval slows it | Aurora |
| Sun / Flow | `flow` | granular hot shader surface, red-orange corona with slow rays, prominences leaping off the limb, embers emitted from the limb outward | emission rate follows the state (thinking pours out, approval nearly still) | Sunset (amber / orange / pink) |

## Palettes (`OrbPalette`, any style)

Signature (cyan / blue / violet), Deep Ocean (teal / blue), Aurora (cyan / violet / pink), Nature (green / teal), Sunset (amber / orange / pink), Royal (blue / purple), Passion (red / orange), Soft Pastel (ice / pink / lavender), Monochrome (white / silver), Rainbow (five hues). Examples: `palette_nebula_sunset.png`, `palette_nebula_nature.png`, `palette_halo_rainbow.png`, `palette_energy_passion.png`, `palette_swarm_mono.png`.

## States on any style/palette

The nine states keep their meaning: tints lean every palette hue toward amber (needs you), green (done), red (attention) or grey (unavailable) by `OrbParams.tintMix`, and the overlays (approval ring with three markers, working arc or progress arc, done bloom, speaking/listening ripples) are drawn in the tinted colour. The owner's board uses amber for "completed" and orange for "needs approval"; this build keeps green for done so it never resembles the approval amber. Changeable in one place (`_tintFor` in `energy_orb.dart`) if the owner prefers the board's colours.

## Shared behaviour (every style)

* Cursor gust: sweeping the pointer over the orb pushes particles and bends ribbons and threads along the sweep, decaying over 1.4 s (`_Gust`, `_place`, `_gustAt`).
* Click: poke (core bump, burst ring, outward kick) plus a UI-local question bubble ("Yes? What should I do?") and composer focus. Double-click opens the Workspace.
* Reduced effects: no shader, no blur, no additive glow passes; structure and tints remain. Reduced motion: still frame.

## Recommendation

Fluid Plasma (Signature) as the default companion: the calmest at idle and the clearest at 72 px in the rail. Particle Intelligence (Aurora) when the owner wants the "thinking" state to be the most expressive. Sun / Flow is the most distinctive but the warmest, which fights the cool UI chrome unless the palette is changed with it.

## Not done

No Blender/TouchDesigner assets; no audio reactivity (no voice source yet). Performance per style is in `UI_TEST_EVIDENCE.md`; the ribbon styles use blurred additive strokes and cost more than the particle-only first build (numbers there).
