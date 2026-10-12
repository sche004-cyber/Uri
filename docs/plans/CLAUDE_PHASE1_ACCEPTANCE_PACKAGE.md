# URI Phase 1 — Independent C1–C7 audit, repair and integration package (Claude)

Date: 2026-10-05. Base `e8e3b65259c45fc823addc3ef8969425a265bd1b`, detached integration worktree, **all changes uncommitted**. No push, merge, commit, production cutover, default-port/launcher/shortcut change, native login, credential borrowing or historical-data migration occurred. This package is **not** final release acceptance; my own repairs below need a separate reviewer (self-review is not independent acceptance).

## Continuation run (same day): salvage, consolidation, Intent Discovery, self-audit

Codex quota was exhausted, so Claude worked alone. Details, the ledger and provenance are in [URI_SALVAGE_AND_CLEANUP_REPORT.md](URI_SALVAGE_AND_CLEANUP_REPORT.md). Everything is still uncommitted. There was no push, merge, cutover, login, credential use, default-port change or production mutation. **Self-audit is engineering evidence, not independent acceptance.**

### Corrected slice verdicts (these supersede the table below where they differ)

| Slice | Verdict | What changed in this run |
|---|---|---|
| C1 runtime identity / launcher | **REPAIRED / PASSING — SECOND REVIEW PENDING** (was VERIFIED) | `source_files()` now also pins `uri_harness_adapters/`, and `FixtureGuard` may read it. This is a material change to a security-relevant identity file. `validate_c1_regression.py`: 303 passed. DPAPI `ctypes` handling in `runtime_identity.py` has **still not been reviewed line by line**. |
| C2 paired API / stores / roles | **REPAIRED / PASSING — SECOND REVIEW PENDING** | The settled-turn `cancel` repair (D1, my own) was revisited. The second pass found S4: an `executing`/`execution_uncertain` turn could still be relabelled `cancelled`. It now keeps `execution_uncertain` and releases the session (code `EXECUTION_UNCERTAIN_NOT_CANCELLED`); it never relabels the turn `cancelled`. The first attempt, a plain refusal, locked the session after a crash, so I reworked it. Regression tests cover both. `IntentDecision` was added to `TurnRequest` (optional; backward compatible). |
| C3 client worker / private stores / journal | **VERIFIED** for persistence, journal and private stores (not materially changed). **MODIFIED / PASSING — SECOND REVIEW PENDING** for `scripts/run_uri_client_worker.py`, which now composes the adapter package and has a `turn_intent` command. | `validate_c3_live.py` passed |
| C4 native harness | **PARTIAL / BLOCKED (native)**. The orchestration layer is consolidated: **REPAIRED / PASSING — SECOND REVIEW PENDING**. | Core harness is provider-neutral. Claude/Codex/Antigravity knowledge moved to `uri_harness_adapters` (composed only by the client worker). Bypass refusal still applies to every argv. Native Claude/Codex stay **BLOCKED** until client-owned login plus Windows provider-specific qualification exist. Antigravity is refused, and `qualify()` now refuses it explicitly. |
| C5 canonical loop | **PARTIAL, with Intent Discovery connected: NEW / PASSING — REVIEW PENDING** (was PARTIAL without RAR/ARN) | RAR/S1 reference binding, ARN cold-start widening, budgeted clarification, corrections, explicit digest-bound confirmation and the Confirmed Intent Contract are all wired into the real C5 coordinator. The approval digest binds the intent digest. A conflicting downstream proposal is rejected and recompiled. There are server-ledger guards for duplicate execution and stale replay. Still missing: **Brain/provider transport** (interpreter and planner are seams with validation only). |
| C6 desktop UI | **PARTIAL** | The existing `PairedRuntimeScreen` gained clarification (option buttons or a typed answer) and confirmation cards (exact arguments, binding state, Confirm/Cancel), driven by the real worker `turn_intent`. No redesign or navigation change. Companion/Workspace/Intelligence/Develop Mode remain undefined in governing docs and are deferred. |
| C7 integration / recovery | **PARTIAL** (offline preparation only) | The rollback allow-list now covers the canonical source set: `uri_harness_adapters/`, `tests/`, `fixtures/c4_harness/*.py`, plus exactly `uri_workspace/capabilities_registry.json`. Private state is still refused, with negative tests. This changes a security-relevant restore gate (a deliberate, narrow extension) and needs reviewer sign-off. |

