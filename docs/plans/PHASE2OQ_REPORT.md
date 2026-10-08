# Phase 2 operational qualification report

Date 2026-10-08. Author: Claude (lead implementer and self-auditor; this is NOT an independent review). Worktree
`C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent`, detached at `e8e3b65`, uncommitted. Evidence root `E:` =
`C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\`. Builds on the accepted closure candidate
`E:phase2close-candidate-20261008-f.zip` (SHA-256 `fcd0d72e0cd91412c361edec9114e2edaebbf70ede052046b808f3c4fc571298`,
Codex closure round 6), which is unchanged and treated as an immutable reference.

**Nothing was committed, pushed, merged, frozen or cut over. No owner credential was read, copied or used for a client.
No power was cut on this PC.**

**Implementer's verdict (not independent): candidate ready for owner physical acceptance, pending the independent review
of this slice (`E:phase2oq_review\`). Phase 2 is NOT qualified: PA-1..PA-13 and the owner decisions in section J are
open. The final chain's phase1-full gate deviates for an environmental reason (section H).**

## A. Acceptance criteria (set before the work)

1. The accepted baseline (closure `-f`, frozen Phase 1 checkpoint, six Codex closure rounds) is verified and unchanged;
   new work gets its own candidate and evidence.
2. EXE-1: native Codex runs inside the real worker with verified executable identity, client-profile isolation, no
   silent `CODEX_HOME` fallback, no PATH widening, no arbitrary executable authority, unchanged approval/ticket/cancel/
   recovery rules, lifecycle exercised in the actual worker process, and an explicit refusal when qualification fails.
   Any genuine authority expansion stops at the smallest owner decision.
3. C6 Option B (owner accepted): the user's message becomes an unsent text-only draft; nothing is sent or executed;
   executor choice, confirmation and approval stay explicit; the screen shows the draft and its next action;
   abandonment, cancellation, restart, stale state and return navigation behave; preparing a draft never authorizes.
4. C6 decisions 1-3 are reviewed against their documents; anything touching authority, permissions or consent stays
   pending.
5. Voice parity and UI acceptance: implemented / partial / missing per area, with an actionable plan; no mockup or
   simulation is presented as device evidence.
6. PA-1..PA-11 (+ new) are prepared with minimal owner effort; client-profile authentication never copies or silently
   uses another identity; installed, authenticated, qualified and operational stay distinct; the power-loss method needs
   no Hyper-V and never touches this PC.
7. SUP-1 and D8 are repaired or dispositioned; LOG-3, VAL-1, CAP-1, ISO-1 are re-checked for regression.
8. A shipping-line recommendation from evidence, coordinated with the git-sync work, with no merge.
9. Every completion claim cites `COMPLETED_WITH_RESULT` evidence; statuses PLANNED -> IMPLEMENTED -> TESTED ->
   INDEPENDENTLY ACCEPTED -> PHYSICALLY QUALIFIED -> FROZEN -> DEPLOYED are never merged.

## B. Baseline (verified 2026-10-08 ~08:45 IST)

* `-f` zip SHA-256 re-computed: `fcd0d72e…71298` (matches). Frozen Phase 1 checkpoint: `tests/phase2a/test_frozen_core.py`
  8 passed. HEAD `e8e3b65`. All six closure review rounds present under `E:phase2close_review\round1..6`.
* Worktrees: 14 (same set as the git-sync audit). The git-sync session had already pushed (owner-authorized) seven
  branches; its integration branch holds the closure `-f` bytes (A7-A9). Nothing of that session's files was touched;
  this work lives only in the Phase 2 worktree and `E:phase2oq\`.
* **Correction to the closure delivery report:** it said "no leftover processes". A suspended `fake_executor.py`
  (PID 3044, created 08:04 by `test_replay_agrees_with_a_real_campaign_output`, parent gone) was still present. Recorded
  in `E:phase2oq\sup1_orphan_observed_20261008.json` (thread state Wait/Suspended), then killed. It was a live SUP-1
  instance and is the reason SUP-1 was repaired in this slice (section F).

## C. EXE-1: native Codex inside the worker (resolved without new execution authority)

**Research.** `codex.CMD` runs `node codex.js`; `codex.js` 0.158.0 only resolves the platform package's native binary
`node_modules\@openai\codex\node_modules\@openai\codex-win32-x64\vendor\x86_64-pc-windows-msvc\bin\codex.exe` and spawns
it, adding `CODEX_MANAGED_PACKAGE_ROOT` and `CODEX_MANAGED_BY_NPM` (update hints only). `claude.cmd` already launches the
native `claude.exe` directly. Under the worker's PATH (venv, System32, git) both native binaries run (`--version`
0.158.0 / 2.1.287; `preflight` field `version_sanitized_env`).

**Decision (better than the recommended node pin).** Qualify the native binary itself: no interpreter is admitted
(pinning `node.exe` would admit a general script host), the PATH is not widened, nothing is resolved by name.
* `qualification.codex_native_launch_chain`: pins the binary, its layout descriptor `codex-package.json` (layoutVersion 1,
  entrypoint, target triple checked) and every `.exe`/`.dll` of its vendor directory (33 files here: command runner,
  sandbox setup, code-mode host, `rg.exe`, voice libraries); `resolve_pins` empty. Unknown layout -> refused.
* `qualification.native_executable` maps the npm launchers to their native binaries; `phase2c_native_qualification.
  direct_probe(executable=...)` and `phase2close_acceptance.py qualify` probe and record the native binary.
* Worker-only invariant `check_codex_client_home` (composition AND every execution via `still_valid`): the executor
  environment must name `<client_root>\home\.codex` (absent = Codex would silently fall back to the Windows user's
  global login -> `CODEX_HOME_NOT_CLIENT_PROFILE`), and a NATIVE Codex record needs a Windows sandbox mode in that home
  (`CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED`).
* A `.cmd` Codex record still fails closed in the worker (`LAUNCH_CHAIN_RESOLUTION_CHANGED`: `node` cannot resolve).

**Second blocker found and handled: the Codex Windows sandbox backend (EXE-1b, owner decision).** A fresh Codex home
has no sandbox mode; Codex then refuses every command of a `workspace-write` run ("rejected: blocked by policy"), so a
qualified worker would still never produce a result. Probes (`E:phase2oq\sandbox_probes\README.md`):
`unelevated` (no setup) confines writes to the workspace (verified both ways) but does **not** confine network (a
sandboxed command reached localhost and `example.com`, HTTP 200). `elevated` needs a one-time administrator setup by
Codex and, per Codex's own messages, restricts network; not tested here. Because the choice decides whether a client
executor has network access, it is the owner's (smallest decision: pick the backend). Implementation: the worker
refuses until a mode is set; acceptance provisioning sets one only when the owner passes `--codex-sandbox`.

**OQ-1 (found while testing EXE-1).** The worker showed an approval card for a qualified but not-logged-in executor;
approving would have sent the approval and only then failed at dispatch. Now `execution_proposal` carries the LIVE
usability (`harness`: usable, auth_state, required_user_action) and `execution_begin` refuses `HARNESS_NOT_USABLE`
before the approval leaves the worker, releasing the turn on the server (CAP-1 route). The UI disables Approve and
shows the required action. One accepted assertion changed (disclosed in the test): `tests/phase2ops/test_lifecycle.py::
test_unqualified_provider_fails_closed_before_any_task` (was: approved, dispatched, refused by the bridge; now: refused
before approval, turn `cancelled`, nothing approved).

**Evidence, REAL worker process** (`scripts/phase2oq_native_worker.py`, `E:phase2oq\native_try2\`, chain gate
`native-worker`): server and worker processes under the frozen manifests, native `codex.exe`, client-profile Codex home
pointing at a SCRIPTED local endpoint (127.0.0.1; no model, no login):
* W: record composes `QUALIFIED` (33 pinned files, no resolve pins); `harness_discover` -> codex `NOT_AUTHENTICATED`,
  usable false, required action shown; Approve -> `REFUSED HARNESS_NOT_USABLE`; server turn `cancelled`; no execution.
* W2: no sandbox mode -> `INVALIDATED CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED`. W3: `codex.CMD` record -> `INVALIDATED
  LAUNCH_CHAIN_RESOLUTION_CHANGED` (resolve pin `node` -> `C:\Program Files\nodejs\node.exe` not on the worker PATH).
* L (worker ENVIRONMENT, one substitution: the live auth gate answers True for codex_cli): `completed` /
  `SETTLED_VERIFIED`, `pong.txt` = `PONG` written by the sandboxed PowerShell; mid-run cancel while a sandboxed
  `Start-Sleep 600` ran -> `uncertain` / `CANCELLED_AFTER_DISPATCH`, attempt PID `DEAD`, 0 surviving processes.
* Every model request reached the scripted endpoint (the client-profile config was used); no `auth*` file exists in
  the client Codex home.

**What this does NOT prove:** a real model, a real login, or PA-10. PA-10 needs the owner's client-profile login (PA-8)
and EXE-1b. The earlier in-process REAL-model evidence (owner shell login, run-scoped) remains what it says it is.

## D. C6 Chat integration (Option B, owner accepted) and decisions 1-3

Implemented (Flutter, additive): `widgets/supervised_handoff_action.dart` mounted under each turn in the Chat pane
(`ask_uri_screen.dart`, one `Column` wrap + one constructor flag); `TaskHandoff` now keeps the user's words whole
(trim only) and refuses an over-limit message instead of truncating it (closure behaviour changed; test updated and
disclosed); the supervised screen shows the draft banner, an "Edited since it left the conversation" note, a
`sx-next-action` line for every state, and keeps a draft without sending when a run is still in flight
(`sx-draft-busy`).
Boundaries: action only for opted-in installations, only on a non-empty user message, hidden while that Chat turn is
being understood, awaiting its own approval or executing (one request never sits in two approval paths); tapping only
navigates; nothing reaches `/ask` or the worker; the supervised session id is never the conversation's; drafts are
memory-only (restart resurrects nothing). Tests: `uri_ui/test/supervised_execution_screen_test.dart` (9 new + 1 updated
cases incl. abandonment via Back, restart, stale run, too long, OQ-1) and `uri_ui/test/chat_supervised_handoff_test.dart`
(the real Chat pane with `AppState`: action only when opted in, rendering sends nothing). Physical: PA-13 (new).

Decision 1 ("Companion", "Intelligence"): RESOLVED AS A DEFINITION, no authority change, reversible. Grounded in
existing owner decisions: "Intelligence" = the intelligence policy mode (`EDGE_ONLY`, `HYBRID`, `MAIN_BRAIN_PREFERRED`,
owner decision D2 of 2026-09-26; a routing preference), "Companion" = the Compact/desktop-companion PRESENTATION of the
same session (M26 "Desktop Companion", frozen blueprint Compact mode). Neither is an authority-bearing role; both are
UX per `SERVER_CLIENT_OWNERSHIP.md`. Owner may override.
Decision 3 (Brain rows): PENDING. Offering a Brain row changes who reasons over the user's requests and which rows the
server composes (C5 policy, C7 gate 3); it is an authority/consent decision.

## E. Voice parity and UI acceptance

`docs/architecture/PHASE2OQ_UI_VOICE_ACCEPTANCE_PLAN.md`: per-area status (Phase 2 tree vs `_V1`), voice rules (a
spoken request becomes an unsent `TaskHandoff(source: 'voice')`; voice never approves; voice-cancel and wake behaviour
are owner decisions), acceptance steps and order. Voice infrastructure exists only on `_V1` (uncommitted, "awaiting
user test" by its own report): BLOCKED on line reconciliation here.

## F. Defects

* **SUP-1 REPAIRED.** `winproc.contain_current_process()`: the process hosting a `Supervisor` joins an unnamed
  kill-on-close job it alone holds, before any spawn. Children of a job member are members from creation (no breakaway
  flags anywhere), so a supervisor death inside the suspended-spawn window now kills the child. Attempt jobs nest under
  it (Windows 8+); ledger, recovery and identity are unchanged; no authority is added. Tests
  (`tests/phase2oq/test_sup1_self_containment.py`, REAL processes): negative control reproduces the orphan; with
  containment the suspended child dies with its host.
* **D8 IMPROVED, attestation still required.** The guest reports its own System-log unclean-shutdown events
  (Kernel-Power 41 / EventLog 6008) and boot time at every boot; `assess` requires, for every VM iteration, such an event
  created after that boot's `ready` (guest clock). A guest shutdown/reboot or a host that never cut anything cannot pass.
  It still cannot prove the HYPERVISOR cut THIS VM; `qualified` stays false. Tests updated/added; the witness query ran
  read-only on this PC (it lists the 2026-10-06 and 2026-10-07 unclean shutdowns of this machine).
* LOG-3, VAL-1, CAP-1, ISO-1: their tests ran unchanged in the chain (section H).
* **Correction (self-inflicted, reversed):** a line-ending normalization I ran converted 151 git-ignored runtime JSON
  files (Phase 1 test outputs under `tmp_m33_c2_pytest\`, `temp_evidence\`, `uri_workspace\`) from CRLF to LF; I
  restored them to CRLF minutes later. Content was unchanged; none is tracked or part of any candidate.

## G. Physical acceptance preparation

Runbook updated in place (`PHASE2CLOSE_PHYSICAL_ACCEPTANCE_RUNBOOK.md`, dated header): `login-guide` (prints, never
runs, an isolated native login), `status` (INSTALLED / AUTHENTICATED / QUALIFIED / OPERATIONAL, each from its own
evidence), `provision --codex-sandbox`, PA-10 rewritten, PA-11 VirtualBox 7 method (host I/O cache off, flushes
honoured, NAT 10.0.2.2, stock Python guest, D8 witness), new PA-13. Preflight now reports the native executables and
the VM tooling present (none here; Windows hypervisor present).

## H. Regression (one sequential chain on the final tree: `E:phase2oq\chain2\`)

`chain1` was aborted by me in its first gate to apply two planned script changes first (`E:phase2oq\chain1\ABORTED.txt`);
nothing from it is used. `chain2` ran every gate on the final code; afterwards only documents changed.

| Gate | Result | Expected | Verdict |
|---|---|---|---|
| phase2 (all Phase 2 suites incl. `tests/phase2oq`) | 470 passed, 2 skipped, 0 failed | 0 failed | PASS |
| authority | 134 passed | 134 | PASS |
| phase1-full | 2676 passed / 5 skipped / **17 failed** | 2675 / 12 / 11, same IDs | **FAIL (environmental, see below)** |
| residue | nothing to remove | — | PASS |
| flutter | 205 passed, 2 skipped | all pass | PASS |
| bridge x10 (live Dart -> worker -> server) | 10/10, 0 refusal lines | 10/10 | PASS |
| native (REAL Codex, in-process, owner shell login, `.CMD` path) | completed/`SETTLED_VERIFIED`; cancel uncertain/`CANCELLED_AFTER_DISPATCH`, PID DEAD | same | PASS |
| native-worker (REAL worker, native `codex.exe`, scripted model) | W refused `HARNESS_NOT_USABLE`; W2/W3 invalidated as expected; L completed/`SETTLED_VERIFIED`, cancel uncertain/`CANCELLED_AFTER_DISPATCH`, PID DEAD, 0 survivors | same | PASS |

Chain verdict as recorded: **`CHAIN_FAILED`** (phase1-full). Cause, established: an Ollama service
(`C:\Users\cheta\AppData\Local\Programs\Ollama\ollama.exe`, started 2026-10-08 09:42 IST, not by this work and not
stopped by it) began listening on 11434 between the closure chain and this one. Seven live tests that skip when Ollama is
unreachable then ran: six fail with `ModelNotFoundError: Model 'qwen3:14b' was not found on this Ollama server`, one
(`test_gemma_worker_mcp.py:329`) passes. Control (`E:phase2oq\chain2b_phase1_ollama_unreachable\`, same tree, only
`OLLAMA_BASE_URL=http://127.0.0.1:9`): 2676 passed / 11 skipped / 11 failed, `SAME_FAILURE_SET` true; the single
remaining difference from the baseline is `test_gemma_worker_mcp.py:329`, which hard-codes `127.0.0.1:11434` (ignores
the variable) and therefore passed against the running Ollama. No file under test changed for these suites. I record the
chain as failed by its own rule and the deviation as environmental; the independent reviewer decides whether that is
acceptable.

