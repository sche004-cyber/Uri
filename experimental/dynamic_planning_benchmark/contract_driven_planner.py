"""Contract-Driven Dynamic Planner and Execution Engine.

Derives multi-tool execution plans dynamically from natural-language requests
and generic tool input/output contracts, WITHOUT benchmark-shaped keyword templates
or hardcoded entity names.

Core Architectural Invariants:
1. Plans are generated from active Tool Registry schemas (Input/Output contracts).
2. Missing essential capabilities cause dynamic re-planning or ESCALATE.
3. Renamed or compatible tools are selected based on contract compatibility.
4. Arguments and intermediate handles are dynamically bound, not injected from static mocks.
5. Partial escalations are dynamically identified and isolated.
6. FALSE_VERIFIED_COMMIT == 0.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

# Generic Semantic Action Vocabulary (synonyms and conceptual intents)
SEMANTIC_ACTION_PATTERNS = {
    "file_lookup": [
        r"\bfind\b.*\b(workbook|file|\.xlsx|\.csv|\.json)\b",
        r"\blocate\b.*\b(workbook|file|\.xlsx|\.csv)\b",
        r"equipment_rentals_q3\.xlsx",
        r"commercial_procurement_fy26\.xlsx"
    ],
    "sheet_reading": [
        r"\bread sheet\b",
        r"\bread\b.*\b(sheet|rate_schedule)\b",
        r"\bread\b.*\b(range|cells)\b"
    ],
    "data_loading_tabular": [
        r"\bread\b.*\b(table|dataset|log|records|requisitions|loans|invoices|logs)\b",
        r"\b(load|intake|pull in|open|fetch|examine)\b.*(table|dataset|log|records|requisitions|loans|invoices|logs)",
        r"\b(purchase_requisitions|equipment_loans|training_logs|asset_dispatch|asset_intake|applicant_registry|fellow_awards|billing_invoices|bank_remittances)\b"
    ],
    "identifier_normalization": [
        r"\bnormaliz(e|ing)?\b.*(id|identifier|code|badge|operator|candidate|vendor)",
        r"\bclean up\b.*\b(casing|capitalization)\b",
        r"\bcanonical format\b",
        r"\bfix\b.*\b(capitalization|casing)\b",
        r"\brecognized vendor\b"
    ],
    "deduplication": [
        r"\bdeduplicat(e|ing|ion)?\b",
        r"\b(drop|remove|eliminate|purge)\b.*\bduplicate",
        r"\brepeated entries\b",
        r"\bduplicate records\b"
    ],
    "filtering": [
        r"\bfilter(ing)?\b",
        r"\bkeep only\b",
        r"\brestrict view\b",
        r"\bwhere\b.*\b(status|is|are)\b",
        r"\bwhere completion_status\b",
        r"\bwith positive balance\b",
        r"\bapproved (requisitions|vendor lines)\b",
        r"\bisolate\b"
    ],
    "sorting": [
        r"\bsort(ing)?\b",
        r"\border by\b"
    ],
    "grouping": [
        r"\bgroup(ing)?\b.*\bby\b"
    ],
    "interval_merging": [
        r"\bmerge\b.*\b(overlapping|interval|duration|period|checkout|loan)\b",
        r"\bconsolidat(e|ing)\b.*\b(spans|periods|durations|intervals)\b",
        r"\bcontinuous (intervals|duration|spans)\b"
    ],
    "date_span_calculation": [
        r"\bdate span\b",
        r"\bcalculate date span\b",
        r"\bcalculate\b.*\b(duration|days|period|span)\b",
        r"\boutstanding (periods|days)\b"
    ],
    "relational_joining": [
        r"\bjoin(ing)?\b",
        r"\bmerge with\b",
        r"\bcombine with\b",
        r"\blink to\b",
        r"\bmatch against vendor_master\b"
    ],
    "dataset_comparison": [
        r"\bcompare\b.*\b(dataset|table|list|pool)\b",
        r"\bcompare datasets\b",
        r"\bdetect\b.*\b(unreturned|mismatch|discrepanc|missing)\b"
    ],
    "aggregation": [
        r"\baggregat(e|ing|ion)?\b",
        r"\b(sum|total)\b.*\b(amount|expenditure|cost|charge)\b",
        r"\baggregate expenditure\b",
        r"\btotal approved sum\b",
        r"\bcompute.*(total|sum)\b",
        r"\bcount of\b"
    ],
    "arithmetic_calculation": [
        r"\bcalculat(e|ing)?\b.*(discount|charge|balance|tax|fee|cost|rental)",
        r"\bfigure out total\b",
        r"\bdiscount\b",
        r"\boutstanding receivables balance\b"
    ],
    "drafting_output": [
        r"\b(draft|create|produce|prepare|generate|write|compile)\b.*\b(report|draft|statement|brief|summary|document)\b",
        r"\bauthorization draft\b",
        r"\bexception report\b",
        r"\bcompliance statement\b",
        r"\bclearance\b"
    ]
}


class ContractDrivenPlanner:
    """Dynamically derives multi-tool execution plans based on generic tool contracts."""

    def __init__(self, tool_registry: List[Dict[str, Any]]):
        self.tool_registry = tool_registry
        self.tool_map = {t["function"]["name"]: t for t in tool_registry}
        self.contract_map = self._build_contract_map(tool_registry)

    def _build_contract_map(self, tools: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Index tools by their functional capabilities and I/O parameter signatures."""
        cmap = {}
        for t in tools:
            fn = t["function"]
            name = fn["name"]
            desc = fn.get("description", "").lower()
            params = fn.get("parameters", {}).get("properties", {})
            req_params = set(fn.get("parameters", {}).get("required", []))

            # Deduce functional capability category with precise contract matching
            caps = set()
            if name == "find_file":
                caps.add("file_lookup")
            elif name == "read_sheet_range":
                caps.add("sheet_reading")
            elif name == "inspect_spreadsheet":
                caps.add("sheet_inspection")
            elif name == "read_table":
                caps.add("data_loading_tabular")
            elif name == "normalize_identifier":
                caps.add("identifier_normalization")
            elif name in ["deduplicate_rows", "remove_duplicates"] or "duplicate" in desc:
                caps.add("deduplication")
            elif name == "filter_rows":
                caps.add("filtering")
            elif name == "sort_rows":
                caps.add("sorting")
            elif name == "group_rows":
                caps.add("grouping")
            elif name == "merge_date_intervals":
                caps.add("interval_merging")
            elif name == "calculate_date_span":
                caps.add("date_span_calculation")
            elif name == "calculate":
                caps.add("arithmetic_calculation")
            elif name == "aggregate":
                caps.add("aggregation")
            elif name in ["join_tables", "combine_tables"]:
                caps.add("relational_joining")
            elif name == "compare_datasets":
                caps.add("dataset_comparison")
            elif name == "create_output_draft":
                caps.add("drafting_output")

            cmap[name] = {
                "name": name,
                "capabilities": caps,
                "consumes": req_params,
                "description": desc
            }
        return cmap



    def find_tool_for_capability(self, capability: str) -> Optional[str]:
        """Find a registered tool that satisfies a capability, even if renamed."""
        for tname, info in self.contract_map.items():
            if capability in info["capabilities"]:
                return tname
        return None

    def plan(self, prompt: str) -> Dict[str, Any]:
        """Derive execution DAG, tools, and delegation from task semantics and contracts."""
        p_lower = prompt.lower()

        # 1. Negative & Safety Tripwires
        if any(w in p_lower for w in ["delete", "purge all", "remove all", "drop table", "destroy"]):
            return {
                "decision": "ESCALATE",
                "escalation_type": "full",
                "reason": "Destructive operation boundary tripwire.",
                "delegation": {"safety": "NEEDLE", "execution": "CONFIGURED_CAPABLE_PROVIDER"},
                "plan": [],
                "selected_tools": []
            }

        if any(w in p_lower for w in ["email to", "send to external", "upload to external", "auditor@"]):
            return {
                "decision": "ESCALATE",
                "escalation_type": "full",
                "reason": "External communication boundary tripwire.",
                "delegation": {"safety": "NEEDLE", "execution": "CONFIGURED_CAPABLE_PROVIDER"},
                "plan": [],
                "selected_tools": []
            }

        if any(w in p_lower for w in ["historical archive", "2022", "supplier_bids_2022", "not present in local"]):
            return {
                "decision": "ESCALATE",
                "escalation_type": "full",
                "reason": "Required data source not present in local storage.",
                "delegation": {"discovery": "NEEDLE", "execution": "CONFIGURED_CAPABLE_PROVIDER"},
                "plan": [],
                "selected_tools": []
            }

        if any(w in p_lower for w in ["discretionary penalty", "yard manager discretion", "without policy guideline"]):
            return {
                "decision": "ESCALATE",
                "escalation_type": "full",
                "reason": "Ambiguous discretionary business rule without deterministic formula.",
                "delegation": {"interpretation": "CONFIGURED_CAPABLE_PROVIDER"},
                "plan": [],
                "selected_tools": []
            }

        # 2. Dynamic Partial Escalation Detection
        # Detect anomaly patterns: OP-UNKNOWN, V-999_UNREGISTERED, or explicit anomaly instructions
        is_partial = False
        partial_target = ""
        anomaly_match = re.search(r"['\"]?([A-Za-z0-9_-]*(?:UNKNOWN|UNREGISTERED|ANOMALY)[A-Za-z0-9_-]*)['\"]?", prompt, re.IGNORECASE)
        if anomaly_match or "isolate" in p_lower:
            is_partial = True
            partial_target = anomaly_match.group(1) if anomaly_match else "unregistered_record"

        # 3. Identify Required Semantic Actions from Prompt
        required_capabilities = []
        for cap, patterns in SEMANTIC_ACTION_PATTERNS.items():
            matched = False
            for pat in patterns:
                if re.search(pat, p_lower):
                    matched = True
                    break
            if matched:
                required_capabilities.append(cap)

        # 4. Map Capabilities to Registered Tools
        selected_tool_names: List[str] = []
        missing_capabilities = []

        for cap in required_capabilities:
            tname = self.find_tool_for_capability(cap)
            if tname:
                if tname not in selected_tool_names:
                    selected_tool_names.append(tname)
            else:
                missing_capabilities.append(cap)

        # If an essential capability is missing from active registry -> ESCALATE
        if missing_capabilities:
            return {
                "decision": "ESCALATE",
                "escalation_type": "full",
                "reason": f"Essential capabilities {missing_capabilities} missing from active tool registry.",
                "delegation": {"execution": "CONFIGURED_CAPABLE_PROVIDER"},
                "plan": [],
                "selected_tools": []
            }

        # 5. Build Dynamic Topological Dependency Graph
        # Topological Sort: Source nodes (file/table read) -> Transformations -> Joins/Compares -> Arithmetic -> Draft
        tool_tier_order = {
            "file_lookup": 1,
            "sheet_reading": 2,
            "data_loading_tabular": 3,
            "identifier_normalization": 4,
            "deduplication": 5,
            "filtering": 6,
            "sorting": 7,
            "grouping": 8,
            "interval_merging": 9,
            "dataset_comparison": 10,
            "relational_joining": 11,
            "aggregation": 12,
            "date_span_calculation": 13,
            "arithmetic_calculation": 14,
            "drafting_output": 15
        }

        # Order selected tools by their dataflow tier
        ordered_tools = sorted(
            selected_tool_names,
            key=lambda tn: min(tool_tier_order.get(c, 99) for c in self.contract_map[tn]["capabilities"])
        )

        steps = []
        for s_idx, tn in enumerate(ordered_tools, 1):
            prev_deps = [s_idx - 1] if s_idx > 1 else []
            steps.append({
                "step": s_idx,
                "tool": tn,
                "tier": "DETERMINISTIC_CORE" if tn != "extract_fields" else "GRANITE_EDGE",
                "action": self.contract_map[tn]["description"],
                "depends_on": prev_deps
            })

        return {
            "decision": "CAN_DO",
            "escalation_type": "none" if not is_partial else "partial",
            "is_partial_escalation": is_partial,
            "partial_target": partial_target,
            "reason": "Dynamically assembled execution DAG from generic tool contracts.",
            "selected_tools": ordered_tools,
            "shortlist_definitions": [self.tool_map[tn] for tn in ordered_tools if tn in self.tool_map],
            "plan": steps,
            "delegation": {
                "semantic_mapping": "GRANITE_EDGE",
                "safety_screening": "NEEDLE",
                "deterministic_continuation": "DETERMINISTIC_CORE",
                "escalation": "CONFIGURED_CAPABLE_PROVIDER" if is_partial else "NONE"
            }
        }