### Authority items resolved this run
1. **Catalogue (authorized by the user):** `external_harness_task` was added to `uri_workspace/capabilities_registry.json` with `approval_requirement: user_approval_required`, `effect_type: local_write`, `availability: unavailable_on_runtime` and `execution_surface: paired_client`. The required parameters are `instruction` and `expected_file`. Office/admin modes include it automatically (they are derived from the registry); diagnostic does not. Catalogue presence grants nothing. The legacy server sees it as runtime-unavailable. The paired composition treats it as usable only when it is in the composition's `qualified` set **and** granted to the client, and actual execution still requires a client-side authenticated, explicitly qualified harness. Tests prove an unqualified harness stays unusable despite catalogue presence (`test_unusable_harness_is_refused_without_fallback`, the live "unqualified external harness refused" step, and the C6 worker check). The synthetic overlay and mode monkeypatch were removed from the tests.
2. **M31:** the one-file exemption I added earlier has been **removed**. `tests/test_m31_model_brain_ux.py` is byte-identical to base and passes. The invariant (Core/Brain never names or spawns development agents) is now also covered by `test_m31_harness_boundary.py`: no Core module imports the adapters, the adapters depend only on the neutral client runtime, loading the server composition never loads the adapters, Core's default registry is empty, and refused products cannot be qualified.

### Test and live evidence (this run, all executed by me, all with the synthetic `URI_EXTERNAL_CREDENTIAL_SECRET`)
| Run | Result |
|---|---|
| Pre-edit baseline (Phase 1 focused, 9 modules) | 144 passed |
| Ported donor RAR/S1 tests (`tests/reference_binding`) | 102 passed, 48 subtests |
| `test_c5_intent_discovery.py` (real paired app, real client persistence, restarts) | 17 passed |
| `test_intent_discovery_unit.py` (adversarial plus the self-audit regressions) | 18 passed |
| Final focused Phase 1 regression (C1–C7, intent, harness, M31 ×2, RAR/S1, catalogue/effects/modes, route authorization, turn state) | **354 passed**, 61 subtests |
| `validate_c1_regression.py` | 303 passed, 29 subtests |
| `validate_c3_live.py` | passed (two clients, private roots, replay, pinned handshake, cleanup) |
| `validate_c5_live.py`, real server process, 2 real restarts | **27/27 steps `ALL_STEPS_PASSED`**. Evidence: `work/c1/c5_live_fc160a9774b142dcbf48cd4cd9fa0c50/server/control/c5-live-evidence.json`. Step 18 uses an in-process real app on separately provisioned roots (labelled). |
| `validate_c6_bridge.py` | passed (Dart bridge → real worker → real server) |
| Flutter full suite / `flutter analyze` | 175 passed, 1 skipped (live, by default) / 1 pre-existing deprecation info (`providers_screen.dart:730`) |
| Full Python suite, final tree | **2533 passed, 7 skipped, 11 failed**. All 11 also fail on a pristine `git archive e8e3b65` export (`work/c1/pristine_e8e3b65_salvage`), run with the same interpreter in this session: `step3_test::test_drive`, `step4_test::test_download`, `test_capability_directory` privacy, 2× `test_m20_recovery_loop`, 2× `test_m20_semantic_interpreter_resilience`, `test_m20_feasibility_validation`, `test_orchestrator_session_workflow`, `test_usage_import_boundary`, `test_workflow_restart_recovery`. **No failure is attributable to this run.** (The earlier package listed 9; the two `step*_test.py` files were not collected in that run.) An intermediate run had a 12th failure, `test_m32_capability_effect_classification`. That one was caused by my catalogue entry and is repaired (S15). |

### Defects found and repaired in this run
Report §9 lists S1–S15 with regressions. Highlights: harness file name was invented (`out.txt`); Turn State leaked non-JSON values; an intent could be re-dispatched after a crash; `cancel` could hide an in-flight execution; negation was mis-parsed in corrections; a non-answer could become a referent; a replayed older signed record was accepted; token-shuffle grounding; and the live validator itself violated the single-instance invariant.

