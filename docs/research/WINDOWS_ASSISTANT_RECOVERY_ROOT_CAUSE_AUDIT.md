# Windows assistant recovery — root-cause audit

Stage 1, 2026-10-14. Source: accepted Assist descendant
`e0b5c298d046622d52550f1455ab649070165602`, tree
`2f2cf27a878fc0c4f1db401a811ee2a9e0aa41bb`. Accepted Office
`aa232e361671678ad323217cd6a705e7a00c9c99` remains immutable.
This document records investigation, not repair or release acceptance.

Evidence is outside the candidate at
`C:\Users\cheta\Development\uri-windows-assistant-recovery-20261014\evidence`.
Prior live evidence remains in `uri-windows-live-qualification-20261013`.

## Observed failure chain

The prior real main Flutter run used the non-opted-in HTTP profile. Its
candidate Core called the canonical decision engine, which returned invalid
JSON, then used the legacy orchestrator. All six preserved canonical telemetry
records say `engine_failure:INVALID_PROPOSAL:malformed_json`,
`canonical_execution_attempted: false`, and `fallback_used: true`.
The generic legacy workflow subsequently selected `prepare_output`, which
correctly refused an unsupported capability. That refusal is a downstream
symptom, not proof that removing the planner guard would fix conversation.

`uri_core/core/decision_engine.py::propose_decision` requests a 500-token
completion and parses `response.content` as JSON. The generic OpenAI-compatible
provider sends ordinary chat parameters without a JSON response constraint or
the OI thinking policy. The recorded malformed response is established; its
exact cause (truncation, reasoning/content behavior, or another output defect)
is not established because the raw output was not retained in those traces.
Do not present a hypothesis as a reproduced model diagnosis.

## Intended existing composition

`docs/working_system/WS_BLUEPRINT.md` and `WS_HARDENING_PLAN.md` define the
Working System profile. `uri_ui/lib/main.dart` selects it when
`URI_CLIENT_MANIFEST` names an installation with
`control/ui-integrated-profile.json`. Actual `WorkingSystemRoot` connects through
`WorkerIntegratedRuntime` to the integrated stdio worker. OI has an existing
language-only answer channel with bounded session history; state-changing turns
go through `PairedCoreGateway` to paired Core discovery, confirmation, approval
and settlement. Its Runtime v1 provider uses constrained JSON and the accepted
FAST policy. This is the first approach to qualify before proposing a parallel
assistant or patching frozen HTTP execution.

Existing conversation history is not proof of durable-memory retrieval. The
worker has a deterministic `memory_list` command; prior direct Brain context
recall passed while Core contextual recall failed. Each must be separately
qualified through the intended UI. Merely mounting Working System proves none
of its live journeys yet.

## Materialization blocker

The documented materializer preserves a real historical Git HEAD
`e8e3b65259c45fc823addc3ef8969425a265bd1b` plus accepted overlay
`759d0d4e4069ddb490e6ce52ac58bf86ef0248f0`; this is deliberate, reproducible
materialization, not identity falsification. The frozen identity check cannot
run directly at the current candidate branch tip.

Deterministic Git-blob comparison proves the existing materializer would restore:

| Path | Materialized SHA-256 | Required canonical SHA-256 |
|---|---|---|
| `uri_core/app/server.py` | `7b455f05ae97f7f6cbc944ba5c93998ea64063402568ea9750b70356db4f366b` | `59cfde59c709fa7f83df84e957f5962701276afce54cb196541134a9a43cf4f8` |
| `uri_core/tools/fetch_url.py` | `f097006211c2b2c4abc9a4aaf7aa64063ee00a55030559caf857724ce2af9bff` | `404e60921c207753868589b8a16f409ee80f35a01b0a33e8400d8780d93139e8` |

The intended paired server does not expose the legacy HTTP server. That fact
does not authorize omitting approved security protections from the shipped
runtime tree. The existing active, owner-approved source checker passes on e0,
recognizing exactly D12/D2/D33. Its accepted activation remains valid despite
its stale proposal docstring. A source-only PASS does not validate historical
materialized output or authorize new exceptions there.

## Edge and Assist

The classic Edge inventory is empty and deployment-owned. User settings cannot
register an unknown runtime/model. The routing policy exists as a pure function;
this is not evidence of an operational Edge inference bridge in Working System.
OI's deterministic lightweight triage is a different facility. Do not relabel it
as live second-model Edge execution or start a second resident model to conceal
the gap. A final profile must distinguish available routing from unimplemented
or unqualified deployment integration.

The integrated worker creates the real Assist command bridge, but production
`default_adapters()` deliberately returns unavailable browser, Windows UIA and
screen adapters. The browser snapshot/probe algorithm and accepted visible-text
repair are not a worker transport. A real capture adapter is new integration
work and needs target binding, grants, immediate revoke, redaction and live
security proof; no test replay or custom fake adapter can replace it.

## Office contract finding

Using the installed `jsonschema` validator against the original advertised
new-workbook schema, an operation with `op=add_sheet` and `name=null` satisfies
that schema. Passing the same operation to the real deterministic validator
raises `BAD_SHEET_NAME`. The original live request also records this refusal
and zero proposals. This is a concrete contract-permissiveness defect with safe
runtime containment, not an unsafe write or a >500-changes regression.

A future repair should compare an operation-specific constrained schema with
other minimal contract approaches using the actual pinned backend. Do not guess
a missing name, relax validation, automatically apply a model retry, or reopen
unrelated accepted Office behavior. No Office implementation was changed in
this investigation.

## Boundaries and actual execution

Current normal GPU fit is CONTENDED (margin −1,252.9 MiB). No Brain, server,
worker or UI was started, no process was terminated, and no new override used.
Original frozen ZIP and source protected blobs pass verification. No new
Windows end-to-end or performance result is claimed.

The necessary runtime restoration crosses the owner's explicit prohibition on
unapproved frozen changes. An external exact two-file transition patch is
prepared, not applied. It copies only the already-approved canonical blobs and
requires independently audited, materialized-tree provenance validation before
use. The checkpoint and historical HEAD remain unchanged. Stop here for owner
authorization; do not weaken security or choose the failed HTTP substitute.
