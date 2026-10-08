# 02 — URI Capability Ownership Matrix

**Checkouts.** "Current" means the `_V1` linked worktree, branch `m35-uri-v1-parallel-architecture`, HEAD `d1feaf7`. "Legacy" means the main worktree `C:\Users\cheta\Development\uri-agent`, branch `master`, HEAD `e8e3b65`.

These are **one git repository**. `_V1` is `master` plus 36 commits, and the merge-base is `e8e3b65`. The legacy tree also carries uncommitted work (38 modified tracked files). The older prototype referenced by `hermes_uri_inventory.json` (`E:\Chetan\Uri Agent\uri_prototype`) is **not accessible** on this machine. Drive `E:` does not exist here. Paths below are relative to the `_V1` worktree unless stated.

**Verdicts:**
- **KEEP:** URI's existing solution stays; no ecosystem replacement is better.
- **ADAPT:** reshape the existing URI mechanism for the harness era.
- **WRAP:** consume an external system behind a URI boundary.
- **REPLACE:** retire URI code in favour of external.
- **BUILD:** genuinely missing everywhere.
- **DEFER:** decide later with evidence.

## A. Relationship, identity, and product layer

| Capability | Current URI | Legacy lesson | Ecosystem | Verdict | Evidence / reason |
|---|---|---|---|---|---|
| Persistent user relationship, identity, accounts, sessions | LIVE: `uri_core/core/user_accounts.py`, `auth_session.py`, `devices.py`, `principal_context.py` | Same code; multi-user isolation tested | Harnesses have profiles, not durable user relationships | **KEEP** | Core of URI identity. Must survive harness replacement (brief principle 7). |
| Companion persona / continuity | `soul.md`, `URI_AI_OPERATING_POLICY.md`; M35 Companion RESERVED_NOT_STARTED (`docs/governance/URI_STATE.yaml`) | — | Hermes `SOUL.md` is harness-owned | **KEEP / BUILD** | Persona must be URI-owned and injected into the harness per run. Hermes `/v1/runs` accepts `instructions` (local source). |
| Product UX (desktop client) | Flutter `uri_ui/`, thin HTTP client (`services/http_uri_client.dart`) | M26 visual failure review; Hybrid UI paused | AG-UI protocol; harness UIs (Hermes TUI/desktop, Goose desktop) | **KEEP UI, ADAPT transport** | Users should never configure the harness UI (principle 6). AG-UI-style event streaming fits "watch URI execute". `/ask/stream` exists but the UI does not use it. |
| Domain packs (URI Office) | Not a concept yet. Office logic is scattered in `uri_core/services/*` and `tools/*`. Modes are filters (`URI_M22_ARCHITECTURE.md` §16) | Institutional drafting rules in `config/institutional_rules.py` | No ecosystem equivalent. Hermes skills and Goose recipes are closest | **BUILD** | Needed so Office assumptions stay out of URI Core. |

## B. Intelligence

| Capability | Current URI | Legacy lesson | Ecosystem | Verdict | Evidence / reason |
|---|---|---|---|---|---|
| Model provider drivers | LIVE: Ollama, OpenAI-compatible, Anthropic (`uri_core/core/model_providers/*`) | Clean and provider-neutral | LiteLLM (supply-chain incident Mar 2026), Lemonade, provider SDKs | **KEEP** | Already neutral. LiteLLM was rejected previously (`docs/plans/M33_3_R_CONTINUOUS_EXECUTION_PLAN.md:50`). Its compromise reinforces minimal dependencies. |
| Model routing / fallback / budgets | LIVE: `model_router.py` (auth errors never fall back), `usage_meter.py`, `usage_ceiling_store.py` | No-silent-substitution invariant (M22.6, M32 D3) | RouteLLM, LiteLLM routers encode none of URI's authority modes | **KEEP** | Repository precedent. |
| Edge path (deterministic → Edge → Capable) | ISOLATED: `uri_core/core/edge/routing_policy.py`, not wired in `/ask`. Qualification evidence in B4, A2.7, M33.3-R | Needle 3 is RESIDENT only for narrow tasks; sub-1B decoders rejected | Nothing equivalent in harnesses. Harnesses send everything to one big model | **KEEP + ADAPT** | This is URI's differentiator: bounded work never needs a heavyweight harness (see `05_TARGET_ARCHITECTURE.md`). Wiring is S13 / INT-* territory, so it is not decided here. |
| Intelligence brokering to harnesses (configure once) | Absent. URI is an OpenAI-compatible **client** only | M24 "Gateways" concept explicitly not built | Harnesses accept custom `base_url` (Hermes, OpenCode, Goose, OpenHands, Agents SDK); Codex needs Responses; Claude and Gemini are closed | **BUILD (thin)** | See `07_INTELLIGENCE_SHARING_ANALYSIS.md`. |
| Local model runtime lifecycle | ISOLATED/accepted: `uri_core/core/edge_lifecycle/*`; lease ownership in `core/edge/lease_ownership.py` | SSRF redirect bug fixed | Ollama, LM Studio, Lemonade manage their own residency | **KEEP / WRAP** | M33.3-R already chose to wrap provider-native TTL and eviction. |

