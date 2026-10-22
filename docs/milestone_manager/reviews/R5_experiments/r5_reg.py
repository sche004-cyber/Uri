from common import *
dev = Path("D:/uri-dev/uri-p0-audit/developmental.md")
w = Path(tempfile.mkdtemp())
m = new()
a = importers.import_register(m, dev)
print("P0 developmental:", a["recorded"])
other = w/"developmental.md"
other.write_text("# Some other project's register\n\n## B. Capabilities\n\n| ID | Capability | Status |\n|---|---|---|\n| CAP-RT1 | Unrelated thing | RED broken |\n", encoding="utf-8")
r = importers.import_register(m, other)
print("other register import:", {k: r[k] for k in ("recorded","revised","unchanged")}, "collisions" in r)
rec = m.projection()["records"]["REG-B-CAP-RT1"]
print("REG-B-CAP-RT1 now fields:", rec["fields"], "color", rec["color"], "register", rec["source"]["register"])
print("revisions:", [(x["fields"].get("capability"), x["source"]["register"]) for x in rec["revisions"]])
# is original text retained in projection?
print("original 'Resident Runtime' text retained anywhere in record:", "Resident Runtime" in json.dumps(rec))
# Second revision by the P0 file itself (re-import same P0): changed? row sha differs -> revise again
b = importers.import_register(m, dev); print("re-import P0 after:", {k: b[k] for k in ("recorded","revised","unchanged")})
