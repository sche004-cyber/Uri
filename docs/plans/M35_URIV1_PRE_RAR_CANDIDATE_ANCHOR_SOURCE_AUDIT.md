# M35 URIv1 — Pre-RAR Existing Candidate/Anchor Source Audit

**Type:** Evidence pass only. No implementation, no `ActiveContext` builder, no RAR wiring, no RAR modification, no Step-1 change, no Needle/Qwen qualification, no benchmark execution, no new architecture design.
**Continues from:** `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_DISCOVERY_PLAN.md` (`VERIFICATION_READY`, not yet approved for implementation).
**Workspace:** `C:\Users\cheta\Development\Uri\_V1`, branch `m35-uri-v1-parallel-architecture`, HEAD unchanged (`e8e3b65259c45fc823addc3ef8969425a265bd1b`). `uri_v1/` confirmed git-untracked (new, uncommitted work); `uri_core/` confirmed git-tracked (the pre-existing, live production runtime this new package is built alongside, per `uri_v1/__init__.py`'s own stated intent: "parallel architecture, built alongside uri_core, not a rewrite of it").
**Status:** `VERIFICATION_READY`

---

## Headline finding

**What URI already knows vs. what Step 2 currently receives are two very different things, and the gap between them is architectural disconnection, not absence of information.**

`uri_core/` is the real, live, production-traffic-serving backend in this repository — not a dormant inheritance and not the separate protected legacy prototype at `C:\Users\cheta\Development\uri-agent`. It has a durable `SessionState`, a live `TurnState.assemble_turn_state()` reached by default from every real `/ask` request, a wired `CapabilityContextResolver` populated by real action results, a durable `FileStore` tracking real uploaded-file IDs, a live `WorkflowExecutor` with durable pause state, a durable `ConversationHistoryStore`, and its own live `ARNEngine`. **Repository-wide grep confirms zero import statements in either direction between `uri_core/` and `uri_v1/turn/`.** Every candidate/anchor source `uri_v1/turn/rar_contracts.py` defines (`ActiveContext`, `RARDeterministicAnchor`) is, today, populated exclusively by fixture/benchmark files — never by any live code path, despite real equivalents or partial equivalents existing one package over.

---

## 1. Repository / Evidence Inspected

- Durable prior evidence recovered first, per the task's instruction not to repeat archaeology: `docs/plans/ARN_1_COMPLETION_REPORT.md` (confirms `uri_core/core/turn_state.py`, `decision_engine.py`, `canonical_execution.py`, `dispatcher.py` are live, tested — 130 passing tests including `test_turn_state.py`, `test_orchestrator_workflow_recovery.py` — and `VERIFIED` in this exact repository as of the current HEAD), `PROJECT_MEMORY.md`'s M33.2/ARN.1 resume-point entries (independently confirms `uri_core/core/edge_lifecycle/`, `uri_core.core.arn` are real and tested), and the prior session's `M35_URIV1_RAR_NATURAL_BOUNDARY_DISCOVERY_PLAN.md` and its underlying legacy-repo audit.
- New source inspection this session (via one dedicated read-only agent): `uri_core/core/state.py`, `uri_core/core/turn_state.py`, `uri_core/capabilities/context_resolver.py`, `uri_core/capabilities/executor.py`, `uri_core/core/file_store.py`, `uri_core/core/decision_engine.py`, `uri_core/core/canonical_execution.py`, `uri_core/app/server.py`, `scripts/run_uri_server.py`, `uri_core/core/arn/__init__.py`/`engine.py`, `uri_core/core/multi_action_dispatch.py`, `uri_core/core/workflow_executor.py`, `uri_core/core/conversation_history.py`, `uri_core/core/drafting_memory.py`, `uri_core/core/capability_registry.py`, `uri_core/core/evidence_context.py`, plus `uri_v1/turn/active_context.py` and `uri_v1/turn/rar_contracts.py` (re-checked for cross-reference, not re-audited internally — already covered in the prior session).
- Repository-wide greps: `RARDeterministicAnchor(`/`ActiveContext(` construction sites; `import.*uri_core` inside `uri_v1/`; `import.*uri_v1` inside `uri_core/`; `selected_ui|active_document|foreground|currently_viewing|selected_item`.
- Confirmed via `git status --porcelain`: `uri_v1/` is wholly untracked; `uri_core/` is fully tracked (pre-existing).
- Not re-executed: no tests run, no server started, no benchmark run. All findings are static code inspection (`TEST_STRUCTURE_INSPECTED`/`OBSERVED_BEHAVIOUR`), except where a specific test count is cited directly from `ARN_1_COMPLETION_REPORT.md`'s own recorded `CURRENT_TEST_RUN_VERIFIED` evidence from that milestone's closure.

---

## 2. Existing Runtime State Sources

| Source | File:line | Live entrypoint reaching it |
|---|---|---|
| `SessionState` / `SessionManager` | `uri_core/core/state.py:10,100` | `server.py`'s `/ask` handler via `context.orchestrator.session_manager.get_session(...)` (e.g. `server.py:1723`) |
| `TurnState.assemble_turn_state()` | `uri_core/core/turn_state.py:349` | `decision_engine.build_turn_state_and_directory()` (`decision_engine.py:1029`), called from 3 real `server.py` sites (895, 1734/1808, 1861); live by default (`canonical_execution.decision_engine_live_enabled()` defaults `True` since M32 B1.1, despite the module's own now-stale top docstring still saying "Default OFF") |
| `_project_active_pointer` | `turn_state.py:175` | Called directly by `orchestrator.py:514` |
| `CapabilityContextResolver` | `uri_core/capabilities/context_resolver.py:25` | `MultiActionExecutor.__init__` default (`executor.py:9,20,25`), populated post-action at `executor.py:76-77`; instantiated by `multi_action_dispatch.py:330`, itself an `orchestrator.py:271-274` attribute dispatched at `orchestrator.py:4936` |
| `FileStore` / `StoredFile` | `uri_core/core/file_store.py:94,151` | `orchestrator.py:331-332` (`self.file_store`), read at `orchestrator.py:3487-3491`/`4626-4629`; validated per-request at `server.py:1556-1572` into `current_turn_attachments` |
| `WorkflowExecutor` + `active_workflow*` `SessionState` fields | `workflow_executor.py:5`; fields `state.py:54-67` | `orchestrator.py:2194,3934-3936`; gated live at `server.py:1723-1727` |
| `ConversationHistoryStore` | `uri_core/core/conversation_history.py:73` | Appended every real turn (`orchestrator.py:4626+`), read by `turn_state.py`'s recent-conversation projection |
| `uri_core.core.arn.ARNEngine` / `attach_not_found_recovery` | `uri_core/core/arn/engine.py:42` | `canonical_execution.py:722-730`, inside the same live `run_canonical_for_ask` path as `TurnState` |
| `DraftingMemory` | `drafting_memory.py:6` | Not confirmed live-wired this pass — a preference store, not a candidate/document-handle mechanism regardless |
| `CapabilityRegistry` | `capability_registry.py:199` | Read-only descriptor catalogue by its own docstring ("never writes"); a metadata source, not results/state |

`scripts/run_uri_server.py` is the confirmed real entrypoint (its own docstring: "Starts the real URI backend (`uri_core.app.server:app`) via uvicorn... every request it receives is still handled exactly as `UriOrchestrator.process_user_input()`..."). This is not a disconnected package in this branch — it is the live production backend.

**Classification: `PROVEN`** (direct code + a prior independently-verified milestone's 130-test regression) that `uri_core/` is live and populated by real request traffic, not merely present-but-dormant.

---

## 3. Candidate-Source Provenance Table

| Candidate source | What information | When produced | Persistence | Authority | Current consumer | Step-2 accessibility | Potential RAR relevance |
|---|---|---|---|---|---|---|---|
| `FileStore.to_reference()` (per-file dicts: `file_id`, `filename`, `media_type`, `size_bytes`) | Real uploaded/attached file identity | On upload, read per-request | Durable (disk + JSON index), session-scoped | Actual runtime state / user-supplied | `orchestrator.py` context assembly, `server.py` validation | **NO** (zero import into `uri_v1/turn/`) | `POTENTIAL_MATCH` — the closest real thing to an `RARCandidate` pool item (has `id`/`title`-equivalent fields already) |
| `current_turn_attachments` (validated list, this turn only) | Which of the user's file IDs are attached *this turn* | Per real `/ask` request | Turn-local | Actual runtime state | `assemble_turn_state`, `TurnStateResult.data` | **NO** | `POTENTIAL_MATCH` for `current_attachment_id`, but plural — no existing code collapses this to a single "the current attachment" |
| `CapabilityContextResolver`'s per-capability last result | The most recent real tool-call result for a given capability (Gmail: message/thread/attachment IDs; other capabilities: full last raw result) | After each successful action execution | In-memory, turn/session-local (not JSON-persisted per what was read) | Actual runtime state | `MultiActionExecutor.resolve()` for follow-up argument grounding | **NO** | `POTENTIAL_MATCH` — a real bounded "last known object" set, though keyed by capability+action shape, not a generic candidate list |
| `ConversationHistoryStore` | Recent turn text/summaries | Every real turn | Durable, session-local | Actual runtime state | `turn_state.py`'s recent-conversation projection | **NO** | `NO_MATCH` for RAR's candidate-pool shape directly (it's text history, not typed candidate objects), though conceivably a future source for deriving one |
| `SessionState.active_workflow*` fields | Whether a workflow is paused, on what question/field | Set by orchestrator workflow logic | Durable, session-local | Actual runtime state | `_project_active_pointer`, `server.py`'s M30.7 gate | **NO** | `POTENTIAL_MATCH` for `recency`/continuation-style evidence (conceptually adjacent to RAR's `recency_hint="same"`), not a candidate pool itself |
| `uri_core.core.arn.ARNEngine`'s live candidate/elimination state | A different, already-in-progress narrowing process's candidates | During a real `NOT_FOUND` recovery | Turn-local (`ARNState` passed through the execution envelope) | Actual runtime state | `canonical_execution.py`'s recovery seam | **NO** | `NO_MATCH` — solves a different problem (recovery from empty search result, task-scoped), confirmed already in the prior legacy audit; this is the same conclusion, now also true of the live `uri_core` copy, not just the external legacy repo |

---

## 4. Deterministic-Anchor Provenance Table

`RARDeterministicAnchor` (`uri_v1/turn/rar_contracts.py:103-123`): `exact_id`, `unique_title_match`, `deterministic_recency`, `current_attachment_id`, `selected_ui_id`.

| Anchor field | Does URI already possess the underlying information (anywhere)? | Where | Does any code construct `RARDeterministicAnchor` from it? | Classification |
|---|---|---|---|---|
| `current_attachment_id` | **YES, partially** — real, durable, live `FileStore`/`current_turn_attachments` | `file_store.py:94,151`; `server.py:1556-1572` | NO — zero live constructor found; only fixture files build this dataclass | Situation **B**: exists, but inaccessible to Step 2, and even if accessible, needs a new singular-selection rule (URI tracks a *list* of this-turn attachments, never a single "current" one) |
| `selected_ui_id` | **NO** — confirmed zero equivalent anywhere in `uri_core/` (grep for `selected_ui|active_document|foreground|currently_viewing|selected_item` returned no matches) | N/A | NO | Situation **A**: genuinely does not exist. This is not an access gap; URI's backend has no concept of a UI-selected/foreground object today, live or dormant. |
| `exact_id` | **Partial** — an explicit ID the user names is only real today as `payload.attached_file_ids` (validated at `server.py:1556-1572`); no generalized "any explicit ID reference in the turn" concept beyond attachments | `server.py:1556-1572` | NO | Situation **B** for the attachment-ID case only; situation **A** for a general explicit-identifier concept beyond attachments |
| `unique_title_match` | **NO** — nothing in `uri_core` indexes candidate objects by title for verbatim/unique matching; `capability_relevance.py` (which RAR's own Level 6 "adapted from," per `rar_deterministic.py:113`'s comment) scores *capabilities*, not titled artifacts/candidates | N/A | NO | Situation **A**: genuinely does not exist for artifacts/candidates (a related but distinct mechanism exists for a different object type — capabilities, not documents/artifacts) |
| `deterministic_recency` (dataclass field, related to `recency_hint`) | **Weak partial** — `SessionState.active_workflow*` gives a binary "is something paused/active" signal, not a ranked recency ordering across multiple candidates | `state.py:54-67` | NO | Situation **A** for genuine ranked recency; situation **B** at best for the coarser "is there an active thing right now" signal |

**Central distinction preserved as instructed:** "No `RARDeterministicAnchor.current_attachment_id` is constructed" (true — `PROVEN`, zero live constructor) is a **different, narrower** statement than "URI possesses no current attachment ID" (**false** — `FileStore`/`current_turn_attachments` is real, live, durable information). The correct statement is: URI possesses real attachment-ID information, in plural per-turn form, with no code anywhere (fixture or production) that collapses it to RAR's expected singular field, and zero code path carrying it from `uri_core` into `uri_v1/turn/` regardless.

---

## 5. What Exists but Is Inaccessible to Step 2 (Situation B)

- `FileStore`/`current_turn_attachments` real file IDs — exists, durable, live; zero import path into `uri_v1/turn/`.
- `CapabilityContextResolver`'s per-capability last-result state — exists, live, in-memory; zero import path into `uri_v1/turn/`.
- `SessionState.active_workflow*` continuation/pause signal — exists, durable, live; zero import path into `uri_v1/turn/`; conceptually the closest real analog to RAR's `recency_hint="same"` ad-hoc literal check (§ prior plan's §4 finding), but genuinely disconnected.
- `ConversationHistoryStore`'s recent-turn text — exists, durable, live; zero import path into `uri_v1/turn/`.
- `TurnState.assemble_turn_state()`'s full assembled projection (which already *combines* several of the above into one object) — exists, live, reached by default from every real request; zero import path into `uri_v1/turn/`. This is the single most consequential Situation-B item: a real, already-assembled, already-honest (`unavailable_fields`-tracked) turn-context object exists one package over from where RAR's `ActiveContext`/`RARDeterministicAnchor` inputs are needed, and nothing connects them.

**Every candidate-pool and deterministic-anchor gap identified in the prior Natural-Boundary plan (§4 of that document) is, per this audit, an access/integration gap (Situation B), not an absence-of-information gap (Situation A), with the single confirmed exception of `selected_ui_id` and general title-indexed candidate matching (`unique_title_match`), both of which are genuinely Situation A.**

---

## 6. What Step 2 Genuinely Receives Today (Situation C)

**Nothing from `uri_core`.** Confirmed by repository-wide grep: zero `import` statements connect `uri_v1/` to `uri_core/` in either direction (the only references are three code comments acknowledging `uri_core` mechanisms as design precedent — `rar_contracts.py:10`, `rar_deterministic.py:113`, `needle_bridge_runtime.py:17` — and `uri_v1/__init__.py`'s own module docstring stating the "built alongside, not a rewrite of" relationship). Step 2's only genuine, real, non-fixture input today is whatever raw text and attachment references are passed directly into `build_turn_frame()`'s own parameters by whatever future caller eventually wires it up — and per the prior plan's §4, even that wiring exists in only one real call path (`lfm_semantic_decoder.py`) for the `reference_expression` derived from `TurnFrame.candidate_references`, with `attachments` itself still an externally-supplied parameter, not derived from `uri_core.FileStore` today.

---

## 7. What Genuinely Does Not Exist (Situation A)

- A UI-selected/foreground object concept (`selected_ui_id`) — zero equivalent anywhere in `uri_core` or `uri_v1`.
- A title-indexed candidate/artifact matching mechanism for `unique_title_match` — `capability_relevance.py` is the nearest relative and scores capabilities, not artifacts/documents.
- A ranked, multi-candidate recency ordering (`deterministic_recency`) — only a binary active/paused workflow signal exists.
- A singular "the current attachment" collapse from the real plural `current_turn_attachments` list.
- A general "any explicit ID the user named in this turn" concept beyond the specific attached-file-ID validation path.

---

## 8. Candidate-Pool Findings

Bounded candidate sets that already exist, with real provenance:
1. **This-turn attachments** (`FileStore`/`current_turn_attachments`) — real, bounded, live, typed (`file_id`, `filename`, `media_type`, `size_bytes`).
2. **Per-capability last result** (`CapabilityContextResolver`) — real, bounded (one entry per capability namespace), live, but keyed to the specific capability's result shape rather than a generic artifact/entity type.

Bounded candidate sets that do **not** exist anywhere in `uri_core` or `uri_v1` today: a general "active artifacts" list, a general "active entities" list, a "recent documents" registry beyond file attachments, a "currently retrieved records" mechanism, or any UI-object registry. `ActiveContext`'s `ArtifactDescriptor`/`EntityDescriptor` shape (`active_context.py:14-32`) has **no real backing data source of either kind** — not even a Situation-B one; this specific gap is genuinely Situation A for anything beyond file attachments.

No aggregation logic is proposed here, per the task's explicit restraint — this section only records what bounded sets already exist and their provenance.

---

## 9. Impact on C1/C2/C3

- **C1/C2 do not necessarily require wholly synthetic/abstract candidate pools for the attachment-reference sub-case.** Evidence supports constructing C1/C2 fixture candidate pools *shaped like* real `FileStore.to_reference()` output (`file_id`, `filename`, `media_type`, `size_bytes`) rather than inventing an arbitrary schema, for any fixture whose true reference is attachment-flavored ("the attached PDF," "this spreadsheet"). This is a **fixture-realism refinement within the existing C1/C2 conditions**, not a new axis and not a wiring proposal — the candidate objects are still hand-authored by the independent fixture author, just modeled on a real, verified data shape instead of an invented one.
- For any fixture whose true reference is a general artifact/entity beyond file attachments (e.g., "that customer record," "the earlier request"), no equivalent real data shape exists anywhere in the repository (§7/§8) — C1/C2 candidate pools for those cases remain **necessarily synthetic**, exactly as the prior plan already assumed. This is not amended.
- **C3 ("no candidate pool supplied") is confirmed to represent URI's actual, real, current end-to-end condition — not merely the absence of a Step-2 integration mechanism that could trivially be added.** The zero-import finding (§6) makes this precise: today, running any real user turn through the actual live system would produce exactly the C3 condition for `uri_v1/turn/`'s RAR calls, because no code path carries any `uri_core` candidate information there at all. C3 should be read in the results report as "what actually happens today," not as a synthetic worst-case control.

---

## 10. Impact on RAR Level 0/1 Qualification

**No natural-runtime condition can legitimately exercise RAR Level 0/1 today**, because `RARDeterministicAnchor` is never constructed by any live code path (§4) and no import connects `uri_core`'s real `FileStore`/`current_turn_attachments` data to `uri_v1/turn/` (§6). This is unchanged from the prior plan's conclusion — this audit adds the specific reason why: it is not that the underlying information is absent (`current_attachment_id` has a real, live source), it is that **the information exists and the wiring does not**, which is a categorically different (and more encouraging, for a possible future decision — not made here) situation than "the information doesn't exist anywhere in URI." Whether wiring it would meaningfully raise Level 0/1's real-world hit rate remains `UNMEASURED` and is not something this audit or the Natural-Boundary experiment as designed can answer without a future, separate wiring decision — explicitly out of scope for both documents.

---

## 11. Whether the Natural-Boundary Benchmark Requires Amendment

**Yes — a narrow, evidence-justified amendment**, not a redesign. Change record below. The two-axis grid (Step-1 input realism × candidate-pool realism), the five-cell condition set (S1×C1, S1×C2, S1×C3, S2×C1, S2×C2), and the failure taxonomy are all **unchanged** — none of this audit's findings contradicts them. What changes is fixture-construction guidance and the interpretive framing of C3.

### Change record (applied to `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_DISCOVERY_PLAN.md`)

1. **§8 (Proposed Benchmark Construction), addition to point 2:** candidate-pool fixtures for attachment-flavored references in C1/C2 should be shaped after the real `FileStore.to_reference()` schema (`file_id`, `filename`, `media_type`, `size_bytes`) rather than an arbitrary invented schema, per this audit's §3/§9. Non-attachment candidate pools remain necessarily synthetic (§7/§8 of this audit — no real data shape exists for them anywhere in the repository).
2. **§9 (Proposed Experimental Conditions), reframing of C3:** C3 is not merely a control condition testing an artificial absence — this audit confirms (§6/§9) it is the literal, verified, current end-to-end state of the real system for any RAR call reachable through `uri_v1/turn/` today. The results report should present C3 as "what actually happens in the live system today," distinct from C1/C2's hypothetical-future-integration framing.
3. **§13 (What This Experiment Explicitly Cannot Conclude), addition:** this experiment still cannot conclude that `uri_core`'s real candidate/anchor sources *should* be wired to `uri_v1/turn/` — only that they exist and currently are not. That decision, and any wiring design, remains explicitly out of scope, per both this audit's and the Natural-Boundary plan's restraint sections.

No other section of the Natural-Boundary plan requires change. §10 (Failure Taxonomy), §11 (Measurements), §12 (Anti-Contamination), §14 (Evidence Gaps), and §15 (Frozen Blueprint) all remain valid as written.

---

## 12. Remaining UNKNOWN / UNMEASURED Items

| Item | Status |
|---|---|
| Whether wiring `uri_core`'s real `FileStore`/`current_turn_attachments`/`CapabilityContextResolver` data into `uri_v1/turn/` would measurably improve RAR's real-world Level 0/1 hit rate | `UNMEASURED` — no experiment (this one or the frozen Natural-Boundary design) tests this; would require an actual wiring decision, explicitly out of scope for both documents |
| Whether `DraftingMemory` is live-wired in any real request path | `UNKNOWN` — not confirmed either way this pass; flagged as an open item rather than guessed at |
| Whether any UI layer (outside `uri_core`/`uri_v1`, e.g. a frontend not inspected this pass) tracks a "selected UI object" concept that simply never reaches the backend | `UNKNOWN` — this audit's scope was the Python backend repository; a frontend-side selection concept, if any, was not searched |
| Real-world frequency with which a true reference expression would resolve via the attachment-shaped candidate pool (§9's C1/C2 refinement) vs. a genuinely-synthetic-only candidate type | `UNMEASURED` — depends on the eventual fixture set's composition, not determinable from static code inspection |
| Whether `uri_core.core.arn.ARNEngine`'s live candidate/elimination machinery, despite solving a different problem than RAR (§3), could ever supply *seed* candidates for a RAR-relevant pool in some future integration | `UNKNOWN`/out of scope — noted only as a possible future research question, not evaluated here |

---

## Summary for User Review

**What URI already knows vs. what Step 2 currently receives — the central distinction:** `uri_core/` is a real, live, tested production backend with durable session state, a live turn-context assembler reached by every real request by default, a wired post-action context resolver, a durable file/attachment store, live workflow-pause tracking, durable conversation history, and its own live ARN recovery engine. `uri_v1/turn/`'s RAR-adjacent inputs (`ActiveContext`, `RARDeterministicAnchor`) are, today, populated by **zero** of this — confirmed by a repository-wide zero-import finding, not inferred from absence of evidence. Most of the previously-reported "gaps" are **access gaps (Situation B)**, not information gaps (Situation A): the one clear, confirmed exception is `selected_ui_id` and general title-indexed artifact matching, which genuinely do not exist anywhere in the codebase.

**Natural-Boundary plan amended:** narrowly, per §11's change record — attachment-flavored C1/C2 fixtures should use the real `FileStore` shape, and C3 is now explicitly framed as today's actual live condition, not a hypothetical worst case. The condition grid, failure taxonomy, and all other sections of that plan are unchanged.

**No architecture was designed, no builder was built, nothing was wired.**

**File created:** [docs/plans/M35_URIV1_PRE_RAR_CANDIDATE_ANCHOR_SOURCE_AUDIT.md](docs/plans/M35_URIV1_PRE_RAR_CANDIDATE_ANCHOR_SOURCE_AUDIT.md)
**File amended:** [docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_DISCOVERY_PLAN.md](docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_DISCOVERY_PLAN.md) (§8, §9, §13 — see change record in §11 above)

Stopped at `VERIFICATION_READY`. Not implemented, not committed, not pushed. Waiting for user review.
