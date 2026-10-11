# W2 — Web & Document Intelligence: plan and acceptance criteria

Status: **PLANNED** — 24 acceptance criteria, delivered as W2a + W2b (§4d) (self-reviewed: FTS5, `Page.find_tables`, POSIX `resource` limits and the pytesseract `timeout`
parameter confirmed present in the cloud venv). Not implemented, not reviewed, not integrated.

Written 2026-10-11 from:
- the owner's "W2 Web & Document Intelligence: Implementation Instructions";
- the earlier brief `docs/plans/W2_SITE_DOCUMENT_SEARCH_BRIEF.md`;
- an inspection of the repository at W1/A0 candidate `3dd9cde` / `20a646f`.

Execution order is unchanged:
1. W1/A0 is integrated.
2. SSRF-1 is accepted and integrated.
3. The W2 branch is restarted from that canonical tip.

No live retrieval happens before step 2. W2 runs under the `uri-development-lifecycle` skill, and integration needs D1.

## 1. What the repository already provides (reused, not rebuilt)

| Need | Existing component | Frozen? | How W2 uses it |
|---|---|---|---|
| Safe network fetch | `uri_web/safe_fetch.py` SafeFetcher + `netpolicy.py` (per-hop URL/DNS/IP checks, pinned connection, redirect re-checks, byte cap, deadline, cancel) | no (W1) | Every W2 request. Adds an opt-in `extra_types` so a fetch can return a PDF body; W1 defaults unchanged (same change as SSRF-1 plan item 2, which lands first) |
| Untrusted content, extraction, citation checks | `uri_web/untrusted.py`, `extract.py`, `synthesize.py` (D7 verbatim quantities) | no (W1) | Answering over document text; instruction-like text stays data |
| Job model | `uri_web/pipeline.py` ResearchJob: budgets, progress, cancel, A2UI surface | no (W1) | Pattern and surface for document jobs |
| PDF text and OCR | PyMuPDF (`requirements.txt` `pymupdf>=1.24`), `pytesseract`; `uri_core/services/pdf_reader.py` | **PDFReader frozen** | Same libraries, run in a W2 worker process with limits (§4). PDFReader itself has no page cap, OCR timeout or isolation and cannot be changed. Its Tesseract path setting is reused |
| Office documents | `uri_core/services/file_extraction.py` (DOCX/XLSX/CSV) | frozen | Called unchanged, inside the same limited worker |
| Relationships | `uri_core/core/graph_store.py` M23 `GraphStore(storage_path=...)`: nodes/edges with provenance, confidence, status | frozen | A **separate** store file `uri_workspace/web_documents/graph.sqlite3`, never the user's `users/<id>/graph.sqlite3` |
| Scheduled refresh | `uri_scheduler/engine.py` | no | Later phase only (§7). Refresh is manual or on demand first |
| Privacy rules | D5 (no sensitive-data learning), D8 (fail-closed values) | — | §5 |

New code lives in a new package, `uri_web/docs/`, plus tests in `tests/web/w2_*`. No frozen file changes and no new
dependency.

## 1a. Owner decision D11 (2026-10-11): W2 runs on ARN and URI's runtime Graphify index

The owner said Graphify (with ARN/RAR) must be involved in all memory indexing and information retrieval. Inspection
showed:
- the runtime Graphify Foundation (`uri_core/core/graphify_index.py`) is a pointer-only index with five kinds
  (capability, skill, workflow, memory_pointer, connected_service) and no document kind;
- ARN.1 (`uri_core/core/arn/`) is the accepted deterministic narrowing engine;
- ARN.2 (PDF/document narrowing) is planned but explicitly not authorised;
- all of these are frozen.

The developer `graphify` CLI (code graph) is a separate tool.

Chosen: **ARN + Graphify pointers**.

