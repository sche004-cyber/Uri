from common import *
import re, collections
P = Path("D:/uri-dev/uri-p0-audit")
dec, opens = importers.parse_decisions(P/"decisions.md")
lines = (P/"decisions.md").read_text(encoding="utf-8").splitlines()
raw_dec = [ (i,l) for i,l in enumerate(lines,1) if re.match(r"^\|\s*DEC-\d+", l)]
print("DEC-like rows:", len(raw_dec), "parsed:", len(dec), "unique ids:", len({r[2]['id'] for r in dec}))
parsed_lines = {i for i,_,_ in dec}
for i,l in raw_dec:
    if i not in parsed_lines: print("DROPPED line", i, len(importers.split_row(l) or []), l[:120])
ids = collections.Counter(r[2]['id'] for r in dec); print("dup ids:", [k for k,v in ids.items() if v>1])
# column count anomalies
for i,l,r in dec:
    c = importers.split_row(l)
    if len(c)!=13: print("cols",len(c),"line",i,r['id'])
print("source_status dist:", collections.Counter(importers.source_status(r['applicability']) for _,_,r in dec))
print("evidence class dist:", collections.Counter(importers._evidence_class(r['evidence_class_raw']) for _,_,r in dec))
raw_open = [l for l in lines if re.match(r"^\|\s*OPEN-\d+", l)]
print("OPEN rows", len(raw_open), "parsed", len(opens))
rows = importers.parse_register(P/"developmental.md")
print("register rows:", len(rows), collections.Counter(s for _,_,s,_ in rows))
firsts = collections.Counter((s, next(iter(r.values()),"")) for _,_,s,r in rows)
print("dup first cols:", [k for k,v in firsts.items() if v>1])
hdrs = {}
for _,_,s,r in rows: hdrs.setdefault(s, list(r.keys()))
for s,h in hdrs.items(): print(s, h)
print("colors:", collections.Counter(importers._color(r.get("status") or r.get("state 2026-10-21") or "") for _,_,s,r in rows))
