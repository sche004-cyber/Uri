"""UNO bridge (plan §5 `lo_bridge.py`, spike S1). Runs in LibreOffice's bundled python.exe as
`python.exe -I <run copy of this file> <pipe name> <work root>`; the service checks this file's hash first.

Under -I the bundled Python cannot find `uno` (S1), so this script adds exactly one folder to sys.path: the folder of
the running python.exe, which is LibreOffice's integrity-checked `program` folder. Nothing else (no PYTHONPATH, no
user site, no current folder).

Protocol: one JSON object per line on stdin, one per line on stdout.
  {"id": "...", "op": "ping"}                                  -> {"id", "ok": true}
  {"id": "...", "op": "convert", "in": <path>, "out": <path>}  -> {"id", "ok", "seconds", "error"?}
  {"id": "...", "op": "quit"}                                  -> exits
Both paths must lie inside the work root given at start (real paths). The input kind picks the export filter.
Documents are loaded hidden, read-only, with macros never executed and links never updated.
"""
import json
import os
import sys
import time

PROGRAM = os.path.dirname(os.path.abspath(sys.executable))
sys.path.insert(0, PROGRAM)

import uno  # noqa: E402
from com.sun.star.beans import PropertyValue  # noqa: E402

FILTERS = {".docx": "writer_pdf_Export", ".pptx": "impress_pdf_Export", ".xlsx": "calc_pdf_Export"}
NEVER_EXECUTE = 0        # com.sun.star.document.MacroExecMode.NEVER_EXECUTE
NO_UPDATE = 0            # com.sun.star.document.UpdateDocMode.NO_UPDATE


def prop(name, value):
    p = PropertyValue()
    p.Name, p.Value = name, value
    return p


def norm(p):
    return os.path.normcase(os.path.realpath(p))


def inside(p, root):
    try:
        return os.path.commonpath([norm(p), root]) == root
    except ValueError:
        return False


def reply(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def connect(pipe):
    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
    deadline = time.time() + 90
    while True:
        try:
            ctx = resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext")
            return ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
        except Exception:
            if time.time() > deadline:
                raise
            time.sleep(0.25)


class LoadReturnedNothing(RuntimeError):
    pass


def convert(desktop, src, dst):
    ext = os.path.splitext(src)[1].lower()
    filt = FILTERS.get(ext)
    if filt is None:
        raise ValueError("unsupported input kind")
    load = (prop("Hidden", True), prop("ReadOnly", True), prop("MacroExecutionMode", NEVER_EXECUTE),
            prop("UpdateDocMode", NO_UPDATE), prop("Silent", True))
    doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(os.path.abspath(src)), "_blank", 0, load)
    if doc is None:
        raise LoadReturnedNothing("the engine could not load the document")
    try:
        data = uno.Any("[]com.sun.star.beans.PropertyValue", (prop("ExportBookmarks", True),))
        doc.storeToURL(uno.systemPathToFileUrl(os.path.abspath(dst)),
                       (prop("FilterName", filt), prop("FilterData", data)))
    finally:
        doc.close(True)


def main():
    pipe, root = sys.argv[1], norm(sys.argv[2])
    desktop = connect(pipe)
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
        if op == "ping":
            reply({"id": rid, "ok": True})
            continue
        if op != "convert":
            reply({"id": rid, "ok": False, "error": "BAD_REQUEST"})
            continue
        src, dst = req.get("in", ""), req.get("out", "")
        if not (isinstance(src, str) and isinstance(dst, str) and inside(src, root)
                and inside(os.path.dirname(dst) or ".", root)):
            reply({"id": rid, "ok": False, "error": "PATH_REFUSED"})
            continue
        t0 = time.perf_counter()
        try:
            # LibreOffice restarts itself once after it creates a new profile. During that restart the connection is
            # disposed or a load returns nothing; reconnect to the same pipe and try again (at most 3 attempts).
            for attempt in range(3):
                try:
                    convert(desktop, src, dst)
                    break
                except Exception as e:  # noqa: BLE001
                    transient = isinstance(e, LoadReturnedNothing) or "Disposed" in type(e).__name__ \
                        or "Disposed" in repr(e)[:200]
                    if not transient or attempt == 2:
                        raise
                    time.sleep(1.0 + attempt)
                    desktop = connect(pipe)
            reply({"id": rid, "ok": True, "seconds": round(time.perf_counter() - t0, 3)})
        except Exception as e:  # noqa: BLE001 - reported to the service as a code, never with document content
            reply({"id": rid, "ok": False, "seconds": round(time.perf_counter() - t0, 3),
                   "error": "CONVERT_FAILED", "detail": type(e).__name__})


if __name__ == "__main__":
    main()
