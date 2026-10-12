# GRAPHIFY-LEAK-1 — plan and acceptance criteria

Owner decision D12 (2026-10-11): fix before W2, as its own milestone; frozen exception for `uri_core/app/server.py`
(and `uri_core/core/graphify_index.py` only if needed — not needed, unchanged). Baseline: canonical `e07b71c6`.

## Problem (confirmed by reproduction on ce1a90c)

Every signed-in user's Graphify view was `GraphifyIndex(records=dict(_graphify_index.records))`: a copy of the shared
index, whose `memory:` pointers were built from the install's primary user's memory store. Another user's Brain hint
(`decision_engine` → `relevant_subset`) could therefore name the primary user's memories (ID, category, consent;
never content). Separately, no view was ever refreshed when memories changed.

## Change

`server._MemoryScopedGraphifyView(GraphifyIndex)`: copies every non-memory record of the shared index, drops all
`memory:` records, and rebuilds the memory scope from one store (via `graphify_index.refresh(scope="memory")`) on every
`get`, `list_all` and `relevant_subset`.
- Signed-in user: store = that user's own `MemoryStore`.
- No-login legacy view (`_orchestrator`): store = the current `_memory_store` (callable, so it follows replacement).
- The shared `_graphify_index` (persisted, used for `catalogue_ready`) is unchanged.

## Acceptance criteria

- AC1 A signed-in user's view, `get`, `list_all`, `relevant_subset` and Brain Turn State never contain another
  store's memory pointer. (Fails on e07b71c6.)
- AC2 A user's own memory added after the view was built appears; a deleted one disappears. No memory content is
  ever copied into a record.
- AC3 Two users never see each other's pointers.
- AC4 Reading a view never changes the shared index.
- AC5 Non-memory records (capabilities, skills, workflows, services) still reach each view; the per-user
  capability/service refresh keeps working.
- AC6 The no-login view shows its own store's pointers, stays current, and follows a replaced `_memory_store`.
- AC7 A failing memory store gives no memory pointers and no exception.
- AC8 Gates: no new failures against the baseline; only `uri_core/app/server.py`, `tests/graphify/**`,
  `docs/graphify/**` change.

Tests: `tests/graphify/test_graphify_leak_1.py` (11 tests; 8 fail on e07b71c6, including AC1 and the Brain-hint
case). `tests/graphify/conftest.py` gives import-only placeholders for the Google client packages only where they
are not installed, and sets a throwaway credential secret only if none is set.

## Not verified here

- Root-level server tests (`test_m33_1_batch2_yt_dlp.py`, `test_m33_1_batch3_github_package.py`) need network and
  package staging: 3 + 2 failures, identical on baseline and candidate (run with the placeholders). Not in the gates.
- Cost: each lookup re-reads the user's memory file (`MemoryStore.list_all` reads JSON). Small files; one read per
  Brain turn.

## Review round 1 repairs (findings R1-01, R1-02)

Corrections to the text above, kept for history:

- R1-02 (the "Change" section is superseded): the memory scope was rebuilt with `refresh(scope="memory")`, which
  deletes and re-adds keys of the view's `records` in place on every lookup. One view serves concurrent `/ask`
  requests (thread pool), so lookups and the capability refresh raced (KeyError, "dictionary changed size during
  iteration", an emptied hint). Now `_sync_memory` builds the memory pointers with `build_index(memory_store=...)`,
  merges them with the non-memory records in a new dict and assigns `records` once; each lookup holds the view's
  `lock` (RLock) for sync plus read, and `refresh_user_external_lifecycle` holds the same lock while it refreshes the
  view's capability/service records. `_sync_memory` never raises (on failure the view keeps its last records).
- R1-01 (the conftest sentence in "Tests" is superseded): the placeholders were installed at collection and the
  server stayed imported with placeholder bindings, so later tests in the same run (e.g. `pytest tests/graphify
  tests/test_m31_model_brain_ux.py`) imported a server bound to MagicMock modules; the credential secret stayed set.
  Now the module-scoped `graphify_server` fixture installs the placeholders and the secret only while a
  tests/graphify module runs; on teardown it removes every module imported in that window that is a placeholder,
  part of `uri_core`, or bound a placeholder (also from its parent package).

- AC9 Concurrent lookups and the capability refresh never break a running lookup; a lookup never raises.
- AC10 Nothing from the tests/graphify placeholders (modules, bindings, secret) reaches a later test in the run.

Regression tests: `tests/graphify/test_graphify_leak_1_repair.py` (4 tests, all fail on 9ae7c60c, pass after). The
races are made deterministic by a record whose summary read starts the competing call in another thread and waits
until it has finished or is waiting for the view's lock.
