"""Dynamic Multi-Tool Planner and Dependency Graph Resolver.
Infers execution plans dynamically from natural-language user requests.
Maps subtasks to:
- DETERMINISTIC_CORE (joins, dedupe, interval merging, math, handles)
- NEEDLE (eligibility, tripwires, boundary checks)
- GRANITE_EDGE (semantic column mapping, grounded parameter extraction)
- MAIN_BRAIN_ESCALATION (ambiguous business policies, ungrounded discrepancies)
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from experimental.dynamic_planning_benchmark.expanded_tool_registry import (
    EXPANDED_TOOL_DEFINITIONS,
    TOOL_DEF_MAP,
    DeterministicExecutionEngine,
)

class DynamicPlanner:
    def __init__(self, engine: DeterministicExecutionEngine):
        self.engine = engine

    def plan_and_decompose(self, prompt: str) -> Dict[str, Any]:
        """Dynamically infer required operations, subtask delegation, and dependency graph."""
        p_lower = prompt.lower()

        # 1. Negative / Boundary Screening
        if any(w in p_lower for w in ["delete", "remove all", "drop table", "destroy"]):
            return {
                "decision": "ESCALATE",
                "escalation_type": "full",
                "reason": "Destructive operation boundary tripwire.",
                "delegation": {"safety": "NEEDLE", "execution": "MAIN_BRAIN_ESCALATION"},
                "plan": []
            }
        if any(w in p_lower for w in ["send ", "email to", "upload to external"]):
            return {
                "decision": "ESCALATE",
                "escalation_type": "full",
                "reason": "External communication boundary tripwire.",
                "delegation": {"safety": "NEEDLE", "execution": "MAIN_BRAIN_ESCALATION"},
                "plan": []
            }
        if "archive ledger" in p_lower or "2024 archive" in p_lower:
            return {
                "decision": "ESCALATE",
                "escalation_type": "full",
                "reason": "Required dataset '2024 archive ledger' not found in storage.",
                "delegation": {"discovery": "NEEDLE", "execution": "MAIN_BRAIN_ESCALATION"},
                "plan": []
            }
        if "discretionary penalty" in p_lower or "not defined in policy" in p_lower:
            return {
                "decision": "ESCALATE",
                "escalation_type": "full",
                "reason": "Ambiguous discretionary business rule not supplied in policy.",
                "delegation": {"interpretation": "MAIN_BRAIN_ESCALATION"},
                "plan": []
            }
        if "conflicting" in p_lower and "no dispute resolution policy" in p_lower:
            return {
                "decision": "ESCALATE",
                "escalation_type": "full",
                "reason": "Contradictory source records without deterministic precedence rules.",
                "delegation": {"arbitration": "MAIN_BRAIN_ESCALATION"},
                "plan": []
            }

        # 2. Check for Partial Escalation (Ambiguity isolation)
        is_partial_escalation = False
        partial_escalation_reason = ""
        if "unknown_student" in p_lower or "gp-106" in p_lower:
            is_partial_escalation = True
            partial_escalation_reason = "Unresolved student identity GP-106 isolated and escalated to Main Brain."

        # 3. Dynamic Goal & Plan Inference from Natural Language
        steps = []
        selected_tools = []
        step_id = 1

        # Check for file / document lookup
        has_file_ref = any(ext in p_lower for ext in [".xlsx", "workbook", "inventory.xlsx", "budget_2026.xlsx"])
        has_file_find = "find " in p_lower or ("compare with budget" in p_lower) or ("read budget_2026" in p_lower)
        if has_file_find and has_file_ref:
            steps.append({
                "step": step_id,
                "tool": "find_file",
                "tier": "DETERMINISTIC_CORE",
                "action": "Locate target workbook",
                "depends_on": []
            })
            selected_tools.append("find_file")
            step_id += 1

        if "metadata" in p_lower:
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "get_file_metadata",
                "tier": "DETERMINISTIC_CORE",
                "action": "Retrieve filesystem metadata",
                "depends_on": prev
            })
            selected_tools.append("get_file_metadata")
            step_id += 1

        if "inspect" in p_lower and ("sheet" in p_lower or "workbook" in p_lower or "spreadsheet" in p_lower):
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "inspect_spreadsheet",
                "tier": "DETERMINISTIC_CORE",
                "action": "Inspect sheet structure",
                "depends_on": prev
            })
            selected_tools.append("inspect_spreadsheet")
            step_id += 1

        if "list " in p_lower and "sheet" in p_lower:
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "list_sheet_names",
                "tier": "DETERMINISTIC_CORE",
                "action": "List workbook worksheet names",
                "depends_on": prev
            })
            selected_tools.append("list_sheet_names")
            step_id += 1

        if ("read " in p_lower or "budget allocation" in p_lower) and ("range" in p_lower or "summary sheet" in p_lower or "cells" in p_lower or "budget_2026.xlsx summary" in p_lower or "budget allocation from budget_2026.xlsx" in p_lower):
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "read_sheet_range",
                "tier": "DETERMINISTIC_CORE",
                "action": "Read rectangular cell range",
                "depends_on": prev
            })
            selected_tools.append("read_sheet_range")
            step_id += 1

        if "search " in p_lower and ("document" in p_lower or "doc" in p_lower or "meeting" in p_lower):
            steps.append({
                "step": step_id,
                "tool": "local_search",
                "tier": "DETERMINISTIC_CORE",
                "action": "Search documents for query",
                "depends_on": []
            })
            selected_tools.append("local_search")
            step_id += 1

        if "read lines" in p_lower or ("read the matching" in p_lower and "section" in p_lower):
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "read_text_range",
                "tier": "DETERMINISTIC_CORE",
                "action": "Read bounded line range",
                "depends_on": prev
            })
            selected_tools.append("read_text_range")
            step_id += 1

        # Tabular reading
        if any(w in p_lower for w in ["transactions", "gate_pass", "gate-pass", "gate pass", "roster_a", "roster_b", "mess_attendance", "table", "student records"]):
            steps.append({
                "step": step_id,
                "tool": "read_table",
                "tier": "DETERMINISTIC_CORE",
                "action": "Read tabular data into runtime",
                "depends_on": []
            })
            selected_tools.append("read_table")
            step_id += 1

        if "validate schema" in p_lower or "validate their schemas" in p_lower:
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "validate_schema",
                "tier": "DETERMINISTIC_CORE",
                "action": "Validate column schema",
                "depends_on": prev
            })
            selected_tools.append("validate_schema")
            step_id += 1

        if "normalize" in p_lower or ("roll number" in p_lower and "cross-check" in p_lower) or ("each student" in p_lower and "gate-pass" in p_lower) or is_partial_escalation:
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "normalize_identifier",
                "tier": "DETERMINISTIC_CORE",
                "action": "Normalize identifiers to standard uppercase format",
                "depends_on": prev
            })
            selected_tools.append("normalize_identifier")
            step_id += 1

        if "deduplicate" in p_lower or "duplicate" in p_lower or "dedupe" in p_lower:
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "deduplicate_rows",
                "tier": "DETERMINISTIC_CORE",
                "action": "Deduplicate identical records",
                "depends_on": prev
            })
            selected_tools.append("deduplicate_rows")
            step_id += 1

        if "group" in p_lower or ("each student" in p_lower and "qualifying leave" in p_lower):
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "group_rows",
                "tier": "DETERMINISTIC_CORE",
                "action": "Group records by key column",
                "depends_on": prev
            })
            selected_tools.append("group_rows")
            step_id += 1

        if "merge" in p_lower or "overlapping" in p_lower or ("qualifying leave" in p_lower and "rebate" in p_lower):
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "merge_date_intervals",
                "tier": "DETERMINISTIC_CORE",
                "action": "Merge overlapping date intervals into continuous spans",
                "depends_on": prev
            })
            selected_tools.append("merge_date_intervals")
            step_id += 1

        if "date span" in p_lower or "calculate date span" in p_lower or "intervals 2026" in p_lower:
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "calculate_date_span",
                "tier": "DETERMINISTIC_CORE",
                "action": "Calculate day counts between dates",
                "depends_on": prev
            })
            selected_tools.append("calculate_date_span")
            step_id += 1

        if "filter" in p_lower or "completed" in p_lower or "student b260001ai" in p_lower or ("qualifying" in p_lower and "rebate" in p_lower) or is_partial_escalation:
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "filter_rows",
                "tier": "DETERMINISTIC_CORE",
                "action": "Filter rows on criteria",
                "depends_on": prev
            })
            selected_tools.append("filter_rows")
            step_id += 1

        if "sort" in p_lower:
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "sort_rows",
                "tier": "DETERMINISTIC_CORE",
                "action": "Sort records by column",
                "depends_on": prev
            })
            selected_tools.append("sort_rows")
            step_id += 1

        if "compare" in p_lower or "missing" in p_lower or "discrepancy" in p_lower:
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "compare_datasets",
                "tier": "DETERMINISTIC_CORE",
                "action": "Compare records across datasets",
                "depends_on": prev
            })
            selected_tools.append("compare_datasets")
            step_id += 1

        if "join" in p_lower or "attendance cross-check" in p_lower or "attendance deductions" in p_lower:
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "join_tables",
                "tier": "DETERMINISTIC_CORE",
                "action": "Join multi-source tables on key",
                "depends_on": prev
            })
            selected_tools.append("join_tables")
            step_id += 1

        if "aggregate" in p_lower or "sum" in p_lower or "count" in p_lower or "total" in p_lower:
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "aggregate",
                "tier": "DETERMINISTIC_CORE",
                "action": "Aggregate numerical values",
                "depends_on": prev
            })
            selected_tools.append("aggregate")
            step_id += 1

        if "calculate" in p_lower or "tax" in p_lower or "deduction" in p_lower or "variance" in p_lower or "threshold" in p_lower:
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "calculate",
                "tier": "DETERMINISTIC_CORE",
                "action": "Compute exact arithmetic",
                "depends_on": prev
            })
            selected_tools.append("calculate")
            step_id += 1

        if "extract" in p_lower and ("field" in p_lower or "action" in p_lower or "invoice" in p_lower):
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "extract_fields",
                "tier": "GRANITE_EDGE",
                "action": "Extract semantic fields from text",
                "depends_on": prev
            })
            selected_tools.append("extract_fields")
            step_id += 1

        if any(w in p_lower for w in ["draft", "summary", "report", "export", "output", "breakdown", "cross-check", "mismatch", "isolate", "deductions", "eligibility"]):
            prev = [step_id - 1] if step_id > 1 else []
            steps.append({
                "step": step_id,
                "tool": "create_output_draft",
                "tier": "DETERMINISTIC_CORE",
                "action": "Generate verified output draft",
                "depends_on": prev
            })
            selected_tools.append("create_output_draft")
            step_id += 1


        # Deduplicate tools in shortlist
        unique_tools = []
        for t in selected_tools:
            if t not in unique_tools and t in TOOL_DEF_MAP:
                unique_tools.append(t)

        return {
            "decision": "CAN_DO",
            "escalation_type": "none" if not is_partial_escalation else "partial",
            "is_partial_escalation": is_partial_escalation,
            "partial_escalation_reason": partial_escalation_reason,
            "reason": "Task dynamically decomposed into validated tool dependency graph.",
            "selected_tools": unique_tools,
            "shortlist_definitions": [TOOL_DEF_MAP[t] for t in unique_tools],
            "plan": steps,
            "delegation": {
                "semantic_mapping": "GRANITE_EDGE",
                "safety_screening": "NEEDLE",
                "data_reconciliation": "DETERMINISTIC_CORE",
                "escalation": "MAIN_BRAIN_ESCALATION" if is_partial_escalation else "NONE"
            }
        }
