# Text Intelligence on WS hardening: integration report

Date: 2026-10-09. Author: Claude (Text Intelligence session). Branch `integration/ti-on-ws-hardening-20261009`,
worktree `C:\Users\cheta\Development\uri-ti-integ`. This session did not modify another session's worktree or process.

## 0. Acceptance criteria (defined before integration)

| ID | Criterion |
|---|---|
| IN-1 | The base is WS hardening's **final, independently accepted** tip. A tip with unreviewed commits after the last acceptance is not used for integration. |
| IN-2 | Every conflict is resolved by hand and explained. Both features keep their authorization, cancellation and lifecycle semantics. Each defect that appears only in the combination is repaired and tested, and the test fails without the repair. |
| IN-3 | Frozen boundaries: `ws_frozen_check.py` ok. No file under `uri_core/`, `uri_supervisor*/`, `uri_harness_adapters/`, `model_lab/integration/` or the root `.gitignore` changes. Scope guards list exact paths only (WS-D3). |
| IN-4 | Regression: `tests/ws` + `tests/oi` show no failure, and the counts equal the union of the two features' suites. The Flutter full suite passes. The accepted chain (phase2, authority, phase1-full, phase1-scope, residue) gives the accepted outcome set. Every outcome difference is explained by evidence, not assumed environmental. |
| IN-5 | Live: the previously failing fact-preservation scenarios and the final verifier (Codex TI r12-15 changes, limitation L-9) run on the real Brain through the combined code, as well as paragraph-local editing and version history. |
| IN-6 | Independent Codex review of the combined candidate: ACCEPT or ACCEPT WITH FINDINGS, with valid findings repaired. |
| IN-7 | The canonical branch moves only after IN-1..IN-6, by fast-forward, without force, after WS hardening has moved it. |

## 1. Cross-thread integration and dependency map (inspected 09:15-09:45 IST)

| Thread | Branch / tip | Worktree | Owner session (state) | Base | Status |
|---|---|---|---|---|---|
| Canonical development branch | `integration/git-sync-20261008` = `037229c` (uri-repo) | — | — | — | Published. Not moved yet |
| Working System integration | `integration/working-system-20261008` = `68cac3d` (published) | `uri-working-system` | 08f073a5 "Intregation" (busy) | 037229c | Codex WS r8 ACCEPT WITH FINDINGS |
| WS hardening | `integration/ws-hardening-20261009`, at inspection `2831586`, later `1401aba` | `uri-ws-hardening`, runtime `uri-ws-hard`, gate `uri-ws-gate3` | same session (busy) | 68cac3d | Codex H-r6 ACCEPT at 9808fb6; post-r6 commits reviewed in rounds 7-10 (r10 ACCEPT WITH FINDINGS at 9ae28f4, as that session reports). Final chain was running; it plans to fast-forward the canonical branch |
| Text Intelligence | `phase/text-intelligence` = `2563ca5` (published) | `uri-text-intel`, runtime `uri-ti-rt`, gates `uri-ti-gate`, `uri-ti-gate2` | this session | 68cac3d | Codex TI r16 ACCEPT WITH FINDINGS; L-9 open |
| TI + hardening candidate | `integration/ti-on-ws-hardening-20261009` | `uri-ti-integ`, gate `uri-tiws-gate` | this session | hardening tip | this report |
| Scheduler | `phase/scheduler` (moved past `4dca63c`: `b809c6d`, `f59aad5`) | `uri-scheduler`, gate `uri-sched-gate` | f3e16c05 / 37ebb119 "Scheduler" (busy: festival calendar) | `99f8041` (mid-hardening) | Codex r8 ACCEPT WITH FINDINGS on 7496bba; F10 live Claude BLOCKED (CLI not logged in); not pushed |
| A2UI | `phase/innovation-lab` `47b63f6` (`innovation_lab/candidates/a2ui/`) | `uri-innovation-lab` | none active | 037229c | Isolated PoC (genui 0.10.4 and a native surface protocol); contract C-A; verdict EXPERIMENTAL → ADAPT; nothing in `uri_ui` |
| Runtime v1 | frozen record (uri-phase1-integration `model_lab`) | — | — | — | FROZEN 2026-10-07; optimization CLOSED |
| Adaptive Runtime research | `research/adaptive-runtime` `7d035aa` | `uri-adaptive-runtime` | none active | 037229c | Research only (R1/R2); nothing accepted |
| Companion voice / living companions / orb | `phase/companion-voice` `ebe3828`, `phase/living-companions` `d7a052f`, `phase/orb-solar-rnd` | own worktrees | none active at inspection | various | Candidates, not merged. Their app windows are GPU consumers (§ performance) |

