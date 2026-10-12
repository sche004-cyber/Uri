# URI Phase 1: second review, repair and continuation

Date: 2026-10-05. Reviewer: Claude (a fresh session, working from primary evidence). Worktree: `C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent`, detached at `e8e3b65`. **Every change is uncommitted.** Nothing was pushed, merged, cut over or logged in. The production launcher, default ports and production state were not touched.

**This is not independent acceptance.** It is a second review of work done in an earlier session, so some findings are independent of that implementer. Every repair below was made by me and has been validated locally only. Whatever I repaired is labelled **implementation repaired and locally validated**. Someone other than me must review it before it can count as accepted.

## Acceptance criteria (set before the review)

1. Each security-relevant claim is checked against code and against an attack I ran myself. Passing tests from the previous session do not count as evidence.
2. Each defect is first reproduced as a failing test, then repaired at the smallest layer, then re-run.
3. No gate is weakened, and no test is changed to make a defect pass.
4. The real C5 restart sequence is re-run after all repairs.
5. The pre-existing full-suite failures are confirmed on a pristine export that I made myself.

## Checkpoints

- Before review: `work/c1/checkpoints/review2-pre-20261005-140453.zip`, sha256 `f12eb8948eedb31c1ca068e9c29c542e6b05ffa3764ff0d52ad806399c0b8bf7`, 100 files. The inherited `post-salvage-final-20261005-111140.zip` was re-verified first. Its sha256 was `2ffbc0bb…925544`, as reported. Its inventory matched the live tree 100/100, `testzip` was clean, and the inventory covered every changed file.
- After review: see the final section, which is written after the last run.

## Defects found and repaired

Each entry below is **implementation repaired and locally validated**.

