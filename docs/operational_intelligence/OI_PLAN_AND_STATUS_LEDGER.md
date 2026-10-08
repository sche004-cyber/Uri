# Operational Intelligence: plan, acceptance criteria and implementation-status ledger

Branch `phase/operational-intelligence`, worktree `C:\Users\cheta\Development\uri-operational-intelligence`,
base `037229c1fc04eadc6a2e42e92e6ef0d12520d3fe`. Status classes: 1 researched/proposed, 2 configured/prototyped,
3 implemented, 4 tested/qualified (development), 5 independently accepted, 6 integrated, 7 production-active.
Nothing in this phase is class 6 or 7.

## 1. Plan (as executed)

1. Discovery: verify baseline; map worktrees and owners; read Core seams (`create_app(composition)`,
   `PairedCoordinator`, `BrainProposer`, `TurnRunner`), Phase 2 composition/qualification, Runtime v1 freeze record.
2. Runtime integration: identity, start-or-attach, streaming, cancellation, deadlines, errors, recovery.
3. Core integration through the existing composition seam; prove it on the real paired Core.
4. Reasoning policy (freeze §4) + deterministic triage + answer channel with guards.
5. Orchestration: Core relay, plans, task ledger, harness choice, UI events, dev SSE server.
6. Benchmarks: task success vs throughput, MTP vs no MTP, routing, latency; failure/recovery tests.
7. Self-audit, accepted regression gates, independent Codex audit, repair, re-audit.

## 2. Acceptance criteria and verdicts

| # | Criterion (mandate §10) | Verdict | Evidence |
|---|---|---|---|
| AC1 | URI communicates with Runtime v1 through the intended architecture | **MET (development)** | `oi_composition` via Core's `create_app(composition=...)`; live 8/8 + Suite P 12/12 on the real paired Core (`OI_BENCHMARKS.md` §2) |
| AC2 | Real inference works without the legacy server | **MET** | all live runs used Runtime v1 on 18470; legacy server on 8000 never contacted |
| AC3 | Model identity and readiness verified | **MET** | 5 artifact hashes (full + cached), listener exe/argv, `/props` build/ctx/slots; READY implies verified artifacts for the live pid (after audit rounds 1-2) |
| AC4 | Streaming and cancellation correct | **MET** | live: cancel 0.56 s, slot freed, next call 0.25 s; HTTP cancel endpoint and disconnect-cancel tested |
| AC5 | Simple tasks remain responsive | **MET for time-to-first-text** | first visible text p50 0.20 s, max 0.61 s, 0 Brain decision calls; whole-turn time depends on answer length (8/12 < 2 s). Degrades ~3× under OI-PERF-1 (now detected) |
| AC6 | Harder tasks get deeper reasoning when appropriate | **MET** | policy NORMAL for analysis/planning; task score 0.667 → 0.853 (FAST → NORMAL), p50 6.2 s |
| AC7 | Orchestration respects permissions and user choices | **MET (development)** | Core authority unchanged; plan approval, verbatim/negation-safe spans, harness choice never auto-selects (tests + live) |
| AC8 | Failure and recovery tested | **MET** | 12 client failure modes, runtime restart, foreign instance, ledger crash recovery, audit regressions |
| AC9 | No frozen source modified | **MET** | `OI_BASELINE_AND_ISOLATION.md` §3 |
| AC10 | Existing accepted regressions still pass | **MET WITH DEFINED EXCEPTION** | §4 below: authority 134/134, Phase 1 full outcome-identical (2,698 ids), Phase 2 486/486 and phase1-scope PASS without OI files; with OI files present two Phase 2 scope guards and phase1-scope flag the new paths by design |
| AC11 | UI project unaffected | **MET** | no write to `uri-ui-phase`; contract published as a document + simulator |
| AC12 | Reproducible evidence for performance claims | **MET with caveat** | scripts + evidence JSON; single runs; run-1 timings invalidated by OI-PERF-1 and replaced |

## 3. Implementation-status ledger

