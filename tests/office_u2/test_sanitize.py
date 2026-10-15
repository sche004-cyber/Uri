"""Sanitizer (AC-O2-4 structure part, AC-O2-13 refusals, F4). No engine needed."""
import hashlib
import io
import re
import zipfile

import pytest

import canaries as CN
from uri_office import sanitize as S
from uri_office.errors import OfficeError

BASE = "http://127.0.0.1:9/canary"


def parts_of(p):
    with zipfile.ZipFile(p) as z:
        return {n: z.read(n) for n in z.namelist()}


def all_text(parts):
    return b"\n".join(v for n, v in parts.items() if n.endswith((".xml", ".rels")))


def test_docx_canaries_removed_and_reported(tmp_path):
    src = CN.docx_canary(tmp_path / "c.docx", BASE)
    before = hashlib.sha256(src.read_bytes()).hexdigest()
    r = S.make_render_copy(src, tmp_path / "out", "docx")
    assert hashlib.sha256(src.read_bytes()).hexdigest() == before == r.source_sha256      # original untouched
    out = parts_of(r.path)
    text = all_text(out)
    assert BASE.encode() not in text                       # every canary URL is gone
    assert b"127.0.0.2" not in text                        # UNC targets gone
    assert b"https://example.invalid/page" in text        # http hyperlink kept
    assert b"altChunk" not in out["word/document.xml"]
    assert b"cached 0" in out["word/document.xml"]         # field results kept as text
    assert "word/vbaProject.bin" not in out
    assert r.removed["field"] == 5 and r.removed["alt_chunk"] == 1 and r.removed["macros"] == 1
    assert r.removed["template_link"] == 1 and r.removed["unc_link"] == 1
    assert r.removed["external_relationship"] == 1
    msgs = [m for _, sev, m in r.findings()]
    assert all(sev == "warning" for _, sev, _ in r.findings())
    assert any("linked item" in m for m in msgs) and any("macros" in m for m in msgs)
    assert "SENTINEL" not in " ".join(msgs)


def test_pptx_canaries(tmp_path):
    src = CN.pptx_canary(tmp_path / "c.pptx", BASE)
    r = S.make_render_copy(src, tmp_path / "out", "pptx")
    text = all_text(parts_of(r.path))
    assert BASE.encode() not in text and b"ppaction://program" not in text
    assert r.removed["ppaction"] == 1 and r.removed["external_relationship"] == 1


def test_xlsx_canaries(tmp_path):
    src = CN.xlsx_canary(tmp_path / "c.xlsx", BASE)
    r = S.make_render_copy(src, tmp_path / "out", "xlsx")
    out = parts_of(r.path)
    text = all_text(out)
    assert BASE.encode() not in text
    assert not any(n.startswith("xl/externalLinks/") for n in out) and "xl/connections.xml" not in out
    sheet = out["xl/worksheets/sheet1.xml"].decode()
    assert "WEBSERVICE" not in sheet and "excel|" not in sheet
    assert re.search(r'<c r="B2"[^>]*><v>0</v>', sheet)                # cached value kept
    assert "SUM(B1:B1)" in sheet                                        # ordinary formula untouched
    assert b"externalReferences" not in out["xl/workbook.xml"]
    assert b"externalLink1" not in out["[Content_Types].xml"]
    assert r.removed["xl_formula"] == 2 and r.removed["xl_external"] >= 1


def test_clean_file_has_no_findings_and_same_parts(tmp_path):
    import docx
    p = tmp_path / "plain.docx"
    d = docx.Document()
    d.add_paragraph("Plain memorandum")
    d.save(p)
    r = S.make_render_copy(p, tmp_path / "out", "docx")
    assert r.findings() == [] and set(parts_of(r.path)) == set(parts_of(p))


def _zip(entries, *, compress=zipfile.ZIP_DEFLATED):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compress) as z:
        for n, d in entries.items():
            z.writestr(n, d)
    return buf.getvalue()


CT = b'<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>'


@pytest.mark.parametrize("raw,code", [
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 600, "ENCRYPTED"),
    (b"just text", "ARCHIVE_REFUSED"),
    (_zip({"[Content_Types].xml": CT, "big.bin": b"\x00" * (20 * 1024 * 1024)}), "ARCHIVE_REFUSED"),   # ratio
    (_zip({"[Content_Types].xml": CT, "../evil.xml": b"<a/>"}), "ARCHIVE_REFUSED"),
    (_zip({"[Content_Types].xml": CT, "word/document.xml":
           b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///c:/windows/win.ini">]><x>&e;</x>'}),
     "XML_REFUSED"),
    (_zip({"[Content_Types].xml": CT, "word/document.xml": b"<unclosed>"}), "XML_REFUSED"),
    (_zip({"word/document.xml": b"<a/>"}), "ARCHIVE_REFUSED"),                      # no content types
], ids=["ole_encrypted", "not_zip", "zip_bomb_ratio", "dotdot_name", "doctype_xxe", "bad_xml", "no_ct"])
def test_refusals(tmp_path, raw, code):
    p = tmp_path / "x.docx"
    p.write_bytes(raw)
    with pytest.raises(OfficeError) as e:
        S.make_render_copy(p, tmp_path / "out", "docx")
    assert e.value.code == code
    assert not (tmp_path / "out").exists()


def test_too_many_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "MAX_ENTRIES", 5)
    p = tmp_path / "x.docx"
    p.write_bytes(_zip({"[Content_Types].xml": CT, **{f"p{i}.xml": b"<a/>" for i in range(6)}}))
    with pytest.raises(OfficeError) as e:
        S.make_render_copy(p, tmp_path / "out", "docx")
    assert e.value.code == "ARCHIVE_REFUSED"


def test_crc_error_refused(tmp_path):
    raw = bytearray(_zip({"[Content_Types].xml": CT, "word/document.xml": b"<a>" + b"x" * 200 + b"</a>"},
                         compress=zipfile.ZIP_STORED))
    i = raw.find(b"xxxxx")
    raw[i] = ord("y")
    p = tmp_path / "x.docx"
    p.write_bytes(bytes(raw))
    with pytest.raises(OfficeError) as e:
        S.make_render_copy(p, tmp_path / "out", "docx")
    assert e.value.code == "ARCHIVE_REFUSED"
