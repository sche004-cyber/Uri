# 01 — Ecosystem Research Report

Investigation: URI Harness/Runtime Consumption Strategy (research only, no implementation).
Date of research: 2026-09-27.
Evidence labels: **VERIFIED** (seen in a primary source during this investigation), **LIKELY** (strong indirect evidence, or primary source read through a summarising fetcher whose output looked unreliable), **UNMEASURED** (a quantity nobody has measured), **UNKNOWN** (not established).

## 0. Provenance of the evidence

Two different kinds of external evidence are used, and they have different strength.

1. **Local-source verification (strongest).** A Hermes Agent install exists on the development machine at `%LOCALAPPDATA%\hermes` (`C:\Users\cheta\AppData\Local\hermes`). Its source tree `hermes-agent/` is version **0.21.2** (`pyproject.toml`), MIT licence, git commit `284d220` dated 2026-09-11. Claims marked *(local source)* were read directly from that code during this investigation. Nothing was executed, configured, or modified. Secret-bearing files (`.env`, `auth.json`) were not opened.
2. **Web-documentation verification.** All other external claims come from official repositories, documentation, specifications, and release pages fetched on 2026-09-27. Pages were read through a summarising fetcher. Wording is therefore paraphrased, and where the fetcher output looked garbled the claim is downgraded to LIKELY. Star counts are recorded as displayed and are not audited. The upstream Hermes web documentation describes **v0.21.5** (released 2026-09-24), three patch releases newer than the local install.

No benchmark or performance number in this report was measured by this investigation. The only third-party performance figure mentioned (OmniParser) is explicitly the project's self-reported number.

---

## 1. General-purpose agent harnesses and runtimes

### 1.1 Hermes Agent (Nous Research)
- **URL:** https://github.com/NousResearch/hermes-agent · docs https://hermes-agent.nousresearch.com/docs/
- **Version:** local 0.21.2 (2026-09-11) *(local source)*; upstream v0.21.5 (2026-09-24), roughly weekly releases — VERIFIED.
- **Licence:** MIT — VERIFIED (local `LICENSE`, "Copyright (c) 2025 Nous Research").
- **Problem solved:** a persistent, self-improving personal agent with a multi-platform messaging gateway (Telegram, Discord, Slack, WhatsApp, Signal, email, and others), 40+ tools, skills it can create itself, memory, cron jobs, and sub-agent delegation — VERIFIED.
- **Integration surfaces** — VERIFIED (web: `/docs/developer-guide/programmatic-integration`; local source where noted):
  - ACP (Agent Client Protocol) over stdio via `hermes acp` / `hermes-acp.exe` (local `acp_adapter/`).
  - TUI-gateway JSON-RPC over stdio or WebSocket (`prompt.submit`, `session.steer`, `session.interrupt`, `session.branch`, `session.compress`).
  - OpenAI-compatible HTTP+SSE API server on `localhost:8642` serving `/v1/chat/completions`, `/v1/responses`, `/v1/models`, `/v1/capabilities`, `/v1/toolsets`, `/v1/skills`, `/api/sessions`, **`/v1/runs`**, `/v1/runs/{id}`, `/v1/runs/{id}/events`, `/v1/runs/{id}/approval`, `/v1/runs/{id}/steer`, `/v1/runs/{id}/stop`, and `/api/jobs` with pause/resume/run *(local source: `gateway/platforms/api_server.py:1-6, 81-87, 1548-1555`)*. The runs handler is described as "Durable `/v1/runs` admission, status, events, and control" with idempotency support (`api_server_runs.py`, `api_server_run_idempotency.py`).
  - In-process Python library (`run_agent.AIAgent`).
  - `hermes mcp serve`: a stdio MCP server that exposes **messaging conversations and approvals**, not agent execution (`mcp_serve.py:1-8`, local source).
