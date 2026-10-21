import sys; sys.argv=[sys.argv[0], "none"]
exec(open("r13_new2.py").read().split("which = sys.argv[1]")[0])
home = mk_pending()
print("recover1", cli_run(home, "--actor", "impl:c", "recover"))
print("open", openc(home))
print("recover2", cli_run(home, "--actor", "impl:c", "recover"))
