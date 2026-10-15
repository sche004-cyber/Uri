# URI Office Unified: discovery, research and roadmap (draft 1, pre-freeze)

Date: 2026-10-14. Milestone family id `URI-OFFICE-U`. Process: `uri-development-lifecycle` (explore, plan, owner vision
check, independent plan review, freeze, then one isolated branch and worktree per phase).
Planning branch: `phase/uri-office-unified-plan` from `5b958da0`, worktree `C:\Users\cheta\Development\uri-office-unified`.
Status: **DRAFT, NOT FROZEN.** Owner decided OD-U1, OD-U2 and OD-U6, and chose O2 as the first milestone (2026-10-14, section 12a). OD-U5 was decided on 2026-10-15 (B1 with refinements). OD-U3, OD-U4 and OD-U7 are open. No production code has changed.

## 0. Acceptance criteria for this document

The draft is acceptable when every item below holds. Section 13 records the self-review.

| # | Criterion |
|---|---|
| P1 | Each Excel capability has a status tier (planned, implemented, unit-tested, live-tested, independently accepted, frozen). Each tier cites a commit or a report. |
| P2 | Each engine choice cites a measurement, an inspected source, or a cited document. No engine is chosen on reputation alone. |
| P3 | The architecture reuses the existing Office service, approvals, A2UI, Brain client and companion. It adds no second orchestration layer and no second assistant. |
| P4 | No phase edits a frozen or protected path (`uri_core/`, `uri_supervisor/` and the other `PROTECTED` prefixes in `scripts/ws_frozen_check.py`) without a named owner decision. |
| P5 | Each phase has scope, dependencies, acceptance criteria, tests, live checks (categories A to L), security notes, expected UX and integration gates. |
| P6 | Each unverified item is named, with its effect on the verdict. |
| P7 | Mission Control and the Skill Command Center are out of scope. |

## 1. Existing Excel implementation: assessment (Phase 1)

### 1.1 Where the implementation is

| Line | Commit | Location | Meaning |
|---|---|---|---|
| M1 (one workbook, edit, save, Google) | `6348b1b1` (receipt `68ce3825`) | branch `phase/uri-office`, worktree `uri-office` | Accepted code |
| M2 (new workbook from files, roles Reference/Check/Edit) | `f50ae1e3` (ledger `b51a3912`) | branch `phase/uri-office-m2`, worktree `uri-office-m2` | Accepted code |
| Combined Office plus frozen authorized repairs | `aa232e36` | `integration/office-frozen-authorized-20261013` | Accepted Office candidate |
| Assist repair descendant | `e0b5c298` | `repair/assist-visible-ink-20261013` | Assist code ACCEPT; final integration BLOCKED |
| Latest descendant (governance/runtime repairs plus `add_sheet` name contract) | `5b958da0` | `repair/office-sheet-name-contract-20261014` | Contract code ACCEPT; pinned-backend live BLOCKED |
| Canonical development | `1b5423bc` | `uri-repo` `integration/git-sync-20261008` | **Does not contain URI Office** |

Evidence: `git worktree list`; `git ls-remote uri-repo` (2026-10-14);
`uri-office-assist-repair-qualification-20261013/M1_M2_FINAL_INTEGRATION_READINESS.md`;
`uri-windows-assistant-recovery-20261014/OFFICE_CONTRACT_INDEPENDENT_AUDIT_5b958da0.md`.

### 1.2 Capability inventory with status tiers

Tier codes:
- **P**: planned.
- **I**: implemented.
- **U**: unit or integration tested.
- **L**: live-tested on the Windows PC with the real UI and service (Brain under an owner-approved GPU override).
- **A**: independently accepted at an exact commit.
- **F**: frozen.

| Capability | Tier | Evidence |
|---|---|---|
| Open local .xlsx in the Univer OSS page inside a locked WebView2 host (values, formulas, basic styles, merges, widths) | I U L A | M1 AC1, AC10, AC15; live check 2026-10-12; M1-c3 ACCEPT |
| Shared versioned draft: URI and user edits, change marks, undo and redo, per-change accept or reject | I U L A | M1 AC2; `uri_office/draft.py` |
| Hash-bound approval (`change_sha256`), stale and replay refusal, A2UI confirmed action `office.apply_change` / `office.reject_change` | I U L A | M1 AC3; `uri_office/approvals.py`; `uri_a2ui/actions.py` |
| Direct cell patch that keeps unrelated parts byte-identical (lxml); CONFLICT on outside change; atomic write; backup | I U L A | M1 AC4, AC5; `uri_office/xlsx_patch.py` |
| 127.0.0.1 service: per-launch bearer token, current-user ACL, Host and Origin guards | I U A | M1 AC6; `tests/office/test_service.py` |
| Picker-granted files only, allowed roots, Windows path-shape refusals | I U A | M1 AC7; `uri_office/grants.py` |
| Google Sheets: read, edit a copy, export, share via upload (existing token reuse, no new scope) | I U A | M1 AC8, AC9; live Google is **NOT VERIFIED** (DEFERRED - OWNER) |
| Brain op planning (strict JSON schema, FAST tier, untrusted-data block) | I U L A | M1 AC13, AC16; `uri_office/brain.py` |
| Correction history (consented, no cell values, view and delete) | I U A | M1 AC12; not wired to Graphify (OFF-O3) |
| URI companion in the Office pane (typed and push-to-talk, routed to the open workbook) | I U L A | M1 AC19 |
| Multi-file sources, roles Reference / Check / Edit, one working file | I U L A | M2-AC1 to M2-AC13; Codex round 13 ACCEPT at `f50ae1e3` |
| Check mode: findings plus suggested fixes as change cards | I U L A | M2-D11; live run 4 |
| Save as new workbook (summary card, no overwrite, openpyxl) | I U L A | M2-AC9, M2-AC10 |
| `copy_range` with open ranges and bare-column targets; `OVERLAPS_EARLIER_OP` | I U L A | M2-D7, M2-D8 |
| Final live Excel qualification at `f50ae1e3` | L | `uri-office-final-qualification-20261013/M2_FINAL_LIVE_QUALIFICATION.md`: PASS. Regressions at that point: 926 passed, 1 failed (REG-EDGE). Repaired later. |
| Model-speed impact of the WebView2 panel (AC11) | P | **NOT VERIFIED.** No `WEBVIEW2_BRAIN_SPEED` record was found. |
| Real Excel-saved fixture (AC4) | I U | `tests/office/test_excel_saved_fixture.py` pins `excel_financial_sample.xlsx` by SHA-256. Provenance is in `tests/office/fixtures/README.md` (not re-audited in this pass). |
| Canonical integration | not done | BLOCKED: Linux-only gates, Brain-backed final live run (GPU `CONTENDED`, no override), owner authorization |
| Frozen | **none** | No Office capability is frozen. |

