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

### 6.4 Protection as implemented after owner decision LDEC-006 (2026-10-23; supersedes the table and residuals in 6.3)

Section 6.3 overclaimed four of its rows (fallback review FB4 R1-06). This section is stated from generated sweeps, and
every row names the sweep. Applies to every non-local destination (WEB_SEARCH, EXTERNAL_*, LOG); local destinations
are unchanged.

| Input | Outcome | Measured / proof (tests/privacy) |
|---|---|---|
| Any run of 9+ digits joined by punctuation/whitespace gaps of any length, or by gaps of 1-3 characters with at most 2 letters, other than dates, clock times, ISO-8601 timestamps and IPv4 addresses | redacted (LONG_NUMBER), or the specific category when a specific rule matches | every 2-4-group split of a card and an Aadhaar x 10 separators (8,060 texts, measured) and of an Amex (test), 3,000 mixed-gap texts x 4 destinations: 0 leaks (`test_ldec006.py::test_fb4_r1_01*`, `*_r1_02*`); long punctuation gaps (`test_ldec006.py::test_ldec006_long_punctuation_gaps*`) |
| Digits hidden between exempt tokens ("4539 1488 2026-10-23 0343 6467") | counted; redacted | `test_ldec006_a_card_hidden_among_exempt_tokens_is_still_counted` |
| A value split around another redacted value | refused | `test_fb4_r1_06_value_split_around_another_value_is_refused` |
| Standard and spaced forms of cards, Aadhaar, PAN (also upper case with single spaces), SSN (also label after), IBAN, accounts, phones, e-mail (also internationalised, Indic marks in the local part) | redacted / pseudonymized | `test_classify.py`, `test_ldec005.py`, `test_ldec006.py` |
| Labelled credentials: label before the value, or clear English value-before-label forms such as `huntertwo is my password` and `use huntertwo as the password` (including alphabetic values); bare English password/passcode, API key, secret key, and token labels with alphabetic values (apart from the prose phrases listed below), `password's X`, `pw X`, `pass X` after a user/login word, labels `pass-word`, `pass_word`, `P@ssword`, `passw0rd`; split keys with a known prefix, including separate uppercase-letter and digit groups | refused (LOG: redacted) | `test_fb4_r1_04*`, `test_fb4_r1_05*` (960 keys), `test_fb4_r1_06*`, `test_r6_split_keys.py` (200 generated keys at each of four destinations; Tavily transport capture), `test_r6_review_repairs.py::test_r4_01_*` (20 value-before-label forms across four destinations, LOG and Tavily transport) |
| Invisible/control/private-use/unassigned characters or combining marks among ASCII letters or digits; accents NFKC composes onto a label | refused, or the label is read through its ASCII base | every mark U+0300-036F x every letter of "password" x 2 destinations: 0 leaks (`test_fb4_r1_03*`) |
| Digits joined by non-standard separators (LDEC-005 signal) | refused | `test_ldec005.py` separator sweep |
| Encoded values; encoding deeper than four levels | refused | `test_ldec005.py`, `test_fb1_repairs.py` |
| Final outgoing text (after rewriting and whitespace collapse) | classified and disguise-checked again; refused if anything not allowed appears | `test_fb4_r1_02_final_text_is_rechecked_after_whitespace_collapse` |

**Left unchanged (measured, 500 generated texts per class, WEB_SEARCH):** dates, times, ISO timestamps and IPv4 with
or without port; ids of 8 digits or fewer; prices; years and counts; version numbers - 0 % altered, 0 % refused.
**Altered by decision (LDEC-006):** order ids, number lists, ms timestamps, CSV rows, thousands groupings, ISBNs -
100 % redacted, 0 % refused. Keycap emoji and ordinary accented prose are unchanged.

**Stated residuals (not protected):**
- a value written in words, a private cipher, or any other deliberate encoding;
- digits separated by 4 or more characters when the gap contains letters, or by 3 or more letters, including words between the groups
  ("4111 one 1111 two 1111 three 1111");
