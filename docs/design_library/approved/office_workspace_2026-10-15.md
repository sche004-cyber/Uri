# URI Office workspace: B1 three-pane layout, with B2 goal grouping

**Status: SELECTED BY THE OWNER, NOT IMPLEMENTED.** The owner approved concept B1 with refinements on 2026-10-15
(decision OD-U5, "APPROVED WITH REFINEMENTS"). Nothing is built yet. Implementation is phase O2 of
`docs/office/unified/`, which needs its own plan approval first.

**Date:** 2026-10-15
**Approved by:** the owner (in chat, 2026-10-15)
**Recorded by:** Claude (URI Office Unified planning session)
**Mockups:** `docs/office/unified/design/office_workspace_mockups.html` (private artifact
https://claude.ai/artifact/MwCYF84TWc6NtMBXG4PA8T)

## What was decided

One Office region under the existing Workspace rail item `WorkspaceFocus.office`, with three panes:

| Pane | Content |
|---|---|
| Left: files and workflows | File navigation, recent documents, templates, **goal-based task grouping (from B2)**, active and completed workflows, search and filter |
| Centre: Office workbench | Excel (existing Univer page), Word, PowerPoint and PDF page previews, automation plans and progress, before/after comparison, output validation and correction |
| Right: URI intelligence | The existing Office companion pane (M1 AC19), generalized: requests, clarification, plan card, change cards, findings, approvals, citations, at most one suggestion |

Owner refinements that bind the implementation:

1. Keep the existing Excel companion integration (`LivingServices.activeOfficeTarget`, `office_panel.dart`).
2. Panels are resizable and collapsible.
3. Responsive layout for small windows.
4. URI V2 visual language (`uri_theme.dart` tokens).
5. Conversation context is kept across Office modes.
6. First-time onboarding and contextual hints.
7. Clear progress, errors and recovery actions.
8. Suggestions are relevant, dismissible and non-intrusive.
9. URI opens and navigates Office modes through the existing UI-state controller
   (`uri_ui/lib/living/presentation/presentation_controller.dart`).
10. No duplication of A2UI or Brain functionality.

## References

Structural only; no code is used.

- AFFiNE (sidebar, document, AI chat panel): `packages/frontend/core/src/blocksuite/ai/chat-panel/`. Licence: MIT core with proprietary portions.
- Paperless-ngx (document detail with a side panel): `src-ui/src/app/components/document-detail/`. Licence: GPL-3.0.
- Stirling-PDF (goal-grouped tool list, source of the B2 grouping): `frontend/editor/src/core/components/layout/Workbench.tsx`, `shared/quickAccessBar/`. Licence: MIT core.

All paths were verified with `gh api` on 2026-10-15. There is no Office category in the library before this record; see
`docs/design_library/office/README.md`.

## Why B1 over the alternatives

- B1 keeps the companion as a fixed right pane. That is where the accepted Excel companion already sits (M1 AC19), so
  Excel users see no change.
- B2's companion drawer would have moved the accepted Excel companion. Only B2's goal grouping was taken (see
  `rejected/office_workspace_b2_layout_2026-10-15.md`).
- Concepts A (one tab per app) and C (conversation only) were rejected in plan section 4.1.

## Backend it maps onto

- Existing: `uri_office/service.py` (127.0.0.1 HTTP, bearer token), `approvals.py` (hash-bound A2UI cards),
  `uri_a2ui/actions.py` (`office.apply_change`, `office.reject_change`), `office_controller.dart`, `office_panel.dart`.
- New in O2, planned and not built: render, preview, workflow and capability routes. See
  `docs/office/unified/01_O2_PLAN_AND_ACCEPTANCE_CRITERIA.md`.
- The left-pane "recent" and "workflows" lists have no backend today. The current `DocumentsRegion` is simulated
  (`work_items.dart` `isSimulated => true`). O2 supplies a real source or the region shows nothing.
