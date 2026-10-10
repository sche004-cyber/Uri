# M1 implementation slices

This document holds the single slice numbering used by every M1 report. Nothing here is authorized to start: each
slice needs its own owner authorization.

**Every slice follows the same rules:**
- an isolated branch and worktree from the then-current canonical tip, re-checked first;
- characterization tests come first;
- an independent review (Codex or a fresh Claude session; the implementer never approves its own work, `AGENTS.md:62`);
- fast-forward-only integration with the owner's authorization;
- production is a separate decision (CUT-1);
- GPU work runs under `gpu_lease run --purpose …`.

**Legend:**
- **Cloud** = fully testable in a Linux cloud session.
- **PC** = needs the owner's Windows PC, GPU, logins or devices.
- **FROZEN** = touches the protected prefixes in `scripts/ws_frozen_check.py`, so it needs owner decision D-2.

## P0: Baseline verification

| ID | Slice | Acceptance criteria | Where | Frozen? | Size |
|---|---|---|---|---|---|
| P0-1 | Re-check the canonical tip and any PC-local work | The tip SHA is recorded. The TIWS push record and staging receipt are reconciled. The frozen check passes on the PC. | PC (part) | No | S |
| P0-2 | Characterization tests, as test files only | Tests that **fail on the base**, proving: R1 (anonymous request reaches owner state), R3 (multi-action Gmail uses the install token), SSRF-1 (`fetch_url` reaches loopback and follows redirects), H-1 (approved Gmail/Drive actions keep the principal; passes or fails honestly) | Cloud | No (root `test_*.py` are not protected) | S |
| P0-3 | Dependency declaration | `requirements.txt` gains the Google client libraries (D-REQ-1). A clean cloud venv collects every Line A test. | Cloud | No | XS |

## P1: Three-user readiness

| ID | Slice | Acceptance criteria | Where | Frozen? | Size |
|---|---|---|---|---|---|
| **P1-1** | `uri_gateway`: auth boundary + fair Brain queue | <ol><li>Every USER/ADMIN route returns 401 without a bearer, and Core is never called.</li><li>Explicit PUBLIC allow-list. Remote `/auth/signup`, `/identity` and `/audit/shadow-comparison` are refused.</li><li>ADMIN routes require `/auth/me` role=ADMIN.</li><li>`/connections/*/authorize` and `POST /connections/credentials` are refused for every remote caller.</li><li>`X-Forwarded-*` headers are stripped; rate limits are keyed per principal.</li><li>One in-flight Brain turn per user; round-robin across 3 fake users with bounded wait; `TURN_IN_PROGRESS` for the same user.</li><li>A simulated lease holder produces `BRAIN_UNAVAILABLE{purpose}` within 1 s.</li><li>The audit log has no content.</li><li>The gateway refuses a non-loopback bind without TLS.</li><li>The frozen check is unchanged.</li></ol> | Cloud | No | M |
| P1-2 | Secret guard + loopback Core | The gateway refuses to start if the provider or external-credential secrets are the hard-coded defaults or shorter than 32 bytes. Core is bound to 127.0.0.1. | Cloud (logic) | No | S |
| P1-3 | Brain bridge (configuration) + live fairness | Three users complete turns on Runtime v1 through the `lm_studio` `base_url`. Tool calls work or fail honestly. No Ollama is resident. Decode is ≥60 tok/s with the client open. The p95 wait is recorded. | PC | No | S |
| P1-4 | Tailnet deployment | Only the gateway port is reachable from the tailnet. The TLS certificate is valid. A remote device logs in and runs a turn. Non-tailnet LAN hosts are refused. | PC | No | S |
| P1-5 | Authorized frozen repair batch | <ul><li>T1: H-1 (fix only if P0-2 fails).</li><li>T2: per-user Gmail on multi-action and evidence paths (R3).</li><li>T3: per-user temp folders.</li><li>T4: per-user graphify index.</li><li>T5: the tier keeps the mode.</li><li>T6: Google tokens encrypted at rest.</li><li>T7: suspension honoured.</li><li>T8: signup-closed flag.</li><li>**T9: `fetch_url` goes through SafeFetcher (SSRF-1).**</li><li>T10: zip decompression bound (ZIP-1).</li></ul> The full cloud suite shows no new failures. The P0-2 tests now pass. | Cloud, then PC chain | **Yes (D-2)** | M |
| P1-6 | Per-user execution identity for harnesses | <ul><li>One low-privilege Windows account per user.</li><li>CLI homes and workspaces ACL'd to that account.</li><li>The supervisor launches under that account.</li><li>User B's process gets ACCESS_DENIED on user A's home.</li><li>No shared login (ISO-1 extended).</li><li>Job limits applied.</li><li>`CLAUDE_CODE_OAUTH_TOKEN` forwarding resolved per D-4b.</li><li>Routing table `user → (account, home, mode)`; a missing entry is refused.</li></ul> | PC | **Yes** | L |
| P1-7 | Per-user Google + Calendar | Three users get three mailboxes and calendars. Calendar starts read-only, with writes approval-gated. The publishing status follows D-5. Cross-user access is negative. | PC (consent) | **Yes** | M |
| P1-8 | Client updates | Gateway base URL. Queue and `BRAIN_UNAVAILABLE` states. Secure token storage (D-7). | PC (Flutter) | No | M |

