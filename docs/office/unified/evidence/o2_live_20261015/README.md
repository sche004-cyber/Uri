# O2 / O2P live runs on the owner's Windows 11 PC, 2026-10-15

Run by Claude. **This is not the owner's check.** The owner rows (E, K2) stay BLOCKED until the owner is back.

## What ran

| Run | Tool | What it drives | Result |
|---|---|---|---|
| Service runs 1–7 | `live_service.py` | The real `python -m uri_office.service run` process (own state folder, pinned LibreOffice 26.8.1.1, WinRT raster worker, pypdf worker, `--enable-printing`) over HTTP with its bearer token. Approvals are pressed through `/a2ui/action` with the bound hash. | Run 7 (final): **36 PASS, 0 FAIL, 4 NOT VERIFIED** (`service_run7/live_result.json`) |
| UI runs 1–2 | `live_ui.py` + `uri_ui/lib/office_o2_live_check.dart` (release build) | The real Windows app: the B1 Office workspace inside the living scope, against a real service; the Excel sheet in WebView2 | Run 2 (final): **COMPLETED_WITH_RESULT**, 17 steps, 17 screenshots (`ui_run2/`) |

All documents are synthetic (`fixtures.py`): an official letter with letterhead, a 41-row office order, a notice and
corrigendum pair, a memorandum, minutes, a bilingual English and Hindi letter, a 20-page report, an 11-slide deck with a
native chart, a budget workbook with a print area, a 60-page tender PDF, a scanned PDF (image only), hostile PDFs and
the F1 canary files. The virtual-printer folder was emptied after each run (OD-U13); `Get-PrintJob` showed no job left.

## Final results (service run 7, UI run 2)

| Row | Verdict | Evidence |
|---|---|---|
| Contract o2.1 served | PASS | |
| AC-O2-6/19 engine verified before first use | PASS | First start in a new state folder: full manifest check 139 s (run 7, cold disk cache) and 18 s (run 6, warm). Once per state folder. |
| K1 open + preview: letter, order, notice, corrigendum, memo, minutes, bilingual, 20-page report, 11-slide deck | PASS (9/9) | First preview 13.9 s on a cold engine (start-up included), then 0.6–1.1 s; page image 25–60 ms |
| Deck slide count 11 = 11 | PASS | |
| U12/H1 warm 20-page DOCX first page | PASS | 0.15–0.45 s (preview cache) ; conversion itself 1.6 s |
| P-1/D1 Save as PDF: letter, order, bilingual, deck, report | PASS (5/5) | 0.6–1.6 s each; **no findings** after the font repair (below) |
| D1 no overwrite of an existing name | PASS | `DESTINATION_EXISTS` |
| P-1 reopen saved PDFs in Office | PASS | page counts equal |
| P-2 60-page PDF: zoom 440/880/1240, search (page 37), no-match case | PASS | page image 24–73 ms |
| P-2 scanned PDF: preview, honest "no searchable text" | PASS | `NO_TEXT_LAYER` |
| P-4 / AC-O2-20 hostile PDFs (empty, garbage, truncated, deep nesting) | PASS | worker fails alone; service keeps answering |
| P-6 Excel: refused with unsaved changes; saved file to PDF with the print-area values | PASS | `UNSAVED_CHANGES`, then every value present |
| F1 canaries (HTTP + SMB) through the live service | PASS | 0 hits, 0 SMB connections |
| L2 five repeats of Save as PDF | PASS | identical outcome, 2 pages each |
| B1 native chart drawn (deck slide 11) | PASS | chart labels Jun–Sep and axis in the PDF text; image `service_run7/pages/deck_p11.png` |
| PR-1 printers match Windows (`Get-Printer`), default matches | PASS | virtual printers only: Microsoft Print to PDF (default), OneNote |
| PR-2 capabilities read | PASS | 54 papers, no duplex, colour, 1 copy |
| PR-3 print preview: exactly the chosen pages, printable area | PASS | |
| PR-4 tampered and replayed print approvals refused | PASS | `BOUND_VALUE_MISMATCH`, `UNKNOWN_SURFACE` |
| PR-5 virtual printer job (OD-U13) | PASS | 2 approved pages written, no dialog; **virtual only, not physical qualification** |
| PR-5b same output file refused | PASS | |
| PR-6 physical print, PR-7 physical progress and cancel, PR-8 real offline printer, PR-9 printer error | **NOT VERIFIED** | no physical printer on this PC; needs one and the owner's authorization |
| F3 / AC-O2-5 / AC-O2-9 kill mid-run: no orphan, interrupted, resumed | PASS | 0 orphans; "interrupted at step 2"; resumed to ready |
| G1 originals byte-identical (12 files) | PASS | no new `%TEMP%` entries |

