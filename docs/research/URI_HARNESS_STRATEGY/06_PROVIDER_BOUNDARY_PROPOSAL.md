# 06 — Provider Boundary Proposal (NOT FROZEN)

**Purpose:** find the smallest URI-owned abstraction that stops URI depending directly on any one harness.

**Status:** research proposal. Method names are illustrative. The API must not be frozen until experiment E-P2 has exercised at least two real harnesses through it.

## 1. Derivation from observed surfaces

The table maps each needed concept to the surface each harness actually exposes. Evidence is in `01`.

| Needed concept | Hermes (local source) | Codex app-server | ACP (generic) | OpenHands server | OpenCode serve | LangGraph / Agents SDK (fallback) |
|---|---|---|---|---|---|---|
| Capability discovery | `/v1/capabilities`, `/v1/toolsets`, `/v1/skills`, `/v1/models` | `initialize` + config | `initialize` capabilities | server info | `/doc` OpenAPI | in-code |
| Start task | `POST /v1/runs` (`instructions`, `model`, idempotency) | `thread/start` + `turn/start` | `session/new` + `session/prompt` | create conversation | create session + message | `graph.invoke` / `Runner.run` |
| Event stream | `GET /v1/runs/{id}/events` | `turn/*`, `item/*` notifications | `session/update` | WebSocket events | SSE `/event` | stream / callbacks |
| Permission request | `waiting_for_approval` + `POST /v1/runs/{id}/approval` | approval request (accept / decline / acceptForSession) | `session/request_permission` | `WAITING_FOR_CONFIRMATION` | `POST /session/:id/permissions/:pid` | interrupt / `needs_approval` |
| Steer mid-run | `POST /v1/runs/{id}/steer` | `turn/steer` | new prompt | message | message | `Command(resume)` |
| Interrupt / stop | `POST /v1/runs/{id}/stop` | `turn/interrupt` | `session/cancel` | pause | `POST /session/:id/abort` | cancel task |
| Resume | sessions persisted; `/api/sessions` | `thread/resume` / `fork` | `session/load` (agent-dependent) | reload by conversation id | session | checkpointer + thread_id |
| Status / result | `GET /v1/runs/{id}` | turn completed | prompt response `stopReason` | state | session | return value |
| Artifacts | workspace files | workspace files | client fs methods | workspace | workspace | your store |
| Resource usage | run fields incl. tokens and duration (`api_server_runs.py:32`) | usage in notifications (L) | UNKNOWN | UNKNOWN | UNKNOWN | your metering |

**Observations.** Every candidate supports start, events, stop and some form of permission request. Resume, artifacts and usage vary. ACP gives a lowest-common-denominator surface; native adapters add depth.

## 2. Proposed minimum contract

This is an extension of the **External Capability Contract** (`docs/architecture/EXTERNAL_CAPABILITY_CONTRACT.md`, `uri_core/external/*`). It is not a parallel system, and it reuses these parts:

- descriptor / instance-state separation
- qualification bound to an exact version and digest
- the orthogonal lifecycle flags
- the durable `operation_store`
- `outcome_unknown`
- the normalised result
- secret redaction

```text
HarnessProvider  (URI-owned port; one adapter per harness family)

  describe() -> HarnessDescriptor
      id, family, version, digest, transport (acp | http | jsonrpc | in_process),
      supported features {streaming, steer, resume, fork, per_call_approval_scope,
                          sandbox, computer_use, browser, terminal, mcp_client_rev},
      model requirements {wire: chat|responses|anthropic, min_context, tool_calling},
      resource profile (declared; measured values come from qualification)

  health() -> HealthStatus                      # orthogonal: installed, configured, reachable,
                                                # model-endpoint-ok, posture-valid
  start_run(capsule, profile_ref, operation_id) -> RunHandle   # idempotent on operation_id
  events(run) -> stream[HarnessEvent]           # normalized: started, message, tool_call,
                                                # tool_result, file_change, permission_request,
                                                # progress, usage, error, finished
  decide(run, permission_request_id, decision)  # allow_once | deny  (URI never grants "always"
                                                # at the harness level; URI keeps its own rules)
  steer(run, message)            [optional]
  stop(run) -> StopAck                          # must be honored; measured bound
  resume(run_or_session) [optional]
  result(run) -> HarnessResult                  # claimed outcome + artifacts + usage;
                                                # status in {completed_claimed, failed, stopped,
                                                # outcome_unknown}
```

**What is deliberately *not* in the contract:**

- **Memory or knowledge APIs.** URI owns these.
- **Tool registration.** Tools reach a harness through (a) profile toolsets and (b) the URI MCP broker. Harness-specific plugin APIs are not used.
- **"verify".** Verification is URI's job, never the provider's.
- **Model selection logic.** The intelligence broker supplies the endpoint (`07`).

## 3. Companion boundaries

1. **URI MCP Capability Broker** (BUILD). An MCP server run by URI that exposes URI-gated tools to any harness, such as `uri.gmail.create_draft`, `uri.files.publish`, `uri.request_approval` and `uri.lookup_reference`.
   - Every call passes the existing gates: `decision_gates`, `ApprovalGate`, grants and effect class.
   - It must declare its MCP revision. MCP 2026-07-28 is stateless and uses multi-round-trip `input_required` for approvals, which suits this broker. Harness client revisions are UNKNOWN and are tested in E-N2 and E-P2.
   - The development-only `scripts/gemma_worker_mcp.py` shows guardrail patterns. It is a pattern reference, not product code.
2. **Intelligence Broker** (BUILD, thin). A loopback OpenAI-compatible (and optionally Responses) endpoint, or a managed shared model server. See `07`.
3. **Capability Provider boundary.** The existing External Capability Contract, extended with an MCP-client transport (`EXTERNAL_CAPABILITY_CONTRACT.md:11,163` already reserves this). "Annotations do not grant trust" stays.

## 4. Design rules

- **Normalise at the edge.** Harness-specific events map into one URI `HarnessEvent` vocabulary, and nothing above the adapter sees harness types. This is the same rule as "the capability layer carries no provider identity" in `registry_bridge.py`.
- **URI never answers "allow always" to a harness.** Standing permission lives in URI grants, not in harness state. Otherwise authority leaks into harness state and would not survive replacement.
- **Fail closed at the boundary.** If the adapter loses the event stream or cannot deliver a decision, it issues `stop` and records `outcome_unknown`.
- **Idempotent admission.** `operation_id` comes from URI's operation store. Hermes supports run idempotency (local source), and other harnesses are wrapped.
- **Posture is data.** The descriptor carries the qualified posture (P0–P3) with evidence reference and expiry on version change.
- **Portability test.** Consistent with the cross-agent portability rule (`docs/governance/URI_STATE.yaml:454-461`): the boundary is not called portable until two different harness families pass the same conformance suite.

## 5. Open questions (answered by experiments, not by guessing)

- Whether ACP's `session/request_permission` coverage is enough for P3 on any agent. (E-P2)
- Whether per-run toolset restriction exists in Hermes beyond profiles. (E-N1, source reading)
- Whether harness MCP clients speak MCP 2026-07-28 or older revisions. (E-N2)
- The stop-latency bound per harness. (E-P2)
