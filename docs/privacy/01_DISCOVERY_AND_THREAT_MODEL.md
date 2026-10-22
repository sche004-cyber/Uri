# M95 — Discovery and threat model

Milestone: M95 Personal Data Sovereignty & Privacy Intelligence Gateway (Milestone Manager id
`PERSONAL-DATA-SOVEREIGNTY`, roadmap P2; task ledger `TASK-20261022-b00805ff`).
Baseline: canonical `uri-repo/integration/git-sync-20261008` @ `8ff6186b` (verified with `git ls-remote`, 2026-10-22).
Branch `milestone/m95-privacy-gateway-20261022`, worktree `D:/uri-dev/uri-m95-privacy`.

Evidence classes: **R** = read in source at the cited line on `8ff6186b`; **M** = measured/executed; **I** = inferred.
Discovery used two read-only subagents; every claim this document relies on for a design decision was re-read by the
coordinator (marked R) — subagent claims that were not re-checked are not used as evidence.

## 1. What exists and is reused

| Capability | Where | Reuse in M95 |
|---|---|---|
| Secret/PII text detectors hardened over 16+ review rounds (JWT, bearer, basic, API-key prefixes, long secrets, `key=value` secrets, Luhn cards, Aadhaar shape) | `uri_assist/redact.py:89-121` (R) | imported as the classifier's credential/card/Aadhaar rules (one detector set for Assist and the gateway) |
| Current-user DPAPI via ctypes, no new dependency | `uri_core/core/runtime_identity.py:182` (R) | protects the gateway's key material and the D10 key-store secrets (imported read-only) |
| Fernet (`cryptography>=42`, already required) | `requirements.txt:14`, `provider_keys.py` (R) | encrypts persisted protected mappings |
| Capability authorization: `CapabilityResolver` ∩ modes → `ApprovalGate` (single-use, fingerprint-bound approvals) | `uri_core/core/capability_resolver.py`, `approval_gate.py`, `approval_store.py` (subagent, spot-checked) | unchanged; a disclosure grant never authorizes a capability, it only relaxes sanitization of an action that is already authorized |
| Destination-bound single-use approvals with TTL (cloud spend) | `uri_operational_intelligence/cloud_policy.py:1-25,73-105` (R) | design pattern for disclosure grants (bound, expiring, consumable, revocable) |
| Loopback-only Brain client that ignores proxies | `uri_web/local_brain.py:18-47` (R) | reused for the OI conversation client and the Office Brain client |
| Cloud model activation disabled in the working system | `cloud_policy.py:9-14,130-132` (R) | the gateway's EXTERNAL_MODEL policy is ready for activation, not activation |

No existing mechanism scopes access by **data category, purpose, destination or duration** (R: resolver scopes capability
ids per user; approvals scope one action; cloud_policy scopes provider/model/cost). M95 adds exactly that layer, beneath
the existing capability authority, not beside it.

## 2. Frozen boundary (decides where M95 may change code)

`scripts/ws_frozen_check.py:20-25` (R) protects all of `uri_core/`, `uri_supervisor/`, `uri_supervisor_bridge/`,
`uri_harness_adapters/`, `model_lab/integration/`, five launcher/worker scripts (incl. `run_uri_phase2_server.py`,
`run_uri_isolated_server.py`) and five UI files. Exceptions need exact-blob owner authorization (`APPROVED`, R).
`ws_frozen_check.py` exits 0 on the baseline (M). `tests/phase2a/test_frozen_core.py` already fails 3 tests on the
baseline (M, `D:/uri-dev/m95-evidence/baseline_frozen_core.txt`); it is not the authoritative check.

## 3. Egress map (where data can leave or reach an unauthorized component)

| # | Path | Data | Destination | Existing protection | Frozen? | Evidence |
|---|---|---|---|---|---|---|
| E1 | Web research search query (`uri_web/search.py:_HttpProvider._call`) | user query ≤400 chars | Tavily / Brave / SearXNG | `trust_env=False`, no redirects, length cap; **no content filter** | no | R `search.py:63-67,95-140` |
| E2 | Scheduler creative harness package (`uri_scheduler/engine.py:838` → `gif_task.build_package`) | `params.audience/style`, revision `request` free text | Claude Code CLI (Anthropic) | env allow-list, workspace confinement; **no content filter** | no | R `engine.py:820-842`, `gif_task.py:66-91` |
| E3 | OI conversation Brain client (`scripts/run_uri_integrated_server.py:89`) | full conversation turns | Runtime v1 on 127.0.0.1 | URL is loopback by construction; **httpx `trust_env=True`** — a system proxy without loopback bypass could carry turns off-machine | no | R `brain_client.py:99-106`, `runtime_v1.py:72` |
| E4 | Office Brain (`uri_office/service.py:1182-1185`) | sheet excerpts + correction history | any `--brain-url` | **no loopback check, proxy-trusting client** | no | R |
| E5 | Paired-turn external harness rows (Codex / Claude Code) | user instruction, workspace copies | OpenAI / Anthropic via vendor CLI | env allow-list, flag refusal, budget cap; no content filter | **yes** (`uri_core/client_runtime`, `uri_supervisor_bridge`) | subagent R `turn_runner.py:229`, `bridge.py:253` |
| E6 | Legacy uri_core server cloud Active Brain (`ModelRouter` → OpenAI/Anthropic/Gemini/Groq/OpenRouter) | full prompt incl. memory, profile, history, Gmail evidence | cloud providers | budget/auth; no content filter | **yes** | subagent R `model_router.py:252`, `openai_compatible_provider.py:103` |
| E7 | uri_core Tavily tool (`uri_core/tools/web_search.py:80-107`) | **entire request text** | Tavily | none on content | **yes** | R |
| E8 | Google APIs (Gmail drafts, Drive/Sheets upload) | user-chosen content | Google | OAuth scopes; token.json plaintext at rest | **yes** (uri_core); Office Sheets share not frozen but user-initiated | subagent R |
| E9 | Assist observation | redacted DOM / masked screenshot | loopback Brain | `require_loopback`, redaction, render check | no | R `uri_assist/redact.py`, `local_brain.py` |

