# URI Phase 1: salvage and cleanup report (Intent Discovery, C4 harness, catalogue, M31)

Date: 2026-10-05. Author: Claude, working alone because Codex has no quota left. Worktree: `C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent`, detached at base `e8e3b65259c45fc823addc3ef8969425a265bd1b`. **Every change here is uncommitted.** Nothing was pushed, merged, cut over, migrated or logged in, and no production state was touched.

This report is my own engineering evidence. It is **not independent acceptance**. Every component I wrote or repaired is marked `REPAIRED / PASSING — SECOND REVIEW PENDING` or `NEW / PASSING — REVIEW PENDING`.

## 0. Acceptance criteria (set before the work)

1. Salvage should leave the codebase with fewer ambiguous paths. Each capability should have one canonical implementation.
2. Every ported file must have recorded provenance: donor commit, blob and hash, plus the exact transformation applied.
3. Confirmed intent must constrain execution, not just set a flag. A downstream proposal that conflicts with it must be rejected and re-planned.
4. Every positive claim must be backed by a test or live run that I executed. Failures and limitations are reported.
5. No authority, grant, approval, ticket or containment check may be weakened, and no guard may be bypassed to get green tests.
6. Recovery must still be possible after cleanup. The canonical source set must be restorable by the offline rollback tool.

## 1. Preservation

| Item | Value |
|---|---|
| Pre-salvage checkpoint | `work/c1/checkpoints/pre-salvage-20261005-093713.zip`, sha256 `0d2125a395f5c92a868bea85810aef2ecc8f5e7ed4bc3902e3f72c6bff224cb0`, 68 files plus `GIT_HEAD`, `GIT_STATUS` and `GIT_DIFF`. Before any edit, I re-verified it byte-for-byte against the live tree: 68/68 hashes matched, `testzip` was clean, and HEAD was `e8e3b65`. |
| Earlier checkpoints | Kept unchanged: `claude-takeover-*`, `claude-c1-c7-source-r3`, `c1`–`c4-c7` provisional, and all `negative_*` fixtures. |
| Donor worktrees | Read only. I edited no file in `uri-m37-m39-integration`, `Uri/_V1`, `.codex/worktrees/intent-discovery/_V1`, `harness-connections-console`, `uri-batch-candidate` or `uri-agent` master. |
| Post-work checkpoints | See the acceptance package, "Checkpoint" section (full, source overlay plus rehearsal, and final). |

## 2. Salvage inventory (what exists, implemented vs planned)

