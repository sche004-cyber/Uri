exec(open("n8_r14_r15.py").read())
import io
o=io.StringIO(); rc=cli.run(["--home",str(m.home),"--actor","impl:a","recover"],out=o); print("recover rc",rc,json.loads(o.getvalue()).get("abandoned_batches"))
p=m.projection(); print("warnings", p["integrity_warnings"], "decisions", {k:v["status"] for k,v in p["decisions"].items()})
