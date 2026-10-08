"""Live Empirical Comparative Qualification Probe for Batch A2.4R:

Architecture-Aligned Semantic Decoder Re-evaluation: Needle 3 vs Qwen3-14B.

Executes the mandatory 2x2 ablation matrix:
  - Mode A: Raw user turn
  - Mode B: Raw + TurnFrame
  - Mode C: Raw + ActiveContext (no TurnFrame)
  - Mode D: Raw + TurnFrame + ActiveContext

Across:
  - 18 Standard Prompts (R1..R10, S1..S8)
  - 6 Exact Restored Conversational Cases (C1..C6)
  - 9 Architecture-Specific Cases (T1..T9: Unresolved honesty, Ambiguity preservation,
    Single-candidate grounding, Irrelevant-context, Stale-context, Negation polarity,
    Multi-operation binding, Step-2 handoff, Current attachment grounding)

Saves full raw telemetry, tokens, RAM, and architecture-aligned scores to
scripts/a2_4r_comparative_results.json.
"""

from __future__ import annotations

from enum import Enum
import json
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from uri_v1.turn.active_context import ActiveContext, ArtifactDescriptor, EntityDescriptor
from uri_v1.turn.contracts import (
    AttachmentReference,
    ConfidenceLevel,
    DecodedRequest,
    IntentFamily,
    OperationStatus,
    ReferenceKind,
)
from uri_v1.turn.decoder import DecodeInput
from uri_v1.turn.needle_decoder import NeedleBridgeTransport, default_venv_python
from uri_v1.turn.needle_single_pass import NeedleSinglePassDecoder, NeedleSinglePassResult
from uri_v1.turn.qwen_decoder import QwenLocalTransport
from uri_v1.turn.qwen_semantic_decoder import (
    DecoderMode,
    Qwen14BDecodeResult,
    Qwen14BSemanticDecoder,
)
from uri_v1.turn.turn_frame_builder import build_turn_frame


class ContextCategory(str, Enum):
    SELF_CONTAINED = "SELF_CONTAINED"
    CURRENT_TURN_CONTEXT = "CURRENT_TURN_CONTEXT"
    ACTIVE_CONTEXT_REQUIRED = "ACTIVE_CONTEXT_REQUIRED"
    STEP2_CONTEXT_REQUIRED = "STEP2_CONTEXT_REQUIRED"
    AMBIGUOUS = "AMBIGUOUS"


# ---------------------------------------------------------------------------
# Corpus 1: Standard 18 Prompts (R1..R10, S1..S8)
# ---------------------------------------------------------------------------

