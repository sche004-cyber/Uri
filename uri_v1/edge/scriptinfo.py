"""Deterministic static inspection of a Python script's workbook usage.

Static only: the script is parsed, never imported or executed. The result is
conservative. Any name-based sheet/column access that cannot be resolved to a
string literal marks the script `dynamic`, which makes local repair
ineligible. Recognized patterns (openpyxl and pandas):
  workbook = load_workbook("x.xlsx") / Workbook()        -> workbook variable
  sheet = workbook["Name"] / workbook.get_sheet_by_name("Name") -> sheet reference
  frame = read_excel("x.xlsx", sheet_name="Name")          -> dataframe + sheet reference
  frame["Column"], frame[["A", "B"]] (load context)         -> column references
  <anything>.index("Column")                                -> column reference (header lookup)
  <x>.save("out.xlsx") / <frame>.to_excel("out.xlsx")      -> output path
"""
from __future__ import annotations

import ast
from dataclasses import dataclass

MAX_SCRIPT_BYTES = 512 * 1024
_WORKBOOK_EXT = (".xlsx", ".xlsm")


@dataclass(frozen=True)
class LiteralRef:
    kind: str            # sheet | column | workbook_path | output_path
    value: str
    lineno: int
    col: int
    end_lineno: int
    end_col: int
    simple: bool         # a single, plain, single-line quoted literal that can be rewritten exactly


@dataclass(frozen=True)
class ScriptInfo:
    parse_ok: bool
    imports: tuple
    refs: tuple
    dynamic: tuple       # reasons name-based access could not be resolved statically

    def values(self, kind) -> list:
        return sorted({r.value for r in self.refs if r.kind == kind})

    def to_dict(self) -> dict:
        return {"parse_ok": self.parse_ok, "imports": list(self.imports),
                "sheets": self.values("sheet"), "columns": self.values("column"),
                "workbook_paths": self.values("workbook_path"), "output_paths": self.values("output_path"),
                "dynamic": list(self.dynamic)}


def _func_name(call) -> str:
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else ""


def _simple(source_lines, node) -> bool:
    if node.lineno != node.end_lineno: return False
    line = source_lines[node.lineno - 1].encode("utf-8")
    seg = line[node.col_offset:node.end_col_offset].decode("utf-8", "replace")
    if len(seg) < 2 or seg[0] not in "'\"" or seg[-1] != seg[0] or seg.startswith(seg[0] * 3): return False
    body = seg[1:-1]
    return "\\" not in body and seg[0] not in body and body == node.value


def inspect_script(source: bytes) -> ScriptInfo:
    if len(source) > MAX_SCRIPT_BYTES: return ScriptInfo(False, (), (), ("SCRIPT_TOO_LARGE",))
    try:
        text = source.decode("utf-8")
        tree = ast.parse(text)
    except (UnicodeDecodeError, SyntaxError, ValueError):
        return ScriptInfo(False, (), (), ("PARSE_FAILED",))
    lines = text.splitlines()
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): imports.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0: imports.add(node.module.split(".")[0])

    workbooks, sheets, frames = set(), set(), set()
    changed = True
    while changed:  # flow-insensitive fixpoint over simple name assignments
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign): continue
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            v = node.value; kind = None
            if isinstance(v, ast.Call) and _func_name(v) in ("load_workbook", "Workbook"): kind = workbooks
            elif isinstance(v, ast.Call) and _func_name(v) == "read_excel": kind = frames
            elif isinstance(v, ast.Subscript) and isinstance(v.value, ast.Name) and v.value.id in workbooks: kind = sheets
            elif isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) and v.value.id in workbooks and v.attr == "active": kind = sheets
            elif isinstance(v, ast.Call) and _func_name(v) in ("get_sheet_by_name", "create_sheet"): kind = sheets
            elif isinstance(v, ast.Subscript) and isinstance(v.value, ast.Name) and v.value.id in frames and isinstance(v.ctx, ast.Load):
                kind = frames if not isinstance(v.slice, ast.Constant) else None
            if kind is not None:
                for n in names:
                    if n not in kind: kind.add(n); changed = True

    refs, dynamic = [], []

    def add(kind, node):
        refs.append(LiteralRef(kind, node.value, node.lineno, node.col_offset, node.end_lineno, node.end_col_offset, _simple(lines, node)))

    def literal_or_dynamic(kind, node, reason):
        if isinstance(node, ast.Constant) and isinstance(node.value, str): add(kind, node)
        elif isinstance(node, (ast.List, ast.Tuple)) and node.elts and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts):
            for e in node.elts: add(kind, e)
        else: dynamic.append(reason)

    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name):
            if node.value.id in workbooks:
                literal_or_dynamic("sheet", node.slice, "DYNAMIC_SHEET_ACCESS")
            elif node.value.id in frames and isinstance(node.ctx, ast.Load):
                if not (isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int)):
                    literal_or_dynamic("column", node.slice, "DYNAMIC_COLUMN_ACCESS")
        elif isinstance(node, ast.Call):
            name = _func_name(node)
            if name in ("load_workbook", "read_excel"):
                if node.args: literal_or_dynamic("workbook_path", node.args[0], "DYNAMIC_WORKBOOK_PATH")
                else: dynamic.append("DYNAMIC_WORKBOOK_PATH")
                for kw in node.keywords:
                    if name == "read_excel" and kw.arg == "sheet_name":
                        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int) and not isinstance(kw.value.value, bool): continue
                        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str): add("sheet", kw.value)
                        else: dynamic.append("DYNAMIC_SHEET_ACCESS")
                    if name == "read_excel" and kw.arg in ("usecols", "names", "header", "index_col"):
                        dynamic.append("UNSUPPORTED_READ_OPTION")
            elif name == "get_sheet_by_name":
                literal_or_dynamic("sheet", node.args[0] if node.args else None, "DYNAMIC_SHEET_ACCESS")
            elif name == "index" and isinstance(node.func, ast.Attribute) and len(node.args) >= 1:
                literal_or_dynamic("column", node.args[0], "DYNAMIC_COLUMN_ACCESS")
            elif name in ("save", "to_excel") and node.args:
                a = node.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.lower().endswith(_WORKBOOK_EXT): add("output_path", a)
    return ScriptInfo(True, tuple(sorted(imports)), tuple(refs), tuple(sorted(set(dynamic))))
