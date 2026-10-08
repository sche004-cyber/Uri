# URI Development Evidence Registry — Independent Evidence & Lineage Audit

**Audited artifact:** `docs/governance/URI_DEVELOPMENT_EVIDENCE_REGISTRY.md` (v1.0.0, authored by Gemini, untracked)
**Auditor:** Claude (Opus 5.5), 2026-09-24
**Mode:** Audit + bounded repair only. No architecture, no implementation, no production code, no RAR/ARN/Step-1/Step-2 changes, no legacy-repository changes, no JSON index, no governance adoption, no commit, no push.
**Status:** `VERIFICATION_READY`

**Verdict:** `READY_WITH_LIMITATIONS` (see §17)

---

## 1. Repository State Verified

| Item | Observed |
|---|---|
| Working directory | `C:\Users\cheta\Development\Uri\_V1` |
| Branch | `m35-uri-v1-parallel-architecture` |
| HEAD | `e8e3b65259c45fc823addc3ef8969425a265bd1b` |
| Registry status | Untracked (`?? docs/governance/URI_DEVELOPMENT_EVIDENCE_REGISTRY.md`), 909 lines at audit start, md5 `0c424312…`, mtime 2026-09-24 01:05 |
| `uri_v1/` | **Untracked** — no `git ls-files uri_v1` output |
| `uri_core/` in `_V1` | Tracked, clean (no working-tree changes) |
| **Worktree relationship** | `git worktree list`: `C:/Users/cheta/Development/uri-agent` = `e8e3b65 [master]`; `C:/Users/cheta/Development/Uri/_V1` = `e8e3b65 [m35-uri-v1-parallel-architecture]`. **Same repository, same commit.** |
| `uri-agent` working tree | Uncommitted edits in 9 `uri_core` files (`server.py`, `route_classification.py`, `edge_lifecycle/detection.py`, `edge_lifecycle/models.py`, `model_providers/*`, `provider_registry.py`, `services/pdf_layout_converter.py`, `tools/convert_document.py`). None of the audited mechanisms (`context_resolver.py`, `turn_state.py`, `file_store.py`, `arn/`, `fact_manager.py`, `facts.py`, `capability_relevance.py`, `decision_engine.py`) differ. Not modified by this audit. |
| Governing skill | `.claude/skills/uri-development/SKILL.md` and `.agents/skills/uri-development/SKILL.md` **do not exist**. The `uri-development` skill is the repository-root `SKILL.md` (locally modified, uncommitted: +387/−116 lines vs HEAD). The working-tree version was used. |
| Other governance read | `ORCHESTRATION.md`, `CLAUDE.md`, `AGENTS.md`, `PROJECT_MEMORY.md` (earlier this session) |

**Most consequential repository fact.** The task framed `uri-agent` and `_V1\uri_core` as two repositories/historical contexts. They are two worktrees of one repository at one commit. Every registry "legacy mechanism" in `uri_core/` is the **same committed code** as the live V1 backend. The genuine historical/structural boundary is `uri_core/` (tracked, live) versus `uri_v1/` (untracked, zero imports to or from `uri_core`).

---

## 2. Audit Scope and Coverage

Method: registry used as an index; each material claim traced to its cited primary evidence, then to later correction evidence; wording, scope, status and numbers compared.

| Registry area | Coverage |
|---|---|
| §1 taxonomy, §2 inventory | Fully reviewed |
| §3 legacy mechanisms (8 rows, 4 anti-patterns, principle quote) | **Fully verified** against source code and `M35_URIV1_A2_5_LEGACY_DETERMINISTIC_REFERENCE_AUDIT.md` |
| Cluster 1 (FIND-SEM-001…005) | SEM-002…005 verified; SEM-001 headline figures accepted from prior-session evidence, secondary percentages (11.1%, 61.1%) **not re-verified** |
| Cluster 2 (FIND-RAR-001…003) | **Fully verified** against Stage 2/3/4/4B-B/4B-C, A2.8B |
| Cluster 3 (FIND-ARN-001…003) | ARN-001/002 verified; ARN-003 figures verified, "solved in Mode D" **not verified** |
| Cluster 4 (FIND-QUAL-001…005) | **Fully verified** against B.4, A2–A2.4R, A2.5 Stage 3/4, A2.6, A2.7, A2.8B/C, Gemma report |
| Clusters 5–8 (GATE, DEC, LAT, MEM) | **Sampled only**: GATE-002 lineage, LAT-002, MEM-002 verified. GATE-001, GATE-003, DEC-001/002/003, LAT-001, MEM-001 **not verified** — flagged in registry |
| §5 lineage table | M35 rows verified; M6–M33 rows **not verified** |
| §6 mechanism table (13 rows) | 10 rows verified; Foundational Force-Inclusion, Three-Way Intent Shift, First-Miss Seam descriptions accepted without re-verification |
| §7.1 rejections (7 rows), §7.2 dead ends (8 rows) | 7.1 fully verified; 7.2 rows 1, 5, 6, 8 verified; rows 2, 3, 4, 7 cross-checked against their cluster entries only |
| §8 pending queue | PEND-EV-007 verified; others **not verified** |
| §9 schema | Fully audited (§14) |