| ID | Area | Defect (with how it was proven) | Repair | Regression test |
|---|---|---|---|---|
| R1 | C1 source pinning | **Stale bytecode bypass.** Python runs a timestamp-valid `__pycache__/*.pyc` even under the exact launch flags `-B -I`. So the hashed `.py` and the code that actually ran could differ. Shown directly: the source hash matched while the code printed `EVIL`. The same gap applied to extension modules and sourceless `.pyc` files that shadow a `.py`, to files edited or added after validation (lazy imports), and to namespace-package portions. **Real finding:** pywin32 merges `.venv/Lib/site-packages/win32/scripts` into the `scripts` namespace. | `runtime_identity.install_source_pin`, called by both entrypoints straight after manifest validation. Bootstrap imports compile from source, because the cache prefix is a fresh, non-existent directory. Every module already imported must match its pin. After that, `PinnedSourceFinder` compiles exactly the pinned bytes for `uri_core`, `uri_harness_adapters` and `scripts` (codes `C1_SOURCE_DRIFT` and `C1_SOURCE_NOT_PINNED`). Namespace packages are pinned to the source-root portion only. The launchers also verify from source. | `test_c1_source_pin.py`. It includes a control test showing the attack works without the pin, and a real launcher start with planted bytecode. |
| R2 | C1 catalogue pin | Validation pinned `state/uri_workspace/capabilities_registry.json`. The paired `ClientService` reads `state/catalogue/capabilities_registry.json`, which was never checked. It is also re-read on every call, so a change after start was never checked either. | Both seeded copies are validated. `PinnedCapabilityRegistry` honours the runtime copy only while it still matches the manifest pin; otherwise it is empty and permits nothing. | `test_phase1_fail_closed.py` (both tests) |
| R3 | C1 DPAPI | Line-by-line review. The `DATA_BLOB` layout, flags and argument order are correct. Defects in hygiene and robustness: plaintext key material was not zeroed before `LocalFree`, the input copy was not zeroed, `argtypes` were changed on the process-wide `windll` objects, and inputs were not type- or size-checked. | Private `WinDLL` handles with full prototypes, zeroing of both buffers, input checks. Behaviour is unchanged. | `test_dpapi_round_trip_and_tamper` |
| R4 | C2 uncertainty | **Idle expiry erased uncertainty.** A claimed (`executing`) turn whose client crashed was relabelled `expired` after 15 minutes. Re-confirming then went to a fresh approval, so the same intent could be dispatched twice. A settled `execution_uncertain` turn was relabelled the same way. | `_expire` keeps `executing` and `execution_uncertain` turns as `execution_uncertain`, and never prunes them. | `test_idle_expiry_never_erases_a_claimed_attempt`, `test_settled_uncertain_turn_is_not_relabelled_by_expiry` |
| R5 | C2 uncertainty | **False terminal state by receipt.** After dispatch, a client receipt with outcome `cancelled` was accepted, which hid a possible effect and unlocked re-dispatch. | Outside the provider-quota path, `settle` refuses `cancelled` after dispatch (`RECEIPT_CANCEL_AFTER_DISPATCH`). | `test_client_receipt_cannot_cancel_a_dispatched_attempt` |
| R6 | C2 uncertainty | **Crash between the provider wait and settle** left the turn `waiting_for_model` while the guard ignored it. That meant re-dispatch. Cancelling such a turn labelled it `cancelled`, and pruning after 30 days would later drop it. A `remember_fact` attempt could also be quota-paused, then closed as `cancelled`. | A durable `dispatched` flag plus `execution_closed`/`execution_outcome` on the turn. The guard treats any turn that was dispatched and not closed as possibly executed. `cancel` keeps it `execution_uncertain`. Only provider-executed capabilities (`external_harness_task`) may use `/wait`. | `test_dispatched_provider_wait_never_becomes_cancelled_or_rerunnable`, `test_local_write_cannot_be_paused_for_quota_and_closed_as_cancelled` |
| R7 | C5 replay | **Verified intent replay.** Restoring the client session from before execution and confirming again reached a second approval for an intent that had already executed. | The server-ledger guard `INTENT_ALREADY_EXECUTED`. Intent lineage (revision and verified state) survives the 30-day ledger pruning as a compact tombstone that holds no private content. | `test_verified_intent_cannot_be_replayed_from_older_client_state`, `test_verified_intent_lineage_survives_ledger_pruning`, live step 22 |
| R8 | C5 ARN | **Graph widening never worked against the real store.** `_graph_candidates` read `node_id`/`name`, but `GraphStore.list_nodes` returns `entity_id`/`canonical_name`. The unit fixture used the invented shape, so the "widened to graph" evidence was vacuous: widening always found nothing. | Read the real projection shape. The fixture now uses that shape too. | `test_graph_widening_with_several_plausible_candidates_asks_and_binds_the_choice`, live step 23 |
| R9 | C5 stale referent | Confirming after the bound session file had been deleted still executed the old binding. | At confirmation, every bound session-file referent must still exist with the same title. Otherwise the confirmation is stale and the reference is resolved again. | `test_confirming_after_the_bound_file_was_removed_is_stale_and_reasked`, live step 24 |
| R10 | C5 graph confirmation | A referent found only by ARN graph widening could auto-confirm under the "complete explicit request" path. | Graph-derived bindings always require explicit confirmation. | `test_graph_widening_with_one_candidate_still_requires_confirmation` |
| R11 | C5 composition (found by wiring the Brain) | **Unconfirmed actions reached approval.** A proposer `multi_action` for `remember_fact` bypassed intent discovery entirely. For the user text "hello there", it put the proposer-invented "remember that the budget is cancelled" in front of the user for approval. | Executable arguments come only from a Confirmed Intent Contract (`REFUSED_UNCONFIRMED_ACTION`). Permission refusals keep their own codes. | `test_brain_cannot_reach_approval_without_a_confirmed_intent` |
| R12 | C5 composition | A proposer that labelled an answer ("the Q4 one") as a new request discarded the pending clarification. | Superseding an open intent requires that the user's own words form a new request (the schema's extraction), not only the proposer's label. | `test_brain_labelling_an_answer_as_a_new_request_does_not_discard_the_open_intent` |
| R13 | C5 honesty | A bare contradiction while a confirmation was pending ("it is not due on Friday") re-presented the unchanged confirmation with no notice. | The reply now says "I did not change anything…". Heuristics were not widened. | `test_bare_negation_while_confirming_asks_instead_of_guessing` |
| R14 | C7 rollback | Windows name aliasing was accepted: case-only duplicates, trailing dots or spaces, `~` short names and device names. Two archive names could then land on one file, and the evidence would describe bytes that were not on disk. | Every aliasing form is refused before writing. The finished tree is re-read, and it must contain exactly the recorded files with exactly the recorded bytes. | `test_c7_rollback_boundary.py` |
| R15 | C7 rollback | **Catalogue substitution.** An overlay catalogue could widen authority, for example by approval `none` or `available`. | A restored catalogue may drop entries. Baseline entries must be unchanged. A new entry must be `unavailable_on_runtime`, `user_approval_required` and `paired_client`. | `test_substituted_catalogue_that_widens_authority_is_refused` |
| R16 | Server boundary | Server refusal of `external_harness_task` depended on an accident: `ToolDispatcher` never checks availability, and the refusal came only from `TurnRunner.__init__` failing to construct. | `ToolDispatcher.execute_tool` refuses `execution_surface: paired_client` before any import. **This is a shared legacy file and needs your sign-off.** | `test_server_dispatcher_refuses_paired_client_capability_before_loading_any_client_code` |

## Reviewed and found sound (no change)

