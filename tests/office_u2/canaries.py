"""Synthetic canary documents for the sanitizer and the isolation tests (AC-O2-4, F1; A1 §A3 XLSX canaries).

Every external reference points at `base` (an HTTP canary server on 127.0.0.1) or at the SMB canary host
`\\\\127.0.0.2\\canary`. Built with python-docx / python-pptx / openpyxl, then edited at the XML level.
"""
from __future__ import annotations

import io
import re
import struct
import zipfile
import zlib
from pathlib import Path

UNC = r"\\127.0.0.2\canary"


def png() -> bytes:
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x00\x80\xff" * 8 for _ in range(8))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def rewrite(path: Path, fn):
    with zipfile.ZipFile(path) as z:
        infos = z.infolist()
        parts = {i.filename: z.read(i.filename) for i in infos}
    fn(parts)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        seen = set()
        for i in infos:
            if i.filename in parts:
                z.writestr(i.filename, parts[i.filename])
                seen.add(i.filename)
        for n, d in parts.items():
            if n not in seen:
                z.writestr(n, d)
    path.write_bytes(buf.getvalue())


def _add_rel(rels: bytes, rid: str, typ: str, target: str, external=True) -> bytes:
    mode = ' TargetMode="External"' if external else ""
    return rels.replace(b"</Relationships>",
                        f'<Relationship Id="{rid}" Type="{typ}" Target="{target}"{mode}/></Relationships>'.encode())


R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def docx_canary(path: Path, base: str, text="SENTINEL-CONTENT-7f3a") -> Path:
    import docx
    d = docx.Document()
    d.add_heading("Canary letter", 1)
    d.add_paragraph(text)
    pic = path.with_suffix(".png")
    pic.write_bytes(png())
    d.add_picture(str(pic))
    d.add_paragraph("after picture")
    d.save(path)
    pic.unlink()

    def edit(parts):
        doc = parts["word/document.xml"].decode()
        rels = parts["word/_rels/document.xml.rels"]
        # 1 linked picture: the embedded picture becomes an external link
        doc = re.sub(r'r:embed="(rId\d+)"', 'r:link="rIdC1"', doc, count=1)
        rels = _add_rel(rels, "rIdC1", f"{R}/image", f"{base}/linked.png")
        # 2 INCLUDEPICTURE, 3 INCLUDETEXT (UNC), 4 LINK, 5 DDEAUTO fields
        fields = "".join(
            f'<w:p><w:fldSimple w:instr=\' {instr} \'><w:r><w:t>cached {k}</w:t></w:r></w:fldSimple></w:p>'
            for k, instr in enumerate([f'INCLUDEPICTURE "{base}/field.png" \\d',
                                       f'INCLUDETEXT "{UNC}\\\\inc.docx"',
                                       f'LINK Excel.Sheet.12 "{base}/link.xlsx" "Sheet1!R1C1"',
                                       'DDEAUTO excel "C:\\\\x.xlsx" "R1C1"']))
        # complex-field form of INCLUDEPICTURE
        fields += ('<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> '
                   f'INCLUDEPICTURE "{base}/complex.png" \\d </w:instrText></w:r><w:r><w:fldChar '
                   'w:fldCharType="separate"/></w:r><w:r><w:t>complex cached</w:t></w:r><w:r><w:fldChar '
                   'w:fldCharType="end"/></w:r></w:p>')
        # 6 altChunk with an external target
        fields += '<w:altChunk r:id="rIdC2"/>'
        rels = _add_rel(rels, "rIdC2", f"{R}/aFChunk", f"{base}/chunk.html")
        # 7 hyperlinks: http stays, UNC goes
        fields += ('<w:p><w:hyperlink r:id="rIdC3"><w:r><w:t>web link</w:t></w:r></w:hyperlink>'
                   '<w:hyperlink r:id="rIdC4"><w:r><w:t>unc link</w:t></w:r></w:hyperlink></w:p>')
        rels = _add_rel(rels, "rIdC3", f"{R}/hyperlink", "https://example.invalid/page")
        rels = _add_rel(rels, "rIdC4", f"{R}/hyperlink", UNC + r"\share.docx")
        doc = doc.replace("<w:sectPr", fields + "<w:sectPr", 1)
        parts["word/document.xml"] = doc.encode()
        parts["word/_rels/document.xml.rels"] = rels
        # 8 attached template (settings.xml.rels)
        settings = parts["word/settings.xml"].decode()
        settings = re.sub(r"(<w:settings[^>]*>)", r'\1<w:attachedTemplate r:id="rIdT1"/>', settings, count=1)
        if 'xmlns:r=' not in settings[:600]:
            settings = settings.replace("<w:settings ", f'<w:settings xmlns:r="{R}" ', 1)
        parts["word/settings.xml"] = settings.encode()
        parts["word/_rels/settings.xml.rels"] = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.'
            b'openxmlformats.org/package/2006/relationships"></Relationships>')
        parts["word/_rels/settings.xml.rels"] = _add_rel(parts["word/_rels/settings.xml.rels"], "rIdT1",
                                                          f"{R}/attachedTemplate", f"{base}/template.dotx")
        # 9 macros present
        parts["word/vbaProject.bin"] = b"\xd0\xcf\x11\xe0fake-vba"
    rewrite(path, edit)
    return path


