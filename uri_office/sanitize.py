"""Render-copy sanitizer (plan §5 `sanitize.py`, §7, §9.2-9.3; A1 §A3 XLSX rules).

`make_render_copy(src, dst_dir)` reads the original once (it is never written), checks the package, and writes a
copy that LibreOffice may open without reaching the network or running anything:

Refusals (an OfficeError; nothing is written):
  * not a ZIP (an OLE compound file is an encrypted OOXML or a legacy binary file);
  * over 10,000 entries, over 500 MB uncompressed, or a compression ratio over 100 (zip bomb);
  * an encrypted ZIP entry, a CRC error, an absolute or `..` entry name;
  * any XML part with a DOCTYPE (XXE), or XML the hardened parser refuses.

Removals (each reported as a finding; the copy differs from the original only in these):
  * external relationships (`TargetMode="External"`) except http(s)/mailto hyperlinks; UNC and file targets always;
  * relationships of type attachedTemplate, subDocument, frame and externalLink; `w:altChunk` elements;
  * Word fields INCLUDETEXT, INCLUDEPICTURE, LINK, DDE and DDEAUTO (the shown result is kept, the instruction goes);
  * PowerPoint `ppaction://program`, `ppaction://ole`, `ppaction://macro` and other non-navigation actions;
  * external `href` / `xlink:href` in embedded SVG;
  * macros (`vbaProject.bin` and its signature parts);
  * XLSX: externalLink parts, `connections.xml`, query tables, data-model parts; formulas calling WEBSERVICE,
    FILTERXML, RTD, DDE (`app|topic!item`) or HYPERLINK to a non-http target are replaced by their cached value.
OLE embedded objects are kept (LibreOffice draws their stored picture and never activates them).
"""
from __future__ import annotations

import hashlib
import io
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from .errors import OfficeError

VERSION = "s1"                      # part of the preview cache key; bump on any rule change
MAX_ENTRIES = 10_000
MAX_UNCOMPRESSED = 500 * 1024 * 1024
MAX_RATIO = 100
OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

R_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
S_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
XLINK_NS = "http://www.w3.org/1999/xlink"

_DROP_REL_TYPES = ("/attachedTemplate", "/subDocument", "/frame", "/externalLink", "/externalLinkPath",
                   "/connections", "/queryTable", "/vbaProject", "/aFChunk", "/oleObject#link")
_HYPERLINK = "/hyperlink"
_SAFE_LINK = re.compile(r"^(https?://|mailto:)", re.I)
_FIELD = re.compile(r"^\s*(INCLUDETEXT|INCLUDEPICTURE|LINK|DDEAUTO|DDE|IMPORT)\b", re.I)
_PPACTION_OK = ("ppaction://hlinksldjump", "ppaction://hlinkshowjump", "ppaction://noaction",
                "ppaction://customshow", "ppaction://hlinkpres")
_XL_FUNCS = re.compile(r"\b(WEBSERVICE|FILTERXML|RTD|_xlfn\.WEBSERVICE|_xlfn\.FILTERXML)\s*\(", re.I)
_XL_DDE = re.compile(r"[A-Za-z0-9_.]+\|'?[^!]*'?!")
_XL_HYPERLINK = re.compile(r"HYPERLINK\s*\(\s*\"(?!https?://|mailto:)", re.I)
_MACRO_PARTS = re.compile(r"(^|/)vbaProject\.bin$|(^|/)vbaProjectSignature[^/]*\.bin$|(^|/)vbaData\.xml$", re.I)
_XL_DROP_PARTS = re.compile(r"^xl/(externalLinks/|connections\.xml$|queryTables/|model/|customData/)", re.I)

_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False, load_dtd=False,
                          remove_blank_text=False)

MESSAGES = {
    "external_relationship": "{n} linked item(s) were not included (they point outside the file).",
    "unc_link": "{n} link(s) to network locations were removed.",
    "field": "{n} field(s) that pull content from other files were turned into plain text.",
    "alt_chunk": "{n} imported content block(s) were not included.",
    "template_link": "The link to an attached template was removed.",
    "ppaction": "{n} slide action(s) that start programs were removed.",
    "svg_href": "{n} external reference(s) in pictures were removed.",
    "macros": "The file contains macros. They were removed from the preview and never run.",
    "xl_external": "{n} link(s) to other workbooks or data sources were removed; stored values are shown.",
    "xl_formula": "{n} formula(s) that fetch data were replaced by their stored values.",
}


