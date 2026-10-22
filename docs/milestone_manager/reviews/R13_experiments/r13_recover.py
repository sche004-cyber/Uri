import sys; sys.argv=[sys.argv[0], "none"]
exec(open("r13_new2.py").read().split("which = sys.argv[1]")[0])
for label, mk in (("pending", mk_pending), ("adopt", mk_adopt)):
    home = mk()
    rc, out = cli_run(home, "--actor", "impl:c", "recover")
    print(label, "recover rc", rc, out)
    print(label, " open", openc(home))
    rc, out = cli_run(home, "--actor", "impl:c", "link-lifecycle", "MM-A", str(home))
    print(label, " link1", rc, out[:200])
    # dedupe path: link again
    home2 = mk(); Manager(home2, actor="x")
    import json as J
