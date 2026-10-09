# URI A2UI — research, decision and contract

Branch `phase/a2ui` (worktree `C:\Users\cheta\Development\uri-a2ui`), based on `phase/scheduler` at `f59aad5`.
Status ladder: Researched → Proposed → Prototyped → Implemented → Tested → Independently accepted → Integrated.

## 1. What existed before this phase (primary evidence)

| item | evidence | status |
|---|---|---|
| A2UI / AG-UI in URI | `docs/plans/PHASE2OPS_REPORT.md` ("AG-UI / A2UI: RESEARCHED, no transport adopted"); `_V1/docs/research/URI_HARNESS_STRATEGY/01,02,10` mention AG-UI only (event protocol, "deferred until needed"); `docs/scheduler/SCHEDULER_ARCHITECTURE.md` §8 (A2UI could render the review card) | Researched (AG-UI only); A2UI never researched in substance; nothing prototyped |
| Declarative UI in Flutter | none; no `genui`/`a2ui` dependency in `uri_ui/pubspec.yaml` | absent |
| Restricted UI command vocabulary | `uri_ui/lib/living/presentation/presentation_controller.dart` (`UiCommand`: mode + workspace focus; "can never send text, approve, ... dismiss an approval card") | Implemented, accepted with the UI phase |
| Digest-bound decisions | worker `oi_decide` echoes `approval_digest`; scheduler `confirm(proposal_sha256)`, `review(sha256)` | Implemented, accepted |

## 2. Research (2026-10-09)

| option | facts checked | fit |
|---|---|---|
| A2UI v0.9.1 (production spec) | Messages `createSurface{surfaceId, catalogId, theme?, sendDataModel?}`, `updateComponents{surfaceId, components}`, `updateDataModel{surfaceId, path?, value?}`, `deleteSurface{surfaceId}`; client `action{name, surfaceId, sourceComponentId, timestamp, context}` and `error`; flat component list with `id`/`component`, one `root`; JSON-Pointer bindings; catalogs restrict the agent to app components; functions referenced by name, no executable code | **adopt the wire format** (subset) |
| A2UI v1.0 | still a release candidate (spec page updated 2026-06-08); "breaking changes to the catalog API between v0.9 and v1.0"; v0.9.1 recommended for production | not yet; keep the subset compatible with both where cheap |
| Flutter `genui` 0.10.4 (+ `genui_a2a`) | pre-1.0; listed platforms Android/iOS/macOS/web (Windows not listed); `flutter pub add genui --dry-run` on a copy of `uri_ui/pubspec.yaml` resolves but **changes 46 dependencies**, adding native plugins (`audioplayers`, `video_player_win`, `jni`), markdown and URL-launching widgets; its model is an LLM conversation loop (`Conversation`, `SurfaceController`) | **rejected for now**: dependency and native-plugin surface on an accepted app, no Windows statement, widgets would not use the Living theme, and URI's authority model needs a restricted catalog anyway |
| AG-UI | event transport between agent back-end and UI | not needed: the integrated worker already streams `uri.oi.event.v1` frames |

Decision: **A2UI v0.9.1 message format, a URI catalog (`uri:a2ui/catalog/v1`), validation in both producer (Python
`uri_a2ui`) and renderer (Dart), a URI renderer built on the Living theme, no new dependency.** The wire format stays
standard, so `genui` can be re-evaluated later without changing producers.

## 3. Roles (unchanged URI architecture)

| role | who | what it may do |
|---|---|---|
| Interpret the request | Brain side: the integrated worker's turn path (deterministic scheduling-request interpreter for this slice, labelled as such) | produce an interpreted request and its open questions; **no** authority |
| Authority | the domain owner of the capability: scheduler engine (owner check, proposal SHA-256, artifact SHA-256), worker/Core for their own commands | validate and execute; refuse anything else |
| A2UI producer | the authority builds surfaces from its own validated data through `uri_a2ui` builders and the validator | presentation only |
| A2UI renderer | Flutter `living/a2ui/` | render only catalog components; collect input; send `action` messages through the action registry |
| Action registry | Flutter `A2uiActionRegistry` | maps an action name to ONE existing authorized client call; unknown names are refused |
| Placement | Companion / Workspace / inline, chosen by the UI within `UiCommand`'s mode vocabulary | a surface can ask for a placement; it cannot change mode, approve or send |

