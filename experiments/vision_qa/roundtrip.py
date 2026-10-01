"""Real conversion check: reference PDF -> URI's own PDF-to-DOCX converter -> Microsoft Word renders the
DOCX back to PDF -> layout_qa.compare(reference, rendered). Shows what the deterministic baseline finds on
genuine conversion damage (not synthetic perturbations). Word is driven through COM, invisible, read-only.
Usage: python roundtrip.py --out roundtrip.json
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from uri_core.services.pdf_layout_converter import convert_pdf_to_docx_preserving_layout  # noqa: E402
from bench import build  # noqa: E402
from layout_qa import compare  # noqa: E402


def word_to_pdf(docx: str, pdf: str):
    import win32com.client
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(docx, ReadOnly=True, AddToRecentFiles=False)
        doc.SaveAs2(pdf, FileFormat=17)   # wdFormatPDF
        doc.Close(False)
    finally:
        word.Quit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = []
    with tempfile.TemporaryDirectory() as d:
        for template in (0, 1):
            for variant, kw in (("portrait", {}), ("landscape", {"landscape": True})):
                ref = str(Path(d) / f"ref{template}{variant}.pdf")
                docx = str(Path(d) / f"conv{template}{variant}.docx")
                back = str(Path(d) / f"back{template}{variant}.pdf")
                build(ref, template=template, **kw)
                t = time.perf_counter()
                conv = convert_pdf_to_docx_preserving_layout(ref, docx)
                conv_ms = (time.perf_counter() - t) * 1000
                if conv.get("status") != "success":
                    rows.append({"template": template, "variant": variant, "convert": conv}); continue
                t = time.perf_counter()
                word_to_pdf(docx, back)
                render_ms = (time.perf_counter() - t) * 1000
                r = compare(ref, back)
                rows.append({"template": template, "variant": variant, "convert_ms": round(conv_ms),
                             "word_render_ms": round(render_ms), "qa_ms": round(r["ms"], 1),
                             "findings": r["findings"]})
    Path(a.out).write_text(json.dumps(rows, indent=1), encoding="utf-8")
    for r in rows:
        print(r.get("template"), r.get("variant"), r.get("qa_ms"), [(f["check"], f["detail"][:70]) for f in r.get("findings", [])][:8])


if __name__ == "__main__":
    main()
