# M35 URIv1 — RAR Natural-Boundary Independent Raw-Turn Fixture Authoring Report

**Type:** Fixture authoring only. No TurnFrame execution, no RAR execution, no benchmark run, no production change, no architecture change, no commit, no push.
**Status:** `VERIFICATION_READY`
**Verdict:** `FIXTURE_CORPUS_FROZEN_AND_READY` (with the disclosed indirect-exposure limitation in §11)

---

## Acceptance criteria (defined before authoring)

1. Every case starts from `raw_user_text`; no pre-segmented expression is the primary input.
2. All twelve required categories A–L are present, with a balanced difficulty spread.
3. 60–80 unique semantic cases; C1/C2 are variants of one case, not separate cases.
4. Ground truth describes user intent only: no cascade level, regex match, TurnFrame ID, lexical score, or confidence.
5. Every expected candidate ID is present in that variant's pool; no candidate is created after the turn's `session_now`; every annotated span occurs verbatim in the raw text.
6. File candidates follow the real `StoredFile.to_reference()` shape, and benchmark additions are labeled as such.
7. Independence metadata and the three blinding flags are recorded truthfully; any exposure is disclosed.
8. The corpus is frozen with a SHA-256 hash.

Self-review against these criteria: see §15–§16. All eight are met. Criterion 7 carries one disclosed limitation (§11).

---

## 1. Repository state

- Workspace: `C:\Users\cheta\Development\Uri\_V1`
- Branch: `m35-uri-v1-parallel-architecture` (verified with `git rev-parse --abbrev-ref HEAD`)
- HEAD: `e8e3b65`
- Working tree before authoring: `SKILL.md` modified locally, many untracked `docs/plans/*` evidence files. Nothing else was modified by this task.
- Files this task created: the corpus JSON (§12) and this report. No other repository file was created or changed.

## 2. Blinding declaration

| Flag | Value |
|---|---|
| `RESOLVER_INTERNALS_NOT_INSPECTED` | `true` |
| `TURNFRAME_PATTERN_LIST_NOT_INSPECTED` | `true` |
| `PREVIOUS_RAR_FIXTURES_NOT_INSPECTED` | `true` |

None of the prohibited files was opened, read, grepped, or delegated to another agent. One Glob listing of `uri_v1/**/*fixture*` returned file *names* only (used to choose the output location). No file content was shown. Second-hand statements about the implementation in the approved plan are disclosed in §11.

## 3. Sources inspected

| Source | What was read | Purpose |
|---|---|---|
| `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_DISCOVERY_PLAN.md` | Section headings; header (lines 1–19); §7–§15 (lines 103–236) | Experimental protocol: S1/S2 × C1/C2/C3 grid, oracle label requirements, independence controls, fixture blueprint |
| `uri_core/core/file_store.py` | Grep of `StoredFile` fields, `to_reference()` (lines 94–119), `file_id = str(uuid.uuid4())` (line 231), and the record loader (lines 352–363) | Real file-reference shape for attachment candidates |
| `git` state | Branch, HEAD, `git status --short` filtered | Repository verification |

Plan §1–§6 (current Step-1 outputs, RAR input contract, historical evidence, legacy mechanism comparison) were **not** read, because their headings show they describe implementation internals.

## 4. Sources explicitly NOT inspected

- `uri_v1/turn/rar_deterministic.py`
- `uri_v1/turn/turn_frame_builder.py`
- `uri_v1/turn/rar_contracts.py`
- `uri_v1/turn/active_context.py`, `uri_v1/turn/lfm_semantic_decoder.py`
- All existing RAR fixture files: `rar_fixtures.py`, `rar_challenge_fixtures.py`, `rar_stage3_blind_fixtures.py`, `rar_stage4b_independent_fixtures.py`, `rar_adversarial_fixtures.py`
- All prior RAR stage reports, manifests, and audit documents, including `M35_URIV1_PRE_RAR_CANDIDATE_ANCHOR_SOURCE_AUDIT.md` and `M35_URIV1_RAR_NATURAL_BOUNDARY_INDEPENDENT_AUDIT.md`
- Plan §1–§6
- The graphify knowledge graph (not queried, because it would expose resolver structure)

