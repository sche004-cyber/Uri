"""OD-U11 investigation (owner, 2026-10-15): can PDF tables be extracted to Excel with engines already on this PC, without
installing pdfplumber or anything else? Nothing installed; nothing printed; synthetic documents only.

Method tested: pypdf (BSD, installed) text positions via `extract_text(visitor_text=...)`, then a deterministic
layout step: group text runs into rows by baseline (y within a tolerance), then into columns by clustering the x
starts of runs across all rows. Ground truth: the synthetic tables the generator wrote.

    python -I table_spike.py <pdf> <truth.json> <out.json>
"""
import json
import sys
import time

import pypdf


def runs(pdf):
    r = pypdf.PdfReader(pdf)
    out = []
    for pn, page in enumerate(r.pages, 1):
        items = []

        def vis(text, cm, tm, font, size):
            t = text.strip()
            if t:
                x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
                y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
                items.append((round(x, 1), round(y, 1), t))
        page.extract_text(visitor_text=vis)
        out.append((pn, items))
    return out


def rows_of(items, ytol=2.0):
    rows = []
    for x, y, t in sorted(items, key=lambda i: (-i[1], i[0])):
        if rows and abs(rows[-1][0] - y) <= ytol:
            rows[-1][1].append((x, t))
        else:
            rows.append([y, [(x, t)]])
    return [sorted(cells) for _, cells in rows]


def columns(rows, xtol=6.0):
    starts = sorted(x for r in rows for x, _ in r)
    cols = []
    for x in starts:
        if cols and x - cols[-1][-1] <= xtol:
            cols[-1].append(x)
        else:
            cols.append([x])
    return [sum(c) / len(c) for c in cols if len(c) >= 2]


def grid(rows, cols):
    out = []
    for r in rows:
        line = [""] * len(cols)
        for x, t in r:
            k = min(range(len(cols)), key=lambda i: abs(cols[i] - x))
            line[k] = (line[k] + " " + t).strip()
        out.append(line)
    return out


def main():
    pdf, truth_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    truth = json.loads(open(truth_path, encoding="utf-8").read())
    t0 = time.perf_counter()
    all_rows = []
    for pn, items in runs(pdf):
        all_rows += rows_of(items)
    cols = columns(all_rows)
    g = grid(all_rows, cols)
    ms = round((time.perf_counter() - t0) * 1000)
    want = [[str(c) for c in r] for r in truth["rows"]]
    found = 0
    for w in want:
        if w in g:
            found += 1
    header = truth["header"]
    res = {"pdf": pdf, "ms": ms, "columns_detected": len(cols), "columns_expected": len(header),
           "rows_expected": len(want), "rows_exact": found, "row_accuracy": round(found / len(want), 3),
           "header_found": header in g, "sample": g[:6]}
    open(out_path, "w", encoding="utf-8").write(json.dumps(res, indent=1))
    print(json.dumps({k: v for k, v in res.items() if k != "sample"}))


if __name__ == "__main__":
    main()