STANDARD_CASES: List[Dict[str, Any]] = [
    {
        "id": "R1",
        "text": "Convert this to PDF.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "expected_goal_keywords": ["convert", "pdf"],
        "expected_intent": "modify",
        "expected_requested_ops": ["convert"],
        "expected_prohibited_ops": [],
        "expected_references": ["this"],
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "R2",
        "text": "Bring that file up.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "expected_goal_keywords": ["bring", "open", "file", "display", "retrieve"],
        "expected_intent": "retrieve",
        "expected_requested_ops": ["bring", "open", "display", "retrieve"],
        "expected_prohibited_ops": [],
        "expected_references": ["that file"],
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "R3",
        "text": "Do the same thing for them.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "expected_goal_keywords": ["same", "thing", "repeat", "apply", "do"],
        "expected_intent": "execute",
        "expected_requested_ops": ["do", "repeat", "apply", "execute"],
        "expected_prohibited_ops": [],
        "expected_references": ["same thing", "them"],
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "R4",
        "text": "Don't send it. Just draft the email.",
        "category": ContextCategory.SELF_CONTAINED.value,
        "expected_goal_keywords": ["draft", "email"],
        "expected_intent": "create",
        "expected_requested_ops": ["draft"],
        "expected_prohibited_ops": ["send"],
        "expected_references": ["it"],
        "has_negation": True,
        "has_context": False,
    },
    {
        "id": "R5",
        "text": "Find the previous approval, compare it with this one and draft a revised order.",
        "category": ContextCategory.STEP2_CONTEXT_REQUIRED.value,
        "expected_goal_keywords": ["compare", "draft", "order", "approval", "find"],
        "expected_intent": "create",
        "expected_requested_ops": ["find", "compare", "draft"],
        "expected_prohibited_ops": [],
        "expected_references": ["previous approval", "it", "this one"],
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "R6",
        "text": (
            "The committee has already changed its view twice and the latest letter doesn't "
            "seem to match what was decided earlier. I need something I can put up tomorrow."
        ),
        "category": ContextCategory.STEP2_CONTEXT_REQUIRED.value,
        "expected_goal_keywords": ["letter", "put up", "prepare", "draft", "compare", "something"],
        "expected_intent": "create",
        "expected_requested_ops": ["put up", "prepare", "draft", "create"],
        "expected_prohibited_ops": [],
        "expected_references": ["latest letter", "what was decided earlier", "something"],
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "R7",
        "text": "Compare only the 2025 and 2026 decisions, do not use anything before 2025, and keep the result under one page.",
        "category": ContextCategory.STEP2_CONTEXT_REQUIRED.value,
        "expected_goal_keywords": ["compare", "decisions"],
        "expected_intent": "compare",
        "expected_requested_ops": ["compare"],
        "expected_prohibited_ops": ["use anything before 2025", "use"],
        "expected_references": [],
        "has_negation": True,
        "has_context": False,
    },
    {
        "id": "R8",
        "text": "Draft a short formal email in Indian English to the Chief Warden.",
        "category": ContextCategory.SELF_CONTAINED.value,
        "expected_goal_keywords": ["draft", "email", "chief warden"],
        "expected_intent": "create",
        "expected_requested_ops": ["draft"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "R9",
        "text": "Do not summarize this; compare the exact figures in a table.",
        "category": ContextCategory.SELF_CONTAINED.value,
        "expected_goal_keywords": ["compare", "figures", "table"],
        "expected_intent": "compare",
        "expected_requested_ops": ["compare"],
        "expected_prohibited_ops": ["summarize"],
        "expected_references": ["this"],
        "has_negation": True,
        "has_context": False,
    },
    {
        "id": "R10",
        "text": "What was approved yesterday?",
        "category": ContextCategory.STEP2_CONTEXT_REQUIRED.value,
        "expected_goal_keywords": ["approved", "yesterday", "what", "determine"],
        "expected_intent": "retrieve",
        "expected_requested_ops": ["retrieve", "find", "query", "check"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "S1",
        "text": "Hello",
        "category": ContextCategory.SELF_CONTAINED.value,
        "expected_goal_keywords": ["hello", "greet", "greeting"],
        "expected_intent": "unspecified",
        "expected_requested_ops": [],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "S2",
        "text": "Thanks",
        "category": ContextCategory.SELF_CONTAINED.value,
        "expected_goal_keywords": ["thanks", "thank", "acknowledge"],
        "expected_intent": "unspecified",
        "expected_requested_ops": [],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "S3",
        "text": "Open calculator.",
        "category": ContextCategory.SELF_CONTAINED.value,
        "expected_goal_keywords": ["calculator", "open", "launch"],
        "expected_intent": "retrieve",
        "expected_requested_ops": ["open"],
        "expected_prohibited_ops": [],
        "expected_references": [],
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "S4",
        "text": "Don't open it yet.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "expected_goal_keywords": ["open", "wait", "hold", "do not open"],
        "expected_intent": "unspecified",
        "expected_requested_ops": [],
        "expected_prohibited_ops": ["open"],
        "expected_references": ["it"],
        "has_negation": True,
        "has_context": False,
    },
    {
        "id": "S5",
        "text": "Send it to him after they approve it.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "expected_goal_keywords": ["send", "approve"],
        "expected_intent": "execute",
        "expected_requested_ops": ["send"],
        "expected_prohibited_ops": [],
        "expected_references": ["it", "him", "they"],
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "S6",
        "text": "Compare the attached PDF with this spreadsheet.",
        "category": ContextCategory.CURRENT_TURN_CONTEXT.value,
        "expected_goal_keywords": ["compare", "pdf", "spreadsheet"],
        "expected_intent": "compare",
        "expected_requested_ops": ["compare"],
        "expected_prohibited_ops": [],
        "expected_references": ["attached PDF", "this spreadsheet"],
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "S7",
        "text": "Make something I can submit tomorrow.",
        "category": ContextCategory.SELF_CONTAINED.value,
        "expected_goal_keywords": ["make", "submit", "prepare", "create", "document"],
        "expected_intent": "create",
        "expected_requested_ops": ["make", "create", "prepare", "draft"],
        "expected_prohibited_ops": [],
        "expected_references": ["something"],
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "S8",
        "text": "No, I meant the earlier one.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "expected_goal_keywords": ["earlier", "correct", "select", "refer"],
        "expected_intent": "retrieve",
        "expected_requested_ops": ["select", "retrieve", "refer"],
        "expected_prohibited_ops": [],
        "expected_references": ["earlier one"],
        "has_negation": False,
        "has_context": False,
    },
]

# ---------------------------------------------------------------------------
# Corpus 2: Exact Restored Conversational Cases (C1..C6)
# ---------------------------------------------------------------------------

CONVERSATIONAL_CASES: List[Dict[str, Any]] = [
    {
        "id": "C1",
        "text": "Bring that file up.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Hostel_Order_21Sep.docx", artifact_type="document"),
            )
        ),
        "target_ref": "that file",
        "expected_target_id": "x1",
        "expected_resolved_name": "Hostel_Order_21Sep.docx",
        "expected_goal_keywords": ["bring", "open", "file", "display", "retrieve"],
        "expected_requested_ops": ["bring", "open", "display", "retrieve"],
        "expected_prohibited_ops": [],
        "has_negation": False,
        "has_context": True,
    },
    {
        "id": "C2",
        "text": "Do the same thing for them.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "context": ActiveContext(
            active_entities=(
                EntityDescriptor(id="e1", name="OH-1 first-year students", category="group"),
            ),
            prior_semantic_operation="draft formal email",
        ),
        "target_ref": "them",
        "expected_target_id": "e1",
        "expected_resolved_name": "OH-1 first-year students",
        "expected_goal_keywords": ["same thing", "draft", "email", "do"],
        "expected_requested_ops": ["draft", "draft formal email", "do", "repeat"],
        "expected_prohibited_ops": [],
        "has_negation": False,
        "has_context": True,
    },
    {
        "id": "C3",
        "text": "No, I meant the earlier one.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Approval_2025.pdf", artifact_type="document"),
                ArtifactDescriptor(id="x2", name="Approval_2026.pdf", artifact_type="document"),
            ),
            recent_relevant_turns=("x2",),
        ),
        "target_ref": "earlier one",
        "expected_target_id": "x1",
        "expected_resolved_name": "Approval_2025.pdf",
        "expected_goal_keywords": ["earlier", "approval", "select", "correct"],
        "expected_requested_ops": ["select", "retrieve", "refer"],
        "expected_prohibited_ops": [],
        "has_negation": False,
        "has_context": True,
    },
    {
        "id": "C4",
        "text": "Use the one we just created.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Revised_Hostel_Order.docx", artifact_type="document"),
            )
        ),
        "target_ref": "the one we just created",
        "expected_target_id": "x1",
        "expected_resolved_name": "Revised_Hostel_Order.docx",
        "expected_goal_keywords": ["use", "order", "created"],
        "expected_requested_ops": ["use"],
        "expected_prohibited_ops": [],
        "has_negation": False,
        "has_context": True,
    },
    {
        "id": "C5",
        "text": "Make that shorter.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Draft_Email_Chief_Warden", artifact_type="draft"),
            )
        ),
        "target_ref": "that",
        "expected_target_id": "x1",
        "expected_resolved_name": "Draft_Email_Chief_Warden",
        "expected_goal_keywords": ["shorter", "shorten", "summarize", "revise", "make"],
        "expected_requested_ops": ["shorten", "revise", "modify", "summarize"],
        "expected_prohibited_ops": [],
        "has_negation": False,
        "has_context": True,
    },
    {
        "id": "C6",
        "text": "Send the same version to him.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Hostel_Timing_Email", artifact_type="email"),
            ),
            active_entities=(
                EntityDescriptor(id="e1", name="Chief Warden", category="person"),
            ),
        ),
        "target_ref": "same version",
        "expected_target_id": "x1",
        "expected_resolved_name": "Hostel_Timing_Email",
        "expected_goal_keywords": ["send", "email", "chief warden"],
        "expected_requested_ops": ["send"],
        "expected_prohibited_ops": [],
        "has_negation": False,
        "has_context": True,
    },
]

