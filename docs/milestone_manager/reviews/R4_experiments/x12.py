from common import *
import io
m = new(); m.create_milestone("MM-A","A"); m.create_milestone("MM-B","B")
lines = m.store.segment_path.read_bytes().split(b"\n")[:-1]; m.store.segment_path.write_bytes(b"\n".join(lines[:-1])+b"\n")
o=io.StringIO(); rc=cli.run(["--home",str(m.home),"log"],out=o); print("log rc", rc, "integrity_errors" in o.getvalue())
for s in ("token: 65536","access_token: expired","secret: rotated","password: hunter22","token=ab12cd34ef","api_key: 123456789012345678901234567890"):
    print(repr(s), model.find_secret(s))