| Capability | Candidates found | Implemented or planning only | Qualification evidence | Decision |
|---|---|---|---|---|
| Deterministic reference resolution (RAR) | `uri_v1/turn/rar_deterministic.py` + `rar_contracts.py` + `rar_clarification_contract.py` on `uri-m37-m39-integration@eb73693` **and** `Uri/_V1@62d564c`. The blobs are identical on both branches. | Implemented and frozen (M35 A2.5 RAR, M33.3 S4 RC-5 repair) | Donor test suites. I ported them and they pass here (§9). | **Salvaged**, as the canonical reference core |
| Reference clarification / binding (S1 BindingService) | `uri_v1/reference_clarification/*` on the same two branches, identical blobs | Implemented and frozen (M33.3 S1, requalified) | Donor S1 tests, ported and passing | **Salvaged**: binding, builder, authority, safeguards, fingerprints, store, session adjunct, facts, attribute narrowing. **Not salvaged:** renderer/bundle (not needed by C5). |
| INT-ARN-1 desktop clarification | `uri_desktop_seams/reference_clarification/*` (service/store/evidence/proposal/wire), wired into the legacy `/ask` and orchestrator on `uri-m37-m39-integration` | Implemented; accepted with amendments after 4 Codex audit rounds | `INT_ARN_1_AUDIT_RECORD.md` | **Not ported. Superseded for Phase 1.** Its durable per-user store and approval identity are covered by the signed session record and the digest-bound approval. Its key defect lesson, "replay after restart" (round 3), was re-applied as the C5 duplicate-execution guard. |
| ARN (adaptive retrieval narrowing) | `uri_core/core/arn/*`, identical on base, `_V1` and m37-m39 | Implemented (ARN.1, accepted) | Base tests | **Reused in place** (canonical, already in base). C5 now uses it for cold-start widening and no-repeat search. |
| Intent workflow controller | `.codex/worktrees/intent-discovery/_V1/experimental/intent_workflow/controller.py` (sha256 `a435ab8ec0f1c001…`), uncommitted | Implemented candidate; Brain-only interpretation; experimental route | 17 scripted tests by Codex; no live trial | **Behaviour salvaged, code not ported.** Kept: the 5-question ceiling, duplicate key/text blocking, revision-bound acceptance, corrections that keep answers and question counts, and corrections that invalidate acceptance. Not kept: the parallel `/desktop/intent` route, the separate cycle store and its Brain-only prompt contract. Those would have added a second controller and store next to C5. |
| Intent Clarification Integration Plan + critical self-review | `Uri/_V1/docs/plans/INTENT_CLARIFICATION_INTEGRATION_PLAN.md` (`152b947a…`), `…_SELF_REVIEW.md` (`8ae04242…`) | **Planning only. Nothing implemented.** | None | **Requirements salvaged.** P1 items are addressed: restart never deserializes binding authority, model output never confirms, there is no second store or route, and no last-write-wins update of unreviewed values. The plan's target (the experimental controller) was not adopted. |
| Correction handling / seeded history / clarification budget | Spread across the controller above, `uri_core/core/clarification.py` (legacy `TASK_REQUIREMENTS`), and the M25 clarification pause in the legacy orchestrator | Legacy path implemented for legacy `/ask` | Legacy tests | Legacy path **RETAINED_FOR_COMPATIBILITY**: the production `/ask` still uses it. Paired C5 never calls it. |
| C4 harness adapters | Phase 1 `uri_core/client_runtime/harness.py` (a minimal port of M38 `uri_v1/execution/harness/*@379769f`); M38 originals on m37-m39 and `_V1`; `uri_v1/desktop_harness` and the harness console in two uncommitted Codex worktrees | Phase 1 port implemented and tested with a fake harness; donors are on other branches | C4 tests | **Phase 1 path is canonical.** Provider knowledge is now split into `uri_harness_adapters/` (§4). Donors stay on their own branches as evidence, and nothing in this tree imports them. |

## 3. Cleanup ledger

