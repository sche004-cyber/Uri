"""Independent recomputation verifier and oracle (Stage 2, Slice 1).

Recomputes structure reports independently from hash-verified original sources
and bundle/plan.json. Never calls PlanRunner or the binder. Compares canonical bytes.
Composes transparently into URI's trusted verifier bootstrap.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from uri_v1.edge.report import recompute as edge_recompute
from uri_v1.execution.officefile import WorkbookReadError, WorkbookStructure, read_workbook_structure
from uri_v1.execution.verify import VERIFIER_ID, VERIFIER_TYPE, VERIFIER_VERSION, make_memory_verifier
from uri_v1.execution.workspace import Workspace, sha256_file

TASK_CLASS_PREFIX = "PLANNED_STRUCTURE_REPORT@"


def canonical(value: Any) -> bytes:
    """Canonical JSON serialization for independent byte comparison."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def recompute(task_class: str, workspace: Workspace, report_path: Path) -> bool:
    """Independently re-derive the structure report from hash-bound sources and plan.json.

    Returns True if and only if report_path byte-for-byte matches the recomputed output.
    """
    if not isinstance(task_class, str) or not task_class.startswith(TASK_CLASS_PREFIX):
        return False

    expected_plan_sha = task_class[len(TASK_CLASS_PREFIX):]
    if len(expected_plan_sha) != 64:
        return False

    # 1. Read and verify bundle/plan.json
    plan_file = workspace.bundle / "plan.json"
    if not plan_file.exists():
        return False

    plan_bytes = plan_file.read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != expected_plan_sha:
        return False

    try:
        plan_dict = json.loads(plan_bytes.decode("utf-8"))
    except Exception:
        return False

    if plan_dict.get("schema_version") != "uri.plan.compiled.v1":
        return False

    # 2. Re-check every manifest copy's hash
    for entry in workspace.manifest:
        p = workspace.files / entry.relpath
        if not p.exists() or sha256_file(p) != entry.content_sha256:
            return False

    source_files = {e.source_id: workspace.files / e.relpath for e in workspace.manifest}

    # 3. Independent direct evaluation of the plan DAG
    values: dict[tuple[str, str], Any] = {}

    try:
        for node in plan_dict.get("nodes", []):
            node_id = node["node_id"]
            action_id = node["action_id"]
            inputs = node["inputs"]
            literals = node.get("literals", {})

            # Resolve inputs from source files or preceding outputs
            resolved: dict[str, Any] = {}
            for port_name, binding in inputs.items():
                if "source" in binding:
                    sid = binding["source"]
                    if sid not in source_files:
                        return False
                    resolved[port_name] = source_files[sid]
                elif "from" in binding:
                    from_node, from_port = binding["from"].split(".", 1)
                    if (from_node, from_port) not in values:
                        return False
                    resolved[port_name] = values[(from_node, from_port)]
                else:
                    return False

            # Independent action execution
            if action_id == "uri.plan.workbook.inspect_structure":
                structure = read_workbook_structure(resolved["source"])
                values[(node_id, "structure")] = structure

            elif action_id == "uri.plan.structure.select":
                structure = resolved["structure"]
                sheets = literals.get("sheets", [])
                headers = literals.get("headers")

                if isinstance(structure, WorkbookStructure):
                    avail = {s.name: s for s in structure.sheets}
                elif isinstance(structure, dict) and "sheets" in structure:
                    avail = {s["name"]: s for s in structure["sheets"]}
                else:
                    return False

                selected = []
                for s_name in sheets:
                    if s_name not in avail:
                        return False
                    s = avail[s_name]
                    raw_h = s.header if hasattr(s, "header") else s.get("header", s.get("headers", ()))
                    h_list = list(raw_h)

                    if headers is not None:
                        for req_h in headers:
                            if req_h not in h_list:
                                return False
                        kept_h = [h for h in h_list if h in headers]
                    else:
                        kept_h = h_list

                    errs = getattr(s, "error_cells", 0) if hasattr(s, "error_cells") else s.get("error_cells", 0)
                    selected.append({"name": s_name, "headers": kept_h, "error_cells": errs})

                values[(node_id, "selection")] = {"sheets": selected}

            elif action_id == "uri.plan.structure.compare":
                if literals.get("match_on") != "sheet_name":
                    return False

                left_sel = resolved["left"].get("selection", resolved["left"])
                right_sel = resolved["right"].get("selection", resolved["right"])

                left_sheets = {s["name"]: list(s.get("headers", [])) for s in left_sel.get("sheets", [])}
                right_sheets = {s["name"]: list(s.get("headers", [])) for s in right_sel.get("sheets", [])}

                shared_sheets = sorted(set(left_sheets.keys()) & set(right_sheets.keys()))
                only_left = sorted(set(left_sheets.keys()) - set(right_sheets.keys()))
                only_right = sorted(set(right_sheets.keys()) - set(left_sheets.keys()))

                sheet_diffs = []
                for s_name in shared_sheets:
                    lh = set(left_sheets[s_name])
                    rh = set(right_sheets[s_name])
                    sheet_diffs.append({
                        "sheet_name": s_name,
                        "shared_headers": sorted(lh & rh),
                        "only_left_headers": sorted(lh - rh),
                        "only_right_headers": sorted(rh - lh),
                    })

                values[(node_id, "comparison")] = {
                    "match_on": "sheet_name",
                    "shared_sheets": shared_sheets,
                    "only_left_sheets": only_left,
                    "only_right_sheets": only_right,
                    "sheets": sheet_diffs,
                }

            elif action_id == "uri.plan.report.write":
                item_keys = sorted(k for k in resolved.keys() if k.startswith("item"))
                report_items = []
                for k in item_keys:
                    item_val = resolved[k]
                    if "comparison" in item_val:
                        report_items.append({"kind": "comparison", "data": item_val["comparison"]})
                    elif "selection" in item_val:
                        report_items.append({"kind": "selection", "data": item_val["selection"]})
                    elif "match_on" in item_val:
                        report_items.append({"kind": "comparison", "data": item_val})
                    elif "sheets" in item_val:
                        report_items.append({"kind": "selection", "data": item_val})
                    else:
                        report_items.append({"kind": "unknown", "data": item_val})

                values[(node_id, "report")] = {
                    "schema_version": "uri.plan.report.v1",
                    "plan_sha256": expected_plan_sha,
                    "items": report_items,
                }

        # 4. Find declared output
        outputs = plan_dict.get("outputs", [])
        if not outputs:
            return False

        terminal = outputs[0]
        term_node = terminal["node_id"]
        term_port = terminal["port"]

        if (term_node, term_port) not in values:
            return False

        expected_data = values[(term_node, term_port)]
        expected_bytes = canonical(expected_data)

        if not report_path.exists():
            return False

        actual_bytes = report_path.read_bytes()
        return actual_bytes == expected_bytes

    except (WorkbookReadError, KeyError, ValueError, OSError):
        return False


def dispatch_recompute(task_class: str, workspace: Workspace, report_path: Path) -> bool:
    """Route PLANNED_STRUCTURE_REPORT@* to dynamic planning oracle, others to edge recompute."""
    if isinstance(task_class, str) and task_class.startswith(TASK_CLASS_PREFIX):
        return recompute(task_class, workspace, report_path)
    return edge_recompute(task_class, workspace, report_path)


def verifier_entries(run_root: Path | str, *, python: str | None = None) -> dict[str, Any]:
    """Composed entries for the M36 trusted verifier bootstrap."""
    return {
        VERIFIER_ID: (
            VERIFIER_TYPE,
            VERIFIER_VERSION,
            make_memory_verifier(run_root, recompute=dispatch_recompute, python=python),
        )
    }
