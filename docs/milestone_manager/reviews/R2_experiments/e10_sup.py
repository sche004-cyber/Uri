from common import *
m = new()
importers.import_decisions(m, Path("D:/uri-dev/uri-p0-audit/decisions.md"), "8e1d6324")
p = m.projection()
for d in p["decisions"].values():
    if d["superseded_by"] or d["status"] in ("SUPERSEDED","PARTIALLY_SUPERSEDED"):
        print(d["id"], d["status"], [(s["by"], s["partial"]) for s in d["superseded_by"]])
        print("    corr:", d["imported_fields"]["corrections_text"][:260])
        print("    appl:", d["imported_fields"]["applicability"][:200])