@dataclass
class SanitizeResult:
    path: Path
    kind: str
    source_sha256: str
    source_size: int
    removed: dict = field(default_factory=dict)        # finding key -> count

    def findings(self) -> list:
        """[(check, severity, message)] for the findings model; warnings, because the preview differs."""
        out = []
        for k, n in sorted(self.removed.items()):
            if n:
                out.append((f"sanitize_{k}", "warning", MESSAGES[k].format(n=n)))
        return out


def _refuse(code, detail):
    raise OfficeError(code, detail, 422)


def _parse(name: str, data: bytes):
    head = data[:2048].lower()
    if b"<!doctype" in head or b"<!entity" in data.lower():
        _refuse("XML_REFUSED", "a part declares a DOCTYPE")
    try:
        return etree.fromstring(data, _PARSER)
    except etree.XMLSyntaxError:
        _refuse("XML_REFUSED", "a part is not well-formed XML")


def _ser(root) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _check_archive(raw: bytes) -> zipfile.ZipFile:
    if raw[:8] == OLE_MAGIC:
        _refuse("ENCRYPTED", "password-protected or legacy binary file")
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        _refuse("ARCHIVE_REFUSED", "not a valid Office file")
    infos = z.infolist()
    if len(infos) > MAX_ENTRIES:
        _refuse("ARCHIVE_REFUSED", "too many parts")
    total = sum(i.file_size for i in infos)
    packed = max(1, sum(i.compress_size for i in infos))
    if total > MAX_UNCOMPRESSED or total / packed > MAX_RATIO:
        _refuse("ARCHIVE_REFUSED", "the file expands too much")
    names = set()
    for i in infos:
        n = i.filename
        if i.flag_bits & 0x1:
            _refuse("ENCRYPTED", "an encrypted part")
        if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/") or ":" in n:
            _refuse("ARCHIVE_REFUSED", "a part has an unsafe name")
        if n.lower() in names:
            _refuse("ARCHIVE_REFUSED", "duplicate part names")
        names.add(n.lower())
    if z.testzip() is not None:
        _refuse("ARCHIVE_REFUSED", "a part is damaged")
    if "[Content_Types].xml" not in z.namelist():
        _refuse("ARCHIVE_REFUSED", "not an Office Open XML file")
    return z


def _rels_source(rels_name: str) -> str:
    """'word/_rels/document.xml.rels' -> 'word/document.xml'; '_rels/.rels' -> ''."""
    d, f = posixpath.split(rels_name)
    return posixpath.join(posixpath.dirname(d), f[:-5]) if f.endswith(".rels") else ""


def _target_part(rels_name: str, target: str) -> str:
    base = posixpath.dirname(_rels_source(rels_name))
    t = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(base, target))
    return t


class _Ctx:
    def __init__(self, kind):
        self.kind = kind
        self.removed: dict = {}
        self.drop_parts: set = set()

    def count(self, key, n=1):
        self.removed[key] = self.removed.get(key, 0) + n


def _clean_rels(name, root, ctx: _Ctx):
    for rel in list(root):
        typ = rel.get("Type", "")
        target = rel.get("Target", "")
        external = rel.get("TargetMode", "") == "External"
        unc = target.startswith(("\\\\", "//", "file:")) or target.lower().startswith("file:")
        drop_type = any(typ.endswith(t) for t in _DROP_REL_TYPES)
        if typ.endswith("/vbaProject"):
            root.remove(rel)
            ctx.drop_parts.add(_target_part(name, target))
            ctx.count("macros")
        elif drop_type:
            root.remove(rel)
            if not external:
                ctx.drop_parts.add(_target_part(name, target))
            if typ.endswith("/attachedTemplate"):
                ctx.count("template_link")
            elif typ.endswith(("/externalLink", "/connections", "/queryTable")):
                ctx.count("xl_external")
            elif typ.endswith("/aFChunk"):
                pass                                        # counted once per w:altChunk element
            else:
                ctx.count("external_relationship")
        elif external:
            if typ.endswith(_HYPERLINK) and _SAFE_LINK.match(target) and not unc:
                continue                                    # live in the output, never fetched while rendering
            root.remove(rel)
            ctx.count("unc_link" if unc else "external_relationship")


