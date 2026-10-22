import sys, os, shutil, subprocess
src, base = sys.argv[1], sys.argv[2]; sys.path.insert(0, src)
from scripts.dev_workflow.milestones.store import EventStore
from scripts.dev_workflow.milestones.service import Manager
for lab, sub, extra in [("ascii", "repo_a/ledger", {}), ("non-ascii", "repo_b/lédger", {}),
                        ("diff.relative", "repo_c/ledger", {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "diff.relative", "GIT_CONFIG_VALUE_0": "true"})]:
    root = os.path.join(base, "r2301", sub.split("/")[0]); shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
    subprocess.run(["git", "init", "-q", root], check=True)
    os.environ.pop("GIT_CONFIG_COUNT", None); os.environ.update(extra)
    home = os.path.join(base, "r2301", sub); EventStore.init(home, "h1")
    s = EventStore(home); s.config["autocommit"] = True
    m = Manager(home, actor="a:1"); m.store.config["autocommit"] = True
    m.create_milestone("M1", "t")
    print(lab, m.last_autocommit)
    for k in extra: os.environ.pop(k, None)