Primary sources opened or grepped this audit: `rar_deterministic.py`, `rar_contracts.py`, `turn_frame.py`, `turn_frame_builder.py`, `active_context.py`, `context_resolver.py`, `turn_state.py`, `orchestrator.py` (read-once sections), `decision_engine.py:340–372`, `capability_planner.py`, `services/fact_extraction.py`, `services/evidence_fact_extractor.py`, `model_reasoning_adapter.py`, `qwen_wire.py`, and the reports named in §4–§12. Earlier-session evidence (Step-2 reconstruction, Natural-Boundary plan, Pre-RAR audit, two read-only agent traces of `uri_core`) reused where unchanged.

---

## 3. Registry Claims Sampled / Verified

Approximately 95 discrete claims were checked: 8 legacy-table rows (×3–4 claims each), 4 anti-patterns, 16 FIND entries in Clusters 1–4 (classification, scope, key metrics, later-evidence, relevance/reuse lines), 3 Cluster 5–8 entries, 7 lineage-table rows, 13 mechanism-table rows, 15 rejection/dead-end rows, 1 pending item, and the JSON schema. Claims not listed as verified in §2 were not verified.

---

## 4. Confirmed-Correct Claims

- `CapabilityRelevance` → RAR Level 6 **`ADAPTED_FROM`** — supported by `rar_deterministic.py:113` ("Adapted from legacy uri_core/core/capability_relevance.py") and A2.5 audit Mechanism 7.
- Stage 4B-B headline figures: 122/136 (89.7%), 100/136 auto-resolved (73.5%), 94/100 precision (94.0%), 0 invented IDs, DET-ONLY 102/136 (75.0%) and 80/136 (58.8%), 21 dependent cases (15.4%).
- A2.1: Schema A collapse to `compare` on 13/14 calls (report states 92.8%; arithmetic 92.9% — source rounding, preserved).
- A2.3: 95.8% contradiction rate, 75% hallucinated IDs, 1,613.9 ms.
- A2.4R: Needle negation and active-context 0% in all four modes; Qwen3-14B Mode D 100% negation/reference, 87.5% (7/8) active-context resolution, latency 7.4–8.5 s.
- A2.6: goal 94.7%, requested ops 73.7%, negation 34.2%, Mode D 254.7 ms; verdict `QWEN3_5_2B_SUB_THRESHOLD_ESCALATE_TO_4B`.
- A2.7 38-case figures (97.4 / 94.7 / 100 / 100 ladder / 96.8% contrastive preservation).
- A2.8B: 2B 33.3 → 50.0 → 58.3; 9B 41.7 → 75.0; Mode C regression 50.0 → 41.7 (2B), 75.0 → 66.7 (9B).
- A2.5 Stage 4 LFM verdict `LFM_TOO_WEAK_EVEN_WITH_DECOMPOSITION`; B.4 verdicts `RESIDENT` (Needle reflex/extraction) and `BYPASS / REDUNDANT` (SmolLM2, Qwen2.5-0.5B).
- ARN.1: 10/10 focused tests, 2,259 passed / 16 classified failures (as `HISTORICAL_TEST_EVIDENCE`); `EvidencePromotionError` barrier (`PROVEN` retained — code invariant with test).
- `FileStore` bounded `to_reference()` handles and session scoping (M34).
- Every cited test file exists (`test_authoritative_facts_immutability.py`, `test_attachment_download.py`, `test_multi_action_capabilities.py`, `test_m35_uriv1_a2_needle_live.py`, `test_decision_gates.py`, `test_m34_attachment_turn_routing.py`, `test_arn_1_deterministic_narrowing.py`).
- Role-scoping of the Needle Step-1 decoder rejection and the Qwen3.5-2B primary-decoder rejection was already correct in v1.0.0.

---

## 5. Corrected Claims (summary; details in §8–§12)

