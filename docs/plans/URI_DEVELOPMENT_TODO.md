# URI development TODO and implementation-status ledger

Created 2026-10-08 (Phase 2 closure). No earlier canonical ledger existed in this tree (the closest were the per-slice
"research / implementation ledger" tables in `PHASE2D_REPORT.md` section I and `PHASE2OPS_REPORT.md` section M, which
this ledger supersedes as the single place to look). Maintainer: whoever changes a status; every change needs an
evidence reference. History is kept: when a status changes, the old value moves to the change log at the end.

Status vocabulary (one or more, in this order of strength): RESEARCHED, PLANNED, DESIGN ONLY, IMPLEMENTED, TESTED,
INDEPENDENTLY ACCEPTED, PHYSICALLY QUALIFIED, FROZEN; or BLOCKED / DEFERRED. A design document or prototype never
makes an item IMPLEMENTED. TESTED means an automated run with `COMPLETED_WITH_RESULT` in the cited log.

Evidence roots: `E:` = `C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\`; paths without a prefix are relative to
the Phase 2 worktree `C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent`.

## 1. Phase 2 core (supervised execution)

| Item | Goal / expected outcome | Status | Evidence | Outstanding | Depends on | Owner decision | Next step |
|---|---|---|---|---|---|---|---|
| 2A durable task supervisor (`uri_supervisor/`) | durable admission, fencing, containment, recovery on a WAL+FULL ledger | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (as part of 2D/ops candidates) | `PHASE2A_REPORT.md`; `tests/phase2a` | physical power loss | PA-11 | none | VM campaign |
| 2B Core <-> supervisor bridge (`uri_supervisor_bridge/`) | signed ticket -> supervised task; no new authority | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED | `PHASE2B_REPORT.md`; `tests/phase2b` | — | — | none | — |
| 2C native qualification (run-scoped) | real CLI through the full governed chain | TESTED (Codex NATIVE RUN in-process, owner shell login); Claude BLOCKED (not logged in) | `PHASE2C_NATIVE_QUALIFICATION_REPORT.md`; `E:phase2c\` | client-profile login; EXE-1 | PA-8/9, EXE-1 | EXE-1 | owner decision |
| 2D composition (persisted qualification, policy file, opt-in profiles) | the worker/server profiles compose qualified rows only | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (Codex round 3) | `PHASE2D_REPORT.md`; `E:phase2d_review\` | — | — | none | — |
| UI/operations slice (execution lifecycle, mid-run cancel, reconnect, supervised screen) | the real UI drives supervised execution with digest-bound approval | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (Codex round 7, candidate `9a0be52c...`) | `PHASE2OPS_REPORT.md`; `E:phase2ops_review\round7\` | human click (PA-1..7) | owner session | none | owner session |
| LOG-3 refusal log retains at most 4096 bytes | bounded memory for error bodies | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (closure round 6) (negative control: r6 code peaks 4.2 MB) | `uri_supervisor_bridge/refusal_log.py`; `tests/phase2ops/test_refusal_log.py::test_log3_*` | independent review | P2-1 | none | review |
| VAL-1 historical HTTP 403 | establish cause; prevent recurrence harm | TESTED: mechanism reproduced deterministically (frozen `issued_at == int(clock())` check across a second boundary -> `TICKET_CLOCK_OR_GENERATION` 403, turn unchanged); measured in-process window 0.55 ms; bounded single resend IMPLEMENTED/TESTED; historical instance NOT attributable (no code was logged then) | `tests/phase2ops/test_val1_clock_boundary.py`; `PHASE2CLOSE_REPORT.md` section C | independent review; physical sessions keep the refusal log | P2-1 | none | review |
| CAP-1 abandoned approval cards held server capacity | a dropped card must not block the session (or, after four, the server) for 15 minutes | IMPLEMENTED, TESTED (incl. real processes; 3 accepted assertions updated, recorded) | `tests/phase2ops/test_capacity_release.py`; `tests/phase2ops/test_worker_process.py::test_cap1_*` | independent review | P2-1 | none (tightening; review may disagree) | review |
| ISO-1 Codex ignored the client profile | a client executor must never use the owner's global login | IMPLEMENTED, TESTED (live leak observed, pin closes it) | `uri_supervisor_bridge/qualification.py::client_cli_homes`; `tests/phase2close/test_iso1_cli_home.py` | independent review | P2-1 | none | review |
| SUP-1 suspended orphan when the supervisor dies during spawn | a supervisor death can never leave a process behind | RECORDED (Low; no effect possible: the child is never resumed) | `uri_supervisor/winproc.py` `spawn_contained` (CREATE_SUSPENDED before AssignProcessToJobObject); seen twice in SIMULATED power-loss tests, killed by the orchestrator; Codex closure round 1 K1 | atomic job assignment (`PROC_THREAD_ATTRIBUTE_JOB_LIST`) in Phase 2A containment | review of a Phase 2A change | none | hardening slice |
| Acceptance `qualify` credential isolation (D1) | only a client-profile login can qualify a client | IMPLEMENTED, TESTED | `scripts/phase2close_acceptance.py::probe_environment`; `tests/phase2close/test_acceptance_tooling.py` | independent review | P2-1 | none | review |
| Power-loss verdict discipline (D2, D4) | no harness output can pass for a physical qualification; the assessment is recomputed from raw records | IMPLEMENTED, TESTED | `phase2close_powerloss_harness.py` (`SERIES_*`, `assess`, `qualified` always false); tests | independent review | P2-1 | none | review |
| EXE-1 worker cannot launch node-based CLIs | native execution inside the worker process | BLOCKED | `PHASE2CLOSE_C7_READINESS.md` section 4 (observed `"node" is not recognized`) | option A implementation | owner decision | **yes (A/B/C/D)** | owner decision |
| Physical power-loss durability | WAL+FULL survives real power cuts | harness IMPLEMENTED, TESTED (SIMULATED plumbing only); durability NOT QUALIFIED | `scripts/phase2close_powerloss_harness.py`; `tests/phase2close/test_powerloss_harness.py`; `PHASE2A_POWER_LOSS_TEST_PLAN.md` | 200+ VM iterations + NORMAL control | VM + hypervisor (none on this PC) | owner provides VM | PA-11 |
| Human acceptance on the real app | owner approves/denies/cancels/reopens | PLANNED (runbook) | `PHASE2CLOSE_PHYSICAL_ACCEPTANCE_RUNBOOK.md`; `scripts/phase2close_acceptance.py` | PA-1..PA-7 | owner present | none | owner session |
| Phase 2 rollback overlay | offline rollback of the Phase 2 file set | DESIGN ONLY | `PHASE2CLOSE_C7_READINESS.md` P2-5 | implementation on the final tree | final tree | none | automation slice |
| Phase 2 freeze | frozen Phase 2 checkpoint | DEFERRED | — | all of the above | owner | **yes** | after acceptance |

## 2. Chat, conversation and UI

| Item | Goal | Status | Evidence | Outstanding | Depends on | Owner decision | Next step |
|---|---|---|---|---|---|---|---|
| C6 decision 2: Chat <-> supervised execution | conversation-to-task without losing context or approval boundaries | RESEARCHED, PLANNED (recommendation B); handoff seam IMPLEMENTED, TESTED (widget) | `PHASE2CLOSE_C6_CHAT_INTEGRATION.md`; `uri_ui/lib/services/task_handoff.dart`; widget tests | Chat action (one widget + 4 tests) | decision | **yes** | owner chooses A/B/C/D |
| C6 decision 1: "Companion" / "Intelligence" roles | defined roles | BLOCKED on owner | `C6_UI_INTEGRATION_CONTRACT.md`; `_V1` harness record mentions Companion/Workspace/Intelligence | definition | — | **yes** | owner |
| C6 decision 3: Brain rows offered | which Brain rows the UI may offer | BLOCKED on owner + C5 policy review | `C7_CUTOVER_REQUIREMENTS.md` gate 3 | review | — | **yes** | owner |
| Companion UI (Living Energy Orb) | ambient companion presence driven by real state | DESIGN ONLY (state contract) | `docs/architecture/PHASE2CLOSE_UI_READINESS.md` section 3 | visual design; line reconciliation | P2-6 | yes (design approval) | design phase |
| Voice Companion <-> Workspace transitions | voice-driven presentation switches | PLANNED; voice status strip IMPLEMENTED on `_V1` only | `_V1` `docs/design_library/approved/voice_status_2026-10-04.md` | voice parity decision; hardware speech acceptance | P2-6 | **yes** | owner |
| Interactive Brain / capability visualization | show executors, qualification, policy, grants | DESIGN ONLY (data sources named) | `PHASE2CLOSE_UI_READINESS.md` section 2 | read-only API contract + design | P2-6 | design approval | design phase |
| Guided onboarding (roles, providers, models, permissions, connection, auth, readiness) | first-run path to a ready installation | PARTIAL: legacy onboarding screens IMPLEMENTED (Phase 1 line); Phase 2 readiness checks exist as scripts | `screens/onboarding/*`; `scripts/phase2close_acceptance.py preflight` | onboarding over preflight/discover/qualify; roles definition | C6 decision 1, EXE-1 | yes | design phase |
| Approval/progress/cancel/recovery/receipt presentation | clear, honest execution UX | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (supervised screen) | `supervised_execution_screen.dart`; widget tests | extraction to shared widgets | next UI phase | none | next UI phase |
| Pinned UI release build | `ui_binary` + `ui_sha256` in the client manifest | PLANNED | `C6_UI_INTEGRATION_CONTRACT.md` | build + pin | C7 | at cutover | C7 slice |
| Development-line reconciliation (P2-6) | one tree to ship | PLANNED | `PHASE2CLOSE_C7_READINESS.md` P2-6 | integration plan | owner | **yes** | owner chooses line |

## 3. Research and later-phase capabilities

| Item | Goal | Status | Evidence | Outstanding | Depends on | Owner decision | Next step |
|---|---|---|---|---|---|---|---|
| Strata (resident model optimisation) | faster resident Brain | RESEARCHED; NOT IMPLEMENTED in Phase 2; NOT REQUIRED | `PHASE2D_REPORT.md` section I; memory `uri-resident-runtime-v1-frozen` (optimisation CLOSED) | none in Phase 2 | reopening criteria of the Runtime v1 freeze | — | none |
| Paperclip (external harness-orchestration project, reconnaissance) | adopt its useful harness patterns, never its bypass defaults | RESEARCHED; owner rulings OD-1..OD-5 accepted 2026-09-28 (harnesses as bounded execution workers, restrictive defaults); DEFERRED as a dependency | `_V1` `docs/plans/PAPERCLIP_URI_ARCHITECTURE_RECONNAISSANCE.md` section 22; `PHASE2OPS_REPORT.md` section M | none in Phase 2 | — | — | none |
| AG-UI / A2UI | agent-UI event transport | RESEARCHED (no transport adopted) | `PHASE2OPS_REPORT.md` section M | — | UI phase | — | revisit in UI phase |
| Context Capsule | bounded, provenance-tagged context package for a harness | DESIGN ONLY (later phase, undated) | `PHASE2C_TASK_COMPILER_PLACEMENT.md`; Codex round 3 section D | design review, implementation | Task Compiler | — | later phase |
| Task Compiler | confirmed meaning -> executor-ready task package | DESIGN ONLY (later phase); only seam: `execution_proposal` | `PHASE2C_TASK_COMPILER_PLACEMENT.md` | design, implementation | — | — | later phase |
| MCP broker | governed MCP access for executors | PLANNED / DESIGN ONLY | `PHASE2OPS_REPORT.md` section M | design | — | — | later phase |
| Model residency (Resident Intelligence Runtime v1) | resident local Brain | FROZEN as a separate prototype (llama.cpp b11425 stock + prompt shaping + MTP); NOT integrated into the Phase 2 composition | memory `uri-resident-runtime-v1-frozen`; `model_lab/URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md` (phase1-integration worktree) | Brain row activation (gate 3) | C6 decision 3 | **yes** | owner |
| URI Memory as harness context | memory feeding a context capsule | DESIGN ONLY (memory exists in Core; no capsule) | `PHASE2OPS_REPORT.md` section M | Context Capsule | — | — | later phase |

## 4. C7 cutover

See `PHASE2CLOSE_C7_READINESS.md` (gates 1-10 + P2-1..P2-8). Summary: gates 1-2 MET (Phase 1), 3/9 PARTIAL, 4/5/8
NOT MET, 6/10 NOT AUTHORIZED/REQUESTED, 7 PROCEDURE ONLY. Verdict NOT READY.

## Change log

| Date | Item | From | To | Evidence |
|---|---|---|---|---|
| 2026-10-08 | ledger created | — | — | this file |
| 2026-10-08 | LOG-3 | OPEN (Low, Codex round 7) | IMPLEMENTED, TESTED | `test_log3_*` |
| 2026-10-08 | VAL-1 | OPEN observation, cause unknown | cause mechanism TESTED; bounded resend IMPLEMENTED, TESTED | `test_val1_clock_boundary.py` |
| 2026-10-08 | CAP-1, ISO-1, EXE-1 | (not known) | found; CAP-1/ISO-1 repaired + TESTED; EXE-1 BLOCKED | closure report section C |
| 2026-10-08 | D1, D2, D3, SUP-1 | (not known) | Codex closure round 1 REJECTED on D1/D2/D3; D1/D2 repaired + TESTED; D3 = rerun full chain; SUP-1 recorded | `E:phase2close_review\round1\` |
| 2026-10-08 | D4, D5 | (not known) | Codex closure round 2 REJECTED on D4 (assess trusted summaries); D4/D5 repaired + TESTED | `E:phase2close_review\round2\` |
| 2026-10-08 | D4 residual | open after round 3 | REPAIRED (exact rebuild from raw record) + TESTED | `E:phase2close_review\round3\` |
| 2026-10-08 | D4 residual (invariants), D6 | open after round 4 | REPAIRED + TESTED | `E:phase2close_review\round4\` |
| 2026-10-08 | D7, power-method check | open after round 5 | REPAIRED / NARROWED + TESTED | `E:phase2close_review\round5\` |
| 2026-10-08 | Phase 2 closure (LOG-3, VAL-1, CAP-1, ISO-1, D1-D7, handoff seam, acceptance tooling, power-loss harness) | IMPLEMENTED, TESTED | INDEPENDENTLY ACCEPTED (Codex closure round 6, `-f` fcd0d72e...71298); D8 + K1 recorded Low | `E:phase2close_review\round6\` |
