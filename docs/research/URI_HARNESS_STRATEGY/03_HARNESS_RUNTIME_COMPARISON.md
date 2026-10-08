# 03 — Harness / Runtime Comparison

This document compares every credible harness/runtime on the same criteria. Hermes is one candidate among thirteen. Facts come from `01_ECOSYSTEM_RESEARCH_REPORT.md` and carry the same evidence labels.

## 1. Two categories, not one

The research shows two different product categories. They have different integration economics.

- **Ready agents with a control surface.** These ship tools, a loop, a UI, a session store and a permission model: Hermes, OpenClaw, Codex app-server, Claude Agent SDK, Gemini CLI, OpenHands Agent Server, Goose, OpenCode, DeepSeek Harness. URI would *drive* them.
- **Agent frameworks (libraries).** These give primitives (loop, interrupts, checkpointing) but URI brings the tools and UX: Microsoft Agent Framework, LangGraph/Deep Agents, OpenAI Agents SDK, smolagents, CrewAI. URI would *build on* them.

Consuming a ready agent gives the native capability for free, including browser, terminal, computer use, sub-agents and skills. It also imports the agent's own state, classifier and update cadence. Building on a framework gives complete interception, because every tool is URI's. It also re-creates the tool surface that the brief says URI should not rebuild.

## 2. Comparison table (ready agents)