LOG-3, VAL-1 (resend), CAP-1, ISO-1: their tests are in the phase2 gate (470 passed). Frozen boundary:
`test_frozen_core.py` passed inside it.

## I. Status matrix (PLANNED -> IMPLEMENTED -> TESTED -> INDEPENDENTLY ACCEPTED -> PHYSICALLY QUALIFIED -> FROZEN -> DEPLOYED)

| Capability | Highest status reached | Not yet |
|---|---|---|
| Native Codex in the worker (EXE-1) | TESTED (real worker up to auth; worker-env lifecycle with scripted model) | independent acceptance; PA-8/PA-10 (physical); EXE-1b decision |
| CODEX_HOME / sandbox invariants | TESTED | independent acceptance |
| OQ-1 unusable-executor refusal | TESTED | independent acceptance; PA (seen in PA-1/PA-10) |
| SUP-1 self-containment | TESTED | independent acceptance |
| D8 guest witness, guest bundle | TESTED (synthetic + simulated) | PA-11 on a VM + owner attestation |
| C6 Option B Chat handoff | TESTED (widget, Chat pane) | independent acceptance; PA-13 |
| Acceptance tooling (login-guide, status, provision choice) | TESTED | owner use in PA-8/9 |
| Voice parity | PLANNED (rules) | implementation (line choice) |
| Shipping line | RESEARCHED (recommendation) | owner decision |
| Everything | — | FROZEN, DEPLOYED: nothing |

