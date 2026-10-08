# 05 — Proposed URI Target Architecture

**Status:** proposal from research. It is not accepted, not frozen, and not authorised for implementation. It sits beneath ADR-018 (model-centric intelligence and a lightweight deterministic runtime, `URI_Model_Centric_Architecture_Docs/URI_ADR_018_MODEL_CENTRIC_ARCHITECTURE.md`) and is consistent with it. The model proposes; URI authorises, executes or delegates, persists, audits and verifies.

## 1. Architectural finding

The evidence supports outcome **D with A at its centre**: a **URI control plane** that consumes different external systems for different capability classes. Two points qualify this:

- **Bounded work stays URI-native.** It runs on URI's deterministic and Edge paths, never through a harness.
- **Agentic, open-ended work is delegated.** It goes to qualified harnesses as bounded outcomes, and the harness's authority is set per harness by qualification (decision D-B).

Outcome B, where URI becomes plugins inside a harness, is **rejected**. Every ready harness owns context, memory and state in its own store, so URI's identity and state would be trapped (principle 7). Outcome E, where URI rebuilds everything itself, is **rejected for agentic execution**. URI has no browser, computer-use or terminal stack, and its own orchestration is its largest maintenance problem. Outcome C, integrating selected capabilities only, is **included** as the capability-provider layer, but it is not sufficient alone.

## 2. Layer diagram

```
USER
  │  (URI UI: chat, watch-execution view, approvals, results)
  ▼
URI CORE (domain-neutral control plane) ───────────────────────────────────────────┐
  • Identity, accounts, companion continuity        • Permissions, grants, approvals│
  • Turn understanding: RAR / ARN / clarification   • Effect + consequence classes  │
  • Context construction (capsule builder)          • Provenance / evidence ledger  │
  • Durable knowledge, memory, graph                • Result versions / redo        │
  • Intelligence routing (Edge ladder)              • Outcome verifier              │
  • Capability registry + discovery                 • Engine lifecycle manager      │
  • Execution router (native / provider / harness)  • Observability (trace ids)     │
└──────────────┬───────────────────────────┬──────────────────────┬────────────────┘
               │                           │                      │
   DOMAIN PACK (URI Office)                │                      │
   • workflows, vocab, rules               │                      │
   • verifiers, capability exposure        │                      │
   • institutional drafting rules          │                      │
               │                           │                      │
     ┌─────────▼────────┐      ┌───────────▼───────────┐   ┌──────▼──────────────────┐
     │ INTELLIGENCE     │      │ HARNESS PROVIDERS     │   │ CAPABILITY PROVIDERS    │
     │ deterministic    │      │ (agentic execution)   │   │ (bounded, direct)       │
     │ Edge Brain       │◄────►│ ACP adapter (generic) │   │ URI native tools        │
     │ Capable Brain    │ URI  │ Hermes /v1/runs       │   │ External Capability     │
     │ (local / cloud)  │ intel│ OpenCode / Goose /    │   │   Contract (cli/http)   │
     │ one shared model │ broker OpenHands / ...     │   │ MCP servers (Playwright,│
     │ server           │      │ URI-native fallback   │   │  Windows-MCP, M365...)  │
     └──────────────────┘      │ (LangGraph/Agents SDK)│   └─────────────────────────┘
                               └───────────┬───────────┘
                                           │ consequential effects (posture P2)
                                           ▼
                               URI MCP CAPABILITY BROKER ──► URI approval gates ──► effect
```

## 3. URI Core (domain-neutral)

URI Core must contain **no Office assumptions**.

It owns:

- **Identity and relationship.** Users, sessions, devices, persona and continuity. Existing assets: `user_accounts.py`, `auth_session.py`, `principal_context.py`, `soul.md`.
- **Turn understanding.**
  - RAR and ARN, clarification and consequence-aware binding. These produce the objective and the authoritative references for a task.
  - The canonical interaction loop is preserved. The Brain reasons and re-evaluates. URI supplies context, evidence and capability. The user is the final authority.
