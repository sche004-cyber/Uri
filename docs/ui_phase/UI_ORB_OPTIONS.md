# Energy Orb options (owner choice)

Date: 2026-10-08. Author: Claude. Status: six variants IMPLEMENTED on one state engine; default `nebula`; owner choice PENDING. Switch at runtime in Workspace > Settings > Orb style, or start the preview with `URI_LIVING_ORB_VARIANT=<name>`.

Owner reference (shared mid-session, saved as `docs/ui_phase/references/owner_orb_reference_2026-10-08.jpg`): six concept renders titled Particle Intelligence ("my first choice"), Liquid Energy, Neural Mesh, Liquid Glass, Plasma Core, Ethereal Orb. The variants below map onto them; none copies the renders, all are drawn procedurally in Flutter and react to state, cursor and click.

Screenshots from the real Windows release build (`docs/ui_phase/screenshots/orb_*.png`, captured by `docs/ui_phase/tools/capture_screenshots.ps1 -Only "orb_*"`).

| Variant (`OrbVariant`) | Maps to owner reference | What it is | Idle | One state | Strengths | Trade-offs |
|---|---|---|---|---|---|---|
| `swarm` | 1 Particle Intelligence (owner's first choice) | no solid body; ~260 soft particles cohere into a sphere, gather/disperse with the breath; thinking tightens, error scatters | `orb_swarm_idle.png` | `orb_swarm_thinking.png` | closest to the reference; reads as "intelligence", not a ball; the gust reaction is most visible here | least defined silhouette at 72 px (rail); most particles per frame (still cheap: 260 circles) |
| `nebula` | 2 Liquid Energy / 5 Plasma Core | shader plasma core, thin limb, loose particle shell (the first build's default) | `orb_nebula_idle.png` | screenshots 01-03 | strongest "energy inside" read; shader does the work | the most literal "glowing ball"; shader off under reduced effects (gradient fallback) |
| `mesh` | 3 Neural Mesh | 72 nodes on a Fibonacci sphere joined by short edges, turning slowly; thinking brightens, error breaks edges | `orb_mesh_idle.png` | `orb_mesh_approval.png` | explicit "network" metaphor; crisp at every size; no shader needed | O(n²) edge pass (72 nodes: trivial); less warmth; can look technical/cold |
| `glass` | 4 Liquid Glass | frosted sphere, dim inner swirl, specular highlight, lit lower rim, few particles | `orb_glass_idle.png` | `orb_glass_error.png` | most "premium object"; calmest; best fit for the glass UI language | least alive at idle; state tints are subtler (owner may want stronger tints) |
| `halo` | 6 Ethereal Orb | small bright core, one wide luminous tilted ring (echoes the eclipse wordmark), particles ride the ring | `orb_halo_idle.png` | `orb_halo_success.png` | ties to the existing brand mark; distinct silhouette | ring reads as a planet/loader if overused; the working arc overlaps the ring |
| `flow` | owner request: "particles coming out of the core" | plasma core that emits its particles: born at the limb, spiral outward, fade, reborn; state sets the emission rate | `orb_flow_idle.png` | `orb_flow_working.png` | motion has a clear direction and cause; thinking visibly "pours out" | needs the ticker (static frame shows a snapshot of the stream); busiest at idle unless the rate is lowered |

## Shared behaviour (every variant)

* Nine states, same tints, rings, arcs, bloom and ripples (`OrbParams`), tweened over 650 ms.
* Cursor gust: sweeping the pointer across the orb pushes nearby particles along the sweep and scatters them from its path, decaying over 1.4 s, like leaves in a gust (`_Gust`, `_OrbPainter._place`). Pure presentation; no state change; off when the ticker is off (reduced motion) or `interactive: false`.
* Click: a poke (core bump, burst ring, outward kick of the particles) plus a question bubble under the orb ("Yes? What should I do?"; UI-local copy, never a Brain reply) while the composer takes focus. Double-click opens the Workspace.
* Reduced effects: shader and blur masks off, everything else on. Reduced motion: still frame.

## Recommendation

`swarm` as the default if the owner's "first choice" stands, with `flow` as the alternative when motion with a visible source is wanted. `glass` is the most restrained match for the Dark Glass language and the safest at small sizes. `nebula` remains the current default until the owner decides (changing the default is one enum value in `LivingServices.orbVariant`).

## Not done

No Blender/3D render. No variant blends (e.g. mesh over glass); straightforward to add as a composite case in `_OrbPainter.paint` if wanted. No per-variant performance table yet beyond the profile numbers in `UI_TEST_EVIDENCE.md`.