UI run 2 (`ui_run2/*.png`): Office Home with goal chips; Word preview ("Preview rendered by LibreOffice"); plan card;
task view with steps; output card; saved; "show my PDFs" (deterministic navigation, saved PDF listed); "do the usual"
(no Brain: clarification chips); 60-page PDF search jumping to page 37; print panel ("No physical printer found");
print card; "Done: the printer wrote the file"; the region at 1100, 900 and 700 px; the Excel sheet in the workspace
with the existing Excel companion; the sheet kept after switching to a document and back.

## Defects found by the live runs and repaired (all re-run)

| # | Found in | Defect | Repair |
|---|---|---|---|
| L-1 | service run 2 | The 9th open document is refused (`TOO_MANY_OPEN`, limit 8). Product behaviour, not a crash; the harness never closed documents. | Harness closes documents it is done with. UX note for the owner: the limit is 8 open documents. |
| L-2 | service run 3 | **Blank-page false positive:** a page with a two-line signature block (0.13 % ink) was called blank. | Rule changed to an absolute count (fewer than 20 ink pixels at 440 px); regression test. |
| L-3 | service run 4 | P-6 check failed on "Digitization": the fixture's default column width clips the text, and the PDF reproduces the sheet as laid out. Fixture defect, not a conversion defect. | Fixture column widths set. UX note: clipped cell text prints clipped, as in Excel; no validation check exists for it. |
| L-4 | service run 5 (visual inspection) | **The deck's native chart rendered as a broken-object icon.** Cause: `DisableActiveContent=true`, added to the hardened profile in review round 1. | Setting removed (verified: chart slide text 28 chars with it, 81 without); its protection is already in the sanitizer and canaries; engine regression test `test_native_chart_is_drawn`. |
| L-5 | service run 5 (census) | **GPU:** the WinRT raster worker holds 30–41 MB of dedicated GPU memory while alive (engine use 0 %). The A1 probe (one PDF, fresh process) had measured 0. **AC-O2-16 "no GPU use" is not met as written.** | Idle PDF workers stop after 60 s: run 7 shows 40.6 MB while working and **0 after 70 s idle**. Owner decision needed (below). |
| L-6 | UI run 1 | Conversation pane did not follow new lines; the clarification and the print card were off-screen. | The list follows the newest line or card. |
| L-7 | UI run 1 | Composer said "Ask URI to change this sheet" on Home, documents and tasks. | Hint follows the view. |
| L-8 | UI run 1 | A saved PDF did not appear under PDFs. | Saved outputs join the recent list. |
| L-9 | UI run 1 / service run 6 | **Font-substitution false positives** (Calibri, Courier, Times) for fonts named only in unused styles or the theme. | Word fonts now come from the runs and the styles actually used (with basedOn), the default style and document defaults. |
| L-10 | UI run 1 | Sheet step failed: the harness did not point at the Univer page bundle (`URI_OFFICE_PAGE_DIR`). Setup only. | Harness sets it; UI run 2 passed the sheet steps. |

## Measurements (service run 7)

- Service start 0.7 s. Idle service: 61 MB.
- During previews: service 72 MB, LibreOffice `soffice.bin` 420 MB, raster worker 158 MB, text worker 31 MB, UNO bridge
  29 MB; total about 750 MB. After conversions: about 810 MB.
- After 70 s idle: PDF workers stopped, total about 588 MB; LibreOffice (454 MB) stays until its 10-minute idle stop.
- GPU: only the raster worker uses dedicated GPU memory (29.6 MB during previews, 40.6 MB after conversions), engine
  use 0 %; 0 once it stops. LibreOffice, the service, the text worker and the bridge: 0.
- Warm conversion of a 20-page DOCX: 1.6 s in the workflow (validation and page images included).

## Not covered here (reported, not claimed)

- **Brain rows** (C1 Brain subset, H3, L1): BLOCKED, no GPU window.
- **Owner check** (E1–E7 think-aloud, K2 owner part): BLOCKED, owner away.
- **Physical printing** (PR-6 to PR-9): NOT VERIFIED.
- **Fidelity against Microsoft Office**: NOT VERIFIED (no Office licence on this PC).
- Real disk-full: NOT VERIFIED (fault injection only).
- WebDAV canary: not run (WebClient service not checked).
- The UI widths were set on the Office region inside the app window (1264 px wide); the Windows window itself was
  not resized.
- The Flutter build downloaded `nuget.exe` into the Flutter tool cache (build tooling, as in earlier phases); nothing
  was installed into Windows.
