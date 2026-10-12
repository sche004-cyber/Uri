# URI development TODO and implementation-status ledger

Created 2026-10-08 (Phase 2 closure). No earlier canonical ledger existed in this tree (the closest were the per-slice
"research / implementation ledger" tables in `PHASE2D_REPORT.md` section I and `PHASE2OPS_REPORT.md` section M, which
this ledger supersedes as the single place to look). Maintainer: whoever changes a status; every change needs an
evidence reference. History is kept: when a status changes, the old value moves to the change log at the end.

Status vocabulary (one or more, in this order of strength): RESEARCHED, PLANNED, DESIGN ONLY, IMPLEMENTED, TESTED,
INDEPENDENTLY ACCEPTED, PHYSICALLY QUALIFIED, FROZEN, DEPLOYED; or BLOCKED / DEFERRED. (DEPLOYED added 2026-10-08 by
the operational-qualification mandate; nothing is DEPLOYED.) A design document or prototype never
makes an item IMPLEMENTED. TESTED means an automated run with `COMPLETED_WITH_RESULT` in the cited log.

Evidence roots: `E:` = `C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\`; paths without a prefix are relative to
the Phase 2 worktree `C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent`.

## 1. Phase 2 core (supervised execution)

| Item | Goal / expected outcome | Status | Evidence | Outstanding | Depends on | Owner decision | Next step |
|---|---|---|---|---|---|---|---|
| 2A durable task supervisor (`uri_supervisor/`) | durable admission, fencing, containment, recovery on a WAL+FULL ledger | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (as part of 2D/ops candidates) | `PHASE2A_REPORT.md`; `tests/phase2a` | physical power loss | PA-11 | none | VM campaign |
| 2B Core <-> supervisor bridge (`uri_supervisor_bridge/`) | signed ticket -> supervised task; no new authority | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED | `PHASE2B_REPORT.md`; `tests/phase2b` | — | — | none | — |
| 2C native qualification (run-scoped) | real CLI through the full governed chain | TESTED (Codex NATIVE RUN in-process, owner shell login); Claude BLOCKED (not logged in); EXE-1 RESOLVED in the operational-qualification slice (native binaries) | `PHASE2C_NATIVE_QUALIFICATION_REPORT.md`; `E:phase2c\`; `PHASE2OQ_REPORT.md` section C | client-profile login; EXE-1b | PA-8/9, EXE-1b | EXE-1b | owner |
| 2D composition (persisted qualification, policy file, opt-in profiles) | the worker/server profiles compose qualified rows only | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (Codex round 3) | `PHASE2D_REPORT.md`; `E:phase2d_review\` | — | — | none | — |
| UI/operations slice (execution lifecycle, mid-run cancel, reconnect, supervised screen) | the real UI drives supervised execution with digest-bound approval | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (Codex round 7, candidate `9a0be52c...`) | `PHASE2OPS_REPORT.md`; `E:phase2ops_review\round7\` | human click (PA-1..7) | owner session | none | owner session |
| LOG-3 refusal log retains at most 4096 bytes | bounded memory for error bodies | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (closure round 6) (negative control: r6 code peaks 4.2 MB) | `uri_supervisor_bridge/refusal_log.py`; `tests/phase2ops/test_refusal_log.py::test_log3_*` | independent review | P2-1 | none | review |
| VAL-1 historical HTTP 403 | establish cause; prevent recurrence harm | TESTED: mechanism reproduced deterministically (frozen `issued_at == int(clock())` check across a second boundary -> `TICKET_CLOCK_OR_GENERATION` 403, turn unchanged); measured in-process window 0.55 ms; bounded single resend IMPLEMENTED/TESTED; historical instance NOT attributable (no code was logged then) | `tests/phase2ops/test_val1_clock_boundary.py`; `PHASE2CLOSE_REPORT.md` section C | independent review; physical sessions keep the refusal log | P2-1 | none | review |
| CAP-1 abandoned approval cards held server capacity | a dropped card must not block the session (or, after four, the server) for 15 minutes | IMPLEMENTED, TESTED (incl. real processes; 3 accepted assertions updated, recorded) | `tests/phase2ops/test_capacity_release.py`; `tests/phase2ops/test_worker_process.py::test_cap1_*` | independent review | P2-1 | none (tightening; review may disagree) | review |
| ISO-1 Codex ignored the client profile | a client executor must never use the owner's global login | IMPLEMENTED, TESTED (live leak observed, pin closes it) | `uri_supervisor_bridge/qualification.py::client_cli_homes`; `tests/phase2close/test_iso1_cli_home.py` | independent review | P2-1 | none | review |
| SUP-1 suspended orphan when the supervisor dies during spawn | a supervisor death can never leave a process behind | IMPLEMENTED, TESTED (operational qualification: the hosting process joins its own kill-on-close job before any spawn; real-process negative control) | `uri_supervisor/winproc.py::contain_current_process`; `Supervisor.__init__`; `tests/phase2oq/test_sup1_self_containment.py`; live orphan observed 2026-10-08 (`E:phase2oq\sup1_orphan_observed_20261008.json`) | independent review | P2-1 | none | review |
| Acceptance `qualify` credential isolation (D1) | only a client-profile login can qualify a client | IMPLEMENTED, TESTED | `scripts/phase2close_acceptance.py::probe_environment`; `tests/phase2close/test_acceptance_tooling.py` | independent review | P2-1 | none | review |
| Power-loss verdict discipline (D2, D4) | no harness output can pass for a physical qualification; the assessment is recomputed from raw records | IMPLEMENTED, TESTED | `phase2close_powerloss_harness.py` (`SERIES_*`, `assess`, `qualified` always false); tests | independent review | P2-1 | none | review |
| EXE-1 worker cannot launch node-based CLIs | native execution inside the worker process | IMPLEMENTED, TESTED: native `codex.exe`/`claude.exe` qualified with pinned vendor launch chain, no interpreter, no PATH change; REAL worker composes the record and fails closed without a client login; worker-environment lifecycle + cancel pass against a scripted model (NOT PA-10) | `uri_supervisor_bridge/qualification.py` (`codex_native_launch_chain`, `native_executable`, `check_codex_client_home`); `scripts/phase2oq_native_worker.py`; `tests/phase2oq/test_exe1_native.py`; chain gate `native-worker` | EXE-1b, client-profile login, PA-10 | owner | EXE-1b (sandbox backend) | owner |
| Physical power-loss durability | WAL+FULL survives real power cuts | harness IMPLEMENTED, TESTED (SIMULATED plumbing only); D8 guest unclean-shutdown witness IMPLEMENTED, TESTED; guest bundle IMPLEMENTED, TESTED (simulated from the extracted bundle); durability NOT QUALIFIED | `scripts/phase2close_powerloss_harness.py`; `scripts/phase2oq_powerloss_bundle.py`; `tests/phase2close/test_powerloss_harness.py`; `tests/phase2oq/test_powerloss_bundle.py` | 200+ VM iterations + NORMAL control + owner attestation | hypervisor + VM (none on this PC) | owner provides VM | PA-11 |
| Human acceptance on the real app | owner approves/denies/cancels/reopens and uses the Chat handoff | PLANNED (runbook, PA-1..PA-13) | `PHASE2CLOSE_PHYSICAL_ACCEPTANCE_RUNBOOK.md`; `scripts/phase2close_acceptance.py` (preflight, provision, login-guide, qualify, status, record, collect) | PA-1..PA-7, PA-13 | owner present | none | owner session |
| Phase 2 rollback overlay | offline rollback of the Phase 2 file set | DESIGN ONLY | `PHASE2CLOSE_C7_READINESS.md` P2-5 | implementation on the final tree | final tree | none | automation slice |
| OQ-1 approval offered for an unusable executor | an approval must never be sent for an executor that cannot run now | IMPLEMENTED, TESTED (`execution_begin` refuses `HARNESS_NOT_USABLE` before the server; UI disables Approve; 1 accepted assertion changed, disclosed) | `uri_supervisor_bridge/execution.py::harness_state`; `tests/phase2ops/test_lifecycle.py`; widget tests "OQ-1" | independent review | P2-1 | none | review |
| EXE-1b Codex Windows sandbox backend of the client profile | Codex commands run sandboxed with the owner's chosen confinement | IMPLEMENTED (fail-closed `CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED`; `provision --codex-sandbox` owner choice), TESTED; measured: `unelevated` confines writes, NOT network | `E:phase2oq\sandbox_probes\README.md`; `tests/phase2oq/test_exe1_native.py`, `test_acceptance_oq.py` | owner choice; elevated setup if chosen | — | **yes** | owner |
| Client-profile authentication tooling | installed / authenticated / qualified / operational kept apart; logins never copied | IMPLEMENTED, TESTED (`login-guide` prints only; `status` four states) | `scripts/phase2close_acceptance.py`; `tests/phase2oq/test_acceptance_oq.py` | PA-8/PA-9 | owner | none | owner session |
| Phase 2 freeze | frozen Phase 2 checkpoint | DEFERRED | — | all of the above | owner | **yes** | after acceptance |

## 2. Chat, conversation and UI

| Item | Goal | Status | Evidence | Outstanding | Depends on | Owner decision | Next step |
|---|---|---|---|---|---|---|---|
| C6 decision 2: Chat <-> supervised execution | conversation-to-task without losing context or approval boundaries | OWNER DECIDED Option B (2026-10-08); Chat action IMPLEMENTED, TESTED (widget + Chat pane); PHYSICALLY QUALIFIED: no (PA-13) | `PHASE2CLOSE_C6_CHAT_INTEGRATION.md` section 9; `uri_ui/lib/widgets/supervised_handoff_action.dart`; `uri_ui/test/chat_supervised_handoff_test.dart` | review; PA-13 | — | none | review, owner session |
| C6 decision 1: "Companion" / "Intelligence" roles | defined roles | RESOLVED AS A DEFINITION (no authority effect, reversible): Intelligence = policy mode (owner D2), Companion = Compact/desktop presentation | `PHASE2OQ_REPORT.md` section D | owner may override | — | confirm (optional) | — |
| C6 decision 3: Brain rows offered | which Brain rows the UI may offer | PENDING (authority/consent: who reasons over requests; which rows the server composes) | `C7_CUTOVER_REQUIREMENTS.md` gate 3; `PHASE2OQ_REPORT.md` section D | review of C5 policy | — | **yes** | owner |
| Companion UI (Living Energy Orb) | ambient companion presence driven by real state | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (Codex companion settings round 4; integration rounds), INTEGRATED into `integration/git-sync-20261008` (2026-10-09): living companions Solar / Sakura / Lunar / Moonlit Blossom + classic Energy Orb, companion-driven theme, Companion Settings (appearance, frame rate, render quality, voices), voice stage beside the companion; not deployed | `docs/companions/settings/COMPANION_SETTINGS_REPORT.md`; `docs/companions/settings/INTEGRATION_RECEIPT.md` | start order vs Runtime v1 VRAM (owner); adaptive back-off not yet observed under a live Brain; production cutover | C7 | yes (start order; cutover) | owner |
| Voice Companion <-> Workspace transitions and voice parity | voice-driven presentation switches; voice as a draft source | Live voice (2026-10-09, `docs/voice/live/`): push-to-talk capture IMPLEMENTED, VERIFIED (real microphone, synthetic talker); local recognition (faster-whisper base.en, CPU) IMPLEMENTED, VERIFIED (WER 7.26 % strict / 3.94 % format-normalised on 45 real-microphone recordings); conversation by voice through Core/OI/Brain with spoken replies IMPLEMENTED, VERIFIED (live run 7); companion listening/transcribing/speaking from real events IMPLEMENTED, VERIFIED; barge-in, cancel, minimised IMPLEMENTED, VERIFIED; speech never authorises IMPLEMENTED, tested (NOT VERIFIED with an open approval card); voice presentation commands IMPLEMENTED (name sometimes misheard); drafting by voice NOT IMPLEMENTED (waits for the TI draft desk on canonical); human-talker run NOT VERIFIED (owner away). ACCEPTED (Codex live-voice round 4 ACCEPT WITH FINDINGS); INTEGRATED into `integration/git-sync-20261008` (receipt `docs/voice/live/INTEGRATION_RECEIPT.md`); not deployed | `docs/voice/live/LIVE_VOICE_REPORT.md`; `docs/voice/live/LIVE_VOICE_AUDIT.md` | TI drafting wiring; own-voice session; start order vs Runtime v1 VRAM (measured demotion) | TI on canonical | **yes** (start order; voice packs) | wire drafting when TI lands |
| Interactive Brain / capability visualization | show executors, qualification, policy, grants | DESIGN ONLY (data sources named) | `PHASE2CLOSE_UI_READINESS.md` section 2 | read-only API contract + design | P2-6 | design approval | design phase |
| Guided onboarding (roles, providers, models, permissions, connection, auth, readiness) | first-run path to a ready installation | PARTIAL: legacy onboarding screens IMPLEMENTED (Phase 1 line); Phase 2 readiness checks exist as scripts | `screens/onboarding/*`; `scripts/phase2close_acceptance.py preflight` | onboarding over preflight/discover/qualify; roles definition | C6 decision 1, EXE-1 | yes | design phase |
| Approval/progress/cancel/recovery/receipt presentation | clear, honest execution UX | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (supervised screen) | `supervised_execution_screen.dart`; widget tests | extraction to shared widgets | next UI phase | none | next UI phase |
| Pinned UI release build | `ui_binary` + `ui_sha256` in the client manifest | PLANNED | `C6_UI_INTEGRATION_CONTRACT.md` | build + pin | C7 | at cutover | C7 slice |
| Development-line reconciliation (P2-6) | one tree to ship | RESEARCHED: recommendation = Core lineage (`integration/git-sync-20261008` + accepted OQ candidate); `_V1`/`eb73693` as donors | `PHASE2OQ_SHIPPING_LINE_RECOMMENDATION.md` | owner decision; A11 sync | git-sync work | **yes** | owner |

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

See `PHASE2CLOSE_C7_READINESS.md` (gates 1-10 + P2-1..P2-11; section 7 = operational-qualification update). Summary:
gates 1-2 MET (Phase 1), 3/4/9 PARTIAL, 5/8 NOT MET, 6/10 NOT AUTHORIZED/REQUESTED, 7 PROCEDURE ONLY. Verdict NOT READY.

## 5. Repository, runtime and PC consolidation (added 2026-10-08)

Source: `docs/governance/consolidation/` (plan, PC audit, branch decision, salvage ledger, verification report) and
`docs/governance/URI_RUNTIME_AUTHORITY_MANIFEST.json`. Evidence root `C:\Users\cheta\Development\uri-canonical-evidence\`.
Note: the Phase 2 worktree keeps its own copy of this ledger; reconcile the two copies when the canonical line is promoted.

| Item | Goal | Status | Evidence | Outstanding | Depends on | Owner decision | Next step |
|---|---|---|---|---|---|---|---|
| CONS-1 legacy scheduled task `\URIServer` | no legacy server at logon | QUARANTINE PREPARED (`scripts/uri_containment.ps1`, plan only) | PC audit F-1 | apply | — | **yes** | `-Apply` |
| CONS-2 `URI.lnk` shortcuts to the donor desktop | no donor launch by click | QUARANTINE PREPARED | PC audit F-3 | apply | CONS-1 | **yes** | `-Apply` |
| CONS-3 stop the running legacy server | free 8000; end legacy writes | PLANNED | PC audit F-1 | timing | CONS-1 | **yes** | owner chooses time |
| CONS-4 authoritative install dir, state root, port | provisioned C1 server + client | PLANNED | plan section 7 P-4 | provisioning | CONS-1..3 | **yes** | provision |
| CONS-5 shared UI preferences (`com.example/uri_ui`) | per-installation client storage | DESIGN ONLY (C3/C6 item) | PC audit F-2 | implementation | C6 | design approval | C6 slice |
| CONS-6 runtime authority check + start gate | detect/refuse unauthorized runtimes | IMPLEMENTED, TESTED (adversarial tests; live run) | verification report | wire into installed launch path at cutover | CONS-4 | at cutover | — |
| CONS-7 frozen `HEAD == e8e3b65` coupling | run the Core from a committed canonical branch | BLOCKED (frozen Core file) | branch decision section 3 | change `runtime_identity.py` + Phase 2 base tests | owner | **yes** | keep materialization or unfreeze |
| CONS-8 canonical branch promotion | `main` = Core lineage, default branch | CANDIDATE BUILT, VERIFIED | branch decision; verification report | push + default change | — | **yes** | plan P-1, P-6 |
| CONS-9 donor reconciliation (desktop features, M36/M37/M39, dynamic planning, dictation, harness console, voice) | parity before retiring the installed desktop | PLANNED (= P2-6) | salvage ledger sections 2-3 | per-capability port with provenance | C5-C7 | **yes** (priority order) | owner picks first donor |
| CONS-10 historical branch / worktree retirement | fewer competing lines | PLANNED | branch decision section 5 | archive tags, deletion | CONS-8 | **yes** per item | — |
| CONS-11 NVMe model copy, `.tmp_m33` worktree | remove duplicates | PROPOSED DELETION | salvage ledger section 4 | hashes identical to pinned copy | — | **yes** | — |
| CONS-12 vault restore drill | proven recovery from `D:\URI-preservation` | PLANNED | salvage ledger section 5 | test restore to a scratch path | — | none | schedule |
| CONS-13 secret ACL hardening | Codex sandbox cannot read URI secrets | DONE (33 files, reversible) | PC audit section 4 | secrets created later inherit again | — | none | re-run after cutover |
| CONS-14 Phase 1 provisional checkpoints `work/c1/checkpoints` (11 MB) | fresh-clone reproducibility of `test_phase1_offline_components` | LOCAL ONLY (Phase 1 integration worktree) | verification report section 1.1 | preserve on GitHub | — | **yes** (push) | preserve branch |
| CONS-15 Phase 2 OQ `-g` in Git | accepted Phase 2 tree recoverable from GitHub | LOCAL GIT IMPORT DONE (byte-exact `6dea266`, evidence `fcb619a`, records `759d0d4`; local tag `accepted/phase2-oq-g-0b49d86d`); GitHub recoverability PENDING the push and fresh-clone check | `URI_SOURCE_OF_TRUTH_MANIFEST.md` | push | — | none (authorized) | — |
| CONS-16 runtime materialization for OQ `-g` | runtime checkout = accepted tree | DONE (`RUNTIME_OVERLAY_PHASE2OQ_G.txt`, 273 paths; runtime candidate rematerialized) | `URI_RUNTIME_BUILD_AND_ROLLBACK_RUNBOOK.md` | — | — | none | — |
| CONS-17 Runtime v1 ~140 tok/s recovery | identify and reproduce the reported AMD result | RECOVERED (Runtime v1 MTP; artifacts hash-verified; reproduction 2026-10-08) | `URI_INFERENCE_OPTIMIZATION_RECOVERY.md` | Core wiring = Operational Intelligence milestone | owner | **yes** (start OI) | — |
| CONS-18 Ollama autostart | no unexpected model service | RECORDED (shared tool, idle, Startup shortcut, update pending) | `URI_CLEANUP_AND_QUARANTINE_MANIFEST.md` §1 | optional removal | — | optional | — |

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
| 2026-10-08 | SUP-1 | RECORDED (Low) | IMPLEMENTED, TESTED (operational qualification) | `tests/phase2oq/test_sup1_self_containment.py` |
| 2026-10-08 | EXE-1 | BLOCKED (owner decision) | owner approved; IMPLEMENTED, TESTED (native binaries; REAL worker fails closed without login; worker-env lifecycle) | `PHASE2OQ_REPORT.md` section C; `E:phase2oq\` |
| 2026-10-08 | EXE-1b, OQ-1, CODEX_HOME invariant | (not known) | found in EXE-1 work; IMPLEMENTED, TESTED; EXE-1b needs the owner | report sections C |
| 2026-10-08 | D8 power-method check | RECORDED (Low) | IMPROVED: guest OS unclean-shutdown witness required per iteration; attestation still required | `tests/phase2close/test_powerloss_harness.py::test_d8_*` |
| 2026-10-08 | C6 decision 2 | recommendation B, BLOCKED on owner | owner chose B; Chat action IMPLEMENTED, TESTED | `PHASE2CLOSE_C6_CHAT_INTEGRATION.md` section 9 |
| 2026-10-08 | C6 decision 1 | BLOCKED on owner | RESOLVED AS A DEFINITION (no authority effect) | report section D |
| 2026-10-08 | P2-6 line reconciliation | PLANNED | RESEARCHED, recommendation made | `PHASE2OQ_SHIPPING_LINE_RECOMMENDATION.md` |
| 2026-10-08 | Operational qualification (EXE-1, OQ-1, SUP-1, D8, C6 Option B, tooling, gate hardening) | IMPLEMENTED, TESTED | INDEPENDENTLY ACCEPTED (Codex OQ round 7 on `-g` 0b49d86d...c4cd after rounds 1-6 rejected); physical gates PENDING | `E:phase2oq_review\round7\` |
| 2026-10-08 | CONS-1..CONS-14 | (not tracked) | consolidation items added; CONS-6 IMPLEMENTED, TESTED; CONS-13 DONE | `docs/governance/consolidation/` |
| 2026-10-08 | CONS-15..CONS-18 | (not tracked) | round 2: Phase 2 OQ `-g` imported and rematerialized; Runtime v1 recovered and reproduced; Ollama origin recorded | `docs/governance/consolidation/URI_CONSOLIDATION_FINAL_AUDIT_20261008.md` |
| 2026-10-09 | Companion visual, voice and settings | DESIGN ONLY (Companion UI) | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (Codex rounds 1-2 REJECT, 3 ACCEPT WITH FINDINGS, 4 ACCEPT; integration ACCEPT WITH FINDINGS), INTEGRATED (fast-forward of `integration/git-sync-20261008`); live voice deferred; not deployed | `docs/companions/settings/INTEGRATION_RECEIPT.md` |
| 2026-10-09 | Live voice (capture, recognition, spoken replies, companion states) | NOT IMPLEMENTED (simulated only) | IMPLEMENTED, VERIFIED (synthetic talker), ACCEPTED (Codex rounds 1-3 REJECT, 4 ACCEPT WITH FINDINGS), INTEGRATED; drafting by voice NOT IMPLEMENTED; human-talker NOT VERIFIED | `docs/voice/live/LIVE_VOICE_REPORT.md` |
