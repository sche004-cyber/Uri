from common import *
import io, json
m=new(); m.create_milestone("MM-1","x")
def cli_(*a, actor="impl:a"):
    o=io.StringIO(); rc=cli.run(["--home",str(m.home),"--actor",actor,"--no-emoji",*a],out=o); return rc,o.getvalue()
print(cli_("reanchor","--reason","rotated key sk-ant-"+"a"*30)[0])
print(cli_("reanchor","--reason","ok", actor="ghp_"+"c"*36)[0])
raw=m.store.segment_path.read_text()
print("secret stored in ledger:", "sk-ant-aaaa" in raw, "ghp_ccc" in raw)
print("verify ok", m.store.verify()["ok"], "conflicts", views.conflict_rows(m.projection()))