Test volume at `5b958da0`: 19 files in `tests/office` with 197 `def test_` functions (static count; not a run result).
The last recorded full Windows Office suite run was PASS in `coverage-office-final.log` (Assist repair qualification, commit `e0b5c298`).

### 1.3 Automation mechanism (how Excel actually works)

1. The owner types or speaks in the companion pane. `LivingServices.activeOfficeTarget` sends the request to the Office service, not to the general conversation.
2. `OfficeBrain.plan` makes one Runtime v1 call through `uri_operational_intelligence.brain_client`. It uses a strict JSON schema, the FAST tier, and the sheet excerpt inside an untrusted-data block.
3. `ops.to_cell_edits` / `copy_edits` validate every op deterministically. Invalid ops are reported and never guessed.
4. `Draft.propose` marks the changes. The owner accepts or rejects each change, or all of them (set hash).
5. `Approvals.propose` builds an A2UI surface bound to `change_sha256`. The action re-checks the target hash and writes atomically with a backup.

Strengths to keep:
- deterministic validation behind every Brain output;
- hash-bound approval;
- source protection by design;
- untrusted-data isolation;
- loopback service separated from the guarded worker.

### 1.4 Weaknesses and UX limitations (evidence-based)

| # | Finding | Source |
|---|---|---|
| W-1 | Office is a single rail item with a sheet-only panel. There is no home, recent work, templates or file browser. A first-time user starts at "Open file / New from files... / Paste a Google Sheets link". | `office_panel.dart` lines 169-201 |
| W-2 | A separate `DocumentsRegion` ("Letter / Spreadsheet / Document / Research" tiles) exists beside Office. It is marked simulated (`services.work.isSimulated`). Two entry points for documents already exist. | `workspace_mode_view.dart` line 739 |
| W-3 | Core already generates DOCX, XLSX, PPTX and PDF from Brain text (`uri_core/tools/generate_document.py`, `office_document_writer.py`). That path is markdown-to-file with no preview, no edit loop and no approval card. It is protected Core, so Office cannot change it. | source |
| W-4 | Every Office request is one Brain call. Clarification is a refusal message ("say why in message"). The Core intent-clarification flow is not used inside Office. | `brain.py` SYSTEM |
| W-5 | Brain-backed live runs need an owner-approved GPU override every time (Brain needs about 15.3 GB). Live qualification depends on the owner. | memory `uri-office-m1`; readiness report |
| W-6 | The main-UI conversation and memory and clarification paths were REJECTED in the owner live semantic review (`fcd9e257`). Office routes around them through its own pane, so cross-feature intent ("open Office and...") from the main conversation is not live-qualified. | `OWNER_LIVE_SEMANTIC_REVIEW_fcd9e257.md` |
| W-7 | The Office line is not in canonical. Any new Office work stacks on an unintegrated line, which raises merge risk. | 1.1 |
| W-8 | The canonical strict frozen checker exits 1 on canonical itself (inherited `server.py` and `fetch_url.py` drift). Every integration gate that runs it needs the owner's reconciliation decision. | `uri-ui-v2-final-qualification-20261013/FINAL_REPORT.md` |

### 1.5 What can support other formats

| Component | Reuse for Word, PDF, PPT |
|---|---|
| `service.py` transport, token, Host/Origin guards | Reuse as is. Add routes. |
| `grants.py` picker grants and path rules | Reuse. Widen the extension allow-list per format. |
| `draft.py` versioned draft, undo, redo, marks | The pattern is reusable, but the cell-addressed state is not. Add a document draft keyed by block address (section 7). |
| `approvals.py` hash-bound A2UI surfaces, audit chain | Reuse unchanged. Add `office.apply_document_change` to `uri_a2ui/actions.py` (additive, same as M1). |
| `brain.py` call shape, `untrusted.py` | Reuse. Add per-format op schemas. |
| `sources.py` roles (Reference / Check / Edit) | Reuse for every format. It is the cross-application input model. |
| `history.py` correction history | Reuse per document. |
| WebView2 locked host plus Univer page | Sheets only. It is not needed for document previews (section 3). |
| Core `PDFReader` (PyMuPDF plus Tesseract), `file_extraction` | Import read-only for extraction, as M1 imports `load_usable_credentials`. Do not change it. |
| Core `generate_document` / `convert_document` | Leave in place for the general conversation. Office does not call through it, because its path has no preview or approval. |
| `uri_operational_intelligence` draft desk (Text Intelligence) | Reuse its drafting prompts and pattern for letter and notice text. Wiring is a planning item for phase O3. |

## 2. Research: automation approaches (Phase 2)

### 2.1 Measured on this PC (2026-10-14)

Script, result, renders and hashes: `evidence/engine_probe_20261014/`. Environment: Windows 11, Python 3.13.15.
Library versions: python-docx 1.2.0, python-pptx 1.0.2, PyMuPDF 1.28.2, pypdf 6.19.0, Tesseract 5.5.3.