Shared files between threads (overlap):
- `uri_operational_intelligence/worker_bridge.py`: WS integration (owner), hardening (health, restart, liveness), TI
  (desk commands). Scheduler does not touch it.
- `uri_ui/lib/living/integration/oi_conversation.dart`: hardening (restart, liveness) and TI (draft state, transcript).
- `uri_ui/lib/living/screens/dashboard_mode_view.dart`: hardening (Brain card) and scheduler (tile). Auto-merges.
- Scope-guard lists (`tests/phase2a/test_frozen_core.py`, `scripts/phase2close_chain.py`): every thread adds exact paths.
- Runtime: one Runtime v1 on port 18470, a machine-wide GPU lease (`%LOCALAPPDATA%\URI\gpu`), and per-tree
  materialized runtimes (frozen `runtime_identity.py` needs HEAD `e8e3b65`).

Integration order, checked against the dependencies: **WS hardening → TI → Scheduler → A2UI.**
- TI and the scheduler both need the hardening worker and UI.
- The scheduler is based on a mid-hardening commit, and it merges cleanly onto the TI candidate (`git merge-tree`,
  tree `6ff2f27`).
- A2UI has no code in `uri_ui`.

## 2. Merge and conflict resolution

Final candidate: base `7160614`, the canonical branch after WS hardening's fast-forward. At 14:55 IST I re-checked it
independently: it is a fast-forward from `037229c`, `uri-repo` holds the same commit, and its code is identical to
`1401aba`/`522939c`.

| Commit | What |
|---|---|
| `913e10f` | merge of `2563ca5`. Its conflict resolution is **byte-identical** to trial 1 for all 4 files (`diff` against `c50e07a`) |
| `8288bd8` | INT-1 glue (cherry-pick of `0b737ce`) |
| `b2d04dd` | L-9 live cases L9a-L9e in `scripts/ti_live_matrix.py` (test tooling) |
| `05bf04a` | Codex TIWS r1 INT-2: after `worker.exited`, the draft buttons that need the worker are off, draft calls are not sent, and Copy stays |
| `ab6f384` | Codex TIWS r1 L9-1..3: only a flag that names the value counts; values must be whole tokens; a failed check exits 1 |

The first trial is preserved as `trial/ti-on-ws-hardening-2831586`.

Trial 1 (`c50e07a` = `2563ca5` merged onto `2831586`, glue `0b737ce`):

| File | Conflict | Resolution |
|---|---|---|
| `scripts/phase2close_chain.py`, `tests/phase2a/test_frozen_core.py` | both sides added exact paths at the same list positions | sorted union. A script refuses any block that is not a pure list of quoted paths. CRLF kept |
| `uri_operational_intelligence/worker_bridge.py` | the whole file conflicted because hardening had turned LF into CRLF (INT-EOL-1). After normalizing, 3 hunks, all additive | COMMANDS = union. OPEN_WHILE_BUSY = union (`brain_health`, `oi_turn_status`, `draft_get`). Both sides' state and handlers kept. Written as LF |
| `uri_ui/lib/living/integration/oi_conversation.dart` | TI split `send` into `send`/`sendTranscript`/`_turn`; hardening added the `restarting` guard and liveness stamps to `send` | TI structure, with the hardening guard and stamps in `_turn`, the single path every send takes |

Semantic checks of the combination:
- The hardening restart gate (`BRAIN_RESTARTING`) applies to every `oi_turn`, so it also covers desk turns. Desk turns
  run as jobs, so `brain_restart` is refused while one runs (TURN_IN_PROGRESS).
- Desk events go through the hardening `_sink`, so liveness counters see desk progress.
- Desk `answer.done` metrics feed the hardening health samples. Desk decode in the TI live matrix was 94-146 tok/s,
  with PerfMonitor's 64-token minimum. That is above the 60 tok/s DEGRADED threshold, so desk turns cannot make a
  healthy Brain look slow.
- `draft_op` is deterministic and stays allowed during a Brain restart. It is refused while a turn runs (TI semantics).
- **INT-1 (defect of the combination, repaired in `0b737ce`).** Hardening's Restart URI replaced the worker, but
  the Draft panel kept the old worker's draft (TI L-7: drafts live in worker memory). Undo/Redo were offered on a
  draft that no longer existed. `draftOp` and `refreshDraft` had neither the restarting guard nor the replaced-worker
  late-reply check. The repair clears the draft with a visible note, adds both guards, and adds 5 tests in
  `uri_ui/test/ws/ti_ws_combined_test.dart`. 3 of the 5 tests fail on the merge commit without the repair (negative
  control run).
