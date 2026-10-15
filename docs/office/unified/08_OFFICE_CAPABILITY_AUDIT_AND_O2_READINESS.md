# URI Office: capability audit, O2 readiness repairs and qualification (owner directive 2026-10-15, evening)

Date: 2026-10-15. Status: **record in progress; live qualification section §7 is filled from run evidence only.**
Nothing here is merged, frozen, pushed or deployed.

## 0. Acceptance criteria (defined before the audit)

1. Every capability status names the code that implements it (file, function or capability id) and the evidence
   class: `IMPLEMENTED + LIVE VERIFIED` only with a real-app (production `main()`) run or an owner-approved PC live
   check at a named commit; tests alone give `IMPLEMENTED + NOT LIVE VERIFIED`.
2. Viewing never counts as authoring. A capability listed `planned:*` in `uri_office/capabilities.py` is `PLANNED`.
3. Each O2 defect (B1–B5 of the directive) has: root cause from code, repair commit or reason for none, test that
   fails before and passes after where possible, and live evidence or an explicit NOT VERIFIED.
4. Defects found during this audit that the directive did not list are reported with the same discipline.
5. Earlier conclusions disproved here are recorded as corrections, not overwritten.
6. Owner decisions are listed separately and only where code, research or tests cannot settle them.

## 1. Branches, commits and workspaces

| Item | Value |
|---|---|
| O2 line | `phase/uri-office-u-2-a` (worktree `uri-office-u2-a`). Reviewed code `b4ea0fae` (Codex ACCEPT r7). New since: `b610d6f2` (C1-1), `37008af0` (B4/O2-RT-1), `37f79f91` (UI-NOTIFY-1) |
| Excel repair line (isolated, from `5b958da0`) | `repair/uri-office-xlsx-brain-clarify-20261015` (worktree `uri-office-xb1`): `eec674af` (M2-XB-1), `87c7b1eb` (XF-1) |
| Readiness candidate (both lines merged, for live runs only) | `candidate/office-o2-readiness-20261015`: `6ec29f39` (r1/r1b), then `2b6ee110` |
| Live workspace | `D:\uri-dev\uri-o2r-live-20261015` (candidate, materialized runtime, harness, evidence). Fixtures under `C:\Users\cheta\uri-o2r-fixtures` (see UX-ROOT-1) |
| Canonical | `7d3d0f63` (DL3 + 3A). Office M1/M2/O2 are **not** in canonical |

## 2. Capability matrix (what a user can actually do in the URI UI)

Legend: **LV** implemented + live verified (real app, named run); **NLV** implemented + not live verified; **PART**
partially implemented; **PLAN** planned (capability id `planned:*`); **MISS** missing (no code, no plan entry);
**BLK** blocked; **OFF** implemented but disabled by default.

### 2.1 Excel (`uri_office/xlsx_*.py`, `draft.py`, `brain.py`, `ops.py`; page `uri_ui/office_web`; panel `office_panel.dart`)

| Capability | Status | Evidence / code |
|---|---|---|
| Open local .xlsx in the workspace (WebView2 Univer page, hash-locked bundle) | LV | O2 r7 J10/J11 (`b4ea0fae`) |
| Type values / formulas in cells; draft with undo/redo | LV (harness) | M1/M2 PC live checks 2026-10-12 (`office_live_check.dart`, real service + WebView2, not production `main()`); production-main typing NOT VERIFIED (WebView2 content is not drivable by Flutter `WidgetTester`) |
| Save (approval card, hash-bound) / Save As (no clobber, OD-U15 repair) | LV (harness) / NLV | M1 live check; OD-U15 repair `69146ea4` not merged here |
| Formatting (bold, colours, number formats, borders, merges) | **MISS → was silently lost (XF-1)** | toolbar visible (`header: true`), page reports values/formulas only; repaired to "not applied, owner told" in `87c7b1eb`; real saving of formatting = future Excel phase |
| Insert/delete/move rows or columns, sort, add/rename sheets in a local file | MISS (refused with message) | `guard.js` STRUCTURAL_COMMANDS; `ops.py` insert/delete rows = Google only |
| Brain: set values / formulas from an instruction, change cards, accept/reject, approval | LV (harness, M1/M2); **FAIL in real app r7 (M2-XB-1)** → repaired `eec674af`; real-app re-check §7 |
| Brain: new workbook from several files with roles (M2) | LV (harness, M2 2026-10-12) | |
| Brain: check working file against references (findings + fixes) | LV (harness, M2) | |
| Excel → PDF | LV | O2 r7 J14 |
| Google Sheets open (read), edit a copy, share via Google | NLV for O2 app; M1 live (deferred owner) | OFF-O1: write scope not granted |
| Tables (ListObjects), charts, pivots | kept, not shown or edited | `kept_not_shown` in workbook view |

