from common import *
import io
w = Path(tempfile.mkdtemp()); reg = w/"r.md"
reg.write_text("# Reg X\n\n## B. Capabilities\n\n| ID | Capability | Status |\n|---|---|---|\n| CAP-1 | a | RED |\n| CAP-2 | b | RED |\n", encoding="utf-8")
for label, first in (("import-register (first command)", lambda m: importers.import_register(m, reg)),
                     ("milestone-add (first command)", lambda m: m.create_milestone("MM-A","A"))):
    m = new(); first(m)
    data = m.store.segment_path.read_bytes(); lines = data.split(b"\n")
    # power loss mid-append: first line(s) of the batch reached disk, the last line is partial, anchors never refreshed
    a = m.store.read_anchors(); a["h1"] = {"count": 0, "head": "0"*64}; m.store.anchors_path.write_text(json.dumps(a))
    cut = lines[0] + b"\n" + lines[1][:20] if len(lines) > 2 else lines[0][:20]
    m.store.segment_path.write_bytes(cut)
    p = m.projection(); print(label, "| lines complete", cut.count(b"\n"), "| warnings", p["integrity_warnings"][:2])
    o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=o)
    print("   recover rc", rc, o.getvalue()[:220].replace("\n", " "))
    try: first(m); print("   retry without recover OK")
    except (ValidationError, StoreError) as e: print("   retry without recover:", e.code)
