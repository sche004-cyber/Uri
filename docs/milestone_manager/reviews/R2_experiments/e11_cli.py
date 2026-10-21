import subprocess, sys, tempfile, json
from pathlib import Path
R="D:/uri-dev/uri-milestone-manager"
home = Path(tempfile.mkdtemp())/"l"
def run(*a):
    p = subprocess.run([sys.executable,"-m","scripts.dev_workflow.milestones","--home",str(home),"--actor","t",*a],cwd=R,capture_output=True,text=True)
    print(a[:2], "rc", p.returncode, "| stdout:", p.stdout.strip()[:120].replace("\n"," "), "| stderr tail:", p.stderr.strip().splitlines()[-1:] )
run("init","--host-id","h1")
run("milestone-add","MM-A","--title","A")
run("import-decisions", str(home/"nope.md"))
sd = Path(tempfile.mkdtemp())
(sd/"state.json").write_text('{"history":[{"hash":"x"}]}')
(sd/"events.jsonl").write_text('{"seq":1,"ts":"t","kind":"K","prev":"' + "0"*64 + '","hash":"x"}\n')
run("link-lifecycle","MM-A",str(sd))
run("sync-lifecycle","MM-A",str(sd))
(sd/"events.jsonl").write_text('[1,2]\n')
run("sync-lifecycle","MM-A",str(sd))
run("evidence-add","MM-A","--kind","log","--ref","x","--result","COMPLETED_WITH_RESULT","--summary","s","--file",str(home/"missing.log"))
run("status-set","MM-A","ACCEPTED","--reason","r","--expect-version","abc")
