# Proposed future enhancement (Lifecycle V3.1): Brain context checkpoint and recovery

Status: PROPOSAL ONLY. Recorded at the owner's direction (2026-10-17). It is not implemented, and it is not part of
URI-RUNTIME-VRAM-R1. It must not become a new persistent-memory implementation, a second memory authority or a
separate task store. URI's existing session/conversation store stays the only source of conversation history.

## Problem (measured in URI-RUNTIME-VRAM-R1)

Changing a resource profile (Vision on/off, context length, MTP) restarts llama-server. llama.cpp b11425 cannot
unload only the vision projector or only the MTP draft. After the restart:

- the conversation is intact, because URI keeps the history;
- the KV / recurrent state is lost. The next turn re-processes the whole prompt: about 10 s per 20K tokens, and
  about 45-49 s for a full 64K context (`evidence/longctx/*`);
- `/slots/0?action=save|restore` (with `--slot-save-path`) works mechanically: 20K tokens saved in 0.3-0.5 s
  (288 MB) and restored in 1.9 s. On this hybrid model, however, the restored state was not reused: cache_n was 0 and
  the prompt was re-processed in full. A slot that contains image tokens cannot be restored into a profile without
  the projector ("Cannot restore media tokens without an mmproj") (`evidence/switch/*`).

## Proposed architecture

1. **Checkpoint = a recorded event, not new memory.** At a profile switch the Brain host writes a small record to
   its existing report/state directory: session id, conversation token count, profile from/to, and the slot file
   path. The conversation text itself stays in URI's session store.
2. **Recovery order after the restart.**
   (a) If the target profile is compatible (same model, same or larger `-c`, no media tokens when the projector is
   off), try slot restore and verify reuse with a 1-token probe (cache_n > 0).
   (b) Otherwise, warm the cache from the session history in the background before the user's next turn, so the user
   does not pay the re-prefill on their turn. This needs a host action and a "warming" UI state.
   (c) Never truncate history to fit a smaller context without the user's confirmation. This is already enforced in
   `runtime_profiles.plan_change`.
3. **Lifecycle integration.** Treat a profile switch as a lifecycle checkpoint: record before/after state, the slot
   file hash and the reuse result in the run evidence, so a reviewer can verify that no context was silently lost.
4. **Investigate first.** Whether checkpoints of the recurrent state (`--ctx-checkpoints`) can be serialised with the
   slot. In b11425 they are in-process only, and a fix may need an upstream change. Under the freeze rules, no local
   patch is allowed.

## Exit criteria for the future milestone

- Measured restore reuse (cache_n) on the hybrid model, or a documented upstream limitation.
- The warm-up hides re-prefill latency from the user's next turn (measured).
- Zero silent context loss across profile switches (tested).
