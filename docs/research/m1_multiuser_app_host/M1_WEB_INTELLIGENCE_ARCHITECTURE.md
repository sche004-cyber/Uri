# M1 Web Intelligence architecture

Proposal. Platform-specific access rules are in `M1_SOCIAL_PLATFORM_RESEARCH.md`. Platform connectors are plugins, specified in `M1_PLUGIN_PLATFORM_ARCHITECTURE.md`. Browser automation is in
`M1_BROWSER_AUTOMATION_AND_SECURITY.md`.

## 1. What exists today

| Capability | Status | Evidence |
|---|---|---|
| `web_search` | Accepted (M15.1). One Tavily query per call, using a server-wide `TAVILY_API_KEY`. Returns title, URL and content. Never invents results. | `uri_core/tools/web_search.py:28,74,78` |
| `fetch_url` | Accepted (M19). Takes the URL deterministically from the user's own text (`_extract_url`), never from model arguments. Allows http(s) only, has a byte cap, and extracts text through `file_extraction`. **SSRF-1:** it reaches loopback and follows redirects (RUN). It is READ_ONLY, so no approval is required. | `uri_core/tools/fetch_url.py:85-131`; `capabilities/registry.py:20`; `evidence/CLOUD_TEST_EVIDENCE.md` Run 3 |
| `file_extraction` (PDF, DOCX, XLSX, text, OCR fallback) | Accepted. Reused by both tools above. | `uri_core/services/file_extraction.py` |
| `skill.yt_dlp` `dump_json` | Accepted (M33.1 B2). Pinned to Wikimedia Commons file URLs. | `uri_core/external/descriptors/yt_dlp.py` |
| Per-user usage meter and pre-flight ceilings | Accepted (M22.7) | `URI_MILESTONE_TRACKER.md:112`; `usage_meter.py`, `usage_ceiling_store.py` |
| Evidence ledger and evidence-fact integrity | Accepted | `uri_core/core/evidence_*`, `test_evidence_*` |
| Scheduler (one owner per instance, harness template only, "never consults the Brain") | Integrated, not activated | `docs/scheduler/SCHEDULER_ARCHITECTURE.md:10,35,75` |

**Missing:**
- following links and crawling across pages;
- structured extraction of tables, notices and downloads into records;
- source records with retrieval timestamps;
- multi-source comparison and conflict detection;
- report generation with citations into a user folder;
- monitoring and change detection;
- any social platform API.

## 2. Service design (PROPOSED)

The new non-frozen package `uri_web/` holds one service. Core reaches it through new capabilities that are registered
the same way as the existing ones, so they go through the same gate, grants and modes. Every surface reaches it
through Core: text, voice (TI and live voice already land in Core turns), Workspace and Companion A2UI surfaces, and
per-user scheduler jobs. No surface gets a private path.

```
 Core turn / scheduler job (principal = user)
   └─ capability web.search | web.read | web.collect | web.research | web.watch | video.search | video.transcript
        └─ uri_web
             ├─ providers/search: tavily (existing key), brave (optional), searxng (optional, self-hosted)
             ├─ SafeFetcher: egress policy (§4), robots.txt and per-site policy, byte, time and redirect caps
             ├─ extract: HTML→text (existing parser), tables, links, downloads → file_extraction
             ├─ SourceStore[user]: SourceRecord per retrieval
             ├─ compare: claim clustering + conflict flags (Brain via the fair queue)
             ├─ report: cited Markdown/DOCX → StorageBroker default output
             └─ watch: snapshot + diff + dedup for the scheduler
```

### SourceRecord

Every fact URI shows must come from a SourceRecord. Its fields:

- `source_id`, `user_id`, `task_id`
- `requested_url`, `final_url`, `redirect_chain`
- `retrieved_at` (UTC), `http_status`, `content_type`, `bytes`, `sha256`
- `extraction_method`, `robots_decision`, `provider` (`tavily`, `direct`, `youtube_api`, …)
- `access_basis`: `public_web`, `official_api`, `user_account`, or `user_upload`
- `analysed_scope`: `full_text`, `snippet_only`, `metadata_only`, `transcript`, or `none`

`analysed_scope` makes the "metadata vs content actually analysed" distinction explicit and machine-checkable.

### Citation rule

- Reports cite `final_url` and `retrieved_at` for every claim.
- A claim backed only by `snippet_only` or `metadata_only` sources is labelled as such.
- A claim with no source is either dropped or marked as URI's reasoning.
- This extends the existing evidence-integrity discipline (`test_evidence_fact_integrity.py`).

### Comparing sources

- Claims are extracted per source by the Brain.
- Claims are grouped, and disagreements are flagged with both citations.
- URI never silently picks one side.
- Freshness is shown with `retrieved_at` and, where present, the page's own date.

### Downloads

1. Each download is saved to the user's private quarantine, through the StorageBroker `create` into
   `users/<uuid>/storage/quarantine/`.
