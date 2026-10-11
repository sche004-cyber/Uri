> **SUPERSEDED (2026-10-11).** Revision 1, kept as history only. Its architecture (Office modules inside `uri_operational_intelligence/`, a stdio helper, new worker commands, its own Google sign-in, Codex-only audit, base ffdf534) was replaced. The current plan is `00_PLAN_AND_ACCEPTANCE_CRITERIA.md`: a top-level `uri_office/` package running as its own local HTTP service; the guarded worker is unchanged.

# URI Office M1 — Live Sheets Panel (blueprint for freeze)

## Context
Owner wants a "URI Office": a live, editable spreadsheet dashboard inside URI. URI edits next to the user and keeps user feedback as recorded history (D4: history, not learning). Discovery on 2026-10-11 rejected REA, which is an analysis tool only, and rejected all paid engines.

Owner rulings (2026-10-11):
- No paid licences.
- Two engines:
  - Local .xlsx in a Univer OSS panel inside URI.
  - Google Sheets, because the owner shares through Google.
- Local write-back = direct cell patch. No LibreOffice.
- Google access = full `spreadsheets` scope. The owner clicks through the "unverified app" warning once; personal use only.
- M1 = Sheets only. Docs comes later.
- Allowed downloads: npm `@univerjs/presets`, `@univerjs/preset-sheets-core`, `vite`; pub.dev `webview_flutter_windows`. Pinned and bundled for offline use.
- Every thread respects the machine-wide GPU lease.

## Acceptance criteria (M1)
1. **Panel.** A local .xlsx opens in an Office panel in Living Workspace. It shows values, formulas, basic styles, merged cells and column widths. Charts and pivots stay in the file, not shown; an "Open file" button is the fallback.
2. **Shared draft.** User edits and URI edits land in one versioned draft.
   - URI edits are marked. A widget test asserts the marker.
   - Undo and redo work.
   - The user can accept or reject each URI change.
3. **Approval first.** Nothing touches the real file or Google Sheet until the user approves a digest-bound version.
4. **Local write-back changes only the expected parts.** Comparison is by unpacked part hash, not zip bytes.
   - Allowed to change: the edited `xl/worksheets/sheetN.xml`, `xl/sharedStrings.xml` (only if new strings are added), and `xl/workbook.xml` (only `calcPr fullCalcOnLoad`).
   - `xl/calcChain.xml` may be removed when formulas change, together with its `[Content_Types].xml` and rels entries.
   - Every other part must be identical.
   - Proved on fixtures containing a chart, an image, shared and inline strings, formulas, styles and merged cells.
   - M1 local ops are cell values and formulas only.
5. **Conflict check.** If the original file changed since copy-in, URI reports a conflict and the user chooses. It never silently overwrites.
6. **Google.**
   - One-time Connect through the system browser and a loopback listener, with its own token.
   - The user opens a sheet by pasting its link.
   - Approved URI edits apply through the Sheets API. Google-only ops: insert/delete rows, add/rename sheet.
   - "Open in Google Sheets" button.
   - Seeing changes live in the browser is an owner check: DEFERRED - OWNER if the owner is absent.
7. **Moving between engines.** "Share via Google" uploads and converts a local file, after approval. A Google sheet can be exported to .xlsx.
8. **Corrections history.** Corrections to URI edits are recorded in an append-only log: workbook, cell, URI value, user value, version, time. The last N corrections go into URI's context for that workbook.
9. **Offline.** The panel works offline for local files. No CDN.
10. **Performance gate.** WebView2 must not degrade the Brain, measured with `gpu_lease census` and Brain tok/s before and after the panel opens. Criteria: either no degradation, or a documented mitigation proven, such as `--disable-gpu` browser args or creating the WebView before the Brain starts.
11. **Gates.**
    - Worktree: `pytest tests/ws tests/oi tests/a2ui tests/office`, scheduler 71/71, `flutter test`, `flutter analyze`, `scripts/ws_frozen_check.py`.
    - Built runtime (HEAD e8e3b65 layout): `test_frozen_core` and `phase2close_chain`.
    - Protected paths untouched.

## Verified repo facts (canonical ffdf534)
- **The Living UI talks to a stdio worker**, not HTTP.
  - UI side: `uri_ui/lib/services/integrated_runtime.dart`.
  - Python side: `uri_operational_intelligence/worker_bridge.py`. Commands are at `:44-61`, with `OPEN_WHILE_BUSY`. `oi_turn` takes an exact key set (`:111`).
  - Event types are a closed set: `uri_operational_intelligence/events.py:15,53`.
  - Frames are limited to 2 MiB (`uri_core/client_contracts.py:14`, frozen).