| Operation | Time | Notes |
|---|---|---|
| Create an office order (header, PAGE field footer, heading, 41-row table) with python-docx | 79 ms | |
| Mail merge: 40 letters from a template | 826 ms | 21 ms per letter |
| Reopen, edit one run, save | 19 ms | |
| 11-slide PPTX with speaker notes and a native chart (python-pptx) | 104 ms | |
| Generate a 20-page PDF (PyMuPDF) | 441 ms | |
| Extract text from 20 pages (PyMuPDF) | 103 ms | |
| `find_tables` on one page | 14 ms | |
| Merge 3 × 20 pages (pypdf) | 307 ms | |
| OCR one page at 200 dpi (Tesseract) | 1,163 ms | Text read correctly |
| Render one PDF page to PNG at 150 dpi (PyMuPDF) | 42 ms | |
| **LibreOffice 26.8.1 headless**, DOCX to PDF, cold (2026-10-15) | 26.5 s / 17.1 s | Peak RSS 418 MB / 396 MB (two runs) |
| LibreOffice, DOCX to PDF, second call | 7.5–7.6 s | Peak RSS 361 MB |
| LibreOffice, 11-slide PPTX to PDF | 7.4–8.1 s | Peak RSS 369 MB. All 11 slides and the native chart render. |
| Peak process RSS | 102 MB | |

**Correction 2026-10-15 (O2 review F12, N11):** the values in the table above do not match the committed
`evidence/engine_probe_20261014/engine_probe_result.json`. The output of the run that produced the table was not
committed and is not stored anywhere, so only the committed values count as evidence. The table is kept unedited
for history.

| Operation | Table | Committed |
|---|---|---|
| Office order (python-docx) | 79 ms | 50.0 ms |
| Mail merge, 40 letters | 826 ms | 880.7 ms |
| Reopen, edit, save | 19 ms | 19.7 ms |
| 11-slide PPTX with chart | 104 ms | 84.0 ms |
| Generate 20-page PDF | 441 ms | 435.1 ms |
| Extract text, 20 pages | 103 ms | 35.4 ms |
| `find_tables`, 1 page | 14 ms | 14.0 ms |
| Merge 3 × 20 pages | 307 ms | 332.0 ms |
| OCR 1 page, 200 dpi | 1,163 ms | 649.1 ms |
| Render 1 page, 150 dpi | 42 ms | 60.0 ms |
| Peak RSS | 102 MB | 102.3 MB |

The committed JSON also starts with a stray stdout line from PyMuPDF; the number of the run is not recorded. None
of the conclusions changes: every operation stays under 1 s, and all of them run on the CPU.