| Capability | Donor (branch @ commit) | Donor files | Behaviour salvaged | Planning-only parts | Canonical destination | Competing / superseded paths | Action | Reason | Tests proving chosen path | Tests proving removed path not required |
|---|---|---|---|---|---|---|---|---|---|---|
| RAR resolver | `uri-m37-m39-integration@eb7369331e8c` (= `_V1@62d564cf`) | 3 `uri_v1/turn/rar_*.py` | All 7 deterministic levels, abstention, no invention, no first-item bias | — | `uri_core/reference_binding/rar_*.py` | Donor `uri_v1/turn/*` (decoders, needle/qwen experiments) | Donor experiments **not ported** (left on their branch) | Only the frozen deterministic core is needed | `tests/reference_binding/test_rar_*` (ported) | No C5 code imports `uri_v1`; `uri_v1` does not exist in this tree |
| S1 binding | same | 9 `uri_v1/reference_clarification/*.py` | Rounds, click via ACTIVE_UI, free input, attribute narrowing, fingerprints/staleness, budget and no-progress guards, Change lifecycle | Renderer/bundle | `uri_core/reference_binding/*` | Renderer, bundle, template renderer | **Not ported** (2 donor tests dropped, recorded in PROVENANCE) | C5 renders questions itself from the contract; bundles are unused | `tests/reference_binding/test_s1_*` | `test_s1_core`/`test_s1_binding` pass without them |
| Intent discovery | intent-discovery worktree (uncommitted), plan + self-review | `controller.py`, plan docs | Budget, no-repeat, revision-bound confirmation, correction continuity | The whole integration plan | `uri_core/core/intent_discovery.py` (new) inside `PairedCoordinator` | Experimental controller and `/desktop/intent`; INT-ARN-1 seam | **Not adopted** (left in place on their branches) | Prefer one canonical path over compatibility shims | `test_c5_intent_discovery.py` (17), `test_intent_discovery_unit.py` (18), live §8 | No code in this tree references the experimental controller or seam |
| Missing-file invention | — | — | — | — | Deterministic proposer | `expected_file: "out.txt"` default | **REMOVED** | It invented information the user never gave | `test_harness_request_without_output_file_is_asked_not_invented`, unit harness tests | Harness tests now say the file explicitly |
| Provider-specific harness code in Core | — | — | — | — | `uri_harness_adapters/__init__.py` | Claude/Codex/Antigravity knowledge in `uri_core/client_runtime/harness.py` | **REMOVED from Core** (moved) | Restores the M31 invariant | `test_c4_harness.py` (11), `test_m31_harness_boundary.py` (5) | `tests/test_m31_model_brain_ux.py` restored **unmodified** and passing |
| M31 one-file exemption | — | — | — | — | — | Exemption I added earlier | **REMOVED** (guard reverted to pristine) | The exemption existed only to get green tests | Original guard passes | — |
| Synthetic catalogue overlay + mode monkeypatch | — | — | — | — | `uri_workspace/capabilities_registry.json` entry + real mode loader | `HARNESS_ENTRY` overlay and `load_modes` monkeypatch in `test_c5_loop.py` | **REMOVED** | Superseded by the canonical entry | C5 harness tests (4) on the real catalogue | — |
| Provider names in Core rules | — | — | — | — | Provider-neutral `use the harness to …` | `(harness|claude|codex)` regex | **REMOVED** | The executor is the user's explicit selection | `claude` phrasing now falls back to conversation (unit test) | — |
| Legacy clarification (`clarification.py`, M25 pause, orchestrator) | base | — | — | — | (legacy `/ask` only) | — | **RETAINED_FOR_COMPATIBILITY** | The production product still depends on it; cutover is not authorized | Legacy suites in the full run | — |
| Dev-workflow agent scripts (`scripts/run_codex_*`, `dev_workflow/`) | base | — | — | — | — | — | **RETAINED** (out of scope) | Developer tooling, not URI runtime; outside `uri_core` | — | — |
| Turn State `known_inputs` | base | — | — | — | `turn_state.py` JSON projection | Fact objects leaked into the projection | **REPAIRED** | Latent defect: non-JSON values broke `public_projection` once an intent was pending | C5 quota/harness tests | — |
| Legacy desktop seams / INT-ARN-1 desktop store | m37-m39 | `uri_desktop_seams/reference_clarification/*` | Lesson only (replay after restart) | — | C5 guard | — | **DEFERRED_WITH_DEPENDENCY** (not in this tree) | Retire only with the legacy desktop `/ask` cutover. The legacy product still uses it on its own branch. | — | — |

Preserved regardless of retirement: all audit reports, the donor branches, checkpoints, and the `PROVENANCE.json` files in `uri_core/reference_binding/` and `tests/reference_binding/`.

## 4. Canonical architecture after consolidation

```
client UI / worker (turn_start | turn_intent | turn_decide)
  -> TurnRunner (client): snapshot = sessions + history + files (session-first context);
     needs_context loop (bounded) for server-requested reads (ARN graph widening)
  -> PairedCoordinator (server, trusted composition)
       ReasoningSelectionPolicy (explicit, no fallback)
       prepare_for_paired_client (Turn State, directory, Graphify, real grant intersection)
       proposer (deterministic rules today; Brain seam) -- PROPOSES only
       IntentDiscovery  [uri_core/core/intent_discovery.py]
          signed intent record in SessionState.active_workflow (existing representation)
          RAR + S1 BindingService [uri_core/reference_binding]   (session files, confirmed referent)
          ARNEngine [uri_core/core/arn] cold-start widening (graph), no repeated search
          budgeted clarification (<=5 questions, <=2 unproductive answers, never the same question)
          corrections (explicit old/new, named field, referent rebind, restated tail; else ask)
          explicit digest-bound confirmation (IntentDecision) unless the request was complete & verbatim
          -> Confirmed Intent Contract (digest)
       planner (Brain seam) -> conflicts() vs confirmed intent -> reject + recompile if different
       duplicate-execution guard (server ledger: claimed & unsettled attempt for this intent)
       stale-replay guard (server ledger: newer revision of this intent exists)
       existing evaluate_gates -> approval digest binds args digest AND intent digest
       ClientExecutionControl ticket -> claim -> client executes -> INDEPENDENT verification -> settle
  -> session_update persisted by the client in ONE consented commit with the transcript
     (verified: intent cleared + confirmed referent via update_fact; uncertain: EXECUTION_UNCERTAIN;
      failed/declined: CONFIRMED preserved for explicit retry)
C4: uri_core/client_runtime/harness.py (provider-neutral: capsule, env, bypass refusal, Job Object
    supervision, claim normalisation, registry/qualification) + uri_harness_adapters (Claude/Codex
    argv & parsers, Antigravity refusal) composed only by the client worker.
```

