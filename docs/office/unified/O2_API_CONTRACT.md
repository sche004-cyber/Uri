# URI Office O2: service interface and capability contract (contract `o2.1`)

Date: 2026-10-15. Phase O2 (G1 active), implementation branch `phase/uri-office-u-2-a`.
Status: **WORKING CONTRACT.** It becomes the frozen O2P interface when the O2 contract tests pass and the independent
review of this file accepts it (A5: "O2's raster worker and approvals contract, frozen at O2 contract time").

Sources: plan rev 3.1 §5, §5.1, §6, §8 and §9 (`01_O2_PLAN_AND_ACCEPTANCE_CRITERIA.md`); amendment A1 §A3, §A4, §A6 and §A7;
the owner's OD-U12 refinement (gate record, 2026-10-15). Where this file is more specific, it is the implementation
contract. Where it disagrees with the plan, the plan wins, and this file is corrected.

## 1. Acceptance criteria for this contract

| # | Criterion | Test |
|---|---|---|
| C1 | Every route has a request shape, a response shape and named error codes. | `tests/office_u2/test_contract.py` checks the route table against the handler. |
| C2 | Every error code has a fixed owner-facing message and a recovery action (refinement 7). | `test_contract.py`: every code in `contracts.ERRORS` has both. |
| C3 | Responses carry no document text, cell values or file content, except what the owner opened and sees: `/document/<id>/search` (page numbers and a short match context), page PNG bytes, and outline titles in DocView. None of these is logged, stored in `workflow.json` or `recent.json`, or sent to the Brain. | `test_service_o2.py` (AC-O2-14 sentinel scan) |
| C4 | One approval path: plan, outputs and print jobs are rows of the existing `surface` table, acted on through the existing `/a2ui/action`. No new authorization system. | `test_plan_card.py`, `test_output_approval.py` |
| C5 | Capabilities, devices and printing are exposed as transport-free descriptors, so a later Brain registration can wrap them without a redesign (OD-U12). No Core file is written. | `test_capabilities.py`, `tests/devices/test_capability.py` |
| C6 | All existing M1/M2 routes keep their shapes. | existing `tests/office` |
| C7 | The contract version is served at `GET /contract` and checked by the Flutter client. | `test_contract.py` |

## 2. Transport (unchanged from M1)

- `127.0.0.1` only, per-launch bearer token in `<state>/api-token`, loopback `Host` for the port, no `Origin`, no CORS,
  `OPTIONS` refused (`service.py` `_auth`).
- `GET` never changes state. Every change is a `POST` with a JSON object body of at most 256 KB.
- Errors: HTTP status plus `{"error": <CODE>, "detail": <short text>}`. `detail` never holds document content.
- New: one binary response type, `image/png`, for page images only, with `Cache-Control: no-store`.

## 3. Shared types

```text
Kind          = "xlsx" | "docx" | "pptx" | "pdf"
StepKind      = "D" (rule-based) | "E" (engine) | "B" (URI-written; not used in O2)
Severity      = "error" | "warning" | "info"
CheckKind     = "structural" | "render" | "visual" | "integrity" | "fidelity"
EngineState   = "unverified" | "verifying" | "ready" | "starting" | "running" | "idle_stopped" | "unavailable"
WorkflowState = "planned" | "waiting_approval" | "running" | "interrupted" | "needs_review" | "ready_to_save"
              | "saved" | "cancelled" | "failed" | "discarded"
StepState     = "pending" | "running" | "done" | "failed" | "skipped" | "cancelled"
```

**Finding** (plan §8):
```json
{"id": "f-3", "check": "font_substitution", "kind": "visual", "severity": "warning",
 "location": {"file": "output", "page": 2},
 "message": "Font 'Mangal' was replaced by 'Nirmala UI'.",
 "repair": {"kind": "owner", "rule_id": null}}
```
- `location.file` is `"source"` or `"output"` (or a source index for O7), never a path.
- `message` comes from a fixed template per check. It may name a font, a page or a count, never document text.
- Errors block approval. Warnings need "Accept with warnings", which is audited.