Notes on the measurements:
- All of these run on the CPU. None needs the GPU, so they do not compete with the Brain.
- **Negative result:** PyMuPDF base opens DOCX and PPTX as "Office document", but only as reflowed plain text. The header, the table, the centred heading and the slide layout are all lost. The 3-page order rendered as 9 pages, and 11 slides collapsed into 2 text pages (see the two PNGs). Base PyMuPDF is **not** usable for DOCX or PPTX previews. Faithful Office rendering in MuPDF is the commercial PyMuPDF Pro ([PyMuPDF Pro docs](https://pymupdf.readthedocs.io/en/latest/pymupdf-pro)), which is excluded by the no-paid-licence rule.

### 2.2 Engine comparison

| Candidate | Role | License | Windows / headless | Fidelity | Already in URI | Verdict |
|---|---|---|---|---|---|---|
| **python-docx** 1.2 | DOCX create, edit, structure | MIT | yes / yes | Keeps unknown XML. Run-level edits keep formatting. No layout engine. | yes (`requirements.txt`; Core writer) | **Select** for DOCX authoring and editing |
| lxml 6.1 | Low-level OOXML patch (as for xlsx) | BSD | yes | Byte-preserving part edits | yes | **Select** for in-place DOCX/PPTX patches where python-docx would rewrite parts |
| **python-pptx** 1.0 | PPTX create, edit, charts, notes | MIT | yes / yes | Native charts and tables. Layouts come from the template master. | yes | **Select** |
| PptxGenJS | PPTX create (JS) | MIT | Node | Good create, no edit of existing files | no | Reject: duplicates python-pptx and adds a Node runtime path |
| docx4j / Apache POI | DOCX/PPTX (Java) | Apache-2.0 | needs a JRE | Strong | no | Reject: adds a JVM for no proven gain over python-docx plus lxml |
| **PyMuPDF** 1.28 | PDF read, text, `find_tables`, render, annotate, redact, generate | **AGPL-3.0** or commercial ([Artifex](https://github.com/pymupdf/pymupdf)) | yes | High for PDF | yes (Core `PDFReader`, writer) | **Select** for PDF. OD-U3 records the AGPL acknowledgement. |
| **pypdf** 6.19 | Merge, split, rotate, form fields | BSD-3 | yes | Lossless page assembly | yes | **Select** for page assembly and AcroForm fill (keeps the AGPL surface small) |
| **Tesseract** 5.5 | OCR | Apache-2.0 | installed at `C:\Program Files\Tesseract-OCR` | Good on clean scans | yes (Core) | **Select** (existing) |
| **LibreOffice** headless (`soffice --headless --convert-to pdf`) | DOCX/PPTX to PDF for preview, Word-to-PDF output, visual qualification | MPL-2.0 | Windows supported; console use via `soffice.com`; one instance per profile ([ask.libreoffice.org](https://ask.libreoffice.org/t/file-format-conversion/90964/3)) | The only free high-fidelity OOXML layout engine found | **installed 2026-10-15** as a user-folder extract (`%LOCALAPPDATA%\URI\engines\libreoffice-26.8.1`). See `evidence/libreoffice_probe_20261015/`. | **Selected (OD-U2).** Fidelity verified on the probe documents. (download and install about 350 MB). Rasterize its PDF with PyMuPDF, because direct PNG export renders only the first page ([LibreOffice bug 157425](https://www.libreoffice.org/bugzilla/show_bug.cgi?id=157425)). |
| Univer docs preset | Rich in-app DOCX editing | Apache-2.0 core | WebView2 | DOCX import and export need the Univer Pro server; unlicensed use has a watermark and a 1 MB cap ([Univer import/export](https://docs.univer.ai/guides/docs/features/import-export)) | Univer sheets already bundled | Reject for now: a paid path, or a custom DOCX-to-IDocumentData converter with fidelity loss |
| docx-preview (docxjs) | DOCX to HTML preview | Apache-2.0 | WebView2 | Approximate HTML layout, not pixel-faithful; upstream inactive since about 2024 ([jsDelivr README](https://cdn.jsdelivr.net/npm/docx-preview@0.4.1/README.md)) | no | Fallback only if OD-U2 is declined |
| pdfplumber, camelot | PDF tables | MIT | yes | Comparable to PyMuPDF `find_tables` for ruled tables | no | Reject: redundant with PyMuPDF |
| OCRmyPDF | Searchable-PDF output | MPL-2.0 | needs Ghostscript | Good | no | Defer: Tesseract plus PyMuPDF text-layer insertion covers the need |
| docx2pdf, comtypes Word, PowerPoint COM | Conversion | — | needs Microsoft Office | — | — | Reject: no Office licence on this PC (`00_PLAN` section 11) |

**Smallest proven combination:** python-docx plus lxml, python-pptx, PyMuPDF plus pypdf, Tesseract (all already
dependencies) **plus one new component: LibreOffice headless**, used only as a sandboxed render and convert subprocess.
No new Python package is required.

LibreOffice is needed for all of the following:
- DOCX and PPTX previews;
- Word-to-PDF and PPT-to-PDF output;
- category K visual qualification.

Without it, those items are BLOCKED rather than approximated.

### 2.3 Google Docs and Slides

- The existing scopes (`drive.readonly`, `drive.file`) already let M1 upload and convert ("Share via Google"). The same route can create a Google Doc or Slides file from a local DOCX or PPTX. **NOT VERIFIED:** whether the Docs and Slides APIs accept `drive.file` for app-created files.
- In-place editing of existing Docs or Slides needs the `documents` / `presentations` scopes. That is a change to frozen `gmail_service.py` `SCOPES`, the same class as OFF-O1. Proposal: same default as OFF-O1, which is edit a copy and no new scope.
- Every Google action stays a separate, hash-bound approval card that names the local or cloud destination. Nothing is uploaded silently, and sharing changes are never made by URI (read-only display of the ACL).

### 2.4 Reusable automation patterns (across all apps)

1. **Extract, then a normalized content model, then render.** Each reader emits the same small model: blocks (heading, paragraph, table, image, slide, page) with a source reference (`file`, `page`/`para`/`cell`/`slide`). Every writer consumes that model. Cross-application workflows become reader × writer, not N² converters.
2. **Address-bound change sets.** Every edit names its address (cell, block path, slide/shape, page/annotation), plus before and after. The hash binds exactly what was shown (M1 rule, generalized).
3. **Deterministic first.** Mail merge, table extraction, page assembly, format conversion, style normalization and numbering are code. The Brain is used only for wording, summarizing, slide outlines, intent, and judging fuzzy structure.
4. **Role-tagged inputs** (M2-D10): Reference, Check or Edit. Never inferred.
5. **Validate after write:** reopen with the engine, run structural checks, render with LibreOffice, run visual checks (overflow, overlap, tiny text, empty placeholders).

## 3. Proposed capability matrix

Codes:
- **D**: deterministic code.
- **B**: Brain needed.
- **E**: engine.
- **Ph**: phase (section 8).

| Capability | DOCX | PPTX | PDF | Google | D/B | E | Ph |
|---|---|---|---|---|---|---|---|
| Open, outline view, page preview | yes | yes | yes | yes (export, then preview) | D | LO render + PyMuPDF raster | O2–O5 |
| Create from template (letter, notice, office order, memo, minutes, report) | yes | yes | via DOCX→PDF | copy | D layout + B wording | python-docx / pptx | O3, O5 |
| Natural-language edit as change cards | yes | yes | annotations only | edit a copy | B → D validate | python-docx / lxml / pptx | O3, O5 |
| Headers, footers, page numbers, sections, tables | yes | — | — | — | D | python-docx + lxml | O3 |
| Format correction (style normalize, numbering, spacing, fonts) | yes | consistency | — | — | D detect + D fix; B only to explain | python-docx | O3 |
| Proofread, rewrite, summarize | yes | yes | read-only | — | B | Runtime v1 | O3 |
| Compare two documents, draft tracked changes (`w:ins`/`w:del`) | yes | — | text compare | — | D diff + B summary | lxml + difflib | O3 |
| Mail merge from Excel rows | yes | (one slide per row) | via conversion | — | D | python-docx | O7 |
| Text, tables, fields extraction | yes | yes | yes, OCR fallback | — | D | readers + Tesseract | O4 |
| Page-cited Q&A over documents | yes | yes | yes | — | D retrieve + B answer with citations | PyMuPDF + Brain | O4 |
| Merge, split, rotate, reorder, assemble | — | — | yes | — | D | pypdf | O4 |
| Highlight and annotate | — | — | yes | — | D | PyMuPDF | O4 |
| Form analysis and assisted fill | — | — | AcroForm | — | D fields + B suggest values from sources | pypdf | O4 |
| Related notices and corrigenda detection | yes | — | yes | — | D (reference numbers, dates) + B confirm | readers | O4/O8 |
| Slides from document, PDF or Excel (outline, charts, notes) | — | yes | — | — | B outline → D layout | python-pptx | O5/O7 |
| Overcrowding and readability check | — | yes | — | — | D (text box fit, font size, contrast) | pptx + render | O5 |
| Conversion DOCX↔PDF, PPTX→PDF | yes | yes | yes | export | D | LibreOffice | O2 |
| Contextual suggestions | all | all | all | — | D triggers, B wording optional | — | O8 |

Explicitly out of scope:
- WYSIWYG rich-text editing of DOCX inside URI (no free engine; section 4 explains the editing model);
- animations beyond python-pptx-safe transitions (python-pptx has no transition API; those would be raw XML: deferred);
- macros;
- real-time multi-user editing.

## 4. Recommended unified workspace design (Phases 4 and 5)

### 4.1 Concepts evaluated

| Concept | Description | Function | Build cost | Performance | Consistency | Scale | UX |
|---|---|---|---|---|---|---|---|
| A. Tabs per app | Separate Word, PDF, PPT and Excel panels under the Office rail | Medium | Low | Good | Medium | Poor: grows per app | Fragmented. The user must pick an app first. |
| **B. Outcome-first Office region** | One Office region: secondary left list (Home, Recent, Documents, Spreadsheets, Presentations, PDFs, Templates, Workflows) · centre surface by file type (sheet = existing Univer page; document, slide or PDF = page preview plus outline) · right pane = existing companion (AC19) generalized · compact status strip | High | Medium: reuses the M1 panel structure | Good: previews are PNG raster, no second WebView | High: same rail, orb, companion | Good: a new format adds one centre view | Best. The user states an outcome; files and workflows sit together. |
| C. Conversation-only | Everything through the main companion; files shown as cards | Low for inspection | Low | Best | High | Good | Poor: no place to inspect or correct output |

**Recommendation: B.** It is the only concept that meets preview-before-commit and "inspect and correct". It also keeps one assistant (the existing companion pane) and adds one centre view per format instead of one app per format.

Concept A was rejected because it builds the "separate scripts per format" experience the brief rejects. Concept C was rejected because it cannot show fidelity problems.

Mockups (2026-10-15): `design/office_workspace_mockups.html`, published privately at https://claude.ai/artifact/MwCYF84TWc6NtMBXG4PA8T. The page shows two variants of concept B:
- **B1:** three panes (files, page, companion), recommended. Structure from AFFiNE (sidebar, document, AI chat panel `packages/frontend/core/src/blocksuite/ai/chat-panel/`) and Paperless-ngx (`src-ui/src/app/components/document-detail/`).
- **B2:** task panel, workbench and companion drawer. Structure from Stirling-PDF (`frontend/editor/src/core/components/layout/Workbench.tsx`, `shared/quickAccessBar/`).

The `docs/design_library/` index had no Office or document pattern, so these external references were verified with `gh api` on 2026-10-15. Licences:
- AFFiNE and Stirling-PDF: MIT core with proprietary portions;
- Paperless-ngx: GPL-3.0.

They are structural references only; no code is used. **Owner decision 2026-10-15 (OD-U5): B1, with B2's goal grouping and 10 refinements.** See section 12a and `01_O2_PLAN_AND_ACCEPTANCE_CRITERIA.md` section 4.

### 4.2 Concept B behaviour

- **Office Home** shows these sections:
  - "What do you want to make?" A single input, plus template chips: Letter, Office order, Notice, Minutes, Report, Presentation, Extract tables.
  - Recent work.
  - Workflows in progress.
- First-time guidance is one dismissible line under the input, shown until the first completed workflow. It is never shown again (persisted flag).
- **Centre:**
  - Sheets use the existing Univer page.
  - Documents, slides and PDFs use a page preview with a thumbnail rail and an outline list. Selecting a paragraph, slide or page scopes the next request to it.
- **Editing model for DOCX and PPTX:** conversation, outline actions (move, delete, restyle a block), and change cards with before and after preview. An "Open in default app" fallback is kept. This is honest about the absence of a free embedded word processor.
- **Right pane:** the same companion. It holds:
  - the request;
  - clarification chips;
  - the **workflow plan card**;
  - change cards;
  - findings;
  - the approval card;
  - at most one suggestion, which is dismissible and can be muted per file.
- **Status strip:** current step, progress, save state ("Unsaved draft" / "Saved to …" / "Original untouched"), validation findings count, last error with a recovery action.
- **Keyboard:**
  - Ctrl+K focuses the request;
  - Ctrl+Z and Ctrl+Y undo and redo the draft;
  - Enter accepts the focused card;
  - Esc dismisses a suggestion;
  - Ctrl+S proposes a save (still opens the approval card).
- **The main companion** can open Office ("prepare a notice from these files"). It hands over through `LivingServices.activeOfficeTarget` and the existing UI-state controller. That handoff depends on W-6 (main-UI intent routing) being repaired outside this milestone. Until then, the Office entry point is the rail.
- **The `DocumentsRegion`** (simulated) is replaced by Office Home in O2 (W-2), so one documents entry point remains.

## 5. Intelligent automation workflow design (Phases 3 and 6)

### 5.1 Request lifecycle (one path for every format)

1. **Intent.** The Brain classifies the request into a closed set of Office intents, with a strict schema:
   - `create_document`
   - `edit_document`
   - `correct_formatting`
   - `compare`
   - `mail_merge`
   - `extract_tables`
   - `summarize`
   - `make_presentation`
   - `convert`
   - `assemble_pdf`
   - `answer_question`
   - `check`
   - `other`

   Slots: output format, inputs needed, recipients or rows, template. Unknown means `other`, which asks; it never guesses (consequence-aware binding memory rule).
2. **Inputs.** The open files and their roles are used. If a needed input is missing, one clarification chip set asks for it ("Which Excel file has the records?"), with a file picker. Roles are always chosen by the owner (M2-D10).
3. **Plan card** (A2UI, read-only). It shows:
   - the steps, each marked deterministic or URI-written;
   - the files read;
   - the files that will be produced (names, count, folder);
   - "originals will not change".

   The owner presses Run or adjusts. For a single-change edit the plan card is skipped and change cards appear directly (the M1 behaviour), so there is no extra click for small tasks.
4. **Execute** in a working folder under `%LOCALAPPDATA%\URI\office\work\<workflow_id>`. Steps run deterministically; Brain steps produce validated op JSON only.
5. **Validate.** Reopen, then structural checks, then render, then visual checks. Placeholders such as `«Name»` must not remain. The results show as findings.
6. **Preview** in the centre view. Batch outputs show the first item, a list, and per-item validation status.
7. **Approve output.** A hash-bound card binds the content hashes of all outputs plus their destinations. Write with no overwrite (M2-AC9 rule). Originals are never written unless the file has the Edit role, and then only through the M1-style backup and CONFLICT path.
8. **Refine.** Offer at most two follow-ups taken from the intent ("Make it shorter", "Convert to PDF").

### 5.2 Workflow record (structured, per run)

`workflows/<id>/workflow.json` records (path corrected 2026-10-15, O2 review F16):
- intent;
- inputs (file id, role, sha256 before);
- steps (kind D/B, engine, version, duration, result);
- outputs (path, sha256, validation results);
- approvals (surface id, hash);
- errors and recovery.

It never records document content. The same file is the source of qualification evidence (section 10) and resume-after-crash: an unfinished step is re-run from its inputs and never assumed done.

### 5.3 Recommendations engine (Phase 8)

Deterministic detectors on open files only:

| Detector | Suggestion |
|---|---|
| PDF with 1 or more tables | "Extract the tables into Excel?" |
| DOCX longer than 1,500 words with headings | "Make a presentation from this report?" |
| Excel with a name-like column and an open letter template | "Make one letter per row (N)?" |
| Two open documents with the same reference number | "Compare these two orders?" |
| Formatting drift (mixed body fonts, inconsistent numbering) | "Fix formatting?" |

Rules:
- At most one visible suggestion.
- Never during a running workflow.
- Dismissed suggestions are muted per file and per detector.
- No learning from content.
- "Previously approved workflows" means a list of the owner's saved workflow recipes (intent plus steps, no content). The list is kept only after an explicit "Save as workflow" action (consent).
- Correction history stays as in OFF-O3.

### 5.4 Document intelligence boundaries

- Facts in an output must trace to an input block reference or to the owner's instruction. A Brain op that inserts a date, number or name with no source is flagged "unsourced" in the change card and is never auto-filled.
- Brain inputs are bounded excerpts inside untrusted-data blocks (M1 AC16). Page-cited Q&A retrieves blocks deterministically (keyword plus reference-number match) and then asks the Brain to answer only from the numbered blocks, citing them. An answer with no citation is shown as "not found in the files".
- Memory and Graphify: no automatic writes from document content. Any later wiring is an owner frozen-file decision (OFF-O3 class).

## 6. Cross-application integration strategy

| Workflow | Readers | Deterministic core | Brain role | Writer |
|---|---|---|---|---|
| Excel → Word (letters, report) | openpyxl (existing reader) | mail merge, table placement | narrative paragraphs (optional) | python-docx |
| Excel → PowerPoint | openpyxl | chart data and native chart | slide titles and takeaways | python-pptx |
| PDF → Word | PyMuPDF (+OCR) | blocks and tables to DOCX | none (conversion) or rewrite on request | python-docx |
| Word → PowerPoint | python-docx | heading tree to slide skeleton | condense bullets, speaker notes | python-pptx |
| PDF → Presentation | PyMuPDF | page and section split | outline | python-pptx |
| Word → PDF | — | LibreOffice convert | none | LibreOffice |
| Multiple documents → summary | all readers | retrieval with citations | summary with citations | python-docx |
| Excel + PDF → official report | openpyxl + PyMuPDF | tables and facts with source refs | narrative from sourced facts only | python-docx (→ PDF) |
| PDF tables → Excel | PyMuPDF `find_tables` | cell mapping | none | openpyxl (M2 new-workbook path, with its approval) |

PDF tables → Excel reuses the M2 new-workbook flow: the extracted tables become `copy_range`-like ops into a new workbook, so the existing approval and save path is used unchanged.

## 7. Architecture (Phase 7, smallest that meets the requirements)

```
Living Workspace (Flutter, existing)
  Office region (concept B)  -- right pane: existing companion (AC19)  -- A2UI cards (existing renderer)
     centre: Univer sheet page (existing) | PagePreview (PNG pages + outline, new) 
  OfficeController -> HTTP 127.0.0.1 + bearer (existing client)
URI Office service (existing uri_office/, extended - NOT a new service)
  capabilities.py   static registry: intent -> required inputs, steps, engines (plain dict, no framework)
  workflows.py      runs a plan: working folder, workflow.json, resume, validation hook
  content.py        normalized block model + source refs (readers emit, writers consume)
  docx_io.py / pptx_io.py / pdf_io.py   readers, writers, address-bound ops (validated like ops.py)
  doc_draft.py      versioned draft for block-addressed changes (draft.py semantics: marks, undo/redo, change_sha256)
  render.py         LibreOffice headless subprocess (private -env:UserInstallation profile, no network config,
                    Job Object kill, timeout, one queue) -> PDF -> PyMuPDF PNG; cache by input sha256
  validate.py       structural + visual checks
  existing: grants, approvals, brain (+ per-intent schemas), sources (roles), history, google (+ Docs/Slides copy)
Core: imported read-only (PDFReader, load_usable_credentials); uri_core unchanged.
```

**Rejected:**
- a separate Office workflow microservice;
- a new agent or orchestrator;
- routing Office through the guarded worker (its FixtureGuard forbids user-file I/O, as in M1 section 4);
- changing Core `generate_document`.

**Security:**
- Grants extend to `.docx`, `.pptx`, `.pdf`, under the same path rules.
- External content stays untrusted:
  - DOCX: `altChunk`, external relationships (`TargetMode="External"`), OLE objects and field codes such as `INCLUDETEXT` are refused or stripped from outputs and reported;
  - PDF: JavaScript, launch actions and embedded files are never executed.
- LibreOffice runs headless with:
  - a fresh profile;
  - macros disabled (security level set in the profile);
  - no network; enforcement method to be proved in O2: profile proxy to an unreachable port and update checks off;
  - output only into the working folder.

**Resources:** CPU-only engines (section 2.1). LibreOffice is started on demand and exits after an idle timeout. **Update 2026-10-15 (`evidence/lo_qualify_20261015/`):** a persistent listener converts a warm DOCX in 0.36 s against 6.1 s per call, so O2 uses the listener. The default LibreOffice profile fetched an external-link canary; the hardened profile did not. There is no GPU use other than the existing Brain. Measured: 7–26 s and about 360–420 MB per conversion, process per call. O2 must measure a persistent listener (`soffice --accept`, UNO) and choose it if it is materially faster. Previews are cached by input SHA-256.

**Recovery:**
- working copies and atomic writes;
- backups for Edit-role saves (M1);
- `workflow.json` resume;
- render failures degrade to "preview unavailable", never to a silent pass.

## 8. Phased roadmap

Each phase:
- has its own branch `phase/uri-office-u-<n>` and worktree;
- follows the lifecycle (plan, freeze, implement, independent review, repair, gates, live, owner check);
- reaches integration only on owner authorization (OFF-O5 pattern).

| Phase | Scope | Depends on | Key acceptance criteria |
|---|---|---|---|
| **O1** Foundation readiness (governance, not code) | Owner decides OD-U1 (base), the frozen-checker reconciliation (W-8) and Office M1/M2 integration status. Record the Excel baseline numbers (latency, RSS, Brain tok/s with the panel: the missing AC11). | owner | Baseline evidence file. Canonical or stacked base pinned. |
| **O2** Unified workspace and shared engine layer | Office Home, secondary navigation, recent work, `content.py`, `render.py` (LibreOffice), `PagePreview`, status strip, `capabilities.py`, `workflows.py`, grants for new formats, `DocumentsRegion` replaced | O1, OD-U2, OD-U5 | Open DOCX, PPTX and PDF read-only with faithful previews. Render sandbox has no network (canary test as in M1). Excel unchanged (M1/M2 suites pass). |
| **O3** Word | Templates (letter, office order, notice, memo, minutes, report), NL edit change cards, headers, footers, numbering, format correction, proofreading, compare and tracked-change draft, Word→PDF | O2 | Each template validates and renders without clipping. Edits keep unrelated XML parts byte-identical. Originals never written without Edit role plus approval. |
| **O4** PDF | Extraction with OCR fallback, cited Q&A, tables→Excel (M2 path), assemble (merge, split, rotate, reorder), annotate, AcroForm assisted fill, related-notice detection | O2 (parallel with O3 after O2) | Page citations resolve to the right page. Original PDF byte-identical. Scanned fixture is OCR'd. |
| **O5** PowerPoint | Slides from outline or document, templates and themes from a master, charts and tables, notes, overcrowding and readability checks, reorganize, shorten, expand | O2 (parallel with O3/O4) | No text overflow in rendered slides. Native charts open in LibreOffice. Readability detector catches seeded defects. |
| **O6** Google Docs and Slides | Copy, upload-convert, export, read-only sharing view; in-place edit only if OD-U4 grants scopes | O3, O5, OD-U4 | No upload without a card naming the cloud destination. `drive.file` behaviour verified live. |
| **O7** Cross-application workflows | Excel→Word mail merge, Excel→PPT, PDF→Word, Word→PPT, multi-document summary, Excel+PDF→report | O3, O4, O5 | Every output fact traces to a source block. Batch of 40 letters validated per item. |
| **O8** Contextual recommendations | Detectors, one-suggestion rule, mute, saved workflow recipes (consent) | O7 | Suggestion precision on the fixture set. No suggestion while running. Mute persists. |
| **O9** UX refinement and whole-program qualification | First-time user study (scripted plus owner), repeated runs, performance comparison with the Excel baseline, independent whole-diff audit | all | Section 10. |

Not in scope: Mission Control, Skill Command Center, production deployment, protected Core changes.

## 9. Parallel development

- **Serial:** O1, then O2. O2 owns the shared files (`service.py` routes, `office_panel` → Office region, `capabilities.py`, `workflows.py`, `render.py`, `uri_a2ui/actions.py` additions).
- **Parallel after O2 freezes its interfaces:**
  - O3 owns `docx_io.py` and `doc_draft` DOCX ops;
  - O4 owns `pdf_io.py`;
  - O5 owns `pptx_io.py`;
  - each phase brings its own tests and fixtures folder;
  - shared-file edits go through a small additive registration (one entry in `capabilities.py` per phase), merged in a fixed order: O3 → O4 → O5.
- **One writer per file set.** `uri_a2ui/actions.py` (shared with other milestones) gets all new Office actions in O2, so later phases do not touch it.
- **Live Brain runs are serialized** on the GPU lease. Only one live qualification at a time.

## 10. Test, audit and live qualification plan

For every phase, the qualification record holds:
- exact commit, tree and environment (WebView2, LibreOffice, Tesseract and Python package versions);
- inputs;
- expected results;
- actual outputs (hashes, plus the files when non-sensitive);
- renders;
- performance;
- findings;
- repairs;
- regressions;
- the independent verdict.

Only `COMPLETED_WITH_RESULT` evidence supports PASS (CLAUDE.md).

| Category | Method |
|---|---|
| A Functional accuracy | Scripted requests through the real UI (Flutter driver harness pattern `office_live_check.dart`), real service, real Brain. Output checked by an independent validator script, not the code under test. |
| B Fidelity | Render source and output with LibreOffice. Compare the pages that should be unchanged by pixel diff (threshold). Unknown XML parts are byte-compared. |
| C Intent | A fixed set of about 40 natural-language requests per phase, including ambiguous and multi-step ones and follow-ups. Expected intent and clarification are recorded beforehand. |
| D Automation | Single, batch (40 or more), cross-application and repeat runs. |
| E UX | Scripted first-time-user path. Owner session with think-aloud notes, time-to-first-output and confusion points. Repairs are re-tested. |
| F Failure | Malformed, encrypted and oversize files; external-link and macro DOCX; JavaScript PDF; LibreOffice crash or timeout; disk-full simulation; service restart mid-workflow (resume); lock file present (CONFLICT). |
| G Integrity | Source hashes before and after every run. Backups exist. No stray files outside the working folder. Undo restores. |
| H Performance | Latency per step, process RSS (service, LibreOffice), CPU, GPU census before and after, Brain tok/s with Office open versus the Excel baseline (O1). UI frame timing (existing perf logger). |
| I Cross-application | The section 6 workflows end to end. |
| J Real-world | Fixtures:<ul><li>an official letter;</li><li>an office order with a transfer table;</li><li>a notice and a corrigendum pair;</li><li>a memorandum;</li><li>minutes;</li><li>a table report;</li><li>Excel-driven letters;</li><li>a multi-PDF summary;</li><li>a scanned PDF;</li><li>report → deck.</li></ul>Synthetic but realistic content; no personal data. Real owner documents are used only with explicit consent and kept out of git. |
| K Visual | Rasterize every output page and slide. Automated checks: text bounding boxes outside the page or shape (overflow), overlapping boxes, font size below 10 pt on slides or 8 pt in documents, empty placeholders. Plus independent visual inspection by the reviewer of a sampled set, recorded with screenshots. |
| L Repeat and regression | 5 repeats of representative workflows. Full M1/M2 Office suites, A2UI, Living Flutter tests, `ws_frozen_check` on every phase. |

**Audit:** whole-diff independent review at the exact commit (lifecycle reviewer, or a separate Claude reviewer process while the owner's CLI is logged out, as in FCV-20261014). Then repair, re-audit and the owner live check. Integration runs only after explicit owner authorization. Nothing is frozen until Windows live functional and UX qualification passes and independent acceptance exists.

**Known live-qualification blockers (carried, not hidden):**
- The Brain needs an owner GPU override for each live run (W-5). Without it, live Brain categories are BLOCKED.
- LibreOffice was installed without admin rights as a user-folder extract (both elevated attempts were cancelled at UAC). Categories B, K and Word→PDF are unblocked.
- Linux gates: not a target (owner ruling 2026-10-11). They stay NOT VERIFIED and non-blocking for Office, unless the owner's later integration rule requires them (the readiness report lists them as blocking for the M1/M2 integration).

## 11. Delivery order for the first implementation milestone

The recommendation is to start O2, not Word first. A Word milestone without the shared preview, render and workflow layer would build the "separate script" pattern again. O2 is also where the main design risk sits (LibreOffice sandbox, preview UX). O2 ends with read-only open and preview for every format, plus the Home and workflow card skeleton. O3, O4 and O5 then plan in parallel.

## 12. Owner decisions needed before freeze

| Id | Decision | Recommendation | Effect if declined |
|---|---|---|---|
| OD-U1 | Base for new Office work: stack on the Office line (`5b958da0`) now, or wait until M1/M2 is integrated into canonical | Stack on `5b958da0`. Rebase when Office integrates. | Waiting blocks all phases on the M1/M2 integration blockers. |
| OD-U2 | Download and install LibreOffice (MPL-2.0, about 350 MB, official installer, pinned version) as the render and convert engine | Approve | No faithful DOCX/PPTX preview, no Word→PDF, categories B and K BLOCKED. docx-preview fallback only for DOCX. |
| OD-U3 | Acknowledge PyMuPDF AGPL-3.0 (already a Core dependency) for Office PDF features. URI is local and personal; distribution would need AGPL compliance or a licence. | Acknowledge. Use pypdf for assembly. | Without it, PDF render and annotate need another engine (none equivalent found). |
| OD-U4 | Google Docs/Slides in-place edit scopes (frozen `gmail_service.py` change) | Not now: copy, upload-convert and export only (same as OFF-O1) | — |
| OD-U5 | Workspace concept B (after mockups) | B | Re-plan O2 |
| OD-U6 | Live-run GPU override policy for this program: per run (current) or standing for scripted qualification windows | Per qualification window, logged | Per-run approvals slow O2–O9 |
| OD-U7 | Real owner documents for category J (consent, kept out of git) or synthetic only | Synthetic first. Owner documents in the owner check only. | — |

## 12a. Owner rulings recorded 2026-10-14 (answered in chat)

| Id | Ruling |
|---|---|
| OD-U1 | Stack new Office phases on `5b958da0`. Rebase when M1/M2 integrates into canonical. |
| OD-U2 | LibreOffice download and install approved: official package, pinned version, run only as a sandboxed headless subprocess. |
| OD-U6 | GPU override: one logged override window per phase qualification. No process is killed without asking. |
| First milestone | O2 (shared workspace and render layer). |
| OD-U5 (2026-10-15) | **B1 approved with refinements**: three panes (files and workflows, workbench, URI), plus B2's goal-based task grouping, plus 10 refinements. Records: `docs/design_library/approved/office_workspace_2026-10-15.md`, `rejected/office_workspace_b2_layout_2026-10-15.md`. Detailed O2 plan: `01_O2_PLAN_AND_ACCEPTANCE_CRITERIA.md`. |

## 13. Self-review against section 0 (draft 1)

| Criterion | Result | Notes and repairs made in this draft |
|---|---|---|
| P1 | Met | Every tier cites a commit or report. AC11: `docs/office/evidence/` holds only GPU-advice probes, with no speed record, so it is P / NOT VERIFIED. Excel-saved fixture provenance is not re-audited (stated). |
| P2 | Met | Measured: python-docx, python-pptx, PyMuPDF, pypdf, Tesseract. The negative PyMuPDF render result is preserved. **Measured 2026-10-15:** LibreOffice fidelity, RSS and cold and warm time. **Not measured:** a persistent-listener mode, docx-preview fidelity, `drive.file` with the Docs and Slides APIs. Each is marked, and each affects only its own phase. |
| P3 | Met | Extends `uri_office`. No new service or assistant. |
| P4 | Met | Core imported read-only. Scope changes are routed to OD-U4. |
| P5 | Partly met | Phase-level criteria are given. Per-phase frozen blueprints with full AC tables are produced at each phase's plan step (lifecycle), not in this program plan. |
| P6 | Met | Sections 2.1, 2.3, 7, 10, 13. |
| P7 | Met | Section 8. |

Unresolved risks:
- The main-UI intent routing defect (W-6) is outside this program. It limits "open Office through conversation" until it is repaired.
- The Office M1/M2 integration blockers (W-7, W-8) stay with the owner.