- **The worker sandbox** (`scripts/run_uri_integrated_worker.py:42,72,131-133`) imports only `WS_PACKAGES = ("uri_operational_intelligence",)`. FixtureGuard blocks reads outside client_root and package roots, and blocks writes outside client_root. So the worker cannot touch user files or `credentials.json`.
- **Precedent for new commands:** `draft_get`/`draft_op` were added in commit e48968c — `COMMANDS` and `OPEN_WHILE_BUSY` entries plus handlers (`:547-561`). New OI files need exact entries in `tests/phase2a/test_frozen_core.py:~95-125`, `scripts/phase2close_chain.py:~204-212`, and `scripts/oi_materialize_test_runtime.py:28-41` (`OI_PATHS`/`TEST_PATHS`).
- **Brain call to reuse:** `DraftDesk._call` (`draft_desk.py:339-375`) → `BrainClient.stream_chat` with `tier_params(FAST)`, a strict JSON schema and the `_ready()` check. The Brain host already holds the GPU lease (`scripts/ws_brain_host.py:171`).
- **Draft versioning to copy:** `draft_store.py` (versions, undo/redo, cap 50). UI side: `living/integration/draft_panel.dart`, `oi_conversation.dart:599-698`.
- **UI anchors:** `living/screens/workspace_mode_view.dart` (rail `:138-145`, focus `:93-106`, `_OiWithDraft` `:387-425`, spreadsheet tile `:750-754`). Plugins are injected only via `main.dart:1-6,43-74`.
- **Google:**
  - Desktop OAuth client: `credentials.json`, type `installed`, project `uridc-508517`.
  - Consent pattern: `InstalledAppFlow.run_local_server(port=0)` (`gmail_service.py:117-137`).
  - `load_usable_credentials(token_path=...)` (`google_auth_common.py:70`) — import only.
  - The existing token can't take new scopes, so Office uses its own token.
- **Environment:** Node 24.19 / npm 11.17, Flutter 3.47.2, WebView2 runtime 154, openpyxl 3.1.5 plus the Google client libraries.
- **Known risk:** a window opened after the Brain loads drops Runtime v1 to about a third of its speed (`launch_uri_working_system.ps1:10`).
- **Launcher:** demos need a runtime built from the committed candidate tree. The UiRoot must match the receipt (`UI_ROOT_NOT_RUNTIME_CANDIDATE`).

## Architecture (decided)
```
Flutter Living Workspace
  OfficePanel (injected WebView surface; webview_flutter_windows / WebView2;
               virtual host -> uri_ui/assets/office/ built from uri_ui/office_web/)
     Univer OSS  <-- chrome.webview postMessage JSON -->  Dart OfficeController
        |                                                   |                       |
        |                         stdio worker (guarded)    |                       | stdio helper (unguarded, narrow)
  uri_operational_intelligence/                            scripts/office_host.py -> uri_operational_intelligence/office_io/*
    office_desk.py   versioned workbook draft, ops,          copy-in (user-picked path) -> %LOCALAPPDATA%\URI\office\<id>\
                     digest, accept/reject, approve          xlsx_model: .xlsx -> workbook JSON (paged per sheet/range)
    office_ops.py    closed op schema + validator            xlsx_patch: approved cell diff -> patched file (AC4)
    office_brain.py  chat -> op JSON via DraftDesk-style     google_sheets: consent (system browser), Sheets read/batchUpdate,
                     BrainClient call                                       Drive upload-convert, export
    office_feedback  corrections log (history)               token: %LOCALAPPDATA%\URI\office\google-token.dpapi
```
**Why two processes.** The worker sandbox forbids user-file and credential I/O, and that sandbox is not touched. The helper has a narrow command set:
- `open(path)`: the path comes from the user's file picker only.
- `writeback(id, approved_digest, diff)`: writes only to the path recorded at open, and only after a hash check against the original.
- `google_connect`, `google_read`, `google_apply(approved_digest, ops)`, `upload_convert`, `export`.