### 2.2 Word (DOC/DOCX)

| Capability | Status | Evidence / code |
|---|---|---|
| Open DOCX (sanitize, LibreOffice render, WinRT raster), page through, zoom, outline | LV | r7 J04/J05 |
| Open legacy .doc | MISS | `KIND_SUFFIX`/inputs list docx, pptx, pdf only |
| Headers, footers, tables, images, pagination | shown in the render only (LV as part of preview) | no structure model |
| Create a new document | PLAN (`write_document`, O3) | capabilities.py |
| Edit an existing document (text, styles, tables, images, header/footer) | PLAN (`edit_document`, O3) | no edit method in `document_controller.dart` |
| Brain drafting / rewriting / proofreading | PLAN (O3); answers "not available yet" | r7 B5 "fix the spelling" → planned |
| Save DOCX | MISS (nothing to save) | |
| DOCX → PDF | LV | r7 J12, J18 (reopened, page count equal) |
| Outside Office: Core M19 `generate_document` one-shot DOCX/PPTX from chat | NLV in this program | canonical `uri_core/tools/generate_document.py`; markdown → default template; no editing; PDF path uses PyMuPDF |

### 2.3 PowerPoint (PPT/PPTX)

| Capability | Status | Evidence / code |
|---|---|---|
| Open PPTX, slide preview, navigate, chart slide renders | LV | r7 J06/J07 |
| Open legacy .ppt | MISS | |
| Create a presentation | PLAN (`make_presentation`, O5) | |
| Add / delete / duplicate / reorder slides; edit text, images, shapes, tables, charts; layouts; templates | PLAN (`edit_presentation`, O5, added `b610d6f2`) / MISS for direct manipulation | no PPTX writer in `uri_office` |
| Brain presentation generation / modification | PLAN (O5) | r7/r1 corpus: "shorten it" (pptx) now kind-checked (C1-1) |
| Save editable PPTX | MISS | |
| PPTX → PDF | LV | r7 J13 |

### 2.4 PDF

| Capability | Status | Evidence / code |
|---|---|---|
| View, page navigation, zoom (WinRT raster worker) | LV | r7 J08/J09 |
| Text search (pypdf text worker), no-match message | LV (r7, but on the system interpreter: O2-RT-1) → packaged runtime §7 | `workers/pdf_text.py` |
| Outline | LV (shown) | |
| Text extraction as a user feature (copy/export) | MISS | text used for search/outline only |
| Ask / summarize (Brain) | PLAN (`ask_pdf`, `summarize_pdf`, O4) | r7 B5 → "not available yet" |
| Tables → Excel | PLAN (deferred, OD-U11) | |
| Annotation, editing, assembly, forms | removed by owner (amendment A1) | |
| PDF generation | via conversion only (LV) | |
| Printing (O2P) | OFF (implemented, `--enable-printing`; physical print NOT VERIFIED) | deferred by owner |

## 3. O2 defects (directive B1–B5) and new findings

