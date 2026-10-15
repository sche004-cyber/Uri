# URI Office Unified: O2 plan and acceptance criteria (frozen-blueprint candidate, rev 1)

Date: 2026-10-15. Milestone `URI-OFFICE-U`, phase **O2: unified workspace, engine layer and validation pipeline**.
Planning branch `phase/uri-office-unified-plan` (base `5b958da0`, local only). Programme plan:
`00_DISCOVERY_RESEARCH_AND_ROADMAP.md`. Status: **CANDIDATE, NOT FROZEN, NOT AUTHORIZED FOR IMPLEMENTATION.**

Owner authorization in force (chat, 2026-10-15):
- OD-U5 is settled: B1 with B2 goal grouping.
- Planning, acceptance criteria, live-test matrices and independent review are authorized.
- O2 implementation, frozen-system changes and integration are **not** authorized.

## 0. Acceptance criteria for this plan

| # | Criterion |
|---|---|
| Q1 | The Excel baseline is re-verified today, and every reuse claim cites a file and line. |
| Q2 | Each engine decision cites a measurement made on this PC, or names the missing measurement. |
| Q3 | The B1 architecture covers the owner's 10 refinements, each with an acceptance criterion. |
| Q4 | It reuses the existing Office service, approvals, A2UI actions, Brain client, companion and UI-state controller. There is no second service, no second assistant and no parallel approval path. |
| Q5 | No protected path (`scripts/ws_frozen_check.py` `PROTECTED`) is touched. |
| Q6 | Every O2 acceptance criterion has an automated test and, where it applies, a live check. Every live check names its environment and says whether it needs the Brain or the owner. |
| Q7 | The live matrix covers the owner's 17 test items and categories A–L. Items that do not apply to O2 say so. Items that cannot run say BLOCKED or NOT VERIFIED. |
| Q8 | Security and owner gates are explicit. Nothing uploads, shares, installs or elevates. |
| Q9 | The O3, O4 and O5 phases are outlined, with scope, dependencies and key criteria. |
| Q10 | Risks are named with severity and mitigation. Unverified items are listed with their effect. |
| Q11 | An independent reviewer gives a verdict, and the findings are repaired or answered (section 16). |

## 1. Verified Excel baseline and reuse

### 1.1 Baseline, re-checked 2026-10-15

Evidence: `evidence/excel_baseline_20261015/`.

| Check | Result |
|---|---|
| `pytest tests/office tests/a2ui` at `5b958da0` code | **483 passed, 5 skipped, 0 failed** (after staging the hash-verified Univer bundle; without it, 1 failure, `BundleRefused`) |
| `flutter test test/office` + presentation controller + living shell | **58 passed** |
| Status tiers per capability | Unchanged from programme plan section 1.2. M1 and M2 are accepted code. Nothing is frozen. The line is not in canonical `1b5423bc`. |
| AC11 (Brain speed with the WebView2 panel open) | **NOT VERIFIED.** It needs a GPU window (OD-U6). O2 measures it in its Brain window. |
| Live Excel at `5b958da0` | Last live pass was at `f50ae1e3` (M2 final). Pinned-backend live at `5b958da0` is BLOCKED (audit `OFFICE_CONTRACT_INDEPENDENT_AUDIT_5b958da0.md`). O2 does not depend on it, but O2's live run re-checks Excel (L-items in section 12). |

### 1.2 What O2 reuses (verified in source at `5b958da0`)

| Existing part | Location | O2 use |
|---|---|---|
| Loopback HTTP service, bearer token, ACL, Host and Origin guards | `uri_office/service.py:612-765` | Same server. O2 adds routes and one binary (PNG) response path. |
| Session table | `service.py:74-131` (`Office`, `_session`, `open_local`) | A document session sits beside the workbook session. Workbook code is unchanged. |
| Picker grants and path rules | `uri_office/grants.py` (`.xlsx` only, `grants.py:84`) | Add per-kind suffixes `.docx .pptx .pdf` through a parameter. The `.xlsx` default and its messages stay, so the existing tests stay green. |
| Hash-bound approvals and audit chain | `uri_office/approvals.py` (`propose`, target kinds `local`, `google`, `google_upload`, `new_file`) | Add target kind `output_files`. **No new apply or reject action:** `office.apply_change` / `office.reject_change` already bind `change_sha256` to any body. |
| A2UI action registry | `uri_a2ui/actions.py:30-31`, Dart mirror `uri_ui/lib/living/a2ui/a2ui_contract.dart:117-119` | Add `office.run_plan` (confirms, `plan_sha256`) and `office.discard_plan`. This is the only A2UI growth. |
| Brain client | `uri_office/brain.py` via `uri_operational_intelligence.brain_client` (FAST tier, strict schema, untrusted block) | Add one schema: Office intent classification. `OfficeBrain.plan` for sheets is unchanged. |
| Untrusted-data wrapper | `uri_office/untrusted.py` | File names, outlines and request history in Brain prompts. |
| Companion routing | `LivingServices.activeOfficeTarget` (`living_scope.dart:159`), `office_panel.dart:208-400` | The companion pane is extracted into its own widget, without behaviour change for sheets. The target is generalized to documents. |
| UI-state controller | `UiPresentationController`, `ShowModeCommand`, `WorkspaceFocus.office` (`presentation_controller.dart:26-160`) | Add an optional `OfficeView` to `ShowModeCommand` and phrases such as `uri office pdfs`. Same cooldown, same history and Back. |
| Rail and regions | `workspace_mode_view.dart:103-105,158` | The rail "Documents" item and the simulated `DocumentsRegion` (`:740`, `work_items.dart:166` `isSimulated => true`) are removed. `WorkspaceFocus.documents` stays as an alias that opens Office › Documents. |
| Live UI harness pattern | `uri_ui/lib/office_live_check.dart`, `office_m2_live_check.dart` | New `office_o2_live_check.dart` on the same pattern. |
| Core PDF and OCR | `uri_core/tools/pdf_reader.py` | **Not used in O2.** PDF preview uses PyMuPDF directly. OCR starts in O4. Core stays untouched. |

## 2. Scope

### 2.1 In O2

1. **B1 Office workspace.**
   - Panes: left (files and workflows), centre (workbench), right (URI).
   - Panes are resizable and collapsible, and there is a responsive layout.
   - Also in this item: the status strip, the Office Home, onboarding and contextual hints.
2. **Open and preview DOCX, PPTX and PDF, read-only.**
   - Faithful page images, a thumbnail rail and an outline.
   - Selecting a page or slide sets the request scope.