**Capability** (`GET /capabilities`):
```json
{"id": "save_as_pdf", "goal": "share_and_print", "title": "Save as PDF",
 "inputs": ["docx", "pptx", "xlsx"], "output": "pdf",
 "steps": [{"id": "sanitize", "kind": "D"}, {"id": "convert", "kind": "E", "engine": "libreoffice"},
           {"id": "validate", "kind": "D"}, {"id": "preview", "kind": "E", "engine": "winrt_pdf"}],
 "engines": ["libreoffice", "winrt_pdf", "pdf_text"],
 "status": "available", "ready": true, "unready_reason": null,
 "approval": "plan_and_outputs", "effects": ["writes_new_file"]}
```
- `status` is `available` or `planned:<phase>`. A planned capability is listed (help chip) but never runs (AC-O2-11).
- `ready` is false while a needed engine is not `ready`/`running`/`idle_stopped`; `unready_reason` is an error code
  from §6.
- `approval` is `none` (open, navigate, preview), `plan_and_outputs` (workflows with outputs) or `print_job` (O2P).
- `effects` is a closed set: `reads_files`, `writes_new_file`, `sends_to_printer`, `uses_brain`. This is the
  OD-U12 descriptor shape that a later Brain registration would map to Core's effect classes.

**Workflow record** (`<state>/workflows/<id>/workflow.json`, plan §6.3; no document text):
```json
{"workflow_id": "w-…", "contract": "o2.1", "capability": "save_as_pdf", "intent": "save_as_pdf",
 "state": "ready_to_save", "created_at": 0, "updated_at": 0,
 "inputs": [{"kind": "docx", "path": "C:\\…\\letter.docx", "sha256": "…", "size": 12345}],
 "steps": [{"id": "convert", "kind": "E", "engine": "libreoffice", "engine_version": "26.8.1.1",
            "state": "done", "started_at": 0, "ended_at": 0, "finding_ids": []}],
 "outputs": [{"name": "letter.pdf", "sha256": "…", "pages": 2, "size": 45678}],
 "findings": [],
 "approvals": [{"surface_id": "…", "subject": "plan", "sha256": "…"}],
 "errors": [{"code": "ENGINE_TIMEOUT", "step": "convert", "at": 0}]}
```

## 4. Routes

All new routes are bearer-guarded and listed in `contracts.ROUTES`. `<id>` values are 16–32 lowercase hex characters;
any other value is `404 UNKNOWN_*`.

| Route | Method | Request | Response | Errors |
|---|---|---|---|---|
| `/contract` | GET | – | `{"contract": "o2.1", "routes": [...], "kinds": [...]}` | – |
| `/capabilities` | GET | – | `{"capabilities": [Capability], "goals": [{id, title}]}` | – |
| `/engines` | GET | – | `{"engines": [{"id", "state", "version", "pinned", "reason", "last_verified"}]}` | – |
| `/engines/verify` | POST | `{"engine": "libreoffice"}` | full-manifest result `{"ok", "files", "seconds", "mismatches": n}` | `ENGINE_MISSING` |
| `/open/document` | POST | `{"path"}` | DocView | `PATH_REFUSED`, `FILE_TOO_LARGE`, `UNSUPPORTED_KIND`, `ENCRYPTED`, `ARCHIVE_REFUSED`, `TOO_MANY_OPEN` |
| `/document/<id>` | GET | – | DocView | `UNKNOWN_DOCUMENT` |
| `/document/<id>/page/<n>` | GET | `?w=440|880|1240|160` | `image/png` | `UNKNOWN_DOCUMENT`, `PAGE_NOT_READY` (202), `PREVIEW_UNAVAILABLE` |
| `/document/<id>/search` | POST | `{"text"}` (≤ 200 chars) | `{"matches": [{"page", "context"}], "truncated"}` | `NO_TEXT_LAYER` |
| `/document/<id>/close` | POST | – | `{"closed": true}` | – |
| `/request` | POST | `{"text", "target": {"kind", "id"}?, "scope": {"pages": [..]}?, "chip": <intent id>?}` | IntentResult | `BRAIN_UNAVAILABLE` never surfaces as an error: the result is `clarify` |
| `/workflow` | POST | `{"capability", "inputs": [{"document_id" or "workbook_id"}], "options": {}}` | `{"workflow_id", "messages": [plan card]}` | `CAPABILITY_PLANNED`, `ENGINE_UNAVAILABLE`, `UNSAVED_CHANGES` |
| `/workflow/<id>` | GET | – | workflow record view | `UNKNOWN_WORKFLOW` |
| `/workflow/<id>/answer` | POST | `{"question_id", "answer"}` | IntentResult | |
| `/workflow/<id>/cancel` | POST | – | record view | `NOT_CANCELLABLE` |
| `/workflow/<id>/resume` | POST | `{"inputs": [{"path"}]}` | record view | `INPUT_CHANGED` |
| `/workflow/<id>/accept_warnings` | POST | – | record view (audited) | `HAS_ERRORS` |
| `/workflow/<id>/propose_save` | POST | `{"save_as_path"}` | `{"messages": [output card]}` | `DESTINATION_EXISTS`, `HAS_ERRORS`, `WARNINGS_NOT_ACCEPTED` |
| `/workflow/<id>/output/page/<n>` | GET | `?w=` | `image/png` | as page |
| `/workflows` | GET | – | `{"running": [...], "done": [...]}` (ids, capability, state, times) | – |
| `/recent` | GET | – | `{"items": [{"path", "kind", "last_opened", "size"}]}` | – |
| `/recent/remove` | POST | `{"path"}` | `{"items"}` | – |
| `/recent/clear` | POST | – | `{"items": []}` | – |
| `/a2ui/action` | POST | existing | existing; now also plan, output and print cards | existing plus `STALE_PLAN` |

