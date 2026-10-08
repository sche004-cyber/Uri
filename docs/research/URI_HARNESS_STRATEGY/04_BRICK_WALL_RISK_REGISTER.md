# 04 — Brick-Wall & Risk Register

This register tries to **falsify** the wrapper strategy ("URI control plane + replaceable external harnesses").

Each risk has:
- **L:** likelihood (H/M/L)
- **I:** impact (H/M/L)
- **Status:**
  - CONFIRMED: evidence shows it is real
  - PLAUSIBLE: consistent with evidence, not proven
  - UNMEASURED: needs measurement
  - MITIGABLE: a known mitigation exists
- **Falsifier:** the experiment that decides it (IDs refer to `08_EXPERIMENT_ROADMAP.md`)

## A. Authority and security

| ID | Risk | Evidence | L | I | Status | Mitigation | Falsifier |
|---|---|---|---|---|---|---|---|
| R-A1 | **URI cannot intercept every consequential harness action.** Harness approvals cover only what the harness classifies as dangerous. | Hermes approvals are dangerous-command scoped (`tools/approval.py`, local source). Edit approval is ACP-only (`acp_adapter/edit_approval.py`). ACP permission requests are issued at the agent's discretion (`01` §14). | H | H | CONFIRMED for Hermes and generic ACP | Posture P2: disable harness-native consequential tools and route external effects through the URI MCP broker. Use P3 only after interception is proven. | E-P2 |
| R-A2 | **Hook failure fails open.** | Hermes `_pre_tool_block_message` returns allow on any exception (`agent/agent_runtime_helpers.py:2210-2222`, local source). | H (for Hermes) | H | CONFIRMED | A URI plugin that never raises (internal catch → block); toolset removal; OS or sandbox confinement as the real boundary. | E-P2 test 2 |
| R-A3 | **Default "smart" approval hands decisions to an auxiliary LLM.** | Hermes docs: `smart` is the default (`01` §1.1). | H | H | CONFIRMED | The URI engine lifecycle manager enforces `manual` (or URI-routed) approvals in the URI-managed profile and verifies config at every start. | E-P1 config audit |
| R-A4 | **Prompt injection through harness browsing or computer use leads to consequential actions.** | Harnesses browse arbitrary pages; no harness proves resistance. URI's own policy treats observed content as data. | M | H | PLAUSIBLE | Posture P2 (external effects only via URI gates with a user-visible approval); capsule declares prohibited operations; outcome verification. | E-P2, E-P7 |
| R-A5 | **Credential exposure.** Harness processes hold provider keys, OAuth tokens and cookies. | Hermes `.env` and `auth.json` live in the harness home. Hermes strips secrets for cua-driver, showing awareness but not a URI guarantee. | M | H | PLAUSIBLE | URI keeps Gmail/Drive OAuth and exposes only brokered tools. Harness gets a loopback intelligence endpoint key, not vendor keys (`07`). | E-N3 design, E-P3 |
| R-A6 | **Supply-chain compromise of harness or gateway dependencies.** | LiteLLM PyPI compromise, 2026-03-24 (`01` §7). Hermes ships `uv`, node_modules and third-party binaries (cua-driver, browser-use). | M | H | CONFIRMED class risk | Pin versions and hashes (M33.1 lockfile precedent); no silent auto-update; staged upgrade with re-qualification. | E-P8 |
| R-A7 | **Harness runs on host without sandbox by default.** | OpenClaw: "tools run on host unless sandboxing configured". Windows Sandbox is single-instance and Pro+ only. | M | H | CONFIRMED | Workspace staging plus harness sandbox (Codex Windows sandbox, docker backends) where qualified; P1 confinement tests. | E-P2 test 4 |
| R-A8 | **Governance: development-agent harnesses conflict with the M31 rule.** | `docs/plans/M31_MODEL_BRAIN_UX_PLAN.md:80-82`; user decision D-A. | — | M | CONFIRMED tension | Separate explicit user ruling before any adoption. | User decision |

## B. Resource and performance (16 GB VRAM / 24 GB RAM)