- **Model ownership:** Hermes owns its model configuration, but accepts any OpenAI-compatible endpoint: `provider: "custom"` with `base_url`; aliases `ollama`, `vllm`, `llamacpp` map to `custom`; LM Studio is first-class as `provider: "lmstudio"` defaulting to `http://127.0.0.1:1234/v1` *(local source: `cli-config.yaml.example:65-83`)*. Provider profiles are plugins (`providers/README.md`). Web documentation states a **minimum of 64k context**, and that llama.cpp needs `--jinja` and vLLM `--tool-call-parser hermes` for tool calls — VERIFIED (web).
- **Per-run control over model and instructions:** a `/v1/runs` request body accepts `model` and `instructions` (ephemeral system prompt) *(local source: `api_server_runs.py:251-285, 420-491`)*. **Per-run toolset scoping was not found** in the runs handler; toolsets appear to be configured per profile. Status: absence observed in one handler, therefore LIKELY profile-level only, not proven.
- **Approval / permission interception** *(local source)*:
  - `tools/approval.py`: "Dangerous command approval". Guards cover terminal commands, code execution, and a generic `request_tool_approval` path; a hardline blocklist, user deny rules, and permanent allowlists; a `smart` mode that asks a guardian LLM (`approval_smart.py`); and approval transports for CLI, gateway, plugins, and MCP elicitation. YOLO mode is frozen at import so a skill cannot flip it at run time.
  - `acp_adapter/permissions.py`: bridges Hermes dangerous-command approvals to ACP `session/request_permission` with allow-once / allow-session / allow-always / deny options.
  - `acp_adapter/edit_approval.py`: pre-execution **file-edit** approval exists **only in ACP sessions**; "CLI, gateway, and other sessions leave it unset and therefore bypass this guard".
  - Plugin hook `pre_tool_call` can block a call or rewrite its arguments. **If the hook raises, the call proceeds**: `_pre_tool_block_message` catches all exceptions and returns `(None, function_args)` (`agent/agent_runtime_helpers.py:2210-2222`). This is fail-open with respect to hook failure.
  - Web docs: default approval mode is `smart` (an auxiliary LLM auto-approves or auto-denies); `manual` and `off`/`--yolo` exist; approvals time out after 300 s — VERIFIED (web: `/docs/user-guide/security`).
- **Computer use:** registered tool `computer_use` backed by the third-party **`cua-driver`** binary on macOS, Windows and Linux, described as background control that does not steal cursor or focus. The driver runs with provider secrets stripped from its environment *(local source: `tools/computer_use_tool.py`, `tools/computer_use/permissions.py`)*. Reliability on Windows: UNMEASURED.
- **Browser:** extensive (CDP tools, browser-use CLI, Camofox, Lightpanda, cloud browsers) *(local source: `tools/browser_*`)*.
- **Terminal / code:** local, docker, ssh, modal, daytona, vercel_sandbox, singularity backends — VERIFIED (web).
- **State:** `%LOCALAPPDATA%\hermes` on Windows: `config.yaml`, `.env`, `state.db` (SQLite with WAL and FTS), `sessions/`, `memories/`, `skills/`, `cron/`, `projects.db` *(local directory listing)*.
- **Windows:** native CLI, gateway, TUI and tools; WSL2 optional; antivirus false-positive on `uv.exe` noted upstream — VERIFIED (web).
- **Protocols:** MCP client — VERIFIED; ACP agent (listed in the ACP registry) — VERIFIED; A2A appears as a platform plugin in the 2026-09-03 inventory (`hermes_uri_inventory.json`) — LIKELY.
- **Maturity:** very active, broad; about 249k stars displayed — VERIFIED (as displayed).
- **Brick walls:** very large surface (hundreds of modules, own memory, self-created skills, own session database); fast release cadence; approval scope defined by Hermes' own classifier, not by URI; `pre_tool_call` fail-open on exception; edit approval only in ACP mode; ≥64k context requirement collides with local VRAM; `smart` default delegates approval to an LLM.