| Criterion | Hermes 0.21.x | Codex app-server | Claude Agent SDK | Gemini CLI | OpenHands Agent Server | Goose | OpenCode serve | OpenClaw | DeepSeek Harness |
|---|---|---|---|---|---|---|---|---|---|
| **Problem solved** | Personal agent, messaging gateway, self-improving skills | Coding agent | Coding / general agent | Coding / general agent | Software agent platform | General agent, MCP-native | Coding agent | Personal agent gateway | Plugin-kernel agent |
| **Control surface** | ACP; TUI-gateway JSON-RPC; HTTP `/v1/runs` + events / approval / steer / stop | JSON-RPC (stdio/WS) threads + turns | SDK (Py/TS); `-p` JSON | stream-json; ACP | REST + WS | ACP serve; CLI; desktop | OpenAPI + SSE; ACP | gateway, CLI | Node; web UI |
| **Model ownership / external endpoint** | Own config; custom OpenAI-compatible `base_url`; LM Studio first-class (V local) | Own config; custom provider; **Responses API only** | **Claude only** | **Gemini only** (L) | Any LLM (L) | 15+ providers incl. Ollama | OpenAI-compatible baseURL | Local models (L) | U |
| **Context ownership** | Harness (compression, memory) | Harness | Harness | Harness | Harness | Harness | Harness | Harness | Harness (append-only log) |
| **Tool ownership** | Harness (40+) + MCP + plugins | Harness + MCP | Harness + MCP | Harness + MCP | Harness + MCP | MCP extensions | Harness + MCP | Harness + MCP | Plugins |
| **Computer use** | `computer_use` via cua-driver (Win) | No native desktop control | Via Anthropic tool (you execute) | No | No (L) | Via MCP extension | No | U | U |
| **Browser** | Extensive native | Via MCP | Via MCP | Via MCP | Browser tools (L) | Via MCP | Via MCP | Yes (L) | U |
| **Terminal / FS** | Yes; docker/ssh/cloud backends | Yes; **native Windows sandbox** | Yes | Yes; sandbox | Yes; sandboxed runtime | Yes | Yes | Yes (host unless sandboxed) | U |
| **MCP** | Client | Client | Client | Client | Client | Core | Client | Client | U |
| **ACP / A2A** | ACP agent / A2A plugin (L) | ACP listed | ACP listed | ACP | ACP client + agent | ACP | ACP | ACP listed | U |
| **Human approval** | Dangerous-command classifier; `smart` default = guardian LLM; ACP-only edit approval | Command + file-change approval requests | Every tool via hooks / `canUseTool` | BeforeTool hook; approval modes | AlwaysConfirm / ConfirmRisky | Modes; per-turn allowlists; denies win | allow / ask / deny per tool | Tool approval | U |
| **External per-call interception** | Partial: classifier-scoped approvals; in-process `pre_tool_call` (**fails open on hook exception**) | Partial: commands + file changes | **Complete** | Complete via hook (L) | Complete with AlwaysConfirm | Partial (config) | Complete via `ask` (config) | Partial (L) | U |
| **Observability** | `/v1/runs/{id}/events`, hooks, webhooks | `item/*` notifications | Hook events, stream | stream-json | WS events | U | SSE `/event` | U | Log replay |
| **Interrupt / resume** | stop, steer, interrupt, branch; sessions persisted | `turn/interrupt`, `thread/resume|fork` | resume / fork; hook `defer` | checkpointing | pause / resume | U | abort; sessions | U | resume / fork / replay |
| **State location** | `%LOCALAPPDATA%\hermes` (state.db, memories, skills) | `~/.codex` | `~/.claude` + project (L) | `~/.gemini` | persistence_dir | U | U | `~/.openclaw` | plugin storage |
| **Extensibility** | Plugins, hooks, skills, providers | hooks.json, MCP | hooks, plugins, skills | hooks, extensions | SDK | recipes, extensions | plugins | plugins | everything-is-plugin |
| **Windows** | Native (V) | Native + sandbox (V) | Yes (L) | Yes (V) | U | Desktop (V) | Native (V) | Native (V) | U |
| **Local-model suitability on 16 GB VRAM** | Needs ≥64k ctx → KV pressure (UNMEASURED) | Needs Responses-capable server | None | None | Depends | Ollama OK; ctx UNMEASURED | OK; ctx UNMEASURED | U | U |
| **Cloud-model suitability** | Broad | OpenAI + custom | Claude | Gemini | Broad (L) | Broad | Broad | Broad | DeepSeek |
| **Resource implications** | Python process + optional gateway, browsers, cua-driver: UNMEASURED | Rust binary: UNMEASURED | Node binary: UNMEASURED | Node: UNMEASURED | Python server + runtime: UNMEASURED | Rust: UNMEASURED | Bun/Node: UNMEASURED | Node 24: UNMEASURED | Node: UNMEASURED |
| **Update burden** | High (weekly, large surface) | Very high (daily alphas) | Medium | Medium | Medium | Medium (weekly) | High | High | Very high (breaking) |
| **Lock-in risk** | Medium (state + skills) | Medium (Responses wire) | High (Claude-only, ToS) | High (Gemini-only) | Low–medium | Low (AAIF, MCP-native) | Low–medium | Medium | High (preview) |
| **Licence** | MIT | Apache-2.0 | Commercial terms | Apache-2.0 | MIT | Apache-2.0 | MIT | MIT | MIT |
| **Maturity** | High activity | High activity, unstable versions | Mature | Mature | Active | Active, foundation-backed | Very active | Very active | Preview |
| **URI governance issue** | Hermes path previously retired (stale inventory, unsafe forge) | **D-A tension** (development agent) | **D-A tension**; Claude-only | **D-A tension** | None | None | None | None | None |
| **Known brick walls** | fail-open hook; classifier-scoped approvals; 64k ctx; smart default; self-learning state | Responses-only; daily churn | cannot use URI intelligence | cannot use URI intelligence | Windows U | interruption/state U | ACP lacks undo/redo | host execution default | immature |

## 3. Frameworks (libraries)

| Criterion | MS Agent Framework 1.x | LangGraph / Deep Agents | OpenAI Agents SDK | smolagents | CrewAI |
|---|---|---|---|---|---|
| Interception | Complete (your tools); tool approval | Complete; `interrupt()` | Complete; `needs_approval` | Step callbacks (L) | HITL |
| Durable pause/resume | Workflow checkpointing | Checkpointer + thread_id (SQLite) | `RunState` JSON | L | Flows |
| Model endpoint | OpenAI-compatible (L) | Any LangChain model incl. Ollama | LiteLLM / OpenAI-compatible | LiteLLM / Ollama | LiteLLM / Ollama |
| Native tools supplied | Harness opt-in shell / file | Deep Agents filesystem / sandbox backends | Sandbox agents | Code executor (not a security boundary) | Some |
| Protocols | MCP, A2A, AG-UI | MCP, ACP (Deep Agents) | MCP | MCP | MCP, A2A |
| Licence | MIT | MIT | MIT | Apache-2.0 | MIT |
| Role for URI | Candidate **URI-native fallback runtime** substrate | Candidate **URI-native fallback runtime** substrate (lightest durable interrupt model) | Candidate fallback substrate | Not recommended | Not recommended |

