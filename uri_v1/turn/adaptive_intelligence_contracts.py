"""Adaptive Intelligence Architecture & Local-Brain Contracts (Batch A2.8).

Governing Principle:
    "URI defines URI. Models provide replaceable cognitive capacity."

This module defines model-independent contracts for:
1. URI Intelligence Ownership & Boundaries
2. Reference Anchor Resolution (RAR) Interface
3. Adaptive Relevance & Narrowing (ARN) Subsystem
4. Empirical BrainProfile Specification
5. Adaptive Decomposition & Safety Invariants
6. Deterministic Semantic Merge Contract
7. Local Brain vs. Main Brain Authority Boundaries
8. Operation Lifecycle & Bound Semantic Operations (resolving temporal/deferred states)

All contracts are strictly provider-agnostic and parameter-count independent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


# ===========================================================================
# 1. URI Intelligence Ownership & Tiers
# ===========================================================================

class IntelligenceTier(str, Enum):
    """Architectural tiers of cognitive execution in URI."""

    DETERMINISTIC_CORE = "DETERMINISTIC_CORE"  # Code, state machines, authority gates, RAR
    LOCAL_BRAIN = "LOCAL_BRAIN"                # Fast, resident, bounded semantic worker
    MAIN_BRAIN = "MAIN_BRAIN"                  # Deep reasoning, broad synthesis, workflow planning
    EXTERNAL_SPECIALIST = "EXTERNAL_SPECIALIST"# Specialized external models/tools (multimodal, etc.)


class AuthorityAction(str, Enum):
    """Actions with authoritative impact on user data or system state."""

    READ_OBSERVE = "READ_OBSERVE"              # Non-mutating observation
    DECODE_INTERPRET = "DECODE_INTERPRET"      # Semantic decoding into structured representations
    PROPOSE_PLAN = "PROPOSE_PLAN"              # Drafting an execution plan or workflow
    MODIFY_LOCAL_STATE = "MODIFY_LOCAL_STATE"  # Mutating session working memory
    EXECUTE_CAPABILITY = "EXECUTE_CAPABILITY"  # Calling external or system tools
    AUTHORIZE_GATE = "AUTHORIZE_GATE"          # Bypassing or satisfying an approval gate
    OVERRIDE_POLICY = "OVERRIDE_POLICY"        # Changing safety boundaries or system policy


# ===========================================================================
# 2. Reference Anchor Resolution (RAR) Contract
# ===========================================================================

class RAROutcome(str, Enum):
    """Tri-state outcome for Reference Anchor Resolution."""

    RESOLVED = "RESOLVED"                      # Exactly one candidate uniquely bound with evidence
    AMBIGUOUS = "AMBIGUOUS"                    # Multiple candidates equally plausible; user or ARN narrowing needed
    UNRESOLVED_REFERENCE = "UNRESOLVED_REFERENCE"  # No matching candidate found in known working set


class RARBasis(str, Enum):
    """Basis upon which reference anchor resolution was made."""

    DETERMINISTIC_ANCHOR = "DETERMINISTIC_ANCHOR"  # Exact title, active UI selection, attachment ID
    LOCAL_DISCRIMINATION = "LOCAL_DISCRIMINATION"  # Model-assisted discrimination between bounded candidates


@dataclass(frozen=True)
class RARContract:
    """Invariants governing Reference Anchor Resolution."""

    # Rule 1: Zero candidate invention.
    # Resolved candidate ID MUST strictly belong to the supplied candidate pool.
    # Ambiguity candidate IDs MUST strictly belong to the supplied candidate pool.
    anti_invention_gate_enforced: bool = True

    # Rule 2: Non-guessing on absence.
    # If evidence is insufficient, RAR MUST emit UNRESOLVED_REFERENCE rather than guess.
    allow_speculative_guessing: bool = False

    # Rule 3: Deterministic precedence.
    # Deterministic anchors (exact ID, current attachment, active UI) strictly outrank model inference.
    deterministic_precedence: bool = True


# ===========================================================================
# 3. Operation Lifecycle & Bound Semantic Operations (Issue 1 & 2 Resolution)
# ===========================================================================

class OperationLifecycle(str, Enum):
    """Semantic status of an operation, distinguishing immediate from deferred/conditional."""

    REQUESTED = "requested"        # Immediate positive execution requested
    PROHIBITED = "prohibited"      # Explicitly forbidden / negative constraint
    DEFERRED = "deferred"          # Intended operation whose execution is temporally delayed
    CONDITIONAL = "conditional"    # Gated by a dynamic contingency or prerequisite condition
    UNSPECIFIED = "unspecified"


@dataclass(frozen=True)
class BoundSemanticOperation:
    """An operation explicitly bound to its direct target and temporal/contingent lifecycle.

    Solves TORT-10 (deferred timing) and TORT-11 (disjoint targets):
    - Decoupling verbs from targets in multi-target turns causes polarity confusion.
    - Forcing deferred operations into binary requested/prohibited causes semantic corruption.
    """

    verb: str
    target_expression: Optional[str] = None
    target_id: Optional[str] = None
    lifecycle: OperationLifecycle = OperationLifecycle.REQUESTED
    temporal_constraint: Optional[str] = None  # e.g. "not_before(tomorrow at 10am)", "after Monday"
    contingency_predicate: Optional[str] = None  # e.g. "unless critical errors occur", "if confirmed"
    confidence: float = 1.0


# ===========================================================================
# 4. Empirical BrainProfile Specification
# ===========================================================================

class ConfidenceCalibration(str, Enum):
    """Empirical reliability of a model's self-reported certainty."""

    OVERCONFIDENT = "OVERCONFIDENT"  # Hallucinates certainty on unknown/ambiguous inputs
    WELL_CALIBRATED = "WELL_CALIBRATED" # Low confidence correlates with ambiguous inputs
    UNRELIABLE = "UNRELIABLE"        # Emits arbitrary confidence scores


