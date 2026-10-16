"""PDF text worker (amendment A1 §A3). Standalone: imports only the standard library and pypdf (BSD).
Run by the service as `python -I <run copy of this file> <work root>` inside a Job Object, so a hostile PDF that
crashes or hangs pypdf takes down only this process. No PDF script, launch action or attachment is run or extracted.

Protocol: one JSON object per line on stdin, one per line on stdout.
  {"id", "op": "info", "pdf"}            -> {id, ok, pages, encrypted, outline: [{title, level, page}],
                                             fonts: [{name, embedded}], page_boxes: [[w, h], ...]}
  {"id", "op": "spans", "pdf", "page"}   -> {id, ok, box: [x0, y0, x1, y1], spans: [{x, y, size, chars}]}
  {"id", "op": "search", "pdf", "text"}  -> {id, ok, matches: [{page, context}], truncated, text_pages}
  {"id", "op": "risk", "pdf"}            -> {id, ok, javascript, launch, remote_goto, unsafe_uri, embedded_files,
                                             web_uri}  (counts only)
  {"id", "op": "placeholders", "pdf"}    -> {id, ok, pages: [{page, count}]}  (counts of «…», {{…}}, [NAME] tokens)
  {"id", "op": "quit"}
`spans` carries positions, sizes and character counts only, never text (validation needs no content). `search`
returns at most 50 matches with 60 characters of context each; the owner asked for them.
"""
import json
import os
import re
import sys

import pypdf

MAX_MATCHES = 50
CONTEXT = 60


def norm(p):
    return os.path.normcase(os.path.realpath(p))


def inside(p, root):
    try:
        return isinstance(p, str) and os.path.commonpath([norm(p), root]) == root
    except ValueError:
        return False