| ID | Risk | Evidence | L | I | Status | Mitigation | Falsifier |
|---|---|---|---|---|---|---|---|
| R-R1 | **Harness context requirement exceeds local VRAM budget.** Hermes requires ≥64k context. | The resident 9B Q4 uses 5.63 GB weights plus about 1.80 GB KV at 16,128 context / 4 slots (`docs/plans/M35_URIV1_A2_7_RESIDENT_MAIN_BRAIN_SEMANTIC_QUALIFICATION.md:51-60`). A linear extrapolation to 64k suggests several more GB of KV. This is an **estimate, not a measurement**, and slot sharing semantics are unclear. | H | H | UNMEASURED | KV quantisation, a single slot for harness runs, cloud Capable Brain for harness work, or a smaller context-capable model. | E-P3 |
| R-R2 | **Duplicate model loading.** The harness loads its own copy of a model beside URI's resident models. | Ollama `MAX_LOADED_MODELS` and LM Studio residency are per server. Two servers means two copies. Co-resident Edge+Capable already uses 9.4 GB GPU (`docs/plans/M33_3_R_IMPLEMENTATION_REPORT.md` §6). | H if misconfigured | H | MITIGABLE | Share **one** model server (URI-managed LM Studio/Ollama) or a URI loopback endpoint; forbid harness-owned model downloads. | E-P3 |
| R-R3 | **Ollama default context is 4k on <24 GiB VRAM**, so a harness silently truncates. | https://docs.ollama.com/context-length | H | M | CONFIRMED | Set context explicitly; URI health check verifies the served context against the harness minimum. | E-P3 |
| R-R4 | **RAM pressure.** Batch A saw host RAM reach 21.7 GB of 24 GB (`docs/plans/M33_3_URI_BRAIN_ARCHITECTURE_PROPOSAL.md:233,316`). A harness Python/Node process, a browser and a driver add more. | Repository measurement plus harness processes (UNMEASURED). | H | H | UNMEASURED | Start the harness on demand, not always-on; scale to zero (Hermes has `scale_to_zero.py`, local source); one harness at a time. | E-P3, E-P9 |
| R-R5 | **Harness startup latency hurts "feels immediate".** | User latency preference (memory: composable Brain). Harness cold start UNMEASURED. | M | M | UNMEASURED | The Edge ladder handles immediate interaction; the harness only handles tasks where seconds do not matter; a warm pool if justified. | E-P9 |
| R-R6 | **Token and context duplication.** URI builds context, then the harness rebuilds or compresses its own, and the system prompt, tool schemas and skills inflate each turn. | Hermes 40+ tool schemas; local models are slower on long prompts. | H | M | UNMEASURED | Compact capsule; restrict toolsets per profile; measure prompt tokens per run. | E-P3, E-P5 |
| R-R7 | **Concurrent local-model latency interference** with URI benchmarks. | Research-before-build rule forbids concurrent local-model measurements on the same hardware. | M | M | CONFIRMED process constraint | Serialise experiments. | Process |

## C. Capability and reliability

| ID | Risk | Evidence | L | I | Status | Mitigation | Falsifier |
|---|---|---|---|---|---|---|---|
| R-C1 | **Local models cannot drive a harness reliably.** Tool-call quality is below cloud models. | Gemma 4 12B 0/8 fabrications but 5.5–7.6 s per turn; Qwen3 14B 7.4–8.5 s (`docs/governance/URI_DEVELOPMENT_EVIDENCE_REGISTRY.md:496-520`). No harness-loop evidence on local models. | H | H | UNMEASURED | Use a cloud Capable Brain for harness runs where the user permits; keep local for Edge. | E-P5 |
| R-C2 | **Computer use on Windows is unreliable** (locale, UIA gaps, focus, DPI). | Windows-MCP prefers an English UI; project-stated speed only. cua-driver reliability unknown. | H | M | UNMEASURED | Prefer API or file-level paths first (openpyxl, Graph); computer use as last resort; qualification per app. | E-P4 |
| R-C3 | **URI cannot verify end state independently.** | No harness offers verification (`01` §15). Some outcomes (sent emails, portal submissions) are hard to observe. | M | H | CONFIRMED gap | BUILD a verifier: file/spreadsheet inspection, re-run scripts, read-back via URI's own connectors. Declare "unverifiable" honestly. | E-P6, E-P7 |
| R-C4 | **Harness hides state** (memory, skills, session DB) that shapes behaviour invisibly and does not migrate. | Hermes `memories/`, `skills/`, `state.db`; self-created skills (`01` §1.1). | H | M | CONFIRMED | Ruling deferred (D-C). Options in §E below. | E-P10 |
| R-C5 | **Office automation without Office** (formulas not recalculated; conversions lossy). | Library limits are prior knowledge only (UNKNOWN in this study). | M | M | UNKNOWN | LibreOffice headless or COM, qualified per task. | E-P6 |