No new execution engine, approval framework, permission model, context store or task state machine was added. Intent state uses the existing `SessionState` fields and the existing client `sessions` store (consented `save_session`).

## 5. Donor commits and hashes

| Donor | Commit | Notes |
|---|---|---|
| RAR / S1 / tests | `eb7369331e8c2ed7c7a8ea85db9ce1382fe3913f` (`uri-m37-m39-integration`). Blob-identical at `62d564cf9d2fa25e5a9860d20dcc7070b112badb` (`Uri/_V1`). | Per-file donor blob, donor sha256 and ported sha256 are in `uri_core/reference_binding/PROVENANCE.json` (sha256 `4b0ab7ac5bc749fc…`) and `tests/reference_binding/PROVENANCE.json` (`aabc11fad09feadc…`). Transformation: import paths only (`uri_v1.turn.*` / `uri_v1.reference_clarification.*` → `uri_core.reference_binding.*`). Tests: also removed 2 tests for modules that were not ported. |
| M38 harness (already ported in C4) | `379769fd486667b62136291dce215e8ab3f06ad1` | Moved unchanged in behaviour into `uri_harness_adapters` |
| Intent workflow controller (behaviour only) | uncommitted on `62d564c`; controller sha256 `a435ab8ec0f1c001…` | Not copied |
| Intent plan / self-review (requirements only) | `Uri/_V1` working tree; sha256 `152b947ab52555ce…` / `8ae04242b1a8516f…` | Planning only |

## 6. Files

**Ported (import rewrite only):** `uri_core/reference_binding/{rar_contracts,rar_deterministic,rar_clarification_contract,attribute_narrowing,authority,binding,builder,facts,fingerprints,safeguards,session_adjunct,store}.py`; `tests/reference_binding/{rar_fixtures,rar_adversarial_fixtures,test_rar_contracts,test_rar_deterministic,test_rar_adversarial_safety,test_rar_stage4_refinements}.py`.
**Adapted:** `tests/reference_binding/test_s1_core.py` and `test_s1_binding.py` (renderer/bundle tests removed); `uri_harness_adapters/__init__.py` (Claude/Codex builders and parsers moved out of Core, unchanged in behaviour).
**New:** `uri_core/core/intent_discovery.py`, `uri_core/reference_binding/__init__.py`, `test_c5_intent_discovery.py`, `test_intent_discovery_unit.py`, `test_m31_harness_boundary.py`, this report.
**Modified (Phase 1 files):** `paired_coordinator.py`, `paired_reasoning.py`, `client_contracts.py` (`IntentDecision`), `client_service.py` (cancel repair), `turn_runner.py`, `turn_service.py`, `client_runtime/harness.py`, `runtime_identity.py` (pins the adapter package and makes it readable to the fixture guard), `scripts/run_uri_client_worker.py`, `scripts/validate_c5_live.py`, `scripts/phase1_offline_rollback.py`, `test_c4_harness.py`, `test_c5_loop.py`, `test_c6_worker_turns.py`, `test_c2_client_state.py`, `test_phase1_offline_components.py`, Flutter `paired_runtime.dart`, `paired_runtime_screen.dart`, `paired_runtime_screen_test.dart`.
**Modified (shared base files):** `uri_workspace/capabilities_registry.json` (+`external_harness_task`, authorized), `uri_core/core/turn_state.py` (JSON-safe `known_inputs`; intent-record inputs).
**Reverted to pristine:** `tests/test_m31_model_brain_ux.py`.
**Removed / quarantined in this tree:** none deleted. The superseded paths listed in §3 lived on donor branches or were in-file code (the overlay, regexes, provider builders) that has been replaced.

