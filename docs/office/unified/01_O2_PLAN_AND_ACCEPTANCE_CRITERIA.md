# URI Office Unified: O2 plan and acceptance criteria (frozen-blueprint candidate, rev 4 = rev 3.1 + amendment A1)

Date: 2026-10-15. Milestone `URI-OFFICE-U`, phase **O2: unified workspace, engine layer and validation pipeline**.
Planning branch `phase/uri-office-unified-plan` (base `5b958da0`, local only). Programme plan:
`00_DISCOVERY_RESEARCH_AND_ROADMAP.md`. Status: **CANDIDATE rev 3 (after independent review rounds 1 and 2, both REVISE, and repair), NOT FROZEN, NOT AUTHORIZED FOR IMPLEMENTATION.**

Owner authorization in force (chat, 2026-10-15):
- OD-U5 is settled: B1 with B2 goal grouping.
- Planning, acceptance criteria, live-test matrices and independent review are authorized.
- O2 implementation, frozen-system changes and integration are **not** authorized.

> **Amendment A1 (2026-10-15) applies.** See `03_O2_AMENDMENT_A1_PDF_PRINT_DEVICES.md`. It changes the following:
> - PDF scope is reduced: no editing, annotation, assembly or forms.
> - **PyMuPDF is removed** and replaced by Windows.Data.Pdf, pypdf and Tesseract (no install).
> - Save as PDF covers Excel as well.
> - Printing and device discovery move to a separate phase, **O2P**.
> - New live rows: P-1 to P-6 for O2, and PR-1 to PR-12 for O2P.
>
> Where A1 disagrees with this document, A1 wins. Sections A1 changes: §1.2 (Core PDF row), §2.1 items 2 and 6, §2.2, §3 (PyMuPDF rows), §7 (PDF reader rows),
> §4.1, §4.3, §5 (`preview.py` / `raster_worker.py`), §8, §9.4, §11 AC-O2-20, §13 (O4), §14 (S9, S10, S11), §15 (OD-U3), §16 (R13) and §17 (pin row).
> The text below is kept unchanged for history.

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
| Session table | `service.py:74-131` (`Office`, `_session`, `open_local`) | A document session sits beside the workbook session. Workbook behaviour is unchanged; section 5.1 lists the mechanical edits. |
| Picker grants and path rules | `uri_office/grants.py` (`.xlsx` only, `grants.py:84`) | Add per-kind suffixes `.docx .pptx .pdf` through a parameter. The `.xlsx` default and its messages stay, so the existing tests stay green. |
| Hash-bound approvals and audit chain | `uri_office/approvals.py` (`propose`, target kinds `local`, `google`, `google_upload`, `new_file`) | Reuse the same table, hash binding, audit chain and the `office.apply_change` / `office.reject_change` actions. **The approval path is workbook-shaped today** (review F1): `propose` needs `edits`/`struct_ops`, `surface.workbook_id` is NOT NULL, `Office._apply` starts with a workbook session lookup, and `Approvals.action` reads only `change_sha256`. Section 5.1 specifies the generalization. It extends the one existing path; it is not a second path. |
| A2UI action registry | `uri_a2ui/actions.py:30-31`, Dart mirror `uri_ui/lib/living/a2ui/a2ui_contract.dart:117-119` | Add `office.run_plan` (confirms, `plan_sha256`) and `office.discard_plan`. This is the only A2UI growth. |
| Brain client | `uri_office/brain.py` via `uri_operational_intelligence.brain_client` (FAST tier, strict schema, untrusted block) | Add one schema: Office intent classification. `OfficeBrain.plan` for sheets is unchanged. |
| Untrusted-data wrapper | `uri_office/untrusted.py` | File names, outlines and request history in Brain prompts. |
| Companion routing | `LivingServices.activeOfficeTarget` (`living_scope.dart:159`), `office_panel.dart:208-400` | The companion pane is extracted into its own widget, without behaviour change for sheets. The target is generalized to documents. |
| UI-state controller | `UiPresentationController`, `ShowModeCommand`, `WorkspaceFocus.office` (`presentation_controller.dart:26-160`) | Add an optional `OfficeView` to `ShowModeCommand` and phrases such as `uri office pdfs`. Same cooldown. History and Back are extended for Office views (section 4.4). |
| Rail and regions | `workspace_mode_view.dart:103-105,158` | The rail "Documents" item and the simulated `DocumentsRegion` (`:740`, `work_items.dart:166` `isSimulated => true`) are removed. `WorkspaceFocus.documents` stays as an alias that opens Office › Documents. **Tests retired or rewritten** (review F2), because they test the simulated region: `living_shell_test.dart:235-275` (A4 template-to-approval flow on the simulated Documents region) and `:292` (`START NEW WORK`, `RECENT DOCUMENTS` labels). `presentation_controller_test.dart:76-82` is kept: its expected focus stays `documents`, now rendered as Office › Documents. The O2 test report lists each change with its reason. |
| Live UI harness pattern | `uri_ui/lib/office_live_check.dart`, `office_m2_live_check.dart` | New `office_o2_live_check.dart` on the same pattern. |
| Core PDF and OCR | `uri_core/services/pdf_reader.py` | **Not used in O2.** PDF preview uses PyMuPDF directly. OCR starts in O4. Core stays untouched. |

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
| DOCX/PPTX page images and DOCX/PPTX→PDF | LibreOffice 26.8.1.1, user-folder extract, `soffice.bin` SHA-256 `cb08cffd…2fa1` | `evidence/lo_qualify_20261015/`: persistent listener warm DOCX **0.36 s**, PPTX **0.42–0.53 s**, start-up about 10.6 s (derived: wall total 12.6 s minus the five conversions; not a JSON field), idle RSS **390 MB**. Measured on a **1-page** DOCX and an 11-slide PPTX only. Per-call mode takes 6–18 s. Fidelity checked on 2 fixtures. Job Object close leaves 0 processes. | **Selected, in listener mode.** Qualified as a dependency only after the O2 failure tests (F-items) pass. |
| Network isolation of LibreOffice | Hardened private profile (macros off, `BlockUntrustedRefererLinks`, proxy to `127.0.0.1:9`) **plus** removing external relationships from the copy that is rendered | The default profile **fetched** the canary. The hardened profile made 0 fetches, in both modes. | Required. Canary in every qualification run. |
| PDF page images, outline, text layer for the selection scope | PyMuPDF 1.28.2 | 60 ms per page at 150 dpi in the committed `engine_probe_result.json`. The programme plan's 42 ms came from an uncommitted run (corrected, review F12). | Selected. Needs **OD-U3** (AGPL acknowledgement) before implementation starts. |
| DOCX outline (headings) | python-docx 1.2.0 | Reopen took 19 ms (2026-10-14) | Selected (already a dependency) |
| PPTX outline (slide titles) | python-pptx 1.0.2 | 84 ms to build 11 slides in the committed JSON (the programme plan said 104 ms; corrected) | Selected (already a dependency) |
| Process containment | Windows Job Object via `ctypes` (kernel32). No new Python package. pywin32 was used only in the probe. | Probe used `win32job`. The `ctypes` path is **not yet measured**. Test T-R3. | Selected |
| UNO client | LibreOffice's bundled `python.exe` running `uri_office/lo_bridge.py` | Probe ran it without `-I`. **NOT VERIFIED:** whether it imports `uno` under `-I` (isolated mode). Spike S1. | Selected, subject to S1 |