**Interim protections** until P1-5 lands, using existing admin grants (`PUT /admin/users/{id}/grants`): revoke `Gmail`
(the multi-action capability) and `fetch_url` from non-owner users.

## P2: User-controlled storage

The design is in `M1_STORAGE_ACCESS_DESIGN.md`.

| ID | Slice | Where | Frozen? | Size |
|---|---|---|---|---|
| P2-1 | Broker core: path safety, fail-closed grants, workspaces, hash-chained audit | Cloud | No | M |
| P2-2 | Delivery manager (pending delivery, re-validated retry) | Cloud | No | S |
| P2-3 | Decision-point integration (`storage_*` capabilities in the existing gate) | Cloud | **Yes** | M |
| P2-4 | A2UI storage surfaces + `catalog/v2` (List row / Table) | Cloud (Python), PC (Flutter) | No | M |
| P2-5 | Client folder picker, local grants, scoped transfer | PC | Part (`uri_ui` protected files untouched) | M |
| P2-6 | NTFS ACL enforcement | PC | No | M |
| P2-7 | Harness, scheduler and app adoption (copy-in/out through the broker) | Cloud (fake harness), PC | Part | M |
| P2-8 | Drive folder grants, scope reduction | PC | **Yes** | M |

Acceptance criteria are the test lists in `M1_STORAGE_ACCESS_DESIGN.md` §9.

## P3: Basic Web Intelligence

The design is in `M1_WEB_INTELLIGENCE_ARCHITECTURE.md`.

| ID | Slice | Acceptance criteria | Where | Frozen? | Size |
|---|---|---|---|---|---|
| P3-1 | SafeFetcher + SourceRecord store (`uri_web/`) | <ul><li>A corpus of loopback, RFC1918, CGNAT/tailnet, link-local, metadata IP, IPv6 ULA and mapped forms is all refused.</li><li>A redirect to a private address is refused at the hop.</li><li>DNS rebinding (first answer public, second private) is refused.</li><li>Robots decisions are recorded.</li><li>Every response yields a SourceRecord with timestamps and a hash.</li><li>Per-user stores.</li></ul> | Cloud | No | M |
| P3-2 | Search providers (Tavily reuse, optional Brave) + per-user metering | Calls are metered to the requesting user. A ceiling refuses before the call. No key appears in logs. | Cloud (fake HTTP) | No | S |
| P3-3 | Research and report pipeline | <ul><li>Link following is limited to the same site, depth 2, within a page budget.</li><li>Claims are cited with `final_url` and `retrieved_at`.</li><li>`metadata_only` and `snippet_only` are labelled.</li><li>Conflicts are flagged with both citations.</li><li>The report is delivered through the StorageBroker.</li></ul> | Cloud (fake Brain), PC (live) | No | M |
| P3-4 | Download validation | Quarantine, type sniffing that must match, size and zip limits, never executed, macros flagged | Cloud | No | S |
| P3-5 | YouTube Data API metadata + permitted transcripts | Per-user quota budget. `metadata_only` labels. Transcripts only through the permitted routes. No yt-dlp for YouTube. | Cloud (fake API), PC (key) | No | M |
| P3-6 | Reddit, after approval | Only after Reddit grants access | Blocked externally | No | S |
| P3-7 | `web_watch.v1` scheduler template | <ul><li>Per-user instance.</li><li>Proposal-hash activation.</li><li>Change detection and dedup.</li><li>Partial-failure briefings.</li><li>Backoff.</li><li>The summary turn goes through the gateway as the job's user, on the local Brain.</li><li>Delivery or pending.</li><li>No external actions.</li></ul> | Cloud (fake time and fetch), PC | No (`uri_scheduler/` is not protected) | M |

