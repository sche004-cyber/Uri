"""Deterministic document layout QA (research prototype, Edge Vision slot baseline).

Compares a reference PDF with a candidate PDF (for example a regenerated or converted document) and
returns machine-actionable findings. No model is involved: PyMuPDF for structure and rendering,
OpenCV/numpy for pixel-level checks. This is the baseline any small vision model must beat.

Checks: page count; page size and orientation; ink margins (left/top/right/bottom, mm); clipping (ink
touching the page edge); missing / added / moved text blocks; table rule lines (horizontal and vertical
line counts); header and footer bands; images (logos, letterheads, signatures); font size drift;
page-level visual difference.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import List

import cv2
import fitz  # PyMuPDF
import numpy as np

DPI = 72
PT_PER_MM = 72 / 25.4


@dataclass
class Finding:
    check: str
    page: int
    severity: str          # "error" | "warning"
    detail: str
    repair_hint: str = ""
    data: dict = field(default_factory=dict)


def _render(page) -> np.ndarray:
    pix = page.get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
    return np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)


def _ink_box(img: np.ndarray):
    ys, xs = np.where(img < 200)
    if len(xs) == 0:
        return None
    return xs.min(), ys.min(), xs.max(), ys.max()


def _lines(img: np.ndarray):
    inv = (img < 128).astype(np.uint8) * 255
    h = cv2.morphologyEx(inv, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (40, 1)))
    v = cv2.morphologyEx(inv, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, 40)))
    nh = cv2.connectedComponents(h)[0] - 1
    nv = cv2.connectedComponents(v)[0] - 1
    return nh, nv


def _blocks(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        text = " ".join(" ".join(s["text"] for l in b["lines"] for s in l["spans"]).split())  # whitespace-normalised
        sizes = [s["size"] for l in b["lines"] for s in l["spans"]]
        if text:
            out.append({"text": text, "bbox": b["bbox"], "size": float(np.median(sizes)) if sizes else 0.0})
    return out


def compare(ref_path: str, cand_path: str, *, margin_tol_mm: float = 3.0, move_tol_mm: float = 4.0,
            size_tol_pt: float = 1.0, diff_tol: float = 0.02) -> dict:
    t0 = time.perf_counter()
    ref, cand = fitz.open(ref_path), fitz.open(cand_path)
    f: List[Finding] = []
    if len(ref) != len(cand):
        f.append(Finding("page_count", 0, "error", f"{len(ref)} pages expected, {len(cand)} found",
                         "check pagination / page breaks", {"expected": len(ref), "found": len(cand)}))
    for i in range(min(len(ref), len(cand))):
        rp, cp = ref[i], cand[i]
        rw, rh, cw, ch = rp.rect.width, rp.rect.height, cp.rect.width, cp.rect.height
        if abs(rw - cw) > 2 or abs(rh - ch) > 2:
            orient = "orientation changed" if (rw > rh) != (cw > ch) else "page size changed"
            f.append(Finding("page_size", i + 1, "error", f"{orient}: {rw:.0f}x{rh:.0f}pt -> {cw:.0f}x{ch:.0f}pt",
                             "restore page size/orientation", {"expected": [rw, rh], "found": [cw, ch]}))
        ri, ci = _render(rp), _render(cp)
        rb, cb = _ink_box(ri), _ink_box(ci)
        if rb and cb:
            scale_r = 72 / DPI / PT_PER_MM
            rm = [rb[0], rb[1], ri.shape[1] - rb[2], ri.shape[0] - rb[3]]
            cm = [cb[0], cb[1], ci.shape[1] - cb[2], ci.shape[0] - cb[3]]
            for name, a, b in zip(("left", "top", "right", "bottom"), rm, cm):
                d = (b - a) * scale_r
                if abs(d) > margin_tol_mm:
                    f.append(Finding("margin", i + 1, "warning", f"{name} margin {a*scale_r:.1f}mm -> {b*scale_r:.1f}mm",
                                     f"adjust {name} margin", {"side": name, "delta_mm": round(d, 1)}))
            for name, v in zip(("left", "top", "right", "bottom"), cm):
                if v <= 1:
                    f.append(Finding("clipping", i + 1, "error", f"content touches the {name} page edge",
                                     "content may be cut off; check margins and scaling", {"side": name}))
        rbl, cbl = _blocks(rp), _blocks(cp)
        cmap = {}
        for b in cbl:
            cmap.setdefault(b["text"], []).append(b)
        for b in rbl:
            hits = cmap.get(b["text"])
            if not hits:
                f.append(Finding("missing_text", i + 1, "error", f'text block missing: "{b["text"][:60]}"',
                                 "re-insert the block", {"text": b["text"][:200], "bbox": b["bbox"]}))
                continue
            c = hits.pop(0)
            dx = (c["bbox"][0] - b["bbox"][0]) / PT_PER_MM
            dy = (c["bbox"][1] - b["bbox"][1]) / PT_PER_MM
            if abs(dx) > move_tol_mm or abs(dy) > move_tol_mm:
                f.append(Finding("moved_text", i + 1, "warning", f'block moved {dx:+.1f}mm, {dy:+.1f}mm: "{b["text"][:40]}"',
                                 "check spacing / alignment", {"dx_mm": round(dx, 1), "dy_mm": round(dy, 1)}))
            if abs(c["size"] - b["size"]) > size_tol_pt:
                f.append(Finding("font_size", i + 1, "warning", f'font size {b["size"]:.1f} -> {c["size"]:.1f}pt: "{b["text"][:40]}"',
                                 "restore font size", {"expected": b["size"], "found": c["size"]}))
        ref_texts = {b["text"] for b in rbl}
        for b in cbl:
            if b["text"] not in ref_texts:
                f.append(Finding("added_text", i + 1, "warning", f'unexpected text block: "{b["text"][:60]}"',
                                 "remove or verify the block", {"text": b["text"][:200]}))
        (rh_, rv_), (ch_, cv_) = _lines(ri), _lines(ci)
        if (rh_, rv_) != (ch_, cv_):
            f.append(Finding("table_rules", i + 1, "error" if (ch_ + cv_) < (rh_ + rv_) else "warning",
                             f"rule lines h/v {rh_}/{rv_} -> {ch_}/{cv_}", "restore table borders",
                             {"expected": [rh_, rv_], "found": [ch_, cv_]}))
        rimg, cimg = len(rp.get_images()), len(cp.get_images())
        if rimg != cimg:
            f.append(Finding("images", i + 1, "error", f"images {rimg} -> {cimg} (logo, letterhead or signature)",
                             "restore the missing image" if cimg < rimg else "verify the extra image",
                             {"expected": rimg, "found": cimg}))
        for band, sl in (("header", slice(0, int(ri.shape[0] * 0.1))), ("footer", slice(int(ri.shape[0] * 0.9), None))):
            if ri.shape == ci.shape:
                d = float(np.mean(np.abs(ri[sl].astype(int) - ci[sl].astype(int)) > 40))
                if d > diff_tol:
                    f.append(Finding(band, i + 1, "warning", f"{band} band differs ({d:.1%} of pixels)",
                                     f"check {band} content", {"diff_fraction": round(d, 4)}))
        if ri.shape == ci.shape:
            d = float(np.mean(np.abs(ri.astype(int) - ci.astype(int)) > 40))
            if d > diff_tol and not any(x.page == i + 1 for x in f):
                f.append(Finding("visual_diff", i + 1, "warning", f"page differs visually ({d:.1%} of pixels)",
                                 "inspect page", {"diff_fraction": round(d, 4)}))
    return {"findings": [asdict(x) for x in f], "ms": (time.perf_counter() - t0) * 1000, "pages": [len(ref), len(cand)]}