- **Turn State repair.** The pristine `e8e3b65` crashed: `Object of type Fact is not JSON serializable` whenever a paused workflow held a fact. The repair projects current fact values only, so superseded values never become inputs. The intent-record branch projects only its own slots. Projection is identical after a persistence round trip, and Turn State is never persisted or digested. I also tried to reach a continuation bypass with tentative slot values: intent discovery never passes a turn through while a record exists. Tests are in `test_turn_state_projection_review.py`.
- **Reference-binding port.** I re-derived all 12 runtime files independently from both donor commits. The donors are byte-identical. The port equals the donor plus the `uri_v1.(turn|reference_clarification).` → `uri_core.reference_binding.` rewrite, with no other change. The test ports differ only in fixture import paths and the declared renderer-test removals.
- **Rollback escape.** Writes go only to a fresh `work/c1/rollback_*` directory under ACL, with no symlinks, junctions, `..`, absolute paths or streams. Private state (`work/`, `uri_workspace/*` except the catalogue, `*.dpapi`, `.env`, `credentials.json`, UI) is refused.
- **Boundaries.** In fresh interpreters, neither the legacy server nor the paired composition loads `uri_harness_adapters`. The default policy refuses every harness selection. The worker registry has nothing usable, and Antigravity is `REFUSED`. Harness capability is supplied explicitly by test compositions (`harness_stack`) and never by default.

## Brain transport (new, PARTIAL)

`uri_core/core/paired_brain.py` adds `BrainProposer` and `brain_composition`. The composition maps exact `("server_local_model", provider, model)` rows to any `ModelProvider`. No model is built in, and the user selects a row explicitly. The Brain proposes using the existing decision contract and validator. A failure is reported as `SELECTED_MODEL_UNAVAILABLE` or `BRAIN_OUTPUT_INVALID`, and there is never a fallback. Harness rows cannot become Brains.

This is proven offline: through the real composition, and with the real `OpenAICompatibleProvider` against a local stub HTTP endpoint.

**Not done:**

- the interpreter and planner Brain seams;
- client cloud models;
- wiring a Brain into the launched isolated server. The C1 manifest requires `model_policy: lazy-not-selected`, and changing that is your decision;
- any live model run, because no local model server was running.

## Superseded material

- **Experimental intent controller** (Codex worktree). Its behaviour had already been salvaged. One regression was added from it, a new request gets its own question allowance. It is marked by `experimental/intent_workflow/SUPERSEDED_BY_PHASE1_C5.md` and was not deleted.
- **INT-ARN-1 desktop seam.** Every lesson from it is covered by the Phase 1 guards and tests. It is marked superseded for Phase 1 only by `uri_desktop_seams/reference_clarification/SUPERSEDED_FOR_PHASE1.md`, and kept, because the legacy `/ask` still uses it.

## Known limitations (not repaired)

- The `.json`/`.yaml` data files read at runtime under `uri_core`, and third-party package contents, are not bound by the import pin. The dependency digest covers only METADATA and RECORD.
- An attacker running as the same Windows user is outside the threat model: DPAPI gives same-user scope only, and server ledgers can be rolled back.
- `FIXTURE_ONLY` qualification makes any executable usable. Nothing outside the tests calls `qualify`.
- A `failed` receipt after dispatch is trusted. An explicit retry is allowed by design.
- The reference-noun list is heuristic. For example, "policy" is not a reference noun, so the statement is stored verbatim.
- `graphify update .` was not run, to keep `graphify-out/` out of the diff.

## Final validation (after all repairs; run in this session)

| Run | Result |
|---|---|
| Focused Phase 1 regression (C1–C7, intent, Brain, boundary, fail-closed, M31 ×2, RAR/S1, catalogue/effects/modes, route authorization, workflow continuation) | **408 passed**, 61 subtests |
| `validate_c1_regression.py` | 303 passed, 29 subtests |
| `validate_c3_live.py` | passed |
| `validate_c5_live.py` (real server process, 2 real restarts) | **30/30 `ALL_STEPS_PASSED`**, including second-review steps 22–24 |
| `validate_c6_bridge.py` | passed |
| Flutter `flutter test` / `flutter analyze` | 175 passed, 1 skipped / 1 pre-existing deprecation info |
| Full Python suite | **2621 passed, 7 skipped, 11 failed** |
| The same 11 test IDs on my own fresh `git archive e8e3b65` export (`work/c1/review2_pristine_e8e3b65`) | **11 failed**: pre-existing, not caused by Phase 1 |

## Final checkpoint

`work/c1/checkpoints/review2-final-20261005-151058.zip`, sha256 `8a43dba45fa12b47388ebc0cb5b7d1df44a65305be4db2671458e94c4aef4ba4`, 111 files plus `GIT_HEAD` and `GIT_DIFF`. `testzip` is clean and the inventory was re-hashed 111/111. The report was written after the checkpoint, so its own sha differs from the archived copy only by this section.