- digits written as letter look-alikes (`l` for 1, `O` for 0), where the look-alikes break a run;
- a value written as a sequence of valid dates, clock times or IPv4 addresses (the exempt classes);
- sensitive numbers of 8 digits or fewer with no label or context (short account numbers, PINs without a code word);
- credential labels in languages other than English, and leetspeak beyond the listed spellings;
- common prose/UI words after a bare password label (`policy`, `field`, `manager`, `strong`, `please`) remain readable; a literal password equal to one of those words is ambiguous and is not detected in that bare form;
- unquoted English question words (`what`, `where`, `which`, `when`, `why`, `whose`, `how`) before `is my password` remain readable; a literal password equal to one of those words must be quoted or labelled before the value;
- API keys whose prefix is not in the list when split by separators; keys whose groups are lower-case words;
- combining marks outside the Latin and Indic ranges inside an internationalised e-mail local part;
- non-standard national formats not listed above.

**A party that controls the outgoing text includes the local Brain when injected web or document content steers the
queries it composes.** Limiting what sensitive context such a party can see is **not implemented**; it is owner
decision **OD-7** (follow-up). Section 6.3 called it OD-6, which the plan already used for integration authorization.

### 6.5 Changes after driver run r6 and owner decisions LDEC-007 / LDEC-008 (2026-10-23; amends 6.4)

| Change to 6.4 | Proof (tests/privacy) |
|---|---|
| Digit runs bridge punctuation and whitespace gaps of any length (r6 R2-01); gaps holding letters still break a run after 3 characters | `test_ldec006.py::test_ldec006_long_punctuation_gaps*` |
| Labelled credentials: letter-only values are refused when a separator joins label and value ("password: x", "password is x"), after a key label as one 16+ letter token, and before a possessive label that ends the sentence ("x is my password."; a quoted value always) | `test_r6_review_repairs.py::test_r3_01*`, `test_r4_01*` |
| Split keys after a fixed-length prefix (AKIA/ASIA 16, AIza 35, ghp_/gho_/ghs_/ghu_ 36, glpat- 20) are refused when the groups add up to the body length, with or without digits | `test_pc13.py::test_r5_01*` |
| Text with nothing to rewrite is sent byte-identical (no NFKC change to half-width katakana, Arabic presentation forms, ligatures, NBSP, URL paths); text that needs a rewrite is sent in the egress form and re-checked | `test_pc13.py::test_r5_02*`, `test_c3_repairs.py::test_canonical_is_what_is_sent` |
| Pseudonym tokens carry a keyed, non-reversible scope tag; a token never restores in another scope | `test_pc13.py::test_scope_tag*`, `test_r6_review_repairs.py::test_r3_02*` |

**Residuals added (owner decision LDEC-007):** a bare credential label directly followed by one letter-only word
without a digit or symbol ("password huntertwo", "access token alphabetic") is not detected, because it cannot be told
apart from ordinary searches ("password reset not working"); pinned by
`test_r6_review_repairs.py::test_ldec007_bare_label_with_one_letter_only_word_is_the_stated_residual`. A letter-only
value before a label that does not end the sentence ("x is my password manager") is not detected for the same
reason. **Removed from the residual list:** digits separated by 4 or more punctuation or whitespace characters (now
redacted); split keys with a fixed-length prefix whose groups are lower-case words or hold fewer than two digits.
Every other residual in 6.4 stands, including OD-7.

### 6.6 Changes after fallback review FB5 (2026-10-23; amends 6.4 and 6.5)