| ID | Root cause (code) | Repair | Ownership | Tests |
|---|---|---|---|---|
| **B1 M2-XB-1** | Brain answer schema had only `message` + `ops`; `OfficeBrain.plan()` kept every op, so "this is ambiguous" and an op over B5 could arrive together (r7) | required `status: propose | clarify | cannot` after `message`; only `propose` drafts; missing/unknown status = `BRAIN_OUTPUT_INVALID`; prompt: never overwrite cells holding data unless asked (`eec674af`) | Excel line, isolated from O2 (OD-U15 spirit) | 13 new (`tests/office/test_xb1_brain_status.py`); office+a2ui 494 passed |
| **B2 C1-1** | closed intent set had no "change a presentation" intent, so stage 2 picked the Word-only `edit_document` | planned `edit_presentation` (O5); stage-2 kind check: an intent acting on the active file whose inputs exclude the active kind → clarification `KIND_MISMATCH` (`b610d6f2`); corpus expectation unchanged | O2 | 11 new in `test_intent.py`; office_u2 206 passed |
| **B3 O2-RT-1** | runtime venvs drifted from `requirements.txt` (pypdf declared since the first commit, missing in every venv) | materializer checks `pypdf, docx, pptx, openpyxl, lxml` in the runtime's own interpreter and refuses otherwise; `--wheel` installs a local wheel into the runtime copy only (pypdf 6.19.0, sha256 `7e5d6e73…8d14`) (`37008af0`) | O2 (packaging) | 4 new; negative materialization refused `RUNTIME_DEPENDENCY_MISSING:pypdf` |
| **B4 packaging** | materialized runtime had no `uri_office`, so the app (manifest `source_root`) could only start Office with dev overrides | Office paths + device provider + tests join the materialized new paths (`37008af0`) | O2 (packaging) | live §7 without `URI_OFFICE_PYTHON/SOURCE` |
| **B5 cancel** | not a code defect found by inspection; never driven in the UI | new journey J20d (Run, then Cancel while `running`, check no output, re-plan) | O2 | live §7 |
| **XF-1** (new) | Univer toolbar applies formatting; page sends only values/formulas; service saves only those → formatting shown then silently lost | page does not apply formatting and says so; merges refused (`87c7b1eb`); saving formatting = future Excel phase | Excel line, isolated | JS 20 passed (real Univer engine test), page canary 19 passed, Flutter office 31 passed |
| **UI-NOTIFY-1** (new; **correction** of the r7 record) | `OfficeWorkspace` set the scope's Office target during build and dispose → 3 Flutter framework assertions in r7 and r1b logs; `07_O2_REAL_APP_QUALIFICATION.md` did not mention them | changes deferred to a safe frame phase with identity checks (`37f79f91`) | O2 | new widget test fails before (same assertion), passes after; Flutter 602 passed |
| **UX-ROOT-1** (new) | Office opens files only under the user home (M1 AC7 default `--allow-root`); the app offers no way to add another folder or drive; a file on D: gives "URI cannot use that location." without saying why | none yet (policy is owner-approved M1 AC7) | owner decision OD-R1 | found by r1b (fixtures on D:) |
| **CX-1** (new, found by the first real-app Cancel, r2) | after Cancel the task view drew output pages whose work files were removed (endless spinners), the conversation never said "cancelled", and `outputPage` cached an HTTP 202 as empty (a page not drawn yet could never load, for any task) | cancelled text and no pages; no caching of empty results; pages wait up to 3 min, then "not ready yet" with Try again; one outcome rule (Codex R4-R7, below) (`c24c7435`, `91a85414`, `e262b063`, `b0144dfe`, `9f07248a`) | O2 | 12 widget/unit tests, each shown failing on the previous commit |
| **NOOP-1** (new, live Brain r3) | the Brain restated unchanged cells (A5 "Travel", C5 22100) next to the real change B5, so one change showed as three cards | restated cells dropped inside `plan()` before the overlap check; cells with a pending proposal never count as unchanged; exact number equality (`60bcc5d8`, `68ea3afc`, `50f6f7be`, `fdbc2ad5`, `d3542134`, `59ba27bd`) | Excel line | 7 tests in `test_xb1_brain_status.py`, each failing first |

