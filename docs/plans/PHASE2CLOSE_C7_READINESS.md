# C7 cutover readiness assessment (Phase 2 closure)

Date 2026-10-08. Author: Claude (self-assessment; not an independent review). Basis: `C7_CUTOVER_REQUIREMENTS.md`
(gates 1-10, procedure, stop conditions), the Phase 2 reports (2A-2D, UI/operations rounds 1-7) and the closure work
recorded in `PHASE2CLOSE_REPORT.md`. **Verdict: NOT READY FOR CUTOVER. Nothing was cut over, activated or authorized.**

## 1. Acceptance criteria for this assessment

1. Every C7 gate gets a state backed by a named artifact, or is marked with what is missing.
2. Phase 2 adds its own gates where Phase 2 changes what a cutover would ship; they are listed separately.
3. Each open item names its owner (automation, owner action, owner decision) and its next step.
4. No gate is marked met because a document or a prototype exists.

## 2. The ten C7 gates

| # | Gate (abridged) | State | Evidence / what is missing | Owner of next step |
|---|---|---|---|---|
| 1 | Independent final acceptance audit of the Phase 1 tree | MET for Phase 1 | `PHASE1_FINAL_CLOSURE_REPORT.md` section 10: "A. PHASE 1 CORE FREEZE ACCEPTED" (2026-10-05); frozen zip `31a34dcb...efeb98cf7` re-verified byte-identical by `tests/phase2a/test_frozen_core.py` | none for Phase 1; a cutover of Phase 2 needs its own final audit (P2-1) |
| 2 | C1 identity and source pin accepted, incl. bootstrap import gate | MET | same report, N2 "ACCEPTED" | none |
| 3 | C5 Brain activation policy reviewed (which rows the launched server composes, real local model evidence) | PARTIAL | Phase 2D policy FILE for the Phase 2 server profile accepted (Codex round 3) for harness rows; no Brain (local model) row is composed (`lazy-not-selected`); no review of a Brain activation | owner decision (C6 decision 3) + review |
| 4 | Native harness qualification: client-owned login, containment, live smoke, `qualify` with evidence | NOT MET | Codex NATIVE QUALIFIED only run-scoped in-process under the owner's shell login (2C/2D/ops); worker-process path blocked by EXE-1; client-profile login not done (PA-8/PA-9); ISO-1 fixed so a shared login can no longer qualify a client | owner decision EXE-1, then owner login (runbook PA-8..PA-10) |
| 5 | C6: Chat connected, pinned UI build in the client manifest, voice parity decided | NOT MET | Chat not connected (owner decision 2, recommendation B in `PHASE2CLOSE_C6_CHAT_INTEGRATION.md`); no `ui_binary`/`ui_sha256` pin; voice parity undecided; the voice work lives on the `_V1` line (see P2-6) | owner decisions; then a UI slice |
| 6 | Owner map and key lineage, copy-first migration rehearsal | NOT AUTHORIZED | no change | owner |
| 7 | Every `execution_uncertain` turn reconciled by the user, none replayed | PROCEDURE ONLY | procedure defined in Phase 1; Phase 2 records are reconciled to `uncertain` and never relaunched (tests); no production data touched | owner, at cutover time |
| 8 | Fresh checkpoint of the final tree + offline rollback rehearsal from that archive | NOT MET for Phase 2 | `scripts/phase1_offline_rollback.py` covers the Phase 1 source set only (`SOURCE_ROOTS` excludes `uri_supervisor`, `uri_supervisor_bridge`, `uri_ui`); a Phase 2 overlay rollback is not implemented | automation (P2-5), after the final tree is fixed |
| 9 | The 11 full-suite failures triaged, each fixed or explicitly accepted | PARTIAL | the 11 IDs are the same set on every run (`SAME_FAILURE_SET`, `phase2close_chain.py`); none fixed; not explicitly accepted by the owner | owner acceptance or a repair slice |
| 10 | Written cutover authorization naming manifests, ports, launch entries | NOT REQUESTED | none | owner |

## 3. Phase 2 additions (what a Phase 2 cutover would ship)

