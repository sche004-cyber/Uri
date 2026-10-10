# M1 plugin platform architecture: Web Intelligence and social connectors

**Status:** research and planning only.

**Scope:** this report turns the platform research in `M1_SOCIAL_PLATFORM_RESEARCH.md` and the service in
`M1_WEB_INTELLIGENCE_ARCHITECTURE.md` into a **plugin-driven** design. Platform specifics are not repeated here; this
report owns the *plugin mechanics*.

## 0. Acceptance criteria for this report (set before drafting)

- **PA-1.** Existing URI plugin infrastructure is inventoried from code before anything new is proposed.
- **PA-2.** No platform logic is placed in frozen `uri_core/`. Connectors are independent packages.
- **PA-3.** Public research and authenticated account operations are separate capability classes, with separate
  credentials and approval rules.
- **PA-4.** Credentials, sessions and enablement are per user, and fail closed.
- **PA-5.** Every consequential operation is approval-bound to its exact arguments.
- **PA-6.** Existing SDKs and MCP servers are evaluated before building custom code.
- **PA-7.** Every slice has acceptance tests and a cloud or PC label.

## 1. What URI already has (re-verified at `54ad7be`)

| Existing component | What it gives a plugin platform | Evidence |
|---|---|---|
| **External capability contract** (M33, accepted). A descriptor has `contract_version, id, name, description, category, transport, actions`. Each action has `interface`, `effect_type` (read_only / local_write / external_write), `approval_requirement` (none / user / admin) and `risk`. | The connector manifest format, almost as-is | `uri_core/external/contract.py:68-109, 218-293`; `uri_core/capabilities/base.py:15-32` |
| **Closed transport set**: `in_process`, `cli` (no shell, JSON on stdin, timeout), `http` (loopback only) | Safe connector execution channels | `contract.py:45`; `uri_core/external/adapters/{cli,http,in_process}.py` |
| **Orthogonal lifecycle state**: presence, qualification, configuration, authentication, health, `enabled`, `update_available`. The derived UI label is data (`LABEL_RULES`). `LifecycleController` refuses to skip steps. | Install, enable, configure, authenticate, update and revoke states | `uri_core/external/lifecycle.py:20-98, 103-150` |
| **Per-user lifecycle store**, UUID-validated paths | Per-user enablement | `uri_core/external/store.py:81-98` |
| **Per-user encrypted credential store** (Fernet, its own env secret, atomic writes, never returned in summaries) | Per-user connector credentials | `uri_core/external/credentials.py:1-20, 75-150` |
| **Fail-closed permission binding.** A new external capability is unreachable without the user's explicit enable. It deliberately does not use the full-registry default of `CapabilityGrantsStore`. | Default-deny plugin access | `uri_core/external/permission_binding.py:1-21` |
| **Registry bridge** into the capability registry and dispatch, plus result normalizer and evidence adapter | Brain discovery and execution through the existing gate | `uri_core/external/registry_bridge.py`, `result_normalizer.py`, `evidence_adapter.py` |
| **Natural-language/UI lifecycle seam.** The model may *propose* install, enable or disable, but only against a developer-maintained catalog. It cannot invent ids, packages, URLs or credentials. | Safe "enable the YouTube plugin" from chat or voice | `uri_core/external/lifecycle_intent.py:1-16` |
| **Pinned package lifecycle** (yt_dlp, strip_json_comments, the GitHub package flow from M33.1 B3) | Versioned connector install and update | `uri_core/external/descriptors/`, `packages/`, `runtime_lifecycle.py` |
| Approval gate and approval store | Consequential-action approval | `uri_core/core/approval_gate.py`, `approval_store.py` |
| A2UI action registry and digest | Workspace plugin settings and approval cards | `uri_a2ui/actions.py`, `surface.py` |
| Skills: `/skills` list, enable, disable, delete. These are admin-only and install-wide. | Not per user. Not the model to follow for connectors. | `route_classification.py:58,70-72`; `uri_core/skills/skill_installer.py` |

**Gaps:**
- **HTTP or A2UI routes for the per-user external lifecycle.** None exist; it is reachable only through the `/ask`
  lifecycle-intent seam.
- An **out-of-process connector host for third-party SDKs.** The `http` transport is loopback-only, and `cli` runners
  are developer-authored.
- **A taxonomy of the operations a connector performs** (search, read, monitor and so on). Today actions are free-form
  names.
- An **OAuth connection flow** for non-Google providers. Google uses the installed-app flow at the server PC.
- **Per-user rate-limit and quota accounting** per connector.
- **Scheduler, Storage Broker and A2UI bindings** for connector operations.
- **Known issue:** the approved-action defect DEF-H1 (see `M1_USER_CLIENT_IDENTITY_MODEL.md` §2) affects every
  approval-gated connector action until it is repaired.