31 registry locations were repaired (§16). By type: lineage 11, repository provenance 9, quantitative/benchmark scope 14, rejection scope 7, classification (`PROVEN` → `OBSERVED` etc.) 11, unsupported paths/citations 5, omitted correction evidence 6, omitted negative precedents 4. Categories overlap; one location often carried several defects.

---

## 6. Unsupported Claims

Claims for which no supporting evidence was located (repaired to `UNMEASURED` / `LINEAGE_UNVERIFIED` / removed):

1. `CapabilityContextResolver` "resolves 3-turn chains with 0% identifier hallucination."
2. TurnFrame "mean ~0.04 ms" and "100% extraction accuracy" (A2.3 says `<0.5 ms` and "100% determinism").
3. Grammar-constraint finding "validated across LFM2.5-350M and Qwen3.5-2B" (neither report tests unconstrained mode).
4. "Critical Anti-Contamination Rule" eliminating example echo in A2.4R/A2.8A (no document contains that rule).
5. Few-shot threshold "fails ≤1.9B, succeeds ≥9B."
6. Needle latency "58.6–211.4 ms (median 187.8 ms)" (B.4 reports p50 159.17 / p95 207.40 ms).
7. RAR "safe for production use"; Qwen3.5-9B "ready for production deployment" / "authoritative provider."
8. Gemma 4 evaluation "established Gemma as approved AO-4 implementation worker."
9. Fail-open catalog "flooded small models with 15+ tools … hallucinated tool calls" (no measurement located).
10. Prompt addenda "failed on smaller local models" (not tied to measured evidence for that file).
11. "Parallel Narrow Feeds" source `uri_v1/turn/qwen_feeds.py` (file does not exist) and think-suppression in `qwen_wire.py` (not present there).
12. Scaffolding lower bound "~1B parameters established" and "minimum parameter boundary for extraction established at ≥1.9B."

---

## 7. Overstated Claims

- **`PROVEN` misapplied** to single-run benchmarks: FIND-SEM-002, SEM-003, RAR-001, RAR-002, RAR-003, QUAL-001, QUAL-002, QUAL-004, LAT-002 (repaired), and DEC-001/002/003, LAT-001, MEM-001/002 (flagged, not re-evaluated). v1.0.0's own taxonomy defines `PROVEN` as passing "across independent audit sweeps."
- "Invariant permanently established" (SEM-002), "permanently designated" / "permanently bypassed" / "disqualified permanently" (QUAL-002, §7.1).
- "Fully satisfies all Step-1 … gates" / "passed 100% of all semantic gates" for Qwen3.5-9B — omits torture 10/12 and `TORT-10`/`TORT-11` (`REWRITE_REQUIRED` in the A2.8 manifest).
- "Proved amplification laws"; "Separating Requirement → Path → Capability eliminated premature execution" — one case (`PRECOND-01`) on one model; the same report found structured separation **reduced** 9B final-path success 81.2% → 75.0%.
- "Always resolve references deterministically before handing prompts to models"; "References must be bound deterministically in code via TurnFrame and RAR" — Qwen3-14B resolved references via prompt context at 100%/87.5%; RAR is unwired.
- `ACTIVE_BASELINE` for untracked, unwired `uri_v1` components (TurnFrame, RAR, Mode D).

---

## 8. Lineage Errors

| v1.0.0 claim | Evidence | Audited status |
|---|---|---|
| `CapabilityContextResolver` **ADAPTED** into RAR Level 1/3 | A2.5 audit Mechanism 1 planned ADAPT via extracting `RARCandidate`s into `ActiveContext`; no `ActiveContext` builder exists; zero imports | `PLANNED_ADAPTATION_NOT_IMPLEMENTED`; retention principle `SIMILAR_PRINCIPLE`; first-item selection = negative precedent |
| `$from` linking **REUSED** in Step 2 execution | `uri_v1/execution/` is an empty stub | Not reused; `LINEAGE_UNVERIFIED` |
| `FactManager` **REUSED** in RAR temporal logic (§3.2 and §6) | RAR Level 5 uses fixture `recency_rank`; no FactManager reference | `LINEAGE_UNVERIFIED`; discipline `SIMILAR_PRINCIPLE` |
| `ContextBuilder` **REUSED CONCEPT** for ARN clarification | ARN plan does not cite it | `LINEAGE_UNVERIFIED`; at most `FUNCTIONALLY_RELATED` |
| `FileStore` **REUSED** in RAR Level 1 (§3.2 and FIND-MEM-002) | No `RARDeterministicAnchor` constructor anywhere live; zero imports | **False as implementation claim**; `POTENTIAL_MATCH` only |
| `FileStore` "REUSED in M34" | `FileStore` handle work *is* M34 | Not a reuse |
| `TurnState` active pointer **ADAPTED** into RAR Level 3 via `ActiveContext.active_pointer` | `ActiveContext` has no such field; A2.5-recommended `immediately_preceding_target_id` never added | `PLANNED_ADAPTATION_NOT_IMPLEMENTED` |
| Example echo eliminated by "Critical Anti-Contamination Rule" | Rule not found anywhere | `LINEAGE_UNVERIFIED` |
| Gemma evaluation → AO-4 worker approval | Gemma report has no AO-4 reference; runtime-model and dev-worker roles conflated | `LINEAGE_UNVERIFIED` |
| RAR anti-invention ← `context_resolver.py` docstring principle | No citation | `SIMILAR_PRINCIPLE` (added) |
| §5 mermaid `ARN_1 --> M35` ordering implies causal hand-off | No document links ARN.1 outcomes to M35 A0 start | Not repaired (low impact); `LINEAGE_UNVERIFIED` — noted here only |