## P4: Authorized browser automation

The design is in `M1_BROWSER_AUTOMATION_AND_SECURITY.md`.

| ID | Slice | Where | Frozen? | Size |
|---|---|---|---|---|
| P4-1 | Server-side public browsing: Playwright Chromium, a per-(user, task) context, a filtering proxy, downloads to quarantine | Cloud (Linux Chromium) | No | M |
| P4-2 | Client-side authenticated browser worker (per-user profile on the device) | PC | Part | L |
| P4-3 | Approval-bound consequential actions with a live-page re-check before execution | Cloud (local test site), PC | No | M |
| P4-4 | Per-site policy table enforcement | Cloud | No | S |

## P5: App-host demonstration

The design is in `M1_APP_HOSTING_DESIGN.md`.

| ID | Slice | Where | Frozen? | Size |
|---|---|---|---|---|
| P5-1 | Registry, manifest validation, fail-closed app grants | Cloud | No | S |
| P5-2 | Launcher on supervisor Job Objects with limits and accounting | PC | D-6 | M |
| P5-3 | A2UI surface bridge + service broker | Cloud | No | M |
| P5-4 | `uri.demo.notes` 0.1.0 → 0.2.0 (migration) | Cloud (logic), PC (launch) | No | S |

## P6: Extended social intelligence

| ID | Slice | Where | Size |
|---|---|---|---|
| P6-1 | Bluesky and Mastodon read adapters | Cloud | S |
| P6-2 | X API pay-per-use adapter behind owner spend approval | Cloud (fake), live needs a key | M |
| P6-3 | Own-account Meta and LinkedIn actions (post or draft) after app review | Blocked externally | M |

## Smallest first release (recommended)

**P0-2 → P0-3 → P1-1 → P1-2 → P1-3 → P1-4**, with the interim grant revocations.

- That gives three users chat, memory, files, per-user single-action Gmail and Drive, and `web_search`, over a private
  network, with fairness on the Brain.
- **Next:** P1-5 (after D-2), then P2-1/2/3/4 and P3-1/2/3.
- **Estimate:** about 2-3 cloud sessions plus one owner-present PC session for the first release.

## Correction record: old to new slice IDs

The earlier commits used S-numbers. This mapping replaces them:

| Old (commits `be55d19`, `a6ef74f`) | New |
|---|---|
| S1 | P1-1 |
| S2 | P1-2 |
| S3 | P1-5 |
| S4 | P1-3 |
| S5 | P1-4 |
| S6 | P1-7 |
| S7 | P1-6 |
| S8 | P5-1..P5-4 |
| S9 | P1-8 |
| S10 | P2-1 |
| S11 | P2-3 |
| S12 | P2-2 |
| S13 | P2-4 |
| S14 | P2-5 |
| S15 | P2-6 |
| S16 | P2-7 |
| S17 | P2-8 |

SSRF-1, P3, P4 and P6 are new in this revision.
