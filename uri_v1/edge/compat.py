"""Script ↔ workbook compatibility diagnosis and unique-remap proposals.

A remap is proposed only when exactly one workbook name normalizes to the same
form as the missing literal (case-fold, trim, and runs of whitespace, `_` or
`-` collapsed to one space). Zero or several matches are reported, never guessed.
"""
from __future__ import annotations

import re

_SEP = re.compile(r"[\s_\-]+")


def normalize(name: str) -> str:
    return _SEP.sub(" ", str(name).casefold()).strip()


def _remap(missing: str, available) -> dict:
    target = normalize(missing)
    matches = sorted({a for a in available if a is not None and normalize(a) == target})
    return {"literal": missing, "remap": matches[0] if len(matches) == 1 else None,
            "status": "UNIQUE" if len(matches) == 1 else "AMBIGUOUS" if matches else "NONE", "candidates": matches}


def diagnose(script_info, structure, workbook_name: str) -> dict:
    """Pure function of the inspection results; returns a JSON-safe diagnosis."""
    info = script_info.to_dict()
    sheet_names = list(structure.sheet_names)
    out = {"workbook_name": workbook_name, "sheet_names": sheet_names, "script": info,
           "missing_sheets": [], "missing_columns": [], "path_mismatch": [], "status": "COMPATIBLE"}
    if not script_info.parse_ok:
        out["status"] = "UNRESOLVED"; return out
    # Any directory component (including an absolute path) is a mismatch, not just a
    # differing basename: a script naming a path outside the workspace must never be
    # treated as referring to the bound workbook (F-2).
    out["path_mismatch"] = [p for p in info["workbook_paths"] if "/" in p.replace("\\", "/") or p != workbook_name]
    for s in info["sheets"]:
        if s not in sheet_names: out["missing_sheets"].append(_remap(s, sheet_names))
    # Columns are checked against the sheets the script names (after remap), or the
    # first sheet (openpyxl `active` / pandas default) when it names none.
    referenced = [s if s in sheet_names else next((m["remap"] for m in out["missing_sheets"] if m["literal"] == s), None)
                  for s in info["sheets"]]
    scope = [s for s in referenced if s] or sheet_names[:1]
    headers = [h for s in scope for h in structure.sheet(s).header if h is not None]
    for c in info["columns"]:
        if c not in headers: out["missing_columns"].append(_remap(c, headers))
    problems = out["missing_sheets"] + out["missing_columns"]
    if info["dynamic"] or out["path_mismatch"] or any(p["status"] != "UNIQUE" for p in problems):
        out["status"] = "UNRESOLVED"
    elif problems:
        out["status"] = "REMAPPABLE"
    return out
