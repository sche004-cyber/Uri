# O2 real-application live qualification (owner directive 2026-10-15, workstream B)

Date: 2026-10-15. Branch `phase/uri-office-u-2-a` (local only; nothing pushed, merged or deployed). Final code commit
tested live: **`b4ea0fae`**. This record replaces the UI part of the earlier harness evidence
(`06_O2_UI_FIRST_QUALIFICATION_GAP.md`: the old UI runs used `office_o2_live_check.dart` with `MockUriClient`).
Evidence: `evidence/o2_realapp_20261015/` (harness, per-run JSON, screenshots, Codex review record).

## 1. What "real application" means here

| Element | Used | Not used |
|---|---|---|
| App | the ORIGINAL production `main()` of `uri_ui` (`lib/main.dart` → `WorkingSystemRoot` → Living UI), debug build run by `flutter test integration_test/…` | no test shell, no `MockUriClient`, no fake Core |
| Core | real integrated paired server + worker from a runtime materialized from the tested commit (`scripts/oi_materialize_test_runtime.py`, verified by `ws_materialized_verify` before each run), installation `o2q-a`, port 18327 | the owner's legacy instance on port 8000 untouched |
| Office | the real Office service, started **by the app itself** (after repair R5-1), real LibreOffice 26.8.1.1 (pinned, signer-checked), WinRT raster and pypdf workers | — |
| Brain | real Runtime v1 (frozen config, sha256 unchanged before/after each run) through the accepted WS Brain host and the machine-wide GPU lease, **no contention override** | — |
| Input | pointer and text through Flutter `WidgetTester` on the real widgets; the real Windows file dialogs filled by `harness/dialog_helper.py` (Win32 messages to the dialog's own controls) | **physical keyboard/mouse input: NOT VERIFIED** |
| Profile | fresh per run (first-time user): APPDATA/LOCALAPPDATA/TEMP and the preference store redirected into the run's fixture folder | the owner's preferences and URI state never touched |
| Documents | synthetic administrative fixtures (letter, office order, 20-page report, 11-slide deck with chart, budget workbook, 60-page tender PDF, damaged .docx) | no owner documents |

Deviations recorded: the Office service runs on the runtime venv's **base interpreter** (system Python 3.13) from the
tested source, because every runtime venv on this PC lacks `pypdf` although `requirements.txt` lists it (finding
O2-RT-1, owner decision); the Univer page bundle comes from `URI_OFFICE_PAGE_DIR` (hash-verified by the app);
`URI_ENGINES_ROOT` points at the real engine folder.

## 2. Runs

| Run | Commit | Brain | Result | Notes |
|---|---|---|---|---|
| base1 | `ee2f2f34` (round-4 code) | no | 8 PASS, 1 PASS-with-finding, **14 FAIL** | baseline: found R5-1..R5-7 |
| r2 | `f27f6bbf` | no | 17 PASS, 6 FAIL | found R6 (Save button out of sight, false font warnings, Ctrl+K) |
| r3 | `5973583b` | no | **23/23 PASS** | |
| r4 | `6de5b32f` | yes | 29/32 | found classifier answering "unclear" for everything |
| r5 | `44ddbbe3` | yes | 30/33 | Brain speed confounded by a second app from another session |
| r6 | `61dd0470` | yes | 31/33 | clean Brain window; prompt fix 4/16 → 15/16 |
| **r7** | **`b4ea0fae`** | yes | **32/33 PASS** | final; only B5-excel-brain FAIL (M2 Excel path, §5) |

Other sessions shared the PC (FCV-R live Core qualification, fire-companion work). GPU use was coordinated through the
lease and by message; r6 and r7 had the GPU alone. CPU overlap is disclosed per run in `codex_review_O2_R5.md` and §6.

## 3. Journeys at `b4ea0fae` (run r7; first-time profile)

| # (directive B2) | Journey | Result |
|---|---|---|
| 1 | Start URI (production main, integrated worker) | PASS |
| 2 | Open URI Office (Companion → Workspace → rail "Office"; the app starts the Office service) | PASS |
| 3 | Office Home ↔ views (Recent, PDFs, Home, document, Back) | PASS |
| 4–5 | Word: open via real dialog, preview, next/next, 150 %, Fit, outline | PASS (first preview 2–3 min on first use: engine check, now explained on screen) |
| 6–7 | PowerPoint: open, 11 slides, navigate to the chart slide | PASS |
| 8–9 | PDF: 60 pages, search "Clause 37" → p. 37, 100 %, previous page, no-match message | PASS |
| 10–11 | Excel in the workspace (real WebView2 sheet) with the existing Excel companion | PASS |
| 12–17 | Word → PDF and PowerPoint → PDF: plan card → **Run** (tap) → task → findings → **Save…** → real folder dialog → output card → **Save** (tap) | PASS (no findings after R6 font repair) |
| 14 | Excel → PDF from the sheet view | PASS |
| 18 | Reopen the saved PDF in Office: 20 pages = source | PASS |
| 19 | Originals unchanged (SHA-256 of all 7 fixtures before/after) | PASS |
| 20 | Cancel/failure: plan "Not now" discards; damaged file → "This file looks damaged or unsafe and was not opened." then back to a good document; dialog Cancel opens nothing | PASS. **Cancelling a running task was not driven in the UI** (service-level F3 evidence only) |
| 21 | Office state kept after leaving to Conversation and back (same controller, 4 documents, active PDF, sheet still open) | PASS |
| 22 | Return to the main workspace | PASS |
| – | Requests in the Office URI pane: "show my PDFs" (navigates), "do the usual" (clarifies with chips), "convert this to PDF" with a PDF active ("Which file? Open a Word, PowerPoint or Excel file first.") | PASS |
| – | Printing off (no `--enable-printing`): no Print button, no Printers entry | PASS |
| – | Keyboard: Ctrl+Shift+B toggles files; Ctrl+K focuses the request box (synthetic key events) | PASS |
| B5 | Brain: "I need it in a format I can email" (docx) → plan card; "make this ready to share" (pptx) → plan card; "send it to the department" → clarification; "fix the spelling" / "what is this about" → "not available yet (planned …)"; continuity "and do the same for the report"; Office conversion concurrent with a Brain request | PASS |
| B5 | Excel Brain: "Add a row for Travel with 25000 below Digitization" | **FAIL** (see §5) |

## 4. Defects found by the real-app runs and repaired

| ID | Found | Defect | Repair (commit) | Retest |
|---|---|---|---|---|
| R5-1 | inspection + base1 | Nothing started the Office service: the real app could only say "The URI Office service is not running." | App starts it on first use (`scripts/run_uri_office_service.py`, `--parent-pid`, progress + Try again; stale `service.json` ignored) `7752469a` | r2–r7 PASS |
| R5-2 | base1 | A `MemoryError` in the start-up engine check (RAM pressure from another session's Brain load) left the engine "checking" all session: every Word/PowerPoint preview unavailable, no way back | `ENGINE_CHECK_FAILED`, retry button, document retry endpoint `fe7ed88a` | tests; r2+ |
| R5-3 | base1 | Global context panel squeezed Office below 1000 px: the Office URI pane, its hints and plan cards were hidden at the default window size | context panel starts closed in Office `fe7ed88a` | r2+ (plan cards visible) |
| R5-4 | base1 | Icon strip had no way back to an open document | open documents listed `fe7ed88a` | r2+ |
| R5-5 | base1 | Stale "damaged file" error stayed under the spreadsheet; disabled Save as PDF / goal chips gave no reason | cleared on navigation; tooltips `fe7ed88a` | r2+ |
| R5-6 | base1 | Shortcuts worked only with focus inside the workspace | global handler `fe7ed88a` | r3+ |
| R5-7 | base1 | Home did not name supported files | "Open a Word, PowerPoint or PDF file" `fe7ed88a` | r2+ |
| SEC-1 | review of R5-1 | Python's HTTP server `SO_REUSEADDR` let a second process listen on 127.0.0.1:18530 beside the service (pre-existing since M1) | exclusive bind; token written after bind `b84062cf`, `f27f6bbf` | tests |
| R6-1 | r2 | Save…/Accept buttons below findings and page images (out of sight) | actions first; "Saved as … · Open it…" (picker) `5973583b`, `6de5b32f` | r3+ |
| R6-2 | r2 | False font warnings (Arial, Symbol, Times New Roman) — partly a regression of the m6 fix | fonts only for scripts present and lists used `5973583b`, `6de5b32f` | r3+ (no findings) |
| R6-3 | r2 | Ctrl+K focused a node no field used | shared composer focus `5973583b` | r3+ |
| R6-4 | r2 | First preview took ~3 min with no explanation | first-use message `5973583b` | r3+ |
| R7-1 | r4/r5 | Stage-2 classifier (never live-tested before) answered "unclear" for every request (4/16 corpus); clarifications hid why | prompt describes intents; `brain_outcome` `44ddbbe3`, `61dd0470`, `e176bd98`, `b4ea0fae` | r6 15/16, r7 15/16 |

Also in this phase: m6 Hindi theme fonts `b54c4000`; Authenticode signer check (plan F11, 229 signed files, 15 pinned
unsigned) and WebDAV canary test `fe7ed88a`; pane-size persistence and keyboard tests `dfbc5f18`.

## 5. Open findings and limitations

| ID | Class | Finding | Status |
|---|---|---|---|
| M2-XB-1 | MATERIAL for the Excel path, **outside O2 repair scope** | Excel Brain (M2 path) answered that "Add a row for Travel with 25000 below Digitization" is ambiguous and listed options, **while the draft already showed B5 changed 60000 → 25000** (yellow, unsaved, nothing written). In r6 the same request ended `BRAIN_INCOMPLETE_LENGTH` (refused, nothing changed). Safe (draft only) but the message and the draft disagree. | Owner decision: M2 follow-up (OD-U15 forbids unrelated Excel changes in this line) |
| B5-PERF | owner decision | Brain decode 123–125 tok/s alone → **39 tok/s as soon as the URI app starts** (before Office), with Brain non-local memory 1121 → 1894 MiB (block demotion). Starting Office afterwards changed nothing measurable (39.1 → 39.6 tok/s; residency unchanged). The cause is the app + Runtime v1 on a 16 GB card (WS PERF-W1, VRAM research), not Office. | Owner decision (runtime/VRAM line) |
| AC-O2-16 | owner decision | Office GPU: raster worker 30–35 MiB while alive (stops after 60 s idle); the Office region adds ~100–150 MiB to the app's own GPU memory. | Owner decision (unchanged) |
| O2-RT-1 | owner decision | Runtime venvs lack `pypdf` (listed in `requirements.txt`); production Office would lose PDF text/search. Installing needs the owner. | Owner decision |
| C1-1 | minor | Corpus: "shorten it" (pptx) → planned edit_document (expected unclear). Answers "not available yet", no action. | Recorded |
| UI-INPUT | limitation | Physical keyboard/mouse on the release exe not exercised; dialogs filled by Win32 messages. | NOT VERIFIED |
| OWNER | limitation | Owner think-aloud / visual check (rows E, K2). | BLOCKED (owner away) |
| CANCEL-RUN | limitation | Cancelling a running task not driven in the UI. | NOT VERIFIED (service evidence only) |
| Codex MINORs | minor | O2-R5-03 (contract probe proves shape, not identity), O2-R5-04 (close during conversion not atomic with cache copy), O2-R6-02 (Han text language union), numbering lvlOverride/numStyleLink not followed, WebDAV positive control not run (needs WebClient started). Codex's final round lists no open findings; these are kept as recorded limitations. | Recorded |
| Office service start | limitation | The working-system launcher still does not start the service; the app does, from the manifest's `source_root`, which in the materialized runtime does **not** contain `uri_office` (dev overrides used). Office must join the runtime materialization at integration. | Integration item |

## 6. Measurements (r6/r7, Windows 11, RX 7900 GRE 16 GB)

- Brain start (lease, no override): READY in 217–220 s (HDD load), calibration 158–160 tok/s; frozen config hash unchanged.
- Brain decode (160-token calibration prompt, 3 runs): alone 123–125 tok/s; app open 38.8–39.1; app + Office 39.4–39.6.
- Office request with Brain (UI, end to end): 3.3–3.7 s; Stage-2 classify via HTTP: median 1.46 s (r7).
- First Word preview on a new state folder: 151–175 s (full engine check incl. signer check, once); later Word/PowerPoint previews 3.9 s; PDF 3.0–3.5 s; saved PDF reopen 2.9–3.5 s.
- Office processes at the end of each run: none left (`office_left: []`); lease FREE; Brain listener gone.
- CPU overlap: r2 overlapped the author's Flutter test run (first minutes); r6 overlapped FCV-R's runtime rebuild (18:36 IST) — latency figures in those runs are indicative only.

## 7. Independent review

Codex CLI `gpt-6-sol` (preferred auditor; it ran commands in a read-only sandbox; its pytest attempts were blocked by
the sandbox's missing temp folder, so test totals are the author's): rounds 1–7 on `fe7ed88a` → `b4ea0fae`; final
round 7 **ACCEPT** on exact commit `b4ea0fae` (source review). Record: `evidence/o2_realapp_20261015/codex_review_O2_R5.md`.

Author's suites at `b4ea0fae`: `tests/office_u2` + `tests/devices` 198 passed; `tests/office` + `tests/a2ui` 483
passed, 5 skipped; real-engine render + service end-to-end 20 passed (WebClient stayed STOPPED); Flutter 601 passed,
5 skipped; `flutter analyze` 4 pre-existing infos.

## 8. Status (separate states, none implies another)

- CODE REVIEW ACCEPTED: **yes** — Codex ACCEPT at `b4ea0fae`.
- LIVE UI QUALIFIED: **partial** — every mandatory automated real-app journey PASS at `b4ea0fae` except the Excel Brain
  journey (M2-XB-1); physical input and the owner check NOT VERIFIED / BLOCKED; running-task cancel not driven.
- INDEPENDENTLY ACCEPTED (phase): **no** — needs the owner decisions in §5 and the owner check.
- CANONICALLY INTEGRATED: **no**. PRODUCTION DEPLOYED: **no**. O2 is not frozen. O2P printing stays deferred and off.