# ---------------------------------------------------------------------------
# Corpus 3: Architecture-Specific Test Cases (T1..T9)
# ---------------------------------------------------------------------------

ARCHITECTURE_CASES: List[Dict[str, Any]] = [
    {
        "id": "T1",
        "name": "Unresolved honesty",
        "text": "Send it to her.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "context": None,
        "expected_goal_keywords": ["send"],
        "expected_requested_ops": ["send"],
        "expected_prohibited_ops": [],
        "expected_references": ["it", "her"],
        "must_be_unresolved": True,
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "T2",
        "name": "Single-candidate grounding",
        "text": "Summarize the report.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Annual_Financial_Report_2025.pdf", artifact_type="document"),
            )
        ),
        "target_ref": "the report",
        "expected_target_id": "x1",
        "expected_resolved_name": "Annual_Financial_Report_2025.pdf",
        "expected_goal_keywords": ["summarize", "report"],
        "expected_requested_ops": ["summarize"],
        "expected_prohibited_ops": [],
        "has_negation": False,
        "has_context": True,
    },
    {
        "id": "T3",
        "name": "Ambiguity preservation",
        "text": "Open the spreadsheet.",
        "category": ContextCategory.AMBIGUOUS.value,
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Q1_Budget.xlsx", artifact_type="spreadsheet"),
                ArtifactDescriptor(id="x2", name="Q2_Budget.xlsx", artifact_type="spreadsheet"),
            )
        ),
        "expected_goal_keywords": ["open", "spreadsheet"],
        "expected_requested_ops": ["open"],
        "expected_prohibited_ops": [],
        "must_preserve_ambiguity": True,
        "has_negation": False,
        "has_context": True,
    },
    {
        "id": "T4",
        "name": "Irrelevant-context resistance",
        "text": "Draft a memo to the staff.",
        "category": ContextCategory.SELF_CONTAINED.value,
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Lunch_Menu.pdf", artifact_type="document"),
            ),
            active_entities=(
                EntityDescriptor(id="e1", name="Building Security", category="role"),
            ),
        ),
        "expected_goal_keywords": ["draft", "memo", "staff"],
        "expected_requested_ops": ["draft"],
        "expected_prohibited_ops": [],
        "must_ignore_context": True,
        "has_negation": False,
        "has_context": True,
    },
    {
        "id": "T5",
        "name": "Stale-context resistance",
        "text": "Update the latest policy draft.",
        "category": ContextCategory.ACTIVE_CONTEXT_REQUIRED.value,
        "context": ActiveContext(
            active_artifacts=(
                ArtifactDescriptor(id="x1", name="Policy_Draft_v1.docx", artifact_type="document"),
                ArtifactDescriptor(id="x2", name="Policy_Draft_v2_Latest.docx", artifact_type="document"),
            )
        ),
        "target_ref": "latest policy draft",
        "expected_target_id": "x2",
        "expected_resolved_name": "Policy_Draft_v2_Latest.docx",
        "expected_goal_keywords": ["update", "policy", "draft"],
        "expected_requested_ops": ["update", "revise", "modify"],
        "expected_prohibited_ops": [],
        "has_negation": False,
        "has_context": True,
    },
    {
        "id": "T6",
        "name": "Negation polarity",
        "text": "Don't delete the backup. Just copy it.",
        "category": ContextCategory.SELF_CONTAINED.value,
        "context": None,
        "expected_goal_keywords": ["copy", "backup"],
        "expected_requested_ops": ["copy"],
        "expected_prohibited_ops": ["delete"],
        "expected_references": ["the backup", "it"],
        "has_negation": True,
        "has_context": False,
    },
    {
        "id": "T7",
        "name": "Multi-operation binding",
        "text": "Draft the response but do not send the attachment.",
        "category": ContextCategory.SELF_CONTAINED.value,
        "context": None,
        "expected_goal_keywords": ["draft", "response"],
        "expected_requested_ops": ["draft"],
        "expected_prohibited_ops": ["send"],
        "expected_references": ["the attachment"],
        "has_negation": True,
        "has_context": False,
    },
    {
        "id": "T8",
        "name": "Step-2 handoff",
        "text": "What was decided in the 2023 syndicate meeting?",
        "category": ContextCategory.STEP2_CONTEXT_REQUIRED.value,
        "context": None,
        "expected_goal_keywords": ["decided", "meeting", "what", "syndicate"],
        "expected_requested_ops": ["retrieve", "find", "query", "check"],
        "expected_prohibited_ops": [],
        "must_not_fabricate": True,
        "has_negation": False,
        "has_context": False,
    },
    {
        "id": "T9",
        "name": "Current attachment grounding",
        "text": "Review this document.",
        "category": ContextCategory.CURRENT_TURN_CONTEXT.value,
        "context": None,
        "attachments": (
            AttachmentReference(
                identifier="att1",
                name="Thesis_Chapter1.pdf",
                mime_type="application/pdf",
            ),
        ),
        "expected_goal_keywords": ["review", "document"],
        "expected_requested_ops": ["review"],
        "expected_prohibited_ops": [],
        "expected_references": ["this document"],
        "has_negation": False,
        "has_context": False,
    },
]