Storage and secrets:

| # | Item | Finding | Frozen? | Evidence |
|---|---|---|---|---|
| S1 | D10 | integrated/phase2/isolated launchers set `URI_PROVIDER_KEY_SECRET` and `URI_EXTERNAL_CREDENTIAL_SECRET` to a new random value every start → saved keys/credentials unreadable after restart (users re-enter secrets; I: encourages plaintext workarounds) | integrated: no; phase2/isolated: **yes** | R `run_uri_integrated_server.py:83-84` |
| S2 | Hard-coded provider-key secret default `uri_local_dev_secret_key_v1` | legacy uri_core server encrypts provider keys with a constant from source = obfuscation only | **yes** | R `uri_core/app/server.py:38`, `scripts/run_uri_server.py:47` |
| S3 | Google OAuth `token.json` plaintext per user | at-rest exposure to any same-user process | **yes** | subagent R `google_auth_common.py:19-32` |
| S4 | Content-bearing logs: harness stream-json `.log`, supervisor `stream_event.raw`, conversation history JSON, `friction_log.json` | prompts/model output on disk unencrypted | mostly **yes** | subagent R |
| S5 | Memory/profile/graph stores | plaintext JSON/SQLite under the user's profile; credential-shaped values already refused by `security_guards` | **yes** | subagent R |

No URI login autofill or credential submission exists (R: grep over py/js/dart finds only Flutter `AutofillHints` for
URI's own login form and OS WebView2 notes). M95 keeps it that way.

## 4. Threats, severity and practical exploitability

Severity = impact if it happens; exploitability = what an attacker or accident needs. Scale HIGH/MEDIUM/LOW.

| ID | Threat | Severity | Exploitability | Addressed by M95 |
|---|---|---|---|---|
| T1 | Secrets (keys, passwords, OTPs) typed or pasted into a web-research query are sent to a search provider and its logs | HIGH | MEDIUM (ordinary user mistake; also prompt-injected follow-up queries) | yes — gateway refuses (E1) |
| T2 | Government/financial identifiers and contact details in web queries | MEDIUM | MEDIUM | yes — redacted unless a scoped grant exists (E1) |
| T3 | Personal identifiers in scheduler free text reach Anthropic via Claude Code | MEDIUM | LOW (owner-authored tasks) | yes — redacted / credentials refused (E2) |
| T4 | Local Brain traffic carried off-machine by a system proxy | HIGH | LOW (needs a proxy without loopback bypass) | yes — proxy-free loopback clients (E3, E4) |
| T5 | Office Brain pointed at a non-loopback URL sends sheet data and correction history off-machine | HIGH | LOW (CLI flag) | yes — loopback enforced (E4) |
| T6 | Saved credentials lost every restart (D10) | MEDIUM (availability, pushes users to unsafe workarounds) | HIGH (every start) | yes for the integrated launcher; frozen launchers → owner decision |
| T7 | External harness rows receive raw user instructions | MEDIUM | LOW-MEDIUM (user explicitly selects the external row) | **no — frozen**; gateway API ready, hook needs owner exception (OD-1) |
| T8 | Legacy uri_core cloud routing sends memory/profile/history to cloud providers | HIGH | LOW in the working system (cloud disabled there); HIGH if the legacy server (`\URIServer`, open AP-2) is configured with a cloud Active Brain | **no — frozen** (OD-1, AP-2) |
| T9 | uri_core Tavily tool sends the whole request text | MEDIUM | LOW (needs `TAVILY_API_KEY` in the legacy server) | **no — frozen** (OD-1) |
| T10 | Constant provider-key secret / plaintext OAuth token at rest | MEDIUM | LOW (same-user local access) | **no — frozen** (OD-3, OD-4) |
| T11 | Gateway itself leaks: mapping table, raw values in audit or logs, cross-session restoration, foreign pseudonym resolution | HIGH | — | design + tests (AC-4..AC-8) |
| T12 | Gateway fails open (exception, missing audit, unknown destination) | HIGH | — | fail-closed design + tests (AC-9) |
| T13 | Prompt injection in documents/web content tries to make URI disclose data or resolve references | MEDIUM | MEDIUM | deterministic gateway (no model in the decision path); restoration only by the scope owner to local destinations (AC-6) |

## 5. Dependency model

- Depends on (all present on `8ff6186b`): `uri_assist/redact.py` (detectors), `uri_core/core/runtime_identity.dpapi`,
  `cryptography`, `uri_web/local_brain.loopback_client`, Milestone Manager + Lifecycle V3.1 (registration, review).
- Feeds: MEETING-INTELLIGENCE (P4, waits for this milestone in the Milestone Manager); later uri_core hooks (OD-1).
- Coordinates with: P0 audit thread (D10 is its defect; AP-2 `\URIServer`), post-integration lifecycle/memory thread
  (no shared files expected).