3. **Engine layer.**
   - LibreOffice render service: pinned, hardened profile, persistent listener, Job Object, external-link sanitizer.
   - PDF rasterizing with PyMuPDF.
   - Preview cache.
4. **Shared validation pipeline**, with the findings model and the repair interface (section 8).
5. **Workflow runner.**
   - Each run has a working folder, a `workflow.json` record, resume, cancel and progress.
   - Plan card (A2UI), output approval (A2UI) and no-overwrite save.
6. **One end-to-end workflow: Convert to PDF** (DOCX or PPTX to PDF).
   - It is deterministic and needs no Brain.
   - It exercises every pipeline stage, so the whole pipeline can be live-qualified without a GPU window.
7. **Capability registry and intent routing.**
   - Requests are first matched by a deterministic phrase matcher. The Brain classifies only when the matcher fails, into the closed intent set.
   - A clarification is offered as chips.
   - For a planned (not yet built) capability, URI answers honestly: "not available yet".
8. **Recent files and the workflows list.** Real data, with a Clear action.
9. **Navigation by URI** through the UI-state controller.
10. **Conversation context kept across Office views.**
11. **Excel kept working unchanged.** The Univer sheet is shown in the centre pane, and the companion stays on the right.

### 2.2 Not in O2

- Editing DOCX, PPTX or PDF (O3, O5, O4).
- Templates content (O3).
- OCR and document Q&A (O4).
- Batch and mail merge (O7).
- Recommendations (O8).
- Google Docs or Slides (O6).
- Any main-conversation intent routing (W-6, outside this programme).
- Mission Control or the Skill Command Center.
- Any protected path.

Integration recommendation: **do not integrate O2 alone**, because documents are read-only in O2. Integrate O2 with O3
(Word) so the owner first meets an Office that can make and change a letter. This is the owner's call at the
integration gate.

## 3. Engine decisions and evidence

| Need | Engine | Evidence (this PC) | Status for O2 |
|---|---|---|---|
| DOCX/PPTX page images and DOCX/PPTX→PDF | LibreOffice 26.8.1.1, user-folder extract, `soffice.bin` SHA-256 `cb08cffd…2fa1` | `evidence/lo_qualify_20261015/`: persistent listener warm DOCX **0.36 s**, PPTX **0.42–0.53 s**, start-up about 10.6 s, idle RSS **390 MB**. Per-call mode takes 6–18 s. Fidelity checked on 2 fixtures. Job Object close leaves 0 processes. | **Selected, in listener mode.** Qualified as a dependency only after the O2 failure tests (F-items) pass. |
| Network isolation of LibreOffice | Hardened private profile (macros off, `BlockUntrustedRefererLinks`, proxy to `127.0.0.1:9`) **plus** removing external relationships from the copy that is rendered | The default profile **fetched** the canary. The hardened profile made 0 fetches, in both modes. | Required. Canary in every qualification run. |
| PDF page images, outline, text layer for the selection scope | PyMuPDF 1.28.2 | 42 ms per page at 150 dpi (2026-10-14) | Selected. Needs **OD-U3** (AGPL acknowledgement) before implementation starts. |
| DOCX outline (headings) | python-docx 1.2.0 | Reopen took 19 ms (2026-10-14) | Selected (already a dependency) |
| PPTX outline (slide titles) | python-pptx 1.0.2 | 104 ms to build 11 slides (2026-10-14) | Selected (already a dependency) |
| Process containment | Windows Job Object via `ctypes` (kernel32). No new Python package. pywin32 was used only in the probe. | Probe used `win32job`. The `ctypes` path is **not yet measured**. Test T-R3. | Selected |
| UNO client | LibreOffice's bundled `python.exe` running `uri_office/lo_bridge.py` | Probe ran it without `-I`. **NOT VERIFIED:** whether it imports `uno` under `-I` (isolated mode). Spike S1. | Selected, subject to S1 |

**No new installs and no elevation.** O2 uses only what is on the PC. LibreOffice is located by its fixed path, never
by `PATH`. At service start the `soffice.bin` SHA-256 is compared with the pinned value in `uri_office/engines.json`. On
a mismatch the preview becomes unavailable and the status strip names the reason. An unpinned engine is never run.

Rejected for O2 (programme plan section 2.2 keeps the full comparison):
- per-call `soffice --convert-to`: 17 times slower;
- docx-preview: approximate HTML, not page-faithful;
- PyMuPDF base for Office files: text reflow only (measured negative result);
- Microsoft Office COM: no licence on this PC.

## 4. B1 workspace architecture

### 4.1 Layout

```
┌ rail ┬───────────── Office region (WorkspaceFocus.office) ─────────────────────────────┐
│      │ LEFT 260 px (180–360, collapsible to 56)│ CENTRE (flex, min 480) │ RIGHT 380 px (320–520) │
│ orb  │ Search                                  │ View header: file, mode│ URI                    │
│ ...  │ Home · Recent                           │  Home | Sheet (Univer) │  conversation (kept    │
│Office│ Goals: Write · Present · PDFs ·         │  | Page preview        │  across views)         │
│ ...  │        Data & Excel · Combine files     │  | Plan / progress     │  clarification chips   │
│      │ Files by kind (Documents, Spreadsheets, │  | Before / after      │  plan card (A2UI)      │
│      │   Presentations, PDFs)                  │ thumbnails / outline   │  findings, approvals   │
│      │ Workflows: running · done               │                        │  composer + PTT        │
│      ├─────────────────────────────────────────┴ status strip ──────────┴────────────────────────┤
└──────┴ step · progress · save state · engine state · findings count · last error + Retry       ┘
```

- **Goal groups** are built from the capability registry (`GET /capabilities`). A group shows only capabilities whose
  status is `available`. In O2 these are:
  - Write: none;
  - Present: none;
  - PDFs: "Make a PDF";
  - Data & Excel: Open workbook, New workbook from files;
  - Combine files: none.

  An empty group is hidden. **No dead buttons.** O3–O8 fill the groups by registering capabilities.
- **Files by kind** lists the Recent entries filtered by kind. There is no folder crawling. Opening a file always goes
  through the system picker, so a grant always exists.

### 4.2 Responsive behaviour

| Width of the Office region | Layout |
|---|---|
| ≥ 1280 px | Three panes at their saved widths |
| 1000–1279 px | Left pane collapses to a 56 px icon strip (goal icons, recent, workflows). It expands as an overlay on hover or click. |
| < 1000 px | The right pane becomes a side sheet over the centre, opened by an orb chip in the view header. The sheet opens by itself when a card needs the owner (clarification, plan, approval). A badge shows the count of waiting cards. A waiting card is never hidden without a badge. |
| < 720 px | The centre shows one view at a time with a back control. The status strip wraps to two lines. |