### 1.2 DeepSeek Harness
- **URL:** https://github.com/deepseek-ai/deepseek-harness (npm `@deepseek-ai/dsh`); https://deepseek.com/harness/en/
- **Status:** official, MIT, Node.js, **developer preview**; README warns of compatibility-breaking changes — VERIFIED. Version reported by a secondary source as 0.1.0-rc.6 (2026-08-13) — LIKELY.
- **Architecture:** Cordis plugin kernel where model, tools, skills, sessions, sandboxes, storage, loop, scheduling and UI are all plugins; sessions are an append-only log that can be resumed, forked, searched, replayed; local web UI on `127.0.0.1:3080` — VERIFIED.
- **Name ambiguity:** an unrelated community Python package `deepseek-harness` (https://github.com/HenryZ838978/deepseek-harness) exists — VERIFIED.
- **Unknown:** non-DeepSeek model adapters, OpenAI-compatible endpoint support, approval hooks, MCP, ACP, Windows support (docs site returned empty) — UNKNOWN.
- **Assessment:** architecturally interesting (plugin kernel, replayable log) but too immature to qualify. Re-check later.

### 1.3 OpenAI Codex CLI (app-server)
- **URL:** https://github.com/openai/codex · https://learn.chatgpt.com/docs/app-server
- **Status:** Apache-2.0; latest 0.159.0-alpha.9 (2026-09-27), several alphas per day — VERIFIED.
- **Surface:** `codex app-server` JSON-RPC 2.0 over stdio, WebSocket or Unix socket. `thread/start|resume|fork|list|read|archive|delete`, `turn/start|steer|interrupt`; streamed `turn/*`, `item/*` notifications; **command and file-change approval requests** answered `accept` / `decline` / `acceptForSession`; generated TypeScript and JSON-schema client types — VERIFIED.
- **Models:** custom `model_providers.<id>` with `base_url`; `--oss` with Ollama or LM Studio; **Responses API only** (chat-completions wire removed around February 2026) — VERIFIED.
- **Permissions:** `approval_policy`; sandbox modes; `hooks.json` lifecycle hooks; native **Windows sandbox** (elevated creates dedicated sandbox users plus firewall rules) — VERIFIED.
- **State:** `~/.codex` — VERIFIED.
- **ACP:** listed — VERIFIED.
- **URI governance tension:** Codex CLI is a URI **development agent** under AO-4. The standing M31 rule forbids using it as URI's Brain (`docs/plans/M31_MODEL_BRAIN_UX_PLAN.md:80-82`, `_V1` worktree). The user authorised evaluating it as an **execution harness** in this study (decision D-A), with any adoption requiring a separate ruling.

### 1.4 Claude Agent SDK / Claude Code headless
- **URL:** https://code.claude.com/docs/en/agent-sdk/overview
- **Licence:** Anthropic Commercial Terms, not open source; third parties may not offer claude.ai login without approval — VERIFIED.
- **Permissions:** the richest interception model seen: evaluation order hooks → deny rules → ask rules → permission mode → allow rules → `canUseTool` callback; `PreToolUse` hook returns allow / deny / ask / **defer** (defer ends the query for later resumption) and may rewrite input; `setPermissionMode()` mid-stream — VERIFIED.
- **Models:** Claude models only; gateways must be Anthropic-format; Anthropic does not support routing to non-Claude models — VERIFIED.
- **Other:** sessions resume/fork, MCP, skills, plugins; ACP listed — VERIFIED.
- **Brick walls:** cannot consume URI's local intelligence; commercial terms; development-agent tension (D-A).

### 1.5 Google Gemini CLI
- **URL:** https://github.com/google-gemini/gemini-cli
- **Status:** Apache-2.0, v0.61.0 (2026-09-23) — VERIFIED.
- **Surface:** headless `--output-format json|stream-json` (init, message, tool_use, tool_result, error, result events); ACP mode; MCP; checkpointing; sandboxing; trusted folders — VERIFIED. `BeforeTool` hook can block — VERIFIED.
- **Models:** Gemini only; no documented custom OpenAI-compatible endpoint — LIKELY.

### 1.6 OpenHands Software Agent SDK and Agent Server
- **URL:** https://github.com/OpenHands/software-agent-sdk · https://docs.openhands.dev/sdk
- **Status:** MIT — VERIFIED.
- **Surface:** Python SDK and an Agent Server (REST + WebSocket, `X-Session-API-Key`) — VERIFIED.
- **Permissions:** confirmation policies AlwaysConfirm / NeverConfirm / ConfirmRisky, LLM security analyser, `WAITING_FOR_CONFIRMATION` status and `reject_pending_actions()` — VERIFIED.
- **State:** `persistence_dir` (`workspace/conversations/` with `base_state.json` and `events/`); pause/resume — VERIFIED.
- **Models:** "any LLM" (LiteLLM-based) — LIKELY. **Windows:** UNKNOWN. MCP — VERIFIED; ACP client and listed ACP agent — VERIFIED.

### 1.7 Goose
- **URL:** https://github.com/aaif-goose/goose (moved from `block/goose`), hosted by the Agentic AI Foundation (Linux Foundation).
- **Status:** Apache-2.0, Rust, v1.52.0 (2026-09-23), weekly — VERIFIED.
- **Models:** 15+ providers including Ollama — VERIFIED. **MCP-native** extensions — VERIFIED. `acp serve` — VERIFIED. Desktop app on Windows — VERIFIED.
- **Permissions:** permission modes; denies win (v1.48); per-turn tool allowlists (v1.49); recipe consent (v1.52) — VERIFIED.
- **Interrupt/resume, state location:** UNKNOWN.

### 1.8 OpenCode
- **URL:** https://github.com/anomalyco/opencode · https://opencode.ai/docs/server/
- **Status:** MIT, very active, Windows exe — VERIFIED.
- **Surface:** `opencode serve` with an OpenAPI 3.1 spec at `/doc`, SSE at `/event`, `POST /session/:id/abort`, `POST /session/:id/permissions/:permissionID`; `opencode acp` — VERIFIED.
- **Permissions:** allow / ask / deny per tool with patterns — VERIFIED.
- **Models:** `@ai-sdk/openai-compatible` with `baseURL` (Ollama, LM Studio, llama.cpp) — VERIFIED.

### 1.9 Microsoft Agent Framework
- **URL:** https://github.com/microsoft/agent-framework · https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/
- **Status:** 1.0 GA 2026-04-03; python-1.19.0 and dotnet-1.22.0 (2026-09-18); MIT — VERIFIED. Successor to AutoGen and Semantic Kernel — VERIFIED.
- **Capabilities:** graph workflows with checkpointing, human-in-the-loop, OpenTelemetry, A2A, MCP, AG-UI, DevUI, declarative YAML — VERIFIED. "Harness" plus Foundry Hosted Agents GA (June 2026) with tool approval, history persistence and compaction; shell and file tools opt-in — VERIFIED (InfoQ, secondary).
- **Nature:** a **framework (library)**, not a ready desktop agent. URI would build tools, UI and permission UX on it.
- **Local models via Ollama:** UNKNOWN (OpenAI-compatible client support LIKELY).

### 1.10 LangGraph and LangChain Deep Agents
- **URL:** https://docs.langchain.com/oss/python/langgraph/interrupts · https://github.com/langchain-ai/deepagents
- **Status:** LangGraph 1.2.12 (2026-09-21), MIT; Deep Agents MIT — VERIFIED.
- **Capabilities:** `interrupt()` + `Command(resume=...)` with a checkpointer (`SqliteSaver`, `PostgresSaver`) and `thread_id`; Deep Agents adds planning, pluggable filesystem/sandbox backends, sub-agents, MCP, human-in-the-loop `interrupt_on`, and ACP via `deepagents-acp` — VERIFIED. Any LangChain chat model including Ollama, vLLM, llama.cpp — VERIFIED.
- **Nature:** library. Strongest durable interrupt/resume primitive among libraries.

### 1.11 OpenAI Agents SDK
- **URL:** https://github.com/openai/openai-agents-python
- **Status:** v0.22.3 (2026-09-17), MIT — VERIFIED.
- **Capabilities:** tools with `needs_approval` (bool or async predicate); pending approvals in `result.interruptions`; `RunState.to_json()/from_json()` for durable pause/resume; MCP servers with `require_approval`; guardrails; sessions; tracing; sandbox agents — VERIFIED. 100+ models via LiteLLM and OpenAI-compatible APIs — VERIFIED.
- **Nature:** library. Cleanest serialisable approval-interrupt model among libraries.

### 1.12 smolagents, CrewAI, OpenClaw
- **smolagents** 1.26.0 (2026-05-29), Apache-2.0; local executor "is not a security boundary"; release cadence slowed — VERIFIED/LIKELY.
- **CrewAI** MIT; crews and flows, human-in-the-loop, MCP, A2A, Ollama via LiteLLM — VERIFIED.
- **OpenClaw** (https://github.com/openclaw/openclaw) MIT, OpenClaw Foundation; local gateway across many chat channels; tools run on host unless sandboxing is configured; tool approval; MCP; native Windows app; state `~/.openclaw`; Node 24.16+; listed ACP agent — VERIFIED. Same product class as Hermes.

---

## 2. Computer-use systems
| System | Evidence | Key facts | Confidence |
|---|---|---|---|
| Anthropic computer-use tool | https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool | `computer_toolset_20260801`, 17 actions incl. zoom and batching; GA on Claude API; reference is a Docker demo. Model-side capability; execution is yours. | VERIFIED |
| OpenAI `computer` tool | https://developers.openai.com/api/docs/guides/tools-computer-use | Responses API tool; you run Playwright or PyAutoGUI; `pending_safety_checks`. Model names reported by fetcher unconfirmed. | VERIFIED / LIKELY |
| Microsoft UFO² / UFO³ | https://github.com/microsoft/UFO | MIT; UFO² (LTS) hybrid Windows UIA + API actions; UFO³ Galaxy multi-device in development; MCP. Local-model support UNKNOWN. | VERIFIED |
| UI-TARS-desktop | https://github.com/bytedance/UI-TARS-desktop | Apache-2.0; Windows/macOS; UI-TARS-1.5 / Seed-VL or OpenAI-compatible; last seen release Nov 2025. | VERIFIED / LIKELY slowing |
| Windows-MCP | https://github.com/CursorTouch/Windows-MCP | MIT; UIA-based, ~20 tools incl. PowerShell, Registry, Snapshot; Python 3.13+; prefers English UI; project-stated 0.2–0.5 s per action (not measured here). | VERIFIED |
| cua-driver (via Hermes) | local Hermes source `tools/computer_use/` | Cross-platform background driver used by Hermes' `computer_use`; separate third-party binary. | VERIFIED (local) |
| Windows native agent platform (MCP on Windows / On-device Agent Registry, agent workspace) | https://learn.microsoft.com/en-us/windows/ai/mcp/overview · https://learn.microsoft.com/en-us/windows/security/book/operating-system-agentic-security | Preview / experimental; agent workspace behind an experimental setting; third-party availability "coming soon" as of the Nov 2025 page. GA by Sep 2026: UNKNOWN. | VERIFIED / UNKNOWN |
| OmniParser V2 | https://github.com/microsoft/OmniParser | Screen parsing; mixed weight licences; self-reported ScreenSpot Pro 39.5% (project's own number). | VERIFIED (self-report) |

## 3. Browser automation
| System | Evidence | Key facts | Confidence |
|---|---|---|---|
| Playwright MCP | https://github.com/microsoft/playwright-mcp | Apache-2.0; accessibility-tree actions (not pixels); `--isolated`, `--user-data-dir`, `--caps`; extension mode attaches to existing Chrome/Edge. | VERIFIED |
| browser-use | https://github.com/browser-use/browser-use | MIT; Ollama support; paid cloud; own model BU2. | VERIFIED |
| Stagehand | https://github.com/browserbase/stagehand | MIT; act / observe / extract / agent primitives; local or Browserbase. | VERIFIED |
| Chrome DevTools MCP | https://github.com/ChromeDevTools/chrome-devtools-mcp | Puppeteer-based; traces, network, console; usage statistics on by default (`--no-usage-statistics`). | VERIFIED |

## 4. Terminal / code execution and sandboxing
- Codex native Windows sandbox (https://learn.chatgpt.com/docs/windows/windows-sandbox) — VERIFIED.
- Hermes docker/ssh/modal/daytona backends and `HERMES_WRITE_SAFE_ROOT` — VERIFIED.
- Windows Sandbox: Pro/Enterprise/Education only, one instance at a time, networking on by default (https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-overview) — VERIFIED. The development machine runs Windows 11 Pro (session environment).
- E2B: cloud sandboxes; Windows sandboxes not mentioned — VERIFIED.

## 5. MCP and tool ecosystems
- **MCP current revision 2026-07-28** is a **breaking** revision: stateless (no `initialize` handshake, no `Mcp-Session-Id`), mandatory `server/discover`, `subscriptions/listen`, multi-round-trip requests (`resultType: "input_required"`) replacing server-initiated sampling / elicitation / roots, tasks moved to the `io.modelcontextprotocol/tasks` extension, SSE resumability removed; Roots, Sampling, Logging, HTTP+SSE and Dynamic Client Registration deprecated; RFC 9207 `iss` validation; `traceparent` in `_meta`. Previous revision 2025-11-25. Backward-compatibility handling specified. Sources: https://modelcontextprotocol.io/specification/versioning, https://modelcontextprotocol.io/specification/latest/changelog — VERIFIED.
- Implication: any URI MCP work must pick a revision explicitly and qualify each harness's MCP client revision.

## 6. Agent-to-agent and agent-to-client interoperability
- **ACP (Agent Client Protocol, Zed):** JSON-RPC 2.0; `initialize`, `authenticate`, `session/new`, `session/prompt`, `session/cancel`; the *client* supplies file-system, terminal, and permission/elicitation methods and receives `session/update` notifications. About 40 listed agents including Claude Agent, Codex CLI, Gemini CLI, Goose, Hermes, OpenClaw, OpenCode, OpenHands, Copilot, Qwen Code. Schema v1.23.0 (date garbled by fetcher). https://agentclientprotocol.com/protocol/overview, https://agentclientprotocol.com/overview/agents — VERIFIED (date LIKELY 2026).
- **A2A:** v1.0.0 (2026-03-12), v1.0.1 (2026-05-28); task states SUBMITTED, WORKING, COMPLETED, FAILED, CANCELED, INPUT_REQUIRED, REJECTED, AUTH_REQUIRED; polling, streaming, push; JSON-RPC, gRPC, HTTP+JSON; under AAIF. https://a2a-protocol.org/latest/specification/ — VERIFIED.
- **AG-UI:** event protocol between agent back-end and UI (lifecycle, text, tool-call, state events, interrupts). https://docs.ag-ui.com/introduction — VERIFIED.
- **AAIF** hosts MCP, goose, AGENTS.md, agentgateway, A2A, Agent Router. https://aaif.io/projects/ — VERIFIED.

## 7. Local / cloud model gateways and serving
| System | Key facts | Confidence |
|---|---|---|
| Ollama v0.34.4 (2026-09-23) | OpenAI-compatible `/v1/chat/completions`, `/v1/completions`, `/v1/embeddings`, `/v1/responses`; tools + streaming; `OLLAMA_NUM_PARALLEL` default 1, `OLLAMA_MAX_LOADED_MODELS` 3×GPUs; **default context 4k when VRAM < 24 GiB**; RX 7900 GRE on Windows ROCm list; Vulkan on by default. https://docs.ollama.com/faq, /gpu, /context-length, /api/openai-compatibility | VERIFIED |
| llama.cpp server | chat completions with tools and reasoning, responses, embeddings, `--parallel` slots, Jinja templates, built-in MCP support. | VERIFIED |
| LM Studio | OpenAI- and Anthropic-compatible endpoints, REST v1, MCP, headless `llmster` daemon on Windows. Licence terms UNKNOWN. Already URI's qualification runtime. | VERIFIED |
| LiteLLM | MIT + enterprise; `/v1/responses`, `/v1/messages`, MCP gateway, A2A. **PyPI 1.82.7 and 1.82.8 compromised 2026-03-24** (credential-stealing `.pth`). https://docs.litellm.ai/blog/security-update-march-2026 | VERIFIED |
| vLLM | No native Windows (WSL only). | VERIFIED |
| Lemonade (AMD) | Apache-2.0; llama.cpp Vulkan/ROCm, ONNX, NPU backends; OpenAI/Ollama/Anthropic-compatible on `localhost:13305/v1`; Windows MSI. | VERIFIED |

## 8. Model-provider abstraction
Every serious open harness except Claude Agent SDK and Gemini CLI accepts an external OpenAI-compatible endpoint; Codex requires the **Responses** wire. See `07_INTELLIGENCE_SHARING_ANALYSIS.md`.

## 9. Messaging / communication integrations
Hermes and OpenClaw ship multi-platform messaging gateways (Telegram, WhatsApp, Slack, Discord, Signal, email, Teams). Microsoft 365 MCP servers (Mail, Calendar, Teams, Word, SharePoint, OneDrive) are **remote, tenant-bound, preview** (https://github.com/microsoft/mcp) — VERIFIED. They do not automate local Office files.

## 10. Voice / realtime
Hermes has voice modules (`gateway/run_voice.py`, `streaming_tts_consumer.py`, wakewords) *(local source)*. URI's own STT is UNQUALIFIED (`docs/plans/M33_2_BATCH_B4_COMPLETION_REPORT.md`). Deep voice research was out of scope: architecturally, voice is a capability provider, not a harness concern. DEFER.

## 11. Document / Office automation
- Anthropic `docx`/`xlsx`/`pptx`/`pdf` skills are "source-available, not open source" (https://github.com/anthropics/skills) — VERIFIED. Exact tooling LIKELY python-docx/openpyxl/LibreOffice recalculation.
- Microsoft 365 MCP: cloud/tenant only — VERIFIED.
- python-docx / openpyxl vs COM automation vs LibreOffice headless: **no primary source fetched this session** — UNKNOWN. Prior knowledge (not evidence): openpyxl does not evaluate formulas; COM requires installed Office and an interactive session; LibreOffice headless converts and recalculates. Needs experiment E-P6.
- URI already has library-based generation (see `02_CAPABILITY_OWNERSHIP_MATRIX.md`).

## 12. Workflow / orchestration runtimes
Temporal (AI cookbook covers OpenAI Agents SDK, Claude, MCP, human-in-the-loop), DBOS (library, SQLite or Postgres), Restate (licence and Windows UNKNOWN), LangGraph checkpointers — VERIFIED. For a single-user Windows desktop, SQLite-backed durability is the lightest fit (judgement, LIKELY).

## 13. Context / memory systems
Hermes memory providers (honcho, mem0, supermemory and others per 2026-09-03 inventory), OpenClaw memory, harness session stores. None is portable across harnesses; each is harness-owned. See `04_BRICK_WALL_RISK_REGISTER.md` R-S1.

## 14. Permission / approval mechanisms (cross-harness summary)
| Harness | Per-call interception available to an external controller | Fail mode | Confidence |
|---|---|---|---|
| Claude Agent SDK | `PreToolUse` hook + `canUseTool` for every tool; allow/deny/ask/defer; input rewrite | Controller decides | VERIFIED |
| Codex app-server | Approval requests for commands and file changes; hooks.json | Policy-driven | VERIFIED |
| Hermes | Approval for Hermes-classified dangerous commands; ACP-only edit approval; in-process `pre_tool_call` for all tools | Hook exception → allow | VERIFIED (local) |
| OpenHands | Confirmation policy per action (AlwaysConfirm available) | Controller decides when AlwaysConfirm | VERIFIED |
| OpenCode | allow/ask/deny per tool; permission endpoint | Config-driven | VERIFIED |
| Goose | permission modes, per-turn allowlists, denies win | Config-driven | VERIFIED |
| OpenAI Agents SDK / LangGraph / MS Agent Framework | Library-level: you own every tool, so every call is interceptable | Your code | VERIFIED |
| ACP generic | `session/request_permission` issued at the agent's discretion | Agent decides what to ask | VERIFIED |

Key finding: **ACP permission requests are issued only when the agent chooses to ask.** A generic ACP client cannot force per-call interception; completeness depends on each agent's own classification. This is why decision D-B (authority posture decided per harness) is necessary.

## 15. Observability and verification
- OpenTelemetry GenAI semantic conventions moved to https://github.com/open-telemetry/semantic-conventions-genai; still in development — VERIFIED/LIKELY. URI S7/S8 already adopt `gen_ai.*` naming without the SDK (`uri_v1/evaluation/*`, `_V1`).
- Langfuse (MIT core; self-host needs Postgres, ClickHouse, Redis, S3); Arize Phoenix (**Elastic License 2.0**, SQLite option) — VERIFIED.
- Harness-native events: Hermes `/v1/runs/{id}/events`, Codex `item/*` notifications, ACP `session/update`, Gemini `stream-json`, OpenCode `/event` SSE — VERIFIED.
- **No harness offers independent outcome verification.** Every harness reports its own success. URI's "verify the end state" principle has no ecosystem replacement — BUILD.

## 16. Emerging standards summary
ACP (agent↔client), MCP 2026-07-28 (agent↔tools), A2A 1.0 (agent↔agent), AG-UI (agent↔UI), AGENTS.md, OpenTelemetry GenAI (observability). Convergence is real but young; MCP just broke compatibility, ACP is fast-moving.
