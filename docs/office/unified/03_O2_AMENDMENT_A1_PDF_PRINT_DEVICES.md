# O2 plan amendment A1 (rev 3): PDF scope, PyMuPDF replacement, printing and device discovery

Date: 2026-10-15. Amends `01_O2_PLAN_AND_ACCEPTANCE_CRITERIA.md` (rev 3.1 → rev 4) and the programme plan
`00_DISCOVERY_RESEARCH_AND_ROADMAP.md`. Planning branch `phase/uri-office-unified-plan`, local only.

Owner instruction (chat, 2026-10-15): "O2 Plan Amendment & Conditional G0/G1 Approval". Its terms:
- G0 and G1 are approved **conditionally**: the amendment must get independent acceptance, and licensing must be resolved.
- No installation, elevation, real printing, canonical integration, push or deployment is authorized.

Where this amendment and the rev 3.1 plan disagree, **this amendment wins**. The rev 3.1 sections it replaces are marked
in the plan.

## A0. Acceptance criteria for this amendment

| # | Criterion |
|---|---|
| AA1 | The PDF scope matches the owner's list exactly. Removed features are named and taken out of the roadmap. |
| AA2 | PyMuPDF is no longer a dependency of any Office phase, unless the owner approves its AGPL obligations. Every replacement engine has a measurement from this PC, or a stated gap. |
| AA3 | Licensing is resolved with **no new installation**, or the remaining install is named as an owner decision that does not block G1. |
| AA4 | Printing has one interface for Word, Excel, PowerPoint and PDF. It uses existing Windows interfaces and drivers, and no paid service. Every job needs explicit approval. |
| AA5 | Device discovery is modular, so scanners can be added later without a redesign. It stays lightweight: one provider, printers. It installs nothing, pairs nothing and changes no configuration. |
| AA6 | B1, the Excel integration, A2UI behaviour and companion continuity are preserved. Print and Save as PDF appear in the document controls. |
| AA7 | O2 and the new printing phase are each independently testable and auditable. Neither inherits the other's qualification. |
| AA8 | Live tests cover the owner's 15 new items. Physical printing is marked NOT VERIFIED where no printer or authorization exists. |
| AA9 | Every interaction with rev 3.1 is resolved: approvals (5.1), raster worker (F9), validation (§8), live matrix (§12) and gates (§15). |

## A1. PDF scope (owner decision D-PDF, 2026-10-15)

**Kept:**
- PDF viewing, navigation (pages, outline), zoom and search;
- conversion of Word, Excel and PowerPoint files to PDF ("Save as PDF");
- reliable rendering and print preview;
- PDF reading, text extraction, OCR of scans, summarization and page-cited Q&A;
- protection of source files and integrity of outputs.

**Removed from the roadmap:**
- merging, splitting, rotating, reordering or assembling pages;
- highlighting, annotating or editing annotations;
- filling AcroForm fields;
- redaction, editing PDF text, and any page-design feature;
- pypdf's use for page assembly; it stays, for reading only.

**Open:** "PDF tables → Excel" (programme plan §6) needs a table extractor. PyMuPDF `find_tables` is gone and pypdf has
none. See decision OD-U11. Until it is decided, this capability is `planned` and not built.

## A2. PDF engines and licensing (replaces rev 3.1 §3 PyMuPDF rows)

Evidence: `evidence/pdf_print_probe_20261015/`. Run 2026-10-15 at 09:45 +0530, with no PyMuPDF imported
(`"pymupdf_imported": false`) and nothing installed.