def reply(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


_cache = {"path": None, "reader": None}


def reader(path):
    if _cache["path"] != path:
        _cache["reader"] = pypdf.PdfReader(path, strict=False)
        _cache["path"] = path
    return _cache["reader"]


def outline(r):
    out = []

    def walk(items, level):
        for it in items:
            if isinstance(it, list):
                walk(it, level + 1)
                continue
            try:
                page = r.get_destination_page_number(it) + 1
            except Exception:  # noqa: BLE001
                page = None
            out.append({"title": str(getattr(it, "title", "") or "")[:200], "level": level, "page": page})
            if len(out) >= 500:
                return
    try:
        walk(r.outline, 1)
    except Exception:  # noqa: BLE001 - a broken outline is not fatal
        pass
    return out[:500]


def fonts(r):
    seen = {}
    for page in r.pages[:300]:
        try:
            res = page.get("/Resources") or {}
            fdict = res.get_object().get("/Font") if res else None
            if not fdict:
                continue
            for _, ref in fdict.get_object().items():
                f = ref.get_object()
                base = str(f.get("/BaseFont", "")).lstrip("/")
                name = base.split("+", 1)[1] if len(base) > 7 and base[6] == "+" else base
                desc = f.get("/FontDescriptor")
                if desc is None and f.get("/DescendantFonts"):
                    desc = f["/DescendantFonts"].get_object()[0].get_object().get("/FontDescriptor")
                emb = False
                if desc is not None:
                    d = desc.get_object()
                    emb = any(k in d for k in ("/FontFile", "/FontFile2", "/FontFile3"))
                if name:
                    seen[name] = seen.get(name, False) or emb
        except Exception:  # noqa: BLE001
            continue
    return [{"name": n[:100], "embedded": e} for n, e in sorted(seen.items())]


def spans(r, n):
    page = r.pages[n - 1]
    box = [float(v) for v in page.mediabox]
    items = []

    def vis(text, cm, tm, font, size):
        t = text.strip()
        if t:
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            scale = (tm[0] ** 2 + tm[1] ** 2) ** 0.5 * ((cm[0] ** 2 + cm[1] ** 2) ** 0.5)
            items.append({"x": round(x, 1), "y": round(y, 1), "size": round(size * scale, 2), "chars": len(t)})
    page.extract_text(visitor_text=vis)
    return box, items[:5000]


def search(r, text):
    needle = " ".join(text.split()).lower()
    matches, text_pages = [], 0
    for i, page in enumerate(r.pages):
        try:
            hay = " ".join((page.extract_text() or "").split())
        except Exception:  # noqa: BLE001
            continue
        if hay:
            text_pages += 1
        low = hay.lower()
        start = 0
        while needle and len(matches) < MAX_MATCHES:
            k = low.find(needle, start)
            if k < 0:
                break
            a, b = max(0, k - CONTEXT // 2), min(len(hay), k + len(needle) + CONTEXT // 2)
            matches.append({"page": i + 1, "context": hay[a:b]})
            start = k + len(needle)
        if len(matches) >= MAX_MATCHES:
            return matches, True, text_pages
    return matches, False, text_pages


PLACEHOLDER = re.compile(r"«[^»]{1,40}»|\{\{[^}]{1,40}\}\}|\[[A-Z][A-Z _]{1,30}\]")


def _action_kind(a):
    try:
        a = a.get_object()
        return str(a.get("/S", ""))
    except Exception:  # noqa: BLE001
        return ""


def risk(r):
    out = {"javascript": 0, "launch": 0, "remote_goto": 0, "unsafe_uri": 0, "embedded_files": 0, "web_uri": 0}
    root = r.trailer["/Root"].get_object()
    names = root.get("/Names")
    if names is not None:
        names = names.get_object()
        out["javascript"] += int("/JavaScript" in names)
        out["embedded_files"] += int("/EmbeddedFiles" in names)
    for key in ("/OpenAction", "/AA"):
        if key in root:
            obj = root[key].get_object()
            if key == "/OpenAction":
                kinds = [_action_kind(obj)] if hasattr(obj, "get") else []
            else:
                kinds = [_action_kind(v) for v in obj.values()] if hasattr(obj, "values") else []
            for k in kinds:
                out["javascript"] += k == "/JavaScript"
                out["launch"] += k == "/Launch"
    for page in r.pages[:2000]:
        for ref in (page.get("/Annots") or []):
            try:
                an = ref.get_object()
            except Exception:  # noqa: BLE001
                continue
            a = an.get("/A")
            if a is None:
                if an.get("/Subtype") == "/FileAttachment":
                    out["embedded_files"] += 1
                continue
            a = a.get_object()
            k = str(a.get("/S", ""))
            if k == "/JavaScript":
                out["javascript"] += 1
            elif k == "/Launch":
                out["launch"] += 1
            elif k in ("/GoToR", "/GoToE"):
                out["remote_goto"] += 1
            elif k == "/URI":
                uri = str(a.get("/URI", ""))
                if re.match(r"^(https?://|mailto:)", uri, re.I):
                    out["web_uri"] += 1
                else:
                    out["unsafe_uri"] += 1
    return out


def placeholders(r):
    pages = []
    for i, page in enumerate(r.pages[:2000]):
        try:
            n = len(PLACEHOLDER.findall(page.extract_text() or ""))
        except Exception:  # noqa: BLE001
            continue
        if n:
            pages.append({"page": i + 1, "count": n})
    return pages


def main():
    root = norm(sys.argv[1])
    reply({"id": None, "ok": True, "ready": True})
    for line in sys.stdin:
        try:
            req = json.loads(line)
        except ValueError:
            reply({"id": None, "ok": False, "error": "BAD_REQUEST"})
            continue
        rid, op = req.get("id"), req.get("op")
        if op == "quit":
            return
        if not inside(req.get("pdf"), root):
            reply({"id": rid, "ok": False, "error": "PATH_REFUSED"})
            continue
        try:
            r = reader(req["pdf"])
            if op == "info":
                enc = bool(r.is_encrypted)
                if enc:
                    reply({"id": rid, "ok": True, "encrypted": True, "pages": None})
                    continue
                boxes = [[round(float(p.mediabox.width), 2), round(float(p.mediabox.height), 2)]
                         for p in r.pages[:2000]]
                reply({"id": rid, "ok": True, "encrypted": False, "pages": len(r.pages), "outline": outline(r),
                       "fonts": fonts(r), "page_boxes": boxes})
            elif op == "spans":
                n = int(req["page"])
                if not 1 <= n <= len(r.pages):
                    raise IndexError
                box, items = spans(r, n)
                reply({"id": rid, "ok": True, "box": box, "spans": items})
            elif op == "search":
                t = str(req.get("text", ""))[:200]
                m, trunc, tp = search(r, t)
                reply({"id": rid, "ok": True, "matches": m, "truncated": trunc, "text_pages": tp})
            elif op == "risk":
                reply({"id": rid, "ok": True, **risk(r)})
            elif op == "placeholders":
                reply({"id": rid, "ok": True, "pages": placeholders(r)})
            else:
                reply({"id": rid, "ok": False, "error": "BAD_REQUEST"})
        except Exception as e:  # noqa: BLE001 - a code, never content
            _cache["path"] = None
            reply({"id": rid, "ok": False, "error": "READ_FAILED", "detail": type(e).__name__})


if __name__ == "__main__":
    main()
