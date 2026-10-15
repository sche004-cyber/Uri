# URI Office workspace: B2 layout (task panel, workbench, companion drawer), plus concepts A and C

**Date:** 2026-10-15. **Decided by:** the owner (OD-U5, chat 2026-10-15). **Recorded by:** Claude.

## What was proposed

- **B2:** a goal-grouped task panel on the left, a workbench in the centre, and the URI companion as a drawer that
  opens over the workbench. Mockup screen 5 in `docs/office/unified/design/office_workspace_mockups.html`.
  Structural reference: Stirling-PDF `frontend/editor/src/core/components/layout/Workbench.tsx` and
  `shared/quickAccessBar/` (MIT core).
- **Concept A:** one tab or panel per application (Word, PDF, PowerPoint, Excel).
- **Concept C:** conversation only, with files shown as cards.

## Why rejected

- **B2 layout:** the drawer moves the accepted Excel companion out of its fixed right pane (M1 AC19). It also hides
  the companion while the owner inspects a page. The owner chose B1.
- **Concept A:** it rebuilds the "one script per format" experience the brief rejects. The user must pick an
  application before stating an outcome.
- **Concept C:** there is no place to inspect a rendered page or correct an output, so fidelity problems stay hidden.

## What was kept

B2's **goal-based task grouping** is part of the approved B1 left pane
(`approved/office_workspace_2026-10-15.md`). Groups: Write, Present, Work with PDFs, Data and Excel, Combine files.

## Revisit when

- B2 drawer: only if a future screen must give the workbench the full window width, for example a two-page
  side-by-side comparison on a small display. Even then, it is a collapse state of B1's right pane, not a new layout.
- A and C: no foreseen condition.
