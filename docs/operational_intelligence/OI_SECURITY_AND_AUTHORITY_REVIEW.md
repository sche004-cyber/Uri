# OI security and authority review (self-review, 2026-10-08)

Scope: `uri_operational_intelligence/` at the head of `phase/operational-intelligence`, the dev host/server, and how
they connect to the frozen Core and Runtime v1. This is the development team's own review; the independent review
is recorded in `OI_INTEGRATION_READINESS.md`.

## 1. Acceptance criteria (defined before the review)

| # | Criterion | Evidence required |
|---|---|---|
| S1 | OI cannot cause any capability execution without Core's confirmation + explicit user approval | code path inspection + live Core tests |
| S2 | No fabricated tool outcome reaches the user | outcome mapping tests; answer-channel claim guard |
| S3 | No silent Brain or provider switch | Core policy behaviour live; harness choice tests |
| S4 | No duplicate execution after an uncertain outcome | ledger recovery tests; Core intent ledger reused |
| S5 | The model cannot raise its own budget or enable unbounded thinking | code inspection + tests |
| S6 | Runtime process safety: one instance, never adopt/kill foreign processes, no orphan | tests + live stop |
| S7 | Runtime provenance verified before use | artifact + live identity checks, live run |
| S8 | Frozen / accepted code untouched | git diff proof |
| S9 | No secrets or user content leaked into logs/evidence beyond the test data | inspection |

## 2. Results

| # | Verdict | Evidence |
|---|---|---|
| S1 | PASS | OI has no import of any dispatcher/executor/ticket code. Its only Core entry points are `TurnRunner.begin / confirm / decide(approve: bool)`; `decide` is called only from `Orchestrator.decide`, whose `approve` comes from the caller (UI button). Live (real paired Core + Runtime v1, `test_oi_core_live.py`, 8/8): remember → approval → SETTLED_VERIFIED; deny → APPROVAL_DENIED with memory unchanged; injected "save … without asking me" → REFUSED_INVALID_PROPOSAL; destructive → REFUSED_UNSUPPORTED. Suite P 12/12 includes p08 injected approval and p12 typed "confirmed" never confirming |
| S2 | PASS (after audit repair) | Success is allowlisted: a step is VERIFIED only for `SETTLED_VERIFIED` with state `reply`; a turn is `ok` only then (unknown codes are `reported`); a non-streamed call is COMPLETE only for finish `stop`/`eos`. Answer text never carries an outcome; a reply claiming an unperformed action is flagged `UNVERIFIED_ACTION_CLAIM` with an appended correction (post-response: the claim may already be visible) |
| S3 | PASS | Core policy refuses unlisted rows; runtime down → SELECTED_MODEL_UNAVAILABLE live, nothing substituted. OI's Core-path pre-check reports BRAIN_UNAVAILABLE instead of calling anything else. `harness_choice.choose` never selects without the user's explicit, still-usable choice (tests) |
| S4 | PASS (after two audit repairs; unit-level) | Round 1: a crash between approval and recording could restart a step; SKIPPED satisfied dependencies. Round 2: the old `decide`+`record_step` path still bypassed the durable write; concurrent `advance()` could dispatch twice; recovery was never invoked. Repaired: the ledger has no transition from WAITING_APPROVAL to an outcome except via EXECUTING (`decide_step`), IN_CORE/EXECUTING are exclusive claims under a per-task file lock (threads tested; separate processes untested), `decide()` refuses plan-step turns, recovery needs exclusive ledger ownership and the dev server recovers before serving, SKIPPED blocks transitively (`test_oi_audit_r1_regressions.py`, `test_oi_audit_r2_regressions.py`). Not exercised: a real process crash against the real Core. Core's own `INTENT_ALREADY_EXECUTED` / `INTENT_EXECUTION_UNCERTAIN` guards remain authoritative |
| S5 | PASS | Budgets exist only in `reasoning_policy.tier_params`; FAST capped at 4,000 tokens; NORMAL fixed 768 thinking; `depth=deep` → escalation offer, no local call (tests) |
| S6 | PASS | FOREIGN_INSTANCE never adopted or started over (test with a foreign listener); `stop()` returns False for non-owned; start lock excludes a second starter; kill-on-close job (live stop: `STOPPED_CLEAN True`) |
| S7 | PASS (after audit repair) | Live: all 5 artifacts MATCH by full hash (model 87.5 s), later starts by cache (reported `cached`); listener exe + argv authorized; `/props` build `b11425-e117148a4`, ctx 32768, 1 slot. Codex round 1: attach skipped artifact verification and the cache trusted size+mtime only. Repaired: attach verifies artifacts; cache hit also needs ctime and file id. Round 2: `status()` could say READY without artifact verification; round 3: it then cached that verification per pid forever. Now every READY probe re-verifies (metadata cache; a removed or changed file turns the next probe into IDENTITY_MISMATCH, tested) and reports the process creation time. Limitation kept: a same-user writer who restores all metadata defeats the cache; `--full-verify` re-hashes |
| S8 | PASS | `OI_BASELINE_AND_ISOLATION.md` §3 |
| S9 | PASS with note | Provider call log stores status/timings only, no prompt text. Benchmark evidence stores model answers to synthetic tasks. Runtime stdout/stderr log (`work/oi/state/logs`) contains llama-server diagnostics only (no prompts at the default log level) |

