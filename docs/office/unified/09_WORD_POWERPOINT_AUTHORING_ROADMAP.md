# Word and PowerPoint authoring: scope, architecture recommendation and phases (draft 1, pre-freeze)

Date: 2026-10-15. Status: **recommendation for owner review. Not frozen. No authoring code is written.**
Inputs: the capability audit (`08_OFFICE_CAPABILITY_AUDIT_AND_O2_READINESS.md`), the discovery roadmap
(`00_DISCOVERY_RESEARCH_AND_ROADMAP.md` §2–§9, phases O3 and O5), amendment A1, and the O2 code at `6ec29f39`.

## 0. Acceptance criteria for this document

1. Scope comes from the audit, not from file-type support: every "missing" item below is traced to code that does not
   exist (§1).
2. At least three architectures are compared on the same criteria, with sources, and one is recommended (§2).
3. The recommendation reuses O2 parts by name: render layer, workflow record, approvals, A2UI cards, intent routing.
4. Phases have dependencies, exit criteria and a UI-first qualification row each (§4).
5. Decisions that are the owner's are listed separately (§6). Nothing here starts implementation.

## 1. What is missing (from the audit)

The O2 code opens, previews, searches and converts Word and PowerPoint files. It does not create or change them:

| Need | Code today | Gap |
|---|---|---|
| New Word document | `capabilities.py` `write_document` = `planned:O3`; no DOCX writer in `uri_office` | everything |
| Edit an existing Word document | `edit_document` = `planned:O3`; `document_controller.dart` has no edit method | everything |
| New presentation | `make_presentation` = `planned:O5`; no PPTX writer in `uri_office` | everything |
| Change a presentation (slides, text, images, tables, charts, layouts) | `edit_presentation` = `planned:O5` (added `b610d6f2`) | everything |
| Save DOCX / PPTX | `safe_write.py`, `approvals.py` exist (used for xlsx and PDF) | DOCX/PPTX writers and their validators |

Outside Office, Core M19 `generate_document` (canonical `uri_core/tools/generate_document.py`) writes a one-shot DOCX,
PPTX, XLSX or PDF from a chat request: Brain markdown rendered by python-docx / python-pptx (default template, one
title + bullets per slide). It cannot open or change an existing file, has no preview or change cards, and its PDF
path uses PyMuPDF, which Office dropped (A1, OD-U14). It is not an Office authoring path; §3 says what can be reused.

## 2. Architectures compared

Criteria: fidelity of the saved file; on-screen editing; Brain change cards with hash-bound approval; new
dependencies and licences; fit with O2 (render layer, workflow, approvals); security posture; effort.