**No new installs and no elevation.** O2 uses only what is on the PC. LibreOffice is located by its fixed path, never
by `PATH`. **Engine integrity (review F11):** `uri_office/engines.json` holds a full-tree manifest (the SHA-256 of every file
in the extract, recorded once from the hash-verified MSI administrative extract) and the expected Authenticode signer of
the signed binaries. The full manifest is checked at service start. The executables, the DLLs and the bundled
`python.exe` are re-checked at **every engine launch** (the bundled Python's `.py` library files and `share/`
configuration only at service start), including a relaunch after idle shutdown. Spike S6 measures the
cost. On any mismatch the preview becomes unavailable and the status strip names the reason. An unverified engine is
never run.

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
  - Ctrl+Shift+B: toggle the left pane (Ctrl+B is bold in Univer; review F18).
  - Ctrl+Shift+J: toggle the URI pane.
  - While the WebView2 sheet has keyboard focus, keys go to Univer and Flutter shortcuts do not fire. Esc returns focus to Flutter.
  - Ctrl+Z / Ctrl+Y: undo and redo (sheets only, unchanged).
  - Esc: dismiss a hint.
  - Ctrl+S: propose a save (opens the approval card).
- All focus targets are reachable by Tab, and every icon button has a semantic label.

**WebView2 composition (review F24):** the vendored plugin renders through `TextureRegistrar`
(`webview_bridge.cc:197-213`), not as a native child window, so Flutter overlays draw above it. Spike S2 only confirms
this live.

**Sheet lifecycle across view switches (review F13):** while a workbook is open, its sheet view stays mounted offstage
when the centre switches to Home or a document. WebView2 is not disposed, Univer is not restarted, and the draft and
undo stack are kept. On a switch away, the WebView2 controller is set invisible and keyboard focus moves to Flutter,
so no keystroke can reach the hidden sheet (review N3). Closing the workbook disposes it. H2 measures memory, CPU and
GPU of the hidden WebView2. Acceptance: AC-O2-17 and AC-O2-21.

### 4.3 Flutter components

All live under `uri_ui/lib/living/office/`.

