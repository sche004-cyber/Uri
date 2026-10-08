# URI Resident Intelligence context architecture v1 (cache-aware, security-first)

Status: part of the Runtime v1 freeze (2026-10-06). Evidence: `evidence/uri_engine/context_reuse/` (runs
`ctx_*`, `TABLES_*.md`), section 1 of `URI_ENGINE_STRATA_RESEARCH.md`.

## 1. Why the layout matters on this runtime

Qwen3.6-35B-A3B is a hybrid model (30 Gated-DeltaNet blocks with a recurrent state, 10 full-attention blocks).
llama-server cannot reuse an arbitrary KV prefix of such a model; it reuses *context checkpoints* (recurrent state +
KV at a position) and whole slot states in the host-RAM prompt cache. Checkpoints are created at the start of every
user message (subject to `--checkpoint-min-step` spacing), one ubatch before the end of the prompt, and nowhere
inside a message on the stock server. A prompt that differs from the cached one is resumed from the last checkpoint
*before* the first differing token; everything after that point is recomputed.

Consequence: the logical sections of URI's context must be delivered as separate chat messages, ordered from the
most stable to the most volatile, with a message boundary wherever URI expects content to change independently.

## 2. Logical sections and their classification

| # | section (message) | content (real URI structures) | stability | security-sensitive | independently invalidatable |
|---|---|---|---|---|---|
| 1 | `URI_SYSTEM` (system message, first part) | `DECISION_CONTRACT_SYSTEM_PROMPT` and the seam-specific system prompts (proposer / interpreter / router / answer) | stable for the life of a Core build | yes (defines the contract) | changes only with a Core release |
| 2 | `CAPABILITY_SCHEMA` (system message, second part) | capability summaries, action affordances, index hint from the capability directory (canonical sorted JSON) | session-stable; changes when capabilities are connected/disconnected | yes (what the model may propose) | yes: any change re-renders the system message |
| 3 | `PERMISSION_STATE` (system message, third part) | granted scopes, approval-required actions, denials, permission version | session-stable; changes on grant/revoke | **yes, authority** | yes: a version bump invalidates sections 3-7 |
| 4 | `SESSION_STATE` (first user message, first part) | session facts, attempt history, active pointer, recent conversation summary | changes slowly within a session | partly (claimed approvals must never live here as authority) | yes |
| 5 | `MEMORY_EVIDENCE` (first user message, second part) | retrieved operational memory (recorded history, not learning) | changes when memory retrieval changes | no | with section 4 |
| 6 | `TASK_EVIDENCE` (one or more acknowledged user messages, part k/n) | retrieved documents, tool observations, vision observations | changes per task; large | no (but provenance-tagged, never authority) | per part: a changed part invalidates that part and later ones only |
| 7 | `CURRENT_TURN` (last user message) | the user's words for this turn (verbatim), plus the JSON-only instruction for structured seams | changes every turn | no | always recomputed (26-50 tokens) |

Message shape: `system` = sections 1-3 concatenated; `user` = sections 4-5, `assistant: "Acknowledged."`; for each
TASK_EVIDENCE part: `user` = part, `assistant: "Acknowledged."`; final `user` = section 7. Measured on the
production binary (`ctx_prod_multi_ms512`, 4 evidence parts, 30k tokens): new turn 50 tokens / 0.56 s TTFT;
changed evidence part: only that part and later parts recomputed (6.3k of 30k tokens, 8.5 s instead of 14.3 s);
return to a previous context: 4 tokens / 0.6 s; permission change: everything after section 3 recomputed (correct).

## 3. Invalidation rules (security correctness outranks cache performance)

1. **Authority never comes from the cache.** Permissions, approvals, confirmations, tickets and gates are decided
   by URI Core deterministically on every turn; the model's context only *describes* permission state. A cached
   prefix that was computed under an older `PERMISSION_STATE` must not serve a turn under a newer one.
2. **Permission/authority change = version bump in section 3.** URI renders `PERMISSION_STATE` with a monotonically
   increasing `version` and an `updated` timestamp. Any grant, revoke, approval-policy or denial change bumps the
   version, which changes the system message text, which (by the longest-common-prefix rule) forces recomputation
   of sections 3-7. Measured excess over the logical change: 365-440 tokens (one ubatch), i.e. the cost is correct
   and small. URI must not "optimise" by placing permission state later in the prompt.
3. **Capability set change** (connect/disconnect, affordance change) re-renders section 2 and therefore sections
   2-7. Same mechanism, same cost class.
4. **Session-state change** re-renders the first user message (sections 4-5 and everything after). Facts that
   change every turn must not be placed in section 4; they belong in section 7 or in a TASK_EVIDENCE part.
5. **Evidence change** re-renders only the affected part. URI orders parts from most to least stable (long-lived
   documents first, fresh tool/vision observations last) so that a new observation invalidates one short part.
6. **Return to an earlier context** (another task, then back) is served from the prompt cache; this requires
   `--slot-prompt-similarity 0` (always save the slot state before switching) and a cache large enough for the
   session's live contexts (`--cache-ram 2048` = ~3 cached 30k states plus their checkpoints).
7. **Server restart** empties checkpoints and the prompt cache; the first turn after a restart pays the full
   prefill (4k: 1.4 s, 16k: 6 s, 30k: 14-15 s on the release binary). No state is persisted across restarts, so
   a stale authority state cannot survive a restart either.
8. **Never reuse across users or sessions with different authority.** One resident slot (`-np 1`) serves one URI
   instance; the prompt cache is keyed by exact token prefix, which already includes the permission state, so a
   different authority state can never match a cached prefix. This rule is stated so that a future multi-slot
   deployment does not weaken it.
9. **Model output never becomes a cache key.** Checkpoints are created from prompt tokens only; generated text is
   not part of any reused prefix except the literal "Acknowledged." turns, which are constants.

## 4. Server flags that implement the policy (stock llama.cpp b11425)

- `--ctx-checkpoints 16 --checkpoint-min-step 512`: a checkpoint at every user-message start (parts, turn) and one
  near the end; 16 checkpoints x ~63 MiB recurrent state cover a 32k context with the layout above (7-8 boundaries).
- `--cache-ram 2048 --slot-prompt-similarity 0`: always save the slot state before loading a different prompt;
  keep ~3 full 30k states for return-to-context.
- `-b 2048 -ub 1024`: the ubatch is the reuse granularity for the "near end" checkpoint and the cost unit of an
  invalidation (one ubatch of excess at most, measured 365-999 tokens).
- No custom extension is required: the 7-line fine-checkpoint patch gives sub-message granularity (227-739 excess
  tokens at 30k) but the layout above already bounds the excess to one evidence part; see the freeze record for the
  final verdict on the patch.

## 5. What URI must implement (Operational Intelligence Integration milestone, not this one)

- A Context Bridge that renders the seven sections in this order and emits the message list above, with canonical
  (sorted-key) JSON for sections 2-4 so that unchanged state renders byte-identically.
- Part sizing for TASK_EVIDENCE (target 2-4 parts, most stable first; a part should not exceed ~8k tokens so that
  an invalidation never costs more than ~4 s at 30k).
- The permission-version bump on every authority change (Core-owned).
- The persistent Brain HTTP client (`model_lab/integration/local_brain.py: BrainClient`): 2.5-11 ms client overhead
  instead of ~235 ms per request, one retried request after a server restart.