Generated UI can never grant a permission, call a tool, bypass a confirmation or change protected state: a surface
only names actions; the renderer only knows registered actions; the authority re-validates every action.

## 4. Contract (`uri_a2ui`, Dart mirror in `uri_ui/lib/living/a2ui/`)

- Envelope: `{"version": "v0.9", <exactly one of createSurface | updateComponents | updateDataModel | deleteSurface>}`.
- `catalogId` must be `uri:a2ui/catalog/v1`. `theme` may carry only `agentDisplayName` and `placement`
  (`companion` | `workspace` | `inline`); colours, icons and URLs are refused (the Living theme is inherited).
- Components (property whitelist and types in `uri_a2ui/catalog.py`): `Column`, `Row`, `Card`, `Text`
  (`variant`: body/title/caption/label), `Divider`, `Badge` (`tone`), `Button` (`label`, `action`, `variant`,
  `enabled`), `CheckBox`, `ChoicePicker`, `DateTimeInput` (time only or date only), `TextField` (bounded),
  `ArtifactImage` (`artifactId` + `sha256`; never a URL), `List` (template over a data path).
- Limits: 120 components, depth 8, 4,000 characters per string, ids `^[A-Za-z][A-Za-z0-9_-]{0,63}$`, exactly one
  `root`, every reference resolves, no cycles, JSON Pointer paths only.
- Actions: a `Button.action` is `{"event": {"name": <registered>, "context": {<key>: <literal or {"path": ...}>}}}`.
  Registered names and their context schema are in `uri_a2ui/actions.py`. Every surface lists the action names it
  allows (`surface.actions`), and every action message must echo the `surface_digest` of the surface version shown.
- Digest: `surface_digest = sha256(canonical(createSurface + components + read-only data))`. Read-only data (e.g.
  `proposal_sha256`, `artifact.sha256`) lives under `/bound/...` and cannot be written by inputs.

## 5. Acceptance criteria (defined before implementation)

| id | criterion | evidence required |
|---|---|---|
| A-AC1 | Contract: v0.9.1 subset, URI catalog, limits and action registry documented and enforced identically in Python and Dart | shared fixtures validated by both suites |
| A-AC2 | Untrusted definitions: every malformed, oversized, unknown-component, unknown-action, URL, colour, cyclic or dangling definition is refused with a code, and nothing is rendered from it | adversarial tests both sides |
| A-AC3 | Actions: an action is executed only if surface exists, digest matches the version shown, the component is a `Button` carrying that action, the action is allowed for the surface, and the context matches its schema; the authority re-validates (proposal hash, artifact hash, owner) | tests incl. stale digest, forged component, forged hash |
| A-AC4 | Scheduler slice: natural-language festival request → interpreted proposal surface → user edits selection/time → revised proposal (new hash) → explicit confirm → job ACTIVE; nothing runs before confirm | process-level test against the real scheduler service |
| A-AC5 | Persistence: the proposal/job and surfaces survive a scheduler restart; a re-rendered surface after restart still enforces the digest | restart test |
| A-AC6 | Simple requests stay conversational: no surface for ordinary questions | worker/router tests |
| A-AC7 | Additional workflows (at least one, at most two) justified by daily use: artifact review with preview (approve/refine/regenerate/reject bound to SHA-256) and festival calendar review/correction | tests + demo |
| A-AC8 | Visual integration: renderer uses Living theme tokens only; Companion card beside the orb, Workspace panel; no existing view replaced | widget tests + screenshots |
| A-AC9 | Measurements: surface build+validate latency, render latency, action round trip; failure recovery (scheduler down, stale surface, invalid surface) shown to the owner | measurement file |
| A-AC10 | No frozen or accepted module changed except recorded hook lines; scope guards extended by exact paths only | guard diff |
| A-AC11 | Independent Codex audit ACCEPT or ACCEPT WITH FINDINGS, findings repaired or recorded | audit record |
