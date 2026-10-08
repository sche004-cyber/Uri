# URI Harness / Runtime Consumption Strategy: Research Index

**Type:** strategic architecture research. **Not** authorisation to implement, install, migrate, integrate or refactor.
**Date:** 2026-09-27.
**Author role:** Claude Code (Architect / Strategic Researcher, AO-4).
**Checkouts inspected:** `_V1` linked worktree (branch `m35-uri-v1-parallel-architecture`, HEAD `d1feaf7`) and the main worktree `C:\Users\cheta\Development\uri-agent` (`master`, HEAD `e8e3b65`, with uncommitted changes). These are one git repository. The older prototype `E:\Chetan\Uri Agent\uri_prototype` named in `hermes_uri_inventory.json` is not accessible on this machine.
**External primary evidence:**
- Local read-only source of Hermes Agent 0.21.2 at `%LOCALAPPDATA%\hermes\hermes-agent` (MIT, commit `284d220`, 2026-09-11).
- Official documentation, repositories and specifications fetched 2026-09-27. URLs are listed in `01`.

**Verdict:** `STRATEGIC_DIRECTION_SUPPORTED_WITH_MAJOR_CONSTRAINTS`

## Primary question and answer

*What should URI own, what should it consume, how should it control consumed systems, and what architecture supports URI Office now and future variants later?*

**Own:**
- the relationship (identity, continuity, knowledge)
- meaning (RAR / ARN / clarification / consequence-aware binding)
- authority (grants, effect classes, approvals, per-harness postures)
- truth (provenance, result versions, **independent outcome verification**)
- economy (Edge ladder, shared model residency, configure-once intelligence brokering)
- stewardship (engine lifecycle)
- domain packs

**Consume:**
- agentic execution, from qualified harnesses behind a URI provider port
- browser, desktop and Office automation, from MCP servers and harness tools
- models, from local servers and cloud providers behind URI's router
- open protocols (ACP, MCP, OpenTelemetry GenAI)

**Control** through:
- outcome-level Execution Capsules
- URI-generated harness profiles
- a URI MCP capability broker for consequential effects
- per-harness authority postures (P0 to P3) earned through qualification
- independent verification

**Architecture:** outcome D (hybrid) with A (URI control plane) at its centre. See `05`.

## User decisions recorded in this investigation

- **D-A.** Codex app-server, Claude Agent SDK and Gemini CLI may be evaluated as execution-harness candidates. Any adoption requires a separate explicit user ruling, because it is in tension with the M31 rule that these development agents must never serve as URI's Brain (`docs/plans/M31_MODEL_BRAIN_UX_PLAN.md:80-82`).
- **D-B.** Authority posture for consequential actions is decided per harness from qualification evidence.
- **D-C.** Treatment of harness-internal memory and self-created skills: the study documents the trade-offs, and the ruling is deferred until experiment E-P10.

## Document map

| # | Document | Deliverable |
|---|---|---|
| 01 | `01_ECOSYSTEM_RESEARCH_REPORT.md` | Ecosystem research (16 areas, primary sources, confidence labels) |
| 02 | `02_CAPABILITY_OWNERSHIP_MATRIX.md` | KEEP / ADAPT / WRAP / REPLACE / BUILD / DEFER per capability |
| 03 | `03_HARNESS_RUNTIME_COMPARISON.md` | Harness comparison (13 candidates) and authority-posture qualification criteria |
| 04 | `04_BRICK_WALL_RISK_REGISTER.md` | Risks and falsification attempt |
| 05 | `05_TARGET_ARCHITECTURE.md` | Proposed target architecture |
| 06 | `06_PROVIDER_BOUNDARY_PROPOSAL.md` | Minimum HarnessProvider boundary (not frozen) |
| 07 | `07_INTELLIGENCE_SHARING_ANALYSIS.md` | Configure-once intelligence sharing |
| 08 | `08_EXPERIMENT_ROADMAP.md` | NO-PC and PC-REQUIRED experiments (none authorised) |
| 09 | `09_MIGRATION_EVOLUTION_STRATEGY.md` | Staged evolution, reuse and retirement, stale-document findings |
| 10 | `10_STRATEGIC_VISION.md` | Concise vision |

## Why "with major constraints"

The wrapper strategy survived a deliberate falsification attempt (`04` §E), but only under these constraints:

