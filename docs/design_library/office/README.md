# Office workspace patterns

Scope: the URI Office region (Excel, Word, PowerPoint, PDF), its file and workflow navigation, its page previews and
its companion pane. Created 2026-10-15. Before this, the library had no Office or document pattern.

## References (structural only, verified with `gh api` 2026-10-15)

| Repository | Path | Pattern | Licence |
|---|---|---|---|
| toeverything/AFFiNE | `packages/frontend/core/src/blocksuite/ai/chat-panel/` | Document with a persistent AI side panel | MIT core, proprietary portions |
| paperless-ngx/paperless-ngx | `src-ui/src/app/components/document-detail/` | Document preview with a metadata and actions side panel | GPL-3.0 |
| Stirling-Tools/Stirling-PDF | `frontend/editor/src/core/components/layout/Workbench.tsx`, `shared/quickAccessBar/` | Goal-grouped tool list beside a workbench | MIT core |

None of these is a URI dependency. No code is copied.

## URI backend evidence

- Office service: `uri_office/service.py` (routes `open_local`, `open_new`, `instruct`, `decide`, `propose_save` and
  others), at commit `5b958da0`.
- Companion routing: `LivingServices.activeOfficeTarget` (`uri_ui/lib/living/living_scope.dart:159`).
- UI-state controller: `UiPresentationController` with `WorkspaceFocus.office`
  (`uri_ui/lib/living/presentation/presentation_controller.dart`). The local phrase parser has no `office` phrase yet.
- `DocumentsRegion` (`workspace_mode_view.dart:740`) is simulated (`work_items.dart`: `isSimulated => true`).

## Decisions

- 2026-10-15: B1 three-pane layout with B2 goal grouping, approved by the owner. See
  `../approved/office_workspace_2026-10-15.md`.
- 2026-10-15: B2 drawer layout, concept A (tab per app) and concept C (conversation only) were rejected. See
  `../rejected/office_workspace_b2_layout_2026-10-15.md`.
