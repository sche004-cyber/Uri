"""Bounded, dependency-free .xlsx structure reader.

Reads sheet names, each sheet's first non-empty row (the header) and the count
of error cells. It never evaluates formulas and never returns data cells other
than header names. Limits guard against oversized and compressed-bomb inputs;
any limit breach or malformed container yields a typed failure, never a guess.
"""
from __future__ import annotations

from dataclasses import dataclass
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
        workbook = _xml(_read(zf, "xl/workbook.xml", budget))
        rels = _xml(_read(zf, "xl/_rels/workbook.xml.rels", budget))
        targets = {r.get("Id"): r.get("Target") for r in rels.findall("pr:Relationship", _NS)}
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = _xml(_read(zf, "xl/sharedStrings.xml", budget))
            shared = [_text(si) for si in sst.findall("m:si", _NS)]
        sheet_nodes = workbook.findall("m:sheets/m:sheet", _NS)
        if len(sheet_nodes) > MAX_SHEETS: raise WorkbookReadError("XLSX_TOO_MANY_SHEETS")
        sheets = []
        for node in sheet_nodes:
            name = node.get("name")
            target = targets.get(node.get("{%s}id" % _NS["r"]))
            if not name or not target: raise WorkbookReadError("XLSX_SHEET_UNRESOLVED")
            member = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
            if member.startswith("../") or not member.startswith("xl/"): raise WorkbookReadError("XLSX_SHEET_UNRESOLVED")
            sheets.append(_sheet(name, _xml(_read(zf, member, budget)), shared))
    return WorkbookStructure(tuple(sheets))


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
    header, errors, scanned = None, 0, 0
    for row in root.iter(_M + "row"):
        cells = row.findall("m:c", _NS)
        values = {}
        for cell in cells:
            scanned += 1
            if scanned > MAX_SCANNED_CELLS: raise WorkbookReadError("XLSX_TOO_MANY_CELLS")
            if cell.get("t") == "e": errors += 1
            if header is None:
                match = _CELL_REF.fullmatch(cell.get("r") or "")
                value = _cell_value(cell, shared)
                if match and value not in (None, ""):
                    values[_col_index(match.group(1))] = value
        if header is None and values:
            if max(values) > MAX_HEADER_CELLS: raise WorkbookReadError("XLSX_HEADER_TOO_WIDE")
            header = tuple(values.get(i) for i in range(1, max(values) + 1))
    return SheetStructure(name, header or (), errors, scanned)
