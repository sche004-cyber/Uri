"""Suite V: does a vision-capable model add value beyond Core's existing Tesseract OCR path?

Synthetic, license-clean images generated with PIL (deterministic). Each case is answered two ways:
  vlm  - image sent to the model through its multimodal projector
  ocr  - Core-style path: Tesseract text extraction, then the same model answers from text only
"""
from __future__ import annotations

import base64
import io
import json
import math
import random
import re
import re

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .client import chat, extract_json

TESSERACT = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _font(size):
    for name in ("segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def img_ui():
    im = Image.new("RGB", (900, 560), "#f3f3f3")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 900, 40], fill="#2b2b2b")
    d.text((14, 9), "URI Settings", fill="white", font=_font(20))
    d.rectangle([20, 60, 880, 110], fill="#fde7e9", outline="#d13438", width=2)
    d.text((36, 72), "Sync failed: token expired (code 401). Reconnect your account.", fill="#a4262c", font=_font(20))
    rows = [("Voice input", True), ("Dark theme", False), ("Gmail drafts", True), ("Auto backup", False)]
    for i, (label, on) in enumerate(rows):
        y = 150 + i * 80
        d.text((40, y), label, fill="#222", font=_font(22))
        d.rounded_rectangle([760, y, 840, y + 34], radius=17, fill="#0f6cbd" if on else "#bdbdbd")
        cx = 823 if on else 777
        d.ellipse([cx - 13, y + 4, cx + 13, y + 30], fill="white")
    return im


def img_table():
    im = Image.new("RGB", (820, 360), "white")
    d = ImageDraw.Draw(im)
    rows = [("Name", "Roll", "Marks"), ("Lhamu Bhutia", "B250412CS", "71"), ("Arjun Das", "B250388CS", "88"), ("Ritu Rai", "B250455CS", "64")]
    for r, row in enumerate(rows):
        for c, cell in enumerate(row):
            x0, y0 = 30 + c * 260, 30 + r * 70
            d.rectangle([x0, y0, x0 + 260, y0 + 70], outline="black", width=2)
            d.text((x0 + 14, y0 + 20), cell, fill="black", font=_font(24))
    im = im.rotate(2.2, expand=True, fillcolor="white")
    rnd = random.Random(3)
    px = im.load()
    for _ in range(9000):
        x, y = rnd.randrange(im.width), rnd.randrange(im.height)
        px[x, y] = (110, 110, 110)
    return im.filter(ImageFilter.GaussianBlur(0.6))


def img_chart():
    im = Image.new("RGB", (700, 460), "white")
    d = ImageDraw.Draw(im)
    vals = {"Q1": 42, "Q2": 67, "Q3": 58, "Q4": 31}
    d.line([60, 400, 660, 400], fill="black", width=2)
    d.line([60, 40, 60, 400], fill="black", width=2)
    for i, (k, v) in enumerate(vals.items()):
        x = 110 + i * 140
        d.rectangle([x, 400 - v * 5, x + 70, 400], fill="#4472c4")
        d.text((x + 20, 410), k, fill="black", font=_font(22))
    d.text((200, 8), "Library visits (thousands)", fill="black", font=_font(22))
    return im


def img_diagram():
    im = Image.new("RGB", (900, 420), "white")
    d = ImageDraw.Draw(im)
    boxes = {"Intake": (40, 160), "Review": (300, 160), "Approve": (580, 60), "Archive": (580, 280)}
    for name, (x, y) in boxes.items():
        d.rectangle([x, y, x + 180, y + 70], outline="black", width=3)
        d.text((x + 30, y + 22), name, fill="black", font=_font(22))

    def arrow(a, b, dashed=False):
        (x1, y1), (x2, y2) = a, b
        n = 18 if dashed else 1
        for i in range(n):
            if dashed and i % 2:
                continue
            t0, t1 = i / n, (i + 1) / n
            d.line([x1 + (x2 - x1) * t0, y1 + (y2 - y1) * t0, x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1], fill="black", width=3)
        ang = math.atan2(y2 - y1, x2 - x1)
        for s in (-0.45, 0.45):
            d.line([x2, y2, x2 - 18 * math.cos(ang + s), y2 - 18 * math.sin(ang + s)], fill="black", width=3)
    arrow((220, 195), (300, 195))
    arrow((480, 185), (580, 100))
    arrow((480, 210), (580, 310), dashed=True)
    d.text((540, 380), "dashed = only if rejected", fill="black", font=_font(18))
    return im