- **ARN without a frozen change:**
  - W2 search and question answering run through `ARNEngine` (imported, unchanged).
  - Each site, document and page checked is `record_source_checked`, so repeated searches are refused.
  - Document candidates are `add_candidates`, and user clues go through `apply_user_clue`.
  - A miss returns ARN's case summary and clarification recommendation (ARN never writes the question).
  - Narrowing follows the ARN.2 plan's order: metadata → document → page → targeted extraction → exhaustive scan,
    bounded by the ARN `CostCeiling`.
  - ARN state stays per task and is never persisted (ARN rules).
- **Narrow frozen exception, controlled like D2:**
  - `uri_core/core/graphify_index.py` gains a `document` pointer kind: doc_id, title, site, date, reference_no,
    department. No page text and no personal-data fields, because the index holds pointers, never content.
  - It also gains a `documents` refresh scope fed by the W2 index, so Brain hints (M34 `relevant_subset`) can point to
    relevant indexed documents.
  - Hint filtering in `decision_engine.py` currently keeps only skill/memory_pointer. Whether `document` pointers need
    a one-line change there is decided at implementation; any such file is named explicitly in
    `authorized_protected_changes`. Nothing else frozen changes.
  - Documents flagged `personal_data = candidate` get no pointer; a later relevant-subset test checks this.
- **Not authorised:** ARN.2 inside `uri_core` remains a separate, unauthorised scope. W2 uses ARN's engine and order
  without building ARN.2.

Added acceptance:
- **W2-AC16:** W2 searches record every source in ARN, never repeat a search, and stop at the ARN ceiling. A miss
  returns an ARN case summary.
- **W2-AC17:** Document pointers appear in a user's Graphify hint for a relevant question and carry no page text.
  Personal-data documents have no pointer. The existing M30/M34 Graphify tests still pass (37 + M34 suite). Only the
  named frozen files change.
- **W2-AC18:** The per-user Graphify view holds document pointers only from documents that user indexed or that are
  shared under an approved scope, never another user's (see GRAPHIFY-LEAK-1).

## 2. Reconciliation with earlier requirements

| # | Earlier requirement | New instruction | Resolution |
|---|---|---|---|
| R-1 | Brief: bounded crawl of any public site, sitemap/feeds, daily refresh | Approved domains or scoped sources only, plus user-supplied URLs; manual/on-demand refresh first | The newer, narrower instruction wins. Crawl only inside an approved scope; no daily refresh in this milestone |
| R-2 | Brief: scanned pages read by the Brain's vision | Tesseract OCR on scanned pages only when needed | OCR via Tesseract; Brain vision not used in W2 |
| R-3 | Brief: benchmark of 30–50 real sites, NIT Sikkim included | Crawl only approved domains | **Owner-gated: the approved domain list.** Until decided, development uses an offline corpus of recorded or synthetic documents, and user-supplied URLs work on demand. A live benchmark is NOT VERIFIED until the domains are approved and egress allows them |
| R-4 | "Reuse the existing PyMuPDF integration" | Page limits, OCR timeouts, isolation | The frozen PDFReader cannot enforce limits, so W2 reuses its libraries and configuration in a limited worker (§4). Disclosed for review; no owner decision needed (no frozen change, no new dependency) |
| R-5 | M23 GraphStore is per user | Keep document knowledge, relationship graph, user memory and temporary context distinct | A dedicated W2 store; nothing is written to `MemoryStore`, user graph, skill/drafting memory or learning (§5) |
| R-6 | D5 is written for Assist adapters | Apply D5 to personal data in public documents | Applied as in §5 |
| R-7 | Brief: JavaScript-built sites go to RW1 | Unchanged | Reported as NOT REACHED until RW1 |

No conflict needs a new owner decision except R-3 (which domains). R-3 does not block implementation.

## 3. Data model

**Document index** (`uri_web/docs/index.py`, SQLite with the standard library, at
`uri_workspace/web_documents/index.sqlite3`):