## 2. Proposed architecture

```
 Brain / A2UI / Scheduler / Web Intelligence service
        │ capability ids of the form  <connector>.<operation>   (via the existing registry bridge)
        ▼
 Core gate (existing):  grants ∩ mode ∩ external_permission_resolver (fail-closed, per user)
        │  approval gate for operations whose effect_type ≠ read_only or which need approval
        ▼
 ConnectorHost (NEW, non-frozen `uri_connectors/host/`)
   - loads connector manifests from the reviewed catalog only
   - one process per (user, connector), run as that user's low-privilege Windows account (P1-6), Job Object limits
   - injects ONLY that user's credential for that connector, per call, from ExternalCredentialStore
   - egress only through SafeFetcher (allow-list = the connector's declared API hosts)
   - storage only through the StorageBroker (downloads → quarantine; uploads → granted files)
   - per-user, per-connector rate limiter and quota meter (usage meter)
        │ stdio JSON-lines (no listening port)
        ▼
 Connector packages (NEW, one per platform: `uri_connectors/youtube`, `reddit`, `x`, `bluesky`, `rss`, …)
   - thin wrappers over vetted official SDKs or REST APIs; no scraping code paths
```

### 2.1 Operation taxonomy

This is the shared capability registry vocabulary. Each connector action declares one `operation` from a closed set.
The operation fixes the minimum safety class; the descriptor may tighten it but never loosen it.

| Operation | Class | Minimum `effect_type` / approval | Typical use |
|---|---|---|---|
| `search` | Public research | read_only / none | Videos, posts, subreddits |
| `read` | Public research | read_only / none | A post, a video's metadata, a thread |
| `extract` | Public research | read_only / none | Captions the user owns, structured fields |
| `analyze` | Public research | read_only / none, runs in the Brain on SourceRecords | Summaries, comparisons |
| `download` | Public research or account | local_write / **user approval** if outside the quarantine; destination via the StorageBroker | User's data export, own captions |
| `monitor` | Public research | read_only / none at run time. **Job activation needs the owner's `proposal_sha256` confirmation** (scheduler). | `web_watch.v1` sources |
| `draft` | Account | local_write / none (stays inside URI) | Prepare a post or reply |
| `publish` | Account | external_write / **user approval, digest-bound** | Post, comment, upload |
| `message` | Account | external_write / **user approval, digest-bound** | Direct messages |
| `delete` | Account | external_write / **user approval** + confirm | Remove own post |

**Public research vs account operations (PA-3):**
- A connector exposes two **separately enabled capability groups**: `<id>.public.*` and `<id>.account.*`.
- Public operations use an owner-held app key (for example the YouTube Data API key) metered per user, or no key.
- Account operations use **only the requesting user's own OAuth token**.
- Enabling public research never enables account access.

### 2.2 Discovery

- **Catalog.** Connectors become known to a user's URI only from the reviewed catalog. The extension of
  `lifecycle_intent`'s catalog is admin-maintained.
- **User state.** Per-user discovery is `GET /plugins`. It returns each catalog entry with the user's own
  `LifecycleState` and derived label (`not_installed`, `needs_authentication`, `ready`, …). The Brain sees only
  connectors whose groups the user has enabled, through the existing registry bridge.
- **Capability ids** are namespaced: `youtube.public.search`, `reddit.public.read`, `x.account.publish`.

### 2.3 Connector manifest

The manifest is the existing descriptor, extended:

```json
{ "contract_version": "1.1", "id": "connector.youtube", "category": "social",
  "transport": "stdio", "package": {"version": "0.1.0", "sha256": "<hex>", "sdk": "google-api-python-client==<pin>"},
  "api_hosts": ["www.googleapis.com", "youtube.googleapis.com"],
  "auth": {"public": {"kind": "app_api_key", "owner_held": true},
           "account": {"kind": "oauth2", "provider": "google", "scopes": ["https://www.googleapis.com/auth/youtube.readonly"]}},
  "quota": {"unit": "youtube_units", "per_user_daily": 3000, "global_daily": 10000},
  "terms": {"automated_access": "official_api_only", "reviewed_on": "YYYY-MM-DD"},
  "actions": {"public.search": {"operation": "search", "effect_type": "read_only", "approval_requirement": "none", "risk": "low", "interface": {}},
              "account.list_my_videos": {"operation": "read", "effect_type": "read_only", "approval_requirement": "none", "risk": "low", "interface": {}}} }
```

`transport: "stdio"` is new. It needs a contract change, `contract_version` 1.1, in frozen `uri_core/external/`. The
alternative is to keep `cli` and have the host wrap it (D-12).

## 3. Multi-user authentication and credential isolation