def _evaluate_item(case: Dict[str, Any], res: Any, model_name: str, mode: str) -> Dict[str, Any]:
    cat = case.get("category", ContextCategory.SELF_CONTAINED.value)
    eval_item: Dict[str, Any] = {
        "id": case["id"],
        "model": model_name,
        "mode": mode,
        "category": cat,
        "text": case["text"],
        "ok": res.ok,
        "latency_ms": getattr(res, "latency_ms", None),
        "prefill_tps": getattr(res, "prefill_tps", None),
        "decode_tps": getattr(res, "decode_tps", None),
        "peak_ram_mb": getattr(res, "peak_ram_mb", None),
        "prompt_tokens": getattr(res, "prompt_tokens", None),
        "completion_tokens": getattr(res, "completion_tokens", None),
        "reasoning_tokens": getattr(res, "reasoning_tokens", None),
        "error": str(res.error) if res.error else None,
        "reasoning": getattr(res, "reasoning", None) or getattr(res, "reasoning_content", None),
    }

    if not res.ok or res.decoded_request is None:
        eval_item["goal_correct"] = False
        eval_item["requested_ops_correct"] = False
        eval_item["prohibited_ops_correct"] = False
        eval_item["references_detected"] = False
        eval_item["unresolved_honesty"] = False
        eval_item["active_context_resolution"] = False
        eval_item["ambiguity_preservation"] = False
        eval_item["context_invented"] = False
        return eval_item

    dr = res.decoded_request
    eval_item["decoded"] = {
        "goal": dr.goal.description,
        "intent_family": dr.goal.intent_family.value,
        "requested_operations": [op.name for op in dr.operations if op.status == OperationStatus.REQUESTED],
        "prohibited_operations": [op.name for op in dr.operations if op.status == OperationStatus.PROHIBITED],
        "references": [
            {
                "expression": r.expression,
                "is_resolved": r.is_resolved,
                "referent_hint": r.referent_hint,
            }
            for r in dr.references
        ],
        "dependencies": [d.description for d in dr.dependencies],
        "ambiguities": [a.description for a in dr.ambiguities],
    }

    # 1. Goal
    goal_str = dr.goal.description.lower()
    exp_kw = case.get("expected_goal_keywords", [])
    if not exp_kw:
        goal_correct = bool(goal_str.strip())
    else:
        goal_correct = any(kw.lower() in goal_str for kw in exp_kw)
    eval_item["goal_correct"] = goal_correct

    # 2. Requested ops
    req_ops = [op.name.lower() for op in dr.operations if op.status == OperationStatus.REQUESTED]
    exp_req = [x.lower() for x in case.get("expected_requested_ops", [])]
    if not exp_req:
        req_correct = True
    else:
        req_correct = any(any(er in ro for ro in req_ops) for er in exp_req)
    eval_item["requested_ops_correct"] = req_correct

    # 3. Prohibited ops / Negation
    proh_ops = [op.name.lower() for op in dr.operations if op.status == OperationStatus.PROHIBITED]
    exp_proh = [x.lower() for x in case.get("expected_prohibited_ops", [])]
    if case.get("has_negation", False):
        if not exp_proh:
            proh_correct = len(proh_ops) > 0
        else:
            proh_correct = any(any(ep in po for po in proh_ops) for ep in exp_proh)
            # Ensure none of prohibited ops are marked requested
            for ep in exp_proh:
                if any(ep in ro for ro in req_ops):
                    proh_correct = False
    else:
        proh_correct = len(proh_ops) == 0
    eval_item["prohibited_ops_correct"] = proh_correct

    # 4. References detected
    exp_refs = [x.lower() for x in case.get("expected_references", [])]
    found_refs = [r.expression.lower() for r in dr.references]
    if not exp_refs:
        ref_detected = True
    else:
        ref_detected = any(any(er in fr for fr in found_refs) for er in exp_refs)
    eval_item["references_detected"] = ref_detected

    # 5. Unresolved honesty (when no context given or case expects unresolved)
    if not case.get("has_context", False) or case.get("must_be_unresolved", False):
        if len(dr.references) > 0:
            unresolved_honest = all(not r.is_resolved for r in dr.references)
        else:
            unresolved_honest = True
    else:
        unresolved_honest = True
    eval_item["unresolved_honesty"] = unresolved_honest

    # 6. Active Context Resolution (when context is provided)
    if case.get("has_context", False) and "target_ref" in case:
        target_ref = case["target_ref"].lower()
        exp_tid = case.get("expected_target_id")
        exp_name = case.get("expected_resolved_name")
        resolved = False
        for r in dr.references:
            if target_ref in r.expression.lower() or r.expression.lower() in target_ref:
                if r.is_resolved and (r.referent_hint == exp_name or r.referent_hint == exp_tid):
                    resolved = True
        eval_item["active_context_resolution"] = resolved
    else:
        eval_item["active_context_resolution"] = None

    # 7. Ambiguity preservation
    if case.get("must_preserve_ambiguity", False):
        # Ambiguity is preserved if ambiguities list has entries OR no single candidate was arbitrarily marked resolved
        ambiguity_preserved = len(dr.ambiguities) > 0 or all(not r.is_resolved for r in dr.references)
        eval_item["ambiguity_preservation"] = ambiguity_preserved
    else:
        eval_item["ambiguity_preservation"] = None

    # 8. Context invention
    raw_lower = case["text"].lower()
    invented = False
    for ent in dr.entities:
        if ent.name.lower() not in raw_lower:
            invented = True
    eval_item["context_invented"] = invented

    return eval_item


