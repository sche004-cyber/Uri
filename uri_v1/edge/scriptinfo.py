"""Deterministic static inspection of a Python script's workbook usage.

Static only: the script is parsed, never imported or executed. The result is
conservative. Any name-based sheet/column access that cannot be resolved to a
string literal marks the script `dynamic`, which makes local repair
ineligible. Recognized patterns (openpyxl and pandas):
  workbook = load_workbook("x.xlsx") / Workbook()        -> workbook variable
  sheet = workbook["Name"] / workbook.get_sheet_by_name("Name") -> sheet reference
  frame = read_excel("x.xlsx", sheet_name="Name")          -> dataframe + sheet reference
  frame["Column"], frame[["A", "B"]] (load context)         -> column references
  <header>.index("Column")                                  -> column reference (header lookup),
                                                                only when <header> traces to a header-row
                                                                derivation such as `[c.value for c in ws[1]]`
  <x>.save("out.xlsx") / <frame>.to_excel("out.xlsx")      -> output path

An `.index(literal)` call on a receiver that is not a recognized header-row
variable is never treated as a column reference: it is marked dynamic instead,
so it cannot be silently rewritten by the literal remap or count as evidence
that the script is compatible. Likewise, a string comparison (`==`, `!=`,
`in`, `not in`) against a value that traces back to a header row -- a loop
variable over the header list, `cell.value` while iterating a sheet row, a
subscript of the header list, a method call on any of those, or the header
list itself as an `in` collection -- is marked dynamic: static inspection
cannot know whether that comparison actually matches, so the script must not
be reported compatible on the strength of it.

A name that is ever bound as a function/lambda parameter, a `for`/comprehension
target, a `with ... as` target or an `except ... as` name anywhere in the
script is never trusted for workbook/sheet/frame subscript access, even at the
occurrence that looks like the real module-level binding: static inspection
has no scope resolution, so a name that is shadowed anywhere could refer to
something else at any given use, and every access through it is marked
dynamic instead of guessing which one is safe.

Any call to `os.chdir`/`os.fchdir` marks the script dynamic on workbook-path
grounds: a script that changes the working directory can make an exact,
unchanged workbook-path literal resolve outside the workspace.
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


def _header_row_vars(tree, sheets) -> set:
    """Names bound to a header-row derivation: `<name> = [c.value for c in <sheet>[<row>]]`.

    Conservative and single-pattern on purpose: this is the only shape the
    qualified repair's `.index(...)` recognition may trust. Anything else stays
    unrecognized rather than risk treating an unrelated `.index()` call as a
    column lookup (F-1).
    """
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign): continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        v = node.value
        if not targets or not isinstance(v, ast.ListComp) or len(v.generators) != 1: continue
        gen = v.generators[0]
        target, elt, it = gen.target, v.elt, gen.iter
        if not isinstance(target, ast.Name): continue
        if not (isinstance(elt, ast.Attribute) and elt.attr == "value"
                and isinstance(elt.value, ast.Name) and elt.value.id == target.id):
            continue
        if isinstance(it, ast.Subscript) and isinstance(it.value, ast.Name) and it.value.id in sheets:
            names.update(targets)
    return names


def _header_value_vars(tree, headers) -> set:
    """Names bound to a single header value: `for h in <headers>` / `for i, h in enumerate(<headers>)`."""
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.For): continue
        it, target = node.iter, node.target
        if isinstance(target, ast.Name) and isinstance(it, ast.Name) and it.id in headers:
            names.add(target.id)
        elif (isinstance(target, ast.Tuple) and len(target.elts) == 2 and isinstance(target.elts[1], ast.Name)
              and isinstance(it, ast.Call) and _func_name(it) == "enumerate"
              and it.args and isinstance(it.args[0], ast.Name) and it.args[0].id in headers):
            names.add(target.elts[1].id)
    return names


def _row_iter_vars(tree, sheets) -> set:
    """Names bound to a single cell by iterating a sheet row directly: `for cell in ws[1]:`
    (the direct-iteration form; `_header_row_vars` covers the list-comprehension form).
    `cell.value` on such a name is a header value read at runtime, same as `_header_value_vars`.
    """
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.For): continue
        it, target = node.iter, node.target
        if (isinstance(target, ast.Name) and isinstance(it, ast.Subscript)
                and isinstance(it.value, ast.Name) and it.value.id in sheets):
            names.add(target.id)
    return names


def _binder_names(tree) -> set:
    """Names ever bound as a function/lambda parameter, a `for`/comprehension target, a
    `with ... as` target, or an `except ... as` name anywhere in the script (F-1 shadowing).
    """
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            a = node.args
            for arglist in (a.posonlyargs, a.args, a.kwonlyargs):
                names.update(x.arg for x in arglist)
            if a.vararg: names.add(a.vararg.arg)
            if a.kwarg: names.add(a.kwarg.arg)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            names.update(n.id for n in ast.walk(node.target) if isinstance(n, ast.Name))
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            names.update(n.id for n in ast.walk(node.optional_vars) if isinstance(n, ast.Name))
        elif isinstance(node, ast.ExceptHandler) and node.name:
            names.add(node.name)
    return names


def _header_scalar(node, header_values, headers, cell_vars) -> bool:
    """True when `node` is an expression that traces back to a header value read at
    runtime: a header-loop variable, `cell.value` on a row-iteration variable, a
    subscript of the header list, or a method call on any of those (F-4).
    """
    if isinstance(node, ast.Attribute) and node.attr == "value" and isinstance(node.value, ast.Name):
        return node.value.id in cell_vars
    if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id in headers:
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        return _header_scalar(node.func.value, header_values, headers, cell_vars)
    if isinstance(node, ast.Name):
        return node.id in header_values
    return False


def _str_literal_seq(node) -> bool:
    return isinstance(node, (ast.Tuple, ast.List, ast.Set)) and bool(node.elts) and all(
        isinstance(e, ast.Constant) and isinstance(e.value, str) for e in node.elts)


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

    headers = _header_row_vars(tree, sheets)
    header_values = _header_value_vars(tree, headers)
    cell_vars = _row_iter_vars(tree, sheets)
    shadowed = _binder_names(tree)

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
            name = node.value.id
            if name in shadowed and (name in workbooks or name in frames):
                # A name bound as a function parameter, loop target, `with`/`except` name
                # or comprehension variable anywhere in the script cannot be trusted for
                # workbook/sheet/frame access at any occurrence, including this one:
                # static inspection has no scope resolution to tell which binding a given
                # use refers to (F-1 shadowing).
                dynamic.append("DYNAMIC_SHEET_ACCESS" if name in workbooks else "DYNAMIC_COLUMN_ACCESS")
            elif name in workbooks:
                literal_or_dynamic("sheet", node.slice, "DYNAMIC_SHEET_ACCESS")
            elif name in frames and isinstance(node.ctx, ast.Load):
                if not (isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int)):
                    literal_or_dynamic("column", node.slice, "DYNAMIC_COLUMN_ACCESS")
        elif isinstance(node, ast.Call):
            name = _func_name(node)
            if name in ("chdir", "fchdir"):
                # A script that changes its working directory can make an unchanged,
                # exact workbook-path literal resolve to a file outside the workspace
                # (F-2): the path check alone cannot see this, so it must be dynamic.
                dynamic.append("DYNAMIC_WORKBOOK_PATH")
            elif name in ("load_workbook", "read_excel"):
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
                recv = node.func.value
                if isinstance(recv, ast.Name) and recv.id in headers and recv.id not in shadowed:
                    literal_or_dynamic("column", node.args[0], "DYNAMIC_COLUMN_ACCESS")
                else:
                    # Receiver does not trace to a header-row derivation, or does but is
                    # also shadowed elsewhere: this is not a column lookup we can trust,
                    # so it must never feed the literal remap or count as evidence the
                    # script is compatible (F-1).
                    dynamic.append("DYNAMIC_COLUMN_ACCESS")
            elif name in ("save", "to_excel") and node.args:
                a = node.args[0]
                if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.lower().endswith(_WORKBOOK_EXT): add("output_path", a)
        elif isinstance(node, ast.Compare) and len(node.ops) == 1:
            op, left, right = node.ops[0], node.left, node.comparators[0]
            if isinstance(op, (ast.Eq, ast.NotEq)):
                for side, other in ((left, right), (right, left)):
                    if (_header_scalar(side, header_values, headers, cell_vars)
                            and isinstance(other, ast.Constant) and isinstance(other.value, str)):
                        dynamic.append("HEADER_VALUE_COMPARISON"); break
                    if (_header_scalar(side, header_values, headers, cell_vars) and _str_literal_seq(other)):
                        dynamic.append("HEADER_VALUE_COMPARISON"); break
            elif isinstance(op, (ast.In, ast.NotIn)):
                if (_header_scalar(left, header_values, headers, cell_vars) and _str_literal_seq(right)):
                    # `h in ("amount", "amt")`: a header value tested against a literal set.
                    dynamic.append("HEADER_VALUE_COMPARISON")
                elif (isinstance(left, ast.Constant) and isinstance(left.value, str)
                      and isinstance(right, ast.Name) and right.id in headers):
                    # `"amount" in hdr`: a literal tested against the header list itself.
                    dynamic.append("HEADER_VALUE_COMPARISON")
    # A SCRIPT_WORKBOOK_REPAIR capability is qualified only for scripts whose
    # workbook input is statically bound through a recognized load_workbook/read_excel
    # call. Treating an unrecognized reader (read_csv, a wrapper, a Path expression) or
    # a script that never reads the input as COMPATIBLE would permit an arbitrary local
    # attempt and could let weak output-only acceptance criteria certify fabricated data.
    if not any(r.kind == "workbook_path" for r in refs):
        dynamic.append("WORKBOOK_ACCESS_UNPROVEN")
    return ScriptInfo(True, tuple(sorted(imports)), tuple(refs), tuple(sorted(set(dynamic))))
