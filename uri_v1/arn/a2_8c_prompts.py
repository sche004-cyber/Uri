"""M35 URIv1 Batch A2.8C — Resolution-Path & Capability-Grounding Prompt Builders.

Builds strictly isolated prompts and strict JSON schemas for:
- Mode A (DIRECT): Direct capability selection from user language.
- Mode B (STRUCTURED): Structured separation of:
  Understood Goal -> Unresolved Requirement -> Resolution Path -> Capability Requirement -> Matched Capability.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from uri_v1.arn.resolution_contracts import (
    CAPABILITY_DESCRIPTIONS,
    AvailableCapability,
    ResolutionRequirementStatus,
)


def format_capability_catalog() -> str:
    """Renders the standard catalog of available capabilities."""
    lines = ["Available Capabilities and Meta-Actions:"]
    for cap, desc in CAPABILITY_DESCRIPTIONS.items():
        lines.append(f"- {cap}: {desc}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Strict JSON Schemas for Structured Output
# ---------------------------------------------------------------------------

MODE_A_SCHEMA_NAME = "direct_capability_selection"

MODE_A_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "selected_capability": {
            "type": "string",
            "enum": [c.value for c in AvailableCapability],
            "description": "Selected capability or meta-action to execute.",
        },
        "justification": {
            "type": "string",
            "description": "Concise justification for why this capability was selected directly.",
        },
    },
    "required": ["selected_capability", "justification"],
    "additionalProperties": False,
}


MODE_B_SCHEMA_NAME = "structured_resolution_path"

MODE_B_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "understood_goal": {
            "type": "string",
            "description": "Concise summary of the user's primary intended outcome.",
        },
        "unresolved_requirement": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": [s.value for s in ResolutionRequirementStatus],
                    "description": "Status of the information or condition needed.",
                },
                "description": {
                    "type": "string",
                    "description": "Specific information, condition, or confirmation that is missing or needed.",
                },
            },
            "required": ["status", "description"],
            "additionalProperties": False,
        },
        "resolution_path": {
            "type": "object",
            "properties": {
                "path_exists": {
                    "type": "boolean",
                    "description": "True if a known grounded automated path or tool exists to resolve this requirement.",
                },
                "step_description": {
                    "type": "string",
                    "description": "Immediate resolution step needed to satisfy the requirement.",
                },
            },
            "required": ["path_exists", "step_description"],
            "additionalProperties": False,
        },
        "capability_requirement": {
            "type": "string",
            "description": "Abstract functional capability needed for this resolution step.",
        },
        "matched_capability": {
            "type": "string",
            "enum": [c.value for c in AvailableCapability],
            "description": "The available capability that matches the abstract capability requirement.",
        },
        "justification": {
            "type": "string",
            "description": "Why this capability specifically satisfies the resolution requirement.",
        },
    },
    "required": [
        "understood_goal",
        "unresolved_requirement",
        "resolution_path",
        "capability_requirement",
        "matched_capability",
        "justification",
    ],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# System Prompts
# ---------------------------------------------------------------------------

MODE_A_SYSTEM_PROMPT = """You are URIv1's Capability Router.
Your task is to examine the user request and available context, and directly select the single most appropriate capability or meta-action to handle it.

Output strict JSON:
- selected_capability: one capability from the catalog.
- justification: concise justification for why this capability is selected (1-2 sentences).
"""

MODE_B_SYSTEM_PROMPT = """You are URIv1's Grounded Resolution Engine.
Your task is to analyze the user request by strictly separating:
1. UNDERSTOOD GOAL: What is the user trying to accomplish?
2. UNRESOLVED REQUIREMENT:
   - status:
     * ALREADY_GROUNDED: The fact/data is already in active context or solvable by simple deterministic logic.
     * RESOLVABLE_VIA_PATH: Unresolved, but a known authorized retrieval/execution path exists.
     * UNRESOLVABLE_AMBIGUITY: Unresolvable without user clarification (ambiguous referent, missing offline secret, or unauthorized request).
     * UNQUALIFIED_STRATEGY: Goal understood, but no qualified path or tool currently exists in the system.
   - description: What specific information, evidence, or confirmation is missing or needed?
3. RESOLUTION PATH:
   - path_exists: true if an automated grounded path exists; false if user must clarify or novel strategy is needed.
   - step_description: The immediate concrete step needed to satisfy the requirement.
4. CAPABILITY REQUIREMENT: Abstract functional ability needed for this step (e.g. 'search authorized private mailbox', 'deterministic calculation', 'request user disambiguation').
5. MATCHED CAPABILITY: Match the capability requirement against the catalog (or select NO_TOOL, ASK_USER, STRATEGY_DISCOVERY_REQUIRED).
6. JUSTIFICATION: Why this capability satisfies the resolution requirement (1-2 sentences).

Invariants:
- Do NOT select a capability merely because its name shares surface words with the user prompt.
- If information is already grounded or solvable by simple math/string logic, select NO_TOOL.
- If an entity is genuinely ambiguous between multiple candidates, do NOT guess; select ASK_USER.
- If a precondition is unverified (e.g. approval needed before submitting an order), resolve the precondition first.
"""


# ---------------------------------------------------------------------------
# Prompt Builders
# ---------------------------------------------------------------------------

def build_mode_a_prompt(user_text: str, active_context: Dict[str, Any]) -> str:
    """Mode A: User message + context + capability catalog -> direct selection."""
    parts = [f"[User Request]\n{user_text}"]

    if active_context:
        ctx_lines = ["[Active Context & Working State]"]
        for k, v in active_context.items():
            ctx_lines.append(f"- {k}: {json.dumps(v) if isinstance(v, (dict, list)) else v}")
        parts.append("\n".join(ctx_lines))

    parts.append(format_capability_catalog())
    parts.append("Task: Select the appropriate capability or action code to handle this user turn.")
    return "\n\n".join(parts)


def build_mode_b_prompt(user_text: str, active_context: Dict[str, Any]) -> str:
    """Mode B: Structured Resolution process."""
    parts = [f"[User Request]\n{user_text}"]

    if active_context:
        ctx_lines = ["[Active Context & Working State]"]
        for k, v in active_context.items():
            ctx_lines.append(f"- {k}: {json.dumps(v) if isinstance(v, (dict, list)) else v}")
        parts.append("\n".join(ctx_lines))

    parts.append(format_capability_catalog())
    parts.append(
        "Task: Execute Structured Resolution.\n"
        "1. Identify understood goal.\n"
        "2. Identify unresolved requirement (status and description).\n"
        "3. Formulate resolution path (path_exists and step description).\n"
        "4. Specify abstract capability requirement.\n"
        "5. Match against available capabilities (or NO_TOOL, ASK_USER, STRATEGY_DISCOVERY_REQUIRED).\n"
        "6. Output strict JSON."
    )
    return "\n\n".join(parts)


def wrap_chatml_prompt(system_prompt: str, user_prompt: str) -> str:
    """Formats prompt with ChatML and pre-closed think block for Qwen models."""
    return (
        f"<|im_start|>system\n{system_prompt.strip()}<|im_end|>\n"
        f"<|im_start|>user\n{user_prompt.strip()}<|im_end|>\n"
        f"<|im_start|>assistant\n<think>\n</think>\n"
    )