Confirmed lineage: `capability_relevance.py` → RAR Level 6 (`ADAPTED_FROM`). The Stage 2 stack's general "derived from legacy URI prototype" docstring supports design-level derivation of the cascade as a whole, not the mechanism-specific adaptations v1.0.0 asserted.

---

## 9. Repository-Provenance Errors

1. §3 framed tracked `uri_core/` mechanisms as a "historical prototype." They are `CURRENT_V1_URI_CORE`, same commit, mostly live (`CapabilityContextResolver` via `MultiActionDispatch`; `TurnState` via `decision_engine.build_turn_state_and_directory`, live by default; `FileStore` via `server.py`; `ARNEngine` via `canonical_execution.py:722–730`).
2. `ARNEngine` listed as a legacy discovery — created by ARN.1 on 2026-09-20, four days before the registry.
3. §3.3 anti-patterns presented as legacy history: first-item selection, fail-open catalog, and prose pronoun rules are **all still in live code**; hardcoded extractor partially remediated (`nit sikkim` removed 2026-09-12; insurance regex remains in `services/evidence_fact_extractor.py:83`); path was `core/` in v1.0.0, actually `services/`.
4. Quote cited at `context_resolver.py:34`; actual line 26.
5. `uri_v1` components described as active/authoritative; `uri_v1` is untracked and unreachable from the live server.
6. Three distinct "ARN"-named things were not distinguished: `uri_core/core/arn` (live recovery engine), `uri_v1/arn` (A2.8A–C uncertainty/resolution-path experiments), and "RAR" (turn-level reference binding).
7. The §6 architecture diagram showed `uri_v1` Step-1 components flowing into `uri_core` Decision Gates/Canonical Execution; no such connection exists.

Repairs: registry §0 (provenance statement and labels), §0.1 (lineage labels), provenance labels on every repaired `uri_core`/`uri_v1` entry.

---

## 10. Quantitative / Benchmark-Scope Errors

| Entry | Defect | Repair |
|---|---|---|
| FIND-RAR-001 | Presented 89.7%/73.5% as RAR capability without stating that reference expressions, candidate pools, `target_type_hint`, and deterministic anchors were fixture-supplied; omitted Stage 4B-C; called RAR "core resolution layer" | Conditions stated; historical chain Stage 2 → 3 → 4 → 4B-B → 4B-C preserved in order; Architecture D, 19.9% lower bound, unquantified split added; `IMPLEMENTED_UNWIRED` |
| FIND-RAR-002 | "Architecture C" presented as current; 75.0% DET-ONLY treated as a deterministic-core figure | 4B-C correction linked; 8/7/6 breakdown added; 58.8%/75.0% marked artifact of pre-segmented expressions |
| PEND-EV-007 | "15.4% of references require upstream type hints" | 15.4% = 8 recency + 7 type + 6 negation; `target_type_hint` alone 7/136 (5.1%) |
| FIND-RAR-003 | 12-case single run labelled `PROVEN`; "~1B threshold" | `OBSERVED`, n noted (1 case = 8.3 pp); threshold `HYPOTHESIS` |
| FIND-QUAL-001 | 100%/100%/50% without n; latency and RAM figures not from B.4 | 8/8, 4/4, 2/4; B.4 p50/p95; 101.4–101.6 MB |
| FIND-QUAL-004 | Omitted torture 10/12; reference-binding 100% and 0 wrong bindings not flagged as RAR-over-supplied-candidates; "validated in A2.8B/C" (different, smaller benchmarks where raw 9B scored 41.7%) | All added/corrected |
| FIND-SEM-005 | "100% extraction accuracy"; recall never measured; closed vocabularies omitted | Corrected; 21 reference patterns, 2 entity literals, turn-global negation; recall `UNMEASURED` |
| FIND-LAT-002 | `PROVEN` on one hardware setup; 8.1x vs 3.1x baselines differ (serial Mode A vs Mode B) | `OBSERVED`; baselines stated |
| §5 A2.5 / A2.6–A2.7 / A2.8A–C rows | Headline numbers without conditions; "passed 100% of all gates"; "eliminated premature execution" | Rewritten with conditions and contrary evidence |
| §5 A0–A2.4R row | "7.4s" | Source is A2.4R's range 7.4–8.5 s; A2.4 means 7.6–8.6 s — both now stated (v1.0.0 quoted a lower bound only; initial audit wording that it was "not found" was itself corrected before completion) |
| §6 Resolution-Path row | "Eliminated premature execution; 100% NO_TOOL accuracy" | One case, one model; structured mode reduced 9B final-path success; LFM passed NO_TOOL "by coincidence" per the report |

