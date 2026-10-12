# URI Phase 2: Task Compiler placement (DESIGN ONLY)

Status: DESIGN NOTE, NOT IMPLEMENTED, NOT PLANNED FOR A DATED SLICE. Written 2026-10-07 after the real native
execution path (Codex CLI through `uri_supervisor_bridge` and `uri_supervisor`) was qualified end to end
(`docs/plans/PHASE2C_NATIVE_QUALIFICATION_REPORT.md`). No code in this note exists. No new specialist model is proposed.

## Where it sits

```
User text
  -> Intent Discovery (frozen Phase 1)          : slots from the user's own words, digest-bound confirmation
  -> CONFIRMED intent  (confirmed_digest)        : the meaning URI may act on; revision-bound; corrections rebind
  -> [Task Compiler]                             : translates the confirmed meaning into an executor-ready task package
  -> approved ExecutionTicket (frozen Phase 1)   : server-signed; binds turn/op/capability/argument digest/intent digest
  -> Phase 2B bridge (SupervisedTurnRunner, verify_authority, SupervisorBridge)
  -> Supervisor (Phase 2A: admission, fenced attempt, containment, ledger, reconciliation)
  -> executor (real Codex CLI / Claude Code / future local model)
```

The compiler runs **after** confirmation and **before** approval. That order is the whole point: what the user approves
is the compiled package (its argument digest), and the signed ticket then carries that digest unchanged into the bridge.
The compiler never sees a ticket and never talks to the supervisor.

Today this seat is occupied by `IntentDiscovery.compile` (frozen), which is a deterministic, one-line translation
(`{instruction, expected_file}` -> `external_harness_task` arguments). The Task Compiler is the place where that
translation may become richer (instruction shaping, context packaging, provider-dialect formatting) without touching
authority.

## What it may do

* Optimise and translate: rewrite the instruction for the selected executor's dialect, add bounded context (file names,
  sizes, hashes of resolved inputs), package expected outputs and postconditions, choose formatting.
* Produce the **approval text** the user reads, derived from the compiled package, so the user approves what will run.
* Emit a compile record (inputs, outputs, digests) for the evidence lineage.

## What it MUST NOT do (enforced by placement, not by promise)

| Prohibition | Why the placement enforces it |
|---|---|
| Create authority | It has no signing key and no ticket; authority is created only by the frozen server after explicit approval of the compiled package's digest. |
| Widen permissions | The ticket's capability and the authorization scope (op classes, executor, workspace) are fixed by the frozen server and the bridge, not by compiler output. Compiler output is `arguments` only, inside the public projection. |
| Change confirmed intent | `IntentDiscovery.conflicts(record, proposal)` (frozen) compares the compiled proposal with the confirmed intent; any `input_changed:*` conflict is refused before approval. The compiler must therefore preserve every confirmed slot verbatim (it may only *add* executor-facing packaging in clearly separated fields). |
| Select an unauthorized executor | The executor is the user's explicit reasoning selection, bound at `begin` (Phase 2C, D-C1) and gated by the Phase 1 registry and the bridge's `allowed_executors`. The compiler receives the selection as read-only input to pick a dialect; it cannot emit one. |
| Silently add task objectives | The user approves the compiled instruction's digest. Added objectives would appear in the approval text, and `conflicts` flags any change to confirmed slots. A compiler that appends goals is caught either by the user or by the conflict check. |

## Deterministic vs model-generated fields

| Field | Deterministic (required) | May be model-generated |
|---|---|---|
| `capability_id`, `action` | yes: copied from the confirmed intent | never |
| `confirmed_slots` (`instruction`, `expected_file`, ...) | yes: verbatim from the Confirmed Intent Contract | never |
| `expected_file` / output names | yes: user's words, validated by the bare-safe-name rule | never |
| `postconditions` (file regular non-empty, hashes, command checks) | yes: derived from capability + slots by rules | never |
| `workspace_policy`, permission profile | yes: user selection (OD-3/OD-4), never widened | never |
| `executor_dialect` (Codex / Claude / generic) | yes: from the bound reasoning selection | never |
| `instruction_rendering` (prompt text for the executor) | template by default | yes, as an *additional* rendering whose source slots are quoted verbatim and whose digest is approved by the user |
| `context_pack` (resolved file list, sizes, hashes) | yes: produced by URI's resolver | summary wording only |
| `approval_text` | template by default | yes, if every claim in it is mechanically checkable against the package (same discipline as Phase 2A narration: cite, re-derive, downgrade) |
| `compile_record` digests | yes | never |

Rule of thumb: anything that reaches argv, a path, a permission, a capability, or an executor identity is deterministic.
Model-generated text may only appear inside the instruction body or the human-facing explanation, and both are approved
by digest.

## Minimal integration contract (for the future slice)

* Input: `(ConfirmedIntentRecord, ReasoningSelection, workspace/permission policy)`; output: `arguments` (public
  projection) + `compile_record`. Pure function of its inputs; no IO except reading resolved inputs' metadata.
* The frozen coordinator keeps computing `args_digest = digest(arguments)` and `approval_digest`; nothing in the ticket
  format changes.
* `IntentDiscovery.conflicts` must pass for the compiled proposal, or the turn is refused `REFUSED_UNCONFIRMED_ACTION`
  exactly as today. Any model-generated rendering is stored alongside, never instead of, the verbatim slots.
* The bridge keeps forwarding the instruction on stdin only (never argv); `expected_file` validation stays in
  `verify_authority`.
* Tests for the slice: compiled arguments reproduce byte-for-byte for the same inputs; a compiler that alters a slot is
  refused by `conflicts`; a compiler that emits a provider name is ignored by the bridge; approval text contains the
  compiled instruction's digest.

## Out of scope here

Implementation, prompt design, a specialist compiler model, multi-action packaging, cost estimation. The Phase 1 and
Phase 2 authority chain is sufficient without the compiler; the compiler is an optimisation seat, not a control.