| Rule | Mechanism |
|---|---|
| Each user connects their own accounts | A per-user OAuth flow per provider. The callback is bound to the initiating user's session and a single-use `state` nonce. The token is stored in `ExternalCredentialStore[user]` and is never shown again. |
| Owner-held public API keys are allowed only for `public.*` | Held server-side, metered per user, and **never** used for `account.*` operations |
| Remote OAuth | Proposed: a gateway-hosted redirect endpoint on the tailnet name, which **replaces** the loopback-only installed-app flow for new connectors. Provider redirect-URI rules (HTTPS, registered host) must be checked per provider. **Unverified.** |
| A connector process sees only one user | One process per (user, connector), under that user's OS account. The credential is passed per call over stdin and is never written into the connector's working directory. |
| Revocation | User revoke means: delete the credential, call the provider's revoke endpoint where one exists, set the lifecycle to `unauthenticated`, kill the running process, and cancel any monitor jobs that use the account group |
| No cross-user reuse | The credential lookup key is `(user_id, connector_id, group)`. An absent key fails closed, with no owner fallback. This is tested in PL-T4. |
| Secret strength | `URI_EXTERNAL_CREDENTIAL_SECRET` must not be the hard-coded default (`scripts/run_uri_server.py:48`). This is enforced by P1-2. |

## 4. Lifecycle, updates and revocation

| Step | Existing state reused | Actor |
|---|---|---|
| Add to catalog (review, pin, hash) | Descriptor review, `qualification` | Owner and admin, with an independent review of the connector code |
| Install on the server | `presence = present` (shared binary, pinned) | Owner and admin |
| Enable per user, separately for public and account groups | `enabled` (per user) | The user, via the A2UI Workspace "Plugins" surface or chat lifecycle intent |
| Configure | `configuration` (per user: channels, subreddits, quotas) | The user |
| Authenticate (account group) | `authentication` | The user, through the provider's own OAuth |
| Health | `health` (provider reachability, quota exhausted) | Host |
| Update | `update_available` → the owner installs the new pinned version side by side → per-user state migration → rollback by pointer | Owner, then each user sees "updated" |
| Disable or revoke | `enabled = False` plus credential deletion | The user, or the admin (admin can disable a connector globally, but cannot read user tokens) |

**Workspace UI.** The A2UI surface `plugins.settings` lists connectors with their lifecycle labels, per-group toggles,
"Connect account", "Revoke" and quota usage. It needs a List row component (`catalog/v2`), which is shared with the
storage design.

## 5. Security boundaries and approval integration

1. **No platform code in Core.** Connectors are separate packages run by the host (PA-2).
2. **Effect classes are enforced by the gate.** `external_write` operations always pass through the approval gate.
   - The approval card shows connector, account, operation and exact payload (text, media file hash, recipients).
   - The digest covers all of these.
   - A changed byte requires re-approval.
   - **Prerequisite:** DEF-H1 must be repaired, or approvals for logged-in users never execute.
3. **Files.** Connector downloads go only to the StorageBroker quarantine. Uploads use only broker-granted files copied
   to a per-call directory. A connector cannot name paths.
4. **Network.** SafeFetcher with the connector's `api_hosts` allow-list. No other egress.
5. **Prompt injection.** Connector results are SourceRecords marked untrusted. They cannot trigger `publish` or
   `message` without a user-approved plan.
6. **Rate limits and terms.** The host enforces the per-user and global quotas declared in the manifest, the provider's
   documented limits, and the terms flag. A connector marked `official_api_only` has no browser or scrape path.
7. **Audit.** Every call records `(user, client, session, connector, operation, approval_id, quota cost)`, with no
   content.

## 6. Integration points

| System | Integration |
|---|---|
| Brain | Connector actions appear as ordinary capabilities through the registry bridge. Results are SourceRecords. Analysis runs through the fair queue. |
| A2UI | `plugins.settings`, connect/revoke actions, approval cards (authority `plugins`) |
| Scheduler | `web_watch.v1` sources may reference `<connector>.public.search` or `.read`, but only connectors the job owner has enabled. Validation happens at job proposal and **re-validation at every dispatch**, the same discipline as the scheduler's authority table. |
| Storage Access Manager | Downloads and exports through broker verbs. Default output is the user's workspace. |
| Web Intelligence | `uri_web` treats connectors as source providers alongside SafeFetcher and the search providers |

## 7. Existing open-source connectors, SDKs and MCP servers