2. It is checked: the extension allow-list (FileStore's), magic-byte sniffing that must agree with the declared type,
   size caps, zip-bomb limits (fixing ZIP-1), and no execution. Office macros are flagged.
3. It moves to a user folder only through the broker's normal grant and approval.

## 3. Search providers

Facts here are EXT-S: secondary sources, dated 2026.

| Provider | Status | Fit |
|---|---|---|
| Tavily | Already integrated. About 1,000 free credits/month, then about $8 per 1,000 basic searches. | Keep as the default; it is already accepted |
| Brave Search API | Independent index; about $5 per 1,000 with a monthly credit | Optional second provider for comparing results |
| SearXNG (AGPL-3.0, self-hosted metasearch) | Upstream engines often block datacenter and automated traffic; no SLA | Optional; not recommended as the primary |
| Google Custom Search JSON API | Closed to new customers; discontinued 2027-01-01 | **Do not adopt** |
| Bing Search API | Retired August 2025 | Unavailable |

**Per-user cost control.**
- Each provider call is metered to the requesting user through the existing usage meter.
- Ceilings use the existing pre-flight enforcement.
- The provider key is owner-owned and server-held. It is not a personal credential, so it is acceptable to share
  centrally, provided the provider's terms allow multi-user end use. **Check this per provider at implementation.**

## 4. Egress policy (SafeFetcher), which fixes SSRF-1 at the new boundary

Required for every server-side fetch: `uri_web`, the repaired `fetch_url`, the browser and the app broker.

1. Allow http and https only. Ports 80 and 443 by default; other ports need a per-source allow-list.
2. Resolve DNS **once**, then connect to the resolved IP: no second lookup, which defeats DNS rebinding. Refuse
   loopback, RFC1918, CGNAT `100.64/10` (this includes **tailnet addresses**), link-local, multicast,
   `169.254.169.254`, IPv6 ULA and link-local, and IPv4-mapped forms.
3. Re-apply the check on **every redirect hop**. Allow at most 5 redirects.
4. Strip credentials from URLs. Send no cookies, except from browser profiles in P4.
5. Apply a fixed `User-Agent` that identifies URI.
6. Rate-limit per host and per user.
7. Check `robots.txt` for automated retrieval and record the decision. Sites whose terms forbid automated access are
   refused, using the per-site policy table maintained in `M1_SOCIAL_PLATFORM_RESEARCH.md`.
8. Defence in depth on Windows: an outbound firewall rule for the fetcher's service account that blocks private
   ranges. Unverified, PC-blocked.

The existing `fetch_url` lives in frozen code. Until it is repaired:
- `fetch_url` is revoked from non-admin users through the existing admin grants (`PUT /admin/users/{id}/grants`);
- the repair (P1-5) routes it through SafeFetcher.

## 5. Untrusted content (prompt injection)

- Retrieved text is wrapped as **data** in a typed `untrusted_web_content` block. It is never merged into system or
  developer instructions.
- URI's existing authority rule applies unchanged: the model's proposed arguments never cross the capability boundary
  (`fetch_url.py:11-21`; `orchestrator.py` docstring). Web text therefore cannot name new URLs to fetch, files to
  write or recipients to message. Only the user's own request text and allow-listed follow-up links can.
- Link following during research is limited to:
  - the same registrable domain as a user-named or search-returned source;
  - a maximum depth of 2;
  - a per-task page budget.
- Any consequential action suggested by web content needs the normal approval card. The card shows that the proposal
  came from web content.
- The existing response-validation layer checks that output quotes are present in the SourceRecords (`test_response_validation.py`).

## 6. Scheduled Web Intelligence (reuses the accepted scheduler)

Do not build a second scheduler. The design:

| Concern | Design |
|---|---|
| Ownership | One scheduler instance per user. The engine lock is per state dir (`engine.py:106-119`), and the API already serves one principal (`SCHEDULER_ARCHITECTURE.md:77`). Jobs belong to that user only. |
| New template | `web_watch.v1`, added in non-frozen `uri_scheduler/`. Its parameters: sources (URLs, RSS/Atom feeds, YouTube channel ids, saved searches), cadence, output workspace, change threshold. Activation still requires the owner of the job to confirm the exact `proposal_sha256` (`SCHEDULER_ARCHITECTURE.md:54`). |
| Collection | Deterministic `uri_web` calls: no Brain and no harness. This keeps the scheduler's "runs without the Brain" rule (A-AC1). |
| Change detection | Per-source canonicalisation (strip boilerplate), then `sha256` plus a text diff against the last snapshot. Dedup by canonical URL and content hash. RSS `guid` or `updated` is used where present. |
| Summarisation | After collection, the job submits *one* low-priority turn to the gateway **as the job's user**. The fair queue gives interactive turns priority. Local Brain only (mode M-4); never an unattended subscription harness. |
| Delivery | The briefing goes through the StorageBroker to the user's selected Office workspace output. If that location is unavailable, the briefing goes to PENDING_DELIVERY (storage design §8). An A2UI `web_watch.briefing` notification goes to that user's Companion. |
| Retry and recovery | Reuse the scheduler's states (`MISSED`, `run_late`/`skip`, `NEEDS_ATTENTION`) and its idempotent attempt keys. A fetch failure is recorded per source; a partial briefing says which sources failed. There is no retry storm: exponential backoff per host. |
| Limits | Per-user caps: sources per job, pages per run, bytes, runs per day, provider credits. A global cap on concurrent web jobs (for example 2) runs through supervisor-style admission pools. |
| External actions | A watch job never posts, messages, submits or deletes. Any such step becomes an approval card for the user. |

## 7. Limits and uncertainty

- Provider prices and terms are EXT-S.
- How much Brain time briefings use on the single slot is unmeasured (PC-blocked).
- Whether robots and terms checks keep government notification sites reachable has to be confirmed per source. Many
  publish RSS, which is the preferred route.