## C. Semantic and context layer

| Capability | Current URI | Legacy lesson | Ecosystem | Verdict | Evidence / reason |
|---|---|---|---|---|---|
| RAR (reference resolution) | RESEARCH/ISOLATED: `uri_v1/turn/rar_deterministic.py` (SHA-pinned). Hybrid at 89.7% but 6/136 unsafe; real grounding 0/84 (`docs/plans/M35_URIV1_A3_...:170-191`) | Prompt-only pronoun resolution fragile | No harness does authoritative reference binding with consequence awareness | **KEEP (research continues)** | Unique. Still EXPERIMENTAL. Its role in the harness era is producing the capsule's authoritative references. |
| ARN (narrowing / clarification) | Production ARN.1 on first NOT_FOUND; uri_v1 ARN experimental; M33.3 clarification (S1/S12) | — | Harness `clarify` tools exist (Hermes `clarify_tool.py`) but are not grounded in URI evidence | **KEEP** | Clarification must remain URI-owned per the canonical interaction loop. |
| Consequence-aware binding | ISOLATED: `uri_core/capabilities/wrong_binding.py` (D1, D5) | — | None | **KEEP** | Required input to harness authority posture. |
| Context construction / budget | LIVE: `query_context.py`, `context_builder.py`, `context_budget.py`, `context_trimmer.py` | Tiering sound; feeds weak | Harnesses compress their own context (Hermes `session.compress`) | **ADAPT** | Output becomes the execution capsule. The harness owns in-run context; URI owns what goes in. |
| Graph / Graphify context | Graph store LIVE but ingestion dormant; Graphify hint index LIVE behind flag | FIND-MEM-001: tested but empty in production | Letta, mem0, Honcho (harness plugins) | **KEEP, DEFER expansion** | Durable knowledge must be URI-owned (principle 7). |
| Durable knowledge / user memory / facts | LIVE: `user_memory.py`, `fact_manager.py`, `experience_store.py` | Passive memory confirm path never triggered live | Harness memories are harness-owned | **KEEP** | Harness learning treatment is a deferred ruling (decision D-C); see `04` R-S1. |

## D. Authority, governance, provenance

| Capability | Current URI | Legacy lesson | Ecosystem | Verdict | Evidence / reason |
|---|---|---|---|---|---|
| Approvals | LIVE: `approval_gate.py`, `approval_store.py` (args SHA-256, single-use, expiry) | Resumption FLAG-OFF (`approval_resumption.py`) | Harness approvals cover their own classification only (Hermes: dangerous commands; ACP: at agent discretion) | **KEEP + ADAPT** | Needs extending to harness approval requests. Per-harness posture per D-B. |
| Grants / capability resolution / modes | LIVE: `capability_resolver.py` | ADMIN never expands grants | Harness toolset configs (Hermes profiles, OpenCode allow/ask/deny, Goose allowlists) | **KEEP; project into harness config** | URI computes the allowed set and the harness adapter enforces it via harness configuration. |
| Effect classification | LIVE: `EffectType` read_only / local_write / external_write (`capabilities/base.py:17-33`) | Native loop auto-runs only read-only | Codex and Claude distinguish commands vs file edits; nobody classifies external_write semantically | **KEEP** | Basis for per-harness posture. |
| Fail-closed external permission | LIVE: `uri_core/external/permission_binding.py` (M33 P1) | Earlier default-allow bug found and fixed | Hermes `pre_tool_call` fails open on hook exception (local source) | **KEEP** | Direct conflict to manage; see `04` R-A1. |
| Provenance / evidence ledger | LIVE: `EvidenceLedger`, `external/evidence_adapter.py`, `result_normalizer.py` (secret redaction), audit trail | — | Harness transcripts and events (not provenance-grade) | **KEEP + ADAPT** | Harness events must be normalised into URI evidence records. |
| Result versioning / redo | ISOLATED: `uri_v1/results/version_ledger.py`, `redo.py` (S11) | — | Hermes session branch; DeepSeek replayable log | **KEEP** | Content-addressed and URI-owned. |
| Observability / traces | ISOLATED: `uri_v1/evaluation/*` (W3C trace, `gen_ai.*` naming, no SDK) | — | OTel GenAI semconv (in development); MCP `traceparent`; Langfuse/Phoenix | **ADAPT** | Propagate the URI trace id into harness runs where supported. |