| ID | Item | State | Evidence | Next step |
|---|---|---|---|---|
| P2-1 | Independent acceptance of the Phase 2 closure changes (LOG-3, VAL-1 resend, CAP-1, ISO-1, handoff seam, harness, scripts) | PENDING | this closure's candidate; Codex review attempted per `PHASE2CLOSE_REPORT.md` section on review | Codex review round(s) |
| P2-2 | Human click on the real app (approve, deny, cancel, reopen) | PENDING (owner physical) | runbook PA-1..PA-7 | owner session |
| P2-3 | Controlled power loss | PENDING (owner VM) | harness ready (`scripts/phase2close_powerloss_harness.py`), SIMULATED plumbing passes; runbook PA-11 | owner VM campaign |
| P2-4 | Native execution inside the worker process | BLOCKED | EXE-1 (below) | owner decision |
| P2-5 | Phase 2 rollback overlay (supervisor, bridge, Phase 2 scripts, UI files) | NOT IMPLEMENTED | gate 8 | automation slice |
| P2-6 | Reconcile the two development lines | NOT STARTED | the Phase 2 tree is `e8e3b65` + uncommitted Phase 1/2 work; `C:\Users\cheta\Development\Uri\_V1` is 62 commits ahead of `e8e3b65` on `codex/antigravity-harness-recon` with further uncommitted UI work (voice strip, desktop harness, compact window). A cutover ships ONE tree | owner decision on the target line; then an integration plan |
| P2-7 | Which worker profile a production launcher starts (frozen worker vs `run_uri_supervised_worker.py`) | DESIGN ONLY | the supervised profile is opt-in per installation (`ui-supervised-profile.json`); the frozen launcher still starts the frozen worker | owner decision at cutover |
| P2-9 | SUP-1: a supervisor killed during `CreateProcess(CREATE_SUSPENDED)` can leave a suspended, never-resumed child outside its job (Low; no effect) | RECORDED | Codex closure round 1 K1; two occurrences in SIMULATED tests | Phase 2A hardening: atomic job assignment |
| P2-8 | VAL-1 | CAUSE ESTABLISHED (mechanism), historical instance not attributable | `tests/phase2ops/test_val1_clock_boundary.py`; bounded resend | physical sessions keep the refusal log; any `TICKET_CLOCK_OR_GENERATION` line is now explained |

## 4. EXE-1: how the worker should launch node-based CLIs (owner decision)

Observed 2026-10-08: with the worker's sanitized PATH (venv, System32, git) `codex.CMD --version` fails with
`"node" is not recognized`; `claude.CMD --version` works. The real worker's `harness_discover` reports both CLIs
`NOT_INSTALLED` because they are not on that PATH, and a client Codex record is not composed.

| Option | What changes | Trust effect | Recommendation |
|---|---|---|---|
| A. Pin the interpreter too | the qualification record pins `node.exe` (path + SHA-256) beside `codex.CMD`/`codex.js`; the executor is launched as `node.exe <pinned codex.js>`; PATH stays sanitized | narrowest: one more pinned, hashed file | **recommended** |
| B. Add the CLI's and node's directories to the executor PATH | worker PATH gains two directories | wider: anything in those directories becomes launchable by name | not recommended |
| C. Require standalone native binaries | no node; only CLIs shipped as single executables qualify | narrow, but Codex's npm distribution would not qualify | fallback if A is rejected |
| D. Stay blocked | native execution only in-process (current evidence) | none | acceptable only while cutover is not wanted |

## 5. ISO-1 (repaired in this closure, recorded here because it is a C7 stop condition)

C7 stop conditions include "using shared client authentication". Codex 0.158.0 ignores `USERPROFILE`, so the
sanitized client profile alone would have let any Codex executor of a client use the owner's global login (observed
live: "Logged in using ChatGPT" with only the profile variables overridden). The worker now pins `CODEX_HOME` to
`<client_root>/home/.codex` (`qualification.client_cli_homes`, `scripts/run_uri_supervised_worker.py`); the live
test `tests/phase2close/test_iso1_cli_home.py` observes the leak without the pin and "not logged in" with it. The
in-process native evidence of Phase 2C/2D/ops used the owner's shell login by design ("run-scoped shell
authentication") and remains valid as what it says it is, not as worker-process evidence.

## 6. Verdict and order of work toward cutover