## J. Owner decisions and gates still needed

1. EXE-1b: Codex sandbox backend for the client profile (`unelevated` = network open; `elevated` = admin setup).
2. PA-1..PA-7, PA-13 (no login needed); PA-8/PA-9 logins via `login-guide`; PA-10; PA-11 (install a hypervisor + VM);
   PA-12.
3. C6 decision 3 (Brain rows); voice rules 3-4; optional confirmation of decision 1's definitions.
4. Shipping line (recommended: Core lineage) and the A11 sync/push of the accepted candidate (git-sync work).
5. Whether the Ollama-induced phase1-full deviation is acceptable or the suite should be rerun with Ollama stopped by you.
6. Phase 2 freeze, C7 cutover (NOT READY).

Coordination note: a separate session works in `C:\Users\cheta\Development\uri-canonical-candidate` (consolidation on
`integration/git-sync-20261008`, a runtime-authority manifest naming `run_uri_supervised_worker.py` as an authorized
entry). This slice changes that worker's composition (CODEX_HOME/sandbox checks); that session must take this candidate
after acceptance. Its tests left a suspended `fake_executor.py` (PID 9060, its own pre-fix code, parent gone); I did not
touch it.

## K. Independent review round 1 and repairs (correction record 1)

Codex round 1 (`E:phase2oq_review\round1\CODEX_REVIEW_OQ_round1.md`) on `phase2oq-candidate-20261008.zip`
(`47f8fc81…1deb`): **PHASE 2 OPERATIONAL CANDIDATE REJECTED**. Earlier claims in this report that the findings contradict
are corrected here, not rewritten above.