## E. Execution

| Capability | Current URI | Legacy lesson | Ecosystem | Verdict | Evidence / reason |
|---|---|---|---|---|---|
| Agent loop / multi-step orchestration | LIVE canonical execution (two model calls per turn, `execute_chain` ≤6 steps); `orchestrator.py` 6,121 lines; native tool loop FLAG-OFF | Duplicated decision mechanisms; built-but-unreached features; ~13.6 s two-call latency (`uri-agent` untracked `docs/plans/URI_NEW_ARCHITECTURE_SOURCE_AUDIT.md:37-43`) | Every harness | **REPLACE for agentic multi-step work; KEEP canonical bounded path** | Strongest evidence against rebuilding orchestration in-house. Bounded single-action turns stay URI-native (Edge ladder). |
| Durable long-running execution | Operation store (`external/operation_store.py`), `outcome_unknown`; no general workflow engine (`EXTERNAL_CAPABILITY_CONTRACT.md:161`) | Workflow planner is template/keyword based | Hermes `/v1/runs` durable admission; Codex threads; LangGraph checkpointers; OpenHands persistence | **WRAP** | Harness owns in-run durability. URI owns the operation handle and outcome ledger (ADAPT the operation store). |
| Terminal / code execution | None for the Brain; CLI adapter is fixed-argv only | Unchecked `hermes_forge` was removed as unsafe | Codex Windows sandbox; Hermes backends; OpenHands | **WRAP** | Only inside a qualified harness with a sandbox posture. |
| Browser automation | Absent; explicitly excluded (M33.1 plan :119) | Agent Reach rejected; Firecrawl not built | Playwright MCP (a11y-tree), browser-use, Stagehand, Hermes browser tools | **WRAP** | Use Playwright MCP as a direct capability provider for bounded browser tasks; harness-native browsing for agentic tasks. |
| Computer use (desktop) | Absent | None | Windows-MCP (UIA), UFO², cua-driver via Hermes, Anthropic/OpenAI computer-use tools | **WRAP, qualification-gated** | Reliability on this machine UNMEASURED (experiments E-P4, E-P5). |
| Institutional portals (SAMARTH) | Absent (zero matches in either checkout) | Only local xlsx student lookup (`services/student_record_service.py`) | Browser agents | **DEFER → WRAP** | Portal work depends on qualified browser automation plus credential policy. |
| Web search / fetch | LIVE: Tavily `tools/web_search.py`, `tools/fetch_url.py` | Thin | Many MCP search servers; harness web tools | **KEEP (bounded) / WRAP (agentic)** | Cheap, bounded; no reason to route through a harness. |

## F. Office domain capabilities (URI Office pack)

