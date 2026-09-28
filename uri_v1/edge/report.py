"""Deterministic Edge reports and their independent recomputation.

A report task's product is `edge_report.json`. The recompute function used by
the URI verifier rebuilds the report from the workspace copies, after checking
each copy still has its copy-in hash, and compares canonical bytes.
"""
from __future__ import annotations

import json
from pathlib import Path

from uri_v1.execution.officefile import WorkbookReadError, read_workbook_structure
from uri_v1.execution.workspace import sha256_file
from .compat import diagnose
from .contracts import TaskClass as T
from .scriptinfo import inspect_script

REPORT_NAME = "edge_report.json"


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_report(task_class, workbook_path: Path, workbook_name: str, script_path: Path | None = None) -> dict:
    structure = read_workbook_structure(workbook_path)
    report = {"schema_version": "m37.edge.report.v1", "task_class": T(task_class).value,
              "workbook": dict(structure.to_dict(), name=workbook_name)}
    if T(task_class) is T.SCRIPT_WORKBOOK_DIAGNOSE:
        report["diagnosis"] = diagnose(inspect_script(script_path.read_bytes()), structure, workbook_name)
    return report


def recompute(task_class, workspace, report_path: Path) -> bool:
    by_role = {e.role: e for e in workspace.manifest}
    for e in workspace.manifest:
        if sha256_file(workspace.files / e.relpath) != e.content_sha256: return False
    try:
        wb = by_role["workbook"]
        script = workspace.files / by_role["script"].relpath if "script" in by_role else None
        expected = build_report(task_class, workspace.files / wb.relpath, wb.relpath, script)
        return report_path.read_bytes() == canonical(expected)
    except (KeyError, OSError, WorkbookReadError, ValueError):
        return False
