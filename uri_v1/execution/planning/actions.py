"""Approved deterministic actions for dynamic planning (Stage 2, Slice 1).

Pure, bounded functions over officefile structures and JSON artifacts:
1. uri.plan.workbook.inspect_structure
2. uri.plan.structure.select
3. uri.plan.structure.compare
4. uri.plan.report.write
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from uri_v1.execution.officefile import WorkbookReadError, WorkbookStructure, read_workbook_structure
from .contracts import (
    CapabilityContract,
    CapabilitySnapshot,
    InputPortSpec,
    LiteralSpec,
    PortType,
)

REPORT_FILENAME = "plan_report.json"
REPORT_SCHEMA_VERSION = "uri.plan.report.v1"


class ActionExecutionError(ValueError):
    """Typed failure during action execution."""
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def action_inspect_structure(source_path: Path) -> dict[str, Any]:
    """Action 1: Read workbook structure from workspace copy."""
    try:
        structure = read_workbook_structure(source_path)
    except WorkbookReadError as exc:
        raise ActionExecutionError("WORKBOOK_READ_ERROR", str(exc))
    except Exception as exc:
        raise ActionExecutionError("WORKBOOK_READ_ERROR", type(exc).__name__)
    return {"structure": structure}


def action_structure_select(
    structure: WorkbookStructure | dict[str, Any],
    sheets: list[str],
    headers: list[str] | None = None,
) -> dict[str, Any]:
    """Action 2: Filter workbook structure by exact sheet and header names."""
    if isinstance(structure, WorkbookStructure):
        avail_sheets = {s.name: s for s in structure.sheets}
    elif isinstance(structure, dict) and "sheets" in structure:
        # Reconstruct or adapt dict
        avail_sheets = {s["name"]: s for s in structure["sheets"]}
    else:
        raise ActionExecutionError("INVALID_INPUT_TYPE", "Expected WorkbookStructure or dict with sheets")

    selected_sheets = []
    for sheet_name in sheets:
        if sheet_name not in avail_sheets:
            raise ActionExecutionError("LITERAL_NOT_IN_SOURCE", f"Sheet '{sheet_name}' not found in workbook")

        s = avail_sheets[sheet_name]
        raw_headers = s.header if isinstance(s, type(s)) and hasattr(s, "header") else s.get("header", s.get("headers", ()))
        sheet_headers = list(raw_headers)

        if headers is not None:
            for req_h in headers:
                if req_h not in sheet_headers:
                    raise ActionExecutionError("LITERAL_NOT_IN_SOURCE", f"Header '{req_h}' not found in sheet '{sheet_name}'")
            kept_headers = [h for h in sheet_headers if h in headers]
        else:
            kept_headers = sheet_headers

        error_cells = getattr(s, "error_cells", 0) if hasattr(s, "error_cells") else s.get("error_cells", 0)

        selected_sheets.append({
            "name": sheet_name,
            "headers": kept_headers,
            "error_cells": error_cells,
        })

    return {"selection": {"sheets": selected_sheets}}


def action_structure_compare(
    left: dict[str, Any],
    right: dict[str, Any],
    match_on: str,
) -> dict[str, Any]:
    """Action 3: Compare two structure selections by exact sheet name."""
    if match_on != "sheet_name":
        raise ActionExecutionError("INVALID_LITERAL_VALUE", f"Unsupported match_on: {match_on}")

    left_selection = left.get("selection", left)
    right_selection = right.get("selection", right)

    left_sheets = {s["name"]: list(s.get("headers", [])) for s in left_selection.get("sheets", [])}
    right_sheets = {s["name"]: list(s.get("headers", [])) for s in right_selection.get("sheets", [])}

    all_left = set(left_sheets.keys())
    all_right = set(right_sheets.keys())

    shared_sheets = sorted(all_left & all_right)
    only_left_sheets = sorted(all_left - all_right)
    only_right_sheets = sorted(all_right - all_left)

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

    return {
        "comparison": {
            "match_on": "sheet_name",
            "shared_sheets": shared_sheets,
            "only_left_sheets": only_left_sheets,
            "only_right_sheets": only_right_sheets,
            "sheets": sheet_diffs,
        }
    }


def action_report_write(
    items: list[dict[str, Any]],
    files_dir: Path,
    plan_sha256: str,
) -> dict[str, Any]:
    """Action 4: Format and write canonical structure report into workspace files/."""
    report_items = []
    for item in items:
        if "comparison" in item:
            report_items.append({"kind": "comparison", "data": item["comparison"]})
        elif "selection" in item:
            report_items.append({"kind": "selection", "data": item["selection"]})
        elif "match_on" in item:
            report_items.append({"kind": "comparison", "data": item})
        elif "sheets" in item:
            report_items.append({"kind": "selection", "data": item})
        else:
            report_items.append({"kind": "unknown", "data": item})

    report_payload = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "plan_sha256": plan_sha256,
        "items": report_items,
    }

    canonical_bytes = json.dumps(report_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    target_path = files_dir / REPORT_FILENAME
    target_path.write_bytes(canonical_bytes)

    return {"report": report_payload}


def canonical_contracts() -> tuple[CapabilityContract, ...]:
    """Canonical capability contracts for the four approved Slice 1 actions."""
    return (
        CapabilityContract(
            action_id="uri.plan.workbook.inspect_structure",
            version="1",
            mechanism="DETERMINISTIC",
            inputs={"source": InputPortSpec("source", (PortType.SOURCE_XLSX,), required=True)},
            outputs={"structure": PortType.WORKBOOK_STRUCTURE},
            literals={},
            effect="READ_ONLY",
            approval="NONE",
            verifier_coverage="",
            qualification="QUAL-M37-INSPECT-01@833d6ed",
        ),
        CapabilityContract(
            action_id="uri.plan.structure.select",
            version="1",
            mechanism="DETERMINISTIC",
            inputs={"structure": InputPortSpec("structure", (PortType.WORKBOOK_STRUCTURE,), required=True)},
            outputs={"selection": PortType.STRUCTURE_SELECTION},
            literals={
                "sheets": LiteralSpec("sheets", expected_type="list", required=True, element_type="str"),
                "headers": LiteralSpec("headers", expected_type="list", required=False, element_type="str"),
            },
            effect="READ_ONLY",
            approval="NONE",
            verifier_coverage="",
            qualification="QUAL-PLAN-SELECT-01@833d6ed",
        ),
        CapabilityContract(
            action_id="uri.plan.structure.compare",
            version="1",
            mechanism="DETERMINISTIC",
            inputs={
                "left": InputPortSpec("left", (PortType.STRUCTURE_SELECTION,), required=True),
                "right": InputPortSpec("right", (PortType.STRUCTURE_SELECTION,), required=True),
            },
            outputs={"comparison": PortType.STRUCTURE_COMPARISON},
            literals={
                "match_on": LiteralSpec("match_on", expected_type="str", required=True, allowed_values=("sheet_name",)),
            },
            effect="READ_ONLY",
            approval="NONE",
            verifier_coverage="",
            qualification="QUAL-PLAN-COMPARE-01@833d6ed",
        ),
        CapabilityContract(
            action_id="uri.plan.report.write",
            version="1",
            mechanism="DETERMINISTIC",
            inputs={
                "item_1": InputPortSpec("item_1", (PortType.STRUCTURE_SELECTION, PortType.STRUCTURE_COMPARISON), required=True),
                "item_2": InputPortSpec("item_2", (PortType.STRUCTURE_SELECTION, PortType.STRUCTURE_COMPARISON), required=False),
                "item_3": InputPortSpec("item_3", (PortType.STRUCTURE_SELECTION, PortType.STRUCTURE_COMPARISON), required=False),
                "item_4": InputPortSpec("item_4", (PortType.STRUCTURE_SELECTION, PortType.STRUCTURE_COMPARISON), required=False),
            },
            outputs={"report": PortType.REPORT_ARTIFACT},
            literals={},
            effect="SCRATCH_WRITE",
            approval="NONE",
            verifier_coverage="report_recomputes",
            qualification="QUAL-PLAN-REPORT-01@833d6ed",
        ),
    )


def snapshot() -> CapabilitySnapshot:
    """Return the pinned CapabilitySnapshot for the canonical Slice 1 actions."""
    return CapabilitySnapshot.create(canonical_contracts())