| File | New or edit | Role |
|---|---|---|
| `office_workspace.dart` | new | Three-pane shell, `ResizableSplit` (own widget, no new package), breakpoints |
| `office_nav_pane.dart` | new | Search, goals, files by kind, workflows |
| `office_home.dart` | new | Request box, goal chips from the registry, recent work, running workflows, first-run line |
| `page_preview.dart` | new | Page images (lazy, cached), thumbnail rail, outline, selection scope, "Rendered by LibreOffice" label |
| `office_companion_pane.dart` | new (extracted from `office_panel.dart:208-400`) | Same widgets for sheets; generalized target; plan, findings and approval cards through the existing A2UI hub |
| `office_conversation.dart` | new | One conversation store for the Office region. **It absorbs the existing per-workbook `OfficeKeep.conversation`** (`office_bridge.dart:133-140`, review F13), so there is one store, not two. Each turn is tagged with its target. It survives view switches for the app session. It is not written to disk. |
| `document_controller.dart` | new | Document session and preview state. Implements the same request-target interface as `OfficeController`. |
| `office_status_strip.dart` | new | Step, progress, save state, engine state, findings, last error with a recovery action |
| `office_panel.dart` | edit | The sheet view becomes the centre view for workbooks. Behaviour is unchanged, except the offstage, invisible and unfocused lifecycle in section 4.2. |
| `office_client.dart` | edit | New routes, binary PNG fetch |
| `office_controller.dart` | edit (minimal) | Implements the shared target interface. Excel logic is unchanged. |
| `../presentation/presentation_controller.dart` | edit | `OfficeView` enum, optional field on `ShowModeCommand`, phrases |
| `../screens/workspace_mode_view.dart` | edit | Remove the Documents rail item and `DocumentsRegion`. The `documents` focus maps to Office › Documents. |
| `../living_scope.dart` | edit | `activeOfficeTarget()` returns the target of the centre view (workbook or document) |
| `../voice/voice_interaction.dart` | edit (minimal) | Push-to-talk routing already uses the Office target (`:255`). It follows the generalized target. |
| A2UI hub | edit in `office_workspace.dart` and `office_controller.dart` | One region-level `A2uiHub` registers the `office.*` handlers once. `OfficeController` uses it instead of its own hub, so an action works with no workbook open (review F1). |
| `uri_ui/lib/office_o2_live_check.dart` | new | Live harness (section 12) |

### 4.4 Navigation by URI (refinement 9)

- `OfficeView { home, recent, documents, spreadsheets, presentations, pdfs, templates, workflows }` is added as an
  optional field of `ShowModeCommand`. The vocabulary stays closed. A command still cannot send text, approve, change
  a setting or dismiss a card (`presentation_controller.dart:20-25`).
- Local phrases: `uri office`, `uri office <view>`. `uri documents` now opens Office › Documents.
- **History (review F3):** today `_history` holds modes only and `back()` restores only the mode
  (`presentation_controller.dart:118,157-186`). O2 keeps the existing mode-only `history` getter (derived), so the
  existing test that expects `[UiPresentationMode.companion]` stays valid. A separate Office view history records
  `officeView` changes only, and Back inside the Office region uses it first. Back for other rail switches (Tasks,
  Settings) is not changed (review N6).
- The Office service may return `navigate: {view, file_id?}` in a response to the owner's own request. The Office
  pane applies it with `UiCommandOrigin.brain`. If the 600 ms cooldown refuses it, nothing moves silently: the
  companion shows the destination as a chip ("Open PDFs") for the owner to press. Navigation never opens a file
  without a grant, and never shows a file the owner has not opened.

### 4.5 Context across views (refinement 5)

The Office region keeps one `OfficeConversation`. Switching between a sheet, a document and Home keeps the visible
history. Each request is sent with:
- the owner's text;
- the active target (kind, id, selected page or slide);
- the last 6 owner turns, as text, inside an untrusted block.

