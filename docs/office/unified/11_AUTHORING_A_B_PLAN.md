# Office authoring, milestones A (shared groundwork) and B (PowerPoint): plan and acceptance criteria

Date 2026-10-16. Owner decisions: OD-A1 (structured editing with python-docx / python-pptx, existing LibreOffice
render, existing services and approvals), OD-A2 (optional LibreOffice hand-off, later), OD-A3 (order A → B → C → D →
E), OD-A4 (controlled-integrated Office baseline; isolated branches), OD-A5 (blank, existing, user templates; reusable
layouts). Branch `milestone/office-authoring-ab-20261016` from the integration branch tip `3e329140`; it is rebased
or merged onto canonical once the O2 integration lands. Research: `09_WORD_POWERPOINT_AUTHORING_ROADMAP.md`.

## 1. What exists and what is reused

| Need | Reused as is | New |
|---|---|---|
| Open a .pptx/.docx the owner picked | `grants.grant_open(kind=)`, `docs.Documents.open` (original never written) | — |
| Preview | `sanitize` → LibreOffice render → WinRT raster (`docs._prepare`) | preview of the **working copy** |
| Change review and approval | A2UI approval cards (`approvals.Approvals`), hash-bound (`change_sha256`), STALE checks | subject kind `authoring` |
| Save | `xlsx_patch.atomic_write` (exclusive temp, atomic replace), save-as grants, backups folder | DOCX/PPTX writers |
| Brain | `brain.OfficeBrain` client, status rule propose/clarify/cannot (M2-XB-1) | milestone D |
| UI | Office workspace, document view, page preview, companion pane, conversation | edit panes |

## 2. Design (A: shared groundwork)

- **Authoring session** (`uri_office/authoring/session.py`): created from an open document or from a template. Holds
  a **working copy** in the state folder: an exact byte copy of the original (not the sanitized render copy, so
  nothing the sanitizer strips is lost on save), plus an ordered **change list**. Each change is one op with a stable
  address, plain-words text, state (applied | undone), and the hash of the op. Undo/redo by replaying the change list
  on the original copy (deterministic; no in-place XML history).