## 4. Authority-qualification criteria (decision D-B: posture decided per harness)

Each harness earns one of four **authority postures**. The posture is a property of a *(harness version × configuration × URI adapter)* triple, re-qualified on every upgrade.

| Posture | May perform directly | Required evidence |
|---|---|---|
| **P0 — Observe only** | Read-only operations inside the staged workspace | Health, event stream, stop works |
| **P1 — Reversible local** | P0 + local writes confined to a URI-staged workspace (copies, sandbox), reversible | Workspace confinement verified; file-change events complete; stop honoured within bound |
| **P2 — Gated consequential** | P1 + consequential actions **only** via URI-brokered tools (URI MCP broker) that pass URI approval gates | Harness-native consequential tools disabled or proven unreachable; broker is the only route to external effects |
| **P3 — Delegated consequential** | Harness-native consequential tools, with every such call routed to URI for decision | **Complete per-call interception** proven (every consequential tool raises a URI decision); fail-closed on adapter / hook failure; deny honoured; args bound to approval (fingerprint) |

Qualification tests (see `08_EXPERIMENT_ROADMAP.md` E-P2):
1. **Interception completeness.** Enumerate the harness's consequential tools (send, delete, submit, external HTTP write, shell outside workspace, credential use). For each, prove a URI decision is raised before effect.
2. **Fail-closed behaviour.** Kill or break the URI hook/adapter mid-run. The harness must stop or deny, not proceed. *Hermes `pre_tool_call` fails open on exception by code inspection; P3 for Hermes therefore needs a mitigation, such as an in-process URI plugin that never raises, plus toolset removal, and must be proven by test.*
3. **Argument binding.** The executed arguments must equal the approved arguments (URI already binds approvals to an args SHA-256).
4. **Scope confinement.** Filesystem and network scope must be enforced by the harness sandbox or OS, not by prompt.
5. **Stop latency and honour.** Stop / interrupt takes effect within a declared bound, and no effect lands after a stop acknowledgement.
6. **Event completeness.** Every tool call appears in the event stream with arguments and result (for provenance).
7. **Configuration drift.** Upgrade the harness version and confirm the posture evidence is invalidated, then re-run.

**Preliminary posture ceilings by code or document inspection (not qualification):**
- Claude Agent SDK: P3 plausible (hooks on every tool; `defer`). D-A tension; Claude-only.
- OpenHands (AlwaysConfirm): P3 plausible. Windows UNKNOWN.
- OpenCode (`ask` on all tools + permission endpoint): P3 plausible.
- Codex: P2–P3 (commands and file changes interceptable; MCP tool calls need checking). D-A tension.
- Hermes: **P2 ceiling until fail-open is mitigated and proven**. Approvals are classifier-scoped; edit approval is ACP-only; `smart` default must be replaced by `manual`.
- Goose: P2 (config-level allowlists; per-call external decision UNKNOWN).
- OpenClaw, DeepSeek Harness, Gemini CLI: UNKNOWN / not assessed deeply.

## 5. Ranking for URI Office (preliminary, subject to experiments)

No single harness wins on all criteria. The evidence supports this shape:

1. **Primary generic boundary: ACP.** One URI ACP client can drive Hermes, Goose, OpenCode, OpenHands, Codex, Claude Agent, Gemini CLI and Deep Agents. The weakness is that permission requests are issued at the agent's discretion, which is why per-harness posture qualification is needed.
2. **First qualification candidates** (open licence, external model endpoint, Windows, strong control surface): **OpenCode**, **Goose**, **Hermes**, **OpenHands**. Hermes has the richest *office-relevant* native capability: computer use, browser, messaging, cron, and a durable runs API. It also has the largest state and authority surface.
3. **Fallback runtime substrate** if every ready agent fails qualification: **LangGraph / Deep Agents** or **OpenAI Agents SDK** inside URI, reusing URI's own tools. This is the "URI-native fallback" in the brief's diagram.
4. **Development-agent harnesses** (Codex, Claude Agent SDK, Gemini CLI) are technically strong. Claude and Gemini cannot consume URI intelligence. Adoption of any of the three requires the separate user ruling in D-A.
5. **DeepSeek Harness:** watch; do not qualify yet.

Hermes is **not** the recommended target architecture. It is one of four first qualification candidates.