def run_comparative_probe():
    print("=================================================================")
    print("  M35 BATCH A2.4R — ARCHITECTURE-ALIGNED COMPARATIVE QUALIFICATION")
    print("  Comparing: Base Needle 3 vs Qwen3-14B-Q4_K_M")
    print("=================================================================")

    # Initialize models
    needle_venv = default_venv_python()
    needle_bridge = Path(__file__).resolve().parent.parent / "uri_v1" / "turn" / "needle_bridge_runtime.py"
    needle_transport = NeedleBridgeTransport(needle_venv, needle_bridge)
    needle_decoder = NeedleSinglePassDecoder(transport=needle_transport)

    qwen_transport = QwenLocalTransport(model_id="qwen3-14b", timeout=120.0)
    qwen_decoder = Qwen14BSemanticDecoder(transport=qwen_transport, max_tokens=800)

    # Load existing Qwen results from A2.4 if available
    a24_path = Path(__file__).resolve().parent / "qwen14b_qualification_results.json"
    a24_data = {}
    if a24_path.is_file():
        try:
            with open(a24_path, "r", encoding="utf-8") as f:
                a24_data = json.load(f)
            print("Loaded existing A2.4 Qwen results for reuse.")
        except Exception as exc:
            print("Could not load A2.4 results:", exc)

    results: Dict[str, Any] = {
        "metadata": {
            "batch": "A2.4R",
            "date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "models": {
                "needle": {
                    "name": "Needle 3 (generation 3, base weights)",
                    "runtime": "cactus-needle 3.0.2 via subprocess bridge",
                },
                "qwen": {
                    "name": "Qwen3-14B-Q4_K_M",
                    "file": "Qwen3-14B-Q4_K_M.gguf",
                    "parameters": "14.77B",
                    "quantization": "Q4_K_M",
                    "runtime": "LM Studio OpenAI endpoint 127.0.0.1:1234",
                },
            },
        },
        "needle_evaluations": [],
        "qwen_evaluations": [],
    }

    all_cases = STANDARD_CASES + CONVERSATIONAL_CASES + ARCHITECTURE_CASES

    # -----------------------------------------------------------------------
    # Part 1: Run Needle across 2x2 Matrix
    # -----------------------------------------------------------------------
    print("\n--- Part 1: Evaluating Base Needle 3 across 2x2 Matrix ---")
    needle_transport.load()
    print("Needle Bridge Ready:", needle_transport.runtime_info)

    for case in all_cases:
        cid = case["id"]
        raw = case["text"]
        ctx = case.get("context")
        atts = case.get("attachments")
        inp = DecodeInput(raw_text=raw, attachments=atts) if atts else raw

        modes_to_run = [DecoderMode.RAW, DecoderMode.TURN_FRAME]
        if case.get("has_context", False):
            modes_to_run.extend([DecoderMode.ACTIVE_CONTEXT, DecoderMode.TURN_FRAME_ACTIVE_CONTEXT])

        for m in modes_to_run:
            needle_decoder.reset()
            res = needle_decoder.decode_with_result(inp, mode=m, active_context=ctx)
            eval_item = _evaluate_item(case, res, "Needle 3", m.value)
            results["needle_evaluations"].append(eval_item)
            print(
                f"[Needle | {cid} | {m.value}] ok={res.ok} | Latency={eval_item['latency_ms']}ms | "
                f"Goal={eval_item['goal_correct']} Req={eval_item['requested_ops_correct']} "
                f"Proh={eval_item['prohibited_ops_correct']} Ref={eval_item['references_detected']} "
                f"Res={eval_item['active_context_resolution']}"
            )
            sys.stdout.flush()

    needle_decoder.close()

    # -----------------------------------------------------------------------
    # Part 2: Run Qwen across 2x2 Matrix (with Evidence Reuse)
    # -----------------------------------------------------------------------
    print("\n--- Part 2: Evaluating Qwen3-14B across 2x2 Matrix ---")

    # Map existing A2.4 data
    existing_qwen_a = {item["id"]: item for item in a24_data.get("mode_a_raw", [])}
    existing_qwen_b = {item["id"]: item for item in a24_data.get("mode_b_turn_frame", [])}
    existing_qwen_d = {item["id"]: item for item in a24_data.get("mode_c_active_context", [])}  # A2.4 Mode C was actually Mode D

    for case in all_cases:
        cid = case["id"]
        raw = case["text"]
        ctx = case.get("context")
        atts = case.get("attachments")
        inp = DecodeInput(raw_text=raw, attachments=atts) if atts else raw

        modes_to_run = [DecoderMode.RAW, DecoderMode.TURN_FRAME]
        if case.get("has_context", False):
            modes_to_run.extend([DecoderMode.ACTIVE_CONTEXT, DecoderMode.TURN_FRAME_ACTIVE_CONTEXT])

        for m in modes_to_run:
            # Check for reuse
            reused = None
            if m == DecoderMode.RAW and cid in existing_qwen_a:
                prev = existing_qwen_a[cid]
                # Synthesize DecodeResult for evaluation
                wire = prev.get("decoded")
                reused = prev
            elif m == DecoderMode.TURN_FRAME and cid in existing_qwen_b:
                reused = existing_qwen_b[cid]
            elif m == DecoderMode.TURN_FRAME_ACTIVE_CONTEXT and cid in existing_qwen_d:
                reused = existing_qwen_d[cid]

            if reused is not None and "decoded" in reused:
                # Reuse existing run
                # Create a mock result container
                dr = None
                if reused.get("ok"):
                    # Reconstruct DecodedRequest or run evaluation from stored item
                    pass
                # To be 100% rigorous and architecture-aligned, evaluate with fresh parser on stored wire or re-run
                # If stored wire exists, re-evaluate with current scoring rules
                if "wire" in reused and reused["wire"]:
                    try:
                        from uri_v1.turn.local_semantic_wire import normalize_qwen14b_wire
                        dr = normalize_qwen14b_wire(reused["wire"], inp if isinstance(inp, DecodeInput) else DecodeInput.from_text(inp), active_context=ctx)
                        mock_res = Qwen14BDecodeResult(
                            decoded_request=dr,
                            mode=m.value,
                            latency_ms=reused.get("latency_ms"),
                            prompt_tokens=reused.get("prompt_tokens"),
                            completion_tokens=reused.get("completion_tokens"),
                            reasoning_tokens=reused.get("reasoning_tokens"),
                        )
                        eval_item = _evaluate_item(case, mock_res, "Qwen3-14B", m.value)
                        results["qwen_evaluations"].append(eval_item)
                        print(f"[Qwen (Reused) | {cid} | {m.value}] ok=True | Latency={eval_item['latency_ms']:.0f}ms | Goal={eval_item['goal_correct']}")
                        sys.stdout.flush()
                        continue
                    except Exception:
                        pass

            # Otherwise run live inference
            res = qwen_decoder.decode_with_result(inp, mode=m, active_context=ctx)
            eval_item = _evaluate_item(case, res, "Qwen3-14B", m.value)
            results["qwen_evaluations"].append(eval_item)
            print(
                f"[Qwen (Live) | {cid} | {m.value}] ok={res.ok} | Latency={eval_item['latency_ms']:.0f}ms | "
                f"Goal={eval_item['goal_correct']} Req={eval_item['requested_ops_correct']} "
                f"Proh={eval_item['prohibited_ops_correct']} Ref={eval_item['references_detected']} "
                f"Res={eval_item['active_context_resolution']}"
            )
            sys.stdout.flush()

    # -----------------------------------------------------------------------
    # Part 3: Calculate Metrics & Statistics
    # -----------------------------------------------------------------------
    def aggregate_metrics(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        total = len(items)
        if total == 0:
            return {}
        ok_cnt = sum(1 for x in items if x["ok"])
        goal_cnt = sum(1 for x in items if x.get("goal_correct", False))
        req_cnt = sum(1 for x in items if x.get("requested_ops_correct", False))
        proh_cnt = sum(1 for x in items if x.get("prohibited_ops_correct", False))
        ref_cnt = sum(1 for x in items if x.get("references_detected", False))
        unres_cnt = sum(1 for x in items if x.get("unresolved_honesty", False))
        inv_cnt = sum(1 for x in items if x.get("context_invented", False))

        # Resolution on context-bearing cases
        res_cases = [x for x in items if x.get("active_context_resolution") is not None]
        res_cnt = sum(1 for x in res_cases if x.get("active_context_resolution") is True)
        res_rate = (res_cnt / len(res_cases)) if res_cases else None

        # Ambiguity preservation cases
        amb_cases = [x for x in items if x.get("ambiguity_preservation") is not None]
        amb_cnt = sum(1 for x in amb_cases if x.get("ambiguity_preservation") is True)
        amb_rate = (amb_cnt / len(amb_cases)) if amb_cases else None

        latencies = [x["latency_ms"] for x in items if x.get("latency_ms") is not None]

        return {
            "total": total,
            "ok_rate": ok_cnt / total,
            "goal_accuracy": goal_cnt / total,
            "requested_ops_accuracy": req_cnt / total,
            "prohibited_ops_accuracy": proh_cnt / total,
            "reference_detection_accuracy": ref_cnt / total,
            "unresolved_honesty_rate": unres_cnt / total,
            "active_context_resolution_rate": res_rate,
            "ambiguity_preservation_rate": amb_rate,
            "context_invention_rate": inv_cnt / total,
            "latency": {
                "min_ms": round(min(latencies), 1) if latencies else 0,
                "median_ms": round(statistics.median(latencies), 1) if latencies else 0,
                "mean_ms": round(statistics.mean(latencies), 1) if latencies else 0,
                "max_ms": round(max(latencies), 1) if latencies else 0,
            },
        }

    # By Model and Mode
    summary: Dict[str, Any] = {"needle": {}, "qwen": {}}
    for m in [DecoderMode.RAW.value, DecoderMode.TURN_FRAME.value, DecoderMode.ACTIVE_CONTEXT.value, DecoderMode.TURN_FRAME_ACTIVE_CONTEXT.value]:
        summary["needle"][m] = aggregate_metrics([x for x in results["needle_evaluations"] if x["mode"] == m])
        summary["qwen"][m] = aggregate_metrics([x for x in results["qwen_evaluations"] if x["mode"] == m])

    results["summary"] = summary

    # Save to JSON
    out_path = Path(__file__).resolve().parent / "a2_4r_comparative_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n=================================================================")
    print(f"  RESULTS SAVED TO {out_path}")
    print("=================================================================")
    print("Needle Mode A:", json.dumps(summary["needle"][DecoderMode.RAW.value], indent=2))
    print("Needle Mode B:", json.dumps(summary["needle"][DecoderMode.TURN_FRAME.value], indent=2))
    print("Needle Mode C:", json.dumps(summary["needle"][DecoderMode.ACTIVE_CONTEXT.value], indent=2))
    print("Needle Mode D:", json.dumps(summary["needle"][DecoderMode.TURN_FRAME_ACTIVE_CONTEXT.value], indent=2))
    print("Qwen Mode A:", json.dumps(summary["qwen"][DecoderMode.RAW.value], indent=2))
    print("Qwen Mode B:", json.dumps(summary["qwen"][DecoderMode.TURN_FRAME.value], indent=2))
    print("Qwen Mode C:", json.dumps(summary["qwen"][DecoderMode.ACTIVE_CONTEXT.value], indent=2))
    print("Qwen Mode D:", json.dumps(summary["qwen"][DecoderMode.TURN_FRAME_ACTIVE_CONTEXT.value], indent=2))


if __name__ == "__main__":
    run_comparative_probe()
