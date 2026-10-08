# M35 — URIv1 Parallel Architecture
## Batch A1 Completion Report: `DecodedRequest` Semantic Contract

**Status:** COMPLETE & ACCEPTED  
**Date:** 2026-09-21  
**Batch:** A1 (Step 1 Semantic Contract Design & Validation)  
**Worktree:** `C:\Users\cheta\Development\Uri\_V1`  
**Branch:** `m35-uri-v1-parallel-architecture`  
**Baseline HEAD:** `e8e3b65259c45fc823addc3ef8969425a265bd1b`  
**Original Prototype Worktree:** `C:\Users\cheta\Development\uri-agent` (PROTECTED — 100% UNTOUCHED)

---

## 1. Executive Summary

Batch A1 replaces the placeholder `DecodedRequest` introduced in Batch A0 with the full, typed semantic contract required by URIv1 Step 1.

Step 1 answers:
> **What does the user mean and what outcome are they asking for?**

A1 enforces the fundamental architectural boundary:
- Step 1 performs **semantic interpretation only**.
- It does **NOT** resolve references, select tools, query Graphify or history, invoke ARN, or execute workflows.
- Unresolved information remains explicitly unresolved.
- `operation != capability` and `operation != tool`.
- Negative/prohibited operations (e.g. "don't send", "do not summarize") are strictly distinguished from requested operations.

---

## 2. Files Changed & Added

All work occurred strictly inside `C:\Users\cheta\Development\Uri\_V1`:

| File | Status | Description |
| :--- | :--- | :--- |
| `uri_v1/turn/contracts.py` | MODIFIED | Implemented typed `DecodedRequest`, supporting value objects, and domain enums. Preserved A0 contracts (`ContextPack`, `EdgeOutcome`, `IntelligenceResult`, `FinalizedTurn`). |
| `uri_v1/turn/decoder.py` | MODIFIED | Implemented provider-neutral `SemanticDecoder(ABC)` and `DecodeInput` value object. |
| `uri_v1/turn/__init__.py` | MODIFIED | Exported all new contracts, enums, value objects, and decoder classes. |
| `test_m35_uriv1_a1_decoded_request.py` | NEW | 15 comprehensive unit tests covering all 10 semantic cases, immutability, serialization, and boundary checks. |
| `docs/plans/M35_URIV1_A1_DECODED_REQUEST_REPORT.md` | NEW | This architectural completion and validation report. |

---

## 3. Final Schema: `DecodedRequest`