- **INT-EOL-1.** Reported to the hardening session, confirmed, and fixed there in `1401aba` (content identical, LF restored).

## 2a. L-2 and L-4 (owner request, 2026-10-09)

**L-2, dictation versus commands.** This reuses the existing routing; no new classifier was added.

| Input | Route |
|---|---|
| Envelope `mode: "dictation"` (typed or transcript; `scope` grammar\|rewrite) | Desk CORRECT/REWRITE with **no fallback**: never Core, whatever the text says. Sentences that read as instructions get a `DICTATED_INSTRUCTION` info line ("written as text, not carried out") |
| Envelope `mode: "command"` | Ordinary path only (triage, intent discovery, Core, approvals). Never a draft |
| Auto mode, "Write: send this letter to the director." | Content marker: dictated content, with the `DICTATED_INSTRUCTION` line |
| Auto mode, "Write a notice. Send the form by Friday." | Deterministic question (no model call): "write it in" or "do it". Only an exact reply decides. Any other non-request reply is asked again; a new request or the user's own question drops the question. "do it" hands the **original** request to Core |
| "Send this letter to the director.", "Draft a letter ... Email the principal.", "... Send it to him.", "... then email it", destinations, "Note down" | Core, unchanged (accepted Codex TI r2 A1) |
| "Delete the previous paragraph." | With an active draft: a draft edit (no authority). Without one: the ordinary path |
| "Prepare the office order for tomorrow." | Drafting |

UI: Dictation toggle in the Living composer, and the source label "· Dictation". The contract is documented in
`TI_INPUT_CONTRACT.md`. A dictated or quoted command cannot reach Core through the desk: the desk has no action
capability, and the dictation path has no fallback.

**L-4, value reassignment.** `text_verify.check_reassignment(reference, revised, instruction)`:
1. Split each text into clauses. Numbers, number words and clock times come from the existing `canonical_numbers`.
2. Find each value's distinctive partner words (words that sit with only that value).
3. Flag only on mutual evidence: the value lost all its old partners and gained another value's partner, and its old
   partner now sits with a different value.
4. The detail names the old association, for example "500 was with “Ravi” and is now with “Sita”, which was with
   700 - check the Changes and Original views".
5. When the user's instruction itself pairs the value with its new word, the line is info ("as asked"), so an
   intended correction stays possible.

