# M1 browser automation and cross-cutting security

This document covers browser automation (P4) and the consolidated M1 threat model. Storage-specific controls are in
`M1_STORAGE_ACCESS_DESIGN.md` §5-§8. Web egress rules are in `M1_WEB_INTELLIGENCE_ARCHITECTURE.md` §4-§5.

## 1. Existing capability

| Item | Status | Evidence |
|---|---|---|
| Browser automation framework in URI (Playwright, Selenium, CDP) | **None** | grep of `*.py`, `*.dart`, `*.json`, `*.txt` returns no hits |
| Harness web tools (Claude Code `WebFetch`/`WebSearch`) | Off unless `capsule.network` is set; Bash always denied | `uri_harness_adapters/__init__.py:27-41` |
| Contained process execution | Job Objects, kill-on-close (Windows) | `uri_supervisor/winproc.py` |
| Approval bound to an exact action | Approval store argument fingerprint; A2UI surface digest; supervisor approval digest | `approval_store.py`; `uri_a2ui/surface.py:76,145`; `uri_supervisor_bridge/worker_service.py` |

## 2. Framework choice

**Recommendation: Playwright for Python.**
- Apache-2.0.
- Supports Linux, macOS and **Windows** for Chromium, Firefox and WebKit (EXT-P: github.com/microsoft/playwright-python).
- Python matches the server stack.
- Its isolation model fits per-user browsing: each `BrowserContext` has its own cookies, storage and cache, and
  `launch_persistent_context(user_data_dir=…)` keeps a profile on disk.

Alternatives considered:

| Alternative | Verdict |
|---|---|
| Selenium | Heavier; weaker isolation primitives |
| Raw CDP | Chromium only; more code |
| Playwright MCP server, or giving harnesses a browser | **Rejected for M1.** It would give a subscription harness an authenticated browser and bypass URI's approval binding |

**Cost:** a new dependency (`playwright`) plus browser binaries of a few hundred MB per engine. Install Chromium only.

## 3. Where the browser runs

| Use | Location | Reason |
|---|---|---|
| **Public, unauthenticated browsing** (JS-rendered pages, following links, downloading public documents) | **Server**, one ephemeral context per task and per user, run as that user's low-privilege Windows account (P1-6), behind SafeFetcher-equivalent egress (§4) | No personal credentials involved. The server egress policy applies. |
| **Authenticated workflows on the user's accounts** (log in, fill forms, upload, submit) | **The user's own client device**, via a client-side browser worker (Phase 1 principle: harness processes and native accounts belong to the client, `SERVER_CLIENT_OWNERSHIP.md:7,34,71`) | <ul><li>The user sees and completes the login themselves, with MFA, in a visible browser.</li><li>Cookies never reach the server.</li><li>No remote-desktop streaming is needed.</li></ul> |
| Authenticated workflows on the server (option for later) | Server, with a persistent per-user profile under `users/<uuid>/browser/<profile>/`, ACL'd to the user's account | Needs a secure way for a remote user to complete login, such as a streamed headed browser. **Deferred:** complex, and a new credential surface on the server. |

**Consequence for P4.** Authenticated automation depends on the client worker, which runs only on the user's Windows
device. P4 authenticated work is therefore **PC-blocked**. The public-browsing part is cloud-testable on Linux with
Playwright Chromium.

## 4. Browser safety controls

### Isolation

- One context per (user, task) for public browsing.
- One persistent profile per (user, named profile) on the client for authenticated work.
- Contexts are never shared across users.
- Downloads go to the user's quarantine through the StorageBroker.

### Egress

- Server-side browsers send all traffic through a local filtering proxy that applies the SafeFetcher IP and redirect
  rules on every request, including subresources and WebSockets.
- Playwright `route()` interception is a second layer.
- Blocked: `file://`, `chrome://`, `data:` navigation, and private ranges including tailnet `100.64/10`.

### Uploads

- Only files the StorageBroker grants for this task, copied into a per-task upload directory.
- The browser never sees user roots.

### Consequential actions

Submit, post, message, purchase, delete and upload count as consequential. Each one follows this sequence:

1. **Plan.** The agent proposes an action record:
   - origin, URL and the target element's accessible name;
   - the field → value map;
   - a list of files;
   - a hash of the visible form region.
2. **Approve.** The A2UI approval card shows the record. Approval is single-use and bound to its digest, using the
   existing approval store.
3. **Execute.** Immediately before the click, URI recomputes the record on the live page. If the origin, field values
   or form hash differ, URI **aborts** and asks again.
