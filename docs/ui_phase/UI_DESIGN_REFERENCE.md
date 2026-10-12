# UI design reference: Living Companion

Date: 2026-10-08. Author: Claude. Status: design decisions RECORDED; visual direction IMPLEMENTED in `uri_ui/lib/living/` and `uri_ui/lib/theme/glass_theme.dart`; owner acceptance of the direction PENDING.

Process followed: the repository's reference-first rule (`.claude/skills/uri-ux-design/SKILL.md`). Backend capability was inspected first (`docs/architecture/PHASE2CLOSE_UI_READINESS.md`, `uri_ui/lib/services/*.dart`), the design library was consulted (`docs/design_library/approved/hybrid_ui_2026-09-16.md` is the approved structure; nothing in `rejected/` covers an orb or a companion form), then references were researched for the three new directions the brief introduces. The Hybrid structure (5 destinations) is kept as the Workspace rail's content model; the living experience is a presentation layer over the same `AppState`.

## 1. Research references (not copied; cited for the decision they informed)

| Reference | What it informed | Verified how |
|---|---|---|
| Flutter codelab "Building next generation UIs in Flutter" (Google, `codelabs.developers.google.com/codelabs/flutter-next-gen-uis`) | Orb as a fragment shader + particle field on desktop; the three-OS desktop target; `FragmentProgram` usage | web search 2026-10-08 |
| Flutter 3.47 release notes / coverage (`startdebugging.net/2026/08/flutter-3-47-impeller-default-renderer-on-desktop/`, `docs.flutter.dev/perf/impeller`) | Impeller is the Windows default from 3.47 (this toolchain is 3.47.2), so runtime shaders and backdrop blur are first-class; `--no-enable-impeller` is the escape hatch | web search 2026-10-08; `flutter --version` |
| `flutter_shaders_ui` / `glow_orb` on pub.dev | Confirmed the same `FragmentProgram` approach; not adopted (one effect, one dependency each) | web search 2026-10-08 |
| "Thinking Orbs" (Product Hunt, 2026-10-05) and 21st.dev "AI Thinking Orb" | Convention that state (idle / thinking / processing) is shown by motion density and colour temperature, not by icons | web search 2026-10-08 |
| Framer "AI Orb Lab" / "interactive orb face" | Frosted shell + inner swirling core + single glow spot reads as calm and premium; a face was rejected (URI is not a character) | web search 2026-10-08 |
| Glassmorphism guidance (LogRocket "what is glassmorphism"; daisyUI trend page; superdesign "glass dark UI") | Restraint rules adopted: few frosted planes, obvious front-to-back order, no nested glass, dark fill with a thin inner highlight, blur as the only costly effect | web search 2026-10-08 |
| URI design library screenshots (`docs/design_library/screenshots/*.jpg`) | Dashboard tile density ceiling (shadcnstore moderate grid, not tabler's); two-pane chat shape | repository |
| Existing URI wordmark (`uri_ui/lib/widgets/uri_wordmark.dart`, "eclipse" mark) | The orb's thin bright limb and off-centre highlight echo the eclipse mark so the companion and the brand read as one | repository |

No reference image was copied into the repository. Screenshots of the implemented UI are in `docs/ui_phase/screenshots/` (captured by `docs/ui_phase/tools/capture_screenshots.ps1` from the real Windows build).

## 2. Visual language: "Obsidian Cyan"

Tokens live in code (`UriColors.obsidianCyan`, `UriGlass.fromPalette`). Rationale per token:

| Token | Value | Why |
|---|---|---|
| canvas | `#070A0F` | near-black with a blue cast so cyan light reads as illumination, not as a colour fill |
| surface / surfaceSunken | `#0E131A` / `#141B24` | two steps up for layered depth without borders |
| border | `#1E2A36` | hairline only; glass panels use a white veil at 10% instead |
| ink / inkSoft / inkFaint | `#E6EEF5` / `#9FB0C0` / `#70849A` | three text tiers; contrast on canvas 16.9:1 / 8.9:1 / 5.2:1 and on surfaceSunken 15.9:1 / 8.4:1 / 4.5:1 (computed 2026-10-08, WCAG AA for normal text on all three; inkFaint was `#5F6F80` = 3.8:1 in the first commit and was raised after the check) |
| accent (glow) | `#38D1E8` | the one illumination colour; contrast 10.8:1 on canvas; canvas-coloured text on an accent button 10.8:1 |
| accentSoft / accentInk | `#0F2A33` / `#8AE6F3` | selected-row wash and link/ink tint |
| success / warning / danger | `#4FD6A6` / `#E8B44F` / `#FF7A7A` | state tints the orb borrows for Done / Needs you / Attention |
| glass fill / fillStrong | white 4.5% / 8% | panels and composer |
| glass highlight | white 20% | one-pixel top light catch |
| blurSigma | 18 | backdrop blur, opt-in per panel (composer only); off under reduced effects |
| specular | white on dark palettes, `#F4FAFF` on the light one | the brightest light the orb may paint (highlights, hot core); a token so `lib/living` names no literal colour (Codex round 2, finding 2) |

Typography: Segoe UI (the app's existing family), weights 400/600/700, eyebrows at 10.5 px uppercase with 1.2 px tracking. No new font asset.

Motion: `UriMotion.fast` 160 ms (chips, notices), `mode` 520 ms with `easeInOutCubicEmphasized` (orb travel, content cross-fade), `orbState` 650 ms (state tween). Only the orb moves continuously; panels move once and rest.

Avoided on purpose (brief section 2C): neon outlines, scanlines, grid overlays, glowing borders on every panel (only "needs you" and selected rows glow), constant particle fields behind content, more than ~3 glass panels per viewport.

## 3. The Energy Orb: state language

One drawing, nine parameter sets (`OrbParams.forState`), tweened on change. What each state does, and the fact it is allowed to come from:

| State | Look | Allowed source |
|---|---|---|
| Unavailable | dim, desaturated, 0.12 Hz breath, sparse slow particles | preflight failed / no opt-in |
| Idle | calm cyan breath 0.18 Hz, loose particle orbit | nothing pending or running |
| Listening | brighter, inward ripples, wider orbit, faint ring | voice listener (none in this tree; mock only) |
| Thinking | fast inner swirl, particles pulled tight and quick, high energy | `isSendingAsk` / turn understanding |
| Speaking | outward ripples at 2.2 Hz, medium energy | TTS/streaming (mock only) |
| Working | rotating orbit arc; a progress arc when a percentage exists | execution queued/approving/starting/running |
| Needs your approval | amber tint, slow, pulsing ring with three markers, particles nearly still | approval_required / clarification |
| Done | green tint, expanding bloom ring, bright core; held 3-4 s then idle | corroborated completion |
| Attention needed | red tint, contracted, turbulent streaks, dim ring | failed / uncertain / unreachable |

Under reduced effects the shader and blur masks are off; the gradient core, particles, tint, ring, arc, bloom and ripples remain, so every state is still distinct (tested). Under reduced motion the orb is a still frame; state is carried by tint, ring, badge and the status line.

### 3.1 Styles, palettes and interactions (owner's mid-session input, three reference images under `references/`)

Seven styles share the state engine (Fluid Plasma, Particle Intelligence, Neural Filaments, Electric Core, Holographic Atmosphere, Aurora Vortex, Sun / Flow), each with its own structure and energy behaviour; ten colour palettes are independent of style (the owner's board: "the same orb style expressed in different colour palettes"). The orb's colours therefore come from `OrbPalette` (a declared token table named after the board) rather than from the UI theme accent; the UI chrome keeps the Obsidian Cyan tokens. Energy is drawn as glowing ribbons under a translucent surface (soft additive pass + thin hot core, smoothed quadratic curves), bolts, threads, shells or embers depending on the style. Details and screenshots: `UI_ORB_OPTIONS.md`. Two interactions on every style: a cursor gust (particles, ribbons and threads pushed along a pointer sweep, decaying over 1.4 s) and a click poke (core bump, burst ring, outward kick) with a UI-local question bubble and composer focus. Double-click opens the Workspace.

### 3.2 Blur policy (changed after the first profile run)

Backdrop blur is opt-in per `GlassPanel` and used only by the composer. Over the flat ambient gradient a blur adds cost without depth: eight blurred dashboard tiles measured 22 ms raster p95 (profile build) before the change. The glass look is carried by the translucent fill, hairline border and top highlight.

## 4. Three forms, one companion

| Form | Orb dock | Content |
|---|---|---|
| Companion | centre, 180-320 px | status line, state action ("Review and decide"), composer, two mode chips |
| Workspace | top of the rail, 72 px | rail (Conversation, Tasks, Documents, Intelligence, Settings; Dashboard, Companion), focus region, context panel (open at >= 1180 px or on demand) |
| Dashboard | top centre, 128 px | eight tiles: Readiness, Current tasks, Brain & models, Harnesses, Connected clients, Permissions, Capabilities, Selected harness |

Transition: the orb is one element (`LivingShell.orbKey`) inside an `AnimatedPositioned`; content cross-fades with a 1.5% drift. The ambient light pool moves with the orb. Tests assert element identity across all three forms.

## 5. Workspace progressive disclosure

Shown always: the rail and the focus region. Shown on demand or on wide windows: the context panel (Now, Executor, Context & files, Results). Shown only when relevant: approval cards (glow border), "Review and decide" in Companion, the command notice after a command-driven switch. Hidden until opened: Settings (harness, Brain, reasoning, approval boundary, permissions, appearance), Intelligence.

## 6. Design-library record

A record for this direction is at `docs/design_library/approved/living_companion_2026-10-08.md` with status "IMPLEMENTED CANDIDATE, owner acceptance pending" (the library's `approved/` folder is used because the structure is implemented, not because the owner has accepted it; the record says so in its first line).