## D. Maintenance, lock-in, licensing

| ID | Risk | Evidence | L | I | Status | Mitigation | Falsifier |
|---|---|---|---|---|---|---|---|
| R-M1 | **Upgrade churn breaks adapters.** | Hermes weekly releases; Codex daily alphas; DeepSeek preview "breaking changes"; MCP 2026-07-28 breaking revision. | H | M | CONFIRMED | Version pinning; adapter conformance suite; staged upgrades; rollback. | E-P8 |
| R-M2 | **Protocol immaturity.** ACP is fast-moving; MCP just changed its session model. | `01` §5–6. | M | M | CONFIRMED | Keep a URI-owned internal event model; protocol adapters stay thin. | E-N2 |
| R-M3 | **Lock-in to one harness** via its state or special APIs. | Hermes `/v1/runs` is Hermes-specific. | M | M | MITIGABLE | Provider boundary (`06`); URI-owned state; at least two qualified harnesses before relying on either. | E-P2 on ≥2 harnesses |
| R-M4 | **Licensing.** Claude Agent SDK is under commercial terms; Anthropic document skills are source-available; Phoenix is ELv2; OmniParser weights are mixed. | `01`. | M | M | CONFIRMED | Prefer MIT/Apache candidates; do not vendor source-available skills. | Legal review |
| R-M5 | **Two-product complexity.** URI plus a harness means two update streams, two config systems and two log formats for the user to debug. | Principle 6 (engines invisible) requires URI to absorb this. | H | M | PLAUSIBLE | Engine lifecycle manager; a URI-managed isolated harness profile (never the user's personal Hermes profile). | E-P1 |

## E. The strongest case *against* the wrapper strategy (falsification attempt)

1. **Complexity may exceed URI-native.** For bounded Office tasks (draft, search, locate file, generate a document) URI already works deterministically and fast. Wrapping a harness adds processes, configuration, RAM, and an authority gap (R-A1, R-A2, R-R1, R-R4). *Finding:* true for bounded work, which is why the Edge ladder keeps bounded work URI-native. It is **false for open-ended agentic work** ("make this script work with this spreadsheet", multi-app workflows, computer use). There URI has no loop, browser or computer control, and its orchestrator is its biggest pain point (6,121 lines, duplicated mechanisms). Rebuilding a competitive agent loop, browser, terminal sandbox and computer-use stack in-house is the larger risk.
2. **The authority gap may make harnesses useless for office work,** since most office value involves external effects (send, submit, upload). *Finding:* partially true. At posture P2 the harness *prepares* work (drafts, files, filled forms up to submit) and URI performs or approves the consequential step via its broker. This keeps value while preserving authority. Whether harnesses cooperate with a broker-only external-effect model is UNMEASURED (E-P2, E-P7).
3. **Local hardware may not run a harness-grade model** at useful speed and context (R-R1, R-C1). *Finding:* likely true for fully local harness runs today (UNMEASURED). The strategy survives only if harness runs may use a cloud Capable Brain or a context-capable local model qualifies. This is a **major constraint** on the verdict.
4. **Hidden harness state may violate "URI-owned state survives replacement"** (R-C4). *Finding:* manageable if harness memory and skills are disabled or treated as cache. The ruling is deferred per D-C, and experiment E-P10 measures the capability cost of disabling them.

Conclusion of the falsification attempt: the strategy **is not falsified**, but it holds only under constraints: posture-gated authority, one shared model server, on-demand harness lifecycle, cloud-or-qualified intelligence for harness runs, URI-owned state, and independent verification. The verdict in `00_INDEX.md` reflects this.