**Ownership and flow.**
- The desk (worker) owns the draft and Brain turns. The helper owns all I/O.
- The UI relays workbook JSON from the helper to `office_open` in the worker.
- Approval returns the digest plus diff, and the UI passes them to the helper.
- Office data lives in `%LOCALAPPDATA%\URI\office\`, so it survives runtime rebuilds. The modules live inside `uri_operational_intelligence/` (precedent: `schedule_intent.py`), so the sandbox's package list stays unchanged.

**Worker contract** (fixed before Wave 1):
- Commands:
  - `office_open{workbook}` (paged)
  - `office_get{sheet, range}`
  - `office_op{op, by:user}`: user edits come back in the reply
  - `office_turn{text}`: skips `schedule_intent` and draft classification
  - `office_decide{version_digest, accept[], reject[]}`
  - `office_close`
- `OPEN_WHILE_BUSY`: `office_get` only. The draft is locked during an `office_turn`; user ops queue.
- Events added to `events.py`: `office.updated`, `office.progress`, `office.clarify`, all with turn_id.

**Op schema** (closed):
- Local and Google: `set_values{sheet, range, values[][]}`, `set_formula{sheet, cell, formula}`.
- Google only: `insert_rows`, `delete_rows`, `add_sheet`, `rename_sheet`.
- Invalid ops are reported, never guessed.

## Waves
**Wave 0 — proof spikes.** Run on worktree `C:\Users\cheta\Development\uri-office`, branch `phase/uri-office` from ffdf534. Disposable code goes in `research/uri_office_spikes/`. Order: P3 → P1 → P2. Stop and report if any spike fails.
- **P3 Google.**
  - Standalone consent script, scopes `spreadsheets` + `drive.file`. The owner clicks consent; if absent, DEFERRED and P1's Google check is skipped.
  - Read and write one cell on a scratch sheet. Record when the token was issued.
- **P1 cell patch.**
  - Build fixtures with openpyxl, plus a chart and an image.
  - Patch values, a formula and a new string.
  - Check unpacked part hashes against the allowed-change list.
  - Reopen with openpyxl. Upload-convert to Drive as an independent opener (needs P3).
- **P2 Univer in WebView2.**
  - Vite bundle, virtual host mapping, and a Dart↔JS round trip (set values, `SheetValueChanged`).
  - Run `gpu_lease advise --window` first. Measure Brain tok/s and `census` with the panel opened after the Brain, then with mitigations.
  - Pick a mitigation, or stop and report.

**Wave 1 — parallel lanes.** Starts after Wave 0 is green and the worker contract is fixed.
- **L1 desk (Python, worker side):** `office_desk`, `office_ops`, `office_feedback`, `office_brain`. Tests use a fake BrainClient, under `tests/office/`.
- **L2 I/O helper (Python):** `office_io/xlsx_model`, `xlsx_patch`, `google_sheets`, plus `scripts/office_host.py`. Uses fixtures and a fake Google service. L2's workbook JSON schema is shared with L1 and defined in Wave 0's contract doc.
- **L3 Flutter:**
  - `WorkspaceFocus.office` and a rail item.
  - `OfficePanel` takes an injected surface factory and never imports the plugin directly.
  - Marks on URI edits, accept/reject, an approve bar, and buttons for Connect Google, Open file and Open in Google Sheets.
  - Univer source in `uri_ui/office_web/`, with a pinned lock file and its own `.gitignore`. The root `.gitignore` is protected.
  - Widget tests with a fake surface.

**Wave 2 — integration.**
- Bridge handlers and events. Helper process lifecycle in the UI. End-to-end tests with fake Brain and fake Google.
- Add allowlist entries in `test_frozen_core`, `phase2close_chain` and `oi_materialize_test_runtime`.

**Wave 3 — qualify and close.**
- All gates (AC11).
- Build the runtime from the committed `phase/uri-office` tip and provision a new client.
- Owner live demo (owner present): local round trip, live Google edit, a recorded correction, and the AC10 measurement.
- Codex independent audit via codex-exec, `gpt-6-sol` at medium effort. If it's unavailable, ask the owner; never substitute silently.
- Repair, re-gate, freeze. Docs go in `docs/office/` (BLUEPRINT, CONTRACT, REPORT, AUDIT_RECORD, STATUS_LEDGER, `evidence/`).
- Merging into canonical is a separate step that needs owner approval.

## GPU lease rules for all threads
- Before opening any window or WebView: `python -m uri_operational_intelligence.gpu_lease advise --window --wait 1800`, saving the JSON as evidence.
  - Exit 75: wait.
  - Exit 76: perf data is invalid.
- Standalone live or perf runs that start their own Runtime go through `gpu_lease run --purpose benchmark -- ...`. Normal Brain turns use the host's lease.
- Never override the lease. Never start a second Brain host.

## Stop conditions
- A Wave 0 spike fails.
- A protected path needs changing, or the sandbox's package list would have to grow.
- The AC10 degradation has no mitigation.
- An owner-only step comes up: marked DEFERRED - OWNER, never simulated.

## Out of scope (M1)
Docs/Slides; editing charts or pivots; local row/sheet structure ops; multi-user collaboration; macros; canonical merge; learning beyond recorded history; the 7-day token survival check (later owner check).
