# URI Web Intelligence (W1) and URI Assist (A0, A1): plan and acceptance criteria

Date: 2026-10-10. Author: Claude (implementation lead). Independent auditor of record: Codex (not available in this
session, see §6). This document was written before implementation and governs W1 and A0. A1 is design only.

## 1. Baseline (verified, not taken from the brief)

| Item | Value | How verified |
|---|---|---|
| Canonical branch | `integration/git-sync-20261008` | `INTEGRATION_RECEIPT.md` §1; `git branch -r` |
| Canonical tip | `ffdf534386a3d40cf9e1646ef1080bee28dd3aa9` (= `integration/final-qualification-20261010`) | fetched 2026-10-10 17:05Z; both refs resolve to it. Two later `research/*` branches are research, not canonical |
| Session branch | `ccr-cab5ed06-9hwyc4` was at `610c8f8` (M38, an older line); it was reset to `ffdf534` before any work | `git merge-base` |
| Frozen boundary | `scripts/ws_frozen_check.py` PROTECTED prefixes: `uri_core/`, `uri_supervisor/`, `uri_supervisor_bridge/`, `uri_harness_adapters/`, `model_lab/integration/`, five `scripts/run_*`/`c1_bootstrap.py`, five `uri_ui` Dart files, `.gitignore` | read the script |
| Brain | Runtime v1 FROZEN: Qwen**3.6**-35B-A3B UD-IQ3_S + `mmproj-F16` on stock llama.cpp b11425 (Vulkan), `127.0.0.1:18470`, `-np 1` (one slot) | `model_lab/integration/local_brain.json:9-34`, `runtime_v1.py:76-87` |

The brief says "Qwen3.5". The deployed model is Qwen3.6-35B-A3B. This plan uses the verified identity.

## 2. Findings that shape the plan

1. **All Core capability registration is frozen.** `uri_workspace/capabilities_registry.json` (Phase 1 checkpoint),
   `uri_core/capabilities/registry.py`, `tool_schema.py`, `orchestrator.py`, `fetch_url.py`, `web_search.py`. A new
   capability cannot become a Brain tool without an owner decision (the M1 research calls it D-2). W1 and A0 are
   therefore built as **new, non-frozen packages** (`uri_web/`, `uri_assist/`) that import nothing they would need to
   change, following the precedent of `uri_operational_intelligence/`, `uri_scheduler/`, `uri_a2ui/`.
2. **SSRF-1 is real on canonical.** `uri_core/tools/fetch_url.py:125` calls `requests.get` with default redirects and no
   address check. It is frozen, so W1 does not repair it. W1 never calls it; W1 has its own SafeFetcher. The repair of
   `fetch_url` stays an owner decision (P1-5 T9).
3. **Vision is qualified at the model level but not wired into the application.** Freeze record: V suite 5/5, 1.6-2.0 s
   per 768 px image; the projector is already resident. No application code sends an image
   (`core_provider.py:45` sends strings only). A0 adds an on-demand request builder that reuses the resident Brain; it
   loads no second model.
4. **One inference slot and almost no VRAM headroom.** Staging: AT_RISK, margin −57 to +72 MB; a 700 MiB window
   degrades the Brain. Assist therefore must add no GPU-resident component, must never stream screenshots, and must
   yield the single slot to the user's own turn.
5. **The UI talks to the integrated worker over framed stdio** (`scripts/run_uri_integrated_worker.py`,
   `worker_bridge.py`), not HTTP. New commands reach the UI by a small additive dispatch in that worker. The worker is
   not frozen, but it is pinned in the materialized runtime and in the client manifest, so live activation needs the
   PC (materialize + provision). Cloud evidence covers the Python bridge directly.
6. **The A2UI catalog refuses URLs anywhere** (`uri_a2ui/validate.py:150`). Research results are rendered as A2UI with
   citations shown as host + path text, never as links. No catalog change.
7. **No browser extension, UI Automation or screen capture exists in URI.** A0 defines and tests the perception
   contracts with synthetic inputs; real adapters on Windows are NOT VERIFIED until the PC.
8. **Codex and the Flutter SDK are not installed in this container.** See §6.

## 3. Milestones and boundaries

| Milestone | Owns these paths (disjoint) | Delivers |
|---|---|---|
| **W1 Web Intelligence** | `uri_web/**`, `tests/web/**`, `docs/assist/W1_*` | read-only Search → Retrieve → Extract → Evaluate → Synthesize → Cite; SafeFetcher; feeds; read-only Mastodon/Bluesky; A2UI result surface; worker commands `web_research*` |
| **A0 Assist foundation** | `uri_assist/**`, `tests/assist/**`, `uri_ui/lib/living/assist/**`, the Assist hook lines in `presentation_controller.dart`, `living_shell.dart`, `companion_mode_view.dart`, `uri_ui/test/living/assist_*`, `docs/assist/A0_*` | third entry *Assist*; scope selection and revocation; 5 separated permissions; perception contracts (DOM, UIA, screenshot) with redaction and freshness; on-demand Brain vision request; worker commands `assist_*` |
| Shared hook | `scripts/run_uri_integrated_worker.py` (dispatch lines only) | routes `web_*` and `assist_*` commands; lands with A0 |
| **A1 Guided learning and Smart Fill** | design only: `docs/assist/A1_*` | no code (gate in §5) |

