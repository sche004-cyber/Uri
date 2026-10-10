# M1 research summary

Prepared 2026-10-10 in a cloud session, with the owner's PC offline. This is research and planning only: nothing is
implemented, merged or deployed.

## Baseline

`github.com/sche004-cyber/Uri`, operative canonical line `integration/git-sync-20261008` at `54ad7be`. The formal
`main` promotion is still pending. Production remains the legacy server (CUT-1). Details are in
`M1_REPOSITORY_CAPABILITY_INVENTORY.md` §1.

## Key findings

1. **The multi-user foundation already exists.**
   - Line A Core (M22.2-M22.7, accepted) has accounts, sessions, an admin role, per-user stores, grants and approvals.
   - 315 tests pass in the cloud.
   - It is not part of the integrated Working System (Line B), which is single-owner and loopback-only by a frozen rule.
2. **Four defects block a networked three-user setup.**
   - Anonymous requests are served as the owner (R1/R2).
   - Multi-action Gmail uses one install-wide mailbox token (R3).
   - **`fetch_url` is an SSRF path to loopback and the Brain's keyless endpoint** (SSRF-1, confirmed by a run).
   - Signup is open, plus there are weak at-rest secrets.
3. **The Brain is one slot on one 16 GB AMD GPU.** Three users need a fair queue and an honest "Brain unavailable"
   state. They do not need more inference capacity.
4. **Harness design is already compliant in spirit.** It uses unmodified CLIs, native per-client logins, a "shared
   login" stop condition, and never forwards API keys. Missing: per-user OS identity, and a remote-login path that
   avoids intermediating credentials.
5. **Licensing.** Central installation is not a licence to share credentials. Compliant modes:
   - each user's own subscription;
   - organization seats;
   - an owner-billed API key for the owner's authorized users (allowed by Anthropic's text);
   - the local Brain.
   Unattended scheduled work should not run on consumer subscriptions.
6. **Storage.** URI cannot reach any user folder today. Default-deny holds only because nothing can reach folders. A
   new fail-closed StorageBroker, consulted from the existing approval gate, can serve chat, harnesses, apps, the
   scheduler and future Office.
7. **Web Intelligence.**
   - Tavily search and `fetch_url` exist. Crawling, source records, citations, comparison, monitoring and all social
     APIs are missing.
   - Only YouTube metadata (Data API), RSS feeds, Bluesky/Mastodon, X (paid) and Reddit (after approval) have
     legitimate routes.
   - Meta and LinkedIn public research is not realistically available.
   - YouTube transcripts are available only for the user's own videos or media the user supplies.
8. **Browser automation is absent.**
   - Public browsing should run on the server: Playwright, per-task contexts, filtered egress.
   - Authenticated workflows should run on the user's own device, where they log in themselves. Every consequential
     action is approval-bound and re-checked against the live page.
9. **App hosting is absent.** A minimal host can reuse the supervisor's Job Objects, A2UI and the brokers, and render
   through A2UI only. The first proof is a tiny Notes app, not Office.
10. **REA** is an optional, isolated developer tool only. It is not a runtime dependency and adds no M1 value.
11. **The scheduler can be reused** with one instance per user (its lock is per state directory), plus a deterministic
    `web_watch.v1` template.

12. **Approved actions are broken for logged-in users (DEF-H1, confirmed by a run).**
    - When the orchestrator includes the principal, the approval store serializes it to a dict.
    - The fingerprint then mismatches, so approval returns an error and nothing executes.
    - The suspected R8 leak to the install token does not occur on this path. It is a fail-closed defect that blocks
      every consequential feature until it is repaired (ID-5).
13. **Plugins.** URI already has most of a plugin platform in the accepted M33 external-capability system:
    - descriptor contract with effect, approval and risk;
    - closed transports;
    - orthogonal per-user lifecycle;
    - per-user Fernet credential store;
    - fail-closed permission binding;
    - catalog-only natural-language lifecycle.
    Missing pieces:
    - an out-of-process ConnectorHost;
    - the operation taxonomy;
    - per-user OAuth for non-Google providers;
    - A2UI and HTTP lifecycle routes.
    Community MCP servers are reference material only. See `M1_PLUGIN_PLATFORM_ARCHITECTURE.md`.
