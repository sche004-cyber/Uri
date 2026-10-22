import sys
p=sys.argv[1]; s=open(p,encoding="utf-8").read()
i=s.index("import subprocess, sys, json, re")
s=s[:i]+'''import subprocess, sys, json
def mm(*a):
    return subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", str(h), "--actor", "owner:x", *a], capture_output=True, text=True)
for ent in ("MM-A", "RV-1"):
    cl = json.loads(mm("conflicts", "--entity", ent).stdout)
    ids = sorted({c["id"] for c in cl if c["entity"] == ent})
    r = mm("resolve-conflict", ent, "--note", "reviewed", *sum((["--id", i] for i in ids), []))
    print("   resolve", ent, ids, r.returncode, r.stdout.replace(chr(10), " ")[:160])
show("R3-02 after resolving conflicts (bound C1 != cand C2)", m)
'''
open(p,"w",encoding="utf-8").write(s)
