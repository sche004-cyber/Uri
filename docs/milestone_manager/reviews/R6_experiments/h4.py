from common import *
import io
m = new(); m.create_milestone("MM-A","A"); m.create_milestone("MM-B","B"); m.create_milestone("MM-C","C")
lines = m.store.segment_path.read_bytes().split(b"\n")[:-1]; m.store.segment_path.write_bytes(b"\n".join(lines[:-2]) + b"\n")
with m.store.segment_path.open("ab") as f: f.write(b'{"x')
o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "recover", "--acknowledge-loss"], out=o)
print("rc", rc, o.getvalue()[:400].replace("\n"," "))
p = m.projection(); print("errors", p["integrity_errors"], "recoveries", len(p["recoveries"]), [(c["type"], c["kind"]) for c in p["conflicts"]])
try: m.store.reanchor("impl:a", "r"); print("reanchor no-ack ok")
except StoreError as e: print("reanchor no-ack:", e.code)