The session may push only to `ccr-cab5ed06-9hwyc4`. The milestone isolation is kept as disjoint path sets and
separate commit ranges on that branch; nothing is merged into the canonical branch by this session (§6).

## 4. Acceptance criteria (defined before implementation)

### W1

| ID | Criterion | Evidence required |
|---|---|---|
| W1-AC1 | SafeFetcher refuses loopback, RFC1918, CGNAT/tailnet 100.64/10, link-local, metadata 169.254.169.254, multicast, reserved, 0.0.0.0, IPv6 loopback/ULA/link-local, IPv4-mapped, NAT64 and 6to4 forms embedding a private v4, Teredo; non-http(s) schemes; userinfo in URLs; ports outside the allow-list | adversarial unit corpus |
| W1-AC2 | Every redirect hop is re-validated (max 5); a redirect to a private address is refused at the hop | unit |
| W1-AC3 | DNS is resolved once per hop and the connection is pinned to the validated address (rebinding: a second, private answer is never used) | unit on the transport |
| W1-AC4 | Timeouts (connect, total), a byte cap enforced while streaming, a content-type allow-list; no cookies, no credentials, fixed User-Agent | unit |
| W1-AC5 | Every retrieval yields a SourceRecord: requested/final URL, redirect chain, retrieved_at, status, content type, bytes, SHA-256, extraction method, analysed scope, trust = UNTRUSTED | unit |
| W1-AC6 | HTML extraction: title, canonical, published/modified time (meta, JSON-LD, `<time>`), language, main text; script/style/nav/hidden content dropped | fixtures |
| W1-AC7 | Feeds: RSS 2.0 and Atom parsed; DOCTYPE/ENTITY refused; feed discovery from HTML | fixtures |
| W1-AC8 | Search provider abstraction with Tavily (reusing the existing key convention), Brave and SearXNG; an unconfigured or failing provider returns an explicit UNAVAILABLE/FAILED status, never empty success; keys never appear in records or errors | unit with fake HTTP |
| W1-AC9 | Duplicate handling: normalized URL and content-hash duplicates collapse; near-duplicates are marked | unit |
| W1-AC10 | Synthesis is citation-backed: every sentence carries ≥1 citation to a retrieved source; the verifier drops sentences whose citation index is invalid, whose numbers do not occur in the cited source, or whose wording has too little support | unit, including a fabricated-citation case |
| W1-AC11 | Conflicting sources are identified (same statement, different number/date) and shown with both citations | unit |
| W1-AC12 | Prompt-injection resistance: source text is wrapped as untrusted data, instruction-like text is flagged, a source can never change the query, the URL set, the provider or the budget, and the Brain prompt places sources only inside the data block | adversarial fixtures |
| W1-AC13 | Bounded background research: page/byte/time budget, progress events, cooperative cancellation, terminal status from a fixed vocabulary; no screen capture involved | unit |
| W1-AC14 | Read-only social: Mastodon public API and Bluesky public AppView through SafeFetcher; unavailable is explicit | unit with fake HTTP |
| W1-AC15 | Result renders through the existing A2UI catalog (validated by `uri_a2ui.Surface`), placement `workspace`, no URLs in the surface, no new action | unit |
| W1-AC16 | No frozen path changed; no new third-party dependency; existing gates unchanged | `ws_frozen_check` protected part, gate run before/after |

