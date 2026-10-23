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

## 6. Corrections (2026-10-23; the rows above are kept as first written)

| Row | Correction | Evidence |
|---|---|---|
| E5 / T7 | **Wrong: "frozen only".** In the working system, external-harness turns arrive as worker commands `turn_start` / `turn_intent` whose `reasoning.kind` is `client_external_harness`, and pass through the non-frozen `scripts/run_uri_integrated_worker.py` before the frozen supervised path (`turns.handle`). M95 now gates them there (`harness_private`, OD-1a): credentials refuse the turn, identifiers and contact details are removed, and the sanitized text is what the proposal, the approval card and the vendor CLI carry. `turn_runner.py:229` is the frozen unsupervised worker path, not used by the working system. `orchestrator.begin_harness` has no live caller. | R `run_uri_integrated_worker.py` (dispatch to `turns.handle`), `uri_supervisor_bridge/worker_service.py:40-41,105`, `authority.py:120`; investigation report 2026-10-23 |
| S1 / T6 | **Overstated: D10 does not lose data in the working system.** The paired/integrated server never builds `ProviderKeyStore` or `ExternalCredentialStore`: only the legacy `uri_core/app/server.py` does, and the client runtime uses its own DPAPI key (`client_runtime/persistence.py:92-100`). The per-start random secrets are placeholders there. M95's persistent DPAPI secret in `run_uri_integrated_server.py` is hardening for any future use, not a fix of an observed loss. The P0 D10 impact holds for the legacy server only (P0 corrected its record the same day). OD-2 (frozen launchers) is proposed for closing as not needed. | R grep of key-store constructors at `c036a901`; P0 Addendum O update 2 |
| E6, E7, S2, S3 | Reached only by the legacy server, which the `\URIServer` scheduled task still starts at logon (enabled, last run 2026-10-23 08:06 IST; owner decision AP-2, BLOCKED - OWNER PC REQUIRED). Disabling it would make OD-1b, OD-1c, OD-3 and OD-4 moot. | Scheduled task query 2026-10-23 |

### 6.1 Second correction (2026-10-23, after fallback review FB2)

The E5 / T7 correction above was itself wrong in one point: the UI's external-harness turns go to the protected
`scripts/run_uri_supervised_worker.py` (`supervised_runtime.dart`), not to the integrated worker. E5 remains
**unprotected in the working system** until the owner grants a frozen exception for that worker (OD-1a); the
integrated-worker gate is defence in depth only. See plan PC-10.

### 6.2 Scope of deterministic protection (2026-10-23)

| In scope | Out of scope (stated limit) |
|---|---|
| Accidental disclosure of standard formats and their common variants; obfuscation by invisible or control characters, encodings (four levels), Unicode look-alikes and arbitrary separators (canonical egress plus LONG_NUMBER) | A party that controls the outgoing text and encodes a value on purpose (digits as words, a private cipher, steganography). The control for that is limiting what such a party can see, not more patterns |

### 6.3 Protection as implemented after owner decision LDEC-005 (2026-10-23; supersedes the scope table in 6.2)

Section 6.2 overstated what was protected (fallback review FB3 R1-07). The owner then decided "refuse on doubt"
(LDEC-005). For every non-local destination the gateway now:

| Input | Outcome | Proof (tests/privacy) |
|---|---|---|
| Standard forms of cards, Aadhaar, PAN, SSN, IBAN, accounts, phones (incl. spaced 3-3-4, landlines), e-mail (incl. internationalised), labelled credentials (incl. `pw:`, spaced codes) | redacted / pseudonymized; credentials refused | `test_classify.py`, `test_ldec005.py::test_fb3_r1_04*` |
| Identifier-shaped digit runs (4-4-4-x, 4-6-4/5) and Luhn/Verhoeff-valid runs with standard separators | redacted | `test_ldec005.py::test_fb3_reported_forms`, separator sweep |
| Invisible/control/private-use/unassigned characters or combining marks among ASCII letters or digits | refused (LOG: fully redacted) | `test_c3_repairs.py` category sweep, `test_ldec005.py` |
| Punctuation look-alikes | sent as ASCII, then checked as such | `test_ldec005.py` look-alike sweep (every code point by Unicode name) |
| Digits joined by non-standard separators or letters (9+ digits) | refused | `test_ldec005.py` separator sweep (all ASCII punctuation, doubled, tripled, spaced, letters, Unicode dashes) |
| A sensitive value visible only after percent/HTML decoding; encoding deeper than four levels | refused | `test_ldec005.py`, `test_fb1_repairs.py` |

**Stated residuals (not protected):** a value written in words or a private cipher; a value deliberately split by
five or more letters, or hidden inside a 32+ character hex token; credential labels in languages other than English;
non-standard national formats not listed above. **A party that controls the outgoing text includes the local Brain
when injected web or document content steers the queries it composes.** The control for that class - limiting what
sensitive context such a party can see before it composes egress - is **not implemented**; it is recorded as owner
decision OD-6 (follow-up), not claimed.
