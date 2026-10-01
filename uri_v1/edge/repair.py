"""Deterministic literal remap: the only local repair qualified in M37.

Rewrites exactly the recognized sheet/column string literals whose diagnosis is
a unique remap, at their exact AST spans. Every other byte of the script is
preserved. The repaired script must re-parse and re-diagnose as COMPATIBLE,
otherwise the repair is refused.
"""
from __future__ import annotations

from .compat import diagnose
from .scriptinfo import inspect_script


class RepairRefused(ValueError):
    pass


def remap_plan(diagnosis) -> dict:
    return {m["literal"]: m["remap"] for m in diagnosis["missing_sheets"] + diagnosis["missing_columns"]}


def apply_remap(source: bytes, diagnosis, structure, workbook_name) -> bytes:
    if diagnosis["status"] == "COMPATIBLE": return source
    if diagnosis["status"] != "REMAPPABLE": raise RepairRefused("NOT_REMAPPABLE")
    plan = remap_plan(diagnosis)
    info = inspect_script(source)
    sheet_literals = {m["literal"] for m in diagnosis["missing_sheets"]}
    column_literals = {m["literal"] for m in diagnosis["missing_columns"]}
    targets = [r for r in info.refs if (r.kind == "sheet" and r.value in sheet_literals) or (r.kind == "column" and r.value in column_literals)]
    if not targets or any(not r.simple for r in targets): raise RepairRefused("LITERAL_NOT_REWRITABLE")
    lines = source.decode("utf-8").splitlines(keepends=True)
    for ref in sorted(targets, key=lambda r: (r.lineno, r.col), reverse=True):
        new = plan[ref.value]
        if any(ord(c) < 32 for c in new): raise RepairRefused("UNSAFE_REPLACEMENT")
        raw = lines[ref.lineno - 1].encode("utf-8")
        quote = raw[ref.col:ref.col + 1].decode()
        if quote in new or "\\" in new: raise RepairRefused("UNSAFE_REPLACEMENT")
        raw = raw[:ref.col] + (quote + new + quote).encode("utf-8") + raw[ref.end_col:]
        lines[ref.lineno - 1] = raw.decode("utf-8")
    repaired = "".join(lines).encode("utf-8")
    after = diagnose(inspect_script(repaired), structure, workbook_name)
    if after["status"] != "COMPATIBLE": raise RepairRefused("REPAIR_DID_NOT_RESOLVE")
    return repaired