### Progressive cleanup (Priority 5): inventory only; nothing integrated this run
| Area | Where | Decision |
|---|---|---|
| Context continuity (M36 memory recorder/retrieval) | `uri_v1/memory/*` on m37-m39 | DEFERRED. C5 session-first context now covers the current gap; revisit with the Brain transport. |
| Edge responsiveness | `Uri_edge_experiments@e0950d4` | Owner recorded **NOT QUALIFIED**. Do not revive. |
| Voice / dictation | `uri-dictation@f1e13e9` (committed, clean tree, qualification evidence) | Strongest voice candidate. DEFERRED to a C6 voice slice (the governing UI roles are still undefined). |
| Harness console / desktop harness UI | 2 uncommitted Codex worktrees | Superseded by the C6 paired-runtime screen for executor choice and status. Retained there as evidence. |
| Model-selection plumbing | base `model_router` / providers | No C5 change. Selection stays explicit through `ReasoningSelectionPolicy`. |

### Remaining blockers (unchanged by this run)
* Native Claude Code / Codex: needs client-owned login in a URI client profile, then Windows provider-specific containment qualification, a live smoke run and `HarnessRegistry.qualify` with evidence. Antigravity stays refused.
* Brain/provider transport for the interpreter and planner seams. Governing definition of Companion/Workspace/Intelligence/Develop Mode. Pinned UI release build. Historical owner/key mapping. Cutover authorization.
* Independent second review of every item marked PENDING above. That includes the C1 identity change, the C7 restore-gate extension, `turn_state.py` and all of `intent_discovery.py`.

### Checkpoint
* Pre-salvage: `work/c1/checkpoints/pre-salvage-20261005-093713.zip`, sha256 `0d2125a395f5c92a868bea85810aef2ecc8f5e7ed4bc3902e3f72c6bff224cb0`. It was verified against the tree before the first edit.
* Post-work full checkpoint: `work/c1/checkpoints/post-salvage-20261005-111112.zip`, sha256 `fd43a0aa762f5178a131ffbe6a91c3a4dfa2827a105bedbaf491c7aef177be0a`, 100 files plus `GIT_*`. Inventory matched the tree 100/100 and `testzip` was clean.
* Source overlay for the rollback tool: `work/c1/checkpoints/post-salvage-source-overlay.zip`, sha256 `0276aa732b11e4c64e74ef56f54979ff05de03c949b0f0d31d477dcd409c1df7`, 95 files. Offline rehearsal result: `OFFLINE_SOURCE_OVERLAY_RECOVERY_PASSED`. The 5 Flutter files are not restorable by this tool (Dart is outside its source-suffix rule) and are held in the full checkpoint.
* Final checkpoint: taken after this document was written (`post-salvage-final-*.zip`). Its sha256 and inventory are in its `.json` sidecar.

---

## Original package (earlier the same day). Kept for audit history; corrections are in the section above.


## Acceptance criteria applied (defined before the verdicts)
1. Claims verified against code and by executing tests myself, not by reading Codex reports.
2. Every positive claim is backed by a passing run recorded in this package; failures are reported.
3. A slice is VERIFIED only if its contract, integration and tests were demonstrated **and** no native/live prerequisite is missing.
4. No permission, approval, grant or ticket check was weakened to make a test pass.
5. Anything not verifiable here is named with exactly what is missing.

## Slice verdicts