def img_form():
    im = Image.new("RGB", (760, 300), "white")
    d = ImageDraw.Draw(im)
    f = _font(24)
    d.text((30, 30), "Hostel accommodation required?", fill="black", font=f)
    for i, (label, checked) in enumerate([("Yes", False), ("No", True)]):
        x = 60 + i * 200
        d.rectangle([x, 90, x + 32, 122], outline="black", width=3)
        if checked:
            d.line([x + 5, 106, x + 13, 117], fill="black", width=4)
            d.line([x + 13, 117, x + 29, 94], fill="black", width=4)
        d.text((x + 45, 92), label, fill="black", font=f)
    d.text((30, 170), "Mess preference:", fill="black", font=f)
    for i, (label, checked) in enumerate([("Veg", True), ("Non-veg", False)]):
        x = 60 + i * 200
        d.rectangle([x, 220, x + 32, 252], outline="black", width=3)
        if checked:
            d.line([x + 5, 236, x + 13, 247], fill="black", width=4)
            d.line([x + 13, 247, x + 29, 224], fill="black", width=4)
        d.text((x + 45, 222), label, fill="black", font=f)
    return im


CASES = [
    {"id": "v01_ui_error", "img": img_ui, "q": "What error does this screen show, and what is its code? Also, which settings are switched on?",
     "check": lambda a: ("expired" in a) + ("401" in a) + ("voice" in a and "gmail" in a and ("dark" not in a or "off" in a))},
    {"id": "v02_scanned_table", "img": img_table, "q": "Who has the highest marks, and how many marks?",
     "check": lambda a: ("arjun" in a) * 2 + ("88" in a)},
    {"id": "v03_chart", "img": img_chart, "q": "Which quarter had the most library visits, and which had the fewest?",
     "check": lambda a: ("q2" in a.split("fewest")[0] if "fewest" in a else "q2" in a) * 1.5 + ("q4" in a) * 1.5},
    {"id": "v04_diagram", "img": img_diagram, "q": "In this process diagram, which step comes after Review normally, and when does Archive happen?",
     "check": lambda a: ("approve" in a) * 1.5 + ("reject" in a) * 1.5},
    {"id": "v05_form_checkbox", "img": img_form, "q": "Did the applicant ask for hostel accommodation? Which mess preference is ticked?",
     "check": lambda a: bool(re.search(r"\bno\b", a.split("mess")[0] if "mess" in a else a)) * 1.5 + ("veg" in a and "non-veg" not in a.replace("not non-veg", "")) * 1.5},
]

SYSTEM = ('Answer from the provided material only. If it cannot be determined, say so. '
          'Reply ONLY with JSON {"answer": "<answer>"}.')


def _b64(im):
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def ocr(im):
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = TESSERACT
    return pytesseract.image_to_string(im, lang="eng").strip()


def run(url, *, template_kwargs=None, model="local", modes=("vlm", "ocr")):
    out = []
    for c in CASES:
        im = c["img"]()
        for mode in modes:
            if mode == "vlm":
                content = [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + _b64(im)}},
                           {"type": "text", "text": c["q"]}]
                msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": content}]
            else:
                text = ocr(im)
                msgs = [{"role": "system", "content": SYSTEM},
                        {"role": "user", "content": f"OCR text extracted from an image:\n{text}\n\nQuestion: {c['q']}"}]
            r = chat(url, msgs, max_tokens=600, template_kwargs=template_kwargs, model=model)
            obj, _ = extract_json(r.text)
            ans = str((obj or {}).get("answer", r.text)).lower()
            raw = c["check"](ans)
            out.append({"id": f"{c['id']}_{mode}", "suite": "V", "mode": mode, "score": round(min(1.0, raw / 3), 3),
                        "answer": ans[:400], "total_s": r.get("total_s"), "prompt_tokens": r.get("prompt_tokens"),
                        "error": r.get("error")})
    return out


def save_images(folder):
    for c in CASES:
        c["img"]().save(f"{folder}/{c['id']}.png")