| Platform | Candidate | License | Assessment |
|---|---|---|---|
| YouTube | `google-api-python-client` (official) | Apache-2.0 (from memory; verify) | Use it. The Google libraries are already imported by URI (D-REQ-1). |
| X | **XDK**, the official Python SDK, generated from X's OpenAPI spec (EXT-S: docs.x.com) | MIT (EXT-S) | Prefer it over Tweepy |
| Reddit | PRAW | BSD-2 (from memory; verify) | Use it after API approval |
| Bluesky | `atproto` Python SDK | Unverified (from memory: Apache-2.0 or MIT) | Use it |
| Mastodon | Mastodon.py | MIT (from memory; verify) | Use it |
| Facebook / Instagram | Meta Graph API over REST; `facebook-business` SDK | Verify | Own-account only, after App Review |
| LinkedIn | REST, no official Python SDK found | — | Own-account posting only, after approval |
| RSS/Atom | `feedparser` | BSD-2 (from memory; verify) | Use it; the P3 monitoring default |
| **Community MCP servers** for these platforms | Various | Various | **Not adopted as runtime plugins.** The MCP registry was reported unvetted, with no signing or pinning. Tool descriptions can carry injected instructions. MCP servers usually take credentials from env vars, which conflicts with per-call per-user injection. Use only as **reference code** for wrapping official APIs. A future "MCP transport" for connectors needs its own qualification (pinning, signature, tool-set freeze at connect time, as the M33 contract §8 already anticipates). |

License claims marked "from memory" must be checked against each project's LICENSE before adoption.

## 8. Platform feasibility (summary)

Full detail is in `M1_SOCIAL_PLATFORM_RESEARCH.md`.

| Platform | `public.*` | `account.*` | First slice |
|---|---|---|---|
| RSS/Atom | Yes | — | PL-2 |
| YouTube | search and read metadata (quota) | read own channel and captions (OAuth) | PL-3 |
| Bluesky / Mastodon | Read and search | Post with approval | P6-1 |
| Reddit | Only after API approval | Only after approval | P3-6 |
| X | Paid per read | Post with approval (paid) | P6-2 |
| Facebook / Instagram | Not feasible at household scale (App Review, business verification) | Own pages or professional account after review | P6-3 |
| LinkedIn | Not feasible (partner-only) | Own-account posting after approval | P6-3 |

**REA** is not a dependency of any connector (`M1_REA_EVALUATION.md`). It may be used, optionally and offline, by a
developer to understand undocumented behaviour of a site the owner is licensed to use. It is never used to build a
connector around an official API restriction.

## 9. Minimal slices and acceptance tests

These IDs are registered in `M1_IMPLEMENTATION_SLICES.md`.

| ID | Slice | Acceptance tests | Where |
|---|---|---|---|
| PL-1 | ConnectorHost + operation taxonomy + manifest 1.1 validation | <ul><li>**PL-T1:** a manifest whose operation class is weaker than the taxonomy minimum is rejected.</li><li>**PL-T2:** an undeclared host is refused by egress.</li><li>**PL-T3:** a connector cannot read the user's storage roots; only broker calls succeed.</li><li>**PL-T4:** user B's call never receives user A's credential, including when B has none (fail closed).</li><li>**PL-T5:** quota exhaustion is per user and does not block other users until the global cap.</li></ul> | Cloud (fake connector) |
| PL-2 | RSS connector (public only) + `web_watch.v1` source | <ul><li>Dedup by guid and hash.</li><li>A monitor job can reference only connectors enabled by its owner.</li><li>Disabling the connector pauses the job at its next dispatch.</li></ul> | Cloud |
| PL-3 | YouTube connector: `public.search`/`read` via an owner key; `account.*` read-only via the user's OAuth | <ul><li>Every result's `analysed_scope` is labelled.</li><li>No media download.</li><li>Per-user unit budget.</li><li>Revoke deletes the token and calls Google's revoke endpoint (fake).</li></ul> | Cloud (fake API), PC/live key for E2E |
| PL-4 | Per-user OAuth connect/revoke flow through the gateway | <ul><li>A `state` nonce bound to the session.</li><li>A replayed or cross-user callback is refused.</li><li>The token is never echoed.</li><li>Revoke is idempotent.</li></ul> | Cloud (fake provider), live provider on PC |
| PL-5 | A2UI `plugins.settings` + lifecycle routes | <ul><li>Per-user lifecycle state.</li><li>Admin global disable without token access.</li><li>Chat lifecycle intent still resolves only catalog ids.</li></ul> | Cloud (Python), PC (Flutter) |
| PL-6 | Approval-bound `publish`/`message`, first on Bluesky | <ul><li>A digest covering account, operation and payload.</li><li>A changed payload is refused.</li><li>Execution keeps the user principal. **Blocked by DEF-H1 repair.**</li></ul> | Cloud (fake), live on PC |

**Frozen-touch:** PL-1 (`contract_version` 1.1, if not wrapped), PL-5 (routes in `server.py`) and PL-6 (via the DEF-H1
fix). Everything else is in new non-frozen packages.

## 10. Uncertainty

- The license claims marked "from memory".
- Remote OAuth redirect feasibility per provider.
- Reddit, Meta and LinkedIn approvals.
- Provider quotas and prices (EXT-S).
- Whether `stdio` should become a contract transport or remain host-internal (D-12).
