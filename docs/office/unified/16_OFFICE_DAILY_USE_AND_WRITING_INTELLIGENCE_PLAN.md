# URI Office daily use and Writing Intelligence: inventory, plan and acceptance criteria

Date 2026-10-23 (owner directive "URI OFFICE COMPLETION & WRITING INTELLIGENCE", owner away until 2026-10-24).
Baseline: canonical `integration/git-sync-20261008` @ `277e81f9` (contains the Office tip `3e769fdf`).
Milestone Manager: `OFFICE-DAILY-USE` (new; no earlier Office completion milestone exists in the ledger) and the
existing `WRITING-INTELLIGENCE` (P3, was PLANNED). Branches `milestone/office-daily-use-20261023`
(worktree `D:/uri-dev/uri-office-daily`) and `milestone/writing-intelligence-20261023` (`D:/uri-dev/uri-writing`).

## 1. Evidence-based inventory (read at 277e81f9, not from earlier summaries)

Sources: code under `uri_office/`, `uri_assist/`, `uri_operational_intelligence/`, `uri_ui/lib`; records 08-15 in
this folder; P0 register `developmental.md` (audit branch @2e4263ad) CAP-OF1..7, CAP-AS1, CAP-TI1, CAP-VO1.

| Area | Item | Class | Evidence |
|---|---|---|---|
| Word | open, view, edit (paragraphs, styles incl. headings and List Bullet/List Number, tables, picture, header/footer, page number, orientation/margins, find and replace), undo/redo, hash-bound Save / Save as, reopen, PDF export | Working and accepted (live a11/a16 13/13) | `authoring/docx_ops.py:610`, `session.py`, live records 15 |
| Word | layouts Blank, Letter, Office order, Notice, Memo, Minutes, Report | Working and accepted | `docx_templates.py:12` |
| Word | Notesheet and Circular layouts | Missing | not in repo |
| Word | lists beyond the two list styles (restart, levels), paper size, run-level formatting | Partial | docx_ops; style-only lists |
| Word | find/replace across runs | Partial (counted, named, not changed) | `docx_ops.py:323` |
| Word | Brain drafting from an instruction ("write an office order...") into a Word document | Missing (`write_document`/`edit_document` = `planned:O3`) | `capabilities.py:57-61` |
| Excel | open, cell values and formulas, Brain proposals (propose/clarify/cannot), row insert/delete via proposals, formatting subset, hash-bound save, new workbook from files | Working and accepted | records 13, CAP-OF1 |
| Excel | blank new workbook; column ops; sort; manual row insert in the grid | Missing / refused by the page | `sources.py:41`, `guard.js:33-96` |
| PDF | view, outline, search (50 matches), Office->PDF | Working and accepted | `workers/pdf_text.py`, `docs.py:211` |
| PDF | text extraction for the user (copy / to Word) | Missing (worker returns no text by design) | `pdf_text.py:5-15` |
| PDF | OCR | Missing in code; Tesseract present on the PC (`C:\Program Files\Tesseract-OCR`, not used) | `which tesseract` empty on PATH |
| PDF | ask / summarize | Missing (`planned:O4`) | `capabilities.py:64-66` |
| PDF | printing | Gated (O2P, off unless `--enable-printing`; physical print NOT VERIFIED) | record 03/04 |
| PowerPoint | edit/new/template op set, PDF export | Working and accepted (A01-A05) | `pptx_ops.py:427` |
| PowerPoint | built-in presentation templates; Brain outline -> deck; charts create/edit | Missing (`planned:O5`) | `session.py:34` |
| Client | Office in UI V2 rail, onboarding O01, file/folder dialogs, Office service started by the app | Working and accepted (live a11) | record 15 |
| Client | installer / packaging | Missing (P5 OFFICE-CLIENT-INSTALLER, CAP-PK1) | P0 register |
| Writing | spelling, grammar, punctuation suggestions anywhere | Missing (no spell library, no Windows API use) | grep: none |
| Writing | Brain correct/rewrite of a draft (draft desk CORRECT/REWRITE with meaning checks `text_verify`) | Working (TI, Codex r16 AwF) but only as a chat turn on a session draft | `draft_desk.py:140-617` |
| Writing | dictation grammar clean-up (`uri.text_input.v1` scope grammar) | Working; "polished" scope `rewrite` exists in the contract but the UI never sends it | `text_input.py`, `oi_conversation.dart:533` |
| Assist | consent, redaction, sensitive-field rules, deterministic form checks | Working | `uri_assist/access.py`, `redact.py:264`, `checks.py:51` |
| Assist | observing external apps / browser fields | Blocked: every perception adapter is `UnavailableAdapter` (D14, milestone P9) | `perception.py:307` |
| Assist | inserting text into external fields | Blocked by policy: `INSERT` not grantable in A0 | `access.py:44-45` |