```python
@dataclass(frozen=True)
class DecodedRequest:
    """Output of Step 1 (Semantic Request Decoding).

    Captures: What does the user mean and what outcome are they asking for?
    Does NOT resolve references, select tools, or query external state.
    """
    raw_text: str
    goal: IntendedOutcome = field(default_factory=lambda: IntendedOutcome(description=""))
    operations: Tuple[SemanticOperation, ...] = ()
    prompt_supplied_context: Tuple[str, ...] = ()
    constraints: ConstraintScope = field(default_factory=ConstraintScope)
    output_preferences: OutputPreferences = field(default_factory=OutputPreferences)
    entities: Tuple[MentionedEntity, ...] = ()
    references: Tuple[SemanticReference, ...] = ()
    temporal_references: Tuple[TemporalReference, ...] = ()
    attachments: Tuple[AttachmentReference, ...] = ()
    dependencies: Tuple[ContextDependency, ...] = ()
    ambiguities: Tuple[SemanticAmbiguity, ...] = ()
    confidence: SemanticConfidence = field(default_factory=SemanticConfidence)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

### Key Properties & Methods
- `requested_operations -> Tuple[str, ...]`: Names of operations with `status == OperationStatus.REQUESTED`.
- `prohibited_operations -> Tuple[str, ...]`: Names of operations with `status == OperationStatus.PROHIBITED`.
- `unresolved_references -> Tuple[SemanticReference, ...]`: All references where `not is_resolved`.
- `has_unresolved_references -> bool`: Quick boolean check for downstream Step 2 triggering.
- `has_ambiguities -> bool`: Quick boolean check for clarification or fallback handling.
- `to_dict() -> Dict[str, Any]`: Pure Python standard library serialization.
- `from_dict(data: Dict[str, Any]) -> DecodedRequest`: Clean reconstruction from dictionary.
- `intent -> Optional[str]`: Backward-compatibility property returning `goal.description`.

---

## 4. Supporting Value Objects & Enums

### Supporting Enums
1. **`IntentFamily`** (Descriptive only, non-routing):  
   `RETRIEVE`, `CREATE`, `MODIFY`, `COMMUNICATE`, `EXECUTE`, `ANALYZE`, `COMPARE`, `RESEARCH`, `NAVIGATE`, `CONVERSE`, `UNSPECIFIED`.
2. **`OperationStatus`**:  
   `REQUESTED`, `PROHIBITED`. (Crucial for differentiating positive intent from negative constraints).
3. **`ConfidenceLevel`**:  
   `HIGH`, `MEDIUM`, `LOW`, `UNCERTAIN`. (Provider-neutral).
4. **`ReferenceKind`**:  
   `PRONOUN`, `PREVIOUS_ACTION`, `DOCUMENT_OR_FILE`, `TEMPORAL_ORDINAL`, `OTHER`.
5. **`EntityCategory`**:  
   `PERSON`, `ROLE`, `ORGANIZATION`, `DOCUMENT`, `FILE`, `PROJECT`, `SERVICE`, `DATE`, `PLACE`, `OBJECT`, `OTHER`.
6. **`ContextDependencyCategory`**:  
   `SAME_SESSION_CONTEXT`, `PRIOR_SESSION_CONTEXT`, `ATTACHMENT_CONTEXT`, `PERSISTENT_KNOWLEDGE`, `EXTERNAL_INFORMATION`.
7. **`AmbiguityKind`**:  
   `UNRESOLVED_REFERENT`, `UNRESOLVED_ARTIFACT_TYPE`, `MULTIPLE_INTERPRETATIONS`, `MISSING_TARGET`, `VAGUE_SCOPE`, `OTHER`.

### Supporting Dataclasses (All `@dataclass(frozen=True)`)
- **`IntendedOutcome`**: `description: str`, `intent_family: IntentFamily`.
- **`SemanticOperation`**: `name: str`, `status: OperationStatus`, `target: Optional[str]`.
- **`ConstraintScope`**: `time_range`, `included_items`, `excluded_items`, `length_limit`, `prohibited_actions`, `source_restrictions`, `precision_requirements`, `language_constraints`, `draft_only`, `custom_constraints`.
- **`OutputPreferences`**: `artifact_type`, `structure`, `language`, `language_variant`, `tone`, `audience`, `length`, `detail_level`, `format`.
- **`MentionedEntity`**: `name: str`, `category: EntityCategory`, `qualifier: Optional[str]`.
- **`SemanticReference`**: `expression: str`, `kind: ReferenceKind`, `referent_hint: Optional[str]`, `is_resolved: bool = False`.
- **`TemporalReference`**: `expression: str`, `is_relative: bool`, `anchor_event: Optional[str]`.
- **`AttachmentReference`**: `identifier: Optional[str]`, `name: Optional[str]`, `mime_type: Optional[str]`, `reference_expression: Optional[str]`.
- **`ContextDependency`**: `description: str`, `category: ContextDependencyCategory`, `unresolved_reference: Optional[str]`.
- **`SemanticAmbiguity`**: `kind: AmbiguityKind`, `description: str`, `candidates: Tuple[str, ...]`.
- **`SemanticConfidence`**: Aspect-level confidences (`goal`, `operations`, `references`, `constraints`, `overall`).

---

## 5. `SemanticDecoder` Signature

Located in `uri_v1/turn/decoder.py`:

```python
@dataclass(frozen=True)
class DecodeInput:
    """Current turn input to the SemanticDecoder.

    Contains ONLY current-prompt material: raw text, attachment metadata,
    and current request metadata. Never contains session history, Graphify,
    prior turns, ARN, or tool data.
    """
    raw_text: str
    attachments: Tuple[AttachmentReference, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)


class SemanticDecoder(ABC):
    """Replaceable provider slot: raw user input -> DecodedRequest."""

    @abstractmethod
    def decode(self, input_data: Union[str, DecodeInput]) -> DecodedRequest:
        raise NotImplementedError
```

---

## 6. Semantic Precedence Rules

1. **Meaning outranks keywords:**  
   *"Don't send it, just draft the email."*  
   `draft` is requested; `send` is prohibited. The appearance of the word "send" never triggers send execution.
2. **Goal outranks verb frequency:**  
   *"Check these three bills and tell me whether usage is increasing."*  
   The goal is determining the consumption trend, not merely checking bills.
3. **Unresolved references remain unresolved:**  
   *"Do the same thing for them."*  
   Step 1 marks `"same thing"` and `"them"` as `is_resolved=False` with a `SAME_SESSION_CONTEXT` dependency. It never guesses or fabricates what they mean.
4. **Prompt-supplied context != persistent context:**  
   Step 1 only records facts explicitly stated in the current utterance. Context that must be looked up is recorded as a `ContextDependency`.
5. **Operation != capability / tool:**  
   Operations describe abstract linguistic actions (`convert`, `compare`, `draft`, `retrieve`). They carry zero tool or capability IDs.

---

## 7. Representative Semantic Examples (Verified by Tests)

### Example 1: "Convert this to PDF."
- `goal.description`: `"convert the referenced document to PDF"`
- `operations`: `[SemanticOperation(name="convert", status=OperationStatus.REQUESTED)]`
- `references`: `[SemanticReference(expression="this", kind=ReferenceKind.PRONOUN, is_resolved=False)]`
- `output_preferences`: `OutputPreferences(format="PDF")`
- `dependencies`: `[ContextDependency(description="unresolved reference 'this'...", category=SAME_SESSION_CONTEXT)]`

### Example 2: "Don't send it. Just draft the email."
- `goal.description`: `"create an email draft without sending"`
- `requested_operations`: `("draft",)`
- `prohibited_operations`: `("send",)`
- `constraints.prohibited_actions`: `("send",)`
- `constraints.draft_only`: `True`
- `output_preferences.artifact_type`: `"email"`

### Example 3: "Draft a short formal email in Indian English to the Chief Warden."
- `output_preferences.artifact_type`: `"email"`
- `output_preferences.tone`: `"formal"`
- `output_preferences.length`: `"short"`
- `output_preferences.language_variant`: `"Indian English"`
- `output_preferences.audience`: `"Chief Warden"`
- `entities`: `[MentionedEntity(name="Chief Warden", category=EntityCategory.ROLE)]`

### Example 4: "Do not summarize this; compare the exact figures in a table."
- `requested_operations`: `("compare",)`
- `prohibited_operations`: `("summarize",)`
- `constraints.precision_requirements`: `"exact figures"`
- `output_preferences.structure`: `"table"`

---

## 8. Test Execution & Verification

### Test Suite 1: `test_m35_uriv1_a1_decoded_request.py` (New)
15 comprehensive unit tests:
```
test_boundary_no_execution_or_graphify_or_arn_fields ... ok
test_enum_completeness ... ok
test_immutability ... ok
test_semantic_decoder_interface ... ok
test_serialization_round_trip ... ok
test_case_1_convert_this_to_pdf ... ok
test_case_2_bring_that_file_up ... ok
test_case_3_do_the_same_thing_for_them ... ok
test_case_4_dont_send_it_just_draft_the_email ... ok
test_case_5_find_previous_approval_compare_and_draft_revised_order ... ok
test_case_6_committee_changed_view_reconcile_for_tomorrow ... ok
test_case_7_compare_2025_and_2026_under_one_page ... ok
test_case_8_draft_short_formal_email_indian_english_chief_warden ... ok
test_case_9_do_not_summarize_compare_in_table ... ok
test_case_10_what_was_approved_yesterday ... ok

