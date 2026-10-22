from common import *
import io
m=new(); m.create_milestone("MM-1","x"); m.create_milestone("MM-2","y")
m.store.segment_path.write_bytes(m.store.segment_path.read_bytes()+b'{"part')
o=io.StringIO(); rc=cli.run(["--home",str(m.home),"--actor","AKIA"+"ABCDEFGHIJKLMNOP","--session","xoxb-1234567890abc","recover"],out=o)
raw=m.store.segment_path.read_text(); print("recover rc", rc, "aws key stored:", "AKIAABCDEFGHIJKLMNOP" in raw, "slack stored:", "xoxb-1234567890abc" in raw)