## 7. Deferred cleanup dependencies

| Item | Status | Dependency |
|---|---|---|
| Legacy `/ask` clarification (`clarification.py`, M25 pause, orchestrator) | RETAINED_FOR_COMPATIBILITY | Production cutover to the paired runtime (not authorized) |
| INT-ARN-1 desktop seam + `uri_v1` experiment trees on m37-m39 / `_V1` | DEFERRED_WITH_DEPENDENCY | Branch-level retirement decision. Do not delete preserved evidence. |
| Experimental intent workflow controller (Codex worktree) | DEFERRED_WITH_DEPENDENCY | User decision to archive that candidate. It is superseded by C5 intent discovery. |
| Post-execution correction of a stored fact (`memory.update`) | Not implemented | Needs a qualified `memory.update` client capability and verifier. Today a post-execution correction creates a new intent. |
| Brain interpreter/planner transport | Seams + validation only | A provider transport (C5 Brain). It must stay provider-neutral. |

## 8. C5 Intent Discovery evidence

**Live run** (`scripts/validate_c5_live.py`): a real isolated server process on port 18060 using the single-instance launcher, pinned signed identity and DPAPI client credentials. Reads are checked by an independent fresh persistence instance. The server was **restarted twice** as a real process. All steps passed (`ALL_STEPS_PASSED`; count in the acceptance package). Evidence: `work/c1/c5_live_<id>/server/control/c5-live-evidence.json`, located through `work/c1/c5-live-locator.json`.

| # | Scenario | Result |
|---|---|---|
| 1–3 | Ambiguous "the budget report" (two session files); missing referent detected; clarification offers 2 options; nothing executed | PASS |
| 15 | Real server restart while the question is pending | PASS. The answer bound the referent and `questions_asked` stayed 1 (the binding round was rebuilt from fresh evidence; authority was never deserialized). |
| 4 | Answer "the Q4 one" | PASS (TENTATIVE binding shown for confirmation) |
| 12–13 | "actually it is due on Monday, not Friday" | PASS. Only the date changed. Friday is in `superseded`. |
| 14 | Every argument token comes from the user or the bound title | PASS |
| — | Confirming with the superseded digest | PASS: refused with `INTENT_DECISION_STALE` (no false CONFIRMED) |
| 5–6 | Explicit confirmation; approval bound to the intent digest; identical arguments; `replanned=false` | PASS |
| 7–8 | Reversible write executed and independently read back | PASS |
| 9 | Intent cleared; confirmed referent stored as a session fact (`update_fact`) | PASS |
| 10/11/16 | Follow-up "it was approved by Priya": bound session-first, 0 questions | PASS |
| 17 | Unknown "the expense form": ARN checked the session, then widened once to the graph via server-requested context, then asked; nothing invented | PASS |
| 18 | A drifting planner proposed "Plan A … rejected": rejected (`action_changed`, `input_changed:request_text`) and recompiled to "Plan B … approved" | PASS. **In-process real app on separately provisioned roots** (it needs an injected planner). Labelled as such. |
| 19 | Ungranted client blocked | PASS (earlier step) |
| 20 | Executor failure: `SETTLED_FAILED`, nothing stored, CONFIRMED intent preserved; explicit retry executes exactly once | PASS (client-side fault injection) |
| 21 | Crash after claim, then real restart, then re-confirm: `INTENT_EXECUTION_UNCERTAIN`, no new approval, nothing stored | PASS (fault injection) |

Not real in this evidence: there is no Brain (deterministic rules plus seams), no native harness, and the faults are injected as listed.

## 9. Defects found during this run (all repaired, each with a regression test)

