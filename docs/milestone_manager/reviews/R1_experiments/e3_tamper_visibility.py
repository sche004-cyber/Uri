from common import *
import io, shutil
m = new()
m.create_milestone("MM-A","A")
m.set_status("MM-A","IN_PROGRESS","go")
seg = m.store.segment_path
# tamper: rewrite the IN_PROGRESS status event to ACCEPTED (hash not recomputed)
b = seg.read_bytes().replace(b'"status":"IN_PROGRESS"', b'"status":"ACCEPTED"')
seg.write_bytes(b)
print("verify ok:", m.store.verify()["ok"])
# 1) with cache: status
out=io.StringIO(); rc=cli.run(["--home",str(m.home),"--no-emoji","status","--no-tasks"],out); print("status rc",rc); print(out.getvalue())
# 2) delete cache -> rebuild path in status text
m.cache_path.unlink()
out=io.StringIO(); rc=cli.run(["--home",str(m.home),"--no-emoji","status","--no-tasks"],out); print("status(no cache) rc",rc); print(out.getvalue())
out=io.StringIO(); rc=cli.run(["--home",str(m.home),"--no-emoji","resume","MM-A","--no-tasks"],out); print("resume rc",rc); print(out.getvalue()[:400])
