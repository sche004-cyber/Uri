# M35 — URIv1 Parallel Architecture
## Batch A1.1 Completion Report: `DecodedRequest` Contract Hardening

**Status:** COMPLETE & ACCEPTED  
**Date:** 2026-09-21  
**Batch:** A1.1 (Step 1 Semantic Contract Hardening)  
**Worktree:** `C:\Users\cheta\Development\Uri\_V1`  
**Branch:** `m35-uri-v1-parallel-architecture`  
**Baseline HEAD:** `e8e3b65259c45fc823addc3ef8969425a265bd1b`  
**Original Prototype Worktree:** `C:\Users\cheta\Development\uri-agent` (PROTECTED — 100% UNTOUCHED)

---

## 1. Executive Summary

Batch A1.1 implements three targeted architectural corrections to the Step 1 `DecodedRequest` semantic contract prior to Batch A2 (Needle 3 integration):
1. **Removed mutable dictionary structures** from frozen semantic dataclasses (`DecodedRequest` and `DecodeInput`), establishing true, deep immutability.
2. **Eliminated premature storage-tier assumptions** in `ContextDependencyCategory`. Step 1 now expresses *that* context is required without prematurely dictating whether Step 2 satisfies it from the current session, prior sessions, Graphify, or external sources.
3. **Unified `SemanticDecoder` into a canonical single-input interface** accepting `DecodeInput` strictly, supported by a clean convenience constructor `DecodeInput.from_text()`.

---

## 2. Files Changed & Added

All modifications occurred strictly inside `C:\Users\cheta\Development\Uri\_V1`:

| File | Status | Description |
| :--- | :--- | :--- |
| `uri_v1/turn/contracts.py` | MODIFIED | Removed `metadata: Dict[str, Any]` from `DecodedRequest`; refined `ContextDependencyCategory` to Step-2-neutral categories (`CONTEXT_REQUIRED`, `PRIOR_CONTEXT_UNSPECIFIED`, `CURRENT_ATTACHMENT`, `EXTERNAL_INFORMATION`); updated serialization methods. |
| `uri_v1/turn/decoder.py` | MODIFIED | Removed `metadata` from `DecodeInput`; added `DecodeInput.from_text()` constructor; simplified `SemanticDecoder.decode` signature to strictly accept `DecodeInput`. |
| `test_m35_uriv1_a1_decoded_request.py` | MODIFIED | Updated existing 15 unit tests to align with refined dependency categories, strict `DecodeInput` interface, and metadata-free serialization. |
| `test_m35_uriv1_a1_1_contract_hardening.py` | NEW | 8 dedicated unit tests specifically verifying deep immutability, context-dependency neutrality, and canonical decoder signature. |
| `docs/plans/M35_URIV1_A1_1_CONTRACT_HARDENING_REPORT.md` | NEW | This architectural hardening report. |

---

## 3. Previous Contract Issues & Exact Hardening Changes

### A. Frozen-Dataclass Mutability Issue
- **Previous Issue:** `DecodedRequest` and `DecodeInput` contained `metadata: Dict[str, Any] = field(default_factory=dict)`. Because Python dictionaries are mutable references, a "frozen" dataclass could still have its internal dictionary mutated at runtime (`req.metadata["foo"] = "bar"`), compromising contract immutability.
- **Exact Hardening Change:** Selected **Option A (Complete Removal)**. All Step 1 semantic needs are already modeled by explicit, typed attributes (`goal`, `operations`, `constraints`, `output_preferences`, `entities`, `references`, `temporal_references`, `attachments`, `dependencies`, `ambiguities`, `confidence`). `metadata` was removed entirely from `DecodedRequest` and `DecodeInput`. Every field is now an immutable scalar, frozen dataclass, or tuple of frozen dataclasses.