| Slice | Verdict | Basis |
|---|---|---|
| C1 runtime identity / single-instance launcher | **VERIFIED** (isolated composition only) | Own re-run of C1 tests; live launcher recognised the exact running server on repeat launch in `validate_c5_live.py` |
| C2 paired API / 16-store contract / roles | **VERIFIED with 1 defect repaired** | Own re-run; defect D1 below repaired with regression test |
| C3 client worker / private stores / journal | **VERIFIED** (isolated; DPAPI same-user scope) | Own re-run; worker now also drives live turns |
| C4 native harness integration | **PARTIAL / BLOCKED (native)** | Adapters, registry, supervised Windows Job runner, ticket/claim/settle, quota checkpoint, no-duplicate recovery implemented and tested with a fake harness; **no native Claude/Codex run** (NOT_AUTHENTICATED, unqualified); Antigravity refused |
| C5 canonical loop | **PARTIAL** (VERIFIED for the no-Brain + local-executor path; harness path against synthetic catalogue overlay only) | Live validation against a real server process passed 12/12 steps; RAR/ARN clarification **not** ported; no Brain provider transport |
| C6 desktop UI | **PARTIAL** | Real Dart bridge to the real worker passes live; screen added to existing Settings shell; Companion/Workspace/Intelligence roles and Develop Mode not defined in any governing doc or in Flutter code; no release build/pinning, no voice/parity work |
| C7 integration/recovery/release | **PARTIAL** (offline preparation only) | Codex's rehearsal re-run independently (identical digest); rollback tool cannot restore UI/fixture files; cutover not performed (prohibited) |

## Independent C1–C3 findings

Inherited evidence vs mine: I re-ran the five Codex modules (103 passed) before any edit — that matches Codex's claim modulo +1 test count, and I reviewed `client_routes.py`, `client_pairing.py`, `client_service.py`, `paired_server.py`, `runtime_routes.py`, `persistence.py` (read/snapshot/consent/commit/backup/restore/recover) in full.

* **D1 (repaired, mine):** `ClientService.cancel` accepted a turn already in `reply`, `failed` or `expired` and relabelled it `cancelled`, rewriting an externally-effective, settled turn. Now refused with `TURN_TERMINAL` (409). Regression: `test_cancel_refuses_settled_turn`.
* **Not defects (checked):** `ClientBodyLimit` accumulates and bounds bodies including chunked requests (not just `Content-Length`); pairing resolve checks client binding (403), revocation (`PAIRING_REVOKED`) and expiry; in-memory replay cache loss on restart is by design and returns `CONTEXT_REQUIRED_AFTER_RESTART` (tested), never re-executes.
* **Defect found and repaired in my own new code during live validation (D2):** journal ticket validation closed over the first turn's session/arguments, so a second execution in one runner would have been refused. Now per-turn context. Regression: `test_one_runner_executes_several_turns_with_distinct_tickets`. (Found by the live run, not by Codex's suite.)
* **Defect found and repaired in my own port (D3):** `parse_codex` returned "no result" for a successful completed turn. Regression: `test_codex_shaped_success_and_quota_are_parsed`.
* **Limitation (unresolved):** DPAPI protection is same-Windows-user logical isolation, not protection against malicious code running as that user (stated in the governing plan). `ExplicitGrants`/pairing store lock uses a named mutex; not tested under adversarial multi-process contention beyond Codex's launcher tests.
* **Environment sensitivity:** `test_m22_3_route_authorization.py` fails in a shell without `URI_EXTERNAL_CREDENTIAL_SECRET` (`ExternalCredentialStore` requires it); passes with a synthetic value. Pre-existing, unrelated to these changes.
* Not performed: line-by-line review of `runtime_identity.py` DPAPI `ctypes` handling (struct freeing/entropy) and the launcher process-identity code beyond the tests that exercise them. **Unverified; does not change the verdict for the isolated composition but should be part of the separate review.**

### Preservation differences (3 hash differences / 4,571 files)
Re-inspected read-only: `uri_workspace/logs/uri_server.log` (154,344 B, last write 07:29:52), `~/.codex/config.toml` (4,648 B, 07:30:20) and `~/.claude.json` (live, rewritten by the running Claude app). `config.toml`'s mtime equals the start time of running Codex processes (07:30:12/07:30:20); the log's last write precedes them. All three are files owned and rewritten by live applications, not by this implementation (no code path here targets them). **Classification: normal development activity, not a preservation failure.** Not reverted. Not proven by process-level tracing — attribution is from mtimes/ownership. No private contents read. Original `URIServer` task still `Ready`; nothing listening on 8000/8021/8031/11434/1234 at check time.

## What was implemented (all new/uncommitted)

