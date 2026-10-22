from common import *
import subprocess
def g(repo,*a): return subprocess.run(["git","-C",str(repo),*a],capture_output=True,text=True,encoding="utf-8")
def mkrepo(commit_first=True):
    repo=Path(tempfile.mkdtemp(prefix="acrepo_"))/"repo"; repo.mkdir(); g(repo,"init","-q")
    g(repo,"config","user.name","t"); g(repo,"config","user.email","t@t")
    if commit_first:
        (repo/"base.txt").write_text("b\n"); g(repo,"add","base.txt"); g(repo,"commit","-qm","base")
    (repo/"wip.txt").write_text("unrelated\n"); g(repo,"add","wip.txt")
    return repo
def case(tag, sub, commit_first=True, winpath=False, extra=None):
    repo=mkrepo(commit_first); home=repo/sub if sub else repo
    EventStore.init(home,"h1",autocommit=True)
    h=str(home).replace("/","\\") if winpath else str(home)
    m=Manager(h,actor="impl:a"); m.create_milestone("MM-A","A"); ac1=m.last_autocommit
    m.update_milestone("MM-A",objective="o"); ac2=m.last_autocommit
    log=g(repo,"log","--format=%s","--name-only").stdout.split("\n")
    staged=g(repo,"diff","--cached","--name-only").stdout.split()
    st=g(repo,"status","--porcelain").stdout.strip().splitlines()
    print(f"{tag}: ac1={ac1} ac2={ac2}\n   log={[x for x in log if x]}\n   staged={staged} status={st} verify_git={m.store.verify()['git']}")
case("subdir","ledger")
case("root",None)
case("space","led ger dir")
case("nonascii","lédger")
case("unborn-HEAD","ledger",commit_first=False)
case("winpath","ledger",winpath=True)
case("glob-chars","l[1]*")