## 5. Fixture methodology

1. One fictional but realistic office workspace (one user, 24 Sep 2026): budget spreadsheets, a lease in three versions, invoices, CVs, board minutes, site photos, a receipt photo, a price list, an insurance certificate, a poorly named scan, letters, emails, approvals, contact and employee records, URI-generated reports, tool results, actions, a calendar event, and agendas. The objects live in one shared `candidate_library` (42 objects).
2. Each case was written as a real user would type it: mixed register, fragments, lowercase, British office idiom, typed filenames, a pasted UUID, pronouns, and implicit edits with no reference words.
3. Wording was chosen from the scenario, not from any list of recognized expressions. The task prompt itself requires recency words (latest, previous, earlier, most recent, one before that); these were used where a user would naturally say them.
4. Ground truth was set by asking what a careful human assistant would do with the same context. Where a human would ask a question instead of guessing, the ground truth is `AMBIGUOUS` or `UNKNOWN`.
5. The draft was written in an earlier ad-hoc schema. The final task specification arrived during authoring, before any freeze. The draft was then re-categorized to the specified A–L taxonomy. Ten cases were added (4 person/entity, 3 multiple-plausible, 3 no-reference). A pure data-transform script converted everything to the final schema and validated it. The script lives in the session scratchpad, outside the repository, and imports nothing from the repository. The transform removed the draft's pre-annotated plan §10 failure-class field, because the final specification prohibits implementation-oriented hints in ground truth.
6. No wording was tuned after any system output, because nothing was executed.

## 6. Category distribution (79 cases)

| Category | Cases |
|---|---|
| A — Explicit reference | 5 |
| B — Immediate conversational | 5 |
| C — Attachment (single, multiple, identifiable, ambiguous) | 7 |
| D — Recency | 7 |
| E — Type-based | 6 |
| F — Named object | 6 |
| G — Person/entity (clear fit and multiple fit) | 6 |
| H — Negated reference | 6 |
| I — Multiple plausible (AMBIGUOUS) | 7 |
| J — Missing candidate | 6 |
| K — No actual reference | 7 |
| L — Natural mixed | 11 |

Eleven cases contain more than one reference (mostly in L). Each case also lists `secondary_signals` to show the other signals present in it (for example, the C attachment cases that also involve a person).

Expected outcomes per reference, summed over all cases:

| Condition | RESOLVED | AMBIGUOUS | UNKNOWN | NO_REFERENCE |
|---|---|---|---|---|
| C1 | 64 | 12 | 8 | 7 |
| C2 | 58 | 18 | 8 | 7 |

Six references change from `RESOLVED` in C1 to `AMBIGUOUS` in C2. This is intentional: in those cases the realistic pool removes the only discriminator (e.g. "the PDF" with one PDF vs. several).

## 7. Difficulty distribution

| Difficulty | Cases |
|---|---|
| straightforward | 20 |
| moderate | 34 |
| ambiguous (correct answer is to ask) | 11 |
| difficult but realistic | 14 |

"Difficult" cases need calendar reasoning ("last quarter"), world-knowledge paraphrase ("the place we're renting"), status reasoning (only a pending request can be approved), negation scoped to one clause, or conflicting signals (position vs. description). Adversarial tricks with no plausible user basis were avoided.

## 8. C1/C2 construction method

