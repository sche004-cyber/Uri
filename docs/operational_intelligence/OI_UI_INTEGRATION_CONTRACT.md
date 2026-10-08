# OI ↔ UI integration contract (proposal, v1)

Status: **proposed** (Operational Intelligence development candidate, branch `phase/operational-intelligence`).
Audience: the parallel UI / Living Companion session. This document is the only coordination surface; the OI session
does not edit the UI worktree, and the UI must not depend on OI internals.

The UI can build against this contract today with the simulator (no GPU, no model):

```
GET /oi/v1/simulate/{answer|reasoning|approval|error|plan|quota}
```

or in-process: `uri_operational_intelligence.events.simulate(scenario)`.

## 1. Transport

Development server: `python -m uri_operational_intelligence.server --port 18471` (loopback only).

| Endpoint | Purpose |
|---|---|
| `GET /oi/v1/brain/status` | Brain readiness and performance health (never starts the runtime) |
| `POST /oi/v1/turns` | body `{"text", "session_id", "depth"?, "turn_id"?}`; response is `text/event-stream`, one JSON event per `data:` line |
| `POST /oi/v1/turns/{turn_id}/cancel` | cancel a running turn; the stream ends with `answer.done` status `CANCELLED` |
| `GET /oi/v1/simulate/{scenario}` | fixed event sequences for UI development |

Authentication: `Authorization: Bearer <token>`; the dev server writes a fresh token to
`work/oi/state/oi_server.token` at start. No CORS headers are sent (browser pages cannot call it).

`depth`: `auto` (policy), `fast`, `normal`, `deep`. `deep` is never run locally; it becomes an escalation offer.

This HTTP surface is a development harness. In the integrated product, the same events would travel over the paired
client channel; the event schema below is the contract, not the endpoint paths.

## 2. Event envelope

```json
{"schema": "uri.oi.event.v1", "seq": 7, "t": 1791459000.123, "turn_id": "…", "type": "answer.delta", "data": {"text": "…"}}
```

`seq` is strictly increasing per stream. Unknown `type` values must be ignored. The UI must never infer that an
action happened from answer text: only `core.result` and `task.step` carry action outcomes.

## 3. Event types

| type | data | UI meaning |
|---|---|---|
| `brain.status` | `state` (READY, LOADING, STARTING, STOPPED, DEGRADED, FOREIGN_INSTANCE, IDENTITY_MISMATCH, ARTIFACT_MISSING, FAILED), `model_id`, `owned`, `detail`, `identity`, `performance?` | Brain indicator. DEGRADED carries `performance.recovery_options` (`restart_brain`, `close_gpu_heavy_apps`, `continue_slow`) |
| `turn.started` | `text_chars`, `depth` | user turn accepted |
| `turn.routed` | `route` (`answer`, `core`, `plan`, `harness_choice`, `escalation_offer`), `triage`, `tier` {`tier` FAST/NORMAL/ESCALATE, `selected_by` policy/user/core_seam, `reason`}, `rerouted_from?` | show reasoning mode chip ("Fast" / "Thinking") |
| `companion.state` | `state`: `idle`, `listening`, `thinking`, `speaking`, `waiting_user`, `error` | Living Companion animation state (`listening` is set by the voice layer, not by OI) |
| `thinking.progress` | `chars` | NORMAL tier only: reasoning progress counter. Reasoning text is not sent |
| `answer.delta` | `text` | append to the visible answer |
| `answer.done` | `status` (COMPLETE, INCOMPLETE_LENGTH, CANCELLED, TIMEOUT_FIRST_TOKEN, STALLED, DEADLINE_EXCEEDED, INTERRUPTED, UNREACHABLE, HTTP_ERROR, PROTOCOL_ERROR), `complete`, `escalation_candidate`, `flags` (e.g. `UNVERIFIED_ACTION_CLAIM`), `metrics` | end of answer; mark incomplete answers visibly |
| `core.result` | `state`, `code`, `message`, `needs` (`confirmation`, `clarification`, `approval`, `none`), `intent?`, `confirmation?`, `clarification?` | Core's authoritative reply; render Core's message and the needed control |
| `approval.required` | `core_turn_id`, `capability_id`, `arguments`, `approval_digest`, `effect`, `reversible` | show the approval card. Only a button press approves; typed text never does |
| `plan.proposed` | `task_id`, `goal`, `steps[]` {id, kind answer/action/harness/ask_user, description, capability, source_span, depends_on, unusable_reason?}, `clarifications[]`, `problems[]`, `downgraded[]` | plan review card; nothing runs before the user approves the plan |
| `task.step` | `task_id`, `step_id`, `state`, `core_code?` | progress of a multi-step task |
| `harness.choice_required` | `options[]` {provider, display, usable, why_not, qualification, auth, quota, source}, `recommendation`, `recommendation_reason`, `requires_user_choice`, `excluded[]` | provider picker. A recommendation is never a selection |
| `escalation.offer` | `reason`, `options` (as `harness.choice_required`) | "needs a stronger tool" offer |
| `error` | `code`, `message`, `recoverable`, `recovery_options[]` (`start_brain`, `retry`, `choose_other_source`, `keep_partial`, `rephrase`, `escalate`) | error card with actions |
| `turn.finished` | `status` (`ok`, `needs_user`, `awaiting_plan_approval`, `needs_harness_choice`, `cancelled`, `incomplete`, `error`), `route`, `total_s` | end of stream (a final `companion.state` follows) |

## 4. Companion state mapping

| OI moment | `companion.state` |
|---|---|
| turn accepted, before first visible text | `thinking` |
| first `answer.delta` | `speaking` |
| `needs_user`, plan or harness choice pending | `waiting_user` |
| `error` status | `error` |
| otherwise after `turn.finished` | `idle` |

## 5. Guarantees and non-guarantees

- The UI receives the selected model and the tier actually used (`turn.routed`), and Brain health (`brain.status`).
- No provider switch happens silently: a quota stop arrives as `core.result` `WAITING_FOR_MODEL` plus
  `harness.choice_required` with the exhausted provider in `excluded`.
- `answer.delta` text is language only. It never confirms an action. A reply that claims an action without Core
  executing one is flagged `UNVERIFIED_ACTION_CLAIM` and corrected in-stream.
- Not yet provided: voice (`listening` comes from the voice layer), images, multi-turn history persistence in the dev
  server (history is passed by the caller), and production transport.