**Correction (M2-XB-1 description in `07_O2_REAL_APP_QUALIFICATION.md` section 5).** The budget fixture already has a
**Travel** row (row 5: Travel 60000 / 22100; Digitization is row 3). r7's "B5 60000 -> 25000" was therefore an update
of the existing Travel row, not an unrelated cell. The defect itself stands as recorded: the message called the
request ambiguous while the same answer drafted a change. In r3 (after `eec674af`) the live Brain answered "I will
update the 'Travel' row ... If you strictly meant to insert a new duplicate row, please clarify", with the matching B5
change card: message and draft agree, and nothing is applied without approval. Whether such a request should always
clarify first is an owner preference (OD-R2), not a defect.

**Correction (r7 test log).** r7's Flutter log contains 3 framework assertions (UI-NOTIFY-1) that the 07 record did not
mention; the r2 and r3 logs contain none.

### 3.1 Independent review (Codex CLI `gpt-6-sol`, read-only sandbox, via codex-exec)

| Round | Exact commits | Verdict | Findings -> repair |
|---|---|---|---|
| R1 | O2 `b610d6f2`, `37008af0`, `37f79f91` (base `b4ea0fae`); Excel `eec674af`, `87c7b1eb` (base `5b958da0`) | REVISE | R1-1 MAJOR column width / row height not guarded -> `91715e8c`; R1-2 MAJOR two workspaces sharing a controller cleared the target -> `44cb32e9`; R1-3 MINOR `--wheel` accepted any wheel -> `44cb32e9` |
| R2 | `91715e8c`, `44cb32e9` | REVISE | R2-1 MAJOR `paste-col-width` and width/height mutations -> `259fae84`; R2-2 MAJOR claims per scope -> `da8efb2b`; R2-3 MINOR wheel version -> `da8efb2b` |
| R3 | `259fae84`, `da8efb2b` | ACCEPT WITH FINDINGS | R3-1 MINOR prerelease wheels -> `6abccf9c` |
| R4 | `6abccf9c`, `c24c7435` (CX-1) | REVISE | saved view requested deleted pages; 8 s page cut-off; "Cancelled" said while still running -> `91a85414` |
| R5 | `91a85414` | REVISE | poll/cancel races; failed-on-cancel left "Stopping" -> `e262b063` |
| R6 | `e262b063` | REVISE | 5 interleavings (late replies, plan reply, resume, task switch, growth) -> `b0144dfe` |
| R7 | `b0144dfe`, `60bcc5d8` (NOOP-1) | REVISE | off-screen outcomes, plan-reply message, revisit; NOOP vs pending proposals; float rounding -> `9f07248a` (one outcome rule replaces the per-path checks), `68ea3afc` |
| R8 | `9f07248a`, `68ea3afc`, merge `6b20e554` | REVISE | R8-1 no-op filtering after the overlap check lost a real change -> `50f6f7be` (R7 controller findings closed) |
| R9 | `50f6f7be`, merge `b77cbda6` | REVISE | R9-1 reverse order silently dropped -> `fdbc2ad5` |
| R10 | `fdbc2ad5` | REVISE | R10-1 clear then restore -> `d3542134` |
| R11 | `d3542134` | REVISE | R11-1 a refused op marked its cells touched -> `59ba27bd` |
| R12 | `59ba27bd` and the whole change set (tip `76b0f600`) | **NO RESULT** (Codex usage limit; resets 00:32 IST) | see section 7 |

Process note: R4-R7 kept finding new interleavings in the same task-outcome code because each path had its own checks;
`9f07248a` replaced them with one rule, after which R8 found nothing further there. R8-R11 were narrow edge cases of
the NOOP-1 filter, each closed with a failing-first test. Codex could not run pytest, Flutter or the Univer Node tests
in its sandbox; test totals are the author's.

### 3.2 Gates

At `bc054574`: `tests/office` + `tests/a2ui` 496 passed, 5 skipped; `tests/office_u2` + `tests/devices` 235 passed;
governance materializer 28 passed; page JS 20 passed; Flutter 604 passed, 5 skipped; analyze 4 pre-existing infos.
At the final tip: section 7 (r4) and `evidence/gates-76b0f600.txt` (D:).
`tests/phase2a/test_frozen_core.py` fails 3 tests on this branch and identically at `b4ea0fae` (valid only inside a
materialized runtime); not a regression.

