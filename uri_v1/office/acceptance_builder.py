"""Derive `AcceptanceCriteria` from the bound originals, before any execution (M39 §4.2).

`script_exit_zero` on the bound script, plus for each workspace-relative
`output_path` string literal the script writes to (`uri_v1/edge/scriptinfo.py
inspect_script`): `output_workbook_exists`, `no_formula_errors`, and, only
where the *original* script names them as string literals (`ws.title = "..."`,
`ws.append([...])`), `workbook_has_sheets` / `workbook_has_columns`. Because
this reads the output structure from the original script rather than from
whatever a harness produces, a harness that removes the script's logic cannot
satisfy the sheet/column items even if it exits 0 and writes *some* file at
that path (M39 plan self-review "neutered-script false pass", scenario D4).

A script with no detectable output, or whose only detected output path is
outside the workspace, yields acceptance without output items plus a warning:
"URI can only check that the script runs".
"""
from __future__ import annotations

import ast
from dataclasses import dataclass

from uri_v1.edge.scriptinfo import inspect_script
from uri_v1.execution.acceptance import AcceptanceCriteria, workspace_relpath

NO_OUTPUT_WARNING = "URI can only check that the script runs"


@dataclass(frozen=True)
class BuiltAcceptance:
    criteria: AcceptanceCriteria
    warnings: tuple


def _func_name(call) -> str:
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""


def _created_workbook_vars(tree) -> set:
    created = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if isinstance(node.value, ast.Call) and _func_name(node.value) == "Workbook":
                created.update(names)
    return created


def _sheet_vars_of(tree, workbook_vars) -> dict:
    """{sheet_var_name: workbook_var_name} for `.active` and `.create_sheet(...)`."""
    sheet_of = {}
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign): continue
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            v = node.value
            wv = None
            if isinstance(v, ast.Attribute) and v.attr == "active" and isinstance(v.value, ast.Name) and v.value.id in workbook_vars:
                wv = v.value.id
            elif (isinstance(v, ast.Call) and _func_name(v) == "create_sheet"
                  and isinstance(v.func, ast.Attribute) and isinstance(v.func.value, ast.Name) and v.func.value.id in workbook_vars):
                wv = v.func.value.id
            if wv is not None:
                for n in names:
                    if n not in sheet_of:
                        sheet_of[n] = wv; changed = True
    return sheet_of


def _titles_and_headers(tree, sheet_vars: set) -> tuple[dict, dict]:
    """First `<sheet>.title = "..."` and first `<sheet>.append([...])` literal list per sheet var.

    "First" means first in *source order* (M39-9, audit): `ast.walk` is
    breadth-first, so an `append` nested one block deeper (e.g. inside an
    `if`) loses to a later, shallower `append` even when the nested one runs
    first and is the real header row. Sorting by (lineno, col_offset) before
    scanning makes "first" mean what a reader of the script would mean by it.
    """
    titles, headers = {}, {}
    ordered = sorted(ast.walk(tree), key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))
    for node in ordered:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if (isinstance(t, ast.Attribute) and t.attr == "title" and isinstance(t.value, ast.Name)
                        and t.value.id in sheet_vars and t.value.id not in titles
                        and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
                    titles[t.value.id] = node.value.value
        elif (isinstance(node, ast.Call) and _func_name(node) == "append"
              and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)):
            var = node.func.value.id
            if var in sheet_vars and var not in headers and node.args:
                arg = node.args[0]
                if (isinstance(arg, (ast.List, ast.Tuple)) and arg.elts
                        and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in arg.elts)):
                    headers[var] = [e.value for e in arg.elts]
    return titles, headers


def _outputs_from_ast(tree) -> list:
    """[{"path": str, "sheets": [str,...] | None, "columns": {sheet: [str,...]}}] for openpyxl `Workbook().save(...)`."""
    workbook_vars = _created_workbook_vars(tree)
    if not workbook_vars: return []
    sheet_vars = _sheet_vars_of(tree, workbook_vars)
    titles, headers = _titles_and_headers(tree, set(sheet_vars))
    outputs = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _func_name(node) == "save"
                and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)):
            continue
        wv = node.func.value.id
        if wv not in workbook_vars or not node.args: continue
        arg = node.args[0]
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.lower().endswith((".xlsx", ".xlsm"))):
            continue
        own_sheet_vars = [sv for sv, owner in sheet_vars.items() if owner == wv]
        sheets = sorted({titles[sv] for sv in own_sheet_vars if sv in titles})
        columns = {titles[sv]: headers[sv] for sv in own_sheet_vars if sv in titles and sv in headers}
        outputs.append({"path": arg.value, "sheets": sheets or None, "columns": columns})
    return outputs


def build_acceptance(script_bytes: bytes, script_relpath: str, *, timeout_s: int = 60) -> BuiltAcceptance:
    info = inspect_script(script_bytes)
    warnings = []
    allowed = {script_relpath}
    output_items = []
    outputs = []
    if info.parse_ok:
        try:
            tree = ast.parse(script_bytes.decode("utf-8"))
            outputs = _outputs_from_ast(tree)
        except (UnicodeDecodeError, SyntaxError, ValueError):
            outputs = []
        detected = {o["path"] for o in outputs}
        for extra in sorted(set(info.values("output_path")) - detected):
            outputs.append({"path": extra, "sheets": None, "columns": {}})
    if not outputs:
        warnings.append(NO_OUTPUT_WARNING)
    for o in outputs:
        try:
            p = workspace_relpath(o["path"])
        except ValueError:
            warnings.append(f"output path {o['path']!r} is outside the workspace; {NO_OUTPUT_WARNING}")
            continue
        allowed.add(p)
        output_items.append({"kind": "output_workbook_exists", "path": p})
        output_items.append({"kind": "no_formula_errors", "path": p})
        if o.get("sheets"):
            output_items.append({"kind": "workbook_has_sheets", "path": p, "sheets": o["sheets"]})
        for sheet, cols in (o.get("columns") or {}).items():
            output_items.append({"kind": "workbook_has_columns", "path": p, "sheet": sheet, "columns": cols})
    items = ([{"kind": "only_changed", "paths": sorted(allowed)},
              {"kind": "script_exit_zero", "script": script_relpath, "timeout_s": timeout_s}]
             + output_items)
    return BuiltAcceptance(AcceptanceCriteria(1, tuple(items)), tuple(warnings))