| | A. URI structured authoring (recommended core) | B. Embedded web editor in WebView2 | C. Server office suite (ONLYOFFICE / Collabora) | D. Hand-off to the LibreOffice GUI |
|---|---|---|---|---|
| How | python-docx / python-pptx + lxml patches behind a change-set model; preview = the O2 LibreOffice render; Flutter panes for outline, slide list and per-block text | Univer Docs / Univer Slides in the existing WebView2 host | Document server + iframe editor | "Edit in LibreOffice" opens a working copy in Writer/Impress with the hardened profile; URI validates and diffs when it is saved |
| Fidelity | python-docx / python-pptx keep unknown XML; edits are part-local (as xlsx patch) | Univer import/export of .docx/.pptx needs the Pro conversion backend ([Univer slides import/export](https://docs.univer.ai/guides/slides/features/import-export); docs: §2.2 of `00_`) | High (LibreOffice / ONLYOFFICE engines) | High (LibreOffice is already the render engine) |
| On-canvas editing | No (structured panes + live re-render, warm listener 0.36 s per DOCX in the 2026-10-15 probe) | Yes | Yes | Yes, outside URI's window |
| Brain change cards + approval | Native: every op has an address, before, after, hash (M1 rule) | Would need a second op model inside the editor | Would need a server plug-in | No: free editing; URI can only diff afterwards |
| New dependencies | None (all already in `requirements.txt`) | Paid licence or a custom converter with fidelity loss | A server (multi-GB), licence review not done (NOT VERIFIED) | None (LibreOffice 26.8.1 is installed and signer-checked) |
| Security | Same as O2: sanitize, no network, approvals | Same WebView2 lockdown as the sheet page | New network service | GUI with macros and external links disabled by the hardened profile; must be re-qualified for GUI use (the O2 qualification covers headless only) |
| Effort | Medium per format; reuses O2 | High, paid path | High, new service | Low |

**Recommendation: A as the product, D as an optional escape hatch.** A is the only option where URI-made changes go
through the same reviewable, hash-bound change cards as Excel, with no new dependency. D gives the owner full manual
editing (fonts, drawing, animations) without URI building a WYSIWYG editor; it is an owner decision because it opens
a GUI office suite on owner files (§6, OD-A2). B and C are rejected for now (licence or server; no change-card fit).

## 3. Recommended design (A)

Shared (built once, "O3/O5 common", before either format):
- **Document model** (`00_` §2.4 pattern 1): blocks with stable addresses. Word: `body/p[12]`, `body/tbl[2]/r[3]/c[1]`,
  `hdr[default]`, `ftr[default]`, `sectPr[0]`. PowerPoint: `slide[id=257]/shape[id=4]` (slide IDs from `p:sldIdLst`, shape
  IDs from `p:cNvPr`, stable across reorder).
- **Change set** (generalized M1 draft): ops with address, before, after, `change_sha256`; accept/reject per card and
  all-or-nothing with a set hash (M2-D2). The Excel `status` rule (M2-XB-1) applies from day one: a Brain answer is
  `propose | clarify | cannot`, and only `propose` may draft changes.
- **Writers** apply accepted ops to a working copy, then validate: reopen with python-docx / python-pptx, render with
  the O2 LibreOffice listener, visual checks (overflow, empty placeholders, tiny text), then the existing output card
  and `safe_write` (no clobber, Save As by default, original untouched unless the owner chose Edit role + approval).
- **Preview**: the O2 page preview shows the working copy; changed pages/slides are marked.

Word (O3) closed op set: `insert_paragraph`, `replace_text` (run-preserving), `delete_block`, `set_style` (named styles
only), `insert_table` / `set_cell_text`, `set_header_text` / `set_footer_text`, `insert_page_number`, `insert_image`
(owner-picked file), `insert_page_break`. New documents start from templates (letter, office order, notice, memo,
minutes, report) built by code with the institutional rules already in Core (reused as data, not by importing
Core).

PowerPoint (O5) closed op set: `add_slide(layout)`, `delete_slide`, `duplicate_slide`, `move_slide`, `set_text(shape)`,
`set_notes`, `insert_image(placeholder)`, `insert_table`, `insert_chart(native, from cells)`, `apply_layout`,
`apply_template(master from a .pptx/.potx the owner picked)`. python-pptx has no public delete/duplicate/move API: these
are `p:sldIdLst` edits plus relationship and part clean-up, the same lxml discipline as `xlsx_patch.py` (to be
unit-tested on round-trip and opened by LibreOffice).

Brain use (both): outline → slides, rewrite / shorten / proofread a block, draft a letter from a short instruction,
"make this ready for the meeting" → a proposed op list. Brain sees block text only for the blocks in scope (§9.5 of
the O2 plan generalised); wording and outlines only; numbers, dates and names are copied from sources by code.

UI (same three-pane workspace, B1/B2 design): left = outline (Word) or slide list with drag-to-reorder and
add/duplicate/delete buttons (PowerPoint); centre = live preview of the working copy; right = URI pane with change
cards. Direct manual edits use the same ops (a text field per block or shape), so manual and URI changes share undo,
approval and history.

Reuse from Core M19: the prompt pattern for slide outlines (`# Title` + bullets) and the institutional drafting brief,
copied as data into Office prompts. Not reused: its PyMuPDF PDF writer and its default-template-only renderer.

## 4. Phases and dependencies

| Phase | Content | Depends on | Exit criteria (each also needs Stage 8 UI-first qualification) |
|---|---|---|---|
| **O3/O5-C** common | document model, change-set + status rule, writer/validator skeleton, preview of a working copy | O2 integrated (or stacked on the O2 readiness candidate) | round-trip of every fixture byte-stable outside touched parts; LibreOffice opens every output |
| **O5a** slides structure | add / delete / duplicate / move slides, set text, notes, layouts; slide list UI | C | 30-op corpus applied and reopened; reorder by drag in the real app; undo |
| **O5b** slides content + Brain | images, tables, native charts from cells, templates; Brain outline → deck and "shorten/expand" | O5a | no overflow in rendered slides; Brain live corpus with `clarify` honoured |
| **O3a** Word structure | new from templates; paragraphs, styles, tables, header/footer, page numbers, images | C | templates render without clipping; edits keep untouched parts byte-identical |
| **O3b** Word + Brain | rewrite, shorten, proofread, draft from instruction, compare / tracked-change draft | O3a | live corpus; change cards consistent with message; original never written without Edit role |
| **D** LibreOffice GUI hand-off (optional) | open working copy in Writer/Impress, watch save, validate + diff, back into URI | owner OD-A2; GUI profile qualification | macros/links canary in GUI mode; diff card shown before anything replaces the original |
| O4 PDF intelligence | ask / summarize with page citations (pypdf text, Tesseract fallback) | O2; packaging fix B4 | already planned in `00_` §8 |

Recommended order: C → O5a → O3a → O5b → O3b, because PowerPoint has no authoring path at all while Word has M19's
one-shot draft, and slide structure ops are the least Brain-dependent (can be qualified while GPU coexistence is open).
O4 can run in parallel with C (separate files, A1 engines).

## 5. Risks

- python-pptx slide duplication must carry charts (embedded workbook parts), images and notes: highest-risk op; spike
  first with the 11-slide fixture deck (chart slide).
- LibreOffice render is the only layout engine: overflow detection depends on it; a missing font changes layout
  (R6-2 history). Fonts present on the PC must be recorded per run.
- GPU: Brain-assisted authoring has the same coexistence limit as today (39 tok/s once the app is open; §D of `08_`).
  Structural O5a/O3a work does not need the Brain and should not wait for it.

## 6. Owner decisions

- **OD-A1** Architecture: A (structured authoring with change cards) as the product. Recommended.
- **OD-A2** Optional LibreOffice GUI hand-off (D) for free manual editing: allow, defer, or refuse.
- **OD-A3** Order: PowerPoint structure first (recommended) or Word first.
- **OD-A4** Base: stack O3/O5 on the O2 readiness candidate (recommended) or wait for O2 integration.
- **OD-A5** Templates: which institutional templates (letter, office order, notice, memo, minutes, report) and whose
  master slides; synthetic fixtures first (OD-U7 pattern).

## 7. Self-review against §0

1. Every gap row cites the planned capability id or the missing method (met). 2. Four architectures on one set of
criteria; B/C sources are vendor documentation, and C licence terms are NOT VERIFIED (stated; does not change the
recommendation because C is rejected on server weight and change-card fit). 3. Reuse named (met). 4. Phases with
dependencies and exit criteria; each requires UI-first qualification (met). 5. Owner decisions separate; nothing
starts (met). Unsupported claim removed in self-review: an earlier sentence that Univer Docs "cannot" import DOCX was
narrowed to "needs the Pro conversion backend", which is what the source says.
