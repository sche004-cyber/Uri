# Living Companion structure (Companion / Workspace / Dashboard forms of one orb)

**Status: IMPLEMENTED CANDIDATE, owner acceptance PENDING.** This record sits in `approved/` because the structure is implemented and tested on branch `phase/ui-living-companion` (not because the User has accepted it). The User's acceptance, or a `rejected/` record, must follow before any integration.

**Date:** 2026-10-08
**Recorded by:** Claude (UI phase session)
**Brief:** "URI — UI & Living Companion Development" (User instruction, 2026-10-08)

## What was decided (by Claude, under the brief's GREEN authority)

* One living form, the Energy Orb, rendered procedurally in Flutter (CustomPainter particles + optional runtime fragment shader core), with nine states derived only from observable facts. No Blender asset: not installed, no MCP, and an exported animation cannot react to live state.
* Three forms over one `AppState`: Companion (orb + composer), Workspace (rail with the five Hybrid destinations' content model: Conversation, Tasks, Documents, Intelligence, Settings), Dashboard (eight sourced tiles). Transitions keep the same orb element and cross-fade content.
* "Obsidian Cyan" added as a fifth `UriThemeChoice`; the four approved Hybrid themes are unchanged.
* A restricted UI-state controller (`ShowModeCommand` only) with a local "URI <mode>" parser; the user can always switch or go Back.
* Every mock-backed region carries a Simulated badge; the memory graph is labelled PROTOTYPE.
* Seven orb styles and ten palettes on one state engine, built from the owner's three reference images (`docs/ui_phase/references/`); the owner picks a style and a palette (`docs/ui_phase/UI_ORB_OPTIONS.md`). Cursor gust and click poke + question bubble on every style (owner requests, mid-session).

## Reference and evidence

* Design reference and token rationale: `docs/ui_phase/UI_DESIGN_REFERENCE.md`.
* Backend capability inspected first: `docs/architecture/PHASE2CLOSE_UI_READINESS.md` (state contract, interfaces), `uri_ui/lib/services/app_state.dart`, `uri_client.dart`, `supervised_runtime.dart`.
* Structural pattern origins: Hybrid approval (`approved/hybrid_ui_2026-09-16.md`) for the destination set and the Chat/Tasks shapes; dashboard tile density ceiling from `dashboard/README.md`.
* Screenshots from the real Windows build: `docs/ui_phase/screenshots/`.
* Tests: `uri_ui/test/living/` (70), full suite 275 passing; Codex read-only review rounds 1-3 (`docs/ui_phase/UI_TEST_EVIDENCE.md` section 6).

## What was explicitly NOT done

* Not wired to Core, the supervised worker or voice. Listening/Speaking are preview-only.
* Not mounted inside the Hybrid `UriApp`; separate entry `lib/main_living.dart`.
* Not merged, pushed or deployed.

## Standing constraints honoured

Chat remains a first-class workspace region (not a dock on Home/Dashboard). No unbacked metric tile (no deadlines, no halted workflows). Presentation never authorizes; approvals go through structured buttons only.
