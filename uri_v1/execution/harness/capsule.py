"""Execution Capsule and instructions bundle from an Edge `EscalationRequest`.

The bundle lives outside the harness-visible `files/` directory. It carries
the goal, the unresolved remainder, compact local findings and the acceptance
items; it carries no file contents beyond names and structure.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from .contracts import CapabilityGrant, ExecutionCapsule, HarnessType, Limits, PermissionProfile

_GOALS = {
    "SCRIPT_WORKBOOK_REPAIR": "Make the Python script in this directory run successfully against the workbook in this directory.",
    "SCRIPT_WORKBOOK_DIAGNOSE": "Explain whether the script in this directory works with the workbook in this directory.",
    "WORKBOOK_INSPECT": "Describe the structure of the workbook in this directory.",
}


def _findings_summary(findings: dict) -> dict:
    out = {}
    if "workbook" in findings:
        out["workbook"] = {"name": findings["workbook"].get("name"),
                           "sheets": [{"name": s["name"], "header": s["header"]} for s in findings["workbook"].get("sheets", [])]}
    diag = findings.get("diagnosis")
    if diag:
        out["diagnosis"] = {"status": diag["status"], "missing_sheets": diag["missing_sheets"], "missing_columns": diag["missing_columns"],
                            "path_mismatch": diag["path_mismatch"], "dynamic_access": diag["script"]["dynamic"],
                            "script_sheet_refs": diag["script"]["sheets"], "script_column_refs": diag["script"]["columns"],
                            "script_workbook_paths": diag["script"]["workbook_paths"]}
    if "local_attempt" in findings:
        la = findings["local_attempt"]
        out["local_attempt"] = {"verification_status": la["verification_status"],
                                "failed_checks": [{"kind": i["kind"], "detail": i.get("detail")} for i in la.get("items", []) if i["status"] != "PASS"]}
    return out


def build_instructions(escalation, manifest) -> str:
    esc = escalation.to_dict()
    names = {e.role: e.relpath for e in manifest}
    changeable = sorted({p for i in esc["acceptance"]["items"] if i["kind"] == "only_changed" for p in i["paths"]})
    lines = [
        "# Task from URI",
        "",
        _GOALS[esc["task_class"]],
        "",
        f"Files: {', '.join(f'{r} = {n}' for r, n in sorted(names.items()))}.",
        "Work only inside the current directory. Do not access other paths or the network.",
        f"You may change only: {', '.join(changeable) if changeable else 'nothing (report only)'}.",
        "",
        "## What URI could not resolve locally",
        *[f"- {u}" for u in esc["unresolved"]],
        "",
        "## What URI already established (hash-verified inputs)",
        "```json",
        json.dumps(_findings_summary(esc["local_findings"]), indent=1, sort_keys=True),
        "```",
        "",
        "## Acceptance criteria (URI will check these itself after you finish)",
        "```json",
        json.dumps(esc["acceptance"]["items"], indent=1, sort_keys=True),
        "```",
        "",
        "URI verifies the result independently. Do not claim that it is verified; say what you changed and why.",
        "",
    ]
    return "\n".join(lines)


def build_capsule(escalation, workspace, *, harness_type: HarnessType, posture: PermissionProfile | None = None,
                  capabilities: CapabilityGrant | None = None, limits: Limits | None = None) -> ExecutionCapsule:
    text = build_instructions(escalation, workspace.manifest).encode("utf-8")
    path = Path(workspace.bundle) / "INSTRUCTIONS.md"
    path.write_bytes(text)
    return ExecutionCapsule(uuid.uuid4().hex, workspace.run_id, escalation.task_id, escalation.trace_id, HarnessType(harness_type),
                            str(workspace.files), tuple({"role": e.role, "source_id": e.source_id, "relpath": e.relpath,
                                                         "sha256": e.content_sha256} for e in workspace.manifest),
                            str(path), hashlib.sha256(text).hexdigest(), escalation.acceptance, escalation.acceptance_sha256,
                            posture or PermissionProfile(), capabilities or CapabilityGrant.none(), limits or Limits())