4. **Verify.** Capture the post-action page state as evidence: URL, status text, screenshot hash.

### Credentials

- URI never types stored passwords. The user types them in the visible client browser.
- An OS password manager inside the user's own browser profile is allowed.
- URI never reads cookies or tokens out of a profile.

### Prompt injection

- Page text is untrusted data (`M1_WEB_INTELLIGENCE_ARCHITECTURE.md` §5).
- Navigation targets come from the user's request, the planned workflow, or the same site.
- A page cannot add steps that skip approval.

### Anti-abuse

- No CAPTCHA solving, no fingerprint spoofing, no stealth plugins, no rate-limit evasion.
- A CAPTCHA or bot wall stops the run and hands control to the user.

## 5. Per-site policy table

The table is maintained in `uri_web` and enforced by SafeFetcher and the browser. Example entries come from
`M1_SOCIAL_PLATFORM_RESEARCH.md`:

| Site class | Automated read | Automated write | Notes |
|---|---|---|---|
| Sites whose terms or robots forbid automation (YouTube watch pages, LinkedIn, Facebook, Instagram, X web) | No: use the official API or `unsupported` | Only an interactive, user-approved action on the user's own account, through the client browser | — |
| Government and public institutional sites | Yes, respecting robots, with a rate limit | Form submissions only through client-side, approved workflows | RSS preferred |
| General web | Yes, with robots, the egress policy and a rate limit | Only on user-approved workflows | — |

## 6. Consolidated M1 threat model

| ID | Threat | Control | Report and phase |
|---|---|---|---|
| T-1 | Unauthenticated access to owner state (R1/R2) | The gateway refuses every non-PUBLIC request without a bearer | Three-user architecture; P1-1 |
| T-2 | Open self-registration | Remote signup blocked; admin creates accounts | P1-1, P1-5 |
| T-3 | A user overwrites the shared Google OAuth client | Admin-only at the gateway | P1-1 |
| T-4 | Cross-user mailbox access (R3) | Interim grant revoke; per-user services fixed | P1-1, P1-5 |
| T-5 | Credentials at rest (plaintext Google tokens; default Fernet secret) | Secret guard; token encryption | P1-2, P1-5 |
| T-6 | A same-host proxy makes callers look like loopback | Gateway blocks; per-principal limits | P1-1 |
| T-7 | A harness, app or browser reads another user's data | Per-user Windows accounts + ACLs; broker copy-in/out | P1-6, P2-6 |
| T-8 | Resource exhaustion | Job memory, CPU and process limits; admission pools; per-user budgets | P1-6, P5-2 |
| **T-9** | **SSRF** to loopback, LAN or tailnet (SSRF-1, RUN) | SafeFetcher everywhere; interim grant revoke | P1-5, P3-1 |
| T-10 | Prompt injection from web or email content | Untrusted-data typing; no model-supplied targets; approval for consequences | P3, P4 |
| T-11 | Malicious downloads | Quarantine, type sniffing, size and zip limits, never execute | P3-4 |
| T-12 | Browser session theft or cross-use | Client-side authenticated profiles; per-task server contexts | P4 |
| T-13 | Unapproved posting, messaging, submitting or deleting | Digest-bound approval plus a live-page re-check | P4-3 |
| T-14 | Brain endpoint without a key (OI-SEC-1), reached by local processes or apps | Apps and browsers run as low-privilege accounts. A firewall rule can restrict loopback by program (unverified). SafeFetcher blocks loopback. | P1-6, P5 |
| T-15 | Subscription-terms breach | `M1_HARNESS_ACCESS_AND_LICENSING.md` §4 | P1-6 |
| T-16 | Missing audit trail | Per-user hash-chained AccessEvent (storage); harness and app run ledgers; gateway content-free log | P1-1, P2-1, P5 |
| T-17 | Admin over-reach through URI | Admin routes exclude private content; physical OS access disclosed | Three-user architecture §5 |
| T-18 | A plugin reads another user's credentials or files, or calls undeclared hosts | Per-(user, connector) process; credential per call; api_hosts allow-list; broker-only files | `M1_PLUGIN_PLATFORM_ARCHITECTURE.md` §5; PL-1 |
| T-19 | Client or session spoofing; unregistered or lost devices | Client registry with proof; session ⊂ client ⊂ user check | `M1_USER_CLIENT_IDENTITY_MODEL.md`; ID-3 |
| T-20 | Consequential action executes under the wrong or no identity after approval (DEF-H1) | `principal_user_id` binding + live re-injection | ID-5 |
