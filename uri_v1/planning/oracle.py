"""Independent recomputation of a planned structure report (Stage 2 §2.6, F6-F8, F11).

The verifier's `report_recomputes` item calls `recompute` with the task class
`PLANNED_STRUCTURE_REPORT@<plan_sha256>`. This module reads `bundle/plan.json`,
checks its SHA-256 against that suffix, re-checks every manifest copy's hash,
and rebuilds the report by its own direct walk over `read_workbook_structure`
results. It never imports the runner, the binder or the action adapters: the
execution path is separate. The `officefile` reader is shared (disclosed, as
with M37's `edge/report.recompute`).

`verifier_entries` composes the dispatch for the M36 trusted bootstrap: planning
task classes go here, every other task class goes to the unchanged
`uri_v1.edge.report.recompute`. The verifier id stays the existing one (D2).
"""
from __future__ import annotations

import hashlib
import json
import re

from uri_v1.edge.report import recompute as edge_recompute
from uri_v1.execution.officefile import WorkbookReadError, read_workbook_structure
from uri_v1.execution.verify import VERIFIER_ID, VERIFIER_TYPE, VERIFIER_VERSION, make_memory_verifier
from uri_v1.execution.workspace import sha256_file
from .contracts import PLAN_SCHEMA_VERSION, REPORT_SCHEMA_VERSION, TASK_CLASS_PREFIX, canonical

_SHA = re.compile(r"^[0-9a-f]{64}$")
# coverage -> (input ports, output port, output type)
_OPS = {
    "oracle.inspect_structure.v1": ({"source"}, "structure", "WORKBOOK_STRUCTURE"),
    "oracle.select.v1": ({"structure"}, "selection", "STRUCTURE_SELECTION"),
    "oracle.compare.v1": ({"left", "right"}, "comparison", "STRUCTURE_COMPARISON"),
    "oracle.report_write.v1": ({"items"}, "report", "REPORT_ARTIFACT"),
}


class _Mismatch(ValueError):
    pass


def _dedupe(header):
    seen = []
    for h in header:
        if h is not None and h not in seen: seen.append(h)
    return seen