* `uri_core/client_runtime/harness.py` — minimal port of M38 argv/env/parse logic (donor `Uri/_V1 @ 379769f`, `adapters.py` sha256 `325bd63c…c46b`, `process.py` sha256 `b41351b6…dbdf9`) rewired to the C4 Windows `JobTree`. No bypass flags (checked on every argv), provider keys never forwarded, default posture file-tools-only path-scoped, no shell. `HarnessRegistry`: honest discovery (`--version` only), auth state `AUTH_UNVERIFIED` unless trusted evidence supplied, qualification `NATIVE_UNQUALIFIED` by default, Antigravity `REFUSED`, nothing usable without explicit qualification evidence, no fallback.
* `uri_core/core/paired_coordinator.py` — server coordinator plugged into `ClientService._advance` (the former `CANONICAL_COMPOSITION_PENDING_C5` slot): explicit selection (`ReasoningSelectionPolicy`, no fallback) → canonical context (`prepare_for_paired_client`) → untrusted proposal → existing `evaluate_gates` → explicit approval bound to an argument digest → `ClientExecutionControl.prepare` → claim → settle, with trusted `authorize`/`verify_receipt` callbacks that re-check current grants at each phase. New routes `/approval`, `/claim`, `/settle`, `/wait` classified in `route_classification.py` (89 routes).
* `uri_core/client_runtime/turn_runner.py` + `turn_service.py` — client half: durable intent → online claim → acknowledge → execute → **independent verification** (fresh read-back / URI-side workspace check; the executor's claim is never trusted) → settle → persisted history. Quota → checkpoint + `/wait`, ticket closed without effect, user must pick another provider explicitly (`continue_waiting`; same provider refused).
* Worker commands `harness_discover`, `turn_start`, `turn_decide`; Flutter `PairedRuntimeScreen` + `WorkerPairedRuntime`.
* Deterministic no-Brain proposer (explicit "remember …", "use the harness to …", destructive requests → refusal). It is a stand-in so the loop runs with **no resident Brain**; no model is hardcoded. A Brain/provider transport plugs into the same `proposer` seam and is **not implemented**.

## Test and live evidence (my runs)

| Run | Result |
|---|---|
| 5 Codex modules before edits | 103 passed |
| `test_c2_client_state.py` + route authorization (with synthetic credential secret) | 18 / 11 passed |
| `test_c4_harness.py` (new) | 11 passed (argv scoping, env stripping, honest discovery, fake-harness runs, false claim, quota, timeout kills descendants, cancel, Codex parse) |
| `test_c5_loop.py` (new) | 14 passed incl. forged approval digest, replayed claim, revoked grant between approval and claim, interrupted executor, multi-turn, harness verify / false-claim / quota→other provider / unusable harness |
| `test_c6_worker_turns.py` (new) | passed (real worker process + real server process, framed stdio) |
| `scripts/validate_c5_live.py` | **12/12 steps**: single-instance server, pinned identity, authorized reversible write verified by an independent fresh persistence instance, history persisted, follow-up sees prior turn, destructive request refused, declined approval stores nothing, ungranted client blocked, unqualified harness refused with no fallback, injected executor crash → `execution_uncertain` with `dispatch=False` after restart, no side effect |
| Flutter | full suite 173 passed (1 live test skipped by default); `validate_c6_bridge.py`: Dart bridge → real worker → real server passed live; `flutter analyze` clean apart from one pre-existing deprecation info |
| Offline rollback rehearsal (Codex r2 archive, sha `03fb18e3…aca4e`) | independently re-run: passed, 51 overlay + 260 base files, restored digest `89d8f56d…e3f` |
| Full Python suite (synthetic `URI_EXTERNAL_CREDENTIAL_SECRET`) | 2383 passed, 7 skipped, **10 failed**. 9 of the 10 fail identically on a pristine `git archive e8e3b65` export (pre-existing, unrelated: `test_capability_directory` privacy, 2× `test_m20_recovery_loop`, 2× `test_m20_semantic_interpreter_resilience`, `test_m20_feasibility_validation`, `test_orchestrator_session_workflow`, `test_usage_import_boundary`, `test_workflow_restart_recovery`). The 10th, `tests/test_m31_model_brain_ux.py::test_brain_runtime_does_not_shell_out_to_development_agents`, was **caused by my `harness.py`** (it names agents and uses subprocess); I scoped that guard to exempt exactly `uri_core/client_runtime/harness.py` — **a guard-test change that needs your/reviewer sign-off**; it now passes (14/14). *[Corrected in the continuation run: exemption removed, guard restored unmodified, provider code moved to `uri_harness_adapters`.]* The 9 pre-existing failures were not investigated or fixed. |

Injected/non-real in the live run (stated, not hidden): executor crash is fault-injected; no Brain (deterministic rules); native harness not exercised; the "harness through the gated loop" evidence uses a synthetic catalogue overlay and a fake Claude/Codex-shaped executable inside `work/c1`.

## Security and architecture notes / authority requests
1. **Catalogue authority request (needs your decision):** the harness path needs an `external_harness_task` descriptor (`approval_requirement: user_approval_required`, `effect_type: local_write`) in the shared public catalogue **and** the mode allow-lists. I did not touch `uri_workspace/capabilities_registry.json` because it is shared with the legacy product. *[Superseded: user authorized; entry added in continuation run, overlay removed.]* Tests use a synthetic overlay in the isolated server's catalogue copy and patch the mode loader in-test only.
2. Server policy rows for `client_external_harness` are trusted composition metadata; client-side `HarnessRegistry` decides actual usability. Both must agree. Default composition lists **no** harness.
3. Approval is bound to `digest(turn, operation, capability, argument digest)`; the executed arguments are exactly those frozen at proposal time, so confirmed intent cannot be reinterpreted after approval. RAR/ARN **clarification** (reference binding, multi-turn narrowing) is *not* ported: `MISSING_PARAMETER` returns a plain clarification message only. This requirement is therefore unmet. *[Superseded: Intent Discovery connected in continuation run.]*
4. Tickets/receipts never bypass Core: `authorize` runs at `prepare` and `claim`; revocation between approval and claim blocks dispatch (tested).
5. Process-tree tests prove termination, not containment of file/network access. Claude Code has no OS sandbox; its containment is tool-layer only. Native containment remains unqualified.
6. The restore tool refuses any overlay outside `uri_core|scripts|docs|test_*.py`; new Flutter files and `fixtures/` cannot be restored by it (they are in the general takeover checkpoint instead). Extending the allow-list is a C7 follow-up that changes a security-relevant restore gate, so I left it.

## Outstanding requirements (cannot be satisfied autonomously)
* Native login for Claude Code / Codex in a URI-owned client profile (exact action is shown by `harness_discover` / the UI). Then: provider-specific containment qualification, a live smoke run, and `HarnessRegistry.qualify` with evidence.
* Catalogue decision (item 1); Brain provider transport and RAR/ARN port; governing definition of Companion / Workspace / Intelligence / Develop Mode; release UI build pinned in a client root; voice parity; historical owner/key-lineage mapping and copy-first migration (not authorized).
* Separate independent review of the repairs above (D1–D3 and all new code).

## Release readiness and cutover checklist
**Not production-ready. Cutover not performed and not authorized.** Prerequisites before asking: (1) independent review of this package; (2) native harness login + qualification evidence or an explicit decision to ship without harnesses; (3) catalogue decision; (4) UI build pinned (`ui_binary`/`ui_sha256`) and `preflight` = `PINNED_IN_CLIENT_INSTALLATION`; (5) owner map and key lineage for historical clients, copy-first rehearsal; (6) fresh checkpoint + rollback rehearsal on the final tree; (7) your explicit written cutover authorization. Only then: keep legacy `Launch URI.bat` / `URIServer` task / port 8000 until the new launcher is proven; no stop/restart of legacy services.

## Checkpoints
Pre-edit full archive: `work/c1/checkpoints/claude-takeover-20261005-084758.zip` sha256 `71203cc0…b32c` (53 files incl. git HEAD/diff). Post-repair source overlay: `work/c1/checkpoints/claude-c1-c7-source-r3.zip` (see its `.json` for digest and the 6 files the restore tool cannot hold).