- Widths and collapse state are kept per user through the existing settings store.
- Keyboard:
  - Ctrl+K: focus the composer.
  - Ctrl+B: toggle the left pane.
  - Ctrl+J: toggle the URI pane.
  - Ctrl+Z / Ctrl+Y: undo and redo (sheets only, unchanged).
  - Esc: dismiss a hint.
  - Ctrl+S: propose a save (opens the approval card).
- All focus targets are reachable by Tab, and every icon button has a semantic label.

**Risk to check in spike S2:** whether the patched WebView2 host renders as a texture or as a native child window. A
native child window would draw over Flutter overlays (the side sheet at < 1000 px). If it is a child window, the
side-sheet layout for sheets uses a push layout instead of an overlay.

### 4.3 Flutter components

All live under `uri_ui/lib/living/office/`.

| File | New or edit | Role |
|---|---|---|
| `office_workspace.dart` | new | Three-pane shell, `ResizableSplit` (own widget, no new package), breakpoints |
| `office_nav_pane.dart` | new | Search, goals, files by kind, workflows |
| `office_home.dart` | new | Request box, goal chips from the registry, recent work, running workflows, first-run line |
| `page_preview.dart` | new | Page images (lazy, cached), thumbnail rail, outline, selection scope, "Rendered by LibreOffice" label |
| `office_companion_pane.dart` | new (extracted from `office_panel.dart:208-400`) | Same widgets for sheets; generalized target; plan, findings and approval cards through the existing A2UI hub |
| `office_conversation.dart` | new | One conversation for the Office region. Each turn is tagged with its target. It survives view switches for the app session. It is not written to disk. |
| `document_controller.dart` | new | Document session and preview state. Implements the same request-target interface as `OfficeController`. |
| `office_status_strip.dart` | new | Step, progress, save state, engine state, findings, last error with a recovery action |
| `office_panel.dart` | edit | The sheet view becomes the centre view for workbooks. Behaviour is unchanged. |
| `office_client.dart` | edit | New routes, binary PNG fetch |
| `office_controller.dart` | edit (minimal) | Implements the shared target interface. Excel logic is unchanged. |
| `../presentation/presentation_controller.dart` | edit | `OfficeView` enum, optional field on `ShowModeCommand`, phrases |
| `../screens/workspace_mode_view.dart` | edit | Remove the Documents rail item and `DocumentsRegion`. The `documents` focus maps to Office › Documents. |
| `../living_scope.dart` | edit | `activeOfficeTarget()` returns the target of the centre view (workbook or document) |
| `uri_ui/lib/office_o2_live_check.dart` | new | Live harness (section 12) |

### 4.4 Navigation by URI (refinement 9)

- `OfficeView { home, recent, documents, spreadsheets, presentations, pdfs, templates, workflows }` is added as an
  optional field of `ShowModeCommand`. The vocabulary stays closed. A command still cannot send text, approve, change
  a setting or dismiss a card (`presentation_controller.dart:20-25`).
- Local phrases: `uri office`, `uri office <view>`. `uri documents` now opens Office › Documents.
- The Office service may return `navigate: {view, file_id?}` in a response to the owner's own request. The Office
  pane applies it with `UiCommandOrigin.brain`, so it gets the existing cooldown, the history and Back. Navigation
  never opens a file without a grant, and never shows a file the owner has not opened.

### 4.5 Context across views (refinement 5)

The Office region keeps one `OfficeConversation`. Switching between a sheet, a document and Home keeps the visible
history. Each request is sent with:
- the owner's text;
- the active target (kind, id, selected page or slide);
- the last 6 owner turns, as text, inside an untrusted block.

Document content is never part of the conversation record. Sheet requests still go through `OfficeBrain.plan`
unchanged.

### 4.6 Onboarding and hints (refinement 6)

- **First Office visit:** a one-line hint under the request box:

  > Tell URI what you need, or open a file. URI shows a plan before it changes anything.

  It is shown until the first completed workflow or a dismissal. The dismissal is persisted.
- **First open of each kind** (PDF, document, presentation): one contextual hint in the companion that names only
  capabilities with status `available` for that kind. In O2, for example: "You can make a PDF of this document" or
  "Ask me to open another file".
- **"What can URI Office do?"** is a fixed help chip. The answer is built from the registry, with available and
  planned capabilities in separate lists. Nothing claims a planned capability works.

### 4.7 Progress, errors and recovery (refinement 7)

| Situation | What the owner sees | Recovery |
|---|---|---|
| Preview engine starting | Status strip: "Preparing preview engine…" with elapsed seconds. The page area shows a skeleton. | Automatic |
| Render timeout or crash | "Preview unavailable: the preview engine stopped." Pages already rendered stay. | Retry (restarts the engine once). "Open in default app" when an association exists. |
| Engine missing or hash mismatch | "Preview unavailable: the preview engine is not the approved version." | No automatic fix. The diagnostics line names the expected path and hash. |
| File changed on disk while open | "This file changed outside URI." | Reload |
| Protected or encrypted PDF or document | "This file is password-protected. URI cannot open it." | None in O2. Password entry is not offered. |
| Workflow step failed | The step is marked failed in the plan view, with the reason. | Retry step, or Discard workflow |
| Validation findings | A findings card lists errors and warnings with locations | Accept with warnings (one more click, logged), or Discard. Errors block approval. |
| Service restarted mid-workflow | On reopen the workflow shows "Interrupted at step N" | Resume (re-runs step N from its inputs after re-checking the input hashes), or Discard |

### 4.8 Visual language (refinement 4)

- Use only `uri_theme.dart` tokens: canvas `#0C0D0F`, surface `#17181B`, accent `#C8A25A`, Segoe UI.
- Use the existing `UriSpace`, `UriGlass`, `Eyebrow` and `StatusBadge` widgets. No new colour literal.
- The light theme mirrors the dark theme, as in the mockups.
- Page images keep their own white paper on a canvas well, so documents look like paper in both themes.

## 5. Service additions (`uri_office/`)