---

## 11. Rejection-Scope Errors

- **FIND-QUAL-002 / §7.1 SmolLM2 & Qwen2.5-0.5B:** v1.0.0 said "negligible quality gain over deterministic baselines" and "failed basic reasoning benchmarks." **Contradicted by B.4**: Qwen2.5-0.5B gave a 50-point gain over the no-reasoner configuration (2/4); SmolLM2 was a language worker (rubric +0.292, 0/4 exact). Both were bypassed because Main-Brain controls scored 4/4. Now `REJECTED_FOR_ROLE`, conditional on a local 9B/12B Main Brain; "permanently" removed.
- **LFM2.5-350M:** "disqualified permanently" → `REJECTED_FOR_ROLE` (Step-1 decoding/feeds).
- **Qwen3.5-0.8B:** "minimum parameter boundary for extraction established at ≥1.9B" → `HYPOTHESIS` (A2.2 recommended the 1.5B–3B tier).
- **Needle 3:** decoder rejection correctly role-scoped in v1.0.0, but the explicitly-open **narrow auxiliary role** (A2.1 §23, A2.4R §11: `POTENTIAL AUXILIARY ROLE — REQUIRES SEPARATE QUALIFICATION`) was omitted everywhere, making Needle look closed beyond evidence. Added to FIND-QUAL-001, §7.1, and PEND-EV-009.
- **Qwen3.5-2B:** "excellent for fast goal classification" — goal accuracy was one dimension of a decoder benchmark, not a standalone classifier qualification → `HYPOTHESIS`.
- **Unconstrained JSON (§7.2):** "mandatory for <2B" generalized one 773M model → `HYPOTHESIS`.

---

## 12. Reusable-Mechanism Corrections

Answers to the nine required questions, per mechanism:

| Mechanism | Exists / where | Tested | Production-wired | Problem actually solved | Registry description accurate? | Reuse: fact or potential | Already independently present in URI? | Omitted failure modes |
|---|---|---|---|---|---|---|---|---|
| `CapabilityContextResolver` | Yes, `CURRENT_V1_URI_CORE` | Single-match only | Yes (`MultiActionDispatch`) | Post-action argument grounding from last result | No ("binds pronouns") | Potential (planned, not built) | Retention principle independently in RAR | **Silent first-item selection on multi-match** (negative precedent, still live) |
| `$from` linking | Yes, `uri_core` | Yes | Yes | Explicit chain path lookup | Yes | Claimed reuse is false | — | None material |
| `FactManager` | Yes, `uri_core` | Yes | Yes | Fact lifecycle | Yes | RAR reuse claim false | Append-only discipline independently in RAR | None found |
| `ContextBuilder` | Yes, `uri_core` | Not verified | Not verified | Field-satisfaction clarification | Not verified | ARN reuse unverified | — | Not assessed |
| `ARNEngine` | Yes, `uri_core` (2026-09-20) | 10 focused tests | Yes (`canonical_execution`) | Recovery from empty search | Yes, but mislabelled legacy | Operational in `uri_core` | Abstention stance independently in RAR | ARN.2/ARN.3 deferred; clarification text not wired |
| `FileStore` | Yes, `uri_core` | Yes (M34) | Yes | Session-scoped attachment handles | Yes | RAR reuse false; `POTENTIAL_MATCH` | — | Plural per-turn list; no singular "current attachment" |
| `CapabilityRelevance` | Yes, `uri_core` | Yes | Yes | Term discrimination over capabilities | Yes | **Real adaptation** into RAR Level 6 | — | Sparse-catalog limitation (already listed) |
| `TurnState` active pointer | Yes, `uri_core` | Yes | Yes (stale docstring says otherwise) | Fresh projection of pending interaction | Partly ("clears read-once" misattributed) | Planned, not built | — | Stale module docstring; canonical-path clearing `UNKNOWN` |
| TurnFrame | Yes, `uri_v1` (untracked) | Unit tests; no recall benchmark | No | Deterministic surface cues | Overstated accuracy | Used in `uri_v1` experiments | — | Closed vocabularies; turn-global negation |
| RAR cascade | Yes, `uri_v1` (untracked) | Stages 2–4B | No | Bind supplied expression to supplied candidates | Overstated scope | Not reused anywhere live | — | 6 independent wrong bindings; Level 0/1 unfed |
| Mode D feeds | Yes, `uri_v1` (path corrected) | Latency benchmarks | No | Concurrent narrow decoding | Path wrong | — | — | Single hardware setup |
| Think suppression | Yes (path corrected) | Not verified | No | Skip long reasoning traces | Path wrong | — | — | Effect measurement not located |
| Resolution-path tri-separation | Yes, `uri_v1/arn` | A2.8C (16 cases) | No | Requirement/path/capability separation | Overstated | Experimental | — | **Reduced 9B accuracy; 2.7× slower** |

