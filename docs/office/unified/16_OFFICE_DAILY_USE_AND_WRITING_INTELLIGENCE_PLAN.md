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
  composer and draft panel get the same strip. Dictation: a "Polish dictation" toggle sends scope `rewrite`
  (existing contract), verbatim stays the default.
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
| WI-8 | Dictation: verbatim default unchanged; "Polish" sends scope rewrite; tests | Flutter + OI tests |
| OD-1 | Notesheet and Circular layouts open, render, save; no pre-filled facts | tests + real engine |
| OD-2 | Brain draft: instruction -> correct layout chosen -> blocks written through docx ops -> preview -> Save as card; clarify honoured; every marked fact in the instruction (section 4, "Fact-check scope") present or warned, and the scope shown to the owner with every draft; original files untouched | service tests (fake Brain) + live Brain corpus of 10 real-shaped tasks |
| OD-3 | PDF text: page-labelled text, size cap, copy and to-Word; OCR only on request, Tesseract in a Job Object, refusal named when absent | tests + real engine |
| G-1 | Gates: office, office_u2, a2ui, assist, ws (TI), Flutter: no new failure against 277e81f9; frozen check ok | driver gates |
| G-2 | Independent review ACCEPT / AwF on the exact commit (V3.1: driver primary; fallback only after driver NO_INDEPENDENT_REVIEWER) | driver receipt / fallback record |
| G-3 | Live (production main, real service, real Brain under the GPU lease, simulated input): W01 type with errors -> suggestions -> accept -> apply -> save; W02 proofread/formal; D01 draft an office order and a notesheet; P01 PDF copy text and to Word; regression a-set and o-set | live record |

Not claimed by increment 1: physical keyboard/mouse input (owner check), external-app writing (OD-WI-1), PDF Q&A,
presentation from outline, blank workbook, installer, production use.

### Implementation status (OD-A, 2026-10-23, branch milestone/office-daily-use-20261023)

Implemented (unit, service and widget tests only; no live run, no real Brain):
- OD-1: layouts `notesheet` (Note Sheet, File No., subject, List Number paragraphs, signature, name, designation,
  date) and `circular` (Circular, No. and Date line, subject, body, issuing authority, Distribution list); placeholders
  only. Python-docx, save-as and real LibreOffice render tests (the engine test ran on this PC).
- OD-2: `POST /authoring/draft {instruction, layout?}`; kind chosen from keywords (earliest keyword wins; none ->
  clarify without a Brain call); `OfficeBrain.draft_document` (FAST tier, strict schema, 60 blocks x 1,500 chars,
  20,000 chars total; over-cap answers refused, not truncated); blocks written by a pure function into a new working
  copy in the layout's page setup; FACT_MISSING warnings for numbers, dates, references, amounts and capitalised names
  not present verbatim (FB12, OD-OD-6: FACT_CHECK when present only inside a longer name or reference); no Brain ->
  BRAIN_UNAVAILABLE. `write_document` available through this route only;
  `edit_document` stays planned:O3. Tests use a fake Brain client.
- OD-3: worker op `text` (page text, 2,000,000-character cap, `truncated`), `POST /document/<id>/text`,
  `POST /document/<id>/to_word` (new working copy, one heading per page, Save as card as usual). OCR on explicit
  request (`{ocr: true}`): Tesseract at the `engines.json` `tesseract.path` entry or the default install folder, on
  page images from the existing raster path (1240 px), one Job Object per page (1 GiB, 90 s), at most 20 pages per
  request (the rest listed), `OCR_UNAVAILABLE` when absent. A real Tesseract test reads a generated page image.
- UI: "Draft with URI…" on Office Home (instruction + optional kind), composer requests routed to `write_document`,
  clarify/cannot/missing facts in words, "Copy text" and "To Word" on the PDF view, "Read scanned pages" chip.

Not implemented / not verified: live Brain corpus of 10 tasks (OD-2 evidence) and live G-3 journeys D01/P01; OCR on a
page rendered by the WinRT raster worker end to end (only the Tesseract step and the routing were tested); Tesseract
is not hash-pinned like LibreOffice (no pin recorded); only the `eng` language pack is installed (Hindi text is not
read). Correction (FB2 R3-07): the earlier sentence here said To Word's OCR option had no button. Since c57a5e24 the
PDF toolbar has a "Read scans" switch: while it is on, Copy text and To Word both send `ocr: true`. The "Read scanned
pages" chip after Copy text still exists as well.

Repairs after fallback review FB1 of 03c2fba9 (REJECT; record
`D:/uri-dev/lifecycle/OFFICE-DAILY-USE-r1/fallback/FB1_subagent_03c2fba9.audit.txt`). The earlier claim that the
fact check catches changed facts was wrong for changed digits and names: it was a substring test, so "7" was found
inside "17" and "Kumar" inside "Kumari". Corrected as follows:
- R2-01: a fact counts as present only as a whole token run (no letter, digit or '/' on either side, no digit group
  continuing it), with spacing normalised and case ignored.
- R2-02: OCR text cut by the size cap sets `truncated` and a per-page `cut` flag. Pages left out are listed in
  `ocr_skipped_reasons` (`page_limit`, `size_limit`, `time_limit`), and the app names the limit instead of saying the
  page could not be read.