| File | New or edit | Responsibility |
|---|---|---|
| `capabilities.py` | new | A static registry. Each entry is a capability with its id, goal group, input kinds, intent, steps (each D, E or B), engines and status (`available` or `planned:<phase>`). It is a plain dict with no framework. `GET /capabilities` returns it. |
| `intent.py` | new | Stage 1, a deterministic phrase matcher: verbs and objects such as "convert / make a PDF", "open", "new workbook from", "show my PDFs". Stage 2, `OfficeBrain.classify` with a strict schema `{intent: <closed enum>, target_kind?, output_kind?, missing: [...]}`, only when stage 1 has no unique match. The result is `matched`, `clarify` (chips from the registry) or `planned` (honest "not yet"). |
| `brain.py` | edit | Add `classify(...)`: FAST tier, strict schema, untrusted block. `plan(...)` for sheets is unchanged. |
| `content.py` | new | `Block` and `SourceRef` dataclasses, plus outline readers for DOCX headings, PPTX titles and PDF TOC or page first lines. The O3–O5 io modules extend it. |
| `docs.py` | new | `DocSession`: grant, kind, input SHA-256, page count, outline, preview state, close. Read-only. |
| `sanitize.py` | new | Make the render copy. Refuse zip bombs (more than 500 MB uncompressed, ratio over 100, more than 10,000 entries). Refuse encrypted OOXML. Remove external relationships (`TargetMode="External"`, except hyperlinks, which are kept inert). Neutralize `INCLUDETEXT`, `INCLUDEPICTURE`, `LINK` and `DDE*` fields. Drop `altChunk` external targets and OLE links. Report each removal as a finding. Never change the original. |
| `render.py` | new | Engine manager. Checks the pin. Re-seeds the hardened profile under `<state>/lo-profile/` at every start. Starts the listener inside a Job Object (`ctypes`) with a random pipe name. Runs one conversion at a time in a queue. Timeouts: 60 s per conversion, 90 s for start-up. Restarts once after a crash. Idle shutdown after 10 minutes. Results are PDF files in the working folder. |
| `lo_bridge.py` | new | Runs in LibreOffice's `python.exe`. JSON lines on stdin and stdout: `{in, out, filter}` → `{ok, seconds, error}`. Accepts only paths under the service's working root, as passed at start. |
| `preview.py` | new | PDF to PNG pages with PyMuPDF at 110 dpi (on-screen) and 200 dpi (zoom). Cache under `<state>/previews/<sha256>/` with a 1 GB LRU cap. Thumbnails at 40 dpi. |
| `validate.py` | new | Shared checks and the findings model (section 8) |
| `workflows.py` | new | Workflow runner: `<state>/work/<id>/`, `workflow.json`, step states, resume, cancel, retention (7 days for abandoned runs, removal on discard or after approval) |
| `recent.py` | new | `<state>/recent.json`: path, kind, last opened, size. No content and no hash. Remove an entry, Clear all. Re-opening an entry asks the picker to confirm the file, so a new grant is made. A recent entry is not a grant. |
| `grants.py` | edit | `check_shape(raw, suffixes=(".xlsx",))`. Per-kind size caps: DOCX and PPTX 50 MB, PDF 100 MB and 2,000 pages. |
| `approvals.py` | edit | Target kind `output_files`. The card lists each output (name, size, pages, SHA-256 prefix, full destination) and "originals will not change". The hash binds the full list. |
| `service.py` | edit | Routes listed below. One binary response helper. Workflow resume scan at start. |
| `engines.json` | new | Pinned engine paths (relative to `%LOCALAPPDATA%\URI\engines\`) and SHA-256 values |

Routes (all bearer-guarded; `GET` for reads):

| Route | Method | Purpose |
|---|---|---|
| `/capabilities` | GET | Registry for the left pane, the help card and the hints |
| `/engines` | GET | Engine status (pinned, running, idle) for the status strip |
| `/open/document` | POST | `{path}`: grant, kind check, sanitized copy, outline, starts preview rendering |
| `/document/<id>` | GET | Session view (pages, outline, preview progress, findings) |
| `/document/<id>/page/<n>?dpi=110|200|40` | GET | PNG bytes |
| `/document/<id>/close` | POST | Close, release the grant |
| `/request` | POST | `{text, target, scope, history}` → intent result (matched, clarify or planned), or a plan |
| `/workflow/<id>` | GET | Status and steps |
| `/workflow/<id>/answer` | POST | Answer a clarification |
| `/workflow/<id>/cancel` | POST | Cancel |
| `/workflow/<id>/resume` | POST | Resume an interrupted run |
| `/workflows` | GET | Running and done lists (no content) |
| `/recent` | GET | Recent list |
| `/recent/remove`, `/recent/clear` | POST | Owner housekeeping |

The A2UI action `office.run_plan` and the existing `office.apply_change` / `office.reject_change` go through the
existing `/a2ui/action` route.

## 6. Intelligent automation design (O2 skeleton, reused by O3–O8)

### 6.1 Request lifecycle

1. **Request** from the composer, Home or a goal chip. A chip sends a fixed intent id and skips the matcher.
2. **Intent.**
   - Stage 1: the deterministic matcher.
   - Stage 2: Brain classification (closed enum), only when stage 1 cannot decide.
   - Stage 2 is never used to fill facts. It only names an intent and the missing inputs.
3. **Inputs.** Missing inputs become one clarification with chips: an open file, "Choose a file…", or a format. Roles
   (Reference, Check, Edit) are always chosen by the owner (M2-D10).
4. **Plan card (A2UI, `office.run_plan`).** It shows:
   - the steps, each marked Rule-based, Engine or URI-written;
   - the files read;
   - the outputs (names, count, kind);
   - "originals will not change".

   `plan_sha256` binds exactly what was shown. Single-step requests with no output (open, navigate) skip the card.
5. **Execute** in the working folder. Brain steps (O3+) return only validated operation JSON.
6. **Validate**, then repair. Repair is deterministic rules only, at most 2 passes. Remaining findings go to the owner.
7. **Preview** the outputs in the centre pane.
8. **Approve outputs.** An `output_files` card goes through `office.apply_change`. The owner picks the destination in a
   save dialog (SAVE_AS grant). The write never overwrites, is atomic, and is audited.
9. **Refine.** At most two follow-up chips taken from the registry (for example "Open the PDF", "Show folder").

### 6.2 Brain-use policy

| Step | O2 | Later |
|---|---|---|
| Intent | D first, then B (classification only) | same |
| Open, navigate, outline, preview, convert, validate, save | D or E only | same |
| Wording, summaries, slide outlines | none | B, with sourced facts only (O3–O7) |
| Clarification text | fixed strings from the registry | same |

Effect: O2's only Brain use is stage-2 classification. Everything else in O2 runs without the GPU.

### 6.3 Workflow record

`work/<id>/workflow.json` holds:
- the intent and capability id;
- the inputs (grant id, kind, SHA-256 before);
- the steps (kind D, E or B; engine and version; start; end; state; finding ids);
- the outputs (name, SHA-256, pages);
- approvals (surface id, `change_sha256`);
- errors and recovery.

It holds **no document text**. The live harness and qualification evidence read it.

## 7. Cross-application workflows (programme view; O2 builds the pipeline they share)

| Workflow | Readers → deterministic core → Brain → writer | Validator focus | Phase |
|---|---|---|---|
| Word → PDF | sanitize → LibreOffice export → none | page count, fonts embedded or substituted, blank pages | **O2** |
| PowerPoint → PDF | same | slide count, overflow | **O2** |
| Excel → Word letters | openpyxl → merge fields → optional wording → python-docx | no `«field»` left, per-item validation, row count = file count | O7 |
| Excel → report | openpyxl → tables and figures with source references → narrative from sourced facts → python-docx | every number traces to a cell | O7 |
| Excel → PowerPoint | openpyxl → native chart data → titles and takeaways → python-pptx | chart axis from zero (O5 finding), overflow | O7 |
| Word → presentation | python-docx heading tree → slide skeleton → condense and notes → python-pptx | overflow, minimum font size | O7 |
| PDF → Word | PyMuPDF (+ OCR) → blocks and tables → none → python-docx | text coverage compared with the source | O7 (O4 readers) |
| PDF → Excel | PyMuPDF `find_tables` → cell mapping → none → M2 new-workbook path | cell count and header match | O4 |
| PDF → presentation | PyMuPDF → section split → outline → python-pptx | sourced bullets | O7 |
| Several documents → consolidated report | all readers → retrieval with citations → summary with citations → python-docx | every claim cites a block | O7 |

## 8. Shared validation architecture

```
intent → workflow → engine → generate/modify → render → VALIDATE → repair (deterministic, ≤2) → preview → approval → save
                                                  │
                         findings model ──────────┴─ structural · render · visual · integrity · fidelity (O3+)
```

**Finding:** `{id, check, severity: error | warning | info, location: {file, page | slide | block}, message, repair:
{kind: rule | brain | owner, rule_id?}}`.
- Errors block approval.
- Warnings need one explicit "Accept with warnings" click, which is audited.

| Check | Kind | O2 | Notes |
|---|---|---|---|
| Archive integrity (zip CRC, content types, size and ratio caps) | structural | yes | Before any parsing |
| Opens in its engine (python-docx, python-pptx, PyMuPDF) | structural | yes | |
| Macros present (`vbaProject.bin`, `.docm`, `.pptm`) | structural | yes | Inputs are preview-only. Outputs must not contain macros. |
| External references remaining in an output | structural | yes | Must be zero |
| Placeholder tokens (`«…»`, `{{…}}`, `[NAME]`) | structural | yes, for outputs | Rule set grows in O3 and O7 |
| Render completes in time | render | yes | |
| Page or slide count matches the expectation (source count for conversion) | render | yes | |
| Blank pages | visual | yes | Pixel coverage under 0.2 % |
| Text outside the page box | visual | yes | PyMuPDF span boxes against the page rectangle |
| Font substitution | visual | yes | Fonts named in the source compared with fonts in the PDF. A warning names the substitute. |
| Minimum font size (8 pt documents, 10 pt slides) | visual | yes | |
| Overlapping text boxes on slides | visual | O5 | |
| Chart axis not starting at zero | visual | O5 | Finding from the 2026-10-15 probe |
| Unchanged pages identical after an edit (pixel diff) | fidelity | O3 | |
| Unrelated XML parts byte-identical after an edit | fidelity | O3 | M1 rule, generalized |
| Every fact traces to a source block | integrity | O3/O7 | `unsourced` marker |
| Source files unchanged (hash before and after) | integrity | yes | On every run |

**Repair interface:** `repair(findings) -> (changes, remaining)`. Rules are registered per check. O2 registers none,
because conversion must not change content. The interface and its tests exist so that O3 and O5 add rules without
changing the pipeline.

## 9. Security

1. **Files.**
   - Picker grants only. Recent entries are not grants.
   - Same path rules as M1, plus the new suffixes and size caps.
   - Originals are never written in O2.
2. **LibreOffice.**
   - Pinned hash.
   - Hardened, re-seeded private profile under the ACL-restricted state folder.
   - Macros disabled.
   - Network blocked by profile settings, with external relationships also removed from the render copy.
   - Named pipe (no TCP port), with a random name per launch.
   - Job Object kill.
   - Only paths under the working root.
   - The canary set (section 12, F-items) runs in every qualification.
3. **UNC and NTLM.** A link target such as `\\host\share` could make Windows send credentials. The sanitizer removes
   UNC targets, and the canary set includes one (an SMB canary on `127.0.0.1`).
4. **PDF.** PyMuPDF renders only. JavaScript, launch actions and embedded files are never run or extracted.
5. **Brain.**
   - Stage-2 classification sees the owner's request, file names, and the outline titles of the active file.
   - The file names and outline titles go inside an untrusted block.
   - The output is a closed enum checked against the schema. Anything else becomes a clarification.
6. **No cloud.** O2 adds no Google, upload or share path. The existing Google Sheets path is unchanged.
7. **No learning.**
   - Correction history is not extended in O2.
   - `workflow.json`, `recent.json` and the logs hold no document content.
   - Nothing is written to memory or Graphify.
8. **Local only.** The service stays bound to `127.0.0.1`.
9. **Tests.** Every new route has a test for:
   - missing token (401);
   - wrong Host or Origin;
   - bad id;
   - a path outside the grants.

## 10. UI/UX acceptance criteria

| # | Criterion | Automated test | Live check |
|---|---|---|---|
| U1 | Three panes at ≥ 1280 px. Left and right panes resize between their limits and collapse. Sizes persist after a restart. | widget tests at 1440 and 1280 px | E1 |
| U2 | Responsive: icon strip at 1000–1279 px, side sheet under 1000 px, single view under 720 px. No overflow errors at 1.3 text scale. | widget tests at 1100, 900 and 700 px | E2 |
| U3 | With a workbook open, the Excel view and companion behave as before. All M1 and M2 Flutter tests pass unchanged. | existing suites | L1 |
| U4 | Goal groups show only `available` capabilities. Empty groups are hidden. No control leads to "not implemented". | widget test with the registry fixture | E3 |
| U5 | Conversation history persists across Home, sheet, document and back. Each turn shows its target label. | widget test | E4 |
| U6 | First-visit hint and first-of-kind hints appear once. A dismissal persists. The help chip lists available and planned capabilities separately. | widget tests | E5 |
| U7 | Every state in section 4.7 has the specified message and recovery action. | widget tests with fake errors | F-items |
| U8 | At most one hint visible. No hint while a workflow runs. A hint can always be dismissed. | widget test | E5 |
| U9 | `uri office`, `uri office pdfs` and the other view phrases, plus service `navigate`, move the view. History has Back. The cooldown holds. | unit tests in `presentation_controller_test.dart` | E6 |
| U10 | No new colour literal. Only theme tokens. | lint grep in CI (`Color(0x` in new files = fail) | K-visual |
| U11 | Keyboard: all shortcuts in 4.2 work. The Tab order covers every control. Icon buttons have semantic labels. | widget tests | E7 |
| U12 | Page preview: first page visible ≤ 2.0 s for a warm 20-page DOCX, ≤ 0.5 s for a PDF page. Scrolling 50 pages keeps 95 % of frames under 16 ms (existing perf logger). | timing test with a fake engine; perf log | H-items |
| U13 | A waiting card (clarification, plan or approval) is never hidden without a visible badge at any width. | widget test at 900 px | E2 |
| U14 | The page preview is labelled "Preview rendered by LibreOffice". | widget test | K |
| U15 | The `DocumentsRegion` simulated tiles are gone. `uri documents` opens Office › Documents. | widget test | E6 |

## 11. O2 functional acceptance criteria

| # | Criterion | Test |
|---|---|---|
| AC-O2-1 | Open DOCX, PPTX and PDF read-only through a picker grant. Pages, outline and thumbnails appear. The original is byte-identical afterwards. | `tests/office_u2/test_open_documents.py` + G1 |
| AC-O2-2 | DOCX and PPTX previews match a reference render (fixtures rendered once, hashes and PNGs in `tests/office_u2/fixtures/`): page count equal, and per-page pixel difference under 0.5 %. | `test_render_fidelity.py` (needs the engine; marked `engine`) |
| AC-O2-3 | Listener mode: warm DOCX conversion ≤ 2 s median over 5 runs for the 20-page fixture. Start-up ≤ 30 s. Idle shutdown after the timeout leaves no process. | `test_render_engine.py` + H1 |
| AC-O2-4 | Hardened profile and sanitizer: every canary type (external image, `INCLUDEPICTURE`, `INCLUDETEXT`, OLE link, `altChunk`, PPTX linked media, UNC target) causes 0 network or SMB connections. Each removal is reported as a finding. | `test_render_isolation.py` + F1 |
| AC-O2-5 | Job Object: killing the service, a conversion timeout, or `soffice.bin` crashing leaves no orphan LibreOffice process within 5 s. The next request restarts the engine once. | `test_render_engine.py` + F2 |
| AC-O2-6 | Engine pin mismatch or missing engine: preview unavailable with the stated message. The engine is never run. | `test_engine_pin.py` |
| AC-O2-7 | Convert to PDF works end to end. The pipeline runs plan card → execute → validate → preview → `output_files` approval → write, with no overwrite. `workflow.json` has every step. Sources are unchanged. | `test_workflow_convert.py` + D1 |
| AC-O2-8 | Validation blocks approval on any error finding. Warnings need explicit acceptance, which is audited. | `test_validate.py` |
| AC-O2-9 | Resume: killing the service during the render step, then restarting, shows "Interrupted at step N". Resume re-runs the step after re-checking the input hashes. A changed input stops the workflow with a finding. | `test_workflow_resume.py` + F3 |
| AC-O2-10 | Intent: the 40-request O2 corpus (`tests/office_u2/intent_corpus.json`) gives the expected result (matched, clarify or planned) on stage 1 alone for the deterministic subset. The Brain subset is checked live. The Brain is never called when stage 1 matches. | `test_intent.py` + C1 (Brain) |
| AC-O2-11 | Planned capabilities answer "not available yet" with the phase. They never start a workflow. | `test_intent.py` |
| AC-O2-12 | A2UI: `office.run_plan` refuses a stale or changed plan hash and a replay. `output_files` approvals refuse a changed output and a destination that already exists. | `test_plan_card.py`, `test_output_approval.py` |
| AC-O2-13 | Security: every new route refuses a missing token, a bad Host or Origin, and an unknown id. Paths outside grants are refused. Zip bomb, encrypted and oversize files are refused with a finding. | `test_service_u2.py`, `test_sanitize.py` |
| AC-O2-14 | No content in `workflow.json`, `recent.json` or the logs: the fixture text "SENTINEL-CONTENT-7f3a" never appears in the state folder outside the work and preview folders. | `test_no_content_leak.py` |
| AC-O2-15 | Excel regression: `tests/office`, `tests/a2ui`, `uri_ui/test/office` and the living shell tests pass unchanged. `ws_frozen_check` shows no protected path changed. | full suites + L1 |
| AC-O2-16 | No GPU use by the Office engines: the GPU process census during previews and conversion shows no LibreOffice or Office-service GPU memory. | H2 |

## 12. Live qualification matrix (O2)

- **Environment:** the owner's Windows 11 PC (24 logical CPUs, 23.9 GiB RAM).
- **Software:** the real URI living UI (`main_living.dart` build) and the real Office service, with pinned LibreOffice
  and real fixtures.
- **Brain:** Runtime v1 only in the O2 GPU window (OD-U6).
- **Driver:** the `office_o2_live_check.dart` harness, plus manual steps.
- **Evidence per item:** commit, inputs, outputs, renders, timings, census and verdict (only `COMPLETED_WITH_RESULT`
  counts).

Column key:
- **Br**: needs the Brain (GPU window).
- **Ow**: needs the owner present.
- **Now**: what can be run while the owner is away (until about 2026-10-23).

| Id | Owner item / category | O2 check | Br | Ow | Now |
|---|---|---|---|---|---|
| C1 | 1 Intent discovery / C | 40-request corpus through the real UI. The deterministic subset runs without the Brain. The ambiguous subset uses the Brain. Expected result recorded beforehand. | partly | no | Deterministic subset runnable. Brain subset **BLOCKED** (GPU window). |
| A1 | 2 Creation and editing / A | **Not O2** (O3/O5). O2 checks open and preview correctness only. | no | no | runnable |
| B1 | 3 Formatting fidelity / B | AC-O2-2 on the J fixtures: page count and pixel difference against the reference render | no | no | runnable |
| K1 | 4 Rendering and previews / K | Rasterize every page. Automated visual checks (section 8). The reviewer inspects a sample of 10 pages and slides, with screenshots. | no | no | runnable |
| D1 | 5 Save, reopen, modify / D | Convert to PDF. Save through the approval card. Reopen the PDF in Office. Its preview matches. No overwrite of an existing name. | no | no | runnable |
| I1 | 6 Cross-application / I | Word → PDF and PowerPoint → PDF only. The rest is O7. | no | no | runnable |
| D2 | 7 Batch generation / D | **Not O2** (O7) | — | — | N/A |
| O1 | 8 Contextual suggestions | **Not O2** (O8). O2 checks only the one-hint rule (U8). | no | no | runnable |
| E1–E7 | 9 First-time use and usability / E | Scripted first-visit path. Time to first preview. Hint behaviour. Responsive widths. Keyboard. Then an **owner think-aloud session** recording confusion points and time to the first output. Repairs are retested. | no | **yes** | Scripted part runnable. Owner session **BLOCKED** (owner away). |
| F1–F6 | 10 Errors and recovery / F | F1 canaries; F2 engine crash and timeout; F3 service kill mid-workflow then resume; F4 corrupt, encrypted, oversize and zip-bomb files; F5 disk nearly full (simulated quota on a test folder); F6 file changed on disk while open | no | no | runnable |
| G1 | 11 Original protection / G | Source hashes before and after every live item. No stray files outside `work/`, `previews/` and the chosen destination. | no | no | runnable |
| H1–H3 | 12 Performance / H | H1 preview and convert latencies (U12, AC-O2-3); H2 CPU, RSS (service, LibreOffice, UI) and GPU census; H3 Brain tok/s with the Office region open (sheet and document) against the Excel baseline (AC11) | H3 only | no | H1 and H2 runnable. H3 **BLOCKED** (GPU window). |
| L1–L2 | 13 Repeats and regression / L | L1 Excel live journey (open, instruct, accept, save) with the Brain; L2 five repeats of D1, F1 and F3 with identical outcomes | L1 | no | L2 runnable. L1 **BLOCKED** (GPU window). |
| L3 | 14 Existing Excel functionality | L1, plus the full automated suites (AC-O2-15) | L1 | no | Suites runnable. L1 **BLOCKED**. |
| J1 | 15 Realistic correspondence / J | Fixtures, all synthetic (OD-U7):<ul><li>official letter with letterhead;</li><li>office order with a 41-row table;</li><li>notice and corrigendum pair;</li><li>memorandum;</li><li>minutes;</li><li>**bilingual English and Hindi letter** (complex script);</li><li>20-page report;</li><li>11-slide deck with a chart;</li><li>scanned PDF;</li><li>60-page tender PDF.</li></ul>Each is opened, previewed and (where it applies) converted. | no | no | runnable |
| K2 | 16 Visual inspection / K | The reviewer inspects the converted PDFs against the source previews. The owner sees the same set in the owner check. | no | owner check | Reviewer part runnable. Owner part **BLOCKED**. |
| R1 | 17 Corrections and refinements | **Not O2** (O3+). O2 checks the follow-up chips after conversion (two at most, from the registry). | no | no | runnable |

**Freeze rule (unchanged).** O2 is not accepted, frozen or integrated until all of these hold:
- every applicable row is PASS at the exact candidate commit;
- the Brain rows have run in an owner-approved GPU window;
- the owner check (E, K2) has passed;
- an independent reviewer has accepted the phase.

Rows that cannot run are reported BLOCKED, never PASS.

## 13. Phases after O2 (outline; each gets its own plan and review)

| Phase | Scope | Depends on | Key acceptance criteria | Brain use |
|---|---|---|---|---|
| **O3 Word** | Templates (letter, office order, notice, memo, minutes, report) from a style-locked base. NL edits as block-addressed change cards. Headers, footers, page numbers, numbering. Format-correction rules (D). Proofreading (B). Compare and tracked-change draft (`w:ins` / `w:del`). | O2 frozen | Each template renders without findings. Edits keep unrelated parts byte-identical and unchanged pages pixel-identical. No unsourced fact is auto-filled. Originals are written only with the Edit role plus approval. | wording, proofreading, edit ops (validated) |
| **O4 PDF** | Extraction with OCR fallback (Tesseract), page-cited Q&A, tables → Excel (M2 path), merge, split, rotate and reorder (pypdf), highlights and notes (PyMuPDF), AcroForm assisted fill, notice and corrigendum linking | O2 (parallel with O3) | Citations resolve to the right page. The original PDF is byte-identical. The scanned fixture is OCR'd above a set character accuracy. "Not found in the files" when nothing is cited. | answers from numbered blocks only |
| **O5 PowerPoint** | Slides from an outline, document or data. Master-based themes. Native charts and tables. Notes. Overcrowding, minimum-size, overlap and axis-from-zero rules. Reorganize, shorten, expand. | O2 (parallel) | Zero overflow in rendered slides. Charts open in LibreOffice. Readability rules catch the seeded defects. | outlines, condensing, notes |
| O6 Google Docs/Slides | Copy, upload-convert, export, read-only sharing view | O3, O5, OD-U4 | No upload without a card naming the destination | none |
| O7 Cross-application | Section 7 rows | O3–O5 | Every output fact traces to a source. A 40-letter batch is validated per item. | sourced wording |
| O8 Recommendations | Deterministic detectors. One suggestion at a time. Mute per file. Saved recipes with consent. | O7 | Precision on the fixture set. No suggestion while running. | optional wording |
| O9 Whole-programme qualification | Owner UX study, repeats, performance against the Excel baseline, independent whole-diff audit | all | Programme section 10 | — |

## 14. Dependencies, workstreams and order

**Before implementation:**
- owner approval of this plan (G0);
- OD-U3 (PyMuPDF AGPL acknowledgement) ruled;
- OD-U7 confirmed for O2: synthetic fixtures only.

**Spikes** (day 1 of implementation, recorded before code depends on them):

| Spike | Question | If it fails |
|---|---|---|
| S1 | Does LibreOffice's `python.exe -I lo_bridge.py` import `uno` and convert? | Run without `-I`, with `PYTHONPATH` cleared and the bridge copied into a private ACL-restricted folder. Record the deviation. |
| S2 | Does the WebView2 host draw as a texture or as a child window? | Push layout instead of overlay for sheets under 1000 px |
| S3 | `ctypes` Job Object: same kill behaviour as the probe? | Fall back to a psutil tree kill (documented weaker guarantee) |
| S4 | Listener start-up with a re-seeded persistent profile (not fresh) | Keep the fresh profile and accept about 10 s start-up |
| S5 | Pixel comparison of per-call and listener output on the fixtures | Investigate before AC-O2-2 references are recorded |

**Workstreams** (one branch `phase/uri-office-u-2` from `5b958da0`, one worktree each, merged in order A → B → C):

| Workstream | Owns | Starts after |
|---|---|---|
| WS-A engine and pipeline (Python) | `capabilities.py`, `intent.py`, `content.py`, `docs.py`, `sanitize.py`, `render.py`, `lo_bridge.py`, `preview.py`, `validate.py`, `workflows.py`, `recent.py`, edits to `grants.py`, `approvals.py`, `service.py`, `brain.py`, `engines.json`, `uri_a2ui/actions.py`, `tests/office_u2/` | Spikes S1, S3, S4, S5 |
| WS-B workspace UI (Flutter) | all `uri_ui/lib/living/office/*` listed in 4.3, `presentation_controller.dart`, `workspace_mode_view.dart`, `living_scope.dart`, `a2ui_contract.dart` mirror, `uri_ui/test/office_u2/` | Route contract frozen (`docs/office/unified/O2_API_CONTRACT.md`, written first in WS-A). Spike S2. Built against a fake client until WS-A merges. |
| WS-C qualification tooling | J fixtures generator, canary set, `office_o2_live_check.dart`, census and perf scripts, evidence layout | Contract frozen |

Rules:
- One writer per file.
- Live Brain runs are serialized on the GPU lease.
- `uri_a2ui/actions.py` and its Dart mirror change once, in WS-A, together with their parity test.

**After O2:** O3, O4 and O5 plan in parallel and implement in parallel. Each owns its io module and registers
capabilities through one additive entry each, merged in the order O3 → O4 → O5.

## 15. Owner approval gates

| Gate | What it authorizes | State |
|---|---|---|
| G0 | This plan (after review and repair) | **Pending: this report** |
| G1 | Start O2 implementation on `phase/uri-office-u-2` | Not granted |
| OD-U3 | PyMuPDF AGPL acknowledgement | Open (needed before G1) |
| OD-U7 | Synthetic fixtures for O2 | Open (recommended yes) |
| G2 | Any protected-path change | None planned |
| G3 | O2 GPU window (C1 Brain subset, H3, L1) | Per OD-U6, on the owner's return |
| G4 | Owner live UX check (E, K2) | On the owner's return |
| G5 | Independent acceptance of O2 | After G3 and G4 evidence |
| G6 | Integration (recommended together with O3) | Owner only |
| G7 | Production deployment | Separately authorized; not part of this programme step |

## 16. Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | LibreOffice idle RSS of about 390 MB while the listener is up, on a PC where the Brain needs about 15.3 GB VRAM and system RAM is 23.9 GiB | Medium | Start on demand. 10-minute idle shutdown. H2 measures the total. LibreOffice uses no GPU (AC-O2-16). |
| R2 | LibreOffice layout differs from Microsoft Word for complex documents. The owner compares with printed Word output. | Medium | The preview label names LibreOffice. The J set includes the owner's real document types in the owner check (OD-U7). Font-substitution findings. |
| R3 | Complex scripts (Hindi and others) render wrongly or substitute fonts | Medium | Bilingual J fixture. Font-substitution check. Nirmala UI is present on Windows; to be confirmed in J1. |
| R4 | Network fetch by LibreOffice (proved with the default profile) | High → Low | Hardened profile plus sanitizer plus the canary set every run (AC-O2-4) |
| R5 | WebView2 child-window airspace breaks overlays | Medium | Spike S2. Push-layout fallback. |
| R6 | The `uno` bridge cannot run isolated (`-I`) | Low | Spike S1 fallback |
| R7 | Stacking on an unintegrated Office line (W-7) and the canonical frozen checker exiting 1 (W-8) | High (integration) | Unchanged owner items. O2 stays rebase-ready and small. |
| R8 | Brain-dependent rows stay BLOCKED until the GPU window | Certain until the owner returns | Most of O2 is Brain-free by design. The rows are reported BLOCKED. |
| R9 | Scope creep into editing within O2 | Medium | Section 2.2. The registry only exposes `available` capabilities. |
| R10 | Preview cache holds rendered images of sensitive documents | Medium | ACL-restricted state folder. 1 GB LRU. "Clear previews" in Office settings. Previews are deleted when a recent entry is removed. |
| R11 | Same-user processes could drive the UNO pipe | Low | Random pipe name. Same-user processes already hold the user's rights. Documented. |
| R12 | A fresh worktree lacks the Univer bundle, so `test_page` fails | Low | WS-C setup stages the hash-verified bundle or records the skip. Found on 2026-10-15. |

## 17. Unverified items and their effect

| Item | Effect |
|---|---|
| AC11 and H3 (Brain speed with Office open) | Blocks O2 acceptance until the GPU window. Does not block G0 or G1. |
| `uno` under `-I` (S1); `ctypes` job (S3); persistent profile (S4); per-call and listener pixel parity (S5); WebView2 airspace (S2) | Each is resolved on the first implementation day. Each has a stated fallback. |
| Which hardened setting stopped the fetch | None: all settings are kept and the canary runs every time |
| Calibri and Nirmala UI rendering in LibreOffice for real owner documents | Covered by J1 and the owner check. Could change R2 and R3. |
| `drive.file` with the Docs and Slides APIs | O6 only |

## 18. Self-review against section 0

Rev 1 self-review was done before the independent review:

| Criterion | Result |
|---|---|
| Q1 | Met. Re-run today. File and line cited. |
| Q2 | Met. The probe's measurements and gaps are named in sections 3 and 17. |
| Q3 | Met. Refinements 1–10 map to U3, U1, U2, U10, U5, U6, U7, U8, U9 and Q4. |
| Q4 | Met. One service. A2UI grows by 2 actions only, and `office.apply_change` is reused for outputs. No second assistant. |
| Q5 | Met. The section 4.3 and 5 file lists contain no `PROTECTED` path. `uri_a2ui` and `presentation_controller.dart` are not protected; they are integrated code, and the edits are additive. |
| Q6 | Met. Sections 10 and 11. |
| Q7 | Met. Section 12 covers items 1–17 and categories A–L. N/A and BLOCKED are marked. |
| Q8 | Met. Sections 9 and 15. |
| Q9 | Met. Section 13. |
| Q10 | Met. Sections 16 and 17. |
| Q11 | Section 19, after the review. |

Repairs made during self-review:
1. Approval reuse: an `office.approve_output` action was first considered. It was replaced by an `output_files` target
   on the existing `office.apply_change`, because adding it would have duplicated A2UI.
2. "Recent" was first treated as a re-open grant. That was corrected: a recent entry is not a grant, and the picker
   confirms the file again.
3. The integration recommendation was added (O2 together with O3), because O2 alone gives the owner read-only
   documents.
4. The UNC/NTLM canary was added. The 2026-10-15 probe covered only HTTP.

## 19. Independent review

Recorded in `02_O2_INDEPENDENT_REVIEW.md` and summarized here after the review.