Ran 15 tests in 0.001s -- OK
```

### Test Suite 2: `test_m35_uriv1_a0_skeleton.py` (Regression)
All 7 baseline skeleton tests re-verified:
```
Ran 7 tests in 0.035s -- OK
```

### Combined Suite:
```
python -m unittest discover -p "test_m35_*.py"
Ran 22 tests in 0.012s -- OK
```

---

## 9. Fields Deliberately Excluded from Step 1

To preserve pure semantic decoding, the following fields were **strictly forbidden and excluded**:
1. `tool_id` / `capability_id` / `selected_tool` / `selected_capability`: Step 1 does not select tools.
2. `graphify_index` / `graph_store` / `sqlite_path`: Step 1 does not search the knowledge graph.
3. `arn_state` / `arn_engine`: Step 1 does not execute adaptive retrieval narrowing.
4. `provider_id` / `model_id` / `runtime_id`: Step 1 does not choose execution backends.
5. `tier_selection`: Step 1 does not decide between Edge, Local, or Extended intelligence.
6. `execution_plan` / `execution_status`: Step 1 does not plan or run actions.

---

## 10. Step-2 Requirements Exposed by the Contract

Batch A1's semantic representation clearly establishes the inputs required by Step 2 (Context Resolution):
1. **Referent Resolution Cascade:** Step 2 must inspect `DecodedRequest.references` and resolve them in priority order:
   - `Current input attachments` (`DecodedRequest.attachments`)
   - `Recent same-session turns` (`SAME_SESSION_CONTEXT`)
   - `Active session state` (active workflow, paused questions)
   - `Persistent Graphify context` (`PERSISTENT_KNOWLEDGE`)
   - `ARN` only if referents remain unresolved after cascading search.
2. **Constraint Enforcement:** Step 2 must pass `ConstraintScope` (e.g. `time_range`, `excluded_items`) to retrieval engines so searches don't over-fetch prohibited ranges.
3. **ContextPack Composition:** Step 2 binds resolved entities, files, and prior turn data to the `DecodedRequest` to form the `ContextPack`.

---

## 11. Open Questions for Batch A2 (Needle 3 Decoder Implementation)

1. **Needle 3 Prompt / Grammar Structure:**  
   Will Needle 3 emit JSON matching `DecodedRequest` directly, or will a lightweight adapter normalize Needle's output into the contract?
2. **Confidence Mapping:**  
   How should Needle's internal logit/probability scores be mapped to `ConfidenceLevel` (`HIGH`, `MEDIUM`, `LOW`, `UNCERTAIN`)?
3. **Heuristic Fast-Path:**  
   Should trivial conversational greetings (e.g. "hi", "hello") use a zero-latency heuristic decoder implementing `SemanticDecoder`, or should all messages traverse Needle 3?

---

## 12. Final Confirmations

1. **No Model, Retrieval, or Runtime Integration Added:**  
   `DecodedRequest` is pure dataclass contracts and interfaces. Zero models were initialized; no network requests were made; no database or file storage was touched.
2. **Original URI Prototype Untouched:**  
   `C:\Users\cheta\Development\uri-agent` was not modified, staged, committed, or pushed.
3. **No Git Actions Taken:**  
   No `git commit`, `git push`, `git merge`, or `git rebase` was executed. All changes remain clean in the working tree of `C:\Users\cheta\Development\Uri\_V1`.
