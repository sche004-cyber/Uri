import sys; sys.argv=[sys.argv[0], "none"]
exec(open("r13_new2.py").read().split("which = sys.argv[1]")[0])
home = mk_pending()
m = Manager(home, actor="x"); segp = m.store.segment_path; print("own seg exists", segp.exists())
segs = {s.name: len(s.valid_events) for s in m.store.read_all()}; print(segs)
# torn tail on the other host? use own seg if present else skip
p = home/"events/hc.jsonl"
if p.exists(): p.write_bytes(p.read_bytes()+b'{"x":')
print("warn", [w[:60] for w in Manager(home, actor="x").projection()["integrity_warnings"]])
rc, out = cli_run(home, "--actor", "impl:c", "recover"); print("recover rc", rc, out)
print("open", openc(home))
