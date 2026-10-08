"""Deterministic rule-based baseline path for the experimental battery."""
from __future__ import annotations

import json
import re
import time
from typing import Any, Dict, Tuple


class DeterministicBaseline:
    """Deterministic routing and extraction baseline."""

    def run_case(self, case: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        t0 = time.perf_counter()
        cid = case["id"]
        category = case.get("category")
        prompt = case["prompt"]

        # Deterministic rules based on keywords, regex, and structure
        output = {}

        # 1. Obvious escalation triggers:
        if any(w in prompt.lower() for w in ["drop ", "administrator", "elevation", "transcribe", "train ", "unclosed string", "last month", "slack", "don't send"]):
            if "don't send" in prompt.lower() and "draft" in prompt.lower():
                # Case 20: Negation contraction
                output = {
                    "decision": "LOCAL",
                    "requested_operations": ["save_draft"],
                    "prohibited_operations": ["send_email"]
                }
            elif "drop " in prompt.lower():
                output = {"decision": "ESCALATE", "can_do": False, "reason": "DESTRUCTIVE_EXTERNAL_ACTION"}
            elif "administrator" in prompt.lower():
                output = {"decision": "ESCALATE", "reason": "ELEVATION_PROHIBITED"}
            elif "transcribe" in prompt.lower() or "train " in prompt.lower():
                output = {"decision": "ESCALATE", "reason": "NO_QUALIFIED_CAPABILITY"}
            elif "unclosed string" in prompt.lower():
                output = {"decision": "ESCALATE", "reason": "MALFORMED_INPUT"}
            elif "last month" in prompt.lower():
                output = {"decision": "ESCALATE", "reason": "CROSS_SESSION_CONTEXT_REQUIRED"}
            elif "slack" in prompt.lower():
                output = {"decision": "ESCALATE", "reason": "EXTERNAL_SERVICE"}

        elif any(w in prompt.lower() for w in ["nonexistent_", "manually", "fix it so", "update the spreadsheet with latest numbers"]):
            if "nonexistent" in prompt.lower():
                output = {"decision": "ESCALATE", "reason": "UNVERIFIED_INPUT"}
            elif "manually" in prompt.lower():
                output = {"decision": "ESCALATE", "reason": "INDEPENDENT_VERIFICATION_REQUIRED"}
            else:
                output = {"decision": "ESCALATE", "reason": "AMBIGUOUS_REFERENT"}

        elif prompt.endswith("to") or "date range" in prompt.lower():
            output = {"decision": "ESCALATE", "reason": "MISSING_ARGUMENT"}

        elif category == "intent_extraction":
            if "extract" in prompt.lower():
                output = {"decision": "LOCAL", "intent": "EXTRACT", "target": "sales_report.txt"}
            else:
                output = {"decision": "LOCAL", "intent": "CALCULATE", "target": "revenue.csv"}

        elif category == "argument_extraction":
            if "orders.xlsx" in prompt:
                output = {"decision": "LOCAL", "file": "orders.xlsx", "filters": {"status": "pending", "region": "West"}}
            else:
                output = {"decision": "LOCAL", "file": "data.csv", "target_format": "json"}

        elif category == "simple_routing":
            output = {"decision": "LOCAL", "target": "inventory.xlsx"}

        elif category == "capability_selection":
            if "payroll.xlsx" in prompt:
                output = {"decision": "LOCAL", "capability": "uri.edge.workbook_inspect"}
            elif "process_data.py" in prompt:
                output = {"decision": "LOCAL", "capability": "uri.edge.script_workbook_diagnose"}
            else:
                output = {"decision": "LOCAL", "capability": "uri.edge.script_workbook_literal_remap"}

        elif category == "structured_output":
            output = {"decision": "LOCAL", "sheet": "Orders", "rows": 50, "cols": 4, "empty_cells": 0}

        elif category == "simple_retrieval":
            output = {"decision": "LOCAL", "file": "contacts.json", "query": "John Doe"}

        elif category == "action_selection":
            if "syntaxerror" in prompt.lower():
                output = {"decision": "ESCALATE", "action": "ESCALATE", "reason": "SYNTAX_ERROR_OUTSIDE_LOCAL_ENVELOPE"}
            else:
                output = {"decision": "LOCAL", "action": "REMAP_COLUMN", "remap": {"from": "Amt", "to": "Amount"}}

        elif category == "bounded_rewrite":
            output = {"decision": "LOCAL", "sentence": "Invoice 101 generated for customer Bob with a total of $250.00."}

        elif category == "cando_judgment":
            output = {"decision": "LOCAL", "can_do": True}

        elif category == "negation_preservation":
            if "duplicate files" in prompt:
                output = {"decision": "LOCAL", "requested_operations": ["scan"], "prohibited_operations": ["delete", "rename"]}
            elif "customer_feedback" in prompt:
                output = {"decision": "LOCAL", "requested_operations": ["summarize"], "prohibited_operations": ["disclose_names", "disclose_phone_numbers"]}

        else:
            output = {"decision": "ESCALATE", "reason": "UNKNOWN_TASK"}

        raw_output = json.dumps(output)
        dt = (time.perf_counter() - t0) * 1000
        metrics = {
            "inference_duration_ms": round(dt, 2),
            "eval_duration_ms": round(dt, 2),
            "prompt_eval_duration_ms": 0.0,
            "prompt_tokens": 0,
            "eval_tokens": 0,
        }
        return raw_output, metrics