| Change | Proof (tests/privacy) |
|---|---|
| Every character with a digit value (decimal digits of any script, dingbat, circled and double-circled digits, Ethiopic numerals and other number forms) reads as its ASCII digit for every rule, including the digit budget | `test_pc14.py::test_fb5_r1_01*` (every digit family x card/Aadhaar x 5 destinations) |
| E-mail with single spaces or a line break around `@`, with `(at)`/`[at]`/`{at}` and `(dot)`/`[dot]`, and with Indic letters and marks in the domain | `test_fb5_r1_03*` |
| PAN with one punctuation separator anywhere (upper case) or between its groups (any case, years excluded); the spaced form is upper case only | `test_fb5_r1_04*`, `test_c5_01*` |
| `pin/otp/cvv number/no./#` before the digits; `pass is X`; Wi-Fi / WPA / network-key labels; PEM private-key blocks (CREDENTIAL, refused) | `test_fb5_r1_05_r1_07*` |
| Invisible format characters (zero-width space, bidi marks, BOM) between non-ASCII letters are dropped without doubt; next to an ASCII letter or any digit they stay a disguise signal | `test_fb5_r1_06*` |
| Text whose matching cost for the reused Assist long-secret rule is pathological (long runs of `/` or `+`) is refused for non-local destinations before matching | `test_fb5_r1_02_pathological*` |

**Residuals added (not protected):** the free digits an exempt token can carry - up to 9 in a clock-time fraction
(`10:00:00.123456789`) and 5 in an IPv4 port; phone numbers of 8 digits or fewer even with a context word ("call 2345
6789"); credential labels outside the listed English set ("creds", letter-spaced labels such as `p a s s w o r d:`);
a lower-case PAN with single spaces (`abcpe 1234 f`) or a PAN whose 4 digits form a year 1900-2099 written lower case
with separators; e-mail addresses written with " at " / " dot " in words; combining marks outside the Latin and Indic
blocks in an e-mail. Every residual of 6.4 and 6.5 stands, including OD-7.

**Stated limit:** a non-local text over the matching-cost bound (for example a 64 KB base64 blob, or 16 KB of
`a/a/...`) is refused, not sent (LOG: fully redacted). At 64 KB the AC-14c margin is thin for scripts with combining marks: the recorded run met it, an earlier run on the same host measured 1.07 s for Hindi (see plan PC-14).

### 6.7 Changes after driver run r8 and fallback review FB6 (2026-10-24; amends 6.5 and 6.6)

| Change | Proof (tests/privacy) |
|---|---|
| Clean text leaves byte-identical also when it is not NFC (decomposed accents), and clean direct WEB_SEARCH text keeps its spacing (repair `1fa3e46e`, replacing 6.5's "already composed" condition) | `test_pc15.py::test_r8_r1_01*`, `test_r8_clean_egress.py` |
| A run over the digit budget that spans a character NFKC expands into letters, digits or more than three characters (U+33C2, U+FDFA, squared CJK units) is refused as a disguise, read on the text as written | `test_pc15.py::test_fb6_r3_01*` (every NFKC-changing code point x card, Aadhaar, SSN, mobile) |

**Stated limit added:** at 64 KB, prose in scripts with combining marks (Hindi, Arabic) takes 0.7-1.1 s per call,
above the AC-14c bound of 1 s in some runs (plan PC-15). Every residual of 6.4-6.6 stands, including OD-7.

### 6.8 Changes after fallback review FB7 (2026-10-24; amends 6.4 row 1 and 6.7 row 2)

| Change | Proof (tests/privacy) |
|---|---|
| The digit budget (6.4 row 1) is measured on the text as written as well as on every folded reading: gaps are counted in code points, and only characters that are letters as written count as letters. A run over the budget in either reading is redacted | `test_pc16.py` (every NFKC-changing code point and every punctuation/symbol code point in protected-shape gaps; random mixed gaps) |
| 6.7 row 2 (refuse a run that spans an expanding compatibility character) is replaced by that rule: such runs are redacted; the original text is rewritten when only its as-written reading shows the run, and a text whose two readings find different things is refused | `test_pc16.py`, `test_pc15.py` |
| Ordinary CJK text with full-width letters, half-width katakana or unit symbols between numbers is not refused; words of letters between numbers break a run | `test_pc16.py::test_fb7_r1_03*` |

**Residual restated:** gaps of three or more letters as written, including a compatibility character that is itself a
letter after two letters ("ab" + U+013F), break a run - the 6.4 letter-gap residual, now counted on the text as
written. Every other residual of 6.4-6.7 stands, including OD-7.