| Need | Engine | Licence | Installed? | Measured on this PC |
|---|---|---|---|---|
| Page images: preview, thumbnails, zoom, validation raster, print raster | **Windows.Data.Pdf** (Windows' built-in WinRT PDF API), run in a PowerShell 5.1 worker | Part of Windows. Nothing is redistributed. | yes (OS) | 10-page PDF: open 159 ms; first page 169 ms; then **27 ms per page** at 900 px; every page distinct; faithful text, table and heading (`winrt_report20_p6.png`). PowerShell start-up is about **1.4 s** once per worker (1.97 s wall minus 0.60 s of rendering; review A1-m7). **GPU:** 0 bytes of dedicated GPU memory and 0 % GPU engine use across 40 samples while rendering 1800 px pages 3 times. The positive control (dwm.exe) read 389 MB, so the counter works (`winrt_gpu_census_result.json`, `gpu_counter_positive_control.json` from `gpu_counter_positive_control.ps1`; review A1-M4).

**Scope of the GPU result (review R4):**
- one simple 10-page text PDF;
- dedicated memory only;
- samples taken about every 100 ms plus the collection time, interval not recorded;
- no instance count recorded.

A very short allocation could be missed. Complex, transparent or image-heavy PDFs are measured in S10 and H2 before AC-O2-16 can pass. |
| Text, search, outline, fonts, page count, scan images | **pypdf 6.19** | BSD-3-Clause | yes (existing dependency) | 10 pages: open 3.9 ms; extract all 279 ms (22,494 characters). Outline items found. Fonts listed (Calibri-Bold, Cambria). Search found "Section 7" on the right page. |
| OCR of scanned pages | **Tesseract 5.5** on WinRT page rasters at 300 dpi (see "OCR input" below) | Apache-2.0 | yes | Measured only on the earlier path, Tesseract on images pypdf extracted from a 2-page image-only PDF: 554 ms and 223 ms, with the text read correctly. **The WinRT-raster OCR path is not yet measured.** It is added to S10 and H. |
| Word, Excel and PowerPoint → PDF | **LibreOffice 26.8.1.1** listener | MPL-2.0 (OD-U2 approved) | yes (user-folder extract) | Load plus export (review A1-M1; export alone is not the conversion time):<ul><li>DOCX, 10 pages: first 4.09 + 0.17 s; warm repeat 0.44 + 0.07 = **0.51 s**.</li><li>PPTX, 11 slides: 0.52 + 0.11 = 0.63 s.</li><li>XLSX: 0.33 + 0.29 = 0.62 s. **The XLSX page count was not measured** (`pages: null`).</li></ul> |
| Slide images | LibreOffice `impress_png_Export` per slide | MPL-2.0 | yes | 11 slides in 0.97 s, all distinct |
| **Negative result** | LibreOffice `writer_png_Export` with `PageRange` | — | — | All 10 page PNGs have one SHA-256 (`lo_writer_pagerange_png_hashes.json`: 1 distinct value out of 10). The probe JSON's `png_pages: 10` counts files written, not distinct pages. The programme plan cited LibreOffice bug 157425 for this limitation; this probe did not re-verify the bug report. Writer pages are rasterized from the PDF. |

**Enforcement (review A1-M7):** a test asserts that no module in `uri_office/`, `uri_devices/` or the workers imports
`fitz` or `pymupdf`. WS-C fixture tooling also generates its PDFs with LibreOffice, Pillow and pypdf, not PyMuPDF.
This keeps the rule simple: no Office code and no Office test tool uses it.

**OCR input (review A1-m8):** OCR pages are rasterized with Windows.Data.Pdf at 300 dpi. pypdf image extraction is not
used for OCR, because JBIG2 and CCITT scans may not decode, and mixed pages need the whole page.

**Decision D-ENG-1:**
- **PyMuPDF is removed from all Office phases.**
- Page images come from Windows.Data.Pdf.
- Text comes from pypdf.
- OCR uses Tesseract.
- Conversion uses LibreOffice.

No new dependency and no installation. **OD-U3 (PyMuPDF AGPL) is withdrawn as an Office dependency.** It no longer
blocks G1.

Notes:
- Core's existing `uri_core/services/pdf_reader.py` imports PyMuPDF. That is a frozen Core dependency outside this
  programme. Office never imports it. Whether Core's own AGPL position is acceptable is an owner awareness item
  (OD-U14), not an Office decision.
- **Fallback, not adopted:** pypdfium2 (Apache-2.0 or BSD-3-Clause, wrapping Google PDFium, 3.9 MB Windows wheel). It
  would be needed only if Windows.Data.Pdf fails a qualification row, for example on hostile or very complex PDFs. It
  needs a pip install, so it needs owner approval (OD-U3b). It would be pinned to a release at least 2 weeks old; the
  current 5.14.0 was released on 2026-10-04 and is too new.
- Gap compared with PyMuPDF: pypdf gives no character-level boxes for highlighting search hits on the page image. O2
  search lists pages and jumps to the page. Hit highlighting is `planned` and depends on spike S9.
- Isolation: Windows.Data.Pdf parses untrusted PDFs **inside the raster worker** (PowerShell, in its own Job Object
  with a memory and time limit). It never runs in the service process. This keeps the rev 3.1 F9 repair. pypdf
  parsing for text runs in a Python worker on the same pattern (`python -I`, standalone script).
  - The worker script files are hash-checked before each start, like the engine manifest.

## A3. Changes to the O2 design (rev 3.1 sections replaced or extended)

| rev 3.1 location | Change |
|---|---|
| §2.1 item 2 | PDF viewing: page images, thumbnails, outline, **zoom** (110/200/300 dpi re-render), **search** (pypdf text; results list pages; jump to page) |
| §2.1 item 6 | "Convert to PDF" becomes **Save as PDF** for Word, PowerPoint **and Excel**. **Excel rule (review A1-M2):** the PDF is made from the **file on disk only**.<ul><li>If the draft holds any change not yet saved (pending or accepted but unsaved, M1 draft semantics), Save as PDF is blocked with "Save your changes first, or discard them."</li><li>LibreOffice recalculates and paginates using the file's page setup (print area, orientation, scaling).</li><li>Google Sheets sessions and new unsaved workbooks (M2 before their first save) are `planned`, not available.</li></ul> |
| §2.2 | Add: PDF editing, annotation, assembly and forms are out of the programme (A1). Printing moves to phase O2P (A5). |
| §5 `sanitize.py`, AC-O2-4, F1 | **XLSX is now a LibreOffice input (review A1-M3).** The sanitizer's XLSX rules, for the render copy only:<ul><li>remove `externalLink` parts and their relationships;</li><li>remove `connections.xml`, query tables and data-model parts;</li><li>neutralize formulas calling `WEBSERVICE`, `FILTERXML`, `HYPERLINK` to non-http targets, `RTD` or DDE (`=app\|topic!item`) by replacing each with its cached value, reported as a finding;</li><li>remove macros (`vbaProject.bin`).</li></ul>The hardened profile also sets LibreOffice to **never recalculate on load** (Calc `Formula/Load` recalculation modes for OOXML and ODF set to "never") and to never update links. Cached values are printed as stored. New canaries in AC-O2-4 and F1: an XLSX with an external link, a WEBSERVICE formula, a DDE formula and a web query connection, each pointing at the HTTP canary. All must give 0 fetches. |
| §3 | PyMuPDF rows replaced by A2 |
| §4.1 / §4.3 | Document view header gains **Save as PDF** and **Print** buttons for every kind (Word, Excel, PowerPoint, PDF), shown only when the matching capability is `available`. In O2, Print is `planned` until O2P qualifies. The left pane gains **Devices › Printers** (A6) only when O2P is available. |
| §5 `preview.py` + `raster_worker.py` | The raster worker becomes `uri_office/workers/winrt_raster.ps1`: JSON lines in and out, renders pages with Windows.Data.Pdf. It runs in a Job Object (1.5 GB, 60 s per request). A sibling `uri_office/workers/pdf_text.py` (standalone, pypdf only, run with `python -I` by absolute path) extracts text, outline and fonts. The service holds no PDF parser. |
| §8 validation | Fonts come from pypdf. Blank pages are found by pixel coverage on the WinRT raster. **Text outside the page box:** pypdf text-position visitor, confirmed by spike S9; if S9 fails, the check falls back to raster edge-ink detection (ink within 2 mm of the page edge). The minimum font size comes from the pypdf text matrix (S9). |
| §9.4 | "PyMuPDF renders only" becomes: Windows.Data.Pdf renders inside the raster worker; pypdf reads inside the text worker; neither runs JavaScript, launch actions or embedded files. |
| §11 AC-O2-20 | Applies to both workers. A hostile PDF that crashes or hangs either worker kills only that worker. |
| §11 AC-O2-2 | The reference renders and comparisons use the **WinRT raster worker** at 110 dpi. |
| §11 AC-O2-16 | "No GPU" covers LibreOffice, the WinRT raster worker, the text worker, the print worker and the service. It is checked by the GPU-memory and GPU-engine counter census of each worker process in H2. The 2026-10-15 probe measured 0 for the WinRT worker, with a positive control. |
| new AC-O2-22 | No Office module, worker or Office test tool imports `fitz` or `pymupdf` (test). |
| §14 spikes | Add S9: pypdf text positions and font sizes for the overflow and size checks. Add S10: the WinRT worker under a Job Object memory limit, a malformed-PDF corpus, a PowerShell Constrained Language Mode check, a per-worker GPU census (dedicated and shared memory, with the instance count recorded) on complex, transparent and image-heavy PDFs, WinRT-raster OCR timing, and the effect of the PowerShell execution policy with `-File` on a hash-checked script. |
| §15 gates | OD-U3 withdrawn (A2). New gates in A9. |
| §1.2 row "Core PDF and OCR" | Core `pdf_reader.py` stays unused by Office (and is PyMuPDF; OD-U14) |
| §7 rows PDF → Word, PDF → Excel, PDF → presentation | Reader is **pypdf** with Tesseract OCR on WinRT rasters, not PyMuPDF. The PDF → Excel tables row waits for OD-U11. |
| §8 "Opens in its engine" | For PDF: opens in pypdf and renders its first page in the WinRT worker. Minimum font size and text outside the page box depend on S9. The edge-ink fallback is **weaker** (it cannot tell text from graphics) and is labelled as such in findings. |
| §14 "Before implementation" | "OD-U3 ruled" is removed. OD-U7 is settled by the owner. |
| §14 spikes | Add S11 (raster print memory and spool, A4) |
| §16 R13 | "MuPDF parses hostile PDFs" becomes "Windows.Data.Pdf and pypdf parse hostile PDFs", in their workers |
| §17 pin row | The PyMuPDF pin is dropped. WS-A records pypdf 6.19.0 as the tested version. |

## A4. Shared print and Save-as-PDF interface (one path for all four kinds)

```
Word / PowerPoint ─┐  LibreOffice listener → PDF (working copy)
Excel (saved file) ┤
PDF (as is) ───────┘──────────────────────────────→ print PDF ──→ raster worker: preview at the chosen paper,
                                                                    orientation, page range and fit
                                                    print card (A2UI, hash-bound) ── owner approves
                                                    print worker → Windows spooler and driver → printer
                                                    job status / cancel ← winspool (own job only)
```

- **One intermediate.** Every kind becomes a PDF first. The preview is rendered from exactly the pages and settings that
  will be sent. The paper can still differ by the printer's hard margins and printable area, so the preview draws the
  printable area (`PageSettings.PrintableArea`) and warns when content falls outside it (review A1-m4).
- **Settings offered**, each only when the printer reports it (A6):
  - printer;
  - page range;
  - copies;
  - orientation;
  - paper size;
  - duplex;
  - colour or monochrome;
  - fit to page or actual size;
  - collate.
- **Approval.** The print card is a row in the generalized approvals table (rev 3.1 §5.1) with `subject_kind = 'print_job'`.
  - It goes through the existing `office.apply_change` / `office.reject_change`. **No new A2UI action.**
  - The hash binds the PDF's SHA-256, the page list, the printer name, every setting, and the printer's capability
    snapshot.
  - If the printer goes offline or its capabilities change before approval, the card is stale and must be shown again.
- **Submission.** `uri_office/workers/print_job.ps1` uses .NET Framework `System.Drawing.Printing.PrintDocument`, which is
  built into Windows. It sets the printer, copies, landscape, paper size, duplex and colour from the approved settings,
  then draws the approved pages as WinRT rasters, one page at a time.
  - All parameters arrive as JSON on stdin, never as command-line arguments (review A1-m2).
  - The document name is `URI Office <job token>`. It contains no file name, because print servers and printer logs
    record it (review A1-m2).
  - **Raster resolution and memory are decided by spike S11, not assumed (review A1-M5).** An A4 page at 600 dpi is
    about 4961×7016 px, roughly 139 MB as 32-bit colour, and the spool holds every page. S11 measures, per page at
    300 and 600 dpi in colour and monochrome:
    - worker memory;
    - spool file size;
    - time.

    S11 then sets a default (expected 300 dpi), a per-job spool budget (a job over budget is refused with "Print fewer
    pages at a time"), and the Job Object memory limit for `print_job.ps1`. Running S11 against Microsoft Print to
    PDF needs OD-U13.
  - **Approval apply only enqueues the job** and returns, so no print work runs inside the approvals lock (review A1-m6,
    same rule as round-2 N2).
- **Progress and cancel.** `winspool` `EnumJobsW` finds the job by token document name, owner (the current user) and
  submit time (printing, spooling, paused, error, offline, paper out). A job that leaves the queue before it is ever
  seen, or that a driver renamed, is shown as **"Sent; status unavailable"**, never as printed (review A1-m3). Cancel
  uses `SetJobW(JOB_CONTROL_DELETE)` on **that job only**. URI never touches other jobs or queues.
- **Trade-off, stated.** The output is raster, not vector. Text is printed at the printer's resolution (≤ 600 dpi), which
  is adequate for office documents, but spool files are larger.
  - The vector alternative is WebView2 `PrintAsync` on a PDF. It would change the native WebView2 plugin, so it is not
    planned. It is recorded as R-P3 for a later decision.
- **The Brain's role.** The intent `print` opens the print card with the default printer preselected. The Brain never
  submits, never picks a non-default printer by itself, and never changes settings without the card showing them.

## A5. Phase structure: O2 and O2P are separate

| Phase | Scope | Depends on | Qualification |
|---|---|---|---|
| **O2** (rev 3.1 plus A3) | Workspace, engines, validation, workflows, PDF viewing, Save as PDF for the three Office kinds, intent routing | G1 | Its own matrix (rev 3.1 §12 plus A8 rows P-1 to P-6). It does not include printing. |
| **O2P printing and devices** (new) | `uri_devices` (A6), print preview, print card, print worker, job status and cancel, the "Connect a printer" onboarding | O2's raster worker and approvals contract, frozen at O2 contract time. It can be built in parallel once that contract freezes, and integrates after O2. | Its own plan section (this amendment), its own review, and its own live matrix (A8 rows PR-1 to PR-12). It does **not** inherit O2's qualification, and O2 does not depend on it. |
| O3 Word | unchanged | O2 | unchanged |
| **O4 PDF intelligence** (reduced) | Extraction (pypdf, OCR), summarization, page-cited Q&A, related-notice detection | O2 | Page citations resolve to the right page. "Not found" when nothing is cited. The original PDF stays byte-identical. |
| O5 PowerPoint | unchanged | O2 | unchanged |
| O7 cross-application | PDF → Excel tables waits for OD-U11. PDF → Word and PDF → presentation stay; they read PDFs and write new files. | O3–O5 | unchanged |

**Integration recommendation (unchanged in spirit).** The first useful release is O2 + O3, with O2P when it has
qualified. Each phase keeps its own qualification record and independent acceptance. A combined integration is an
owner decision at G6.

## A6. Device discovery (`uri_devices/`, new top-level package, not protected)

The design is small on purpose. There is one provider, printers, behind an interface a scanner provider can implement
later.

| File | Role |
|---|---|
| `uri_devices/model.py` | `Device {id, kind, name, connection: usb\|network\|virtual\|unknown, is_default, status: ready\|offline\|error\|busy\|unknown, status_detail, capabilities: dict, first_seen, last_seen}` |
| `uri_devices/provider.py` | `DeviceProvider` protocol: `kind`, `list() -> [Device]`, `capabilities(id)`, `status(id)`. A registry maps kind to provider, and only `printer` is registered. A future `scanner` provider (Windows WIA 2.0, built into Windows) implements the same protocol. |
| `uri_devices/printers.py` | `ctypes` winspool only: `EnumPrintersW(level 2, LOCAL\|CONNECTIONS)`, `GetDefaultPrinterW`, `DeviceCapabilitiesW` (papers, duplex, colour, copies, orientation, collate), status and attribute bits (`WORK_OFFLINE` 0x400, `NETWORK` 0x10, `PRINTER_STATUS_OFFLINE` 0x80, `ERROR` 0x2, `PAPER_OUT` 0x10). Ports `PORTPROMPT:`, `nul:` and `FILE:` are classified as `virtual`. |
| `uri_devices/known.py` | `<state>/devices/known.json` (ACL-restricted): device id, name and first or last seen time. It holds no document data. It separates "installed and known" from "new since URI last looked". |

The **service host** is the existing Office service. Routes:
- `GET /devices/printers`
- `GET /devices/printers/<id>`
- `POST /devices/refresh`

The UI never calls winspool itself.

Interpretation of **"integrated with the URI harness"** (OD-U12): this amendment reads "harness" as the URI host
runtime: the loopback service, A2UI approvals, the UI-state controller and the companion. It does **not** mean the
M38 agent `HarnessRunner`. Exposing printing to the main Brain as a Core capability would need a descriptor under
`uri_core/external/descriptors/` and a registry change. That is a protected path, needs an owner decision, and is not
planned.

**Permissions:**
- Listing devices is read-only and local, so no prompt is needed.
- Each print job needs its card.
- Device discovery never probes the network itself. Finding a network printer that is not yet installed is handed to
  Windows (next list).
- There is no driver install, no adding or removing of printers, no default-printer change, and no change to printer
  properties. Each would need separate owner approval and is not planned.

**Onboarding: "Connect a printer".**
1. Steps for turning the printer on and connecting it by USB or the same network.
2. **Open Windows Printers & scanners**, which launches `ms-settings:printers` after an explicit click. Windows does any
   discovery, driver install or elevation in its own UI, with its own prompts.
3. **Check again**, which re-lists printers and shows new ones with a "New" badge.

If the list has only virtual printers, the card says so plainly ("No physical printer found").

## A7. Security additions

| Item | Rule |
|---|---|
| Worker scripts | `winrt_raster.ps1`, `print_job.ps1` and `pdf_text.py` are listed in `engines.json` with their SHA-256. Before every start, the service reads the script bytes, checks the hash, and writes those exact bytes to a new file in the ACL-restricted `<state>/run/`. It runs that copy, which closes the swap window between check and run (review A1-m1). They run with `-NoProfile -NonInteractive -ExecutionPolicy Bypass -File <copy>` (PowerShell; the policy flag affects only that process) or `python -I <copy>`. A script that fails its hash is never run. Spike S10 also checks PowerShell Constrained Language Mode (AppLocker or WDAC), under which `Add-Type` and WinRT fail; if CLM is active, the preview becomes unavailable with a named reason (review A1-n1). |
| Print scope | Only the approved PDF, pages and settings. Document names are unique, and cancel acts only on that job id. |
| Printer names | Treated as untrusted text (a network printer can carry any name). They are shown as text, never interpreted, and quoted in A2UI. |
| Content exposure | The print spool holds the rendered pages. That is inherent to printing. The card says "Pages are sent to <printer> through Windows". |
| Network printers | The spooler sends data to the printer, and URI makes no network connection of its own. Printing to a network or shared printer **does send the pages off this PC**. The print card shows the connection type and the server name ("Network printer on \\\\server"). The owner's approval of that card is the only exception to rev 3.1 Q8, "nothing is shared" (review A1-m5). |
| No silent printing | Every job, including a repeat of the same file, needs a new card. |

## A8. Live qualification additions

O2 rows (no printing):

| Id | Check | Br | Ow | Now |
|---|---|---|---|---|
| P-1 | Save as PDF for Word, PowerPoint and Excel J fixtures. Reopen each PDF in the Office viewer. Page images match the source preview. No overwrite. | no | no | runnable |
| P-2 | PDF viewing: navigate, zoom at 110/200/300 dpi, outline, search (correct page, "no matches" case) on a 60-page tender PDF and a scanned PDF | no | no | runnable |
| P-3 | Source-grounded PDF intelligence (O4 scope) | yes | no | **Not O2.** O4. |
| P-4 | Hostile and malformed PDF corpus: the worker is killed, the service survives (AC-O2-20) | no | no | runnable |
| P-5 | Performance: WinRT page render, pypdf extraction and LibreOffice conversion, with CPU and RAM for both workers | no | no | runnable |
| P-6 | Excel Save as PDF is refused while unsaved changes exist. After a save, the PDF matches the file:<ul><li>one PDF page group per printed sheet;</li><li>every cell value in the print area appears in the PDF text (pypdf), with formatted numbers as shown;</li><li>nothing outside a defined print area appears.</li></ul> | no | no | runnable |

O2P rows (printing), with their own qualification record:

| Id | Check | Br | Ow | Now |
|---|---|---|---|---|
| PR-1 | Discovery: the list matches Windows Settings (names, default, virtual or physical). Refresh shows a newly added printer as New. | no | no | Runnable with the existing virtual printers. **Physical USB or network printer: NOT VERIFIED** (none installed on this PC, 2026-10-15). |
| PR-2 | Capabilities: duplex, colour, papers and copies match `DeviceCapabilitiesW` and .NET `PrinterSettings` | no | no | Virtual printers only. Physical: NOT VERIFIED. |
| PR-3 | Print preview equals the pages to be printed (range, orientation, paper, fit) | no | no | runnable |
| PR-4 | Card binding: a changed setting, file or printer state makes the card stale; replay is refused | no | no | runnable |
| PR-5 | Submission to **Microsoft Print to PDF**, with output to a test folder. The result is compared page by page with the preview. | no | no | **Needs OD-U13** (whether a virtual-printer job is allowed). Never counts as physical print qualification. |
| PR-6 | Physical print: copies, duplex, colour, paper, page range | no | **yes** | **NOT VERIFIED.** Needs a physical printer and the owner's explicit authorization for each run. |
| PR-7 | Job progress and cancel on a physical job | no | yes | NOT VERIFIED (as PR-6) |
| PR-8 | Offline or unavailable printer: status shown, nothing submitted, recovery advice | no | yes | Fake status bits in tests. A real offline printer needs a printer, or an owner-approved "use printer offline" setting change: **NOT VERIFIED.** |
| PR-9 | Printer error mid-job (paper out, jam): status and recovery | no | yes | NOT VERIFIED (physical) |
| PR-10 | "Connect a printer" onboarding: the copy, the Settings handoff, Check again | no | yes (UX) | Scripted part runnable. Owner session pending. |
| PR-11 | Intent "print this": the card opens and nothing prints without approval | partly | no | Deterministic phrase runnable. Brain phrasing in the GPU window. |
| PR-12 | Repeat and regression: 5 previews and cards. Excel, O2 and A2UI suites unchanged. | no | no | runnable |

Rule: O2P qualification is reported as **PARTIAL** unless PR-6 to PR-9 pass on a physical printer under owner
authorization. A virtual printer or mocks never give full print qualification.

## A9. Gates and owner decisions after this amendment

| Id | Item | State |
|---|---|---|
| G0 | Plan approval | Conditionally approved by the owner. It becomes effective after the amendment review accepts. |
| G1 | O2 implementation (not O2P) | Conditionally approved. It activates after G0 is effective. Licensing is resolved without any install (A2). |
| G1P | O2P implementation | Activates with G1, on the strength of this amendment review. OD-U12 and OD-U13 gate only the PR-5 and PR-6 rows, and S11 when run against a printer. |
| OD-U3 | PyMuPDF AGPL | **Withdrawn** for Office (A2) |
| OD-U3b | pypdfium2 install, only if Windows.Data.Pdf fails a row | Open, not needed now |
| OD-U7 | Synthetic fixtures | **Settled** by the owner ("Use synthetic administrative documents") |
| OD-U11 | PDF tables → Excel: keep it, using an MIT table extractor (pdfplumber, which needs an install), or drop it | Open. The capability stays `planned`. |
| OD-U12 | Meaning of "URI harness" for printing (A6 interpretation), and any later Core capability registration | Open. The A6 interpretation is used until answered. |
| OD-U13 | May automated tests submit jobs to Microsoft Print to PDF? | Open. Recommended yes: no paper, no external effect, output to a test folder. |
| OD-U14 | Core's own PyMuPDF dependency (`pdf_reader.py`) | Awareness only. Outside the programme. |
| GPU window, owner live check, physical print authorization, G5, G6, G7 | unchanged from rev 3.1 §15 | pending |

## A10. Excel save timing gap (investigated separately, no code change)

Read-only finding at `5b958da0`:
- **Save As over an existing Excel file** (`service.py:497-507`): `dest.exists()` is checked, then
  `xlsx_patch.patch → atomic_write → os.replace` (`xlsx_patch.py:296`). `os.replace` overwrites. A file created at
  that name between the check and the write would be replaced. The destination's real path is also not re-checked at
  write time. A junction swapped into the parent folder after the grant would redirect the write.
- **New workbook from files** (`xlsx_new.py:72-90`): `os.link` refuses an existing name, so this path cannot
  overwrite. The real path is still not re-checked.
- **In-place save:** replacing the file is intended, and a backup is taken (`service.py:503-506`).

Severity: Low. It needs a racing process under the same user. The repair would use the same pattern as O2 (rev 3.1
§5.1 output write): a real-path re-check and a rename that does not replace. That changes accepted M1/M2 code, so it is
**not done**. It is listed as owner decision OD-U15 (authorize a scoped M1/M2 repair, or accept the risk).

## A11. Risks added

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R-P1 | No physical printer on this PC, so physical printing cannot qualify | Certain until the owner provides one | PARTIAL qualification rule (A8) |
| R-P2 | Windows.Data.Pdf fails on some PDFs, or is slower on very large ones | Medium | Spike S10 corpus. The pypdfium2 fallback needs OD-U3b. |
| R-P3 | Raster printing gives larger spool files and slower jobs than vector printing | Medium | 600 dpi cap, a progress display, banding per page. WebView2 `PrintAsync` is the recorded vector alternative. |
| R-P4 | Print driver dialogs or behaviour differ by vendor | Medium | Only `PrinterSettings` and `DeviceCapabilities` fields are used. No vendor dialog in O2P. |
| R-P5 | PowerShell 5.1 as a worker runtime (policy, profile, AMSI scanning) | Low | `-NoProfile -ExecutionPolicy Bypass -File`, hash-checked scripts, measured start-up (about 1.4 s once) |
| R-P6 | Search without hit highlighting is a weaker UX than PyMuPDF's | Low | Page list and jump. Highlighting depends on S9. |

## A12. Self-review against A0

| # | Result |
|---|---|
| AA1 | Met. A1 lists what is kept and what is removed. Tables are open as OD-U11. |
| AA2 | Met. A2 measurements. The Core PyMuPDF dependency is noted as OD-U14. |
| AA3 | Met. No install. pypdfium2 is only a named fallback (OD-U3b). |
| AA4 | Met. A4: one PDF path, `.NET` printing and the winspool spooler, the existing approvals, no paid service |
| AA5 | Met. A6: one provider, and a protocol a scanner provider can implement |
| AA6 | Met. A3 header buttons. B1 unchanged. Approvals reused. |
| AA7 | Met. A5: O2 and O2P are separate, with their own matrices |
| AA8 | Met. A8 maps the owner's items: creating, opening, editing and saving (rev 3.1 plus O3); fidelity B1; PDF conversion P-1; viewing and intelligence P-2 and P-3; discovery PR-1 and PR-2; preview and approval PR-3 and PR-4; real print PR-6; cancel PR-7; offline PR-8; onboarding E-items and PR-10; natural language C1 and PR-11; cross-application I; performance H and P-5; repeats L and PR-12; Excel L1 and L3; integrity G1 |
| AA9 | Met. A3 maps each changed rev 3.1 section. Approvals use `subject_kind` from §5.1. Worker isolation is kept. |

Review of A1 at `62cdb877` (separate Claude reviewer): **REVISE (narrow)**, licensing resolved. Repaired in A1 rev 2:
- majors A1-M1 to A1-M7 (A1-M6 in the rev 3.1 overlay table in A3 and the programme plan matrix);
- minors A1-m1 to A1-m8;
- notes A1-n1 to A1-n3, which were kept as written.

Issues repaired in this self-review:
1. Print was first placed inside O2. It was split into O2P, so O2 can qualify without a printer.
2. A virtual-printer job was first listed as runnable. It is now gated by OD-U13, because the owner forbade "real
   printing" and a virtual job is still a spooler submission.
3. "Search" first promised hit highlighting, which pypdf cannot support as measured. It is now page-level, with S9.