Negative precedents now recorded in the registry: first-item selection (live), A2.8D `fast_path_gate.py` benchmark-answer hardcoding (`CONTAMINATED`), prose pronoun rules (live), structured single-prompt separation accuracy penalty.

---

## 13. Historical Contradictions Preserved

The registry now records each as original evidence → later correction → current interpretation, without rewriting the original:

1. RAR wrong bindings: Stages 2, 3, 4 and A2.5 Stage-3 adversarial all reported 0 → Stage 4B-B found 6/136 → Stage 4B-C attributed them to three mechanisms (not 4B-B's single cause) → current: nonzero confident-wrong-binding rate on independent data; 0 invented IDs still holds.
2. RAR coverage: 4B-B "Architecture C, ~59% deterministic core" → 4B-C "Architecture D, split unquantified, 19.9% proven lower bound" → current: raw-turn coverage `UNMEASURED`.
3. Needle: M33.2 early general-Edge candidacy → B.4 `RESIDENT` reflex only → A2–A2.4R Step-1 decoder rejection → A2.4R narrow auxiliary role left open → never qualified; A2.8D unqualified.
4. Qwen3.5-9B: A2.7 38-case gates passed → torture 10/12 → A2.8B raw 41.7% on a different 12-case set → A2.8C structured-mode regression → current: qualified for one role under one benchmark.
5. Fail-open capability catalog: A2.5 legacy audit calls it an anti-pattern → live `decision_engine.py:359–361` deliberately keeps it with documented rationale → current: contested design question, not a registry fact.
6. `TurnState` wiring: module docstring "not called by live code" → M32 B1.1 canonical-live-by-default → current: live.

---

## 14. JSON-Index Schema Audit

Not implemented. The proposed `uri_evidence_index.json` schema cannot preserve what the registry needs:

| Required property | Schema support | Defect |
|---|---|---|
| Evidence source | `primary_evidence_file` (single string), `telemetry_file` | Cannot hold multiple sources or a section/line anchor |
| Repository provenance | **None** | No field for `CURRENT_V1_URI_CORE` / `PROTECTED_LEGACY_URI_AGENT` / `URI_V1_NEW`, commit, or tracked/untracked state |
| Classification | Enum | Missing `LINEAGE_UNVERIFIED`; no "qualified for role" |
| Scope | Free string | Adequate but unstructured |
| Conditions (benchmark, n, oracle-supplied inputs, hardware) | **None** | This audit's most frequent defect class cannot be represented |
| Limitations / confounds | **None** | — |
| Historical corrections | **None** | No `original_claim` → `correction` → `current_interpretation` chain; violates registry invariant 1 in machine form |
| Lineage status | **None** | No `lineage` object (`relation`, `source`, `evidence`) |
| Reuse guidance | `do_not_repeat` only | No positive reuse guidance, no negative-precedent flag |
| Supersession | **None** | No `superseded_by` / `supersedes` IDs |
| Role scope for rejections | **None** | `rejected_for_role` exists as a relevance value without a role field |
| Extensibility | `additionalProperties: false` at record level | Blocks adding any of the above without a schema version change |

Other defects: `finding_id` pattern `^FIND-[A-Z]+-[0-9]{3}$` excludes `PEND-EV-*` and mechanism entries; `current_relevance` overlaps `classification`; `key_metrics` values carry no n/denominator; `total_records` not required and unvalidated. A note pointing here was added at registry §9.

---

## 15. Remaining UNKNOWN / UNMEASURED Items

| Item | Status |
|---|---|
| Clusters 5–8 entries not verified (GATE-001/003, DEC-001/002/003, LAT-001, MEM-001) and their `PROVEN` labels | `UNKNOWN` — flagged in registry |
| §5 lineage rows M6 through ARN.1 | `UNKNOWN` |
| PEND-EV-001…006, 008 | Not re-verified |
| FIND-SEM-001 secondary metrics (11.1%, 61.1%), SEM-002 "8 of 18 ≥ 0.82" | Not re-verified |
| Whether the canonical `/ask` path clears `last_goal_attempt_history` | `UNKNOWN` |
| Think-suppression effect ("eliminated token-exhaustion timeouts") — which report measured it | `UNKNOWN` |
| `FileStore` "stopped prompt injection" | Not re-verified |
| FIND-ARN-003 "solved in Mode D" | Not verified |
| A2.8 manifest's `TORT-10` wording ("Hold off deploying until tomorrow at 10am") differs from A2.7's `TORT-10` ("Do not file the expense report until next Monday") | `UNKNOWN` which is authoritative; both classify the case as deferred/temporal |
| Any UI-side "selected object" concept outside the Python backend | `UNKNOWN` |

**Corrections needed in other documents (recorded, not edited — outside this audit's authority):**
- `docs/plans/M35_URIV1_A2_5_LEGACY_DETERMINISTIC_REFERENCE_AUDIT.md` frames tracked `uri_core` as a "historical prototype" — origin of the registry's provenance error.
- `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_DISCOVERY_PLAN.md` §6 (ARN row, line ~96) still says legacy ARN is "not yet wired into the legacy orchestrator's live loop"; `canonical_execution.py:722–730` calls `attach_not_found_recovery` on the live-by-default path. Its TurnState row ("no read-once/expiry hack") is correct for `TurnState` itself but omits that one of its input fields is read-once-cleared by `process_user_input`. Both that plan and `M35_URIV1_PRE_RAR_CANDIDATE_ANCHOR_SOURCE_AUDIT.md` treat `uri-agent` and `_V1\uri_core` as distinct codebases; they are one repository at one commit.
- `uri_core/core/turn_state.py` module docstring is stale (claims no live caller). Code comment, not changed.

---

## 16. Exact Registry Edits Performed

File: `docs/governance/URI_DEVELOPMENT_EVIDENCE_REGISTRY.md` (909 → 962 lines; md5 `0c424312d42d8fcbf4c10e7db8306ecd` → `b5005cfc119f9f01a2ac47365e9a25e5` final). `uri-agent` worktree status unchanged by this audit (65 pre-existing entries). Pre-audit copy: `C:\Users\cheta\AppData\Local\Temp\claude\C--Users-cheta-Development-Uri--V1\d8fe4ebe-a0a7-448f-98f2-66b481fcc295\scratchpad\REGISTRY_v1.0.0_pre_audit.md` — **session scratchpad, not durable**. Because the registry is untracked, v1.0.0 has no git history; every repaired entry therefore quotes the v1.0.0 claim inline ("v1.0.0 said …").

1. Header: version → `1.0.1-audited`; classification-status note.
2. Added audit notice block.
3. Added §0 Repository Provenance.
4. Added §0.1 Lineage Labels.
5. §1.2: classification-discipline correction note.
6. §2: inventory-gap note; items 74–79 added.
7. §3 intro: repository-identity correction.
8. §3.1: line citation 34 → 26; `SIMILAR_PRINCIPLE` note.
9. §3.2: table replaced with corrected table retaining v1.0.0 dispositions in their own column; read-once / stale-docstring correction note.
10. §3.3: current-code corrections for items 1–4; A2.8D negative precedent.
11. FIND-SEM-002: classification, scope, relevance, open question.
12. FIND-SEM-003: finding, classification, scope, later-evidence, relevance, reuse.
13. FIND-SEM-004: later-evidence (anti-contamination rule), relevance, open question.
14. FIND-SEM-005: entry rewritten (classification, scope, evidence, measurements, limitations, later evidence, relevance, reuse, open question).
15. FIND-RAR-001: finding, classification, scope, conditions, limitations, historical chain, later evidence, relevance, reuse, do-not-repeat, open question.
16. FIND-RAR-002: classification, scope, limitations, later evidence.
17. FIND-RAR-003: finding, classification, later evidence, relevance, reuse, do-not-repeat.
18. FIND-ARN-001: scope, measurement evidence label.
19. FIND-ARN-002: scope/provenance note.
20. FIND-QUAL-001: finding, classification, scope, measurements, later evidence, relevance.
21. FIND-QUAL-002: finding, classification, scope, measurements, relevance, reuse, do-not-repeat, open question.
22. FIND-QUAL-003: later evidence, relevance, reuse.
23. FIND-QUAL-004: finding, classification, measurements, later evidence, relevance, reuse.
24. FIND-QUAL-005: later evidence, relevance.
25. FIND-GATE-002: lineage-verified note. FIND-LAT-002: finding, classification, relevance, reuse. FIND-MEM-002: later evidence.
26. Clusters 5–8 audit flag.
27. §5: rows A0–A2.4R, A2.5, A2.6–A2.7, A2.8A–C rewritten; rows A2.8D, A2.9, Step-2 reconstruction added.
28. §6: diagram wiring note; rows Context Resolver, Fact Supersession, TurnFrame, RAR, Attachment Handles, Mode D, Think Suppression, Resolution-Path corrected.
29. §7.1: Needle narrow-schema, Qwen 0.8B, LFM, SmolLM2/Qwen0.5B rows. §7.2: prompt-only references, first-item, fail-open, unconstrained JSON rows.
30. §8: PEND-EV-007 corrected; PEND-EV-008 "not re-verified"; PEND-EV-009 and PEND-EV-010 added (both are existing documented open items).
31. §9: schema-deficiency note. §3.3 item-1 current-code note (added in final pass).

Not changed: §10 maintenance invariants (changing them would be governance), Clusters 5–8 entry bodies, PEND-EV-001…006.

---

## 17. Suitability as a Future Shared Evidence Source

**`READY_WITH_LIMITATIONS`**

Usable now as an **index to primary evidence** for Claude, Codex, Gemini and Antigravity, provided readers follow the audit notice and treat entries without an audit note in Clusters 5–8 as unverified pointers.

Limitations that must hold before it is treated as authoritative:
1. **It is untracked.** A shared durable source must be committed; today it exists only in one working tree and has no history. (Commit is a User decision; this audit does not commit.)
2. Clusters 5–8, most §5 rows, and six pending items remain unverified and still carry v1.0.0 `PROVEN` labels under a blanket flag.
3. The proposed JSON index must not be built from the current schema (§14).
4. The source document that introduced the "legacy prototype" framing (`M35_URIV1_A2_5_LEGACY_DETERMINISTIC_REFERENCE_AUDIT.md`) and two of this session's plans still carry provenance/wiring statements the registry now contradicts (§15). Readers comparing documents will find conflicts until those are corrected.
5. Maintenance invariants in §10 do not yet require repository-provenance or lineage labels; without that, future entries can reintroduce this audit's two most common defect classes.

Why not `READY_FOR_SHARED_USE`: items 1–2. Why not `NOT_READY_FOR_SHARED_USE`: the high-impact areas (lineage, RAR, model qualification/rejection, provenance) are now evidence-grounded, and the remaining gaps are explicitly labelled rather than hidden.

---

## Self-Review Against the Task's Final-Verification Checklist

- Modified sections reread: §0–§3.3 fully reread after edit; residual-phrase sweep run over the whole file (`ADAPTED** into`, `REUSED in`, `ready for production`, `safe for production`, `permanently`, `Architecture C`, `qwen_feeds`, `Authoritative`, `ACTIVE_BASELINE`, `PROVEN`). Remaining hits are either inside "v1.0.0 said …" quotations, role-scoped (`Disqualified permanently from Step 1` quoting A2.3's own verdict), correct `uri_core` baselines, or covered by the Clusters 5–8 flag.
- Each repaired claim cites a document, file, or line.
- Repository provenance stated in §0 and on every repaired `uri_core`/`uri_v1` entry.
- No unsupported lineage remains asserted; the only positive mechanism-specific lineage kept is Level 6 ← `capability_relevance.py`.
- Rejected models are rejected only for evidenced roles; Needle's open auxiliary role is recorded.
- Historical benchmark numbers retain their conditions (supplied inputs, n, hardware).
- Recent RAR and candidate/anchor findings are incorporated (FIND-RAR-001/002, FIND-SEM-005, FIND-MEM-002, §3.2, §6, PEND-EV-010).
- One correction made during the audit to the audit's own repair: the §5 "7.4s" note first said the figure was not found; A2.4R reports 7.4–8.5 s, so the note now says v1.0.0 quoted A2.4R's lower bound.

Stopped at `VERIFICATION_READY`. No commit, no push, no JSON index, no governance adoption, no architecture or production-code changes.