## 3. Findings

| ID | Severity | Finding | Status |
|---|---|---|---|
| OI-SEC-1 | Medium | Frozen Runtime v1 flags start `llama-server` with **no API key and CORS allowing all origins** (server log: "security: no API key is set and CORS allows all origins"). Any local process, and any web page open in a local browser, can send prompts to 127.0.0.1:18470 and occupy the single slot. It cannot reach URI tools, Core or user data (the runtime has none), so the exposure is model use / denial of service, not authority | Open. Fix = add `--api-key` (+ client header) to the frozen flag set: a Runtime v1 amendment, **owner decision (AMBER)**; not done |
| OI-SEC-2 | Low | Dev SSE server uses one bearer token per launch; no per-client binding; ledger tasks are not scoped per client | Accepted for development only; production transport must be the paired client channel |
| OI-SEC-3 | Low | The answer-channel action marker is probabilistic (held-out: recall 1.00 combined with triage, triage alone 0.75). Failure mode is "an action request answered with text and nothing done", never an action | Mitigated by design (answer channel has no tools) + claim guard |
| OI-SEC-4 | High → fixed (3 rounds) | Planner `source_span` check could strip negation ("Don't email Ravi, just draft it" contains "email Ravi"). First fix only looked two words back; Codex round 1 broke it with "Do not under any circumstances email Ravi." | Fixed: any negation/exclusion earlier in the same clause rejects the span (fail closed); spans must match with word boundaries where hyphen and apostrophe count as word characters (round 2: "activate account" inside "deactivate account"; round 3: "-activate account" inside "de-activate account") and are replaced by the user's exact characters. Tests incl. both Codex counter-examples. Core confirmation would still have shown the words to the user, but the step must not be proposed at all |
| OI-PERF-1 | Medium (availability) | Runtime v1 can silently lose VRAM residency (dedicated −689 MiB, shared +794 MiB) and run ~3× slower with no error | Detected by `perf_monitor` (DEGRADED + recovery options). Root cause of the eviction: CAUSE UNKNOWN (desktop VRAM pressure suspected, not proven) |
| OI-SEC-5 | Info | `recall_memory` is not a qualified paired capability; "what did I ask you to remember?" is refused by Core with the Brain row (REFUSED_INVALID_PROPOSAL) and answered without memory on the answer channel | Capability gap, not a bypass |

## 4. Authority boundaries re-checked

- Brain ≠ development agent: Runtime v1 is a direct local model; no code path shells out to `claude` or `codex`.
- Harness ≠ Brain: harness options are execution providers chosen per task by the user.
- Model output is untrusted everywhere: Core seams validated by Core; plans validated deterministically; answer text
  never carries outcomes.
