"""Synthetic layout-QA benchmark for layout_qa.compare (deterministic baseline).

Builds an institutional letter (letterhead image, title, body, bordered table, signature image,
header and footer) in two templates, then perturbed copies, each with one known defect, plus
unchanged and sub-tolerance-jitter controls. Scores detections against the known defect.
Usage: python bench.py --out results.json
"""
from __future__ import annotations

import argparse
import io
import json
import tempfile
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

from layout_qa import compare

MM = 72 / 25.4


def _png(w, h, color):
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    d.rectangle([2, 2, w - 3, h - 3], outline=color, width=4)
    d.ellipse([w // 4, h // 4, 3 * w // 4, 3 * h // 4], fill=color)
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


LOGO, SIGN = _png(160, 60, "navy"), _png(140, 50, "black")


def build(path, *, template=0, shift_x=0.0, shift_y_body=0.0, drop_block=False, table_border=True, font_delta=0.0,
          landscape=False, extra_page=False, logo=True, header="Office of the Registrar", clip=False, sign=True,
          jitter=0.0):
    doc = fitz.open()
    w, h = (842, 595) if landscape else (595, 842)
    p = doc.new_page(width=w, height=h)
    x0 = 25 * MM + shift_x * MM + jitter * MM
    fs = 11 + font_delta
    p.insert_text((x0, 12 * MM), header, fontsize=9)
    if logo:
        p.insert_image(fitz.Rect(x0, 18 * MM, x0 + 45 * MM, 34 * MM), stream=LOGO)
    title = "Office Order No. 14/2026" if template == 0 else "Notice: Revised Examination Schedule"
    p.insert_text((x0, 46 * MM), title, fontsize=14)
    body = ["The following members are nominated to the purchase committee.",
            "The committee will meet every Monday at 11 am in the Senate Hall.",
            "This order comes into effect immediately."]
    y = 58 * MM + shift_y_body * MM
    for i, line in enumerate(body):
        if drop_block and i == 1:
            y += 8 * MM
            continue
        if clip and i == 0:
            line = line + " " + "and all departments are requested to circulate it widely among staff members today."
        p.insert_text((x0, y), line, fontsize=fs)
        y += 8 * MM
    ty = y + 6 * MM
    rows = [("Name", "Department", "Role"), ("A. Rao", "Physics", "Chair"), ("S. Das", "Chemistry", "Member")]
    cw = [45 * MM, 50 * MM, 35 * MM]
    for r, row in enumerate(rows):
        cx = x0
        for c, cell in enumerate(row):
            p.insert_text((cx + 2 * MM, ty + r * 9 * MM + 6 * MM), cell, fontsize=fs - 1)
            if table_border:
                p.draw_rect(fitz.Rect(cx, ty + r * 9 * MM, cx + cw[c], ty + (r + 1) * 9 * MM), color=(0, 0, 0), width=0.8)
            cx += cw[c]
    sy = ty + 3 * 9 * MM + 20 * MM
    if sign:
        p.insert_image(fitz.Rect(x0 + 100 * MM, sy, x0 + 140 * MM, sy + 14 * MM), stream=SIGN)
    p.insert_text((x0 + 100 * MM, sy + 20 * MM), "Registrar", fontsize=fs)
    p.insert_text((x0, h - 12 * MM), "Page 1 of 1", fontsize=8)
    if extra_page:
        doc.new_page(width=w, height=h).insert_text((x0, 30 * MM), "Annexure", fontsize=11)
    doc.save(path)


CASES = [
    ("identical", {}, []),
    ("jitter_0_5mm", {"jitter": 0.5}, []),
    ("margin_shift", {"shift_x": 10}, ["margin", "moved_text"]),
    ("clipping", {"clip": True}, ["clipping"]),
    ("missing_block", {"drop_block": True}, ["missing_text"]),
    ("table_borders_lost", {"table_border": False}, ["table_rules"]),
    ("font_drift", {"font_delta": 2}, ["font_size"]),
    ("orientation", {"landscape": True}, ["page_size"]),
    ("extra_page", {"extra_page": True}, ["page_count"]),
    ("logo_removed", {"logo": False}, ["images"]),
    ("signature_removed", {"sign": False}, ["images"]),
    ("header_changed", {"header": "Office of the Dean"}, ["missing_text"]),
    ("spacing_shift", {"shift_y_body": 8}, ["moved_text"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = []
    with tempfile.TemporaryDirectory() as d:
        for template in (0, 1):
            ref = str(Path(d) / f"ref{template}.pdf")
            build(ref, template=template)
            for name, kw, expected in CASES:
                cand = str(Path(d) / f"{name}{template}.pdf")
                build(cand, template=template, **kw)
                r = compare(ref, cand)
                got = sorted({x["check"] for x in r["findings"]})
                tp = [e for e in expected if e in got]
                rows.append({"case": name, "template": template, "expected": expected, "detected": got,
                             "missed": [e for e in expected if e not in got],
                             "false_positive_findings": len(r["findings"]) if not expected else 0,
                             "ms": round(r["ms"], 1), "findings": r["findings"][:6], "ok": len(tp) == len(expected)})
    defect = [r for r in rows if r["expected"]]
    ctrl = [r for r in rows if not r["expected"]]
    summary = {"defect_cases": len(defect), "defects_detected": sum(r["ok"] for r in defect),
               "control_cases": len(ctrl), "controls_clean": sum(r["false_positive_findings"] == 0 for r in ctrl),
               "median_ms": sorted(r["ms"] for r in rows)[len(rows) // 2], "max_ms": max(r["ms"] for r in rows)}
    Path(a.out).write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")
    print(json.dumps(summary))
    for r in rows:
        if not r["ok"] or r["false_positive_findings"]:
            print("MISS/FP", r["case"], r["template"], r["missed"], r["detected"])


if __name__ == "__main__":
    main()