### B. Context-Dependency Storage Prematurity
- **Previous Issue:** `ContextDependencyCategory` previously defined `SAME_SESSION_CONTEXT`, `PRIOR_SESSION_CONTEXT`, `ATTACHMENT_CONTEXT`, and `PERSISTENT_KNOWLEDGE`. Defaulting unresolved references like *"that file"* or *"them"* to `SAME_SESSION_CONTEXT` forced Step 1 to make an unverified assertion about *where* the context lives.
- **Exact Hardening Change:** Refined `ContextDependencyCategory` to represent semantic need rather than storage location:
  - `CONTEXT_REQUIRED`: General requirement for context resolution (e.g. *"Bring that file up"* -> context is needed; Step 2 determines whether it's in the current session, history, or elsewhere).
  - `PRIOR_CONTEXT_UNSPECIFIED`: Linguistic reference to past events/actions/decisions (e.g. *"Do the same thing"*, *"What was approved yesterday"*) without presuming whether it resides in session history, cross-session records, or Graphify.
  - `CURRENT_ATTACHMENT`: Explicitly supplied or referenced in current-turn attachments (e.g. *"Use the attached spreadsheet"*).
  - `EXTERNAL_INFORMATION`: Explicitly refers to external facts outside the workspace.

### C. Polymorphic `SemanticDecoder` Input Signature
- **Previous Issue:** `SemanticDecoder.decode` accepted `Union[str, DecodeInput]`. Having union types on abstract provider interfaces introduces branching and inconsistent calling conventions across implementations.
- **Exact Hardening Change:** Unified the interface into one canonical signature:
  ```python
  class SemanticDecoder(ABC):
      @abstractmethod
      def decode(self, input_data: DecodeInput) -> DecodedRequest:
          raise NotImplementedError
  ```
  Added a convenience classmethod `DecodeInput.from_text(raw_text: str, attachments: Tuple[AttachmentReference, ...] = ()) -> DecodeInput` on the input object itself.

---

## 4. Final Metadata Strategy

Step 1 is strictly semantic, inspectable, and strongly typed. No generic `metadata: Dict[str, Any]` is present on `DecodedRequest` or `DecodeInput`.
- If request-level tracing or transport tags are needed by server or infrastructure layers in future batches, they will reside in the request envelope or Step 2 `ContextPack`, never contaminating the pure semantic contract.
- Serialized representations (`to_dict()`) contain only explicit, typed semantic keys.

---

## 5. Final Context-Dependency Strategy

```python
class ContextDependencyCategory(str, Enum):
    """Categories of contextual dependencies identified at Step 1.

    Step 1 expresses THAT context is needed without prematurely choosing
    how or from where Step 2 should resolve it (current session, prior session,
    Graphify, or external).
    """
    CONTEXT_REQUIRED = "context_required"            # General unresolved context requirement
    PRIOR_CONTEXT_UNSPECIFIED = "prior_context_unspecified"  # Reference to prior events/actions (unspecified source)
    CURRENT_ATTACHMENT = "current_attachment"        # Explicitly present or referenced in current turn attachments
    EXTERNAL_INFORMATION = "external_information"    # Explicitly refers to external facts/sources outside user workspace
```

- **Example 1:** User: *"Bring that file up."*  
  `dependency: ContextDependency(category=ContextDependencyCategory.CONTEXT_REQUIRED, unresolved_reference="that file")`.  
  Step 1 flags that a file referent needs context. Step 2 searches current attachments, recent session turns, and persistent state in prioritized order.
- **Example 2:** User: *"What was approved yesterday?"*  
  `dependency: ContextDependency(category=ContextDependencyCategory.PRIOR_CONTEXT_UNSPECIFIED, unresolved_reference="what was approved yesterday")`.  
  No premature assumption is made that yesterday's approvals exist in the current session vs. Graphify vs. Drive.
- **Example 3:** User: *"Use the attached spreadsheet."*  
  `dependency: ContextDependency(category=ContextDependencyCategory.CURRENT_ATTACHMENT, unresolved_reference="attached spreadsheet")`.  
  Permissible because the prompt explicitly cites an attachment provided in the current turn.

---

## 6. Final `SemanticDecoder` & `DecodeInput` Specification

```python
@dataclass(frozen=True)
class DecodeInput:
    """Current turn input to the SemanticDecoder.

    Contains ONLY current-prompt material: raw text and current attachment
    metadata. Never contains session history, Graphify, prior turns, ARN,
    or tool data. Genuinely frozen and immutable (no mutable dict/list).
    """
    raw_text: str
    attachments: Tuple[AttachmentReference, ...] = ()

    @classmethod
    def from_text(
        cls,
        raw_text: str,
        attachments: Tuple[AttachmentReference, ...] = (),
    ) -> DecodeInput:
        """Convenience constructor from plain text and optional attachments."""
        return cls(raw_text=raw_text, attachments=attachments)


class SemanticDecoder(ABC):
    """Replaceable provider slot: DecodeInput -> DecodedRequest."""

    @abstractmethod
    def decode(self, input_data: DecodeInput) -> DecodedRequest:
        raise NotImplementedError
```

---

## 7. Test Execution & Verification

### Test Suite 1: `test_m35_uriv1_a1_1_contract_hardening.py` (New)
8 dedicated tests specifically proving the A1.1 hardening corrections:
```
test_decoder_strictly_requires_decode_input ... ok
test_all_dependency_categories_are_step2_neutral ... ok
test_bring_that_file_up_does_not_assert_same_session ... ok
test_use_attached_spreadsheet_is_current_attachment ... ok
test_what_was_approved_yesterday_is_prior_context_unspecified ... ok
test_decode_input_is_genuinely_immutable ... ok
test_decoded_request_contains_no_mutable_containers ... ok
test_serialization_produces_no_generic_metadata_key ... ok

Ran 8 tests in 0.001s -- OK
```

### Test Suite 2: `test_m35_uriv1_a1_decoded_request.py` (Updated)
All 15 semantic cases and contract integrity tests re-verified:
```
Ran 15 tests in 0.001s -- OK
```

### Test Suite 3: `test_m35_uriv1_a0_skeleton.py` (Baseline Regression)
All 7 baseline skeleton tests re-verified:
```
Ran 7 tests in 0.035s -- OK
```

### Full Discovery Run:
```
python -m unittest discover -p "test_m35_*.py"
Ran 30 tests in 0.014s -- OK
```

---

## 8. Confirmations & Scope Boundaries

1. **No Step-2 Logic Introduced:**  
   Step 1 exclusively describes what the user means. No reference resolution algorithms, session history queries, Graphify lookups, or ARN invocations were implemented.
2. **No Model, Runtime, or Third-Party Integration Added:**  
   Pure standard-library Python dataclasses and abstract interfaces. Zero network calls, zero model weights initialized.
3. **Downstream Contracts Preserved:**  
   `ContextPack`, `EdgeOutcome`, `IntelligenceResult`, and `FinalizedTurn` remain untouched from Batch A0.
4. **Original URI Prototype Untouched:**  
   `C:\Users\cheta\Development\uri-agent` was verified with `git status` and is **100% UNTOUCHED**.
5. **No Git Actions Taken:**  
   No commit, push, merge, or rebase was executed. All changes reside cleanly in the working tree of `C:\Users\cheta\Development\Uri\_V1`.