## 4. Runtime packaging and dependencies

- requirements.txt declares pypdf, python-docx, python-pptx, openpyxl; lxml arrives with python-docx/python-pptx.
- Source venvs (`uri-agent/.venv`, `uri-ws-hard/.venv`) lack pypdf. They were **not** changed (shared by other
  sessions). The runtime copy gets the wheel at materialization; the receipt records its hash.
- Between 22:00 and 22:12 IST another session freed C: (0 → 80 GB) and `uri-ws-hard\.venv` (the venv earlier
  runtimes were copied from) disappeared. The `bc054574` runtime is materialized from `uri-agent\.venv` (same
  Python 3.13.15; receipt `venv_source`). Not changed by this session.
- The UI page bundle is not part of the runtime (it ships next to the app exe, `data/office_page`, hash-checked);
  live runs use `URI_OFFICE_PAGE_DIR` with the verified bundle of the commit under test.
- Office engines (LibreOffice 26.8.1.1 user-folder extract, signer-pinned) stay under `%LOCALAPPDATA%\URI\engines`.
- Integration item (unchanged): the working-system launcher does not start Office; the app does, on first use.

## 5. Brain / GPU coexistence (Phase D)

Measured, no runtime/model/scheduler change, no stress test:

| Run | Brain after load (dedicated / non-local MiB) | Brain alone tok/s | Event | After event |
|---|---|---|---|---|
| r7 (`b4ea0fae`) | 15 601 / 1 121 | 123–125 | app exe launched 14:03:35–39 UTC (first frame) | 14 828 / 1 894 within one 10 s sample; app open 38.8–39.1, app + Office 39.4–39.6 tok/s; still 14 828 / 1 894 after the app exited |
| r1b (`6ec29f39`) | 14 992 / 1 730 (demoted during load itself; free 492 MiB) | 119–122 | app used 80 MiB; journeys stopped early (UX-ROOT-1) | no further demotion while the app was open; no app-open bench (journeys never reached B5) |
| r2 (`bc054574`) | 15 602 / 1 121 | 118-119 | app first frame about 16:58:00 UTC (80 MiB; build 37.8 s) | 14 828 / 1 894 (identical to r7); **after the app exited: 39.1 tok/s** with 648 MiB free |
| r3 (`4a179be4`, Brain mode) | same pattern | 116-118 | app open | app only 33.6-38.0; app + Office 38.5-38.6; after the app exited 39.2-39.3 |
| r4 (`76b0f600`, Brain mode) | **14 992 / 1 730** (demoted during load; free 500 MiB) | 120-122 | app open, up to 473 MiB | **no further demotion**; app only 119-120; app + Office 113-119; after the app exited 122-123 |

Findings:
1. The 123 → 39 tok/s drop in r7 coincides with the app's first GPU allocation (~300 MiB), not with Office (Office
   added nothing measurable, as recorded in r7).
2. Non-local MiB alone does not predict speed: r1b ran at 120 tok/s with 1 730 MiB non-local; r7 ran at 39 with 1 894.
   Which allocations Windows demotes matters (WDDM residency), so the trigger is the moment of pressure, not a size.
3. **Two load-time placements, and the placement decides the speed (r1b and r4 correct the earlier reading).**
   Placement A (r7, r2, r3): the Brain loads at 15 602 / 1 121 MiB; the app's first frame forces a second demotion to
   14 828 / 1 894 MiB and decode drops to about 39 tok/s, which stays after the app exits (sticky).
   Placement B (r1b, r4): the Brain is already demoted during its own load to 14 992 / 1 730 MiB (free about 500 MiB)
   and runs at 120 tok/s; the app (up to 473 MiB) and Office cause no further demotion, and decode stays 113-123 tok/s
   for the whole run. So the slowdown is not caused by the app or by Office as such; it is the second demotion event
   in placement A, which lands on hot allocations. Which placement occurs was not controlled by these runs (same
   commit family, same harness; RAM and other GPU users differed).