**DocView:** `{"document_id", "kind", "name", "pages", "slides"?, "outline": [{"title", "level", "page"}], "preview":
{"state": "rendering|ready|unavailable", "reason", "seconds"}, "findings": [Finding], "sha256_prefix",
"read_only": true, "renderer": "LibreOffice"|"Windows"}`. A PDF that is encrypted or over 2,000 pages opens with
`preview.state = "unavailable"` and `preview.reason` = `ENCRYPTED` or `TOO_MANY_PAGES` (the PDF is parsed only in
the workers, after the session exists).
- Outline titles are shown to the owner in the UI. They travel only on this owner-facing route, never to the Brain
  (plan §9.5) and never into logs.

**IntentResult:** one of
- `{"result": "matched", "intent", "capability", "stage": 1|2, "inputs_needed": []}`;
- `{"result": "clarify", "question_id", "question", "chips": [{"label", "intent"|"answer"}]}`;
- `{"result": "planned", "intent", "phase", "message": "… is not available yet (planned for O3)."}`;
- `{"result": "navigate", "view": OfficeView}` for "show my PDFs" and similar;
- `{"result": "help"}` for "help" / "what can you do"; the client builds the answer from `/capabilities`.

`/request` body fields: `text`, `target: {kind}`, `history` (earlier owner turns, at most 4 reach the Brain), `chip`.
`scope` is accepted and ignored in O2 (page scopes start in O3/O4).

`OfficeView` = `home | recent | documents | spreadsheets | presentations | pdfs | templates | workflows | devices`
(`devices` only when O2P is available).

## 5. Approval subjects (one table, one chain; plan §5.1, A1 §A4)

Apply never runs a workflow or a print job inside the approvals lock; it records the decision and queues them. The
O2 output write (a copy of one approved PDF) does run inside apply, as M1/M2 saves do.

| `subject_kind` | Created by | Bound hash key | A2UI actions | Apply does |
|---|---|---|---|---|
| `workbook` (existing) | `propose` | `change_sha256` | `office.apply_change`, `office.reject_change` | unchanged |
| `plan` | `propose_plan` | `plan_sha256` | `office.run_plan`, `office.discard_plan` | records the state change and enqueues the run, then returns |
| `output_files` | `propose_outputs` | `change_sha256` | `office.apply_change`, `office.reject_change` | real-path re-check, temp write, fsync, no-replace rename |
| `print_job` (O2P) | `propose_print` | `change_sha256` | `office.apply_change`, `office.reject_change` | enqueues the job, then returns |

