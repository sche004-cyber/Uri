# W2 — Web & Document Intelligence: plan and acceptance criteria

Status: **PLANNED** (self-reviewed: FTS5, `Page.find_tables`, POSIX `resource` limits and the pytesseract `timeout`
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