Owner-visible gaps for daily administrative work, in order of daily impact:
1. No spelling/grammar help while writing anywhere in URI.
2. URI cannot draft a document into Word from an instruction (the most common administrative task).
3. No Notesheet / Circular layouts.
4. PDF text cannot be taken out (copy, to Word), scanned PDFs cannot be read (no OCR).
5. Dictation cannot be polished on request.
6. PDF ask/summarize, presentation from an outline, blank workbook (second increment).

## 2. Spike result: deterministic spelling layer without any install (2026-10-23)

Windows Spell Checking API (`ISpellCheckerFactory`, built into Windows 8+, no install, no GPU), driven from a
PowerShell worker with an in-memory C# interop (same pattern as the existing WinRT PDF raster worker). `en-IN`
checker: on "I recieve the the letter ... on tuesday. Kindly acommodate ... seperate copies to Shri Sharma, Dy. Secy."
it returned REPLACE recieve->receive, DELETE repeated "the", GET_SUGGESTIONS "tuesday", REPLACE acommodate,
REPLACE seperate; honorifics and abbreviations not flagged. Compile 0.45-0.6 s once per worker; checker create 20 ms;
first check 32 ms, warm check 6 ms. Decision: use it as the deterministic layer; the Brain is used only on request
(proofread / tone), never per keystroke. Rejected: pyspellchecker / hunspell / LanguageTool (new permanent dependency,
LanguageTool needs Java and ~1 GB); a second resident model (no VRAM headroom: Brain 14.99 GiB + 1.73 GiB shared).

## 3. Increment 1 plan

### WI-A Writing Intelligence engine (branch writing-intelligence; package `uri_assist`)

The engine extends URI Assist (owner: "extend the existing URI Assist") and is reused by Office and OI:
- `uri_assist/writing.py`: `check(text, lang)` -> list of suggestions `{id, start, end, original, replacement[],
  kind: spelling|repeat|punctuation|spacing|capital|grammar|style|tone, class: correction|rewrite, source:
  windows_spell|rules|brain, message}`; deterministic rules (double space, space before punctuation, missing space
  after punctuation, sentence-initial capital, lone "i", repeated word, duplicated punctuation, a/an before a vowel
  letter) plus the Windows spell worker; `apply(text, accepted)` applies non-overlapping accepted suggestions from
  the end so offsets stay valid and returns the new text with an undo record.
- `uri_assist/workers/spell_worker.ps1`: persistent JSON-lines worker (compile once), ops `check{text,lang}`,
  `quit`; started lazily, stopped after idle; refusal `SPELL_UNAVAILABLE` -> rules only (never blocks typing).
- Brain proofread / tone (`proofread`, `rewrite{tone: formal|concise|friendly|plain}`, `complete` sentence/phrase):
  one FAST-tier call through the existing `brain_client` with a strict JSON schema; Brain output is re-diffed into
  suggestions; `text_verify`-style checks from TI classify each Brain change: a change that drops or adds a number,
  date, name or negation is `class: rewrite` (meaning may change -> explicit approval), otherwise `correction`.
- Privacy: text from a field `field_is_sensitive` refuses (`SENSITIVE_FIELD`); text containing secrets per
  `redact.redact_text` refuses Brain use (`SENSITIVE_TEXT`), deterministic checks still run locally; local Brain
  only (loopback enforced by `brain_client`); nothing is stored or logged except counts.
- Surfaces in increment 1: Office Word and PowerPoint editors (`AuthoringTextField`): underline-free suggestion strip
  under the field after a typing pause (debounce 700 ms) with Accept / Dismiss per item, Accept all corrections,
  Undo; buttons "Proofread", "Formal", "Concise"; nothing changes the document until the existing Apply op. The URI
  composer gets the same strip (spelling and grammar only; the draft panel keeps its own Brain editing).
  Dictation (corrected 2026-10-23, review FB1 R2-08): Settings "Dictated words" chooses As spoken (new scope
  `verbatim`, no Brain call), Corrected (scope `grammar`, the accepted default, unchanged) or Polished (scope
  `rewrite`, already in the contract).
- External text fields (Assist browser/desktop): NOT in increment 1 - blocked by D14 (no perception adapter) and by
  the A0 `INSERT` policy; recorded as owner decision OD-WI-1 (see section 6). Assist's existing `assist_check`
  gains writing findings for shareable contenteditable text only when such observation exists.

### OD-A Office daily use (branch office-daily-use)

- Layouts Notesheet and Circular (`docx_templates.py`), same rules (no pre-filled names, numbers or dates).
- Word drafting with the Brain (`write_document`, O3 subset): `POST /authoring/draft {instruction, layout?}` ->
  document type chosen deterministically from the instruction (letter, office order, notesheet, notice, circular,
  memo, minutes, report; else clarify), Brain returns `{status: propose|clarify|cannot, blocks[{role, text}],
  missing[]}` (strict schema, FAST tier), blocks are written into a new working copy made from that layout through
  the existing docx ops; facts (numbers, dates, names, reference numbers) in the instruction must appear verbatim or
  the draft carries a named warning; the owner edits in the existing Word editor and saves with the existing Save as
  card. Nothing is written to disk before approval.