- **C1 (clean):** the intended candidate(s), plus only the same-kind siblings the situation itself depends on. A "latest minutes" case needs both minutes files in C1, or recency is untested. An ambiguity case needs all equally valid candidates in C1.
- **C2 (realistic):** C1 plus distractors along axes a real workspace produces: same type, overlapping title words (e.g. "September" in minutes vs. a P&L request), nearby creation time, same person name (two contacts named Marcus Hale), an action or email about the target object, or a derived report of the target spreadsheet.
- **C3:** not authored, as the task instructs. The corpus's `harness_input_contract.C3_derivation` states the rule: no candidates. Expected result is `UNKNOWN` for every reference, and `NO_REFERENCE` for K cases.
- Each variant has its own `expected_by_reference`, because the correct answer can change between C1 and C2.
- Validation guarantees: every expected, alternative, and attachment ID is in its variant pool; no pool member was created after the turn's `session_now`; and pools contain no duplicates.

## 9. Ground-truth methodology

Per case:
- `case_id`, `category`, `difficulty`, `raw_user_text`, `conversation_context` (`session_now`, `prior_turns`, `turn_attachments`), and `reason`.
- `ground_truth_references[]` (oracle annotation, separate from the input): the span a human would mark (`null` for implicit references, with `implicit_antecedent`), `intended_type`, `temporal_meaning`, and `user_exclusions` scoped to that reference only. The vocabulary is the author's own and is not mapped to any resolver field. Mapping is the later scorer's job.
- Per variant: `candidate_condition`, `available_candidates`, `expected_outcome`, `intended_candidate_id`, and `expected_by_reference[]` (outcome, IDs, `plural_reference`).
- `acceptable_alternatives` appears where a reasonable reviewer would also accept another answer (e.g. abstaining on a case that needs world knowledge). The scorer must report these separately and must not merge them into the primary expectation.

Ground truth contains no cascade level, regex, TurnFrame ID, lexical score, or confidence.

Judgement calls that affect ground truth (listed so reviewers can dispute them):
- **NB-C-06:** "The first attachment is our insurance certificate", where the first attachment is actually `scan_0034.pdf`. Primary: `AMBIGUOUS`. Alternative: the certificate.
- **NB-C-07:** "first thing this morning", with two CVs uploaded 50 seconds apart. Primary: `AMBIGUOUS`. Alternative: the earlier CV.
- **NB-I-06 (forward "the letter" to Priya):** Priya being in HR is judged not to be a sufficient discriminator.
- **NB-I-07 ("the money one"):** in C1, the topic is treated as a discriminator (the budget vs. a roster).

## 10. Candidate realism methodology

- **Real source state:** `uri_core/core/file_store.py` `StoredFile` holds `file_id` (uuid4), `filename`, `stored_name`, `media_type`, `size_bytes`, `session_id`, `created_at`, and `schema_version`. `to_reference()` exposes only `file_id`, `filename`, `media_type`, and `size_bytes`.
- **Benchmark candidate representation (files):** `representation: file_reference_shape`. `file_reference` contains exactly the four `to_reference()` fields, with uuid4-format IDs. `benchmark_added` contains `created_at` (a real `StoredFile` field that `to_reference()` does not expose) and `object_type` (derived from `media_type` by the author). These are **not** literal production RAR candidate objects. No production path currently carries file references into `uri_v1/turn/`, according to the plan's amendment note in §8.
- **Non-file objects:** `representation: synthetic_minimal`. These carry only the fields each scenario needs: `object_type`, `title`, `created_at`, and optionally `origin`, `status`, `direction`, and `counterparty`. Synthetic IDs are opaque (`obj-xxxxxx`) so that IDs carry no semantic words. No future URI object model is proposed.

## 11. Independence limitations

1. **Indirect exposure through the approved plan.** The plan's §8–§10 (read before the full task specification arrived) state second-hand facts about the implementation:
   - a 21-pattern Step-1 vocabulary exists (the patterns are not shown);
   - the real wired recency field only takes a "same"-type value or none;
   - a later resolver stage was taught to use words such as "latest", "current", and "previous";
   - production does not derive per-reference negation or type hints;
   - attachment examples "the attached PDF" and "this spreadsheet" appear in an amendment note.

   No pattern list, regex, or code was seen. **Effect on the verdict:** low. The recency words used in the corpus are required by the task prompt itself. "same" is not used in any case. Neither example attachment phrase appears verbatim; "the spreadsheet" appears twice because it is the natural wording. This matches the plan's own §12 expectation that full blindness may not be achievable. The limitation is recorded in the corpus's `independence.known_indirect_exposure` field. The corpus is **not** labeled fully "blind".