- **Capsule builder.** Adapts the context builder, budget and trimmer into an **Execution Capsule** (§6).
- **Execution router.** Selects the cheapest qualified path:
  1. Deterministic mechanism.
  2. Qualified Edge capability.
  3. Capable Brain with direct capability providers. This is the canonical bounded path, native tool loop included.
  4. Harness provider, used when iterative, multi-application, exploratory or computer-use execution is needed.

  The router is a policy decision informed by qualification evidence, never a fixed pipeline. This follows the "routes are eligible destinations, not a pipeline" principle in `docs/plans/M33_3_URI_BRAIN_ARCHITECTURE_PROPOSAL.md`.
- **Authority.**
  - Existing mechanisms: grants ∩ mode ∩ scope, effect classification, single-use argument-bound approvals, fail-closed external permission, and harness posture (P0–P3).
  - Authority never depends on the active Brain or the active harness. This is the Brain-agnostic authority constraint in the M33 blueprint.
- **State ownership.** Memory, knowledge, the evidence ledger, operation handles, result versions, approvals and provenance all live in URI stores. Harness state is **cache** unless the D-C ruling decides otherwise.
- **Outcome verifier.** See §8.
- **Engine lifecycle manager.** See §9.

## 4. Domain Pack (URI Office first)

A domain pack is a **declarative-plus-code bundle** that URI Core loads. It declares:

- The capability exposure set, meaning which providers and harness toolsets are relevant.
- Domain vocabulary and aliases for RAR.
- Workflows and recipes, as hints to the Brain rather than rigid scripts. The canonical-loop rule forbids forcing a scripted procedure on the Brain.
- Domain rules, for example `config/institutional_rules.py`.
- Verifiers, for example spreadsheet or document checks.
- Default policies, for example "Gmail: draft only, never send".
- Harness profile templates, meaning which toolsets are enabled.

Modes already work as "filters, not Core variants" (`URI_M22_ARCHITECTURE.md` §16). Domain packs generalise that principle. Future packs (Content, Personal, Health) plug in the same way. **This is the separation URI needs today**: stop adding Office-specific logic to `uri_core/core/*`.

## 5. Intelligence layer and the Edge path

- The intelligence ladder is unchanged: deterministic → Edge → Capable. Placement is decided experimentally, per the user's composable-Brain definition.
- Harnesses are **consumers** of URI-configured intelligence. They do not have their own brains to configure (see `07`).
- **Key rule.** The Edge path must never be bypassed merely because a harness exists. The following never enter a harness:
  - resolving a reference
  - locating a file
  - extracting arguments
  - a qualified direct tool call
  - bounded drafting
- Harness invocation is itself a routing decision with a cost model (startup, RAM, tokens, authority posture). After research, the separation in the brief **remains architecturally sound**, and it is strengthened by the resource findings (R-R1, R-R4).

## 6. Outcome-oriented delegation: the Execution Capsule

URI delegates **bounded outcomes**. It does not micromanage harness actions. The capsule is URI-owned and harness-neutral:

| Field | Content | Source in URI |
|---|---|---|
| `objective` | What the user needs (Brain-formulated, re-evaluated) | canonical loop |
| `authoritative_references` | Resolved entities with binding tier (CONFIRMED / TENTATIVE) | RAR, D5 rule |
| `resources` | Staged files and workspace paths, with read or write scope | `file_store.py` (ADAPT) |
| `context` | Minimal relevant knowledge, preferences, prior evidence | capsule builder |
| `allowed_operations` | Toolsets and effect classes permitted | grants ∩ mode ∩ domain pack ∩ posture |
| `prohibited_operations` | Explicit denials (for example send email, delete, submit) | policy |
| `brokered_tools` | URI MCP broker tools for consequential steps | broker |
| `expected_outcome` | Declarative end state | Brain + domain pack |
| `verification_criteria` | Checks URI will run itself | verifier |
| `budgets` | Time, tokens, cost, steps | usage ceilings |
| `intelligence` | Endpoint and model for the run | intelligence broker |
| `trace` | URI trace id | `uri_v1/evaluation` |

