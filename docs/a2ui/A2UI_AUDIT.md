# URI A2UI — independent audit record

Auditor: Codex CLI 0.158.0, `gpt-6-sol`, reasoning `medium`, read-only, clone `C:\Users\cheta\Development\a2a`
(`core.autocrlf=false`). Codex did not write this code. Codex could not run tests in its sandbox (no temp dir); every
finding was confirmed by Claude (reproduced where stated) and every repair has a regression test.

## Round 1 — candidate `953f91b` (scope `git diff b02ed4f 953f91b`) — **REJECT**

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| F1 | High | both validators accepted `updateDataModel` at `/bound/...`; the hub applied it (read-only data patched; the scheduler gate still refused forged digests) | reproduced (`validate_message` returned no error) | **repaired**: a partial update under `/bound` is refused on both sides (`READ_ONLY_PATH`); bound data is set only by the authority's full model load (`path "/"`); shared fixture cases `data_patch_bound`, `data_root_load_ok`; renderer test |
| F2 | High | `discard` checked `PROPOSED` then cancelled; a concurrent confirm in between would be cancelled | confirmed by reading (`cancel_job` accepts ACTIVE) | **repaired**: every action (surface load, gate, state checks, engine call, surface update) is one critical section under the engine mutex; test `test_r1_discard_and_confirm_are_serialized` |
| F3 | Medium | "schedule an email to remind me about a festival greeting card", "schedule a meeting to discuss festival GIFs" were routed to A2UI | reproduced | **repaired**: the request must ask URI to make the greeting (create/make/generate/…) and must not name another action (email, meeting, remind, send, post, share, …); six new negative cases; the owner's sentence still matches |
| F4 | Medium | template inputs (relative path in a `List` item) replaced the list with a map | confirmed by reading `A2uiSurface.write` | **repaired**: list-aware, `~1`/`~0`-decoding writer used for inputs and partial data updates; no new list slots; relative writes into `/bound` refused; test |
| F5 | Medium | 1,100 nested objects raised `RecursionError` in the Python validator | reproduced | **repaired**: iterative nesting check (32 levels, 200,000 nodes) before any recursive inspection, mirrored in Dart (`TOO_NESTED`); shared fixture `too_nested`; test |

Codex also verified: changed-path inventory against `b02ed4f`; scheduler owner and hash checks; Dart action registry and
image-hash path; fixture label in the live evidence; no `api-token` or token value in committed evidence; protected paths
unchanged.

After repair: Python `tests/a2ui tests/scheduler tests/oi tests/ws` 386 passed / 20 skipped; Flutter 444 passed / 4 skipped;
live check re-run **PASS** (`evidence/live_20261009`).
