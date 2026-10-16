from pathlib import Path
import json, hashlib, subprocess
root=Path('.').resolve(); d=root/'docs/ui_v2'
rows=[
('UI-001','Bootstrap','uri_ui/lib/screens/bootstrap/bootstrap_screen.dart','class BootstrapScreen','Server address / validation / connection test','Existing HTTP bootstrap','preserved themed candidate','bootstrap_screen_test.dart'),
('UI-002','Login','uri_ui/lib/screens/auth/login_screen.dart','class LoginScreen','Login / password / submit / errors / signup','Existing auth callbacks / AppState','implemented candidate','living/ui_v2_test.dart'),
('UI-003','Classic onboarding','uri_ui/lib/screens/onboarding/onboarding_screen.dart','class OnboardingScreen','Focus / style / approval preference / skip','Existing user preferences; UX-only approval preference','preserved baseline','onboarding_screen_test.dart'),
('UI-004','Brain setup','uri_ui/lib/screens/onboarding/brain_onboarding_screen.dart','class BrainOnboardingScreen','Provider / model / next / skip','Existing provider APIs','preserved baseline','brain_onboarding_test.dart'),
('UI-005','Living setup','uri_ui/lib/living/screens/onboarding/living_onboarding_flow.dart','class LivingOnboardingFlow','Connect / Harness / Brain / Permissions / ready','Readiness source; existing authority unchanged','preserved baseline','living/living_onboarding_test.dart'),
('UI-006','Dashboard','uri_ui/lib/living/screens/frost_dashboard.dart','class FrostDashboard','Six destination cards / composer / navigation','Shared AppState, readiness, work, presentation','implemented candidate','living/ui_v2_test.dart'),
('UI-007','Artwork','uri_ui/lib/living/screens/frost_dashboard.dart','class UriArtwork','Unframed engraving / responsive reservation','Local cutout image; no actions','implemented candidate','living/ui_v2_test.dart'),
('UI-008','Companion click','uri_ui/lib/living/presentation/living_shell.dart','void _onOrbTap','Single acknowledgement / reveal; double Dashboard','Existing speech service; no Brain ask','implemented candidate','living/ui_v2_test.dart'),
('UI-009','Companion buttons','uri_ui/lib/living/screens/companion_mode_view.dart','static List<CompanionUiAction> actions','Chat / Dashboard / available Voice / contextual Review','Separate local A2UI catalog, guarded voice controller','implemented candidate','living/ui_v2_test.dart'),
('UI-010','Detached chat','uri_ui/lib/living/screens/companion_mode_view.dart','class _DetachedChat','Conversation / scroll / close / submit','Same AppState or OI, LivingComposer','implemented candidate','living/ui_v2_test.dart'),
('UI-011','Orbital layout','uri_ui/lib/living/screens/companion_mode_view.dart','static Map<CompanionUiAction, Rect> buttonRects','Circular targets / safe paths / large-text fallback','Host geometry; no runtime state mutation','implemented candidate','living/ui_v2_test.dart'),
('UI-012','Orbit pause','uri_ui/lib/living/presentation/living_shell.dart','void _orbitTick','Pointer approach / focus / hidden / reduced motion','Existing paced frame clock; own-window cursor only','implemented candidate','living/ui_v2_test.dart'),
('UI-013','Native overlay','uri_ui/lib/services/companion_window_adapter.dart','class CompanionWindowAdapter','Frameless / restore bounds / move / clamp','Windows window_manager + own native channel','implemented; desktop behavior unverified','living/ui_v2_test.dart'),
('UI-014','Native hit regions','uri_ui/windows/runner/flutter_window.cpp','HRGN orb =','Companion ellipse / circles / narrow arcs / chat / waveform','Native SetWindowRgn; target-window DPI','implemented; 96 DPI region inspection only',''),
('UI-015','Audio level bars','uri_ui/lib/living/voice/voice_waveform.dart','class VoiceBarsPainter','RMS bars; silent listening marks','Existing live level/flux; existing hidden/paced clock','implemented candidate','living/ui_v2_test.dart'),
('UI-016','Voice activation','uri_ui/lib/living/screens/companion_mode_view.dart','case CompanionUiAction.voiceStart','Start / finish / cancel only when available','Existing VoiceInteractionController; no wake detector','implemented clicks; wake phrase unsupported','living/ui_v2_test.dart'),
('UI-017','Companion catalog','uri_ui/lib/living/companion/companion_design.dart','class CompanionDesign','Eleven existing renderer identities','Four Living + seven Classic; procedural 2D','implemented candidate','living/ui_v2_test.dart'),
('UI-018','Theme independence','uri_ui/lib/living/companion/companion_preferences.dart','class CompanionPreferences','Explicit theme / original follow / persistence / fallback','Existing preference store; no runtime schema','implemented candidate','living/ui_v2_test.dart'),
('UI-019','Gallery','uri_ui/lib/living/screens/settings/companion_gallery.dart','class CompanionGallery','Select / preview states / zoom / larger / Apply / Cancel','One isolated renderer; no active request/audio mutation','implemented candidate; no true 3D rotation','living/ui_v2_test.dart'),
('UI-020','Shared composer','uri_ui/lib/living/widgets/living_composer.dart','Future<void> _submit','Draft / attachments / enter / send / busy','AppState.ask OR OI.send; UI commands intercepted','preserved service path / compact view','living/ui_v2_test.dart'),
('UI-021','Workspace','uri_ui/lib/living/screens/workspace_mode_view.dart','class WorkspaceModeView','Conversation / tasks / drafts / intelligence / settings','Existing Classic HTTP and OI paths remain distinct','preserved candidate navigation','living/living_shell_test.dart'),
('UI-022','OI stream','uri_ui/lib/living/integration/oi_widgets.dart','class OiConversationPane','Messages / busy / errors / confirmations / approval review','Integrated OI event stream; digest-bound explicit decisions','preserved; compact transcript reused','ws/ws_integration_test.dart'),
('UI-023','Task review','uri_ui/lib/screens/tasks/tasks_screen.dart','class TasksScreen','Task list / details / status','Classic HTTP AppState tasks','preserved baseline','tasks_screen_test.dart'),
('UI-024','Supervised task','uri_ui/lib/screens/tasks/supervised_execution_screen.dart','class SupervisedExecutionScreen','Approve / cancel / checkpoints / receipts','Paired/supervised worker; frozen file unchanged','preserved frozen baseline','supervised_execution_screen_test.dart'),
('UI-025','Draft desk','uri_ui/lib/living/integration/draft_panel.dart','class DraftPanel','Current / changes / original / undo / redo / copy','Existing OI draft model','preserved baseline','ws/ws_integration_test.dart'),
('UI-026','Providers','uri_ui/lib/screens/settings/providers_screen.dart','class ProvidersScreen','Credentials / model / subscription / local / fallback','Existing provider APIs; no automatic auth grant','preserved baseline','providers_screen_test.dart'),
('UI-027','Connections','uri_ui/lib/screens/connections/connections_providers_screen.dart','class ConnectionsProvidersScreen','Connect / reconnect / disconnect / Brain','Existing services and classic navigation','preserved baseline',''),
('UI-028','Memory','uri_ui/lib/screens/settings/memory_context_settings_screen.dart','class MemoryContextSettingsScreen','Remember / edit / forget / context preferences','Existing memory APIs','preserved baseline',''),
('UI-029','Intelligence','uri_ui/lib/living/screens/intelligence/intelligence_overview_view.dart','class IntelligenceOverviewView','Budgets / facts / sources / memory views','Existing intelligence sources','preserved baseline',''),
('UI-030','Settings','uri_ui/lib/screens/settings/settings_shell.dart','class SettingsShell','Profile / preferences / devices / runtime / about','Frozen settings shell / existing service contracts','preserved frozen baseline',''),
('UI-031','Diagnostics','uri_ui/lib/screens/settings/diagnostics_settings_screen.dart','class DiagnosticsSettingsScreen','Health / runtime facts / diagnostic details','Existing diagnostics APIs','preserved baseline',''),
('UI-032','Admin grants','uri_ui/lib/screens/settings/admin_grants_screen.dart','class AdminGrantsScreen','Review grant changes / explicit submission','Existing authorization APIs; never UX auto-grants','preserved baseline',''),
('UI-033','Scheduler','uri_ui/lib/living/screens/scheduler/scheduler_view.dart','class SchedulerView','Jobs / upcoming / executions / review','Existing scheduler service, distinct from OI/HTTP','preserved baseline',''),
('UI-034','Assist','uri_ui/lib/living/assist/assist_mode_view.dart','class AssistModeView','Scope / suggest / pause / resume / revoke / research','Existing Assist adapter permissions; unavailable tabs stay unavailable','preserved baseline','living/assist_mode_test.dart'),
('UI-035','Runtime A2UI','uri_ui/lib/living/a2ui/a2ui_hub.dart','class A2uiHub','Validated panels / actions / notices / reject','Existing runtime catalog vs separate host-local catalog','preserved validation / host-local extension','living/a2ui_test.dart'),
]
base='1b5423bc15fd7e5da9161c862cf839925da9f2eb'
inv=['# Screen and function inventory — bounded implementation ledger','',f'Accepted base: `{base}`. Candidate source revision is the local Git snapshot identified by HEAD/lifecycle receipt; exact file hashes are in WORKING_STATE.json. This is the V2 implementation inventory, not a claim of an exhaustive audit of every legacy inline control or unreachable experimental route. Office M2 and dirty Harness/Console overlays remain separate unintegrated candidates.','', '| ID | Entry / controls | Exact candidate source | State owner / dependency | Implementation evidence | Acceptance scenario |','|---|---|---|---|---|---|']
cov=['# Functional coverage matrix','', 'Owner visual approval applies to the image, not candidate code. Unit/widget fixtures, recorded render captures, independent acceptance, integration and deployment are separate evidence fields. No Figma node links are claimed.','', '| ID | Destination / component | Existing test evidence | Recorded verification | Independent integration | Deployment |','|---|---|---|---|---|---|']
for id,surface,file,anchor,controls,dep,state,test in rows:
 p=root/file; line=None
 if p.exists():
  for n,l in enumerate(p.read_text(encoding='utf-8-sig').splitlines(),1):
   if anchor in l:line=n;break
 source=f'[{Path(file).name}](../../{file}'+(f'#L{line}' if line else '')+')'+(f' line {line}' if line else ' (anchor unverified)')
 inv.append(f'| {id} | {surface}: {controls} | {source} | {dep} | {state} | Exercise controls, retain context, report unavailable/errors truthfully; no implicit decision |')
 tp=root/'uri_ui/test'/test if test else None
 evidence=f'[{test}](../../uri_ui/test/{test}) — fixture coverage, see raw suite log' if tp and tp.is_file() else 'Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it'
 record='Engine capture + fixture interaction; native/runtime caveats in CURRENT_UI_EVIDENCE.md' if id in {'UI-002','UI-006','UI-007','UI-008','UI-009','UI-010','UI-015','UI-017','UI-019'} else 'Source/test inspection; live journey NOT VERIFIED'
 cov.append(f'| {id} | {surface} | {evidence} | {record} | None for new candidate | None |')
