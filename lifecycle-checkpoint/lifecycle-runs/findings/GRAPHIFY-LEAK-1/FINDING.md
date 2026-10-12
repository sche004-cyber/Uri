# GRAPHIFY-LEAK-1 — another user's memory pointers reach a user's Brain hint (pre-existing, frozen code)

Status: **CONFIRMED** by reproduction on canonical `ce1a90c` (2026-10-11). Not fixed. A fix needs a frozen-file
decision (`uri_core/app/server.py`; possibly `uri_core/core/graphify_index.py`).

## Mechanism

1. `server._GraphifyIndexLoader.start()` builds the process-global Graphify index with
   `memory_store=_memory_store` (server.py ~L895). That store is the install's primary user (`portable_identity`
   user_id, server.py ~L835-861).
2. `_build_user_context(user_id)` gives every other user `GraphifyIndex(records=dict(_graphify_index.records))`
   (server.py ~L557). This copies the primary user's `memory_pointer` records.
3. `decision_engine.build_turn_state_and_directory` (~L1061-1080) puts `relevant_subset(user_text)` records of kind
   `memory_pointer` into the Brain's `capability_index_hint`.

## Reproduction

`test_graphify_pointer_leak.py` here, with `conftest.py` stubbing the absent Google client libraries (import only)
and a throwaway `URI_EXTERNAL_CREDENTIAL_SECRET`. It drives the real loader and `_build_user_context` with temporary
paths. Output (`run_output.txt`):

- `USER_B_VIEW_HAS_PRIMARY_POINTER True {'kind': 'memory_pointer', 'summary': 'preference (user_provided)', ...}`
- `HINT_FOR_USER_B [('memory:<id>', 'preference (user_provided)')]`
- Memory content is not copied (asserted).

## Impact

- **What leaks:** metadata only (memory ID, category, consent), and only on installs with more than one user.
- **Wrong attribution:** user B's Brain is told a memory exists that is not B's.
- **Content:** a lookup by that ID goes to B's own MemoryStore, so it fails; content is not exposed.
- **Severity:** MEDIUM for privacy and correctness in multi-user use; none for a single user.

## Suggested fix (not applied)

The per-user view keeps only the global non-memory scopes and rebuilds the memory scope from that user's own
`memory_store`, with `graphify_index.refresh(view, memory_store=<user's store>, scope="memory")`. Separately, the
memory scope should also be refreshed when memories change; that this never happens is UNCONFIRMED.