- PDF text out: `POST /document/<id>/text` (whole text, page-labelled, size-capped) for "Copy text" and
  "To Word document" (new working copy, Save as card); OCR fallback for pages without a text layer through the
  installed Tesseract, run in the existing worker Job Object, only on owner request (button "Read scanned pages").

## 4. Acceptance criteria (increment 1)

| ID | Criterion | Evidence |
|---|---|---|
| WI-1 | `check` finds spelling (Windows API), repeated words, spacing, punctuation, capitalisation and a/an on a corpus of 40 administrative sentences with no false positive on honorifics, abbreviations, reference numbers, dates, amounts, Indian names in the corpus | unit tests + corpus file |
| WI-2 | Suggestions apply exactly (offsets), overlapping ones are not applied together, Undo restores the exact text | unit tests |
| WI-3 | Spell worker absent or failing -> rules still run, status says why; never raises into typing | tests (forced failure) |
| WI-4 | Brain proofread/tone returns suggestions; any change to numbers, dates, names, negation or reference numbers is classed `rewrite` and never offered in "Accept all corrections" | tests with a fake Brain + live Brain corpus |
| WI-5 | Sensitive fields and secret-bearing text never reach the Brain or logs | tests |
| WI-6 | Latency: deterministic check p95 < 50 ms for 1,000 characters warm; first-use worker start < 1.5 s; no GPU use; Brain only on explicit request | measured on the PC, exact commit |
| WI-7 | Word and PowerPoint editors show suggestions without changing the document until Apply; Accept/Dismiss/Undo work; Flutter tests | widget tests + live journey |
| WI-8 | Dictation: As spoken (verbatim, no Brain) / Corrected (grammar, default unchanged) / Polished (rewrite) chosen in Settings; tests | Flutter + OI tests |
| OD-1 | Notesheet and Circular layouts open, render, save; no pre-filled facts | tests + real engine |
| OD-2 | Brain draft: instruction -> correct layout chosen -> blocks written through docx ops -> preview -> Save as card; clarify honoured; every number/date/name/reference in the instruction present or warned; original files untouched | service tests (fake Brain) + live Brain corpus of 10 real-shaped tasks |
| OD-3 | PDF text: page-labelled text, size cap, copy and to-Word; OCR only on request, Tesseract in a Job Object, refusal named when absent | tests + real engine |
| G-1 | Gates: office, office_u2, a2ui, assist, ws (TI), Flutter: no new failure against 277e81f9; frozen check ok | driver gates |
| G-2 | Independent review ACCEPT / AwF on the exact commit (V3.1: driver primary; fallback only after driver NO_INDEPENDENT_REVIEWER) | driver receipt / fallback record |
| G-3 | Live (production main, real service, real Brain under the GPU lease, simulated input): W01 type with errors -> suggestions -> accept -> apply -> save; W02 proofread/formal; D01 draft an office order and a notesheet; P01 PDF copy text and to Word; regression a-set and o-set | live record |

Not claimed by increment 1: physical keyboard/mouse input (owner check), external-app writing (OD-WI-1), PDF Q&A,
presentation from outline, blank workbook, installer, production use.

## 5. Coordination

M95 owns `uri_privacy/` and touches `uri_office/service.py` `main()` only: this work does not edit `main()`. Vision F-1
touches the profile-switch block of `worker_bridge.py`: not edited here. Codex is booked for M95 driver r8 at 23:29
IST: driver reviews here are started only when Codex is free, otherwise the driver records NO_INDEPENDENT_REVIEWER
and the V3.1 fallback applies. No GPU-heavy run overlaps an M95 live run; Brain live runs only under the GPU lease.

## 6. Owner decisions (only genuine ones)

- OD-WI-1: writing suggestions in external apps need (a) a working Assist perception adapter (P9) and (b) granting
  `INSERT` for an "apply suggestion" button, which is a permission-boundary change. Until decided, external use is
  read-only and copy-based.
- OD-WI-2 (preference): default language `en-IN` (Indian English spelling) - chosen by default from the owner's
  context; one line to change.

## 7. Self-review against the Verification-First standard

Acceptance criteria precede work (section 4). Every inventory row cites code read at 277e81f9; prior records were
re-checked where claims mattered (pdf_text has no text route, no OCR, no spell library, Office already imports OI).
The spike numbers come from one PC run (stated as such, not a qualification). Unverified: Tesseract version and
language packs (checked at OD-3), Windows en-IN dictionary presence on other machines (the worker falls back to en-US
then rules only, named). Live criteria remain NOT VERIFIED until G-3 runs.