NOT READY. Shortest defensible order: (1) independent review of the closure changes (P2-1); (2) owner session for
PA-1..PA-7 (no login needed for the deterministic row); (3) owner decision on EXE-1 and implementation of option A;
(4) client-profile logins and PA-8..PA-10; (5) VM power-loss campaign (PA-11); (6) owner decisions on C6 (2, 3, voice)
and on the target development line (P2-6), then the integration slice; (7) Phase 2 rollback overlay (P2-5) on the
final tree; (8) owner acceptance of the 11 baseline failures or their repair; (9) written authorization (gate 10).

## 7. Update 2026-10-08 (Phase 2 operational qualification, `PHASE2OQ_REPORT.md`)

Sections 1-6 are kept as written at closure acceptance. **Verdict unchanged: NOT READY FOR CUTOVER.** Nothing was cut
over, activated, frozen or authorized.

**Correction record (section 4).** Option C said "Codex's npm distribution would not qualify". That was wrong: the npm
package ships the native binary (`vendor\x86_64-pc-windows-msvc\bin\codex.exe`), and `codex.js` only spawns it. EXE-1
was resolved with that observation (a fifth option, narrower than A: qualify the native binary; no interpreter, no PATH
change). Option A (pin `node.exe`) was not needed.

| Gate / item | Closure state | Now | Evidence | Next step |
|---|---|---|---|---|
| Gate 4 native harness qualification | NOT MET | PARTIAL: the worker-process path is proven up to authentication (native record composes in the REAL worker; a not-logged-in profile is refused before approval); the worker-environment lifecycle and cancel pass against a scripted model; client-profile login (PA-8/9) and EXE-1b open | `E:phase2oq\` native-worker gate; `tests/phase2oq/test_exe1_native.py` | owner: EXE-1b, PA-8..PA-10 |
| Gate 5 Chat / UI pin / voice | NOT MET | still NOT MET as a gate (Chat traffic stays on `/ask`; no UI pin; voice parity open). Progress: Option B handoff implemented and widget-tested; voice parity rules proposed | `PHASE2CLOSE_C6_CHAT_INTEGRATION.md` section 9; `PHASE2OQ_UI_VOICE_ACCEPTANCE_PLAN.md` | owner: PA-13, voice rules, line choice |
| P2-1 independent acceptance | PENDING (closure accepted round 6) | closure ACCEPTED; operational-qualification candidate review PENDING | `E:phase2oq_review\` | Codex review |
| P2-3 power loss | PENDING (owner VM) | PENDING; rig method chosen (VirtualBox 7, flush-honouring disk, NAT), guest bundle built, D8 witness required | runbook PA-11; `scripts/phase2oq_powerloss_bundle.py` | owner installs a hypervisor + VM |
| P2-4 native execution in the worker | BLOCKED (EXE-1) | PENDING (EXE-1 resolved; EXE-1b and the client-profile login remain) | report section C | owner |
| P2-6 line reconciliation | NOT STARTED | RECOMMENDATION: ship from the Core lineage; `_V1` and `eb73693` are donors | `PHASE2OQ_SHIPPING_LINE_RECOMMENDATION.md` | owner decision |
| P2-9 SUP-1 | RECORDED | IMPLEMENTED, TESTED (self-containment job; real-process negative control) | `tests/phase2oq/test_sup1_self_containment.py` | review |
| P2-10 (new) EXE-1b Codex sandbox backend of the client profile | — | OWNER DECISION: `unelevated` confines writes but NOT network (measured); `elevated` needs administrator setup | `E:phase2oq\sandbox_probes\README.md` | owner |
| P2-11 (new) OQ-1 approval for an unusable executor | — | IMPLEMENTED, TESTED (refused before the approval leaves the worker) | `tests/phase2ops/test_lifecycle.py` (disclosed assertion change), widget tests | review |

Shortest order now: (1) independent review of the operational-qualification candidate; (2) owner session PA-1..PA-7 and
PA-13; (3) EXE-1b and PA-8..PA-10; (4) PA-11 on a VM; (5) shipping-line decision and the A11 sync of the accepted
candidate; (6) C6 decision 3, voice rules; (7) rollback overlay on the final tree; (8) the 11 baseline failures; (9)
written authorization (gate 10).
