"""Runs under LibreOffice's bundled python. Connects to a running soffice over a named pipe and converts files.
argv: pipe_name out_dir file1 [file2 ...]. Prints one JSON line per file: {file, seconds, ok, error}."""
import json, sys, time, os
import uno
from com.sun.star.beans import PropertyValue

def prop(name, value):
    p = PropertyValue(); p.Name = name; p.Value = value; return p

pipe, out_dir, files = sys.argv[1], sys.argv[2], sys.argv[3:]
local = uno.getComponentContext()
resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
ctx = None
for _ in range(120):
    try:
        ctx = resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext"); break
    except Exception:
        time.sleep(0.25)
if ctx is None:
    print(json.dumps({"error": "connect failed"})); sys.exit(2)
desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
for f in files:
    t0 = time.perf_counter()
    try:
        doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(os.path.abspath(f)), "_blank", 0,
                                           (prop("Hidden", True), prop("ReadOnly", True)))
        name = os.path.splitext(os.path.basename(f))[0] + ".pdf"
        filt = "impress_pdf_Export" if f.lower().endswith(".pptx") else "writer_pdf_Export"
        doc.storeToURL(uno.systemPathToFileUrl(os.path.join(os.path.abspath(out_dir), name)), (prop("FilterName", filt),))
        doc.close(True)
        print(json.dumps({"file": os.path.basename(f), "seconds": round(time.perf_counter() - t0, 3), "ok": True}), flush=True)
    except Exception as e:
        print(json.dumps({"file": os.path.basename(f), "seconds": round(time.perf_counter() - t0, 3), "ok": False,
                          "error": repr(e)[:300]}), flush=True)