4. With Runtime v1 requesting ~15.3 GiB on a 16 GiB card, any second GPU consumer of a few hundred MiB can trigger
   this. This is the separate runtime/VRAM workstream's subject (Adaptive Runtime R1: fit-under-budget); Office should
   not try to solve it. Coordination: these timelines and sample files are the reproducible measurements to hand over
   (`evidence/live/r2|r3|r4/resource-samples.json`, `brain_bench.json`). Questions for that workstream (nothing
   changed here): what makes the driver choose placement A or B at load; whether a small fixed headroom at load
   (about 500 MiB, as placement B leaves) makes B reliable; whether starting the app before the Brain does the same.

## 6. Qualification gaps (unchanged by this work unless stated)

- Physical keyboard/mouse on a release exe: NOT VERIFIED (all runs use Flutter `WidgetTester` + real Windows dialogs).
- Owner think-aloud / visual check: BLOCKED (owner away).
- Typing and toolbar use inside the WebView2 sheet from the production app: NOT VERIFIED (Flutter cannot drive the
  page); XF-1 is verified in the real Univer engine (Node) and the headless Edge canary only.
- Printing: deferred (O2P, off).

## 7. Live qualification (real app, production `main()`, packaged runtime)

r1 (`6ec29f39`, 20:53 IST): INVALID — Flutter build failed with "No space left on device" (C: 0 GB free, PC-wide;
other sessions affected). Workspace moved to D:.

r1b (`6ec29f39`, 21:13 IST): 8 PASS / 16 FAIL — every document open failed with "URI cannot use that location."
because the fixtures were on D: (UX-ROOT-1); the Office service itself **started from the packaged runtime without
dev overrides** (J02 PASS: "Starting URI Office…", home in 0.48 s after start) — first evidence for B4. Not counted
as a qualification run. Also logged the UI-NOTIFY-1 assertions.

r2 (`bc054574`, main mode, 22:25 IST, GPU lease without override): **23 PASS / 1 FAIL**. Every Word, PowerPoint,
PDF, Excel, save, reopen, damaged-file, dialog-cancel, navigation, state, keyboard and print-off journey passed.
- **B4 verified:** the app started Office itself as `D:\uri-dev\...\runtime\.venv\Scripts\python.exe -B -I
  ...\runtime\scripts\run_uri_office_service.py run ... --brain-from-runtime` (no `URI_OFFICE_PYTHON/SOURCE`);
  `session-final.json` `office_cmdlines`.
- **B3 verified:** the PDF text worker ran on the runtime venv (`...\runtime\.venv\Scripts\python.exe -I -B
  ...pdf_text-....py`) and the search for "Clause 37" found page 37 of the 60-page tender.
- **B5:** Cancel tapped while `running` (2.47 s after Run) -> `cancelled`, no file written. The FAIL is only the
  driver's recovery step, which revealed **CX-1** (endless spinners, no message).
- UI-NOTIFY-1: 0 framework assertions (r7: 3).

r3 (`4a179be4`, Brain mode, 22:57 IST): **33 PASS / 1 FAIL**.
- J20d cancel PASS with the CX-1 feedback ("Cancelled. Nothing was saved...", 0 spinners, same line in the
  conversation).
- B5 Brain journeys PASS (email format -> plan, ready to share -> plan, send it -> clarify, fix spelling / what is this
  about -> "not available yet", continuity, concurrent).
- C1-1 live: corpus 15/16 by the harness rule; the 16th, "shorten it" (pptx), now answers `edit_presentation` ->
  "Change a presentation is not available yet (planned for presentations)", which the corpus records as acceptable
  (`also_acceptable`), so all 16 are a correct intent or an honest non-action.
- B5-excel-brain FAIL by the driver's own "no overwrite" rule, which was wrong for this fixture (correction in
  section 3); the run revealed **NOOP-1**. Driver rule for r4: every change card must change something.