2. **Knowledge of the experiment's hypotheses.** The author read the plan's failure taxonomy (unscoped negation, distractors, recency and type gaps). Some cases exercise those situations, for example negation in one clause with a reference in another (NB-L-06). The task requires these situations: the H and L categories and the "name + negation" example. They were written as natural office turns, but a reader should know the author understood which phenomena were under study.
3. **Single author.** One model authored both the turns and the ground truth. No second human annotator checked agreement. The judgement calls in §9 are the most likely points of disagreement.
4. **Synthetic workspace.** The turns are realistic but invented. They are not sampled from real URI traffic, so frequency statistics from this corpus do not estimate real-world frequencies.

## 12. Frozen corpus path

`uri_v1/turn/rar_natural_boundary_raw_turn_fixtures.json`

The file sits next to the existing `uri_v1/turn/rar_*_fixtures.py` benchmark fixture files, following the `rar_<stage>_fixtures` naming convention; only the file names were observed. It is JSON data, not a Python module, so it contains no executable logic. It is benchmark-only and is not imported by production code.

## 13. Fixture count

- 79 unique semantic cases
- 158 authored candidate-pool variants (C1 + C2 per case); C3 is derived by the harness
- 84 ground-truth references across 72 reference-bearing cases (11 of them multi-reference), plus 7 no-reference cases; 91 expected-outcome entries per condition
- 42 candidate objects (18 file-reference-shaped, 24 synthetic)

## 14. SHA-256

```
0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380  uri_v1/turn/rar_natural_boundary_raw_turn_fixtures.json
```

The corpus is frozen at this hash. The later execution phase must use it unchanged. Change it only if a fixture is objectively malformed. Record any such correction in a separate post-freeze correction document that gives the old hash, the new hash, and the reason. Do not overwrite silently.

## 15. Contamination status

**NOT CONTAMINATED** under the task's definition: all three blinding flags are `true`. The indirect plan exposure in §11.1 is disclosed as a limitation, not hidden, and it does not falsify any flag.

Pre-freeze quality review (checks run only against the task's review list, never against RAR behavior):
- **Internal consistency:** three timestamp inconsistencies were found in the draft and fixed before freeze. In two, a candidate was created after the turn's time. In one, a pool member only existed later in the day. The transform script's validation now enforces this rule for every variant.
- **Duplicates:** no duplicate `raw_user_text`. Paired cases that share objects on purpose (e.g. "approve the leave request" vs. "what dates is the leave request for?") differ in whether the context contains a discriminator. They are not duplicates.
- **Impossible ground truth:** all expected IDs are in their pools. RESOLVED has exactly one ID unless the reference is plural. AMBIGUOUS has at least two IDs. UNKNOWN has none.
- **Missing metadata:** every pool ID exists in `candidate_library`.
- **Answer leakage:** candidate titles and IDs contain no ground-truth annotations. `harness_input_contract` lists which fields the system under test may and may not receive. `reason`, `category`, `difficulty`, and all `expected_*` fields are excluded.
- **Category balance:** every category has 5–11 cases.

## 16. Readiness for independent execution

Ready. To run, the execution phase needs:
- a harness that feeds only `raw_user_text` + `conversation_context` + resolved `available_candidates` to the system under test;
- a candidate-mapping step that converts `candidate_library` entries into the resolver's input type, documented in the execution report. This mapping is not defined here, to preserve blindness;
- a separate scorer that maps `temporal_meaning`/`intended_type`/`user_exclusions` to S2 oracle inputs and applies plan §10.

None of these is part of this task.

**Final verdict: `FIXTURE_CORPUS_FROZEN_AND_READY`**