def pptx_canary(path: Path, base: str) -> Path:
    from pptx import Presentation
    from pptx.util import Inches
    p = Presentation()
    s = p.slides.add_slide(p.slide_layouts[5])
    s.shapes.title.text = "Canary deck"
    pic = path.with_suffix(".png")
    pic.write_bytes(png())
    s.shapes.add_picture(str(pic), Inches(1), Inches(2))
    p.save(path)
    pic.unlink()

    def edit(parts):
        slide = parts["ppt/slides/slide1.xml"].decode()
        rels = parts["ppt/slides/_rels/slide1.xml.rels"]
        slide = re.sub(r'r:embed="(rId\d+)"', 'r:link="rIdC1"', slide, count=1)
        rels = _add_rel(rels, "rIdC1", f"{R}/image", f"{base}/slide_linked.png")
        # a program-launch action on the title
        slide = slide.replace("<p:cNvPr id=\"2\" name=\"Title 1\"/>",
                              '<p:cNvPr id="2" name="Title 1"><a:hlinkClick r:id="" '
                              'action="ppaction://program"/></p:cNvPr>', 1)
        parts["ppt/slides/slide1.xml"] = slide.encode()
        parts["ppt/slides/_rels/slide1.xml.rels"] = rels
    rewrite(path, edit)
    return path


