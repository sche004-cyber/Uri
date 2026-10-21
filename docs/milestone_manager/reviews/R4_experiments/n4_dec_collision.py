from common import *
src = Path("D:/uri-dev/uri-p0-audit/decisions.md").read_text(encoding="utf-8")
d = Path(tempfile.mkdtemp())/"decisions.md"; d.write_text(src, encoding="utf-8")
m = new()
r = importers.import_decisions(m, d, None); print("first import skipped_secret:", r["skipped_secret"], "recorded", r["recorded"])
m.record_decision("Milestone Manager is P0","MM is the P0 milestone","2026-10-21","OWNER-PROMPT","owner prompt", ident="DEC-091")
# P0 register later gains its own DEC-091 row (copy DEC-090's row shape)
row = [l for l in src.splitlines() if l.startswith("| DEC-090")][0].replace("DEC-090","DEC-091",1)
cells = row.split("|"); cells[3] = " P0 later decision about something else "; row = "|".join(cells)
d.write_text(src.rstrip("\n")+"\n"+row+"\n", encoding="utf-8")
r = importers.import_decisions(m, d, None); print("re-import:", {k:r[k] for k in ("recorded","revised","unchanged","skipped_secret")})
dec = m.projection()["decisions"]["DEC-091"]
print("DEC-091 title:", dec["title"], "| imported:", dec["imported"], "| source_revisions:", len(dec["source_revisions"]))
print("revision raw starts:", dec["source_revisions"][0]["raw"][:90] if dec["source_revisions"] else None)