It runs on create (against the user's words) and on every edit (against the previous version). Tests cover swaps of
amounts, quantities, dates between events, roll numbers and clock times; seven legitimate rewrites with no flag;
the "as asked" case; thousands separators; and unspaced lists.

## 3. Combined regression report

### 3.1 Final gates at `48d2f78` (canonical `b02ed4f` + TI + WS hardening)

| Gate | Result | Evidence |
|---|---|---|
| Chain (gate tree `C:\Users\cheta\Development\uri-tiws-gate4`, materialized from `48d2f78`, fixtures hash-identical to the gate4 list (883), the regression_chain lease held, idle Ollama launched from PowerShell) | **ALL_PASS**: phase2 486/0/2; authority 134/0; phase1-full 2,676/11/11, outcome identity (missing = added = outcome_changed = ∅, same failure set as accepted); phase1-scope PASS; residue PASS | `uri-tiws-gate4\evidence\tiws_chain\chain_summary.json` |
| `pytest tests/ws tests/oi` | 468 passed, 22 skipped (all skips opt-in live tests) | session run at `d847f4d`; no Python path changed by the two merges |
| `tests/scheduler` | 71/71 with the base interpreter `Python313\python.exe` (= scheduler receipt). With the venv redirector, `test_task_ctl.py::test_rollback_dry_run_only_targets_this_scheduler_service` fails, and **fails identically on `b02ed4f` without TI**. Finding SCH-ENV-1 (LOW, test assumes `svc.pid` is the service pid), relayed to the scheduler owner | session runs |
| Flutter full (`uri_ui`) | **446 passed, 4 skipped** = canonical 431/3 + TI 15/1 (exact union) | session run at `48d2f78` |
| Frozen check (`ws_frozen_check.py`) | ok, 121/121, no protected path changed | `48d2f78` |
| Codex | TIWS r5 **ACCEPT** on the merges; r4 ACCEPT WITH FINDINGS on the TI code | §6 |

### 3.2 Correction history (kept, not rewritten)

1. **First candidate chain (`8288bd8`, 15:05) and rerun (15:32): phase1-full had one outcome change**
   (`test_c3_client_worker::test_windows_powershell_client_launcher_preserves_binary_frames`, CLIENT_WORKER_REFUSED).
   I did not accept it as flaky. A control tree from canonical `7160614` without TI (`uri-ctl-gate`) gave the
   **identical** outcome set. Fixture pollution was ruled out: the first run started from fixtures hash-identical to
   the gate4 list.
   **Cause found (ENV-C3):** the failure needs an idle `ollama serve` **launched from Git Bash** while the full suite
   runs. With Ollama launched the way gate4 had it (`Start-Process -WindowStyle Hidden` from PowerShell), the same
   reproduction passes. The `1f34cb3` and `48d2f78` chains then had outcome identity.
   The exact exception is unknown: the frozen worker swallows it after writing `worker-instance.json`.
   Owner note: launching Ollama from Git Bash is now a known invalid gate environment.
2. **First Ollama hypothesis, "fails whenever an idle Ollama is up"**: disproved by the PowerShell-launch run, and
   recorded as wrong.
3. **My statement that `workspace_mode_view.dart` was shared by the scheduler merge**: wrong (Codex r5). That file was
   shared only in the companion merge.
4. **A scripted wait loop in my phase1 rerun** looked for a label that sed had renamed, so it would have hung. I stopped
   it before it started any test, released the lease cleanly (the holder exited on its done-file), and reran.
5. **Heredoc patch** turned `\b` into backspace characters in two regex lines of `text_intent.py`. Found by a
   control-character scan before commit and repaired with a Write-tool script; no commit contained it.
6. **L-2 first version** regressed the accepted Codex TI r2 A1 case ("Draft a letter ... Email the principal." went to
   the question instead of Core). The full suite caught it (`test_ti_audit_r2_regressions`); repaired before commit.

## 4. Live results on Runtime v1

Conditions:
- Runtime v1 frozen argv, started by the accepted Brain host (`uri-tiws-rt2`) under the machine-wide lease
  (acquired 19:39:56, after the Live Voice session released it; released 20:04:28).
- Census before the start: AT_RISK, 26 MB short, desktop only. Your Chrome had held 584 MiB earlier, so the start
  waited until it was gone.
- Calibration 155.2 tok/s (first start) and 146.7 tok/s (restart with the launcher's report directory, see the
  correction below).
- SAFE-1 watchdog: llama-server non-local memory was 1,120.6-1,121.8 MiB in every one of 29+ samples. No demotion,
  no stop. Evidence: `evidence/residency/`, `evidence/brain_host_report_run2.json`.
- Transcript inputs are SIMULATED (engine "simulated"); no microphone was used.

| Test | Code basis | Result | Evidence |
|---|---|---|---|
| Live matrix M1-M20 + L9a-e (in-process bridge + Runtime v1) | worktree at `48d2f78`. Its OI code is **identical to the final commit** | **100/103**. Failures: M1 `second_para_shorter` (known model residue L-6); L9d routed to the answer channel (2 checks), which is limitation **LV-1** (a Hinglish letter that mentions a family "function" hits the code-work rule; safe direction) | `docs/text_intelligence/evidence/ti_live_matrix_fast_20261009T194422.json` |
| L9a-e + M7, 2 repetitions | `c775997` (LV-1 exemption, later reverted) | 50/50. L9a, b, c and e are unaffected by the exemption. The L9d draft content was right ("kal" became a `[Start Date]` placeholder, never guessed), but drew 5 error-level FACT_UNSOURCED/FACT_MISSING flags because the model put commentary into its Hinglish fact values: **LV-2**, precision noise under L-3 | `ti_live_matrix_fast_20261009T194815.json` |
| L-9 verdict (verifier changes of Codex TI r12-15, live) | — | **Closed.** I read the drafts. Clock 18:00 and Rs5400 were kept by a grammar-only fix with no flag. "east wing, sector C" was replaced whole. "Dr. Mehta" was kept whole. A tone change kept 5400, 2231 and Sunil. No silent change, and no error flag on a correct non-Hinglish draft | same files |
| Real integrated worker: TI warden demo, typed + simulated transcript | `uri-tiws-rt2` (OI code = `c775997`; the only difference from the final commit is the LV-1 exemption, which this test does not exercise) | 2/2 | `evidence/ti_worker_live_20261009-195100.json` |
| Real integrated worker: WS hardening journeys (preflight, answer, reasoning, cancel, approve, deny, destructive refusal, forged digest, health, turn status, liveness) | same | 11 passed, 1 skipped (opt-in Brain restart) | `evidence/worker_live_20261009-195140.json` |
| Living UI, TI journey (real composer, Draft panel, Undo/Redo, simulated transcript) | Dart at `48d2f78` (= final) against the real worker | pass | `docs/text_intelligence/evidence/ti_ui_live_tiws_20261009.json` |
| Living UI, WS journeys (health chip, Dashboard Brain card, markdown, worker exit + Restart URI) | same | pass, after the correction below | `evidence/ws_ui_live_tiws2_20261009.json` |

Correction: the first WS UI run failed at `speed?.tps`. That was my setup error: I had started the host with a
`--report-dir` in my scratchpad, while the worker reads `<client_root>\control\oi` (the launcher's directory). I
stopped the host cleanly with its stop file (lease RELEASED), restarted it with the launcher's directory, and the run
passed. Not a product defect.

## 5. Limitations L-1..L-10 classified against the TI acceptance contract (`TI_BLUEPRINT.md` §0)

Classes used: **DESIGN** means it was decided in the frozen blueprint. **RESIDUAL** means a criterion is met for the
recognised phrasings and a known residue remains, which needs owner acceptance. **GAP** means a part of a criterion
as written is not met, which needs an explicit owner decision. **EVIDENCE** means evidence is missing.
**ENVIRONMENT** means the cause is outside the feature. **COSMETIC** means no criterion is affected.
Nothing here is waived by this report.

| ID | Limitation | Criterion | Class | Effect of the combination |
|---|---|---|---|---|
| L-1 | Routing is a heuristic. A request phrased outside both the classifier and the model-side guard can be drafted without the action being done (the draft says nothing was sent) | TI-AC1 | RESIDUAL. Safe direction: no action is taken without Core. Codex rule (b) is not triggered because the model-side guard covers it | unchanged |
| L-2 | Dictated content that starts sentences with action verbs and has no colon goes to Core instead of the desk | TI-AC1 ("drafting ... requests go to the draft desk") | was **GAP**. **RESOLVED** by the owner's 2026-10-09 rules (`95789ad`, `5344905`, `d847f4d`; Codex TIWS r4 ACCEPT WITH FINDINGS). The changes: an explicit Dictation mode (content, never Core); a Command mode (the ordinary path only); in auto mode a "Write: ..." marker; and a deterministic question for recipient-free action sentences, decided only by an exact "write it in" / "do it" reply. Residue: auto-mode phrasing outside these forms keeps the L-1 heuristic | see §2a |
| L-3 | Review lines appear on some correct drafts (CORRECTION_UNCONFIRMED, FACT_REWORDED) | TI-AC4 is not violated, because these are extra flags | RESIDUAL (precision noise). Measured live in §4 | unchanged |
| L-4 | Value **reassignment** (values swapped between two items) gets no deterministic flag; the Changes view shows the diff | TI-AC4 ("a violation is shown to the user as a flag") | was **GAP**. **RESOLVED as an advisory check** (`text_verify.check_reassignment`): VALUE_REASSIGNED (review) or VALUE_REASSIGNED_AS_ASKED (info); never reverted. **Recorded recall limits** (RESIDUAL): a word that sits with two values anywhere in the text is never distinctive, so two values in one clause or a restructured sentence usually give no evidence; and a value that keeps any old distinctive word is not flagged (Codex TIWS r2 L4-R2-2) | see §2a |
| L-5 | Replacement-matcher abbreviation list and other residual verifier heuristics | TI-AC4 | RESIDUAL. Live case L9c exercises "Dr." (§4) | unchanged |
| L-6 | Runtime v1 quality: occasional escalation wording, placeholder lists, one paragraph miscount | TI-AC10 (measured, not a quality bar) | RESIDUAL. Shown to the user by flags (ESCALATION_ADDED) | unchanged |
| L-7 | Drafts live in the worker's memory per session | Blueprint D3 | DESIGN | **Made visible by the combination**: INT-1 and INT-2 repaired. After Restart URI the draft is cleared with a note; after a worker exit only Copy stays |
| L-8 | Decode 33-40 tok/s in the physical app | TI-AC10, measured | **ENVIRONMENT**: GPU memory residency (`TIWS_PERFORMANCE_INVESTIGATION.md`). Not caused by TI | hardening now detects it (DEGRADED, GPU_MEMORY_TAKEN_AFTER_LOAD) |
| L-9 | No live run after the final verifier commits | TI-AC4/AC10 evidence | EVIDENCE. Closed only by §4 | — |
| L-10 | The missing-information list can repeat a placeholder in other words | none | COSMETIC | unchanged |
| LV-1 | (live, new) A Hinglish drafting request that contains a code word, for example a family "function" ("ghar mein function hai"), goes to the ordinary path instead of the desk | TI-AC1 | RESIDUAL under L-1, safe direction: nothing is executed, and the answer channel replies. Three repairs were rejected (Codex r6-r8) | — |
| LV-2 | (live, new) Error-level FACT_UNSOURCED/FACT_MISSING on a correct Hinglish draft when the model writes commentary into its fact values | TI-AC4 not violated (extra flags only; Codex r6) | RESIDUAL under L-3. The flags are misleading at error severity | — |
| LV-3 | (pre-existing, found by Codex r8) Plural code words ("functions", "scripts") are not code words, so such a request can reach the desk. The model-side `actions_requested` guard is the backstop | TI-AC1 | RESIDUAL under L-1. Adding plurals diverted legitimate corrections (Codex r9) | — |

Owner decisions still needed: accept the RESIDUAL items L-1, L-3, L-5, L-6, LV-1, LV-2, LV-3, the L-4 recall
limits, and the auto-mode L-2 residue. No GAP remains.

## 6. Independent review

| Round | Candidate | Verdict | Findings | Disposition |
|---|---|---|---|---|
| TIWS r1 | `b2d04dd` | **ACCEPT WITH FINDINGS** (Codex `gpt-6-sol`, medium, read-only, clone `C:\Users\cheta\Development\tia`; thread `01a12005-b31b-7022-b928-3a45a2c83360`) | INT-2 LOW: a draft stays usable in the UI after `worker.exited` without a restart. L9-1 LOW: any flag counted as disclosure. L9-2 LOW: substring matching, narrow paraphrases. L9-3 INFO: the matrix always exits 0. No HIGH/MEDIUM finding. Q1 (conflict fidelity), Q2 (semantics), Q4 (frozen/scope) found no defect | All confirmed against the source by me. INT-2 repaired in `05bf04a` (2 tests). L9-1..3 repaired in `ab6f384` |
| TIWS r2 | `0bbf88c` (L-2, L-4, contract) | **REJECT** (thread `01a12053-4ca9-74a0-b33e-f6c42cd699b2`) | L2-R2-1 MEDIUM: the answer matcher read substrings ("No, not in the text; do it" became content; "No, don't do it" went to Core). L4-R2-1 LOW: "Rs 1,500" split at its comma. L4-R2-2 LOW: a shared partner word suppresses the warning (recall) | Confirmed. Repaired in `5344905` (negation and both-sides replies asked again; digit commas). L4-R2-2 recorded as a recall limit |
| TIWS r3 | `5344905` | **REJECT** (thread `01a12058-d116-7a83-b692-d68bb1860e1b`) | L2-R3-1 MEDIUM: "dont do it" (no apostrophe) read as "do it". L2-R3-2 MEDIUM: "yes"/"no" reached the Brain without a choice. L4-R3-1 LOW: "1,2" read as 12 | Confirmed. Repaired in `d847f4d` with a structural rule: only an exact whole-reply choice decides; any other non-request reply is asked again; the user's own question or a new request drops the question. Commas are thousands separators only before exactly three digits. Tests fail on the r3 code (2 of 5) |
| TIWS r4 | `d847f4d` | **ACCEPT WITH FINDINGS** (thread `01a12060-880c-7a92-ab27-69a7d3571b4b`) | R4-1 LOW: the Phase 2A `ALLOWED_NEW` list does not name the TI docs/UI paths; the closure guard covers them by its Phase 2 scope | Checked by gate: the phase2 suite, which includes `tests/phase2a/test_frozen_core.py`, runs in the materialized gate tree; result in §3 |

| TIWS r5 | `48d2f78` (merges `1f34cb3` = canonical `f24d57a` companions, `48d2f78` = canonical `b02ed4f` scheduler) | **ACCEPT** (thread `01a120a7-8660-70b2-90ea-746748e8c133`) | none. The merges are faithful (blob comparison; the guard lists are exact unions, CRLF). No semantic interaction found: companion voice signals feed presentation only, frame-clock suspension does not stop conversation events, and scheduler paths never call `oi_turn` or draft commands. `b02ed4f..48d2f78` contains only the reviewed TI + WS work. No frozen change | — |

| TIWS r6 | `c775997` (LV-1: Hinglish letter vs code-work rule) | **REJECT** (thread `01a12117-2f33-77e1-b3fb-42e8e195e813`) | MEDIUM: "bug report likho aur bug fix karo" reached the desk. LOW: LV-2 classification plausible | Narrowed in `0efa586` |
| TIWS r7 | `0efa586` (verb list) | **REJECT** (`01a1211c-1846-7ad3-a1a1-006247e562f8`) | MEDIUM: "… aur function ko badlo" slipped past the verb list | Structural rule in `53e2156` |
| TIWS r8 | `53e2156` (family-event phrase) | **REJECT** (`01a12122-cdef-7662-afaf-e602743c76ab`) | MEDIUM: "Ek function hai, usko run karo …" matched; MEDIUM: plural "functions" not a code word (pre-existing) | **LV-1 reverted** to the accepted round-5 routing; plurals added in `dca2094` |
| TIWS r9 | `dca2094` (plural code words) | **REJECT** (`01a12127-3eab-7c83-95d4-f776729dd45c`) | MEDIUM: "Correct this: The exam scripts were marked yesterday" would lose its correction | Plurals reverted too: `text_intent.py` **byte-identical to round 5** (`5cc0220`); LV-3 recorded |
| TIWS r10 | `5cc0220` | **ACCEPT WITH FINDINGS** (`01a1212b-4ae9-74a2-a0a1-87edbcfec50d`) | Tree identical to round 5 except one test file. Assertions true. Two wording issues in the test comment and name | Fixed in `f0a8103` (test-only) |

Result of rounds 6-10: the TI code at the integration commit is exactly the code Codex accepted in round 5. The live
finding LV-1 and the pre-existing gap LV-3 are recorded limitations (§5), not repaired: every narrower repair broke
something else.

Codex built none of this code. It reviewed statically and ran no tests; every gate result is from this session's
own runs.

## 7. Scheduler and A2UI compatibility

State at inspection, read only. I did not modify either worktree.

- **Scheduler** (`phase/scheduler` `f59aad5`, base `99f8041`, a mid-hardening commit). Codex r8 ACCEPT WITH FINDINGS on
  `7496bba`; later commits are festival-calendar and logon-task work. Owner-gated: F10 live Claude generation (the
  Claude CLI is not logged in), F2 filesystem boundary, schedule activation. **Textually compatible**: it merges onto
  this candidate with no conflict (`git merge-tree`, tree `6ff2f27`). Integration needs its own rebase onto the
  canonical branch, chain and review. It is not integrated here.
- **A2UI** has an active thread: `phase/a2ui` `602fe4d` (worktree `uri-a2ui`, on the scheduler), with uncommitted work
  in progress. It implements an A2UI v0.9.1 subset with a URI catalog, validation in Python (`uri_a2ui`) and Dart, an
  action registry, and digest-bound actions. Its first domain is scheduler surfaces. It adds
  `schedule_intent.interpret` in `worker_bridge._oi_turn` **before** the turn job, and an `a2ui.handoff` event handled
  in `oi_conversation.dart` (uncommitted).
- Overlap with TI, for the A2UI thread to resolve when it rebases. These are not defects of either branch today:
  1. Same hook point. In TI, `_oi_turn` parses `uri.text_input.v1` and computes `plain` (cleaned transcript) before
     the job. The A2UI interpreter reads raw `text`. For a simulated or real transcript, the handoff should read
     `plain` and run after `TI.parse`, or fillers can block or skew its match.
  2. Precedence: a scheduling handoff before the desk is the right order. An authority-domain request must not become
     a draft. Its interpreter needs schedule words (`_SCHEDULE`), so "write a Diwali greeting" still reaches the
     desk. A request that mixes both ("schedule a Diwali greeting and draft it now") is a combined case to test.
  3. `oi_conversation.dart`: A2UI adds a stream and an event case. These are additive next to TI's draft cases; no
     conflict is expected beyond context lines.
- Compatibility prepared for A2UI (contract only, no code). TI already emits declarative JSON: `draft.updated` (a
  snapshot with versions, blocks, `changed`, flags with severity, missing items, source label), `draft.clarify` and
  `draft.progress`. Its button path is a closed command set (`draft_op`: undo/redo/restore/discard) with no authority,
  so it maps onto A2UI's action-registry rule. Mapping for a future A2UI draft surface:
  - **review and revision**: `Card` with block `Text` items, `changed` shown as `Badge`;
  - **proposed changes**: the Changes view, as a list of changed blocks;
  - **fact-conflict warnings**: flags as `Badge(tone)` + `Text`, with error, review and info always shown;
  - **approval and refinement**: `Button` actions `draft.undo`, `draft.redo`, `draft.restore{version}` and
    `draft.discard`, registered to `draft_op`, digest-bound to the draft version shown;
  - **free-form refinement**: the composer's ordinary turn.
  - Scheduled-task proposals, execution status and failure/recovery actions belong to the scheduler surfaces A2UI is
    building; TI adds none.
  - Explicit user approval stays where it is: TI never sends, saves or executes, and the scheduler's confirm stays
    digest-bound.
- **The existing Draft panel stays the drafting UI** until an A2UI replacement is implemented, tested and accepted.

## 8. Implementation ledger and cleanup inventory

### 8.1 Ledger

Ladder: PLANNED → IMPLEMENTED → TESTED → INDEPENDENTLY ACCEPTED → INTEGRATED → STAGED → DEPLOYED. "Integrated" and
"staged" are set by the integration receipt (`TIWS_INTEGRATION_RECEIPT.md`). Nothing here is DEPLOYED to production.

| Item | Highest status reached | Notes |
|---|---|---|
| Text Intelligence draft desk (TI-AC1..13) | INDEPENDENTLY ACCEPTED (Codex TI r16; TIWS r1-r10) | live: §4 |
| WS hardening | INTEGRATED by its own session (canonical `7160614`) | carried |
| TI + WS combination glue (INT-1, INT-2) | INDEPENDENTLY ACCEPTED | tests fail without the glue |
| L-2 dictation versus commands | INDEPENDENTLY ACCEPTED (r4) | auto-mode residue under L-1 |
| L-4 value-reassignment warning | INDEPENDENTLY ACCEPTED (r4) | recall limits recorded |
| `uri.ti.draft.v1` contract | IMPLEMENTED, TESTED, reviewed (r4) | for A2UI; A2UI itself is not integrated |
| L-9 live verifier evidence | TESTED live | §4 |
| LV-1 fix | REJECTED (r6-r9), reverted | limitation |
| P-GOV-1 (app windows vs GPU lease) | PLANNED: handoff to the lease/launcher owner, which put it to you (the owner) | `P_GOV_1_HANDOFF.md` |
| Performance investigation | Researched; answered with recorded and reused controlled evidence | `TIWS_PERFORMANCE_INVESTIGATION.md` |
| ENV-C3 (c3 test vs Ollama launch method) | Researched; cause narrowed to the launch method; exact exception unknown | §3.2 |
| SCH-ENV-1 (scheduler test vs venv redirector) | Reported to the scheduler owner (through the Integration session) | not TI |
| Speech (microphone, STT, TTS) | Not in this phase (the Live Voice session owns it) | TI input is SIMULATED only |

### 8.2 Cleanup inventory (created by this session; nothing deleted yet; all are outside other sessions' trees)

| Path / item | Kind | Keep? |
|---|---|---|
| `C:\Users\cheta\Development\uri-ti-integ` (branch `integration/ti-on-ws-hardening-20261009`) | git worktree | keep (source of the integration) |
| branch `trial/ti-on-ws-hardening-2831586` | local branch | keep until owner review, then delete |
| `uri-tiws-gate` (trial chain, stopped), `uri-tiws-gate2` (Git Bash Ollama runs), `uri-tiws-gate3` (`1f34cb3` ALL_PASS), `uri-tiws-gate4` (`48d2f78` ALL_PASS) | materialized gate trees + evidence | keep gate4 (final evidence); others deletable after review |
| `uri-ctl-gate` (control at `7160614`, ENV-C3 reproductions `diag_x*.log`) | gate tree | keep until the ENV-C3 note is settled |
| scratchpad worktree `ctl_src` (detached `b02ed4f`) | git worktree | delete (`git worktree remove`) |
| `uri-tiws-rt` (stale, `8288bd8`), `uri-tiws-rt2` (live runs) | runtime trees | rt deletable; rt2 keep until staging is accepted |
| `uri-staging-src` (worktree), `uri-staging`, `uri-staging2`, and the final staging tree named in the receipt | staging | keep the final one; the others are superseded |
| `C:\Users\cheta\Development\tia` | Codex review clone (existed before; reused) | keep |
| `uri-staging-build.log`, `uri-staging*-materialize.log` in `C:\Users\cheta\Development` | logs | copy into evidence, then delete |
| Processes | — | none left running by this session (checked at the end; see the receipt) |