- R2-03: a single capitalised word after to/from/Shri/Smt/Mr/Mrs/Ms/Dr, and numbers written in words ("twenty five
  thousand", not a lone "one".."ten"), are extracted and checked.
- R2-04: a draft message over 600 characters or a missing item over 120 is refused (BRAIN_OUTPUT_INVALID), not cut.
- R2-05: one OCR request has a 180 s deadline, below the app's 240 s request timeout. Pages left when it runs out are
  listed under `time_limit`.

Repairs after fallback review FB2 of d94961c7 (REJECT; record
`D:/uri-dev/lifecycle/OFFICE-DAILY-USE-r2/fallback/FB2_subagent_d94961c7.audit.txt`; R2-01..R2-05 confirmed fixed):
- R3-01: dates without a year ("3rd November", "November 3", "3 Nov", "15th August", with or without a year) are date
  facts.
- R3-02: a number's unit is part of the fact ("7 days", "10:30 PM", "5 lakh"). A number word right after a number,
  or right before a number-word fact, means the number changed ("twenty five thousand five hundred", "two lakh fifty
  thousand").
- R3-03: a draft block, message or missing item containing a character a Word document cannot hold is refused
  (BRAIN_OUTPUT_INVALID), so the fact check reads exactly the text that is written.
- R3-04: no name fact is taken from inside a reference number ("F.No. A-12/2026"). An amount may end in "/-", and
  lakh/crore match their plurals.
- R3-05: To Word writes "[Not read: page limit|size limit|time limit]" for pages OCR left out, and the app names the
  limit for To Word as it does for Copy text.
- R3-06: a text or To Word request has one 200 s deadline from the moment it arrives. The text worker gets at most
  150 s of it, and OCR gets what is left (at most 180 s).
- R3-07: the status note above is corrected.

Repairs after fallback review FB3 of da62f66d (REJECT; record
`D:/uri-dev/lifecycle/OFFICE-DAILY-USE-r3/fallback/FB3_subagent_da62f66d.audit.txt`; R3-06 was NOT FIXED there):
- R4-01 corrects R3-04. The R3-04 repair dropped a whole run of capitalised words when it touched a date or a
  reference. So in "3rd November Dr Anil Sharma" and "F.No. A-12/2026-Estt. Shri Ram Kumar" only the first name was
  checked, and a changed surname passed silently (d94961c7 had warned). Now only the words inside the date or
  reference are dropped, and the rest of the run is still a name.
- R4-02: "and <number word>" continues a number only when another number word follows it ("two lakh and fifty
  thousand"), not in "Rs. 25,000 and one laptop" or "10 days and one half day". "may" is a month only when written
  "May" after a day ("3 May") or before a day with an ordinal or a year ("May 3rd", "May 3, 2026"); a day must be 1 to
  31. "Rs 2,50,000/-" is the amount "2,50,000".
- R4-03 corrects R3-06. The R3-06 claim of "one 200 s deadline" was not true: page rendering used the raster
  worker's own 60 s and was not bounded, and a simulated request reached 256 s. Every wait is now bounded by the time
  left:
  - the text worker gets at most 150 s;
  - each page render gets at most 60 s;
  - each OCR run gets at most 90 s;
  - all text and OCR work ends 15 s before the 200 s deadline (at 185 s from arrival).

  The real bound on waiting is therefore 185 s plus the few seconds a stopped worker or Tesseract takes to exit. The
  remaining 15 s cover building the To Word document. That building (python-docx and the sanitizer on at most 500,000
  characters) is not itself time-limited. Whether a real WinRT page render ever comes close to 60 s is not measured.
- R4-04: common office units were added (choice: extend the list and state it exactly). Units that count as part of a
  number:
  - lakh(s), crore(s), thousand, hundred;
  - day(s), week(s), month(s), year(s), hour(s), minute(s);
  - per cent / percent, AM/PM, a.m./p.m.;
  - km(s), kg(s), kilometre(s), kilometer(s), kilogram(s), metre(s), meter(s), litre(s), liter(s);
  - post(s), vacancy/vacancies, copy/copies, page(s), person(s), member(s), officer(s), employee(s), set(s), unit(s),
    seat(s), file(s), room(s), nos.

  Any other word after a number is not part of the fact ("5 miles" is checked only as "5").

Repairs after fallback review FB4 of ef9ce641 (REJECT; record
`D:/uri-dev/lifecycle/OFFICE-DAILY-USE-r4/fallback/FB4_subagent_ef9ce641.audit.txt`; R4-01 was NOT FIXED there).
Four rounds each found a new variant, and each patch caused the next regression:
- R3-04's name skip lost names after references;
- R4-01's segmenting lost the first of two people;
- R4-02's "May" rule lost "May 3".

So the extractor was rewritten as one pipeline. The stages claim spans in a fixed order: references with their
designator, then dates, then digit numbers with units, then number words, then names split at every honorific, then
cue names. A corpus-driven property test now guards it: `tests/office_u2/test_office_daily_fact_corpus.py` with
`tests/office_u2/data/office_fact_corpus.json` (189 instructions). For every case it checks three things:
- the facts match the expected list;
- an identical draft never warns;
- every one-fact change warns about that fact. The changes are made in code: surname, first name, day, month,
  digits, unit, number word, a digit put in front.

The individual repairs:
- R5-01 corrects R4-01: a run of capitalised words is split at every honorific, each name keeping its own
  honorific ("Shri Ram Kumar and Smt. Sita Devi" gives two names). Kum, Km, Kumari and Sushri are honorifics and cue
  words.
- R5-02 corrects R4-02. "may" is the month, in any case, when:
  - the day has an ordinal;
  - a year follows;
  - on, by, from, till, until, dated, before, after or of comes before it;
  - or, after a day, it is written "May" or "MAY".

  "aged 55 may apply", "you may 3 times" and a sentence starting "May 3 officers" are not dates.
- R5-03: an identical draft never warns. The number-word continuation applies only to facts that end in a number
  word, and not when the instruction has the same following word. A number repeated in words in brackets ("3 (three)
  posts") is read as the number alone in the instruction and in the draft.
- R5-04: the designator (F.No., O.M. No., D.O. No., No.) is inside the claimed reference span. "Refer", "under" and
  the designators are never name words.
- R5-05: only the raster worker's TIMEOUT, or BUSY waiting for it, counts as a time limit late in a request. Any
  other render failure is raised as before.
- R5-06 (choice: bound it, not document it): the text op and the OCR page renders call the worker with
  `total_timeout`. The worker lock is then acquired with a timeout taken from the remaining budget, and the worker's
  start is bounded by what is left. A worker held by another request beyond that budget gives BUSY. The bound on
  waiting is 185 s plus the time a stopped process takes to exit. Building the To Word document (at most 500,000
  characters) is the remaining part that is not itself time-limited.

Repairs after fallback review FB5 of dbde00f6 (REJECT; record
`D:/uri-dev/lifecycle/OFFICE-DAILY-USE-r5/fallback/FB5_subagent_dbde00f6.audit.txt`). R2-01..R5-06 were confirmed
fixed. FB5 found two classes of silent miss that every earlier commit also had, and that this list did not mention.
The FB4 status above was therefore incomplete: those forms were never checked.
- R6-01: new date stages, all run before the digit stage, with the May rule kept:
  - "Nth (day) of Month [YYYY]" ("the 5th of June, 2026", "12th day of March 2026");
  - day ranges in one month ("9th-10th November", "3rd to 7th October 2026", "8 and 9 October 2026");
  - month-to-month periods ("April to June 2026", "May to July", "January - March 2026");
  - "Month[,] YYYY" ("April 2026", "May 2026", "April, 2026 to March, 2027").
- R6-02: names are deduplicated only on exact repeats. A name's occurrence inside a longer name of the same
  instruction does not count when the draft is checked, so "Shri Anil Kumar" next to "Shri Anil Kumar Singh" (in
  either order), "Smt. Sunita" next to "Smt. Sunita Sharma" and "Dr. Rakesh" next to "Dr. Rakesh Gupta" are each
  checked. The cue stage now skips only words inside a claimed span. A person named twice in the instruction needs
  to appear once; repeats are not counted.
- R6-03: a lone "one".."ten" is a fact when a unit from the list follows it ("seven days", "two officers").
- R6-04:
  - "Mohd." and "Md." do not end a sentence;
  - a bracketed honorific stays inside the name ("Dr. (Smt.) Kavita Krishnan");
  - a name needs a word that is not an honorific or a designator ("Dr" or "Room" alone is not a name);
  - a possessive "'s" is not part of the name;
  - weekday names are not names;
  - "5-day" is a number.
- R1-01/R1-02 follow-up: an uncued, yearless period with capitalised "May" ("May to July") is one date fact;
  lowercase verbal "may" remains excluded. A standalone month after an explicit time preposition ("in April",
  "in May") is also a date fact, so changing it in the draft produces FACT_MISSING.
- OFFICE-DAILY-USE-r6 review repair: month periods joined by "through" ("May through July") and relative months
  ("next April") are date facts. A full name after an explicit person label ("staff member ramesh kumar") is a name
  fact even when lowercase. Changing any of these in the draft produces FACT_MISSING.
- Corpus: 281 instructions. It now has templates for month-year, "Nth (day) of", periods, shared and prefix names in
  both orders, small number words with units, Mohd./Md. and bracketed honorifics. It also has 10 of the reviewer's
  out-of-corpus instructions (expected facts written by hand) and 20 new hand-written instructions in other forms.
  The 20 new ones first showed these misses:
  - silent: "9th" in "9th-10th November" was not a fact;
  - false facts: "Natarajan's" with the possessive, "Monday", "5-day" read as a reference;
  - split facts: "3rd to 7th October 2026", "8 and 9 October 2026" and "14th to 28th September 2026" were split
    into a number and a date. A change to either part still warned, so these were not silent.

  All of these are repaired above, and all 281 cases pass (a), (b) and (c).

OFFICE-DAILY-USE-r6 R3 repair:
- A lowercase full name after an explicit person label ends before "about" or "regarding"; a draft that keeps the
  person and rephrases the topic does not receive a false FACT_MISSING warning.
- A digit amount such as "Rs. 12" is not counted as present when the draft grows it to "Rs. 12 thousand".
- A standalone month modifying "salary" or "attendance" is a date fact, including "April salary processing".
  Replacing that month in the draft produces FACT_MISSING.

OFFICE-DAILY-USE-r6 R4 repair:
- Standalone month names identify office periods regardless of the following topic noun (for example, "June roster",
  "October duty chart", and "May roster"). A changed month produces FACT_MISSING. Lowercase auxiliary "may"
  and question forms such as "May staff apply?" remain excluded from this fallback.
- A lowercase full name after an explicit person label ends before a following clause or prepositional phrase
  (for example, "ramesh kumar on leave" and "asha devi under review"). Rephrasing that topic while keeping the
  person does not produce a false name warning.

OFFICE-DAILY-USE-r6 R6 repair:
- A lowercase full name after a letter-recipient phrase such as "letter to ramesh kumar about his transfer" is a name
  fact. Changing that recipient in the draft produces FACT_MISSING; a purpose phrase such as "letter to request
  transfer" is not treated as a name.

OFFICE-DAILY-USE-r6 R9 repair:
- A comma-delimited designation after an explicitly labelled person is excluded from name facts, as it already was
  after an honorific name. The person's name remains a fact when the draft rephrases the designation.
- A single capitalised name between an appointment verb and "as" is a name fact. Changing that appointee in the
  draft produces FACT_MISSING.

Fact-check scope (owner decision 2026-10-24, OD-OD-4). Driver r6 ran 11 Codex review and repair rounds on
c2d0786a..41eb14b4 and every round found another phrasing that a rule-based check misses or misreads (lowercase or
unmarked names, a month on its own, designations after names); it stopped at its 12-round budget. A deterministic
check cannot meet "every fact, never silently" for free text, so the owner scoped the guarantee to marked facts:
- names with an honorific (Shri, Smt., Kum., Sushri, Dr, Mr, Ms ...) or an explicit cue ("to", "from", "of",
  "appoint ... as", a letter recipient);
- dates with a day or a year (day-month, month-day, numeric dates, "Nth (day) of Month", "Month YYYY", periods);
- amounts and numbers written in digits, numbers in words, and a number's unit from the unit list;
- reference numbers with or without a designator (F.No., O.M. No., D.O. No., No.).
Anything outside this list is outside the guarantee, is listed below, and the Office shows the scope with every
draft ("Check before saving": what URI checks, what "Missing" and "Check" mean, and that the owner reads the whole
draft). The Save as card stays the only way a draft reaches disk.

Two signals (owner decision 2026-10-24, OD-OD-6, MM LDEC-014; replaces the OD-OD-5 exception). Each marked fact gets
at most one warning, with one of two codes:
- FACT_MISSING: the fact does not appear in the draft word for word. "Word for word" uses the per-kind token
  boundaries only: case and spacing are ignored; no letter or digit directly before or after it ("Kumar" is not
  inside "Kumari", "25,000" is not inside "1,25,000", "3 November" is not inside "13 November", FB1 R2-01); a date
  is not a different date; a number followed by another number word is a different number (FB4 R5-03); and a name
  inside a longer name that is itself a fact of the instruction does not count ("Shri Anil Kumar" next to "Shri Anil
  Kumar Singh" are two people, FB5 R6-02). A reference may be followed by "/" or by a date word written without a
  space. No extension rule ever produces FACT_MISSING.
- FACT_CHECK: the fact appears word for word, but every occurrence is inside what the rules read as a longer name or
  reference. The message names both forms: "'Anjali' appears only as 'Anjali Sharma'. Check it is the same
  person." / "'14/2/2026' appears only as '14/2/2026-1'. Check it is the same file." The panel shows it as a quieter
  "Check: ..." line; FACT_MISSING stays a warning-coloured "Missing: ..." line.
The guarantee: a marked fact that is absent from the draft (dropped, or replaced so that no word-for-word occurrence
is left: "Shri Ram Ji Gupta" for "Shri Ram Ji Lal", "Sunita" for "Anjali", a different file number) always gives
FACT_MISSING, and a faithful draft (one that keeps the fact word for word) never gives FACT_MISSING, whatever
surrounds the fact. Extensions give FACT_CHECK where the rules see them; the coverage list follows.

FACT_CHECK coverage (formerly the "Caught" / "Not caught" lists of "Exception inside the scope (owner decision
2026-10-24, OD-OD-5)", withdrawn by OD-OD-6):
- FACT_CHECK is given for:
  - a capitalised continuation of a name ("Anjali Sharma", "Smt. Sunita Kumari Singh"), including in a heading
    while the body names someone else ("Subject: Deputation of Anjali Sharma" with "Sunita" in the body, FB8);
  - an honorific word used as a middle name ("Smt. Sunita Kumari Singh", "Shri Ramesh Shri Vastava");
  - a hyphenated surname ("Anjali-Sharma");
  - a lowercase titled name continued at the end of a block when the name starts its block, up to four lowercase
    words after the title ("To / Shri ramesh kumar sharma", "To / Shri mohammad ahmed"), or continued before
    punctuation inside a block when no added word ends in -ed or -ing ("Leave of Shri ramesh kumar sharma."); and a
    capitalised word after a lowercase name ("Shri ramesh kumar Xavier");
  - a longer name with the same start found only in the draft ("Shri Anil Kumar Singh" for "Shri Anil Kumar");
  - a reference followed directly (or after a dot) by "-" or "/" and digits or a capitalised code of at most six
    letters ("14/2/2026-1", "...-II", "...-Admn", "...-Estt.-II", "...-Estt./2", "14/2/2026/1"), or by a
    part-file or section bracket ("(1)", "(II)", "(A)", "(Pt.)", "(Pt.II)", "(Part-I)", "(Part II)", "(Vol.2)"), or
    preceded by a code of at most three capitals or by digits and a hyphen ("A-14/2/2026").
- These are read as the same fact (no warning):
  - after a reference: a trailing lowercase word ("-dtd.", "-wef", "-reminder", "-dated", "./dated", "/dated"); a
    date or reference word in any case ("-Dated", "-Date", "-Dt.", "-DT", "-W.E.F.", "-Reg.", "-Wef", "-Ref",
    "-Vide", "/Dated", "/dt.", "/Dt."); a date word without a space ("HR/Trg/2026/145dt."); an ordinary bracket
    ("(copy)", "(PDF)", "(2 pages)", "(Annexure ...)"); a designator or word joined by a hyphen before it ("No-",
    "F.No-", "Ref-", "O.M.No-", "D.O.No-", "Letter-", "Memo-");
  - before a title: a courtesy or designation word ("Hon'ble Shri", "Hon'ble Minister Shri", "Late Shri",
    "Minister of State Shri", "MLA Shri", "Secretary Shri", "Collector Shri", "Adarniya Shri"): it is not part of
    the name (FB12 R2-01);
  - a lowercase titled name followed by a word ending in -ed or -ing at the end of a block it does not start
    ("Subject: Leave of Shri ramesh kumar sanctioned", FB12 R2-03), or inside a sentence ("Shri ramesh kumar
    reported for duty").
- Given FACT_CHECK although the draft is faithful (the rules read an extension; the owner checks and saves):
  - a capitalised ordinary word of up to six letters joined by a hyphen after a reference ("-Copy", "-Encl.",
    "-Urgent", "-Final", "-Draft", "-Annex", "-Sub:") and a hyphenated date after it ("-04.10.2026"), and the bare
    prefixes "OM-" and "DO-" (FB12 R2-04).
- No FACT_CHECK, so an extended draft gives no warning:
  - a lowercase name without a title continued with lowercase words ("ramesh kumar" -> "ramesh kumar sharma");
  - a lowercase titled name continued inside a sentence ("Shri ramesh kumar sharma is informed"), so that "Shri
    ramesh kumar reported for duty" is never a false warning (FB10 R2-03); one continued by a word ending in -ed or
    -ing before punctuation inside a block ("Shri mohammad ahmed." in a sentence), read as a verb; and one continued
    by an -ed or -ing word at the end of a block it does not start ("Leave of Shri mohammad ahmed" in a heading);
  - a titled lowercase name continued past four lowercase words;
  - a capitalised name continued in lowercase ("Ramesh iyer");
  - a continuation after a comma, in brackets or after a possessive ("Ramesh Kumar, Yadav", "Shri ramesh kumar
    (sharma)", "Ramesh's brother Suresh");
  - a second honorific with a dot after a name ("Anjali Dr. Sharma");
  - a capitalised connector ("Anjali Of Delhi");
  - a date, amount or number followed by more digits or words ("3rd October 2026-27", "15 days and 2",
    "Rs. 2,45,000/- lakh");
  - a reference extended in these forms (FB10 R2-04, FB11): "...-Estt.I" / "...-Estt.II", "..._1", an "A." prefix,
    an en dash ("...-Estt–1"), a part-file marker after a space (". (Pt.)"), a capitalised code longer than six
    letters, a lowercase code ("-admn"), a date or reference word used as a code ("-Reg.", "-DT."), and a word
    prefix that is not a code of at most three capitals ("Reg-", "ENo-");
  - a name continued after a post-nominal or a heading word ("Shri Anil Verma IAS Kumar", "Shri Anil Retd. Verma",
    "Shri Anil Verma With Kumar") (FB10 R2-05);
  - two people written next to each other without "and" or a comma when the second title is "Shri" or "Kumari"
    without a dot ("Shri Ram Kumar Shri Mohan Lal"): that title is read as a middle name ("Shri Ramesh Shri
    Vastava", "Smt. Sunita Kumari Singh"), so the pair is one name fact. Any other second title ("Smt", "Dr", "Mr",
    or any title with a dot) starts a second name (FB12).

An absent marked fact always gives FACT_MISSING. The FACT_CHECK coverage above is the only part that depends on how
the rules read a longer name or reference, and under OD-OD-6 its gaps are not blockers.

How the code reads the name cues of this scope (stated in FB6):
- An honorific may be followed by a capitalised or a lowercase full name ("Shri Ram Kumar", "Shri ramesh kumar").
  An honorific on its own is never a name.
- "to" and "from" mark one capitalised word ("to Ramesh").
- "of" marks one capitalised word ("the transfer of Ramesh", "the deputation of Anjali"). The exception is a
  designation or an institution before it ("the collector of Pune", "the director of Kolkata office", "copy of
  Annexure"): there the next word is a place, a body or a document, not a person.
- Multi-word capitalised names ("Ministry of Finance", "Government of India") are names in their own right.

Repairs after fallback review FB6 of 3f445a75 (REJECT; record
`D:/uri-dev/lifecycle/OFFICE-DAILY-USE-r7/fallback/FB6_subagent_3f445a75.audit.txt`):
- R2-01, a regression from r6 e1135343: the service checks the Brain's blocks joined by newlines, but a capitalised
  run did not stop at a newline. So "Shri Venkatesh Iyer" followed by an "Assistant Section Officer" block became one
  longer draft name, and a faithful draft got a false FACT_MISSING. A newline (block boundary) now ends a run.
- R2-02: in "letter to Shri ramesh kumar" the only fact was the honorific "Shri", so a changed name passed
  silently. An honorific followed by a lowercase full name is now one name ("Shri ramesh kumar", "Smt. anita
  sharma"), and an honorific alone is never a name.
- R2-03: the scope above names "of" as a cue, but the code had none. It is implemented as described above.
- R2-04: page images rendered for OCR are deleted when the document is closed, unless another open document shares
  the same preview cache. Ordinary preview page images are a cache and stay until the cache limit prunes them, as
  before.
- R2-05: the returned PDF text, page labels included, never exceeds the cap; when the labels would push it over,
  the text is cut and `truncated` is set.
- Corpus (295 instructions) has a new property (d). For every case a faithful multi-block draft (each fact in its
  own block between capitalised neighbour blocks, joined as the service joins the Brain's blocks) gives no warning,
  and every one-fact change made in it warns. There are new cases for an honorific with a lowercase name, for "of"
  names, and for the "Ministry of", "Government of India" and "<post> of <place>" negatives.

Repairs after fallback review FB7 of db652f38 (REJECT; record
`D:/uri-dev/lifecycle/OFFICE-DAILY-USE-r8/fallback/FB7_subagent_db652f38.audit.txt`; every earlier finding,
including FB6, confirmed fixed):
- R2-01, a regression from the FB6 R2-03 "of" cue: a faithful draft whose heading title-cases the phrase around a
  cued name ("Subject: Deputation of Anjali", "The Tehsildar of Haveli", "Filling Up of the Post of Superintendent")
  got a false FACT_MISSING. Two things caused it. "of" joins capitalised words into one draft name, so the heading
  became a longer name that seemed to contain the fact. And that longer name was matched in any case, so it also
  covered the body's "the deputation of Anjali". The FB6 note that such a word "can give a false warning if the
  draft drops it" did not describe this; here the draft kept it. The rule now:
  - a longer name hides a shorter one only when it extends the name itself ("Shri Anil Kumar" -> "Shri Anil Kumar
    Singh", FB5 R6-02 unchanged), not when a connector word (of, for, the, and, to, from, in, on, at, by) joins
    them;
  - a longer name found only in the draft covers only its own case-sensitive positions, never a lowercase
    occurrence in a body sentence;
  - tehsildar, talathi, patwari, SDM, BDO and SHO were added to the designation words before "of".
- R2-02: corpus property (e) (corpus now 297 instructions). Each fact is placed in a title-case heading
  ("Subject: Transfer of <name>" or
  "Subject: <fact>"), in a capitalised "To" block ("The Tehsildar of <name>") for names, and in a body sentence that
  is the instruction itself. That faithful draft gives no warning, and every one-fact change made everywhere the
  fact appears warns.
- R2-03 (choice: accept). A draft that only adds honorifics in front of a cued name ("to Ramesh" -> "Shri Ramesh")
  counts as the same name. A draft that adds more words ("Shri Ramesh Kumar") is still another person and is
  reported.
- Found while re-running the FB5 probes for this round: a date written with dashes or slashes around a month name
  ("5-May-2026", "06/Nov/2026") gave only the month as a fact, so a changed day passed silently. That came from the
  r6 bare-month rule. It is now one date fact, with corpus cases P-0 and P-1.

Repairs after fallback review FB8 of 1ad2e97f (REJECT; record
`D:/uri-dev/lifecycle/OFFICE-DAILY-USE-r9/fallback/FB8_subagent_1ad2e97f.audit.txt`; all FB7 and earlier findings
confirmed fixed):
- R2-01, a regression from the FB7 R2-01 repair. The FB7 rule above ("a longer name hides a shorter one only when
  it extends the name itself, not when a connector word joins them") was wrong as written: it looked only at the
  words before the name. So "Subject: Deputation of Anjali Sharma" counted as containing "Anjali", and a draft that
  extended the name in the heading and changed it in the body ("deputation of Sunita") passed silently. The same
  happened with "Promotion of Kavitha Reddy", "Deputation of Ramesh Kumar Yadav" and "Leave for Ramesh Kumar". The
  rule now:
  - words after the name that continue it make a longer name, whatever comes before;
  - with nothing after it (or a connector next), only the words between the last connector and the name count, and
    none or honorifics only is the same name (FB7 R2-01 and R2-03 kept).
- Same class, found by the follow-up search the coordinator asked for, now reported:
  - an honorific word at the end of a run is a surname ("Anjali Kumari"), not the start of another name;
  - a name joined by a hyphen to another word ("Anjali-Sharma") is part of a longer name;
  - a lowercase cued name followed on the same line by a capitalised name word ("Shri ramesh kumar Xavier") is a
    longer name.
- Checked and not silent in that search:
  - commas ("Anjali, Sharma", "Anjali Sharma, Assistant");
  - "and" ("Anjali and Sita Devi");
  - brackets ("Anjali (Sharma)");
  - designations after a name on the same line ("Anjali Sharma Assistant").

  These either keep the name as written or are reported.
- R2-02: corpus property (f). For every name, the draft extends it into a longer name in a heading ("Subject:
  Deputation of <name> Xavier") or in a "To" block ("<name> Xavier"), while the body changes the name or drops it.
  That draft must warn.
- In the per-line check the draft keeps its block boundaries: spacing is normalised within each line, and a newline
  is kept.

Repairs after fallback review FB9 of 2831f984 (REJECT; record
`D:/uri-dev/lifecycle/OFFICE-DAILY-USE-r10/fallback/FB9_subagent_2831f984.audit.txt`; FB8 and earlier confirmed
fixed; this is the last repair round for the extension class under OD-OD-5):
- R2-01: an honorific word without a dot in the middle of a run, after a name word and not after "and", is a middle
  name ("Sunita Kumari Singh", "Anil Kumari Prasad"). FB8 had fixed only the end-of-run position. Two people joined
  by "and" or a comma still split.
- R2-02: the FB8 limitation sentence said "Shri ramesh kumar sharma" was reported. That was true only inside a
  sentence; in a "To" block or a heading it passed silently. A titled lowercase name may now end at a newline and
  have up to four words, and it is read before the capitalised runs, so "Pension of Shri ramesh kumar sharma" no
  longer lends "Shri" to "Pension of Shri".
- R2-03: a reference followed directly by "-<letter or digit>", "(<letter or digit>", ".-", "./", ".(" or
  "/<letter or digit>", or preceded directly by "<letter or digit>-", is another file. A full stop, comma or space
  after it, and "F.No." / "O.M. No." before it, still match.
- R2-04: post-nominals and heading words end a name and are never part of it: IAS, IPS, IFS, IRS, MD (in capitals;
  "Md." stays a name word), Esq., Ji, Retd., PhD, MBBS, Under, Regarding, Sanctioned, With. So "Shri Ramesh Kumar
  IAS", "Dr. Rakesh Gupta MD" and "Subject: Deputation of Anjali Under Rule 12" give no false warning. A
  designation written after a name on the same line without a comma ("Shri Ramesh Kumar Assistant") is still
  reported, which is the safe direction.
- R2-05 (answered by OD-OD-5): the extension exception is stated in the scope paragraph above.
- Corpus (297 instructions): property (f) adds "<name> Kumari Xavier" and, for titled lowercase names, "<name>
  xavier". Property (e) adds a faithful "<name> IAS" / "Under Rule 12" draft. References get "-1", "(Pt.)" and
  "A-" changes in (c), (d) and (e).

Repairs after fallback review FB10 of 264e3036 (REJECT; record
`D:/uri-dev/lifecycle/OFFICE-DAILY-USE-r11/fallback/FB10_subagent_264e3036.audit.txt`). Two FB9 repairs caused
regressions, and one older false warning was found. All three are false warnings or a replaced fact, not
extensions, so they were blocking:
- R2-01, a regression from FB9 R2-03: "No-14/2/2026-Estt", "F.No-", "Ref-", "<file>-dated", "<file>-reg." and
  "<file>(2 pages)" gave a false FACT_MISSING. The FB9 sentence "preceded directly by '<letter or digit>-' ... is
  another file" was untrue for designators. A designator joined by a hyphen, those trailing words, and brackets
  longer than four characters are now excluded. "-1", "-II", "(1)", "(Pt.)", "-Admn" and "A-" still warn.
- R2-02, a regression from FB9 R2-04: "Ji" in the name-end list cut "Shri Ram Ji Lal" down to "Shri Ram", so a
  replaced surname passed silently. "Ji" is now trimmed only as the last word of a name ("Shri Ramesh Ji,").
- R2-03 (older): a faithful sentence "Shri ramesh kumar reported for duty on Monday." gave a false FACT_MISSING.
  The draft read "Shri ramesh kumar reported" as a longer name. Lowercase extra words in a draft name now count as
  an extension only when they reach a block end or punctuation, and never when one of them looks like a verb (ends
  in -ed or -ing). The FB9 exception text said a lowercase continuation "inside a sentence" was caught; it is now
  listed under "Not caught".
- Found while checking that the FB9 cases still hold: the FB9 middle-name rule read "Respected Shri Ramesh Ji" as
  one name. A salutation ("Respected", "Revered", "Dear", "Sir", "Madam") is no longer a name word before a title.
- R2-04 and R2-05: the forms are listed under "Not caught" above.
- Corpus: 301 instructions. New property (g) gives explicit faithful drafts that must not warn and changed drafts
  that must warn: "No-"/"F.No-"/"Ref-"/"O.M.No-"/"D.O.No-", "-dated", "-reg.", "(2 pages)", "Shri Ram Ji Lal",
  "Shri Ramesh Ji", and a lowercase titled name followed by a verb. Every FB9 case, test and probe result still
  holds.

Repairs after fallback review FB11 of 2641b828 (REJECT; record
`D:/uri-dev/lifecycle/OFFICE-DAILY-USE-r12/fallback/FB11_subagent_2641b828.audit.txt`; FB10 and earlier confirmed
fixed):
- R2-01, the FB9 reference-suffix class again. Faithful "...-Admn-dtd. 4.9.2026", "-wef", "-reminder",
  ".-dated", "./dated", "(copy)", "(PDF)" and "Letter-<ref>" gave a false FACT_MISSING. The FB10 list of excluded
  words could not cover the class, so the rule was replaced with a positive, code-shaped rule (stated under
  "Caught" above): only digits, a capitalised code of at most six letters or a part-file bracket after the
  reference, and only a code of at most three capitals or digits before it, make another file.
- R2-02: the FB10 -ed/-ing rule silenced a lowercase titled name extended at a block end ("To / Shri mohammad
  ahmed", "Shri ramesh kumar harding"). At a block end, any lowercase continuation is now an extension. The -ed/-ing
  rule applies only before punctuation inside a block, and "reported for duty" is still read as sentence text.
- R2-03: "(Pt.II)", "(Part-I)", "(Part II)" and "(Vol.2)" are caught again, because part-file brackets are now
  recognised by pattern.
- Where the reviewer's probes expected a warning and this rule gives none, the plan lists the form under "Not
  caught": "-Reg.", "-DT.", "-Dtd." read as date words; "Reg-", "ENo-" are not three-capital codes. These are
  reviewer expectations this rule does not adopt, because "-Dated" and "-reg." are faithful forms (FB10).
- Corpus (303 instructions): property (g) adds every reviewer faithful form, the part-file forms in both directions,
  and "Shri mohammad ahmed" / "khan" at a block end. The R10, R11 and R12 probes and fb1–fb10 were re-run; nothing
  changed for the worse.

Repairs after fallback review FB12 of 644be9b1 (REJECT; record
`D:/uri-dev/lifecycle/OFFICE-DAILY-USE-r13/fallback/FB12_subagent_644be9b1.audit.txt`; FB11 and earlier confirmed
fixed). The blockers were false FACT_MISSING warnings from the extension rules, so the owner split the check into
two signals (OD-OD-6, section 6) instead of another round of rule tuning. Correction history: OD-OD-5 above (from
FB9 to FB11) treated every extension the rules saw as FACT_MISSING; that is withdrawn, and the "Caught" / "Not
caught" lists became the FACT_CHECK coverage list. FB5 R6-01 (an added surname found only in the draft) and the FB8
heading case now give FACT_CHECK, not FACT_MISSING; FB5 R6-02 (two instruction facts with the same start) still
gives FACT_MISSING.
- R2-01: "Hon'ble Shri", "Hon'ble Minister Shri", "Late Shri", "Minister Shri", "Minister of State Shri", "MLA
  Shri", "Secretary Shri", "Collector Shri" before a name made one longer draft name. A courtesy or designation word
  before a dotless title is no longer a middle name, and a run of such words alone is dropped, so these drafts give
  no warning (and the instruction's own fact is "Shri Mohan Lal", not "Hon'ble Minister Shri Mohan Lal"). "Kumari"
  after such a word stays a middle name ("Joint Secretary Kumari Xavier").
- R2-02: "/dated", "/dt.", "/Dt.", "/Dated", "-W.E.F.", "-Date" and "145dt." after a reference. The token rule now
  lets "/" and a date word without a space follow a reference, and "date" and "W.E.F." are date words: no warning.
- R2-03: a subject line ending in a participle ("Subject: Leave of Shri ramesh kumar pending", "... received",
  "... sanctioned"). At a block end, an -ed or -ing word is a verb unless the name starts its block: no warning.
- Also found while re-running the R11 probes: "Shri Ram Kumar Smt Sita Devi" in the instruction (no comma) was one
  name fact, so a faithful draft that wrote the two names on separate lines gave FACT_MISSING (R11 K1, listed before
  as a limitation). Only "Shri" and "Kumari" (and "Km", "Kum") without a dot can now be a middle name; "Smt", "Dr",
  "Mr" ... after a name start a second name, so the two people are two facts and the draft gives no warning.
- R2-04 (LOW): "-Copy", "-Encl.", "-Urgent", "-Final", "-Draft", "-Annex", "-Sub:", "-04.10.2026", "OM-", "DO-"
  give FACT_CHECK, never FACT_MISSING (listed above).
- R2-05 (LOW): a single capital section bracket ("...-Estt.(A)", "...-Vig(A)") gives FACT_CHECK.
- Corpus (309 instructions): property (c), (d) and (e) expect FACT_MISSING for a replaced fact and FACT_CHECK for
  the reference changes that extend it ("-1", "(Pt.)", "A-"); (f) expects FACT_CHECK; (g) moves the 23 changed
  drafts that are extensions to a new checked_drafts list (FACT_CHECK, no FACT_MISSING) and adds six FB12 cases;
  new property (h) wraps every fact in the faithful forms above and asserts no FACT_MISSING.

Fact-check limitations that remain (outside the scope above):
- a single capitalised word after "of" that is a place or a body but follows a word not in the designation list
  (for example "the residents of Pune" is excluded, but "the visit of Pune officials" reads "Pune") becomes a name
  fact. That can give a false warning if the draft drops or rewords it, never a silent miss;
- a cued single name that the draft extends with more words ("Ramesh" -> "Shri Ramesh Kumar") gives FACT_CHECK,
  because the longer name may be another person;
- a number followed by a word that is not in the unit list ("3 vehicles") is checked as "3" only, so a changed noun
  is not reported;
- the same person named twice in the instruction needs to appear only once in the draft;
- lowercase names outside an explicit person label or letter-recipient phrase, and a single name without a cue word;
- a single all-capitals word such as a cadre ("LDC" against "UDC") is not a fact;
- several people without honorifics joined by "and" form one name fact ("Ram Kumar and Sita Devi"): a change to
  either still warns, but the warning names the pair;
- ordinal and fraction words ("first", "half");
- "and <number word>" followed by a noun ("Rs. 25,000 and fifty rupees more") is not read as part of the number;
- "May 3" without a preposition, ordinal or year before it (for example at the start of a sentence) is not a date;
- a fact written differently in the draft: "11 AM" against "11 a.m." or "23rd" against "23" is reported, not matched;
- swapped numbers and a fact present but used in the wrong place;
- words in Indian languages.

A FACT_MISSING or FACT_CHECK list is an aid to the owner's own reading, not a guarantee that nothing else changed.

## 5. Coordination

M95 owns `uri_privacy/` and touches `uri_office/service.py` `main()` only: this work does not edit `main()`. Vision F-1
touches the profile-switch block of `worker_bridge.py`: not edited here. Codex is booked for M95 driver r8 at 23:29
IST: driver reviews here are started only when Codex is free, otherwise the driver records NO_INDEPENDENT_REVIEWER
and the V3.1 fallback applies. No GPU-heavy run overlaps an M95 live run; Brain live runs only under the GPU lease.

## 6. Owner decisions (only genuine ones)

- OD-WI-1: writing suggestions in external apps need (a) a working Assist perception adapter (P9) and (b) granting
  `INSERT` for an "apply suggestion" button, which is a permission-boundary change. Until decided, external use is
  read-only and copy-based.
- OD-OD-4 (decided by the owner 2026-10-24): the OD-2 fact check guarantees marked facts only (section 4,
  "Fact-check scope"), and the scope is shown with every draft. Raising the driver budget to chase every phrasing and
  dropping FACT_MISSING were the alternatives offered.
- OD-OD-5 (decided by the owner 2026-10-24, MM LDEC-013, after FB9): "Fix these, then stop." The FB9 extension
  shapes were repaired. From then on, a marked fact kept word for word but extended into a longer name or number is
  a stated limitation (section 4, the exception in "Fact-check scope"), not a blocker. The guarantee stays: a marked
  fact missing or changed always warns. Superseded by OD-OD-6 for how extensions are signalled.
- OD-OD-6 (decided by the owner 2026-10-24, MM LDEC-014, after FB12): split the fact check into two signals.
  FACT_MISSING only when a marked fact does not appear word for word (per-kind token boundaries; no extension rule
  ever produces it, so a faithful draft never gets it). FACT_CHECK, a softer line, when the fact is there word for
  word but only inside what the rules read as a longer name or reference; its message names both forms. The service
  returns both in `warnings` with their codes; the Office shows "Missing: ..." warning-coloured and "Check: ..."
  quieter (section 4, "Two signals").
- OD-WI-2 (preference): default language `en-IN` (Indian English spelling) - chosen by default from the owner's
  context; one line to change.

## 7. Self-review against the Verification-First standard

Acceptance criteria precede work (section 4). Every inventory row cites code read at 277e81f9; prior records were
re-checked where claims mattered (pdf_text has no text route, no OCR, no spell library, Office already imports OI).
The spike numbers come from one PC run (stated as such, not a qualification). Unverified: Tesseract version and
language packs (checked at OD-3), Windows en-IN dictionary presence on other machines (the worker falls back to en-US
then rules only, named). Live criteria remain NOT VERIFIED until G-3 runs.