(d/'SCREEN_AND_FUNCTION_INVENTORY.md').write_text('\n'.join(inv)+'\n',encoding='utf-8');(d/'FUNCTIONAL_COVERAGE_MATRIX.md').write_text('\n'.join(cov)+'\n',encoding='utf-8')
(d/'COMPANION_THEME_SPEC.md').write_text('''# Companion and interface compatibility

One Companion catalog represents all eleven existing identities: four Living and seven Classic renderer variants. There is no separate new Orb-style system, new 3D engine, creature or shader dependency. Every catalog entry retains its actual renderer and original interface theme.

The persisted interface override is nullable. Null means original-theme following; an explicit installed theme remains selected when Companion identity changes. Switching interface theme never restyles the underlying model. Unknown/obsolete references use the existing predictable fallback; legacy preferences migrate through the existing store. Gallery previews use isolated preferences and one renderer; only Apply changes the active identity/theme. Cancel discards preview changes. True 360-degree model rotation is unavailable because the current designs are procedural 2D. Zoom/state previews and larger inspection are provided.

Solar uses presentation framing 1.85 only in V2 Companion mode. This compensates for the existing renderer’s intentional half-box body footprint. The renderer, shader uniforms, state, identity palette and saved look remain unchanged, with the existing SoftDisc keeping the atmosphere within its reserved box. Dashboard and other identities retain their original framing.

| Interface theme | Canvas | Surface | Text | Brass |
|---|---|---|---|---|
| Ivory Foundry | #E9E3D5 | #F2EDE2 | #292821 | #77603C |
| Snow Archive | #F5F4EF | #FFFEFA | #292A27 | #776541 |
| Ash & Limestone | #BABBB5 | #D1D0C7 | #262824 | #55462D |

These are the three approved reference palettes. Existing legacy themes remain supported for saved/original-theme compatibility. The V2 explicit selector presents the three approved choices; no neon/teal scheme was added. Status always retains textual labels; automated contrast checks cover the theme tokens. Floating audio status uses ivory text with a small dark shadow over the transparent desktop.

Contextual controls are generated by a trusted local A2UI producer with its own catalog. The runtime hub rejects that catalog. Only the host chooses circular icons/presentation; model definitions cannot opt into host controls, grant authority, select executors or approve tasks.
''',encoding='utf-8')
(d/'INTERACTION_ACCESSIBILITY_PERFORMANCE.md').write_text('''# Interaction, accessibility and performance boundary

Single click uses the existing recognizer delay, gives one local acknowledgement, and reveals contextual controls. Chat opens the approved detached shared conversation; close retains draft/turn state. Double click opens Dashboard and suppresses single-click acknowledgement/opening. No Brain request or microphone opening occurs merely by revealing controls. Explicit Voice uses the existing controller. Wake phrase activation is unsupported by the accepted baseline.

Normal controls are 80px circular icon-and-label targets with 14px labels. Labels remain upright through a 180-second orbit. Shared geometry drives rendering and native hit regions. Full-turn circular-clearance tests cover every degree at 440x680 and 360x560. Voice stays below every orbital path and chat below voice. At large text or over four contextual actions, stationary text controls replace the orbit.

The existing Companion clock drives the UI. Orbit geometry updates at most 10Hz; no independent continuous ticker/renderer is introduced. Reduced motion, hidden windows, pointer approach, pressing/focus, open chat and active voice stop travel. Windows polls only the pointer’s position relative to its own window; no global hooks, screenshot or listening permission is added. Pointer departure holds travel for 1.5 seconds. Unsupported pointer reads fail static.

Keyboard controls, visible labels, tooltips, focus and 200% text are tested. The detached transcript scrolls in its remaining space. No floating control approves a task. Pending decisions remain in explicit Review, drafts in the existing document desk, and runtime state is never inferred from text or decorative animation.

Voice bars use the actual RMS level and shared paced waveform driver; silent listening stays quiet. The bar display is not an audio-frequency spectrum. Capture audio levels are fixtures, not microphone recordings. Hidden gallery previews stop and dispose resources; only one model renders at a time.

Native RGBA rendering/96-DPI region inspection are available; desktop compositor behavior, cross-app clicks, hardware DPI/monitors, GPU/VRAM/frame/memory profiling and live backend/voice/auth journeys are NOT VERIFIED. No performance percentage or VRAM claim is made. Future qualification must compare measured behavior against the exact accepted baseline.
''',encoding='utf-8')
(d/'FUTURE_QUALIFICATION.md').write_text('''# Further independent qualification — no integration authorization

1. Fresh reviewer at the exact candidate snapshot: renderer preservation, auth/runtime boundaries, local A2UI isolation, theme migration and UI/service call paths.
2. On an available test desktop, exercise transparency and clicking into unrelated applications, moving circular targets, drag/restore, alternate DPI, negative monitor origins and unplugged-display recovery.
3. Use isolated test accounts/services/devices to qualify real login/bootstrap, stream/error/cancel, approvals denied/stale, interrupted workers and audio input/output. Owner credentials/conversations are not test fixtures.
4. Compare exact-size captures with the approved source, review readable sizing and actual Solar texture differences, and record owner dispositions. The prior dashboard SSIM checkpoint does not certify Companion fidelity.
5. Measure frame timing, GPU/VRAM, memory and inference coexistence against the accepted base; check reduced effects and hidden suspension.
6. Independently review repairs at their new SHAs. Only a later separately authorized integration process may create an integration receipt. This task forbids merge, canonical push and deployment.

Figma edit capability remains unverified; no new editable file or prototype/node link is claimed. Office and experimental Console work remain outside this candidate.
''',encoding='utf-8')
print({'inventory_rows':len(rows),'baseline':base})