@dataclass(frozen=True)
class BrainProfile:
    """Provider- and model-independent empirical capability profile.

    Represents measured cognitive capacity rather than parameter count.
    A model is qualified against URI's contracts by producing a validated BrainProfile.
    """

    profile_id: str                          # e.g. "qwen3.5-9b-q4km-rx7900gre"
    provider_type: str                       # e.g. "local_gguf", "llama_cpp", "vllm"
    model_family: str                        # e.g. "qwen35", "gemma", "lfm"

    # Measured cognitive capacities (empirically qualified)
    max_context_tolerance_tokens: int       # Maximum prompt tokens before extraction degradation
    max_retained_operations: int            # Maximum number of operations retained without verb omission
    contrastive_negation_preservation_pct: float  # Measured % preservation of contrastive polarity (gate: >=95%)
    supports_nested_conditionals: bool      # Can reliably parse "X unless Y except when Z"
    supports_disjoint_multi_targets: bool   # Can parse "Sign A but shred B" without polarity corruption

    # Architectural preferences
    preferred_feed_width: str                # "atomic_narrow", "composite_residual", "broad"
    max_safe_concurrent_slots: int           # Maximum concurrent execution slots before scheduling stall

    # Latency & resource envelope (measured on target hardware)
    typical_feed_latency_ms: float           # Measured mean latency for atomic feed
    p95_feed_latency_ms: float               # Measured 95th percentile latency
    vram_footprint_mb: float                 # Measured base model VRAM usage
    kv_cache_per_slot_mb: float              # Measured KV cache allocation per concurrent slot
    host_ram_overhead_mb: float              # Measured host RAM footprint

    # Safety & Reliability metrics
    false_safe_acceptance_rate_pct: float    # Measured rate of falsely accepting un-executable/ambiguous turns (gate: <=2.0%)
    calibration: ConfidenceCalibration = ConfidenceCalibration.WELL_CALIBRATED
    qualification_verdict: str = "PENDING"
    qualification_timestamp: str = ""

    @property
    def is_local_brain_qualified(self) -> bool:
        """Evaluates whether the profile satisfies the minimal Local Brain safety gates."""
        return (
            self.contrastive_negation_preservation_pct >= 95.0
            and self.max_retained_operations >= 3
            and self.false_safe_acceptance_rate_pct <= 2.0
            and self.qualification_verdict == "QUALIFIED"
        )


# ===========================================================================
# 5. Adaptive Relevance & Narrowing (ARN) Subsystem Contract
# ===========================================================================

class FeedDimension(str, Enum):
    """Semantic dimensions extracted by narrow feeds."""

    GOAL_INTENT = "GOAL_INTENT"              # High-level outcome and intent family
    OPERATIONS_POLARITY = "OPERATIONS_POLARITY" # Verbs, positive vs negative polarity
    CONSTRAINTS_PREFERENCES = "CONSTRAINTS_PREFERENCES" # Formats, limits, style, temporal conditions
    RELATIONAL_BINDING = "RELATIONAL_BINDING"# Mapping operations to specific target candidates
    DEFERRED_LIFECYCLE = "DEFERRED_LIFECYCLE"# Temporal scheduling and gating conditions