The Brain classifier receives the request, the last owner turns and the **kind** of the active file. It does not receive
file names or outline titles, because it is not verified whether the Brain host logs prompt bodies (spike S8).

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
| Render timeout or crash | "Preview unavailable: the preview engine stopped." A LibreOffice render is all or nothing (review F20). Cached previews of other files stay. | Retry (restarts the engine once). "Open in default app" when an association exists. |
| Engine missing or hash mismatch | "Preview unavailable: the preview engine is not the approved version." | No automatic fix. The diagnostics line names the expected path and hash. |
| File changed on disk while open | "This file changed outside URI." | Reload |
| Protected or encrypted PDF or document | "This file is password-protected. URI cannot open it." | None in O2. Password entry is not offered. |
| Workflow step failed | The step is marked failed in the plan view, with the reason. | Retry step, or Discard workflow |
| Validation findings | A findings card lists errors and warnings with locations | Accept with warnings (one more click, logged), or Discard. Errors block approval. |
| Service restarted mid-workflow | On reopen the workflow shows "Interrupted at step N". Grants live in memory only (`grants.py:113-150`) and do not survive a restart (review F4). Any open output card is closed at start-up and audited as `INTERRUPTED`. | Resume: the owner re-confirms each input through the picker, with the recorded path pre-filled. A new grant is made, and the file's SHA-256 must equal the recorded value, or the workflow stops with a finding. Steps from N on re-run. A new destination is picked before a new approval card. Or Discard. |
| Brain unavailable (the normal state until a GPU window) | For an ambiguous request: "I'm not sure what you need. Choose one:" with the available capabilities as chips (review F14) | The owner picks a chip |
| Disk full or write error | "Not enough space to finish. Nothing was saved." | Free space, then Retry step |

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
| `sanitize.py` | new | Make the render copy. Refuse zip bombs (more than 500 MB uncompressed, ratio over 100, more than 10,000 entries). Refuse encrypted OOXML. Remove external relationships (`TargetMode="External"`, except hyperlinks, which stay live in outputs and are never fetched; see section 7). Neutralize `INCLUDETEXT`, `INCLUDEPICTURE`, `LINK` and `DDE*` fields. Drop `altChunk` external targets and OLE links. Remove `attachedTemplate` and `subDocument` relationships, PPTX `ppaction://program` and other non-navigation `ppaction` links, and external `href` / `xlink:href` in embedded SVG. OLE **embedded** objects are kept but never activated; OLE **links** are removed. The sanitizer parses XML with a hardened lxml parser (no DTD loading, `resolve_entities=False`, `no_network=True`, `huge_tree=False`) and refuses any part that has a DOCTYPE (review F10). Report each removal as a finding. Never change the original. |
| `render.py` | new | Engine manager. Checks the pin. Checks engine integrity at every launch. Re-seeds the hardened profile under `<state>/lo-profile/` at every start; the profile also disables crash reporting and update and extension checks (review F8). Sets `TMP`/`TEMP` for the engine to `<state>/lo-tmp/` and empties it after each job and at shutdown. Starts the listener inside a Job Object (`ctypes`) with a random pipe name. One queue with two priorities: previews before conversions. A queued job is cancelled when its document or workflow closes. Timeouts: 60 s per conversion, 90 s for start-up. Restarts once after a crash. **Idle** means no queued or running job; shutdown after 10 idle minutes (review F20). Results are PDF files in the job's folder. |
| `lo_bridge.py` | new | Runs in LibreOffice's `python.exe`. JSON lines on stdin and stdout: `{in, out, filter}` → `{ok, seconds, error}`. Accepts only paths under the service's working root, as passed at start. |
| `preview.py` + `raster_worker.py` | new | PDF to PNG pages with PyMuPDF at 110 dpi (on-screen), 200 dpi (zoom) and 40 dpi (thumbnails). **Untrusted PDFs are parsed in a worker subprocess**: `raster_worker.py` is a standalone script that imports only `pymupdf` and the standard library, run as `python -I <absolute path>\raster_worker.py <in> <outdir>` (`-m uri_office...` fails under `-I`, review N1), in its own Job Object, with a 1.5 GB memory limit and a 60 s timeout. They are not parsed in the service process, which holds the token and the grants (review F9). The worker receives only a file path and an output folder. Cache under `<state>/previews/<key>/`; the key is the SHA-256 of (input SHA-256, engine manifest hash, sanitizer version, dpi) (review F20). 1 GB LRU cap. "Clear previews" is in the Office region's left-pane menu, because `settings_shell.dart` is protected. |
| `validate.py` | new | Shared checks and the findings model (section 8) |
| `workflows.py` | new | Workflow runner: `<state>/workflows/<id>/` (review F16: `work/` already holds workbook copies, `service.py:134,536`), `workflow.json`, step states, resume, cancel, retention (7 days for abandoned runs, removal on discard or after approval) |
| `recent.py` | new | `<state>/recent.json`: path, kind, last opened, size. No content and no hash. Remove an entry, Clear all. Re-opening an entry asks the picker to confirm the file, so a new grant is made. A recent entry is not a grant. |
| `grants.py` | edit | `check_shape(raw, flavor=None, *, suffixes=(".xlsx",))`, which keeps the existing positional `flavor` (review F5; `test_grants.py:49-67` passes it positionally). `grant_open(raw, *, kind="xlsx")` and `grant_save_as(raw, *, kind="xlsx")`. Per-kind size caps: DOCX and PPTX 50 MB, PDF 100 MB and 2,000 pages. |
| `approvals.py` | edit | Generalized as specified in section 5.1. The output card lists each output (name, size, pages, SHA-256 prefix, full destination), every sanitizer warning, and "originals will not change". The hash binds all of it. |
| `service.py` | edit | Routes listed below. One binary response helper. Workflow resume scan at start. |
| `engines.json` | new | Pinned engine paths (relative to `%LOCALAPPDATA%\URI\engines\`) and SHA-256 values |

### 5.1 Approval generalization (review F1)

| Change | Detail |
|---|---|
| Table | `surface` gains `subject_kind TEXT NOT NULL DEFAULT 'workbook'` through `ALTER TABLE ... ADD COLUMN`, so existing rows stay `workbook`. The existing `workbook_id` column holds the subject id: a workbook id or a workflow id. Plan cards are rows of the same table (`record_json.kind = 'plan'`). One audit chain. |
| Propose | New `propose_outputs(workflow_id, outputs, destination)` and `propose_plan(workflow_id, plan)`. The existing workbook `propose` keeps its behaviour, with one mechanical change: its positional `INSERT INTO surface VALUES (...)` (`approvals.py:144`) becomes a named-column insert, because the new column would break it (review N5). The `ALTER TABLE` runs only when `PRAGMA table_info(surface)` lacks the column. "One open card per workbook" becomes "one open card per subject". |
| Action | `office.run_plan` apply only records the state change and enqueues the workflow, then returns. Execution never runs inside the approvals lock, which `Approvals.action` holds around `apply_fn` (`approvals.py:241-264`; review N2). Each workflow has its own lock, taken before the approvals lock, as workbook sessions do (`service.py:561-567`; review N9). `Approvals.action` reads the bound hash key from a per-action map: `office.apply_change` and `office.reject_change` use `change_sha256`; `office.run_plan` and `office.discard_plan` use `plan_sha256`. Audit payloads use counts that exist for each kind (outputs, steps). |
| Apply | `Office._apply` dispatches on `body["target"]["kind"]`. `output_files` and `plan` are handled **before** any workbook session lookup. The workbook branch is unchanged. |
| Output write | For each output, at apply time: re-check the destination's real path against the grant (no junction swapped in since the grant), then write to a temporary file in the destination folder, flush and fsync, and rename it to the final name with a rename that fails if the name exists (`os.rename` on Windows). Any failure deletes the temporary file, so nothing partial is left at the destination (reviews F23, N8). A test injects ENOSPC and checks this. The same gap in the M1/M2 save path is reported to the owner as a finding. O2 does not change M1/M2 code. |
| Dart | One region-level action handler (section 4.3) |
| Concurrency test | A workbook save completes while a conversion runs (review N2). |
| Regression | All M1/M2 approval tests (`tests/office/test_service.py`, `test_review_*`, `test_m2_new_workbook.py`) pass unchanged. A test proves that an existing database without `subject_kind` migrates and its chain still verifies. |

**Destination order (review F5):**
1. Validation.
2. Preview.
3. The owner presses Save.
4. The save dialog picks the destination (SAVE_AS grant, `kind="pdf"`).
5. The card is proposed. It binds the outputs **and** the destination.
6. Apply.

O2 has one output per workflow. Several outputs (O7) need a folder-destination grant, which is designed in O7.

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
8. **Approve outputs.** The owner presses Save and picks the destination in a save dialog (SAVE_AS grant). Then an
   `output_files` card, binding the outputs and the destination, goes through `office.apply_change` (order in section
   5.1). The write never overwrites, is atomic, and is audited.
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

`workflows/<id>/workflow.json` holds:
- the intent and capability id;
- the inputs (path, kind, SHA-256 before; the path is kept so that resume can pre-fill the picker; it is not content);
- the steps (kind D, E or B; engine and version; start; end; state; finding ids);
- the outputs (name, SHA-256, pages);
- approvals (surface id, `change_sha256`);
- errors and recovery.

It holds **no document text**. The live harness and qualification evidence read it.

## 7. Cross-application workflows (programme view; O2 builds the pipeline they share)

**Conversion and the sanitizer (review F15).** Convert to PDF renders the sanitized copy.
- Hyperlinks stay live in the output PDF. They are never fetched while rendering.
- Linked images, `INCLUDE*` field content and OLE links are not loaded. Each one is a **warning** on the
  output-approval card ("1 linked picture was not included"), so the owner accepts a PDF knowing that it differs.

This is the O2 default. The owner can change it at G0.

| Workflow | Readers → deterministic core → Brain → writer | Validator focus | Phase |
|---|---|---|---|
| Word → PDF | sanitize → LibreOffice export → none | page count, fonts embedded or substituted, blank pages, **each item the sanitizer removed** | **O2** |
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
| Count check: the slide count equals the source (PPTX). For DOCX, the PDF page count equals the preview render's count. Both come from the same engine, so this is a consistency check, not a fidelity check (review F17). | render | yes | |
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
   UNC targets. The canary set includes a dedicated UNC canary host (section 12, row F1).
4. **PDF.** PyMuPDF renders only. JavaScript, launch actions and embedded files are never run or extracted.
5. **Brain.**
   - Stage-2 classification sees the owner's request, the last owner turns and the **kind** of the active file only.
     It sees no file names and no outline titles (section 4.5, spike S8; review N4). A test asserts that the
     classify prompt contains no file name or title.
   - The request and turns go inside an untrusted block.
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
| U3 | With a workbook open, the Excel view and companion behave as before. All M1 and M2 Flutter tests pass unchanged, except the simulated-Documents tests listed in section 1.2, which are retired or rewritten with reasons. | existing suites | L1 |
| U4 | Goal groups show only `available` capabilities. Empty groups are hidden. No control leads to "not implemented". | widget test with the registry fixture | E3 |
| U5 | Conversation history persists across Home, sheet, document and back. Each turn shows its target label. | widget test | E4 |
| U6 | First-visit hint and first-of-kind hints appear once. A dismissal persists. The help chip lists available and planned capabilities separately. | widget tests | E5 |
| U7 | Every state in section 4.7 has the specified message and recovery action. | widget tests with fake errors | F-items |
| U8 | At most one hint visible. No hint while a workflow runs. A hint can always be dismissed. | widget test | E5 |
| U9 | `uri office`, `uri office pdfs` and the other view phrases, plus service `navigate`, move the view. History has Back. The cooldown holds. | unit tests in `presentation_controller_test.dart` | E6 |
| U10 | No new colour literal. Only theme tokens. | Lint grep over new and edited files. Any `Color(0x`, `Color.fromARGB`, `Color.fromRGBO` or `Colors.` fails. | K-visual |
| U16 | No duplication (refinement 10): no new Brain client, A2UI renderer, approval store or conversation store. | A test greps O2 files for imports of `brain_client` outside `brain.py`, any second `A2uiHub` construction and any second conversation store | — |
| U17 | Follow-up chips (at most two) and hints can be dismissed. A dismissed chip does not return for that output. | widget test | E5 |
| U11 | Keyboard: all shortcuts in 4.2 work. The Tab order covers every control. Icon buttons have semantic labels. | widget tests | E7 |
| U12 | Page preview. These are **provisional thresholds**: the listener was measured on a 1-page DOCX only, so spike S7 measures the 20-page fixture and the thresholds are set from it before freeze. First page visible ≤ 2.0 s for a warm 20-page DOCX, and ≤ 0.5 s for a PDF page. Scrolling 50 pages keeps 95 % of frames under 16 ms (existing perf logger). | timing test with a fake engine; perf log | H-items |
| U13 | A waiting card (clarification, plan or approval) is never hidden without a visible badge at any width. | widget test at 900 px | E2 |
| U14 | The page preview is labelled "Preview rendered by LibreOffice". | widget test | K |
| U15 | The `DocumentsRegion` simulated tiles are gone. `uri documents` opens Office › Documents. | widget test | E6 |

## 11. O2 functional acceptance criteria

| # | Criterion | Test |
|---|---|---|
| AC-O2-1 | Open DOCX, PPTX and PDF read-only through a picker grant. Pages, outline and thumbnails appear. The original is byte-identical afterwards. | `tests/office_u2/test_open_documents.py` + G1 |
| AC-O2-2 | **Engine regression** (not fidelity to Word; review F17): DOCX and PPTX previews match a reference render (fixtures rendered once, hashes and PNGs in `tests/office_u2/fixtures/`): page count equal, and per-page pixel difference under 0.5 %. | `test_render_fidelity.py` (needs the engine; marked `engine`) |
| AC-O2-3 | Listener mode (provisional; set from S7): warm DOCX conversion ≤ 2 s median over 5 runs for the 20-page fixture. Start-up ≤ 15 s with the persistent profile, and ≤ 30 s on the first ever start (review F25). Idle shutdown after the timeout leaves no process. | `test_render_engine.py` + H1 |
| AC-O2-4 | Hardened profile and sanitizer: every canary type (external image, `INCLUDEPICTURE`, `INCLUDETEXT`, OLE link, `altChunk`, PPTX linked media, UNC target) causes 0 network or SMB connections. Each removal is reported as a finding. | `test_render_isolation.py` + F1 |
| AC-O2-5 | Job Object: killing the service, a conversion timeout, or `soffice.bin` crashing leaves no orphan LibreOffice process within 5 s. The next request restarts the engine once. | `test_render_engine.py` + F2 |
| AC-O2-6 | Engine pin mismatch or missing engine: preview unavailable with the stated message. The engine is never run. | `test_engine_pin.py` |
| AC-O2-7 | Convert to PDF works end to end. The pipeline runs plan card → execute → validate → preview → `output_files` approval → write, with no overwrite. `workflow.json` has every step. Sources are unchanged. | `test_workflow_convert.py` + D1 |
| AC-O2-8 | Validation blocks approval on any error finding. Warnings need explicit acceptance, which is audited. | `test_validate.py` |
| AC-O2-9 | Resume: killing the service during the render step, then restarting, shows "Interrupted at step N". Resume asks the owner to re-pick each input (path pre-filled), makes a new grant, and re-runs the step only if the SHA-256 equals the recorded value. A changed input stops the workflow with a finding. Open output cards were closed at start-up. | `test_workflow_resume.py` + F3 |
| AC-O2-10 | Intent corpus (review F14): 40 requests in `tests/office_u2/intent_corpus.json`, with expected results recorded before the run: 24 deterministic and 16 ambiguous.<ul><li>Deterministic: 24/24 correct on stage 1, with **zero** Brain calls.</li><li>Brain subset (live, GPU window): 100 % schema-valid; at least 14/16 correct; a wrong classification never starts a workflow without the plan card.</li><li>With the Brain unavailable, all 16 ambiguous requests give clarification chips.</li></ul>`missing` is a closed enum (`input_file`, `output_format`, `page_scope`, `input_role`). The classifier uses a document-specific system rule, not the spreadsheet `SYSTEM_RULE`. | `test_intent.py` + C1 (Brain) |
| AC-O2-11 | Planned capabilities answer "not available yet" with the phase. They never start a workflow. | `test_intent.py` |
| AC-O2-12 | A2UI: `office.run_plan` refuses a stale or changed plan hash and a replay. `output_files` approvals refuse a changed output and a destination that already exists. | `test_plan_card.py`, `test_output_approval.py` |
| AC-O2-13 | Security: every new route refuses a missing token, a bad Host or Origin, and an unknown id. Paths outside grants are refused. Zip bomb, encrypted and oversize files are refused with a finding. | `test_service_u2.py`, `test_sanitize.py` |
| AC-O2-14 | No content in `workflow.json`, `recent.json` or the logs: the fixture text "SENTINEL-CONTENT-7f3a" never appears in the state folder outside `workflows/` and `previews/`, and never in `%TEMP%` after a job. | `test_no_content_leak.py` |
| AC-O2-15 | Excel regression: `tests/office`, `tests/a2ui`, `uri_ui/test/office` and the living shell tests pass unchanged, except the simulated-Documents tests listed in section 1.2. `ws_frozen_check` shows no protected path changed. | full suites + L1 |
| AC-O2-16 | No GPU use by the Office engines: the GPU process census during previews and conversion shows no LibreOffice, raster-worker or Office-service GPU memory. WebView2's own GPU process is measured separately (AC-O2-21). | H2 |
| AC-O2-17 | Switching sheet → PDF → sheet keeps the workbook's draft, change marks and undo stack, with no Univer reload. | widget test + live E4 |
| AC-O2-18 | The hardened profile also disables crash reporting and update and extension checks. The census of Job Object process ids shows no outbound connection during the whole live run. | `test_render_isolation.py` + F1 |
| AC-O2-19 | Engine integrity: changing one byte of any file in the manifest makes the next launch refuse to run the engine. | `test_engine_pin.py` |
| AC-O2-20 | A malformed or hostile PDF that crashes or hangs MuPDF kills only the raster worker. The service keeps running and shows "Preview unavailable". | `test_raster_worker.py` |
| AC-O2-21 | While a sheet is hidden behind a document view, keys typed in the document view never change the sheet's draft. The hidden WebView2's CPU and GPU use is measured in H2 and H3 and reported against the Excel baseline. | widget test + live E4, H2, H3 |

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
| B1 | 3 Formatting fidelity / B | (a) Engine regression: AC-O2-2 on the J fixtures. (b) Rendering fidelity: the reviewer compares each render with the structure the fixture generator wrote (headings, tables, header, footer, chart). (c) Fidelity against Microsoft Word: **NOT VERIFIED** (no Office licence on the PC). | no | no | (a) and (b) runnable; (c) NOT VERIFIED |
| K1 | 4 Rendering and previews / K | Rasterize every page. Automated visual checks (section 8). The reviewer inspects a sample of 10 pages and slides, with screenshots. | no | no | runnable |
| D1 | 5 Save, reopen, modify / D | Convert to PDF. Save through the approval card. Reopen the PDF in Office. Its preview matches. No overwrite of an existing name. | no | no | runnable |
| I1 | 6 Cross-application / I | Word → PDF and PowerPoint → PDF only. The rest is O7. | no | no | runnable |
| D2 | 7 Batch generation / D | **Not O2** (O7) | — | — | N/A |
| O1 | 8 Contextual suggestions | **Not O2** (O8). O2 checks only the one-hint rule (U8). | no | no | runnable |
| E1–E7 | 9 First-time use and usability / E | Scripted first-visit path. Time to first preview. Hint behaviour. Responsive widths. Keyboard. Then an **owner think-aloud session** recording confusion points and time to the first output. Repairs are retested. | no | **yes** | Scripted part runnable. Owner session **BLOCKED** (owner away). |
| F1–F6 | 10 Errors and recovery / F | <ul><li>**F1 canaries:**<ul><li>an HTTP canary for each reference type;</li><li>for SMB/UNC, links point at a dedicated canary host `\\127.0.0.2\canary`, and connections to 127.0.0.2 on ports 445 and 139 are detected system-wide (the kernel redirector, PID 4, makes SMB connections, so a per-process census cannot see them), which filters out ambient SMB traffic (review N10);</li><li>a WebDAV canary `\\127.0.0.1@<port>\x` on a high port (review F6);</li><li>an outbound-connection census of all Job Object process ids for the whole run, polled at ≤ 50 ms (review F8). A poll can miss a very short connection, so the canary servers remain the primary detector and the census is a second net.</li></ul></li><li>**F2:** engine crash and timeout, with crash reporting disabled and no dump upload.</li><li>**F3:** service kill mid-workflow, then resume (inputs re-confirmed).</li><li>**F4:** corrupt, encrypted, oversize, zip-bomb and DOCTYPE/XXE files.</li><li>**F5:** disk full by **fault injection** (ENOSPC raised in the write and convert paths), labelled as a simulation (review F7).</li><li>**F6:** file changed on disk while open.</li></ul> | no | no | F1 HTTP and port diff, F2–F4, F5 (simulated) and F6 runnable. WebDAV canary runnable only if the WebClient service is running; otherwise NOT VERIFIED. A real disk-full test: NOT VERIFIED. |
| G1 | 11 Original protection / G | Source hashes before and after every live item. No stray files outside `workflows/`, `previews/`, `lo-tmp/` (empty after each job) and the chosen destination. `%TEMP%` scanned before and after for new files from the engine (review F8). | no | no | runnable |
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
| S1 | Does LibreOffice's `python.exe -I lo_bridge.py` import `uno` and convert? Does the known stderr line "Could not find platform independent libraries" from the extracted Python matter in `-I` mode? | Run without `-I`, with `PYTHONPATH` cleared and the bridge copied into a private ACL-restricted folder. Record the deviation. |
| S2 | Live confirmation that the texture-based WebView2 host (`webview_bridge.cc:197-213`) draws under Flutter overlays | Push layout instead of overlay for sheets under 1000 px |
| S3 | `ctypes` Job Object: same kill behaviour as the probe? | Fall back to a psutil tree kill (documented weaker guarantee) |
| S4 | Listener start-up with a re-seeded persistent profile (not fresh) | Keep the fresh profile and accept about 10 s start-up |
| S5 | Pixel comparison of per-call and listener output on the fixtures | Investigate before AC-O2-2 references are recorded |
| S6 | Cost of the full-tree engine manifest check (file count, seconds) | Full check at service start only; executables, DLLs and `python.exe` at each launch |
| S7 | Listener timing on the 20-page DOCX and 60-page PDF fixtures | The U12 and AC-O2-3 thresholds are set from the measurement |
| S8 | Does Runtime v1 or the Brain host log prompt bodies? | Already mitigated: the classifier gets no file names or titles (section 4.5) |

**Workstreams** (review F19): the integration branch is `phase/uri-office-u-2` from `5b958da0`. Each workstream has its own sub-branch and worktree (`phase/uri-office-u-2-a`, `-b` and `-c`). They merge into the integration branch in order A → B → C.

| Workstream | Owns | Starts after |
|---|---|---|
| WS-A engine and pipeline (Python) | `capabilities.py`, `intent.py`, `content.py`, `docs.py`, `sanitize.py`, `render.py`, `lo_bridge.py`, `preview.py`, `validate.py`, `workflows.py`, `recent.py`, edits to `grants.py`, `approvals.py`, `service.py`, `brain.py`, `engines.json`, `raster_worker.py`, `uri_a2ui/actions.py` **and its Dart mirror `a2ui_contract.dart`**, `tests/office_u2/` | Spikes S1, S3, S4, S5 |
| WS-B workspace UI (Flutter) | all `uri_ui/lib/living/office/*` listed in 4.3, `presentation_controller.dart`, `workspace_mode_view.dart`, `living_scope.dart`, `voice_interaction.dart`, `uri_ui/test/office_u2/` | Route contract frozen (`docs/office/unified/O2_API_CONTRACT.md`, written first in WS-A). Spike S2. Built against a fake client until WS-A merges. |
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
| R5 | WebView2 overlay composition | Low (texture host in source) | Spike S2 live confirmation. Push-layout fallback. |
| R6 | The `uno` bridge cannot run isolated (`-I`) | Low | Spike S1 fallback |
| R7 | Stacking on an unintegrated Office line (W-7) and the canonical frozen checker exiting 1 (W-8) | High (integration) | Unchanged owner items. O2 stays rebase-ready and small. |
| R8 | Brain-dependent rows stay BLOCKED until the GPU window | Certain until the owner returns | Most of O2 is Brain-free by design. The rows are reported BLOCKED. |
| R9 | Scope creep into editing within O2 | Medium | Section 2.2. The registry only exposes `available` capabilities. |
| R10 | Preview cache holds rendered images of sensitive documents | Medium | ACL-restricted state folder. 1 GB LRU. "Clear previews" in the Office region's left-pane menu. Previews are deleted when a recent entry is removed. |
| R11 | Same-user processes could drive the UNO pipe | Low | Random pipe name. Same-user processes already hold the user's rights. Documented. |
| R12 | A fresh worktree lacks the Univer bundle, so `test_page` fails | Low | WS-C setup stages the hash-verified bundle or records the skip. Found on 2026-10-15. |
| R13 | MuPDF parses hostile PDFs | Medium → Low | Raster worker subprocess in a Job Object (AC-O2-20). Residual: the worker runs as the same user. |
| R14 | The user-writable LibreOffice extract could be altered | Medium → Low | Full-tree manifest and signer check at each launch (AC-O2-19) |
| R15 | Grants lost on restart make resume heavier | Low | The owner re-confirms inputs through the picker (section 4.7) |
| R16 | The same TOCTOU gap exists in the M1/M2 save path | Low | Reported to the owner as a finding. O2 does not change M1/M2 code. |

## 17. Unverified items and their effect

| Item | Effect |
|---|---|
| AC11 and H3 (Brain speed with Office open) | Blocks O2 acceptance until the GPU window. Does not block G0 or G1. |
| `uno` under `-I` (S1); `ctypes` job (S3); persistent profile (S4); per-call and listener pixel parity (S5); WebView2 airspace (S2) | Each is resolved on the first implementation day. Each has a stated fallback. |
| Which hardened setting stopped the fetch | None: all settings are kept and the canary runs every time |
| Calibri and Nirmala UI rendering in LibreOffice for real owner documents | Covered by J1 and the owner check. Could change R2 and R3. |
| `drive.file` with the Docs and Slides APIs | O6 only |
| 20-page and 60-page timings (S7) | The U12 and AC-O2-3 thresholds are provisional until S7 |
| Whether the Brain host logs prompts (S8) | Mitigated. It affects only what the classifier may receive later. |
| The owner's 17 items were mapped from the owner's message of 2026-10-15. The reviewer did not see the original wording. | None, if the owner confirms the mapping at G0 |
| `requirements.txt` says `pymupdf>=1.24`; the measured version is 1.28.2 | WS-A pins the tested version for the Office path, or records the tested range |

## 18. Self-review against section 0

Rev 1 self-review was done before the independent review:

| Criterion | Result |
|---|---|
| Q1 | Met. Re-run today. File and line cited. |
| Q2 | Met. The probe's measurements and gaps are named in sections 3 and 17. |
| Q3 | Met (rev 2). Refinements 1–10 map to U3/AC-O2-17, U1, U2, U10, U5, U6, U7, U8/U17, U9 and U16. |
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

- Round 1 (separate Claude reviewer, read-only, at `d2706bff`): **REVISE**. It found 2 blockers, 13 major, 8 minor and
  2 notes.
- Round 2 (same reviewer, at `78cfdacc`): **REVISE (narrow)**. No blockers. 16 of the 25 findings were closed and 9
  were partly closed. It found 4 new major and 7 new minor findings.
- Rev 3 repairs all of them.

The reviewer's freeze-readiness expectation after these repairs was ACCEPT WITH FINDINGS. Round 3 (check of the rev 3 diff, at `d54f8905`): **ACCEPT WITH FINDINGS** for the planning gate.
Its two wording notes are fixed in rev 3.1. Details are in `02_O2_INDEPENDENT_REVIEW.md`.