- **Apply model**: an op is applied to the working copy immediately (owner's own edits) and the preview re-renders
  (warm LibreOffice listener ~0.4 s). Nothing touches the original or any destination until the owner approves a
  save card that lists every change in plain words (hash binds the list + destination).
- **Save**: `Save` (replace the opened file, backup first, refused if the file changed on disk since it was opened)
  or `Save as` (new file through the save dialog, never replaces). New documents: always Save as.
- **Validation after write**: reopen with python-pptx/python-docx; LibreOffice converts it (so a file LibreOffice
  cannot open is refused before replacing anything).
- **Unsupported content is preserved, not touched**: ops never rewrite parts they do not own (charts, SmartArt,
  media, comments, custom XML stay byte-identical except where an op is about them). An op that would need to change
  such content is refused with a reason (`AUTHORING_NOT_SUPPORTED`).
- **Templates** (OD-A5): blank presentation (python-pptx default master), the owner's own .pptx/.potx as a
  template (new file from it, its layouts and theme kept), and "a slide like this one" (duplicate). Template
  discovery / Skill Command Center are later and not prerequisites.

## 3. PowerPoint (B): closed op set

| Op | Address | Behaviour |
|---|---|---|
| `add_slide` | `after` (slide id or null = end), `layout` (name from the deck's masters) | new slide from that layout |
| `delete_slide` | slide id | relationship dropped; unreachable parts not saved |
| `duplicate_slide` | slide id | shapes, pictures (shared image parts), tables, notes copied; **charts: chart part and its embedded workbook copied**; refused for media/OLE/SmartArt slides (named reason) |
| `move_slide` | slide id, `to` index | `sldIdLst` order |
| `set_layout` | slide id, layout name | only when the slide's placeholders map by type; otherwise refused |
| `set_text` | slide id, shape id, paragraphs | replaces the text of a text shape or placeholder; keeps the first run's formatting per paragraph |
| `set_title` | slide id, text | title placeholder |
| `set_notes` | slide id, text | notes slide |
| `insert_text_box` | slide id, position (EMU box), text | |
| `insert_image` | slide id, picked image file (grant kind `image`), position | |
| `insert_table` | slide id, rows×cols, cell texts, position | native table |
| `set_table_cell` | slide id, shape id, row, col, text | |
| `move_shape` / `resize_shape` | slide id, shape id, EMU box | |
| `delete_shape` | slide id, shape id | not on placeholders' layout inheritance (the placeholder is emptied instead) |
| `format_text` | slide id, shape id, paragraph index or all, bold/italic/underline/size/colour/alignment | |
| charts | — | existing charts kept and shown; **creating or editing charts is PLANNED (milestone D/E)** |

Stable addresses: slide id from `p:sldIdLst` (`id` attribute, unchanged by moves), shape id from `p:cNvPr/@id`.

## 4. UI (B)

Office document view gains an **Edit** mode for a .pptx (and "New presentation" on Office Home):
- left: slide strip (thumbnails from the preview) with Add (layout menu), Duplicate, Delete, Move up/down (and drag);
- centre: the selected slide's preview;
- right (existing URI pane area): the slide's editable items — title, each text shape as a text field, notes, table
  cells — plus Insert (text box, image, table) and simple formatting buttons;
- top: change counter, Undo/Redo, Save…, Save as…; leaving edit mode with unsaved changes asks (keep, discard).
States shown in words: Viewing / Editing (n unsaved changes) / Saving / Saved as … / Cancelled / Failed (reason).

Implementation note (2026-10-16): the slide's editable items are a column inside the editor, not the URI pane, so the
URI pane keeps showing the conversation and the save card beside the editor (the card must stay visible while the
owner reviews what they changed). After an approved save, Done opens the saved file again in the viewer so it shows
what is on disk. Save as continues the edit on the new file. A refused change is shown in words above the slides with
the reason the service names (for example video that cannot be copied).

## 5. Acceptance criteria

| ID | Criterion | Evidence |
|---|---|---|
| AB-1 | A working copy is byte-identical to the original at start; the original is never written except by an approved Save | unit + service tests (hash before/after) |
| AB-2 | Every op in section 3 except charts works on synthetic fixtures (11-slide deck with chart, blank, user template) and the result reopens in python-pptx and converts in LibreOffice | unit + real-engine tests |
| AB-3 | Untouched parts stay byte-identical (charts, media, unrelated slides) after any op set | part-hash tests |
| AB-4 | Undo/redo restore exactly the earlier working copy (hash) | tests |
| AB-5 | Save card lists every change in plain words and binds them with the destination (hash); a later edit makes it stale | service tests |
| AB-6 | Save replaces only after a backup; refused when the original changed on disk; Save as never replaces | tests |
| AB-7 | Unsupported content (media, OLE, SmartArt slides for duplicate; chart editing) is refused with a named reason, never half-done | tests |
| AB-8 | Real app: create a presentation from blank and from a template; add, duplicate, delete, move slides; edit title, text, notes, a table cell; insert an image and a text box; Save as; close; reopen; export PDF; preview matches | Stage 8 live journeys |
| AB-9 | Real app: undo/redo, leave-with-unsaved, cancel a save card, refused op message, damaged file | Stage 8 |
| AB-10 | First-time user: Edit is discoverable from a .pptx view and from Home ("New presentation") without instructions | Stage 8 UX notes |
| AB-11 | Independent review ACCEPT (or AwF) on the exact commit; gates (office, office_u2, a2ui, Flutter) pass | driver receipt |

Not in A/B: Word (C), Brain-assisted authoring (D: "Create a presentation from these points", "Make slide three
shorter"), charts creation/editing, OD-A2 LibreOffice hand-off, printing (O2P, deferred).

## 6. Self-review

Each criterion has evidence; unsupported features are named, not implied (chart editing, media). The working-copy
choice (original bytes, not the sanitized render copy) is deliberate so a save never drops content the sanitizer
removed for previewing; the sanitized copy is still what LibreOffice renders, so the preview's security is unchanged.
