from common import *
import shutil, io
src = Path("D:/uri-dev/uri-p0-audit/decisions.md"); dev = Path("D:/uri-dev/uri-p0-audit/developmental.md")
w = Path(tempfile.mkdtemp())
# a different project's register, also called decisions.md, reusing DEC-001.. numbering
(w/"other").mkdir()
hdr = "| ID | Date | Title | Decision | Reasoning | Alt | Corr | Scope | Appr | Related | Applicability | Sources | Evidence |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|\n"
(w/"other"/"decisions.md").write_text("# Other project decisions"+chr(10)+chr(10)+hdr + "| DEC-001 | 2025-01-01 | Unrelated | Other project decides Q | r | a | — | s | none | — | ACTIVE | x | REPO-RECORD |\n", encoding="utf-8")
m = new()
r1 = importers.import_decisions(m, src, "8e1d6324"); print("real: recorded", r1["recorded"], "collisions", len(r1["collisions"]), "secret", r1["skipped_secret"], "supersessions", r1["supersessions"])
r2 = importers.import_decisions(m, w/"other"/"decisions.md"); print("other project's decisions.md: recorded", r2["recorded"], "revised", r2["revised"], "collisions", r2["collisions"])
d = m.projection()["decisions"]["DEC-001"]; print("  DEC-001 title", d["title"][:40], "| source_revisions from", [x["source"]["path"][-30:] for x in d["source_revisions"]])
# renamed copy of the real register -> collisions?
shutil.copy(src, w/"decisions_2026-10-21.md")
m2 = new(); importers.import_decisions(m2, src, "8e1d6324")
r3 = importers.import_decisions(m2, w/"decisions_2026-10-21.md"); print("renamed identical copy: unchanged", r3["unchanged"], "collisions", len(r3["collisions"]))
# real registers: idempotence, unbound refs, supersession binding
for imp, path in ((importers.import_register, dev),):
    a = imp(m, path, "8e1d6324"); b = imp(m, path, "8e1d6324")
    print("developmental: first rec", a["recorded"], "secret", a["skipped_secret"], "bad", a["skipped_bad_id"], "| re-import rec", b["recorded"], "rev", b["revised"], "unch", b["unchanged"])
r4 = importers.import_decisions(m, src, "8e1d6324"); print("decisions re-import: rec", r4["recorded"], "rev", r4["revised"], "unch", r4["unchanged"], "coll", len(r4["collisions"]), "sup", r4["supersessions"])
p = m.projection()
print("conflicts:", {c["type"] for c in p["conflicts"]}, len(p["conflicts"]), "integrity", p["integrity_errors"], p["integrity_warnings"])
links = [(k, s["by"]) for k,dd in p["decisions"].items() for s in dd["superseded_by"]]
bad = [(k,b) for k,b in links if b not in p["decisions"] or not any(x["id"]==k for x in p["decisions"][b]["supersedes"])]
print("supersede links", len(links), "not two-way:", bad[:5])