| Feature | Class | Notes |
|---|---|---|
| Runtime v1 discovery, artifact + live identity, readiness states | 4 | `runtime_v1.py`; live verified |
| Single-instance start/attach/stop (lock, kill-on-close job, foreign refusal) | 4 | live stop/start; foreign test |
| Streaming client, cancellation, deadlines, honest statuses, retry rules | 4 | 12 fake-server tests + live cancel |
| Performance health (VRAM residency + decode rate, DEGRADED) | 3 | unit-tested; thresholds from one incident; live residency sampling works; no live DEGRADED detection observed after the fix |
| Reasoning policy FAST / NORMAL / ESCALATE, user depth | 4 | tests + benchmark |
| Deterministic triage | 4 | held-out recall 0.75 alone |
| Answer channel + action marker + claim correction | 4 | held-out combined recall 1.00, FP 0.05; claim guard is post-response |
| Core ModelProvider + `oi_composition` | 4 | Suite P 12/12 (single run), live 8/8 |
| Orchestrator (routing, Core relay, CONVERSATION fallback, readiness fast-fail) | 4 | fake-Core tests + live end-to-end |
| Planner (NORMAL, schema) + deterministic validation | 3 | validation tested incl. negation; live plan quality NOT benchmarked (no plan-quality suite run live) |
| Task ledger + restart recovery + `decide_step` | 3 | unit-tested; not exercised against the real Core across a real process crash |
| Harness choice + quota choice event + `begin_harness` | 3 | unit-tested; live harness execution NOT run (Phase 2 physical qualification pending; owner policy rows absent) |
| Quota resume (`continue_waiting`) through OI | 1 | frozen client supports it; no OI method yet |
| UI event contract + simulator + dev SSE server | 3 | tested; not consumed by the UI yet |
| Benchmarks (tasks, routing, latency, MTP comparison) | 4 | evidence JSON |
| Production composition offering the Runtime v1 row | 1 | owner decision |
| Integration into canonical development | 1 | procedure in `OI_INTEGRATION_READINESS.md` |

## 4. Regression gate record (accepted chain `scripts/phase2close_chain.py`, gate checkout `uri-oi-gate`)

| Run | Tree | phase2 | authority | phase1-full | phase1-scope | residue |
|---|---|---|---|---|---|---|
| chain1 (with OI package, without `tests/oi`) | e8e3b65 + OQ overlay + OI | 484 passed / **2 failed** (`test_frozen_core::test_nothing_changed_outside_checkpoint_and_phase2a_paths`, `test_boundary::test_phase2a_frozen_core_tests_still_hold`: both list the OI paths) | **134 passed** | **PASS**: 2,676 / 11 failed / 11 skipped, same 11 failure ids, 2,698 ids, missing/added/changed empty | **FAIL**: `outside_phase2_scope` = OI paths; importer = `runtime_v1.py` (imports `uri_supervisor.winproc`) | PASS |
| chain2 (control: OI files moved out) | e8e3b65 + OQ overlay | **486 passed** | — | — | **PASS** | — |

Reading: with the OI package present no Phase 1 or Phase 2 test changed outcome; the only failures are scope guards
that list every path outside their allowlists. Not run: flutter, bridge ×N, native, native-worker (OI adds no file
to `uri_ui/`, the bridge or the harness adapters).

Integration consequence: the accepted scope guards will flag OI until the owner authorizes a defined OI scope in
those gates (Phase 2 tests are accepted files; OI did not edit them).

## 5. Known limitations and outstanding defects

| ID | Item | Affects |
|---|---|---|
| OI-PERF-1 | Silent VRAM residency loss (~3× slower). Detected, not prevented; trigger unknown | responsiveness |
| OI-SEC-1 | Runtime v1 has no API key and CORS `*` (frozen flags). Owner decision | local exposure of the model endpoint |
| CONS-7 | Core runs only at `HEAD == e8e3b65`; live tests need a materialized tree | integration |
| LIM-1 | Only `remember_fact` and `external_harness_task` are qualified paired capabilities; recall/search/drafting-to-file are not executable via paired Core | usefulness |
| LIM-2 | NORMAL tier uses its full 768-token budget almost always (~6 s) | latency of analysis turns |
| LIM-3 | Error-recovery knowledge tasks fail at both tiers (0.25): recovery must stay deterministic (it is) | model limits |
| LIM-4 | Live planner quality, live harness execution and live quota resume not demonstrated | orchestration claims |
| LIM-5 | Benchmarks are single runs (repeatability: 59/60 identical answers between two MTP runs) | statistics |
| LIM-6 | Dev SSE server: single bearer token, no per-client scoping (development only) | not production |
| LIM-7 | Claim guard is a post-response correction; the claim may be shown first | UI must render the flag |