**Link-detection scope for W1-AC12/AC15 (owner decisions D13 and D15, 2026-10-11).** Retrieved text is checked
with an allow-list of characters (D15): a token holding a character outside the listed scripts and ordinary
punctuation, a letter named as a dot, colon or separator, or letters of two script families is treated as a link (the
sentence is never shown or used as support; the token is masked). Any two words joined by a dot-like mark, with or
without spaces, brackets or dashes around it, are a link (D13). **D16 (owner, 2026-10-11): the separator does not matter.** A name, then anything at all, then a real top-level
domain from the complete list (`uri_web/tld_list.py`, the Public Suffix List's ICANN section, 1,441 endings) is a
link; letters spelt out with spaces are joined first ('c o m', 'c om'). When only ordinary prose lies between the two
words (spaces, everyday punctuation, digits and numbers, quotes, dashes, breadcrumbs), only the core generic domains
that are not English words (com, org, gov, edu, mil, biz, io, xyz) count, also after a plain space ('portal com'). After R11-01 (coordinator repair): the gap has no length limit; words of another script and single letters may stand between the two words when they hold at most two distinct letters, a repeated letter counting once ('portal ٠ ٠ ٠ ٠ ٠ ٠ com', 'portal 丶 丶 丶 shop', 'portal ʘ com', 'portal o com'); an ending split in two ('co m', 'sh op') or spelt with punctuation ('c-o-m', 'c.o.m', core domains only) is joined; an 'xn--' label is a domain by itself. After R12-01: the name may be in any listed script ('пример com', 'refunds-portal ~ рф'); only separator words (D17) count as part of the separator, and native sentence punctuation (danda, Tibetan shad, Arabic and CJK commas) counts as ordinary prose, so 'Tokyo (東京) in Japan.' stays readable. **D17 (owner, 2026-10-11, after R13-01):** a short word of another script (at most two distinct letters: '丶丿', 'ㆍᆢ') between the name and the ending is a separator unless it stands alone in brackets as a gloss; so is a word made only of odd Latin letters ('ʘʘ'). Recorded residual (owner-accepted): a bracketed separator ('portal (丶丿) shop'). Precision cost: 'Tokyo 東京 is big' (unbracketed) is masked; 'the org chart' and similar uses of a core domain as a word are masked. **Not owner-accepted, disclosed for review:** a split ending whose first piece is a common two-letter English word ('to day', 'be st') is not joined, to keep ordinary prose readable. **Out of scope, accepted by the owner as
residual risk:** a non-core domain after ordinary prose punctuation ('portal, shop', 'portal_shop'; 'portal. Cash'
where D13 does not apply), words for letters or punctuation ('see oh em', 'portal period com'), top-level domains
created after the list snapshot, and D13's 'x. com'. A finding in that class is not blocking for this milestone.

### A0

| ID | Criterion | Evidence required |
|---|---|---|
| A0-AC1 | Opening Assist starts no observation: initial state OFF, no grant, no adapter call | unit + widget test |
| A0-AC2 | Scope kinds: browser tab, desktop window, entire screen. Entire screen needs a second, explicit confirmation. A grant names exactly one target | unit |
| A0-AC3 | Five permissions are separate grants: OBSERVE, REMEMBER, SUGGEST, INSERT, ACT. None implies another. ACT cannot be granted in A0. INSERT cannot be granted in A0 (A1) | unit |
| A0-AC4 | Revocation is immediate: after revoke, observation, suggestion and every later step is refused, and any observation captured before revoke is stale (grant generation) | unit |
| A0-AC5 | Pause/stop: pause refuses capture without discarding the grant; stop revokes | unit |
| A0-AC6 | Perception: an observation is bound to (grant id, generation, target, captured_at, content hash); older than the freshness bound or from another target is refused; a stale observation can never authorise anything | unit |
| A0-AC7 | Redaction before anything leaves the adapter: password, hidden, OTP, card, token/secret/API-key fields and values matching secret patterns are removed or masked; the redaction is recorded | unit with a synthetic form |
| A0-AC8 | Structured browser perception (DOM/a11y snapshot) yields fields, labels, selection, headings with a size bound; page text is untrusted | fixtures |
| A0-AC9 | On-demand vision: request built for the resident Runtime v1 only (loopback base URL), one image, size-bounded, never automatic; refused without OBSERVE, when stale, or while the Brain slot is busy with a user turn; debounced | unit |
| A0-AC10 | No transfer of captured content to an external provider: the Assist path refuses any non-loopback model endpoint | unit |
| A0-AC11 | UI: third entry *Assist* in the Companion next to Workspace and Dashboard; orb and its appearance unchanged; active-scope indicator and one-tap revoke; Ctrl+4 | Flutter widget tests (if SDK available; else NOT VERIFIED) |
| A0-AC12 | Developer diagnostics: adapter status (AVAILABLE/UNAVAILABLE with reason), permission state, last failure — read-only | unit |
| A0-AC13 | No frozen path changed; existing Flutter and Python gates unchanged | gate run |

## 5. A1 entry gate

A1 implementation may start only when: A0 is independently accepted (Codex); a real browser or UIA adapter has run on
the PC with the redaction tests passing against live pages; INSERT has a digest-bound, single-use or count-bounded
grant design accepted by the owner; and workflow storage has an approved retention and deletion design. None of these
is met in this session, so A1 is design only.

## 6. Independent review and integration in this session

- Codex is not installed or reachable in this container. **No Codex audit was performed.** A Codex review package
  (scope, diff range, questions) is prepared in `docs/assist/CODEX_AUDIT_PACKAGE.md`.
- An independent Claude reviewer (a separate agent with no part in writing the code) reviews the diff as an interim
  check. Its verdict is recorded as such and **does not replace Codex**.
- Without a Codex ACCEPT, no milestone is integrated into the canonical branch. The ledger level is at most TESTED.