| ID | Severity | Finding (reviewer) | Earlier claim corrected | Repair | Regression test |
|---|---|---|---|---|---|
| OQ-R1-1 | High | a vendored `codex.exe` with its descriptor missing was treated as a standalone binary with empty pins | section C "Unknown layout -> refused" held only for a PRESENT unknown descriptor | `codex_native_launch_chain`: any `codex.exe`, or any file under a `vendor` directory, without the recognised layout -> `LAUNCH_CHAIN_LAYOUT_UNKNOWN`; worker rule `_pins_recognised_codex_layout`: a NATIVE Codex record composes in the worker only when its pins include the descriptor of its own `bin\codex.exe` layout (`LAUNCH_CHAIN_LAYOUT_NOT_PINNED`) | `test_unknown_or_damaged_vendor_layout_is_refused`, extended `test_worker_codex_home_invariant` |
| OQ-R1-2 | High | the legacy blocking `turn_decide approve=true` skipped the OQ-1 gate, so an approval for an unusable executor could reach the server | section C OQ-1 "refuses before the approval leaves the worker" held only for `execution_begin` | `SupervisedWorkerService._refuse_unusable_harness`: the same live usability check, turn released (CAP-1), `HARNESS_NOT_USABLE`; declining is never gated | `test_oq_r1_2_legacy_turn_decide_cannot_approve_an_unusable_executor` (with and without `approval_digest`; decline still works) |
| OQ-R1-3 | Medium | `Supervisor` continued when self-containment was unavailable | section F "SUP-1 REPAIRED" held only on hosts where containment succeeds | `Supervisor.__init__` raises `SELF_CONTAINMENT_UNAVAILABLE` on Windows (fail closed); the host-wide side effect (every process the host started dies with it) is documented in the code | `test_oq_r1_3_no_supervisor_without_self_containment` |
| OQ-R1-4 | Gate | `chain2` was `CHAIN_FAILED`; a separate control cannot make it green | section H | the chain's phase1-full gate now runs with `OLLAMA_BASE_URL` unreachable (as the baseline effectively did) and passes on regression equivalence: same failure IDs, same total (2698), passes >= 2675; then one new full chain `E:phase2oq\chain3\` on the repaired tree | chain3 |