| Capability | Current URI | Legacy lesson | Ecosystem | Verdict | Evidence / reason |
|---|---|---|---|---|---|
| Gmail read/search/thread/attachments | LIVE, tested (`services/gmail_service.py`, `capabilities/gmail/capability.py`) | Per-user token scoping | M365 MCP (cloud/tenant); Hermes email/Google Workspace skills | **KEEP** | Works; OAuth ownership should stay URI's so credentials do not live in a harness. |
| Gmail draft (approval-gated) / no send | LIVE; send deliberately absent (`gmail_service.py:28-50`) | Compose-without-send is a reusable safety pattern | Harness messaging tools can send | **KEEP as policy** | Any harness must be denied send capability for Gmail unless the user changes policy. |
| Document generation (docx/xlsx/pptx/pdf) | LIVE: `tools/generate_document.py`, `services/office_document_writer.py`, `document_writer_service.py` | Standard libraries | Anthropic document skills (source-available); harness code execution | **KEEP bounded; WRAP complex** | Simple generation stays deterministic. "Make this script work with this spreadsheet" is harness work. |
| PDF→docx conversion / OCR | LIVE, hand-rolled (`services/pdf_layout_converter.py`), legacy tree has uncommitted edits; Tesseract with hardcoded path | Fragile | LibreOffice headless, dedicated converters (UNKNOWN quality) | **REPLACE (DEFER until E-P6)** | Hand-rolled converters are high-maintenance. |
| Institutional drafting | LIVE, tested (`services/institutional_drafting.py`, `config/institutional_rules.py`) | Brain-authored and rule-driven since M17 | None | **KEEP (domain pack)** | Most domain-specific asset; belongs in the URI Office pack. |
| Spreadsheet data work (student records) | LIVE: openpyxl lookup | Header-alias approach | Harness code execution | **KEEP bounded; WRAP complex** | — |
| Files / attachments store | LIVE: `core/file_store.py` (per-user, path confinement) | Solid | Harness workspaces | **KEEP + ADAPT** | Becomes the capsule's resource staging area. The harness receives scoped copies or a scoped workspace. |
| Drive | LIVE: `services/drive_service.py` | Two environment-sensitive tests | M365/Google MCP | **KEEP** | — |
| Meetings / calendar / messaging (Teams, WhatsApp) | Absent | — | Hermes/OpenClaw gateways; M365 MCP | **DEFER** | Consequential and credential-heavy; needs posture per D-B. |

## G. Integration substrate

| Capability | Current URI | Legacy lesson | Ecosystem | Verdict | Evidence / reason |
|---|---|---|---|---|---|
| External Capability Contract (descriptor, qualification, lifecycle, transports) | LIVE via registry (`uri_core/external/*`, M33 A–D, M33.1 35/35) | Qualification checks descriptor shape, not argv safety; registration not restricted | MCP `tools/list` + annotations (annotations are not trust) | **ADAPT** | Seed of both the capability-provider boundary and the harness-provider boundary (`06`). |
| MCP transport (URI as MCP client) | DOC-ONLY reserved (`EXTERNAL_CAPABILITY_CONTRACT.md:11,163`) | Design rules exist | Playwright MCP, Windows-MCP, M365 MCP, thousands of servers | **BUILD (thin) + WRAP servers** | Must target MCP 2026-07-28 or declare its revision. |
| URI as MCP server (capability broker for harnesses) | Absent. Development-only MCP servers exist (`scripts/gemma_worker_mcp.py`, `qwen_coordinator_mcp.py`) as patterns | Guardrail patterns reusable | All candidate harnesses are MCP clients | **BUILD** | Mechanism for exposing URI-gated consequential tools to any harness. |
| ACP client (URI drives harnesses) | Absent | — | About 40 ACP agents | **BUILD** | Most generic harness boundary; see `06`. |
| A2A | Absent | — | A2A 1.0.1 | **DEFER** | No multi-agent federation need for URI Office yet. |
| Skill registry / router (Hermes-derived) | Dormant, unwired in M20 (stale machine-specific inventory) | Stale inventory data made it useless | Harness skill systems | **REPLACE (retire)** | Harness discovery must be live (`capabilities()` at connect time), never a static scan. |
| Safe skill installer | LIVE metadata-only (`uri_core/skills/skill_installer.py`) | Quarantine / digest concepts reusable | Harness plugin managers | **ADAPT** | Reuse quarantine and digest concepts for engine lifecycle pinning. |
| Engine lifecycle (install / pin / health / upgrade / rollback) | Partial: model lifecycle (`edge_lifecycle/*`), npm/yt-dlp pinned installs (M33.1) | Lockfile + `--ignore-scripts` + content-addressed cache precedent | Harness self-updaters (Hermes `.update_check`, weekly releases) | **BUILD (extend M33.1 pattern)** | Silent auto-update is not acceptable for consequential engines (principle 6). |
| Outcome verification (independent end state) | Partial: evidence facts, `decision_gates`; Permanent Acceptance Rule | "Worker-reported success is not trusted" (governance) | **None in ecosystem** | **BUILD** | Unique URI value (`05` §8). |