def expected_report(plan: dict, plan_sha256: str, source_paths: dict) -> dict:
    """Rebuild the report a correct execution of `plan` must have written."""
    nodes = {n["id"]: n for n in plan["nodes"]}
    if len(nodes) != len(plan["nodes"]): raise _Mismatch("DUPLICATE_NODE")
    memo, active = {}, set()

    def upstream(ref):
        node_id, port = ref.split(".")
        node = nodes[node_id]
        if _OPS[node["verifier_coverage"]][1] != port: raise _Mismatch("PORT")
        return _OPS[node["verifier_coverage"]][2], value(node_id)

    def value(node_id):
        if node_id in memo: return memo[node_id]
        if node_id in active: raise _Mismatch("CYCLE")
        active.add(node_id)
        node = nodes[node_id]
        ports, _, _ = _OPS[node["verifier_coverage"]]
        if set(node["inputs"]) != ports: raise _Mismatch("INPUT_PORTS")
        lit = node["literals"]
        cov = node["verifier_coverage"]
        if cov == "oracle.inspect_structure.v1":
            sid = node["inputs"]["source"]["source"]
            wb = read_workbook_structure(source_paths[sid])
            out = {"source_id": sid, "sheets": [{"name": s.name, "header": list(s.header), "error_cells": s.error_cells}
                                                for s in wb.sheets]}
        elif cov == "oracle.select.v1":
            (ref,) = node["inputs"]["structure"]["from"]
            kind, structure = upstream(ref)
            if kind != "WORKBOOK_STRUCTURE": raise _Mismatch("TYPE")
            sheets = []
            for name in lit["sheets"]:
                match = [s for s in structure["sheets"] if s["name"] == name]
                if not match: raise _Mismatch("LITERAL")
                if "headers" in lit:
                    for h in lit["headers"]:
                        if h not in match[0]["header"]: raise _Mismatch("LITERAL")
                    sheets.append({"name": name, "header": list(lit["headers"])})
                else:
                    sheets.append({"name": name, "header": list(match[0]["header"])})
            out = {"source_id": structure["source_id"], "sheets": sheets}
        elif cov == "oracle.compare.v1":
            if lit.get("match_on") != "sheet_name": raise _Mismatch("LITERAL")
            (lref,), (rref,) = node["inputs"]["left"]["from"], node["inputs"]["right"]["from"]
            (lk, left), (rk, right) = upstream(lref), upstream(rref)
            if lk != "STRUCTURE_SELECTION" or rk != "STRUCTURE_SELECTION": raise _Mismatch("TYPE")
            rnames = [s["name"] for s in right["sheets"]]
            lnames = [s["name"] for s in left["sheets"]]
            shared = []
            for s in left["sheets"]:
                if s["name"] not in rnames: continue
                l_h = _dedupe(s["header"])
                r_h = _dedupe(right["sheets"][rnames.index(s["name"])]["header"])
                shared.append({"name": s["name"], "shared": [h for h in l_h if h in r_h],
                               "only_left": [h for h in l_h if h not in r_h], "only_right": [h for h in r_h if h not in l_h]})
            out = {"match_on": "sheet_name", "left_source_id": left["source_id"], "right_source_id": right["source_id"],
                   "shared_sheets": shared, "only_left_sheets": [n for n in lnames if n not in rnames],
                   "only_right_sheets": [n for n in rnames if n not in lnames]}
        else:
            items = []
            for ref in node["inputs"]["items"]["from"]:
                kind, v = upstream(ref)
                if kind not in ("STRUCTURE_SELECTION", "STRUCTURE_COMPARISON"): raise _Mismatch("TYPE")
                items.append({"ref": ref, "type": kind, "value": v})
            out = {"schema_version": REPORT_SCHEMA_VERSION, "plan_sha256": plan_sha256, "node": node_id, "items": items}
        active.discard(node_id)
        memo[node_id] = out
        return out

    writers = [n for n in plan["nodes"] if n["verifier_coverage"] == "oracle.report_write.v1"]
    if len(writers) != 1 or plan["outputs"] != [writers[0]["id"] + ".report"]: raise _Mismatch("OUTPUTS")
    return value(writers[0]["id"])


def recompute(task_class, workspace, report_path) -> bool:
    if not isinstance(task_class, str) or not task_class.startswith(TASK_CLASS_PREFIX): return False
    want = task_class[len(TASK_CLASS_PREFIX):]
    if not _SHA.fullmatch(want): return False
    try:
        data = (workspace.bundle / "plan.json").read_bytes()
        if hashlib.sha256(data).hexdigest() != want: return False
        plan = json.loads(data)
        if canonical(plan) != data or plan.get("schema_version") != PLAN_SCHEMA_VERSION: return False
        for e in workspace.manifest:
            if sha256_file(workspace.files / e.relpath) != e.content_sha256: return False
        manifest = sorted([e.source_id, e.content_sha256] for e in workspace.manifest)
        if sorted(plan["sources"]) != manifest: return False
        paths = {e.source_id: workspace.files / e.relpath for e in workspace.manifest}
        expected = expected_report(plan, want, paths)
        return report_path.read_bytes() == canonical(expected)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, WorkbookReadError):
        return False


def dispatch(task_class, workspace, report_path) -> bool:
    if isinstance(task_class, str) and task_class.startswith(TASK_CLASS_PREFIX):
        return recompute(task_class, workspace, report_path)
    return edge_recompute(task_class, workspace, report_path)


def verifier_entries(run_root, *, python=None) -> dict:
    """Entries for the M36 trusted verifier bootstrap (qualification script and tests only)."""
    return {VERIFIER_ID: (VERIFIER_TYPE, VERIFIER_VERSION, make_memory_verifier(run_root, recompute=dispatch, python=python))}
