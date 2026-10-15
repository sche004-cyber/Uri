"""Synthetic administrative fixtures for the O2 real-application runs (owner OD-U7: synthetic only).

    python -B harness\\make_fixtures.py <run-name>

Reuses the accepted generator docs/office/unified/evidence/o2_live_20261015/fixtures.py (invented names and numbers)
for the Word, PowerPoint and Excel files. The 60-page tender PDF is written directly as a plain text PDF (Helvetica,
one "Clause N" heading per page) so no Office engine is used to prepare inputs. A corrupt .docx (random bytes) is
the failure-recovery input. Writes fixtures/<run>/docs/* and fixtures/<run>/fixtures.json with SHA-256 of each.
"""
import hashlib, json, os, pathlib, sys, zlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Fixtures (documents, saved outputs, redirected profile) stay under the user profile: the Office service only
# opens files inside the user home by default (M1 AC7, finding UX-ROOT-1), and C: is short of space, so only
# these small files live there; runtime, build and evidence are on D:.
FXR = pathlib.Path(r"C:\Users\cheta\uri-o2r-fixtures")
RUN = sys.argv[1]
GEN = ROOT / "candidate/docs/office/unified/evidence/o2_live_20261015"
sys.path.insert(0, str(GEN))
import fixtures as F  # noqa: E402

D = FXR / f"{RUN}/docs"
D.mkdir(parents=True, exist_ok=True)
OUTDIR = FXR / f"{RUN}/saved"
OUTDIR.mkdir(parents=True, exist_ok=True)


def text_pdf(path, pages):
    objs = []

    def add(b):
        objs.append(b)
        return len(objs)
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids, content_ids = [], []
    pages_id_placeholder = len(objs) + 1 + 2 * len(pages)
    for lines in pages:
        stream = ["BT /F1 12 Tf 72 770 Td 16 TL"]
        for ln in lines:
            stream.append("(" + ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj T*")
        stream.append("ET")
        data = zlib.compress("\n".join(stream).encode("latin-1"))
        cid = add(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(data) + data + b"\nendstream")
        pid = add(b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 %d 0 R >> >> "
                  b"/Contents %d 0 R >>" % (pages_id_placeholder, font, cid))
        page_ids.append(pid)
        content_ids.append(cid)
    pages_id = add(b"<< /Type /Pages /Kids [" + b" ".join(b"%d 0 R" % i for i in page_ids) + b"] /Count %d >>" % len(page_ids))
    assert pages_id == pages_id_placeholder
    catalog = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, b in enumerate(objs, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + b + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offsets:
        out += b"%010d 00000 n \n" % o
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, catalog, xref)
    path.write_bytes(bytes(out))


def main():
    files = {
        "letter": D / "Letter to District Collector.docx",
        "order": D / "Office Order 41.docx",
        "report": D / "Annual Report 2025-26.docx",
        "deck": D / "Quarterly Review.pptx",
        "budget": D / "Budget 2026-27.xlsx",
        "tender_pdf": D / "Tender Document 2026-07.pdf",
        "corrupt": D / "Damaged minutes.docx",
    }
    F.official_letter(files["letter"])
    F.office_order(files["order"])
    F.report20(files["report"])
    F.deck11(files["deck"])
    F.budget_workbook(files["budget"])
    pages = []
    for n in range(1, 61):
        lines = [f"Tender Document 2026-07  -  page {n} of 60", "", f"Clause {n}. Conditions of the tender"]
        lines += [f"{n}.{k} The bidder shall comply with condition {k} of clause {n} of this tender." for k in range(1, 30)]
        pages.append(lines)
    text_pdf(files["tender_pdf"], pages)
    files["corrupt"].write_bytes(b"PK\x03\x04" + os.urandom(40000))
    rec = {k: {"path": str(v), "sha256": hashlib.sha256(v.read_bytes()).hexdigest(), "bytes": v.stat().st_size}
           for k, v in files.items()}
    rec["_saved_dir"] = str(OUTDIR)
    (FXR / f"{RUN}/fixtures.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps(rec, indent=1))


if __name__ == "__main__":
    main()
