# Buttons, proportions and page placement

Scope: isolated Flutter UI V2 candidate; no merge, push or runtime/security changes. Approved visual references are the dashboard and detached Companion images in `evidence/reference`. Other page adjustments follow their implemented functionality and the same neutral design language; they are not newly owner-approved mockups.

## Shared proportions

Standard text buttons: minimum 48 logical pixels high, content-driven width with 16-pixel horizontal padding (12 for text-only actions), 14-pixel medium-weight text, 20-pixel icon theme. No fixed maximum height: large text can grow. Forms use a full-width primary action; inspection and operational actions use intrinsic widths. Action groups have 8-pixel spacing and wrap instead of shrinking text. Icon targets remain at least 48 pixels; the approved Companion circles and 44-pixel detached send control retain their dedicated geometry.

## Page review

| Page / inventory IDs | Placement decision | Scope of this pass |
|---|---|---|
| Dashboard UI-006/007 | Keep six linked cards around the existing Companion; review count above, work composer below, engraving bottom right | Preserve accepted composition; inherit shared button proportions |
| Companion UI-008–016 | Keep Chat left, Dashboard right, Voice below, waveform under orbit and detached chat below | Preserve approved placement; fit A2UI label and icon within each circle; minimum native chat header target |
| Login / signup UI-002 | Center a bounded form; fields and full-width primary share alignment; secondary account action below | Explicit minimum primary height; inherit shared styles |
| Bootstrap UI-001 | Center connection setup with readable width; Save/Test/status wrap below address | Widen bounded container to match form family; preserve connection behavior |
| Onboarding UI-003–005 | Scroll step content; keep Skip separate from Back/Next, wrapping at narrow widths | Fix Living onboarding footer crowding; classic flows inherit shared styles |
| Gallery / viewer UI-017–019 | Catalogue left on desktop, viewer center; controls bounded under viewer; persistent Cancel/Apply footer | Place actions outside title, bound control width, allow long animation labels |
| Workspace UI-020–022 | Composer below conversation; context on right only when enough room | Flexible header; narrow context opens a dismissible panel instead of squeezing conversation |
| Tasks / approvals UI-023/024 | Decision buttons below their own summary with clear spacing | Living approval rows wrap; frozen supervised screen only inherits shared theme |
| Draft / documents UI-025 | Version controls above document; Undo/Redo/Copy/Close below | Existing wrapping toolbar inherits shared style; no document command changes |
| Connections / providers UI-026/027 | Controls belong to their provider card/dialog | Inherit shared style; existing wrap groups retained; exhaustive dialog visual coverage pending |
| Memory / intelligence / settings UI-028–032 | Controls stay with their setting; no detached global Save | Inherit shared style; protected settings files unchanged |
| Scheduler UI-033 | Occurrence/job text above its actions; wrap actions below | Remove crowded fixed inline action rows |
| Assist UI-034 | Persistent scope controls; Research next to field on wide layouts, below on narrow layouts | Responsive Research group; no observation/permission changes |
| A2UI UI-035 | Host styles govern standard controls; dedicated Companion circles unchanged in identity | Shared styles and bounded circle content; no schema/catalog/authority changes |
| Office / experimental console | Separate candidate evidence | Deferred: no approved page reference or integration evidence added |

## Acceptance and evidence

- Verify control rectangles, large-text wrapping and action placement at 360/390, 1024 and 1440+ widths.
- Keep callbacks, keyboard focus, action labels, state owners and authentication/approval behavior intact.
- Shared styles must cover Elevated/Filled/Outlined/Text/Icon buttons; Companion overrides remain intentional.
- Run targeted/full Flutter checks and capture every affected route when SDK access is restored. Historical captures from `15a322d1` cannot verify this source.
- Current session still fails Flutter launch with `resolved_executable_name`; no new runtime/visual pass or 80% accuracy claim is permitted.

The full V2 acceptance requirements in [00_PLAN_AND_ACCEPTANCE_CRITERIA.md](00_PLAN_AND_ACCEPTANCE_CRITERIA.md) continue to apply. This pass does not relax any requirement or lifecycle gate.