r4 (final candidate `76b0f600`, Brain mode, 23:40 IST): **34 / 34 PASS**, 0 Flutter framework assertions, frozen
Brain config hash unchanged, no Office process left, lease FREE at the end.
- B4/B3 again: Office started by the app from the runtime venv; "Clause 37" -> page 37.
- Cancel while running (2.45 s) -> cancelled, no file, "Cancelled. Nothing was saved..." in the task view and the
  conversation, 0 spinners; re-plan after Back works.
- Excel Brain ("Add a row for Travel with 25000 below Digitization"): message "I will insert a new row for 'Travel'
  ... shifting the existing 'Travel' row and subsequent rows down by one ... update the SUM formulas", with matching
  change cards (row 6 = old Travel, row 7 = Maintenance, B5 = 25000, C5 cleared, totals to row 7); every card is a real
  change (NOOP-1 dropped the restated A5). Message and draft agree; nothing is applied without approval.
  **Finding XB-2 (quality, not safety):** "below Digitization" is row 4 here, but the Brain inserted at row 5, and it
  emulates an insert by rewriting cells because local files have no insert-rows op (Google only). The owner sees every
  before/after and can reject; the real fix is a local insert-rows op in a later Excel phase (owner decision OD-R3).
- Corpus: 15/16 by the harness rule, the 16th is "shorten it" -> `edit_presentation` (planned), recorded acceptable.

## 8. Status (separate states, none implies another)

- O2 readiness repairs B1-B5: implemented; B1 (M2-XB-1), B2 (C1-1), B3 (pypdf in the packaged runtime), B4 (Office
  from the packaged runtime), B5 (running-task cancel) each LIVE VERIFIED through the real app in r4 at `76b0f600`.
- New defects found and repaired in this work: XF-1, UI-NOTIFY-1, CX-1, NOOP-1 (plus 22 Codex findings R1-R11).
- Independent review: Codex R1-R11 on exact commits; R11's only finding repaired in `59ba27bd`; **R12 (final, on
  `76b0f600`) NOT RUN** because of the Codex usage limit (resets 00:32 IST). Not counted as accepted.
- Physical keyboard/mouse: NOT VERIFIED. Owner check: BLOCKED (owner away).
- Integrated: no. Frozen: no. Pushed: no. Printing (O2P): deferred and off.

## 9. Decisions that need the owner

| ID | Decision | Recommendation |
|---|---|---|
| OD-R1 | UX-ROOT-1: Office opens files only under the user home. Allow more folders/drives (for example D:) through a setting that passes `--allow-root`, or keep home-only and say so in the refusal message? | Keep the fail-closed default; add an owner-managed list of extra folders, and make the refusal say which folders are allowed |
| OD-R2 | Excel Brain on a request that conflicts with the data (a "Travel" row already exists): propose the most likely change with a note (current behaviour, consistent since M2-XB-1), or always ask first? | Current behaviour (propose + note, approval required) |
| OD-R3 | XB-2: add a real local insert-rows / delete-rows op for .xlsx (structural edit with formula/range shifting), instead of the Brain emulating inserts by rewriting cells | Yes, as its own Excel milestone with the XF-1 formatting save |
| OD-R4 | Merge order and base: the Excel repair line (`repair/uri-office-xlsx-brain-clarify-20261015`) and the O2 line both change `uri_office/service.py`/`brain.py`; the readiness candidate shows they merge (import-line conflict only) | Integrate O2 + Excel repairs together after the owner check, from the readiness candidate's two parent lines |
| OD-R5 | pypdf in the shared source venvs (`uri-agent\.venv`): install the declared requirement there too, or keep wheels at materialization only | Keep materialization-time install (no shared venv change); install in source venvs only with the owner's go-ahead |
| OD-A1..A5 | Word/PowerPoint authoring architecture, optional LibreOffice GUI hand-off, order, base, templates | See `09_WORD_POWERPOINT_AUTHORING_ROADMAP.md` §6 |
| (open from 07) | AC-O2-16 Office GPU budget wording; owner visual check; physical-input check | unchanged |