class FeedExecutionTopology(str, Enum):
    """Topology for executing semantic feeds."""

    DIRECT_BOUNDED = "DIRECT_BOUNDED"        # Single focused prompt (sufficient for simple turns)
    CONCURRENT_INDEPENDENT = "CONCURRENT_INDEPENDENT" # Multiple independent narrow feeds run in parallel
    SERIAL_PIPELINED = "SERIAL_PIPELINED"    # Feed 2 depends on output of Feed 1
    ESCALATE_TO_MAIN_BRAIN = "ESCALATE_TO_MAIN_BRAIN" # Turn cannot be safely decomposed; dispatch to Main Brain


@dataclass(frozen=True)
class SemanticFeedSpec:
    """Specification of a single narrow semantic feed."""

    feed_id: str
    dimension: FeedDimension
    prompt_template_key: str
    input_text_slice: str
    bound_anchors: Tuple[str, ...] = ()
    expected_output_schema: str = "json"
    timeout_ms: float = 2000.0


@dataclass(frozen=True)
class SemanticFeedPlan:
    """Output of the ARN subsystem: how to decode the current turn."""

    topology: FeedExecutionTopology
    feeds: Tuple[SemanticFeedSpec, ...] = ()
    concurrency_limit: int = 2
    rationale: str = ""
    escalation_reason: Optional[str] = None

    @property
    def requires_escalation(self) -> bool:
        return self.topology == FeedExecutionTopology.ESCALATE_TO_MAIN_BRAIN


# ===========================================================================
# 6. Adaptive Decomposition & Safety Invariants
# ===========================================================================

class DecompositionSafety(str, Enum):
    """Assessment of whether a turn can be safely split into independent feeds."""

    SAFE = "SAFE"
    UNSAFE_TIGHTLY_COUPLED = "UNSAFE_TIGHTLY_COUPLED"
    UNSAFE_NESTED_POLARITY = "UNSAFE_NESTED_POLARITY"
    UNSAFE_DISJOINT_TARGETS = "UNSAFE_DISJOINT_TARGETS"
    UNSAFE_EXCEEDS_PROFILE = "UNSAFE_EXCEEDS_PROFILE"


@dataclass(frozen=True)
class DecompositionSafetyAssessment:
    """Result of evaluating whether decomposition is safe for the active BrainProfile."""

    verdict: DecompositionSafety
    explanation: str
    must_escalate: bool

    @property
    def is_safe(self) -> bool:
        return self.verdict == DecompositionSafety.SAFE


# ===========================================================================
# 7. Deterministic Semantic Merger Contract
# ===========================================================================

class MergeStatus(str, Enum):
    """Status of merging narrow feed outputs into a canonical DecodedRequest."""

    MERGED_SUCCESS = "MERGED_SUCCESS"
    AMBIGUITY_DETECTED = "AMBIGUITY_DETECTED"
    UNRESOLVABLE_CONFLICT = "UNRESOLVABLE_CONFLICT"


@dataclass(frozen=True)
class MergeResult:
    """Result of deterministic feed merging.

    Governing rule:
        Merger must NEVER invent semantics to reconcile conflicting feeds.
        If feeds irreconcilably conflict, the merger MUST report UNRESOLVABLE_CONFLICT
        and trigger escalation to Main Brain.
    """

    status: MergeStatus
    operations: Tuple[BoundSemanticOperation, ...] = ()
    unresolved_conflicts: Tuple[str, ...] = ()
    requires_main_brain_escalation: bool = False
    rationale: str = ""


# ===========================================================================
# 8. Local Brain Authority Contract (Can Do / Must Escalate / Never Authorize)
# ===========================================================================

@dataclass(frozen=True)
class LocalBrainContract:
    """Formal authority boundaries for any model acting as a Local Brain.

    CORE INVARIANT:
        Correct escalation counts as a successful execution!
        A Local Brain is never required or expected to guess on turns outside its envelope.
    """

    # 1. CAN DO: Fast, bounded semantic extraction
    can_classify_simple_intent: bool = True
    can_extract_atomic_operations: bool = True
    can_extract_explicit_constraints: bool = True
    can_discriminate_between_bounded_rar_candidates: bool = True
    can_format_structured_json_schema: bool = True

    # 2. MUST ESCALATE: Outside safe boundary
    must_escalate_unresolved_references: bool = True
    must_escalate_nested_conditionals: bool = True
    must_escalate_cross_target_contrasting_operations: bool = True
    must_escalate_unresolvable_feed_conflicts: bool = True
    must_escalate_unseen_domain_ambiguity: bool = True

    # 3. MUST NEVER AUTHORIZE: Safety & Authority Invariants
    never_authorizes_capability_execution: bool = True
    never_bypasses_approval_gates: bool = True
    never_modifies_security_policy: bool = True
    never_invents_candidate_identities: bool = True
    never_overrides_deterministic_rar_anchors: bool = True
