# Discovery report — actual Companion baseline

Canonical independently accepted development pin: `1b5423bc15fd7e5da9161c862cf839925da9f2eb`, remote `uri-repo`, branch `integration/git-sync-20261008`; rechecked on 2026-10-13. The original uri-agent checkout is an older dirty line. Work is confined to `C:/Users/cheta/Development/uri-ui-v2`, branch `ui/companion-v2-visual-qualification`. Office M2 and experimental Harness/Console overlays are separate candidates and were not integrated.

## Existing renderer inventory

| Identity / actual display name | Existing implementation |
|---|---|
| Solar | companion_solar.frag |
| Sakura | companion_sakura.frag |
| Lunar | companion_lunar.frag |
| Moonlit Blossom | companion_moonlit.frag |
| Fluid Plasma | EnergyOrb / nebula |
| Aurora Vortex | EnergyOrb / halo |
| Particle Intelligence | EnergyOrb / swarm |
| Holographic Atmosphere | EnergyOrb / glass |
| Sun / Flow | EnergyOrb / flow |
| Neural Filaments | EnergyOrb / mesh |
| Electric Core | EnergyOrb / energy |

Source: `uri_ui/lib/living/companion/companion_orb.dart`, `energy_orb.dart`, `living_companion.dart`, `companion_preferences.dart`, existing shader assets and frame clock. Discovery found eleven renderable designs across two historical families, rather than relying on the owner-reported approximate count. A catalog adapter exposes them as one Companion system. No shader or EnergyOrb renderer was changed; Solar gets presentation-only framing in compact mode. The actual procedural designs are not rotatable 3D objects.

Shared state projection supports unavailable, idle, listening, thinking, speaking, working, awaitingApproval, success and error. Existing expression parameters/shader uniforms, quality/frame-rate controls, reduced effects and hidden-window suspension remain the baseline. Some source comments say voice is mock-only; later call paths through LiveVoiceService/VoiceInteractionController supersede those historical comments. No live device verification was performed.

Owner-reported native transparency/speech behavior was checked against the pin. The inspected accepted adapter primarily resized windows and exposed local poke/text acknowledgement. Candidate transparency/frameless hit regions and optional local acknowledgement speech were added in isolated UI/native code; this is not evidence that all reported desktop behavior was already verified in the accepted pin. Existing single/double-tap arbitration and shared conversation/presentation controllers were reused.

Classic HTTP, paired/supervised worker, integrated OI runtime, scheduler and Office dependencies remain distinct. No runtime API, authority or grant was added. Login/bootstrap/session handling stays behind real gates. The optional worker entry requires an explicitly isolated manifest; it was not launched. The offline preview is fixture-only and cannot demonstrate successful authentication or real execution.

The 35-ID inventory and matrix bound current traceability. They do not assert an exhaustive legacy control/unreachable-route audit. Existing screens remain accessible; Office and experimental Console functionality is not labelled integrated. Frozen UI/Core/security paths have zero candidate delta against the accepted pin. The historical frozen checkpoint already fails in the accepted baseline: 120/121 hashes match, with server.py drift and two historical protected-path deviations. No checker was weakened.

See DESIGN_SOURCE_INVENTORY.json, COMPANION_THEME_SPEC.md and CURRENT_UI_EVIDENCE.md for exact references and separate implemented/tested/recorded/integration/deployment status.