def xlsx_canary(path: Path, base: str) -> Path:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws["A1"] = "Region"
    ws["B1"] = 10
    ws["B2"] = "=WEBSERVICE(\"%s/ws\")" % base
    ws["B3"] = "=SUM(B1:B1)"
    wb.save(path)

    def edit(parts):
        sheet = parts["xl/worksheets/sheet1.xml"].decode()
        # cached values, as Excel would store them
        sheet = re.sub(r'(<c r="B2"[^>]*>)<f>(.*?)</f>(<v>.*?</v>)?', r'\1<f>\2</f><v>0</v>', sheet)
        # a DDE formula and an external-workbook formula
        sheet = sheet.replace("</sheetData>",
                              '<row r="4"><c r="B4"><f>excel|\'C:\\x.xlsx\'!R1C1</f><v>7</v></c>'
                              '<c r="C4"><f>[1]Sheet1!A1</f><v>8</v></c></row></sheetData>')
        parts["xl/worksheets/sheet1.xml"] = sheet.encode()
        wbx = parts["xl/workbook.xml"].decode()
        wbx = wbx.replace("</workbook>", '<externalReferences><externalReference r:id="rIdX1"/>'
                                         '</externalReferences></workbook>')
        root_tag = wbx[wbx.index("<workbook"):wbx.index(">", wbx.index("<workbook"))]
        if "xmlns:r=" not in root_tag:
            wbx = wbx.replace("<workbook ", f'<workbook xmlns:r="{R}" ', 1)
        parts["xl/workbook.xml"] = wbx.encode()
        rels = parts["xl/_rels/workbook.xml.rels"]
        rels = _add_rel(rels, "rIdX1", f"{R}/externalLink", "externalLinks/externalLink1.xml", external=False)
        rels = _add_rel(rels, "rIdX2", f"{R}/connections", "connections.xml", external=False)
        parts["xl/_rels/workbook.xml.rels"] = rels
        parts["xl/externalLinks/externalLink1.xml"] = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><externalLink xmlns="http://schemas.'
            b'openxmlformats.org/spreadsheetml/2006/main" xmlns:r="' + R.encode() + b'"><externalBook r:id="rId1">'
            b'<sheetNames><sheetName val="Sheet1"/></sheetNames></externalBook></externalLink>')
        parts["xl/externalLinks/_rels/externalLink1.xml.rels"] = _add_rel(
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.'
            b'openxmlformats.org/package/2006/relationships"></Relationships>', "rId1",
            f"{R}/externalLinkPath", f"{base}/other.xlsx")
        parts["xl/connections.xml"] = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><connections xmlns="http://schemas.'
            b'openxmlformats.org/spreadsheetml/2006/main"><connection id="1" name="q" type="4" '
            b'refreshOnLoad="1"><webPr url="' + base.encode() + b'/query"/></connection></connections>')
        ct = parts["[Content_Types].xml"].decode().replace(
            "</Types>",
            '<Override PartName="/xl/externalLinks/externalLink1.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.spreadsheetml.externalLink+xml"/><Override PartName="/xl/connections.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.connections+xml"/></Types>')
        parts["[Content_Types].xml"] = ct.encode()
    rewrite(path, edit)
    return path


def docx_webdav_canary(path: Path, port: int) -> Path:
    r"""WebDAV form of the Word canary (plan F1; not run in the first live runs). UNC paths of the form
    \\127.0.0.1@<port>\DavWWWRoot\... make Windows' WebDAV redirector (the WebClient service) send HTTP requests to
    the canary server: a linked picture, INCLUDEPICTURE and INCLUDETEXT fields, and a hyperlink."""
    import docx
    dav = "\\\\127.0.0.1@%d\\DavWWWRoot\\canary" % port
    d = docx.Document()
    d.add_paragraph("WebDAV canary letter")
    pic = path.with_suffix(".png")
    pic.write_bytes(png())
    d.add_picture(str(pic))
    d.save(path)
    pic.unlink()

    def edit(parts):
        doc = parts["word/document.xml"].decode()
        rels = parts["word/_rels/document.xml.rels"]
        doc = re.sub(r'r:embed="(rId\d+)"', 'r:link="rIdW1"', doc, count=1)
        rels = _add_rel(rels, "rIdW1", f"{R}/image", dav + "\\linked.png")
        instrs = ['INCLUDEPICTURE "%s\\\\field.png" \\d' % dav.replace("\\", "\\\\"),
                  'INCLUDETEXT "%s\\\\inc.docx"' % dav.replace("\\", "\\\\")]
        fields = "".join(f"<w:p><w:fldSimple w:instr=' {instr} '><w:r><w:t>cached {k}</w:t></w:r></w:fldSimple></w:p>"
                         for k, instr in enumerate(instrs))
        fields += '<w:p><w:hyperlink r:id="rIdW2"><w:r><w:t>dav link</w:t></w:r></w:hyperlink></w:p>'
        rels = _add_rel(rels, "rIdW2", f"{R}/hyperlink", dav + "\\share.docx")
        doc = doc.replace("<w:sectPr", fields + "<w:sectPr", 1)
        parts["word/document.xml"] = doc.encode()
        parts["word/_rels/document.xml.rels"] = rels
    rewrite(path, edit)
    return path