Disclosed accepted-test changes caused by the OQ-R1-2 repair (found by the aborted `E:phase2oq\chain3\`, gate 1):
`tests/phase2d/test_worker_service.py::test_model_outside_the_qualified_set_is_refused_before_any_task`,
`::test_unqualified_provider_offered_by_policy_fails_closed_with_zero_execution` and
`tests/phase2d/test_worker_process.py::test_worker_profile_refuses_fixture_records_without_the_flag` asserted the old
behaviour (approval sent, refused at dispatch, `SETTLED_FAILED`). They now assert the refusal before the server
(`HARNESS_NOT_USABLE`), the released (`cancelled`) turn and zero tasks; each carries an inline note.

Disclosed rule change (OQ-R1-4): the closure gate demanded exactly 2675 / 12 / 11. With an Ollama service running on
this PC, `test_gemma_worker_mcp.py:329` (it hard-codes `127.0.0.1:11434`) passes instead of skipping, so exact counts can
no longer hold without stopping a service this work did not start. The new rule still fails on any new failure, any
missing test, or any lost pass.

## L. Record H2: final chain on the repaired tree (`E:phase2oq\chain4\`, ALL_PASS)

`chain3` was aborted after gate 1 (three accepted assertions, above). `chain4` ran every gate on the repaired code;
afterwards only documents changed. This supersedes section H as the final chain; section H is kept as history.

| Gate | Result |
|---|---|
| phase2 | 472 passed, 2 skipped, 0 failed |
| authority | 134 passed |
| phase1-full (`OLLAMA_BASE_URL=http://127.0.0.1:9`) | 2676 passed / 11 skipped / 11 failed; SAME_FAILURE_SET; total 2698 = baseline; PASS under the disclosed equivalence rule |
| flutter | 205 passed, 2 skipped |
| bridge x10 | 10/10, 0 refusal lines |
| native (REAL Codex, in-process, owner shell login) | completed/`SETTLED_VERIFIED`; cancel uncertain/`CANCELLED_AFTER_DISPATCH`, PID DEAD |
| native-worker | W `REFUSED HARNESS_NOT_USABLE`; W2 `CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED`; W3 `LAUNCH_CHAIN_RESOLUTION_CHANGED`; L completed/`SETTLED_VERIFIED` (`pong.txt` = PONG), cancel uncertain/`CANCELLED_AFTER_DISPATCH`, PID DEAD, 0 survivors |

`chain_summary.json`: `ALL_PASS: true`. No leftover process of this tree after the chain. The guest bundle
(`E:phase2oq\powerloss_guest_bundle.zip`) was rebuilt from the repaired tree before chain4.

## M. Independent review round 2 and repair (correction record 2); Record H3 (`E:phase2oq\chain6\`, ALL_PASS)

Codex round 2 (`E:phase2oq_review\round2\CODEX_REVIEW_OQ_round2.md`) on `-b` (`5d5e111b…5706`): OQ-R1-1, -2, -3
REPAIRED; **REJECTED** on OQ-R2-1 (Gate): the count-based equivalence rule of section K could pass with a missing test or
a lost pass offset by another test. Section K's rule is superseded by the following (kept above as history).

Repair: `scripts/phase2close_chain.py::phase1_equivalence` passes only when, per test: the failure-ID set equals the
baseline's; the collected test IDs equal a stored baseline collection (`E:phase2oq\phase1_collection_baseline.txt`,
2698 IDs = the independent baseline total 2675 + 12 + 11); every PASSED and FAILED ID belongs to the collection; the
number of named PASSED IDs equals the passed count; every skip (location + reason, URLs normalised) is one the baseline
had, never more of one kind; every baseline skip that disappeared is matched by a named PASSED test of the same file.
New gate `phase1-scope` proves the Phase 1 suite's inputs equal the accepted `-f`: every path that differs from `-f`,
is new, or is modified vs HEAD is Phase 2-only scope or a frozen checkpoint file byte-identical to the checkpoint (98),
and nothing outside Phase 2 scope imports `uri_supervisor`/`uri_supervisor_bridge`. The collection baseline can only be
written while that check passes and the size equals 2698 (`--make-phase1-collection-baseline`; written 2026-10-08,
`E:phase2oq\collection_baseline2\`; the first attempt `collection_baseline\` collected nothing because of a doubled `-q`
and was refused). Adversarial tests: `tests/phase2oq/test_chain_equivalence.py` (the reviewer's offset case is refused
only with the collection check; identical / skip-to-named-pass accepted; new failure, new skip kind, unnamed pass
refused).

Chains: `chain5` aborted (my own flag error: `-rP` lists passed-with-output only, so 0 PASSED IDs were recorded and the
gate correctly failed; corrected to `-rp`). `chain6` = final, on the final code:

| Gate | Result |
|---|---|
| phase2 | 477 passed, 2 skipped, 0 failed |
| authority | 134 passed |
| phase1-full | 2676 passed / 11 skipped / 11 failed; SAME_FAILURE_SET; collection 2698 = baseline, none missing/added/outside; 2676 named passes; no new skip kind; the one gone skip (`test_gemma_worker_mcp.py:329`) matched by its named pass |
| phase1-scope | PASS (98 frozen files identical; nothing else outside Phase 2 scope; no Phase 1 importer of Phase 2) |
| flutter | 205 passed, 2 skipped |
| bridge x10 | 10/10, 0 refusal lines |
| native (in-process REAL Codex) | completed/`SETTLED_VERIFIED`; cancel uncertain/`CANCELLED_AFTER_DISPATCH`, PID DEAD |
| native-worker | as section L |

`ALL_PASS: true`; no leftover process of this tree.

## N. Independent review round 3 and repair (correction record 3)

Codex round 3 (`E:phase2oq_review\round3\CODEX_REVIEW_OQ_round3.md`) on `-c` (`a2c11441…9602`): OQ-R1-1..3 still
REPAIRED; **REJECTED** on OQ-R3-1 (a baseline pass becoming a skip while a baseline skip becomes a pass under the same
skip-summary key passed the gate) and OQ-R3-2 (the collection baseline was made by the candidate itself, and the scope
check exempted the Phase 1 runner). Section M's rule and its collection baseline are superseded (kept as history).

Repair:
* Per-test OUTCOME identity (`outcome_identity`, `junit_outcomes`): the gate runs Phase 1 full with `--junitxml` and
  requires every test ID to exist in both runs with the SAME outcome (passed / failed / skipped / error); plus the
  failure-ID set equal to the accepted log's.
* The outcome baseline (`E:phase2oq\phase1_outcome_baseline.json`, 2698 IDs, made by `--make-phase1-outcome-baseline`,
  run `E:phase2oq\outcome_baseline\`) is produced with the ACCEPTED runner: `scripts/phase2d_regression.py` is read from
  the `-f` zip and its own `main()` builds the argv (captured, then executed); the only addition, disclosed, is
  `--ignore=tests/phase2oq` (a directory that did not exist in `-f`). It is written only when the scope check passes and
  the run matches the ACCEPTED log's anchors: identical failure IDs, total 2698, no skip kind the accepted run lacked,
  and every accepted skip that disappeared matched by a named pass of the same file (one: `test_gemma_worker_mcp.py:329`,
  which reaches the local Ollama by a hard-coded URL). The file records the `-f` runner's SHA-256 and the argv.
* The scope check no longer exempts the runner: `scripts/phase2d_pytest.ini` must equal `-f`, and the current runner's
  phase1-full argv must equal the accepted runner's plus exactly that ignore (`runner_argv`, verified).
* Tests: `test_oq_r3_1_a_pass_skip_swap_is_refused` (the reviewer's counterexample), `test_junit_outcomes_reads_every_outcome`,
  `test_oq_r3_2_the_runner_must_build_the_accepted_argv` (a runner that ignores one more file is detected).

Residual limitation, stated: the outcome baseline is a NEW run of the accepted runner on inputs proven identical to `-f`
(98 frozen files byte-identical, no Phase 1 importer of Phase 2, runner argv bound), not a per-test record from the
accepted closure run itself (that run kept counts, failure IDs and skip summaries only; it is used as the anchor).

Record H4 (final chain on the round-3 repair, `E:phase2oq\chain7\`, `ALL_PASS: true`): phase2 480 passed / 2 skipped / 0
failed; authority 134; phase1-full 2676 / 11 / 11 with per-test outcome identity to the accepted-runner baseline (2698
IDs, none missing / added / changed) and the failure set equal to the accepted log's; phase1-scope PASS (runner argv
bound, 98 frozen files identical); Flutter 205 / 2; bridge 10/10, 0 refusal lines; native completed/`SETTLED_VERIFIED`,
cancel uncertain/`CANCELLED_AFTER_DISPATCH`, PID DEAD; native-worker as section L (0 survivors). No leftover process.

## O. Independent review round 4 and repair (correction record 4)

Codex round 4 (`E:phase2oq_review/round4/CODEX_REVIEW_OQ_round4.md`) on `-d` (`822c49be...0b8b`): OQ-R3-1 and OQ-R3-2
REPAIRED, OQ-R1-1..3 still repaired; **REJECTED** on OQ-R4-1 (Gate): two distinct tests can share a JUnit
`classname::name`; the parser collapsed same-outcome duplicates, so an added colliding test passed the outcome gate
(shown by the reviewer with real pytest output). Section N's claim "every test ID must exist in both runs" held only for
injective IDs.

Repair: `junit_records` keeps every testcase; a duplicated ID becomes `conflict` (never collapsed); `junit_integrity`
requires unique keys AND raw testcase count == pytest's summary total, for the current run AND the stored baseline run
(re-verified at every gate), and the baseline maker refuses a non-injective run. The existing baseline run satisfies it
(2698 testcases, 2698 unique, summary 2698), as does chain7. Tests: `test_oq_r4_1_a_real_pytest_junit_collision_is_refused`
(real pytest, `--import-mode=importlib`, two files colliding), `test_oq_r4_1_a_testcase_count_below_the_summary_is_refused`.

Record H5 (final chain on the round-4 repair, `E:phase2oq/chain8/`, `ALL_PASS: true`): phase2 482 passed / 2 skipped /
0 failed; authority 134; phase1-full 2676 / 11 / 11, outcome identity with the baseline for all 2698 IDs, JUnit integrity
ok for the run and for the baseline (2698 unique = summary); phase1-scope PASS; Flutter 205 / 2; bridge 10/10, 0 refusal
lines; native completed/`SETTLED_VERIFIED`, cancel uncertain/`CANCELLED_AFTER_DISPATCH`, PID DEAD; native-worker as
section L (0 survivors). No leftover process.

## P. Independent review round 5 and repair (correction record 5)

Codex round 5 (`E:phase2oq_review/round5/CODEX_REVIEW_OQ_round5.md`) on `-e` (`a914d086...ea3f`): OQ-R4-1 REPAIRED;
**REJECTED** on OQ-R5-1 (the integrity check compared only the total of XML records with pytest's summary, not each
outcome category) and OQ-R5-2 (each gate rechecked the stored baseline XML's structure but not that its outcome map
still equals the baseline JSON). Repair: `junit_integrity` now requires the XML's passed/failed/skipped/error counts to
equal the summary's, category by category; the phase1-full gate requires `junit_outcomes(baseline XML) ==` the baseline
JSON map at every run (`baseline_json_equals_baseline_xml`). Tests `test_oq_r5_1_per_outcome_counts_must_agree` (the
reviewer's probe) and `test_oq_r5_2_the_stored_baseline_map_is_bound_to_its_xml`. Both the baseline run and chain8
satisfy the stricter checks (2676 / 11 / 11 / 0 in XML and summary alike).

Record H6 (final chain on the round-5 repair, `E:phase2oq/chain9/`, `ALL_PASS: true`): phase2 484 passed / 2 skipped /
0 failed; authority 134; phase1-full 2676 / 11 / 11 with outcome identity (2698 IDs), JUnit integrity per category for
the run and the baseline, baseline JSON == baseline XML; phase1-scope PASS; Flutter 205 / 2; bridge 10/10, 0 refusal
lines; native completed/`SETTLED_VERIFIED`, cancel uncertain/`CANCELLED_AFTER_DISPATCH`, PID DEAD; native-worker as
section L (0 survivors). No leftover process.

## Q. Independent review round 6 and repair (correction record 6)

Codex round 6 (`E:phase2oq_review/round6/CODEX_REVIEW_OQ_round6.md`) on `-f` (`69f999be...4b9e`): OQ-R5-1/-2 REPAIRED;
**REJECTED** on OQ-R6-1 (the phase1-full PASS ignored pytest's exit code) and OQ-R6-2 (a jointly altered baseline XML
and JSON map passed, because no immutable baseline anchor was checked). Repair: the gate requires exit code 1 exactly
(`PHASE1_EXPECTED_EXIT`: the session completed and only tests failed; 2/3/4/5 or a timeout fail); the SHA-256 of the
baseline JSON, XML and log are pinned in the gate script itself (`BASELINE_PINS`, checked at every run by
`baseline_pins_hold`), so any change to the baseline needs a new reviewed digest. Tests:
`test_oq_r6_2_baseline_files_are_pinned_and_a_joint_tamper_is_refused`, `test_oq_r6_1_only_the_expected_pytest_exit_is_accepted`.

Record H7 (final chain on the round-6 repair, `E:phase2oq/chain10/`, `ALL_PASS: true`): phase2 486 passed / 2 skipped
/ 0 failed; authority 134; phase1-full exit 1 (expected), 2676 / 11 / 11, outcome identity (2698 IDs), JUnit integrity
per category, baseline JSON == XML, baseline pins hold; phase1-scope PASS; Flutter 205 / 2; bridge 10/10, 0 refusal
lines; native completed/`SETTLED_VERIFIED`, cancel uncertain/`CANCELLED_AFTER_DISPATCH`, PID DEAD; native-worker as
section L (0 survivors). No leftover process.

## R. Acceptance record

Codex review round 7 (`E:phase2oq_review/round7/CODEX_REVIEW_OQ_round7.md`) on `phase2oq-candidate-20261008-g.zip`
(SHA-256 `0b49d86d89b26d3332fcbfbc9b4b7b981cdc1075d5dc295588a5cef92a82c4cd`, final chain `E:phase2oq/chain10/`):
**PHASE 2 OPERATIONAL CANDIDATE ACCEPTED — READY FOR OWNER PHYSICAL ACCEPTANCE**, no remaining defect; every OQ finding
(R1-1..4, R2-1, R3-1/2, R4-1, R5-1/2, R6-1/2) REPAIRED. Rounds 1-6 rejected candidates `-`, `-b`..`-f`; all kept.
Status: INDEPENDENTLY ACCEPTED. NOT physically qualified, NOT frozen, NOT deployed: PA-1..PA-13 and the owner decisions
of section J remain open.
