"""Runs under LibreOffice's bundled python. Connects to a running soffice and exports every page of each document to
PNG (one file per page) through the graphic export filter with a PageRange, then exports a PDF.
argv: pipe_name out_dir pixel_width file1 [file2 ...]. Prints one JSON line per file."""
import json, os, sys, time
import uno
from com.sun.star.beans import PropertyValue


def prop(name, value):
    p = PropertyValue(); p.Name = name; p.Value = value; return p


pipe, out_dir, width, files = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4:]
local = uno.getComponentContext()
resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
ctx = None
for _ in range(160):
    try:
        ctx = resolver.resolve(f"uno:pipe,name={pipe};urp;StarOffice.ComponentContext"); break
    except Exception:
        time.sleep(0.25)
if ctx is None:
    print(json.dumps({"error": "connect failed"})); sys.exit(2)
desktop = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
for f in files:
    stem = os.path.splitext(os.path.basename(f))[0]
    ext = f.lower().rsplit(".", 1)[-1]
    png_filter = {"docx": "writer_png_Export", "pptx": "impress_png_Export", "xlsx": "calc_png_Export"}[ext]
    pdf_filter = {"docx": "writer_pdf_Export", "pptx": "impress_pdf_Export", "xlsx": "calc_pdf_Export"}[ext]
    row = {"file": os.path.basename(f)}
    try:
        t0 = time.perf_counter()
        doc = desktop.loadComponentFromURL(uno.systemPathToFileUrl(os.path.abspath(f)), "_blank", 0,
                                           (prop("Hidden", True), prop("ReadOnly", True)))
        row["load_s"] = round(time.perf_counter() - t0, 3)
        t1 = time.perf_counter()
        pdf = os.path.join(os.path.abspath(out_dir), stem + ".pdf")
        doc.storeToURL(uno.systemPathToFileUrl(pdf), (prop("FilterName", pdf_filter),))
        row["pdf_s"] = round(time.perf_counter() - t1, 3)
        if ext == "docx":
            pages = doc.getCurrentController().getPropertyValue("PageCount")
        elif ext == "pptx":
            pages = doc.getDrawPages().getCount()
        else:
            pages = None
        row["pages"] = pages
        t2 = time.perf_counter(); n = 0
        for i in range(1, (pages or 1) + 1):
            fd = uno.Any("[]com.sun.star.beans.PropertyValue",
                         tuple([prop("PixelWidth", width), prop("PixelHeight", int(width * 1.414))]))
            args = [prop("FilterName", png_filter), prop("FilterData", fd)]
            if ext == "docx":
                args.append(prop("PageRange", str(i)))
            if ext == "pptx":
                doc.getCurrentController().setCurrentPage(doc.getDrawPages().getByIndex(i - 1))
            uno.invoke(doc, "storeToURL", (uno.systemPathToFileUrl(
                os.path.join(os.path.abspath(out_dir), f"{stem}_p{i}.png")), tuple(args)))
            n += 1
        row["png_pages"] = n
        row["png_s"] = round(time.perf_counter() - t2, 3)
        doc.close(True)
        row["ok"] = True
    except Exception as e:
        row["ok"] = False; row["error"] = repr(e)[:300]
    print(json.dumps(row), flush=True)
