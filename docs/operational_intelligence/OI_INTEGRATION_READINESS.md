# OI integration readiness, independent audit record and controlled-integration procedure

## 1. Readiness verdict

| Level | Verdict |
|---|---|
| Development candidate (this branch) | see §2 for the independent verdict |
| Integration into canonical development | **NOT READY**: needs the owner decisions in §4 and a combined regression gate with a defined OI scope |
| Production | **NOT READY / NOT AUTHORIZED**: no cutover, no service, no startup entry; requires separate owner authorization |

## 2. Independent audit (Codex CLI, model `gpt-6-sol`, effort `medium`, read-only disposable clone `C:\Users\cheta\Development\oia`)

Codex output is a claim; every finding below was checked against the source before repair.

| Round | Commit | Verdict | Findings |
|---|---|---|---|
| 1 | `467e4e5` | **REJECT** | High: crash between approval and recording could restart a step; SKIPPED satisfied dependencies; attach skipped artifact verification + size/mtime-only cache; negation check limited to two words (counter-example "Do not under any circumstances email Ravi."). Medium: unknown finish reasons / Core codes could read as success; SSE disconnect left inference running; quota pause emitted no provider choice. Low: claim guard is post-response. A10: docs overclaimed on those points; readiness doc missing |
| repair | `5aad403`, `1953362` | — | all eight repaired with regression tests (`tests/oi/test_oi_audit_r1_regressions.py`); my own SSE fix was itself flaky (sync generator blocked in `queue.get`) and was replaced by an async disconnect-polling stream, 3 consecutive green suite runs |
| 2 | `9265d00` | **REJECT** | H1/H3/A10 partially fixed; H2, H4, M1-M3, L1 verified fixed. New: concurrent `advance()` could dispatch twice (High); partial-word span match "activate account" in "deactivate account" (High); approval path bypass via `decide`+`record_step` and no startup recovery (High); `status()` READY without artifact verification (High); Core CONVERSATION on an action step counted as success (Medium) |
| repair | `aea8f8f` | — | repairs with tests (`tests/oi/test_oi_audit_r2_regressions.py`); doc claims narrowed |
| 3 | `aea8f8f` | **REJECT** | R2-1, R2-5 verified fixed; R2-2/3/4 partially: public `decide()` still usable on plan steps (High); READY verification cached per pid forever (High); punctuation/hyphen span boundary "-activate account" in "de-activate account" (High); recovery not coordinated with a live owner (Medium); `confirm_step` unclaimed and non-outcome replies after approval undefined (Medium); doc overclaims on these |
| repair | see git log after `aea8f8f` | — | repairs with tests (`tests/oi/test_oi_audit_r3_regressions.py`); claims limited to what the tests exercise (threads, not processes; simulated, not real crashes) |
| 4 | `b6c345f` | **REJECT** | confirm()->decide() on a plan step's new turn bypassed decide_step (High); curly apostrophe / Unicode hyphen defeated negation and boundaries (High); writers without ledger ownership (Medium); fail-open task scan (Medium); quota pause after approval undocumented (Low) |
| repair | `738a9af` | — | single-turn allowlist, Unicode folding, one writer process per ledger (real second-process test) |
| 5 | `738a9af` | **REJECT** | ownership, scan removal, quota documentation verified fixed. Remaining: a plan step's confirmation payload spliced under a registered single-turn id (High); U+201B / U+2015 not folded (High); in-memory registry lost on restart (Medium); unbounded registry (Low) |
| repair | see git log after `738a9af` | — | registry binds a digest of the whole issued envelope, single use, bounded 256, restart fails closed (documented); folding by Unicode category Pd / Pi / Pf / Zs (`test_oi_audit_r5_regressions.py`) |
| 6 | see §2.1 | see §2.1 | see §2.1 |

### 2.1 Round 6

Recorded after the run (if empty, round 6 did not complete).

## 3. What was verified, by whom

| Claim | Verified by |
|---|---|
| Real Core + Runtime v1 loop, Suite P, benchmarks, cancellation, restart | this session, live runs (evidence JSON) |
| Accepted regression chain gates | this session, chain1 + control chain2 |
| Source-level authority, recovery, honesty | this session's self-review + Codex rounds |
| Physical acceptance, production behaviour, long soak of the OI layer | **not verified** |

## 4. Owner decisions needed before integration

1. Offer the Runtime v1 row (`server_local_model`, `llamacpp-runtime-v1`, `qwen3.6-35b-a3b-ud-iq3_s`) in a server
   profile (Phase 2 composition reserves server-local-model rows for the owner).
2. OI-SEC-1: add `--api-key` to the Runtime v1 flags (Runtime v1 amendment) or accept the local exposure.
3. Gate scope: authorize adding the OI paths (`uri_operational_intelligence/`, `tests/oi/`, `model_lab/` integration
   copies) to the accepted scope guards (`tests/phase2a/test_frozen_core.py` allowlist and the chain's
   `phase1-scope` check), or keep OI in a separately gated location.
4. Where the dev SSE surface ends: production events should travel over the paired client channel.

## 5. Controlled-integration procedure (proposed; not executed)

1. Freeze the OI candidate: tag the reviewed commit, archive `docs/operational_intelligence/` and the evidence JSON.
2. Rebase-free merge preparation: create `integration/oi-candidate` from the canonical branch tip; `git merge --no-ff
   phase/operational-intelligence` (adds only new paths + one `.gitignore` line; expect no conflicts).
3. Materialize the combined runtime (`scripts/oi_materialize_test_runtime.py`, gate mode) and run the accepted chain
   with the owner-approved OI scope: phase2, authority, phase1-full, phase1-scope, residue, flutter, bridge, native as
   available; plus `tests/oi` (unit) and `URI_OI_LIVE=1 tests/oi` (live) with Runtime v1 READY.
4. Re-run `bench/suite_p.py` (≥ 3 runs) and `bench/reasoning.py` with residency sampling; reject the run if the
   server's dedicated VRAM dropped ≥ 300 MiB during it.
5. Independent audit of the merge commit (Codex, read-only).
6. Integration receipt document: commit ids, gate results, audit verdict, deviations.
7. UI session consumes the event contract; any change to it is versioned (`uri.oi.event.v2`).
8. Production activation: separate owner authorization (RED).

## 6. Development acceptance vs production readiness

Development acceptance means: the code exists, tests and live runs pass in an isolated tree, and an independent
reviewer found no blocking defect. It says nothing about: physical acceptance gates (PA-1..PA-13 of Phase 2), a
production server profile, credentials, the live PC's legacy server, multi-day stability of the OI layer, or real
user workloads. None of those were exercised.