| ID | Where | Defect | Found by | Repair / regression |
|---|---|---|---|---|
| S1 | deterministic proposer (my C5 code) | Invented `expected_file: "out.txt"` when the user gave none | Salvage review | Removed; `test_harness_request_without_output_file_is_asked_not_invented` |
| S2 | `turn_state.py` (shared, latent) | `known_inputs` leaked Fact objects, so the C5 context hit `JSON_REQUIRED` once a pending intent existed | C5 harness test | JSON projection; C5 quota test |
| S3 | my intent code | Re-confirming after a crash could re-dispatch the same intent, because the client never persisted "uncertain". This is the same class as INT-ARN-1 round 3. | `test_uncertain_execution_is_not_repeated_by_reconfirming` | Server-ledger duplicate-execution guard |
| S4 | `client_service.cancel` (D1 slice, second pass) | An `executing`/`execution_uncertain` turn could be relabelled `cancelled`. That hid a possible effect and would defeat S3. | Revisit of the D1 slice | First repair refused the cancel (`TURN_EXECUTION_IN_PROGRESS`). That broke an existing C5 test and showed an availability defect: the session stayed locked for 15 minutes after a crash. **Second repair:** cancel releases the session but sets `execution_uncertain` (never `cancelled`). Regression tests: `test_cancel_never_relabels_claimed_or_uncertain_execution`, and the updated `test_interrupted_executor_is_uncertain_and_never_redispatched`. |
| S5 | my correction parser | Bare negation ("it is not due on Friday") parsed as an old/new pair and produced "…is it is". This is the "complex correction → unsupported assumption" class. | Self-audit | A comma is required for "X, not Y"; otherwise URI asks. `test_regression_bare_negation_is_never_parsed_as_old_new_pair` |
| S6 | my intent code | "I don't know" became a user-supplied referent | Self-audit | Non-answer filter; `test_regression_non_answer_never_becomes_a_referent` |
| S7 | my intent code | "no, the Q4 one" answering a choice was treated as a correction | Self-audit | Routed as an answer; regression test |
| S8 | my intent code | One unproductive answer ended clarification, and the next round dropped the displayed choices (empty-scope round) | Self-audit + unit test | One distinct re-ask variant; empty-scope round closed. Regression test. |
| S9 | my intent code | Interpreter values were checked as a token subset, so a model could drop "not" | Self-audit | Verbatim (contiguous) check; regression test |
| S10 | my intent code | A replayed, validly signed OLDER revision could resurrect superseded meaning | Self-audit | Server-ledger revision check, `INTENT_STATE_STALE`; `test_replayed_older_signed_record_cannot_resurrect_superseded_meaning` |
| S11 | my intent code | A tampered record was cleared only on decisions | Self-audit | Cleared on any turn; regression test |
| S12 | `_extract_remember` | "remember that" produced the statement "that" | Unit test | Word-boundary regex. While repairing this, a heredoc bug wrote literal backspace bytes; I found it, fixed it, and grep-checked every touched file for `\x08`. |
| S13 | my live validator | The in-process app shared a control root with the real server process, which violates the C1 single-instance invariant | Live run (429) | Separate provisioned roots for step 18 |
| S15 | `KNOWN_CAPABILITY_EFFECTS` | Adding `external_harness_task` to the catalogue without a verified effect failed `test_known_effects_dictionary_covers_all_shipped_tools` | Full suite | Registered as `LOCAL_WRITE` (it writes only a client workspace copy) |
| S14 | Pronoun heuristic | "this must not be stored" was treated as a reference | Live run | Only "it/they" count as entity pronouns. Limitation noted in §11. |

## 10. Tests run at the end

See the acceptance package §"Test and live evidence" for the final numbers. They are recorded only after each run completed.

## 11. Known limitations (honest)

* Reference detection is heuristic: a leading "it/they", or "the/that/this + one of ~25 document nouns". A reference outside that pattern is not detected and the statement is stored verbatim. That is not invention, but it may be imprecise. A Brain interpreter seam exists to improve this, and any value it produces must still pass the verbatim/grounding checks.
* Corrections are deterministic and conservative. Anything ambiguous makes URI ask "which detail should change?".
* BindingService rounds are process-local. After a restart they are rebuilt from fresh evidence when every scoped candidate fingerprint still matches. Otherwise URI asks again and reports `reissued_after_restart`.
* The signed record protects integrity, not confidentiality. The intent text lives in the client's DPAPI-scoped store.
* The conflict check compares the full compiled inputs. Any planner elaboration that changes an input is treated as a conflict, by design. Planner-added inputs need a schema-declared elaboration key, which does not exist yet.

## 12. Corrected milestone verdicts

See `CLAUDE_PHASE1_ACCEPTANCE_PACKAGE.md`, which holds the authoritative table for this run.
