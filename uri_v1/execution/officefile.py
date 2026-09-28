"""Bounded, dependency-free .xlsx structure reader.

Reads sheet names, each sheet's first non-empty row (the header) and the count
of error cells. It never evaluates formulas and never returns data cells other
than header names. Limits guard against oversized and compressed-bomb inputs;
any limit breach or malformed container yields a typed failure, never a guess.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_RATIO = 200
MAX_SHEETS = 256
MAX_HEADER_CELLS = 512
MAX_SCANNED_CELLS = 2_000_000
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
       "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
       "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
_M = "{%s}" % _NS["m"]
_CELL_REF = re.compile(r"^([A-Z]{1,3})(\d{1,7})$")


class WorkbookReadError(ValueError):
    """Typed failure: the reason code is the message."""


@dataclass(frozen=True)
class SheetStructure:
    name: str
    header: tuple
    error_cells: int
    scanned_cells: int
    # Cells with a real, non-empty value in a row other than the header row.
    # `scanned_cells` counts every `<c>` node found, header or not, present or
    # empty -- a sheet with a header and nothing else scans the same as a
    # sheet with a header and real rows below it whose cells are all blank.
    # Finding 1 (M38 repair round 3 re-audit): that let a script produce an
    # output sheet with only its header row and still pass "has data"
    # checks built on `scanned_cells`. `data_cells` counts only cells that
    # actually hold a value, and only outside the header row, so a
    # header-only sheet reads as zero.
    data_cells: int = 0


@dataclass(frozen=True)
class WorkbookStructure:
    sheets: tuple

    @property
    def sheet_names(self) -> tuple:
        return tuple(s.name for s in self.sheets)

    def sheet(self, name):
        return next((s for s in self.sheets if s.name == name), None)

    def to_dict(self) -> dict:
        return {"sheets": [{"name": s.name, "header": list(s.header), "error_cells": s.error_cells} for s in self.sheets]}


def _col_index(letters: str) -> int:
    n = 0
    for ch in letters: n = n * 26 + (ord(ch) - 64)
    return n


def _read(zf: zipfile.ZipFile, name: str, budget: list) -> bytes:
    try: info = zf.getinfo(name)
    except KeyError: raise WorkbookReadError("XLSX_MEMBER_MISSING")
    if info.file_size > MAX_MEMBER_BYTES: raise WorkbookReadError("XLSX_MEMBER_TOO_LARGE")
    if info.compress_size and info.file_size / max(info.compress_size, 1) > MAX_RATIO: raise WorkbookReadError("XLSX_COMPRESSION_RATIO")
    budget[0] += info.file_size
    if budget[0] > MAX_TOTAL_BYTES: raise WorkbookReadError("XLSX_TOTAL_TOO_LARGE")
    with zf.open(info) as stream:
        data = stream.read(MAX_MEMBER_BYTES + 1)
    if len(data) > MAX_MEMBER_BYTES: raise WorkbookReadError("XLSX_MEMBER_TOO_LARGE")
    if b"<!DOCTYPE" in data[:4096] or b"<!ENTITY" in data[:65536]: raise WorkbookReadError("XLSX_DTD_REJECTED")
    return data


def _xml(data: bytes):
    try: return ET.fromstring(data)
    except ET.ParseError: raise WorkbookReadError("XLSX_MALFORMED_XML")


def _text(node) -> str:
    return "".join(t.text or "" for t in node.iter(_M + "t"))


def _resolve_sheet_members(zf: zipfile.ZipFile, budget: list) -> list:
    """The (sheet_name, zip_member) pairs a workbook's own relationships name,
    in declaration order. Factored out of `read_workbook_structure` so the
    differential-rerun perturbation helper below locates the exact same sheet
    member a structure read would, rather than guessing at zip layout."""
    workbook = _xml(_read(zf, "xl/workbook.xml", budget))
    rels = _xml(_read(zf, "xl/_rels/workbook.xml.rels", budget))
    targets = {r.get("Id"): r.get("Target") for r in rels.findall("pr:Relationship", _NS)}
    sheet_nodes = workbook.findall("m:sheets/m:sheet", _NS)
    if len(sheet_nodes) > MAX_SHEETS: raise WorkbookReadError("XLSX_TOO_MANY_SHEETS")
    resolved = []
    for node in sheet_nodes:
        name = node.get("name")
        target = targets.get(node.get("{%s}id" % _NS["r"]))
        if not name or not target: raise WorkbookReadError("XLSX_SHEET_UNRESOLVED")
        member = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
        if member.startswith("../") or not member.startswith("xl/"): raise WorkbookReadError("XLSX_SHEET_UNRESOLVED")
        resolved.append((name, member))
    return resolved


def _shared_strings(zf: zipfile.ZipFile, budget: list) -> list:
    if "xl/sharedStrings.xml" not in zf.namelist(): return []
    sst = _xml(_read(zf, "xl/sharedStrings.xml", budget))
    return [_text(si) for si in sst.findall("m:si", _NS)]


def read_workbook_structure(path) -> WorkbookStructure:
    try:
        with open(path, "rb") as probe:
            head = probe.read(4)
            probe.seek(0, 2); size = probe.tell()
    except OSError: raise WorkbookReadError("XLSX_UNREADABLE")
    if size > MAX_FILE_BYTES: raise WorkbookReadError("XLSX_FILE_TOO_LARGE")
    if head != b"PK\x03\x04": raise WorkbookReadError("XLSX_NOT_ZIP")
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError): raise WorkbookReadError("XLSX_NOT_ZIP")
    budget = [0]
    with zf:
        resolved = _resolve_sheet_members(zf, budget)
        shared = _shared_strings(zf, budget)
        sheets = [_sheet(name, _xml(_read(zf, member, budget)), shared) for name, member in resolved]
    return WorkbookStructure(tuple(sheets))


def workbook_content_sha256(path) -> str:
    """Digest of what a workbook *says* -- sheet names and every cell's reference,
    type and value -- and nothing else.

    The raw bytes of an .xlsx also carry the writer's save time (docProps/core.xml
    `dcterms:created`/`modified`, zip entry mtimes), so two saves of identical content
    a second apart hash differently. The differential rerun compares with this, never
    with raw bytes: a byte comparison let a hardcoded output "change" whenever the two
    runs straddled a clock second, passing intermittently.
    """
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError): raise WorkbookReadError("XLSX_NOT_ZIP")
    budget = [0]; digest = hashlib.sha256()
    with zf:
        shared = _shared_strings(zf, budget)
        for name, member in _resolve_sheet_members(zf, budget):
            digest.update(b"\x00S" + name.encode("utf-8"))
            scanned = 0
            for cell in _xml(_read(zf, member, budget)).iter(_M + "c"):
                scanned += 1
                if scanned > MAX_SCANNED_CELLS: raise WorkbookReadError("XLSX_TOO_MANY_CELLS")
                value = _cell_value(cell, shared)
                if value in (None, ""): continue
                digest.update(b"\x00C" + "\x1f".join((cell.get("r") or "", cell.get("t") or "", value)).encode("utf-8"))
    return digest.hexdigest()


def _cell_value(cell, shared):
    kind = cell.get("t")
    if kind == "inlineStr":
        node = cell.find("m:is", _NS)
        return _text(node) if node is not None else None
    value = cell.find("m:v", _NS)
    if value is None or value.text is None: return None
    if kind == "s":
        try: return shared[int(value.text)]
        except (ValueError, IndexError): raise WorkbookReadError("XLSX_SHARED_STRING")
    return value.text


def _sheet(name, root, shared) -> SheetStructure:
    header, errors, scanned, data_cells = None, 0, 0, 0
    for row in root.iter(_M + "row"):
        cells = row.findall("m:c", _NS)
        values = {}
        row_is_header_candidate = header is None
        for cell in cells:
            scanned += 1
            if scanned > MAX_SCANNED_CELLS: raise WorkbookReadError("XLSX_TOO_MANY_CELLS")
            if cell.get("t") == "e": errors += 1
            value = _cell_value(cell, shared)
            if row_is_header_candidate:
                match = _CELL_REF.fullmatch(cell.get("r") or "")
                if match and value not in (None, ""):
                    values[_col_index(match.group(1))] = value
            elif value not in (None, ""):
                data_cells += 1
        if header is None and values:
            if max(values) > MAX_HEADER_CELLS: raise WorkbookReadError("XLSX_HEADER_TOO_WIDE")
            header = tuple(values.get(i) for i in range(1, max(values) + 1))
    return SheetStructure(name, header or (), errors, scanned, data_cells)


def _find_numeric_data_cells(root, shared) -> list:
    """The cell references of every numeric value in a non-header row of
    `root`'s sheet. Uses the same "first non-empty row is the header" rule as
    `_sheet` so this never mistakes the header for data.

    Every numeric data cell is perturbed, not just one: a script reads a
    specific column (e.g. "Unit Price", not "Amount"), and perturbing an
    arbitrary cell that happens not to be in that column would leave the
    script's real input to that column untouched, making a correct script
    look non-causal (M38 repair round 3, found via the M37 qualification
    battery's E03 case, whose script reads a column other than the first
    numeric one in the row)."""
    header_seen = False
    refs = []
    for row in root.iter(_M + "row"):
        cells = row.findall("m:c", _NS)
        if not header_seen:
            if any(_cell_value(c, shared) not in (None, "") for c in cells): header_seen = True
            continue
        for cell in cells:
            if cell.get("t") in ("e", "s", "str", "inlineStr", "b"): continue
            value = cell.find("m:v", _NS)
            if value is None or value.text is None: continue
            try: float(value.text)
            except ValueError: continue
            ref = cell.get("r")
            if ref: refs.append(ref)
    return refs


def _perturb_numeric_cell(data: bytes, cell_ref: str) -> bytes:
    """Change the `<v>` text of the cell at `cell_ref` within a sheet member's
    raw bytes, leaving everything else byte-identical. Targeted string
    slicing rather than a regex substitution over the whole document: cell
    references are unique within a sheet, so locating this one occurrence of
    `r="<ref>"` and the `<v>...</v>` that immediately follows it identifies
    the exact cell an ElementTree parse would have resolved to the same ref,
    without needing a full round-trip XML rewrite."""
    marker = ('r="%s"' % cell_ref).encode()
    idx = data.find(marker)
    if idx == -1: raise WorkbookReadError("XLSX_PERTURB_CELL_NOT_FOUND")
    v_start = data.find(b"<v>", idx)
    v_end = data.find(b"</v>", v_start) if v_start != -1 else -1
    if v_start == -1 or v_end == -1: raise WorkbookReadError("XLSX_PERTURB_CELL_NOT_FOUND")
    try: num = float(data[v_start + 3:v_end])
    except ValueError: raise WorkbookReadError("XLSX_PERTURB_NOT_NUMERIC")
    bumped = num + 1
    new_text = str(int(bumped)) if bumped.is_integer() else repr(bumped)
    return data[:v_start + 3] + new_text.encode("ascii") + data[v_end:]


def make_perturbed_copy(src_path, dest_path) -> bool:
    """Write a copy of the workbook at `src_path` to `dest_path` with every
    numeric data cell in its first sheet changed by +1.

    For the differential-rerun check (M38 repair round 3, finding 1): a
    script whose output does not move when a real input value changes cannot
    have derived that output from the input it was given, whether because it
    hardcodes an answer or never actually reads the input at all. This
    perturbation is what makes that check possible without depending on any
    task-specific recompute oracle. Every numeric data cell is changed, not
    just one, so the check does not depend on knowing which column the
    script actually reads.

    Returns False, writing nothing, when the workbook has no non-header
    numeric cell to perturb (e.g. an all-text sheet) -- callers must treat
    that as UNVERIFIABLE, never as a pass or a fail, since no perturbation
    was actually exercised.
    """
    budget = [0]
    with zipfile.ZipFile(src_path) as zf:
        resolved = _resolve_sheet_members(zf, budget)
        if not resolved: return False
        _, member = resolved[0]
        shared = _shared_strings(zf, budget)
        data = _read(zf, member, budget)
        refs = _find_numeric_data_cells(_xml(data), shared)
        if not refs: return False
        new_data = data
        for ref in refs: new_data = _perturb_numeric_cell(new_data, ref)
        with zipfile.ZipFile(dest_path, "w", zipfile.ZIP_DEFLATED) as out:
            for info in zf.infolist():
                out.writestr(info, new_data if info.filename == member else zf.read(info.filename))
    return True