1. **Authority is not portable by default.** Hermes approvals are scoped by its own classifier. Its `pre_tool_call` hook fails open on exception. ACP permission requests are issued only when the agent chooses to ask. Consequential effects must go through a URI broker until a harness proves complete, fail-closed interception (posture P3).
2. **Local resources are the binding limit.** Hermes needs a context of at least 64k tokens. The measured 9B residency (5.63 GB weights plus about 1.80 GB KV at 16k context) and the observed 21.7 GB host RAM peak leave uncertain headroom. Fully local harness runs are UNMEASURED and may need a cloud Capable Brain.
3. **No ecosystem verifier exists.** URI must build independent outcome verification. Without it, delegation would reduce URI to trusting "done".
4. **Churn is high.** Weekly or daily harness releases, a breaking MCP revision (2026-07-28) and a supply-chain incident (LiteLLM, March 2026) require pinning, conformance testing and staged upgrades.
5. **Harness state ownership is unresolved** (D-C).
6. **Governance.** Three strong harnesses are URI development agents (D-A).

The strategy is not `NOT_SUPPORTED`. For agentic work, URI-native rebuilding is the larger risk: URI lacks browser, desktop, terminal and agent-loop capability, and `orchestrator.py` is already its main maintenance burden at 6,121 lines. The verdict is also not `REQUIRES_MORE_EVIDENCE`. The *direction*, meaning which layers URI owns and which it consumes, is well supported by evidence gathered now. What remains unmeasured are feasibility parameters, and those are scheduled in `08`.

## Self-review log (Verification-First protocol)

Acceptance criteria are defined in the approved plan (`C:\Users\cheta\.claude\plans\pasted-content-id-205a-role-you-floating-sparrow.md`).

| Check | Result |
|---|---|
| AC1: repository claims cite path and checkout | Pass after repair. Two sub-agent line citations were wrong on direct check: `M33_3_URI_BRAIN_ARCHITECTURE_PROPOSAL.md:229` corrected to `:233,316`, and `URI_STATE.yaml:307-360` corrected to `:454-461`. `ARCHITECTURE.md:46-50` corrected to `:47-51`. |
| AC1: spot-checks confirmed | A2.7 VRAM table lines 51-60; M33.3-R S10 residency rows; `EffectType` at `capabilities/base.py:17-33`; Gmail no-send docstring; Hermes remnants lines; M31 rule lines 80-82; External Capability Contract lines 3, 11, 161, 163. |
| AC2: external claims labelled, provenance separated | Pass. Local-source versus web-doc distinction stated in `01` §0. The web-fetch caveat (summarising fetcher) is recorded. |
| AC3: no invented measurements | Pass. Every number is either quoted from repository reports, a project's self-report (flagged), or marked UNMEASURED / ESTIMATE. The KV extrapolation is explicitly labelled an estimate. |
| AC4: Hermes not privileged | Pass. 13 candidates on the same criteria. Hermes is one of four first qualification candidates and is not the target architecture. |
| AC5: falsification attempted | Pass (`04` §E). |
| AC6: every capability classified with evidence | Pass (`02`, 7 groups). |
| AC7: boundary not frozen | Pass (`06` header and §5). |
| AC8: experiments fully specified, none executed | Pass. 5 NO-PC and 10 PC-REQUIRED experiments, all fields present. |
| AC9: no frozen or active-milestone file touched | Pass. Only new files under `docs/research/URI_HARNESS_STRATEGY/` (verified with `git status`). |
| AC10: stale-document findings recorded, not fixed | Pass (`09` last section). |
| Unverified items affecting the verdict | (a) Hermes per-run toolset scoping: absence seen in one handler only. (b) ACP permission coverage per agent. (c) All resource figures for harness runs. (d) Windows support for OpenHands and DeepSeek Harness. (e) Office library fidelity. None of these changes the *direction*. Items (b) and (c) directly shape the constraints and are the first experiments. |
| Residual risk in method | Web evidence came through a summarising fetcher, and star counts or dates may be imprecise. The Hermes web docs describe v0.21.5, while the local source is 0.21.2, so behaviour may differ slightly between them. |
| Content-safety note | The ecosystem sub-report tripped a harness pattern filter on the string "bypassPermissions", which is a Claude Agent SDK permission-mode name. It was data, not an instruction, and no action was taken. |

## Governance note

- These files are **uncommitted research artefacts**. They do not register a milestone or an integration event, and they do not edit `URI_STATE.yaml`. Registration or commit happens only on user direction.
- `graphify update .` was not run. These are documentation-only changes, and CLAUDE.md requires a graph update after *code* changes. Run it if the research docs should be indexed.