14. **Identity.**
    - User IDs, sessions, the ADMIN role and per-user device revocation exist on Line A.
    - Real Client IDs bound to one principal (with spoof rejection) exist only in Line B pairing.
    - Line A `device_id` is an unauthenticated label, any device can log in, and no-login requests map to the install
      (owner) data.
    - The scheduler's default owner is the string `"owner"`.
    See `M1_USER_CLIENT_IDENTITY_MODEL.md` for the model, migration and tests ID-T1..T12.

## Reuse, don't rebuild

- Line A accounts, stores, grants and approvals.
- Runtime v1 and the GPU lease.
- The supervisor and harness adapters.
- A2UI.
- The scheduler.
- The external-capability contract, lifecycle, credential store and fail-closed binding (the plugin platform base).
- Line B client pairing semantics (the client identity model).
- FileStore and the verified copy-out pattern.
- `web_search`, `file_extraction` and the usage meter.
- faster-whisper.

## Potentially unnecessary dependencies

| Dependency | Why it can be skipped |
|---|---|
| A reverse proxy such as Caddy or nginx | `tailscale serve` plus the Python gateway are enough |
| Containers, Docker or WSL | Job Objects already exist; Vulkan GPU passthrough under WSL is poor |
| A second scheduler or job queue (Celery etc.) | The accepted scheduler covers it |
| A webview or iframe app runtime | It breaks A2UI's no-URL rule |
| SearXNG as the primary search | Unreliable upstream; AGPL |
| Google Custom Search | Discontinued 2027-01-01 |
| yt-dlp for YouTube | Terms |
| A Playwright MCP server for harnesses | It bypasses approval binding |
| REA | No M1 benefit |
| Multi-slot llama.cpp | Measured negative |

**Necessary new dependencies:** `playwright` with Chromium only (P4). Possibly a Flutter secure-storage package (D-7).

## Main risks

**Security**
- R1/R3/SSRF-1, until P1-1, the interim grant revocations and P1-5.
- Same-Windows-user harnesses until P1-6.
- Prompt injection from web content.
- SAFE-1 machine stability.

**Licensing**
- Hosted Claude Code interpretation (D-4a).
- Unattended subscription use.
- Platform terms for automated access.
- Reddit and Meta approvals.

**Delivery**
- Several fixes require frozen-code authorization (D-2).
- Single-slot latency is unmeasured.
- There may be unpushed work on the PC.

## Recommendation for the first implementation slice

**Start with P0-2 (including the ID-1 identity tests and the DEF-H1 reproduction) + P0-3, then P1-1 (`uri_gateway`, including ID-2).**
- All three are non-frozen and fully cloud-testable.
- P0-2 captures R1, R3, SSRF-1 and H-1 as failing tests on the base.
- P1-1 closes the critical anonymous-access path and adds the fair Brain queue without touching frozen code.
- Apply the interim admin grant revocations (multi-action `Gmail`, `fetch_url`) for non-owner users at the same time.
- The first usable three-user release is P0-2 → P0-3 → P1-1 → P1-2 → P1-3 → P1-4. That is about 2-3 cloud sessions
  plus one PC session.

## Report map

| # | Report |
|---|---|
| 1 | `M1_REPOSITORY_CAPABILITY_INVENTORY.md` |
| 2 | `M1_THREE_USER_SERVER_ARCHITECTURE.md` |
| 3 | `M1_HARNESS_ACCESS_AND_LICENSING.md` |
| 4 | `M1_STORAGE_ACCESS_DESIGN.md` |
| 5 | `M1_WEB_INTELLIGENCE_ARCHITECTURE.md` |
| 6 | `M1_SOCIAL_PLATFORM_RESEARCH.md` |
| 7 | `M1_BROWSER_AUTOMATION_AND_SECURITY.md` |
| 8 | `M1_REA_EVALUATION.md` |
| 9 | `M1_APP_HOSTING_DESIGN.md` |
| 10 | `M1_IMPLEMENTATION_SLICES.md` |
| 11 | `M1_OFFLINE_BLOCKERS_AND_STATUS.md` |
| 12 | This file |
| 13 | `M1_PLUGIN_PLATFORM_ARCHITECTURE.md` (added in round 4) |
| 14 | `M1_USER_CLIENT_IDENTITY_MODEL.md` (added in round 4) |

Supporting material: `README.md` (acceptance criteria, self-review, isolation record) and
`evidence/CLOUD_TEST_EVIDENCE.md`.
