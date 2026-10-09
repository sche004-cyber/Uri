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

## Round 2 — candidate `29692c0` — **ACCEPT WITH FINDINGS**

F1, F2, F4, F5 **FIXED** (F2: the action path holds the engine RLock through load, gate, engine call and save; it never
waits for a harness run; Codex notes that other tick bookkeeping is outside the lock, which is not claimed otherwise).
F3 PARTIAL → N1.

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| N1 | Medium | "Cancel my schedule to create a festival GIF …" produced a NEW proposal; "… and send it to me for approval" stayed conversational | reproduced both | **repaired**: change/cancel verbs (cancel, stop, pause, delete, edit, change, reschedule, …) never produce a proposal; approval-delivery phrases ("bring/send/show it to me", "for approval/review") are removed before the competing-action check; tests for both directions |
| N2 | Medium | string limits counted code points in Python and UTF-16 units in Dart (3,000 emoji passed Python, failed Dart) | confirmed | **repaired**: Python counts UTF-16 code units everywhere a limit applies (`u16`); shared fixture cases `emoji_text_utf16_limit` (2,001 emoji → BAD_TEXT) and `emoji_text_under_limit` (2,000 → valid) agree on both sides (44 cases) |

## Round 3 — candidate `a85d893` (scope `git diff 29692c0 a85d893`) — **REJECT**

N1 **FIXED** (change/cancel requests return no handoff; approval phrasing and the owner's sentence match; no catastrophic
backtracking within the 2,000-character cap). N2 PARTIAL → R3-1.

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| R3-1 | High | the new UTF-16 length helper raised `UnicodeEncodeError` on an unpaired surrogate (a valid JSON escape in hostile text) instead of returning a code | reproduced; the same crash existed in `validate_data` (UTF-8 size) and in `canonical()` (surface digest) | **repaired**: `surrogatepass` in all three (a lone surrogate counts as one UTF-16 unit, like Dart; UTF-8 size as 3 bytes, like the Dart counter); `test_r3_lone_surrogates_never_crash_the_validator`; shared fixture `lone_surrogate_text` (fixtures now ASCII-escaped so the case reaches Dart intact); 45 shared cases agree |

## Round 4 — candidate `186fc31` (scope `git diff a85d893 186fc31`) — **REJECT**

R3-1 PARTIAL: validation no longer crashed, but an accepted lone surrogate still broke persistence and auditing.

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| R4-1 | High | a lone surrogate in a request `assumptions` string: the PROPOSED job was committed, then the surface save failed in SQLite → 500 and an orphaned proposal | confirmed by reading (job before surface) and Codex's SQLite reproduction | **repaired at the root**: unpaired surrogates are refused as text everywhere on both sides (`lone_surrogate` / `hasLoneSurrogate`: definitions, data, options, pointers, context values, request assumptions); `propose_from_request` runs under the engine mutex and withdraws the job if its surface cannot be built or stored (`test_r4_proposal_is_withdrawn_if_its_surface_cannot_be_saved`) |
| R4-2 | Medium | a hostile `name`/`sourceComponentId` reached the audit event and its UTF-8 hashing → 500 | confirmed by reading | **repaired**: identifiers must be strings ≤ 128 without lone surrogates before any lookup or audit (`BAD_ACTION_MESSAGE`); hostile context values are refused by the gate and only the result code is audited; hash chain verified in the test |
| R4-3 | Medium | Python and Dart sized lone surrogates differently in the 64 KiB data limit | confirmed | **repaired by R4-1** (no lone surrogate is accepted on either side); shared cases `lone_surrogate_text`, `lone_surrogate_data` (BAD_TEXT) and `paired_surrogates_ok` (valid, decoded like the wire); 47 shared cases agree |

After repair: Python 399 passed / 20 skipped (a2ui + scheduler + OI + WS); Flutter 444 passed / 4 skipped; analyze: the 2
pre-existing infos; live check re-run PASS.

## Round 5 — candidate `561d771` (scope `git diff 186fc31 561d771`) — **ACCEPT WITH FINDINGS**

R4-2 FIXED; R4-3 FIXED for values; R4-1 PARTIAL (the compensating cancel is a second transaction) → R5-2. Codex re-confirmed
the whole scope against the owner principles (presentation only, restricted registry, authority re-checks digest, button,
bound values, owner and hashes; ordinary requests stay conversational; only recorded hooks and exact-path guards changed).

| # | Codex severity | finding | classification (rule: repair unless the governing contract documents it) | disposition |
|---|---|---|---|---|
| R5-1 | Medium | data-model **keys** were not checked (a lone-surrogate key passed both validators and broke SQLite) | violates A-AC2 | **repaired**: keys must be strings ≤ 256 UTF-16 units without lone surrogates on both sides (`BAD_KEY`); shared case `lone_surrogate_key` (48 cases agree) |
| R5-2 | Medium | an engine transition and the following surface write are separate transactions; a storage failure between them leaves the surface behind the engine (revise could orphan the new proposal and cancel the old one) | violates A-AC5 (persistence) — not a documented limitation | **repaired**: (a) revise stores the new surface BEFORE withdrawing the superseded proposal; a failed save withdraws the new proposal so the shown one stays valid; (b) every load of a stored surface reconciles with the authority: a proposal surface whose job is ACTIVE/PAUSED becomes the status surface, one whose job is CANCELLED/unknown is closed; (c) review surfaces were already reconciled (`sync_reviews`) and the calendar surface is rebuilt from the records on open. Tests `test_r5_surfaces_follow_the_authority_after_a_failed_surface_save`, `test_r5_failed_revise_save_keeps_the_shown_proposal_valid`. Residual: if both the save and the compensating cancel fail (storage down), the extra proposal stays PROPOSED — inert by design (a PROPOSED job never runs) and visible in the Scheduler view |