- **`documents`:** `doc_id`, `source_url`, `final_url`, `referring_url`, `nav_path` (list of menu or link labels),
  `site`, `title`, `date` (+ `date_source`: page | metadata | text), `reference_no`, `department`, `retrieved_at`,
  `content_sha256`, `version`, `status` (CURRENT | CHANGED | GONE), `personal_data` (none | candidate).
- **`versions`:** `doc_id`, `version`, `content_sha256`, `retrieved_at`, `page_count`, `changed_pages`. Historical
  hashes are kept, so changes are detectable after the PDF is deleted.
- **`pages`:** `doc_id`, `version`, `page_no`, `text` (capped), `method` (native | ocr), `ocr_confidence`,
  `headings`, `tables` (list of cell grids, kept only when PyMuPDF's table finder returns a consistent grid),
  `flags` (ocr_low_confidence, table_ambiguous, personal_data_candidate, instruction_like).
- **Search:** SQLite FTS5 when it is available in the build; otherwise a plain-token fallback, recorded per
  installation. Checked here: FTS5 present (SQLite 3.45.1); on the owner's Windows Python it is NOT VERIFIED.
- **Storage root:** resolved through the frozen `uri_core/core/portable_paths.py` helpers (imported, not changed),
  the same way the existing stores resolve `uri_workspace/`; the paths above are relative to that root.

**Relationship graph** (separate GraphStore file; packaged types only, so no registry change):

- **Nodes:** `Document` (external_ref = doc_id), `Source` (site), `Department`.
- **Edges:**

| Edge | When |
|---|---|
| `RELATED_TO` with `attributes.kind = attachment_of` | A PDF linked from a notice page |
| `RELATED_TO` with `kind = same_reference` | Exact normalised reference number shared |
| `RELATED_TO` with `kind = same_department` / `same_subject` | Metadata or heading match; candidate only |
| `RELATED_TO` with `kind = corrigendum_of / amends / cancels` | See the evidence rule below |
| `SUPERSEDES` | Only when the newer text explicitly says so (see the evidence rule below) |
| `DERIVED_FROM` with `kind = version_of` | A new content hash at the same URL |

- **Evidence rule.** Every edge records in `provenance` the source URLs, page numbers and the exact quoted evidence
  sentence. It also records `attributes.verification` = `candidate` | `confirmed`, and a `confidence`.
  - `confirmed` amend, cancel or supersede edges need explicit text naming the other document's reference number
    or title, matched to an indexed document: for example "in supersession of", "this corrigendum to", "stands
    cancelled", "amended as".
  - A shared reference number or a later date alone gives `candidate` at most.
  - Unconfirmed relations are never shown as fact. Answers say "may be related (unconfirmed)".

## 4. Processing pipeline and limits (all in one documented config, `uri_web/docs/limits.py`)

1. **Discover:**
   - A user-supplied URL is fetched on demand.
   - An approved scope (domain + optional path prefix) is crawled by link discovery: menus and submenus read for
     links, plus page bodies.
   - Discovery stays on the scope, honours robots.txt, has a per-host rate limit and never follows external links
     out of scope.
   - It records the navigation path and the referring page.
2. **Fetch:** through SafeFetcher only.
3. **Spool:** to a private job directory (`uri_workspace/web_documents/tmp/<job_id>/`, mode 0700, random names).
4. **Extract:** in a separate worker process (`python -I -m uri_web.docs.worker`).
   - Process limits: CPU time, address space and wall clock (POSIX `resource`; on Windows a Job Object is NOT
     VERIFIED, and wall-clock kill plus page caps apply).
   - The worker refuses: more than `MAX_PAGES` pages; encrypted PDFs; byte size over the limit; PyMuPDF open errors.
   - Native text is taken per page. A page is OCRed only when its native text is below `OCR_MIN_CHARS` and it has
     images; that is bounded by a per-page OCR timeout and `MAX_OCR_PAGES`.
   - The worker never runs embedded JavaScript, never opens embedded files or links, and never renders forms.
5. **Index:**
   - Pages, metadata and hashes are capped per page, per document and per index.
   - Instruction-like text is flagged by the W1 `untrusted` rules.
6. **Delete:**
   - The spool file goes in `finally`, and also on failure, cancel and worker kill.
   - At start-up, leftover `tmp/<job_id>` directories older than the job timeout are swept and the sweep is logged
     (interrupted-job recovery).
   - Indexing is transactional, so an interrupted job leaves no partial document.

Limits (initial values, to be confirmed by the reviewer): download 20 MB; 300 pages; 50 OCR pages per document;
30 s OCR per page; 120 s per-document worker wall clock; 1 GB worker address space; 200 KB of text per page;
5 MB of text per document; crawl budget 200 pages, depth 4, 1 request/s per host, 2 concurrent document workers.

## 4a. Frequently needed documents (owner direction, 2026-10-11)

The owner asked that "files that are required often may also be saved for faster retrieval". This refines §4 step 6
(delete after processing). The default stays delete-after-processing; a bounded cache is added:

- **When a document is kept:**
  - It has been needed at least `CACHE_MIN_USES` times within `CACHE_WINDOW_DAYS` (initially 3 uses in 30 days).
    A use is an answer citing the document, or the user opening it.
  - Or the user pins it.
- **Where and how much:** `uri_workspace/web_documents/cache/`. Total size cap `CACHE_MAX_MB` (initially 500 MB) and
  per-file cap = the download limit. Least-recently-used documents are evicted first; pinned documents are never
  evicted automatically.
- **Integrity:** every cached file is checked against its recorded `content_sha256` before use.
  - On refresh, a changed document replaces the cached copy, and the old hash stays in `versions`.
  - A document that disappears from the site (GONE) stays cached only if pinned.
- **Never cached:** documents flagged `personal_data = candidate` (D5). Encrypted or refused files.
- **Controls:** list, pin, unpin and clear the cache. Clearing never touches the index text, so answers and citations
  keep working from stored text.
- **Speed without the file:** answers already come from the indexed page text, which is fast without the original.
  The cache helps with re-reading the original, re-running OCR with better settings, and offline viewing.

Acceptance:
- **W2-AC15:** a document reaches the threshold and is cached; LRU eviction holds the cap; a pinned document
  survives eviction.
- A hash mismatch makes the cached copy unusable and it is re-fetched.
- A personal-data document is never cached.
- Clearing the cache keeps answers working.

## 4b. Named collections and the "current rules" view (owner approval, 2026-10-11)

These were added after the owner asked what URI would do with "maintain a database of rules and regulations
concerning NIT Sikkim".

### Named collections

- **What a collection is:** a named, topic-filtered set of documents within an approved scope, for example
  "NIT Sikkim — Rules & Regulations". It is defined by:
  - name;
  - scope (domain and path prefixes);
  - topic criteria (document kinds such as regulation, ordinance, statute, handbook, policy, circular amending a rule,
    and keywords);
  - owner (the user who created it).
- **Stored as:** a `collections` table (id, name, scope, criteria, created_by, created_at) and `collection_members`
  (collection_id, doc_id, `membership` = matched | candidate | added_by_user | excluded_by_user, `evidence` = the
  title, heading or sentence that matched, decided_at).
- **Membership rules:**
  - Documents outside the topic (event notices, tenders, results) stay out.
  - Uncertain matches are `candidate` and are shown as such.
  - The user can add or exclude a document, and that decision is kept across refreshes.
- **Operations:** create from a request, list, browse (by kind, date or department), search within, refresh,
  export (CSV or Markdown with links and page citations; no document bodies beyond the cited sentences), delete.
  Deleting a collection removes the collection rows only; the shared document index stays.
- **Graphify and ARN:**
  - A collection gets a Graphify pointer (name, scope, member count, no content).
  - Searches within a collection run through ARN with the collection as the candidate set.
- **Privacy:** personal-data-flagged documents can be members only as `candidate`. Their passages follow §5
  (targeted questions only), and they never appear in exports.

### Current-rules view

- **What it shows:** for each rule document in a collection, its status, computed only from **confirmed**
  relationships (§3 evidence rule):

| Status | Meaning |
|---|---|
| IN FORCE (no confirmed amendment) | No confirmed change found |
| AMENDED | Confirmed amendment(s) listed in date order, each with its evidence quote, link and page |
| SUPERSEDED / CANCELLED | The confirmed replacing or cancelling document is linked |
| STATUS UNCONFIRMED | Only candidate relations exist, e.g. a newer document with the same reference number or subject; shown as "may be affected by …", never as superseded |

- **Amendment chain:** the original document, then each confirmed corrigendum or amendment, then the latest. The
  "current text" of a clause is never merged or reconstructed. URI shows the original clause and the amending
  sentence(s) side by side, each quoted verbatim with citations (D7 applies to numbers).
- **When a document changes:** a new version of a rule document (hash change) marks the view "changed since last
  refresh", with the changed pages listed.
- **Disclaimer:** answers built from the view say what the documents state. They are not legal interpretation.

Acceptance:
- **W2-AC19 Collections:**
  - A collection is created from a request; topic filtering puts regulation documents in, keeps event notices and
    tenders out, and marks uncertain ones `candidate` (fixture site).
  - User add and exclude decisions survive refresh.
  - Export carries links and page citations and no personal-data passages.
  - Deleting the collection keeps the index.
  - Search within a collection is limited to its members and recorded in ARN.
  - The collection pointer appears in the Graphify hint, without content.
- **W2-AC20 Current rules:**
  - The status is computed only from confirmed relationships. Negative tests: a later date alone, or a shared
    reference number alone, gives STATUS UNCONFIRMED, never SUPERSEDED or AMENDED.
  - The amendment chain is ordered and every link carries an evidence quote, link and page.
  - Clause text is shown verbatim, never merged.
  - A changed rule document is flagged with its changed pages.

## 4c. The document-retrieval skill: intents and owner examples (owner approval, 2026-10-11)

The owner gave three examples and said they are only *some* of the information-retrieval work expected from URI:

1. "Maintain a database of rules and regulations concerning NIT Sikkim" → §4b (collections, current rules).
2. "Maintain all items/agendas as indexes for all the minutes of the meetings of BoG, Senate, FC and BWC for NIT
   Sikkim" → W2-AC21 and W2-AC22.
3. "Show links for all the relevant DoPT orders related to leave", then the user opens each and asks URI to
   summarise it → W2-AC23 and W2-AC24.

W2 is therefore built as **one general document-retrieval skill**, not three features. Every request maps to one of
five intents over the same index, ARN narrowing, Graphify pointers and citation rules. The examples become benchmark
tasks and fixtures, never per-site code.

| Intent | Example | Output |
|---|---|---|
| FIND / LIST | "show links for all relevant DoPT orders on leave" | Ranked list with links and a coverage statement (W2-AC23) |
| ANSWER | "what is the minimum attendance rule?" | Cited answer (§6) |
| SUMMARISE | "summarise this one" | Cited summary of one chosen document (W2-AC24) |
| MAINTAIN | "maintain a database of …" | Named collection with refresh (W2-AC19/20) |
| STRUCTURE | "index all agenda items of …" | Item-level index (W2-AC21) |

### Agenda-item index for meeting minutes (W2-AC21)

- **Bodies:** governance bodies are configurable per institution. Default set: BoG, Senate, Finance Committee (FC),
  Building and Works Committee (BWC).
- **Item records:** each minutes or agenda document is split into items. Each item record holds:
  - body, meeting number and date;
  - item number as printed (for example "45.3");
  - the agenda heading;
  - the decision or resolution quoted verbatim;
  - status (approved | recommended | deferred | noted | ratified | withdrawn | not stated);
  - page citation and split confidence.
- **Uncertain splits:** an uncertain split is a `candidate`, and the user can correct it; corrections persist.
- **Item relations** (same evidence rule as §3; `confirmed` only where the text states the link):
  - `recommended_to` (FC/BWC/Senate → BoG)
  - `approved_in` / `ratified_in` (a later meeting)
  - `action_taken_on` (an action-taken report)
  - `carried_over_to`
- **Questions this supports:** "items about X since <date>", "what happened to <body> item N", "pending action-taken
  items". References such as "item 3 of the last BoG" are resolved by RAR against the indexed items.
- **Privacy:** items about named individuals (appointments, promotions, disciplinary, pay fixation) are personal
  data.
  - Listings and exports show the item number and a generic topic only.
  - The text is shown only for a question about that matter.
- **Financial figures** are quoted verbatim or omitted (D7), never summed or reconstructed.

### Non-web sources: uploaded and Drive minutes (W2-AC22)

- Unpublished minutes and agenda papers enter the same index from:
  - files the user uploads (existing `read_attached_file` path);
  - a Google Drive folder the user approves (existing Drive tools, read-only);
  - a local folder the user approves.
- **Labels:** each document is labelled `public` (found on an approved public site) or `internal` (user-provided).
  Internal documents are:
  - visible only to the user who added them;
  - never exported, and never given a Graphify pointer outside that user's view, unless the user says so;
  - never fetched or shared with any external service.
- **Same handling as web documents:** extraction limits, temporary-file deletion (originals stay where the user
  keeps them), provenance (file name, Drive file ID, folder path, hash) and versioning apply unchanged.

### Find and list across official sources (W2-AC23)

- For a FIND request, URI searches the approved scope (for example the DoPT orders and OM pages, once approved) or
  the collection, narrowed through ARN.
- **What URI returns:** a ranked list of matching documents. Each entry has:
  - title, order/OM number, date, issuing department;
  - the link (to the document and its referring page);
  - a one-line description quoted from the document's own subject line, with a page citation;
  - flags: `superseded/amended (confirmed)` or `may be affected (unconfirmed)` from §3/§4b.
- **Coverage statement (mandatory):** URI never says "all" without one. It states:
  - which sources and sections were searched and how many pages and documents were checked (from the ARN case
    summary);
  - what was not reached (JavaScript-built pages → RW1, login-only, egress-blocked, budget stopped);
  - the date of the last refresh.
- **Opening:** opening a link is the user's action, in the user's own browser (hand-off). URI never browses for the
  user.
- **Approvals:** a new source in the request (for example dopt.gov.in) is added only after the user confirms it as
  an approved scope.

### Summarise a chosen document (W2-AC24)

- **Which document:**
  - "summarise this / the second one / the 2019 OM" is resolved by RAR against the list URI just showed;
  - or, if the user has the document open and has granted Assist OBSERVE for that tab, by matching the tab's URL
    to an indexed document (A0 rules; no new permission);
  - an ambiguous reference makes URI ask which one (ARN clarification recommendation; URI does not invent).
- **How the summary is built:** from the indexed page text (fetched first if not yet indexed) through the W1
  synthesis path.
  - Every summary sentence is checked against a cited source sentence (wording, negation).
  - Quantities (days of leave, amounts, dates, percentages) are quoted verbatim with their page, or omitted (D7).
  - Unverifiable sentences are dropped and counted.
- **Shape:** key provisions; who it applies to; effective date; what it amends or supersedes (confirmed only);
  each with page citations. Length on request (brief / detailed).
- **Safety:** instructions inside the document are untrusted data (§6). The summary never adds advice or
  interpretation beyond the text.

Acceptance:

- **W2-AC21 Agenda items:**
  - On fixture minutes for the four bodies (native text and scanned), items are split with correct numbers,
    headings and statuses.
  - Uncertain splits are `candidate`; user corrections persist across refresh.
  - Cross-body relations are `confirmed` only with explicit text (negative tests: the same topic in two meetings
    alone gives `candidate`).
  - Personal-data items show only a generic topic in listings and exports.
  - "Item N of the last BoG" resolves through RAR.
- **W2-AC22 Non-web sources:**
  - Uploaded and Drive-folder documents are indexed with provenance and the `internal` label.
  - Another user's view, exports and Graphify pointers never show them.
  - No external call is made for internal documents.
  - Originals are untouched.
- **W2-AC23 Find and list:**
  - Every listed item has link, number, date and a quoted subject with citation.
  - Confirmed and unconfirmed supersession flags are correct.
  - The coverage statement is always present and matches the ARN case summary.
  - A source not yet approved triggers a confirmation, not a crawl.
  - The DoPT-leave-style benchmark runs on an offline fixture; live is NOT VERIFIED until the domain is approved and
    egress allows it.
- **W2-AC24 Summarise:**
  - The document is chosen through RAR from the last list, or the active-tab URL under an OBSERVE grant.
  - Ambiguity gives a clarification, not a guess.
  - Every summary sentence has a page citation and passes verification; quantities are verbatim or omitted.
  - An instruction embedded in the document does not change the summary's behaviour.

## 4d. Delivery in two lifecycle milestones

W2 now has 24 acceptance criteria. One independent review of the whole change would be slow and less reliable, so W2
is delivered as two milestones. Each has its own branch from the canonical tip, its own independent review and its
own D1 integration. Same order in the queue.

- **W2a — core retrieval.**
  - Covers: discovery and fetch, extraction/OCR worker and limits, document index and versions, temporary files and
    cache, relationship evidence rules, privacy separation, ARN narrowing, Graphify document pointers (D11), and the
    FIND / ANSWER / SUMMARISE intents.
  - Acceptance: W2-AC1…AC18, AC23, AC24.
- **W2b — structured knowledge.**
  - Covers: named collections and the current-rules view, the agenda-item index, and non-web (uploaded/Drive/local)
    sources.
  - Acceptance: W2-AC19…AC22.
  - Depends on W2a being integrated.

## 5. Privacy and knowledge separation

- **Where W2 writes:** only the W2 index and the W2 graph store. It never calls `MemoryStore`, `user_memory`,
  `skill_memory`, `drafting_memory`, the user graph or any learning or preference writer.
  - **Test:** a run with those modules patched to fail on any write; plus a static import check.
- **Personal-data candidates.** Detected per page by heuristics (counts as candidates, never as proof). Signals:
  - roll, registration or enrolment numbers;
  - phone numbers and e-mail addresses;
  - date of birth;
  - tables of person-like names with marks or ranks.
- **Effect of the flag:**
  - Flagged passages are excluded from digests, snippets and "related documents" listings.
  - An answer may use a flagged passage only when the question explicitly targets that content (for example a
    specific roll number or name the user supplied). Even then it shows only the matching row or sentence.
  - Values from flagged pages are never written anywhere outside the index (D5).
- **Temporary retrieval context** (job spool, worker output) is deleted with the job.

## 6. Answers

- Answers are built from indexed page text through W1 `synthesize.verify`, so the same citation, wording, negation
  and D7 checks apply.
- **Citations** give the source URL, `page_no` and the retrieval date.
- **Quantities:** quoted verbatim from a cited page, or omitted.
- **OCR uncertainty:**
  - A page with low OCR confidence, or a quantity that came from OCR, is quoted only with an "OCR — check the
    original" mark.
  - A quantity read from a table flagged `table_ambiguous` is never quoted; the answer points to the page instead.
- **Instructions inside documents** are data and never commands. The W1 untrusted rules and the surface filters
  apply.

## 7. Refresh

- Manual or on demand: re-fetch an indexed document or scope, compare hashes, and record a new version or GONE.
- A scheduled refresh through `uri_scheduler/engine.py` is a later, separate step, off by default and enabled per
  scope by the owner.

## 8. Acceptance criteria

**Functionality**

- **W2-AC1 Discovery:** for a fixture site with nested menus (including submenus present in the HTML), the document
  links are found within budget. Scope is respected and no request leaves it (counted at the fetch layer).
  robots.txt is honoured.
- **W2-AC2 Extraction:**
  - Native-text PDFs give per-page text with correct page numbers.
  - A scanned page is OCRed only when needed (the decision is unit-tested in the cloud with a fake OCR engine).
  - Headings and metadata are extracted, and tables only when the grid is consistent.

**Privacy, cleanup and isolation**

- **W2-AC3 Temporary files:** no PDF remains after success, failure, cancel or worker kill. The start-up sweep
  removes leftovers from a simulated crash.
- **W2-AC4 Provenance:** every indexed document has source URL, referring URL, navigation path, title/date/reference/
  department when present, `retrieved_at` and hash. Version history detects a changed document after the PDF is
  deleted.
- **W2-AC5 Relationships:**
  - Attachment and same-reference edges are created with evidence.
  - Corrigendum, amend, cancel and supersede edges are `confirmed` only with explicit text.
  - A later date, or a shared reference number alone, never yields `confirmed`/`SUPERSEDES` (negative tests).
  - Every edge stores its evidence quote and source.
- **W2-AC6 Separation:** no writes to user memory, the user graph or learning (patched-store test + static check).
  The W2 graph lives in its own file.
- **W2-AC7 Personal data:** passages flagged as personal-data candidates never appear in digests, snippets or
  unrelated answers, and appear only as the matching row for a targeted question (tests with a synthetic results
  list).

**Answers**

- **W2-AC8 Citations and D7:** every answer sentence cites URL and page. Quantities are verbatim from the cited page
  or omitted. OCR-derived quantities carry the OCR mark; ambiguous-table quantities are never quoted.
- **W2-AC9 Injection:** instructions embedded in a PDF or a page never change URI's behaviour and are never shown as
  instructions.

**Security and resources**

- **W2-AC10 Security:**
  - All W1 SSRF and redirect tests still pass.
  - W2 fetches go only through SafeFetcher (a static check plus a test with the network layer patched).
- **W2-AC11 Malformed files:** truncated, encrypted, oversized, too many pages, deeply nested objects, a "zip bomb"
  stream, and JavaScript/embedded-file PDFs are refused or handled within limits, and the worker kill is tested.
  Limits live in one configurable place and are documented.
- **W2-AC12 Cancel and restart:**
  - Cancel stops crawl and extraction within a bounded time.
  - A job killed mid-index leaves no partial document.
  - A restart resumes or re-runs cleanly.

**Gates and process**

- **W2-AC13 Gates:** no new failures against the baseline in the combined gates. No frozen-file change. No new
  dependency in `requirements.txt`.
- **W2-AC14 Process:** independent separate-process ACCEPT on the exact commit, then D1 integration with a receipt,
  and updates to the qualification ledger and dashboard.

## 9. NOT VERIFIED here (follow-up qualification on the owner's PC)

- Real Tesseract OCR: the binary is absent in this cloud container. OCR is tested with a fake engine and the
  decision logic only. The Windows Tesseract path is that of `pdf_reader.py`.
- Windows worker limits (Job Object): POSIX limits are tested here; Windows relies on the wall-clock kill and page
  caps.
- A live crawl of real institutional sites, including NIT Sikkim: owner domain approval is needed, and egress is
  blocked here.
- Performance on large real PDFs on the owner's hardware.

## 10. Owner-gated items

- **Approved domain list** (R-3): not blocking.
- **Enabling scheduled refresh later:** not blocking.
- **Optional, environment only:** installing `tesseract-ocr` in the cloud development environment's setup script.
  This would let real OCR be tested here; it is not a URI runtime dependency.