- The plan hash binds: capability, steps (id, kind, engine), inputs (kind, SHA-256), outputs (name pattern, count,
  kind) and the text "originals will not change".
- The output hash binds: each output (name, size, pages, SHA-256), every warning finding id and message, the full
  destination path, and the warnings-accepted flag.
- The print hash binds (O2P): the PDF SHA-256, the page list, the printer name, every setting and the printer
  capability snapshot.
- Lock order: workflow lock, then approvals lock. No work runs inside the approvals lock.

## 6. Error catalogue (refinement 7)

Every code has a fixed message and a recovery action; the UI shows both. The full list lives in
`uri_office/contracts.py` `ERRORS` and is tested. Examples:

| Code | Message | Recovery |
|---|---|---|
| `ENGINE_MISSING` | The document engine is not installed. | "How to set up previews" (help) |
| `ENGINE_INTEGRITY` | The document engine failed its safety check and was not started. | "Verify engine" |
| `ENGINE_TIMEOUT` | The document took too long to render. | "Try again" |
| `PREVIEW_UNAVAILABLE` | This page could not be shown. | "Try again" / "Open another file" |
| `ENCRYPTED` | This file is password-protected; URI cannot open it. | "Choose another file" |
| `ARCHIVE_REFUSED` | This file looks unsafe or damaged and was not opened. | "Choose another file" |
| `UNSAVED_CHANGES` | Save your changes first, or discard them. | "Save" / "Discard" |
| `DESTINATION_EXISTS` | A file with that name already exists. | "Choose a new name" |
| `INPUT_CHANGED` | The file changed since this task started. | "Start again" |
| `CAPABILITY_PLANNED` | This is not available yet. | none |
| `CLM_ACTIVE` | Windows security policy blocks the PDF renderer on this PC. | "Learn more" |

Other codes the O2 routes return, without a catalogue entry because they need no owner action: `UNKNOWN_PAGE`
(404), `CANCELLED` (a queued engine job dropped because its document or task closed), `NOT_FOUND`, `BAD_REQUEST`.

**Resume rules as built (review round 1).** At service start, a task that was running or waiting to be saved
becomes `interrupted`; a plan the owner never approved becomes `discarded` (it cannot be resumed). Resume needs the
owner's earlier plan approval, re-confirms each input through the picker and checks its SHA-256, then re-runs every
step from the start (all O2 steps are deterministic and short; plan §4.7 said "from step N"). A new destination is
picked with a new Save before any new output card.

## 7. Devices and printing (O2P; contract only in O2)

`uri_devices` (A1 §A6) is transport-free:

```text
Device      {id, kind: "printer"|"scanner", name, connection: usb|network|virtual|unknown, is_default,
             status: ready|offline|error|busy|unknown, status_detail, capabilities: {}, first_seen, last_seen, new}
DeviceProvider (protocol): kind; list() -> [Device]; capabilities(id) -> {}; status(id) -> (status, detail)
Registry: kind -> provider; only "printer" is registered in O2P.
CapabilityDescriptor (OD-U12): {id, title, inputs, effects, approval, requires_device_kind}
```

- `print_document`: `inputs = ["pdf"]` (every kind becomes a PDF first), `effects = ["sends_to_printer"]`,
  `approval = "print_job"`, `requires_device_kind = "printer"`.
- `list_printers`: `effects = []`, `approval = "none"` (read-only, local).
- Routes (served by the Office service): `GET /devices/printers`, `GET /devices/printers/<id>`,
  `POST /devices/refresh`, `POST /print/preview`, `POST /print/propose`, `GET /print/<job>`,
  `POST /print/<job>/cancel`. Their shapes are fixed in the O2P plan section before O2P code starts.
- A future Brain registration would add a Core descriptor that calls these descriptors through the Office service.
  That needs frozen-Core authorization and is not part of O2 or O2P (OD-U12).

## 8. Versioning

- `contracts.CONTRACT_VERSION = "o2.1"`. An additive change (a new optional field, a new route) bumps the minor
  number. A changed or removed field bumps the major number and needs the reviewer.
- The Flutter client reads `GET /contract` at start and refuses to show the Office workspace on a major mismatch
  ("The Office service and the app are different versions; restart URI").
