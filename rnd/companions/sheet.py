"""Builds a labelled contact sheet from captured frames."""
import sys, os
from PIL import Image, ImageDraw

def build(out, items, cols, cell=380, label_h=26):
    rows = (len(items) + cols - 1) // cols
    W, H = cols * cell, rows * (cell + label_h)
    sheet = Image.new("RGB", (W, H), (8, 7, 11))
    d = ImageDraw.Draw(sheet)
    for i, (path, label) in enumerate(items):
        c, r = i % cols, i // cols
        x, y = c * cell, r * (cell + label_h)
        if os.path.exists(path):
            im = Image.open(path).convert("RGB").resize((cell, cell), Image.LANCZOS)
            sheet.paste(im, (x, y + label_h))
        d.text((x + 7, y + 7), label, fill=(226, 218, 210))
    sheet.save(out)
    print(out, sheet.size)

if __name__ == "__main__":
    base, out, cols = sys.argv[1], sys.argv[2], int(sys.argv[3])
    items = []
    for spec in sys.argv[4:]:
        f, lab = spec.split("=", 1)
        items.append((os.path.join(base, f), lab))
    build(out, items, cols)