def _clean_word(root, ctx: _Ctx):
    w = f"{{{W_NS}}}"
    for el in list(root.iter(f"{w}altChunk")):
        el.getparent().remove(el)
        ctx.count("alt_chunk")
    for el in list(root.iter(f"{w}fldSimple")):
        if _FIELD.match(el.get(f"{w}instr", "")):
            parent, idx = el.getparent(), el.getparent().index(el)
            for child in list(el):
                parent.insert(idx, child)
                idx += 1
            parent.remove(el)
            ctx.count("field")
    for el in list(root.iter(f"{w}instrText")):
        if _FIELD.match(el.text or ""):
            el.text = " "                                   # empty instruction: the cached result stays visible
            ctx.count("field")
    for el in list(root.iter(f"{w}attachedTemplate")):
        el.getparent().remove(el)


def _clean_pptx(root, ctx: _Ctx):
    for tag in (f"{{{A_NS}}}hlinkClick", f"{{{A_NS}}}hlinkHover", f"{{{A_NS}}}hlinkMouseOver"):
        for el in list(root.iter(tag)):
            action = (el.get("action") or "").lower()
            if action and not action.startswith(_PPACTION_OK):
                el.getparent().remove(el)
                ctx.count("ppaction")


def _clean_svg(root, ctx: _Ctx):
    for el in root.iter():
        for attr in ("href", f"{{{XLINK_NS}}}href"):
            v = el.get(attr)
            if v is not None and not v.startswith(("#", "data:")):
                del el.attrib[attr]
                ctx.count("svg_href")


def _clean_sheet(root, ctx: _Ctx):
    s = f"{{{S_NS}}}"
    for c in root.iter(f"{s}c"):
        f = c.find(f"{s}f")
        if f is None or not (f.text or ""):
            continue
        t = f.text
        if _XL_FUNCS.search(t) or _XL_HYPERLINK.search(t) or (_XL_DDE.search(t) and "|" in t):
            c.remove(f)                                     # the cached <v> stays and is printed as stored
            ctx.count("xl_formula")


def _clean_workbook(root, ctx: _Ctx):
    s = f"{{{S_NS}}}"
    for el in list(root.iter(f"{s}externalReferences")):
        el.getparent().remove(el)


def _clean_content_types(root, drop: set):
    for o in list(root):
        pn = (o.get("PartName") or "").lstrip("/")
        if pn and pn in drop:
            root.remove(o)


def make_render_copy(src: Path, dst_dir: Path, kind: str) -> SanitizeResult:
    raw = Path(src).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    z = _check_archive(raw)
    ctx = _Ctx(kind)
    names = z.namelist()
    parts = {}
    for n in names:
        data = z.read(n)
        low = n.lower()
        if _MACRO_PARTS.search(n):
            ctx.drop_parts.add(n)
            ctx.count("macros")
            continue
        if kind == "xlsx" and _XL_DROP_PARTS.match(n):
            ctx.drop_parts.add(n)
            continue
        if low.endswith((".xml", ".rels", ".svg", ".vml")):
            root = _parse(n, data)
            if low.endswith(".rels"):
                _clean_rels(n, root, ctx)
            elif low.endswith(".svg"):
                _clean_svg(root, ctx)
            elif kind == "docx" and low.startswith("word/"):
                _clean_word(root, ctx)
            elif kind == "pptx" and low.startswith("ppt/"):
                _clean_pptx(root, ctx)
            elif kind == "xlsx" and low.startswith("xl/worksheets/"):
                _clean_sheet(root, ctx)
            elif kind == "xlsx" and low == "xl/workbook.xml":
                _clean_workbook(root, ctx)
            parts[n] = (root, None)
        else:
            parts[n] = (None, data)
    # Drop parts named by removed relationships, and their own .rels files.
    for n in list(parts):
        if n in ctx.drop_parts or any(n == posixpath.join(posixpath.dirname(p), "_rels",
                                                         posixpath.basename(p) + ".rels") for p in ctx.drop_parts):
            parts.pop(n)
    if ctx.drop_parts:
        ct = parts["[Content_Types].xml"][0]
        _clean_content_types(ct, ctx.drop_parts)
    if kind == "xlsx" and ctx.drop_parts & {n for n in names if _XL_DROP_PARTS.match(n)}:
        if not ctx.removed.get("xl_external"):
            ctx.count("xl_external", len([n for n in ctx.drop_parts if _XL_DROP_PARTS.match(n)]))
    if ctx.removed.get("macros"):
        ctx.removed["macros"] = 1
    dst_dir.mkdir(parents=True, exist_ok=True)
    out = dst_dir / f"render.{kind}"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zo:
        for n in names:
            if n in parts:
                root, data = parts[n]
                zo.writestr(n, _ser(root) if root is not None else data)
    out.write_bytes(buf.getvalue())
    return SanitizeResult(out, kind, sha, len(raw), ctx.removed)