**Evaluation against real harnesses:**
- Hermes `/v1/runs` accepts `instructions` plus `model`, so the capsule maps onto instructions plus a pre-staged workspace plus a profile. Per-run toolsets were not found and are likely profile-level (VERIFIED, local source).
- Codex and ACP `session/prompt` take text plus a working directory.
- OpenHands takes a workspace plus a confirmation policy.

The capsule is therefore delivered as **(rendered instructions + staged workspace + harness profile + brokered MCP tools)**. No harness natively accepts structured verification criteria or prohibited-operation lists as enforced constraints. Enforcement comes from the profile, sandbox and broker, and **verification is URI's job**. The model is viable, with that caveat.

## 7. Harness / runtime layer

- Provider boundary: see `06_PROVIDER_BOUNDARY_PROPOSAL.md`.
- Adapters:
  - **ACP adapter** (generic, many agents).
  - **Native adapters** where richer (Hermes `/v1/runs`, OpenCode `serve`, Codex app-server subject to D-A).
  - A **URI-native fallback** (LangGraph or OpenAI Agents SDK over URI's own tools) if no external harness qualifies.
- **One harness per task run**, isolated by a URI-managed profile and workspace. URI never uses the user's personal harness profile.
- Harness events are normalised into URI evidence records (ADAPT `evidence_adapter.py`).

## 8. Verification (URI's irreducible job)

"Done" from a harness is a **claim**, never evidence. This mirrors the repository's own Evidence Integrity Rules. After a run, URI:

1. Reads the harness event log. Every tool call becomes a provenance record.
2. Runs the capsule's `verification_criteria` with URI's own means:
   - open the workbook and check cells and formulas;
   - re-run the script and check the exit code and output;
   - diff files;
   - read back a draft through Gmail;
   - screenshot or UIA-inspect the application state.
3. Classifies the result as `VERIFIED`, `PARTIALLY_VERIFIED`, `UNVERIFIABLE` or `FAILED`. The status vocabulary mirrors `outcome_unknown` in the External Capability Contract.
4. On `FAILED`, returns evidence to the Brain. The loop continues through the canonical interaction loop, never by a silent retry.

Verifiers are **domain-pack assets**. URI Office ships spreadsheet, document, file and email verifiers first.

## 9. Engine lifecycle management

URI manages harness engines the way M33.1 manages pinned tools:

- **Discover.** Detect installed engines. The user's own installs are adopted only with consent and never modified.
- **Install.** Pinned version, hash-verified, into URI user-space, following the `edge_lifecycle` and M33.1 lockfile precedent. No privileged installs, per the M33.2 §13 amendment.
- **Configure.** Generate a URI-managed profile: intelligence endpoint, `manual` or URI-routed approvals, toolsets per domain pack, memory policy per D-C, and telemetry off.
- **Operate.** Start on demand, health-check, scale to zero, stop.
- **Upgrade.** Staged. Run the conformance and qualification suite; re-derive the posture; roll back on failure. **No silent upgrades** when the upgrade changes privacy, permissions, cost, security or consequential behaviour. The user sees a summary and approves.
- **Replace.** Swap providers without migrating any URI state, because harness state is cache.

## 10. State ownership summary

| State | Owner | Survives harness replacement |
|---|---|---|
| Identity, preferences, persona | URI | Yes |
| Knowledge, memory, facts, graph | URI | Yes |
| Approvals, grants, policies | URI | Yes |
| Evidence, provenance, audit, result versions | URI | Yes |
| Operation handles / task outcomes | URI | Yes |
| Staged workspaces | URI (file store) | Yes |
| In-run harness context and transcript | Harness (mirrored as events into URI) | Mirror only |
| Harness memory / self-created skills | Harness | **Ruling deferred (D-C)** |
| Harness config / profile | Generated by URI | Regenerated |

## 11. Permissions summary

- URI decides **what** a harness may do: the capsule and the profile.
- The harness posture decides **how much** it may do natively (P0–P3, `03` §4).
- Consequential effects at P2 go **only** through the URI MCP broker, which applies the existing approval gates. Approvals stay single-use and argument-fingerprinted.
- Existing product policies carry over unchanged. For example, Gmail send stays absent.
