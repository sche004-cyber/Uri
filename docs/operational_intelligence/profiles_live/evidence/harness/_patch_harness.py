"""One-off: adapt the copied canonical UI V2 harness to this run directory (paths + --profile). Idempotence not needed."""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def edit(name, pairs):
    p = HERE / name
    s = p.read_bytes().decode()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    for a, b in pairs:
        assert s.count(a) == 1, (name, a)
        s = s.replace(a, b)
    if crlf:
        s = s.replace("\n", "\r\n")
    p.write_bytes(s.encode())


OLD_SRC = r'pathlib.Path(r"C:\Users\cheta\Development\uri-ui-v2p")'
NEW_SRC = r'pathlib.Path(r"D:\uri-dev\uri-runtime-profiles-integ")'

edit("live_session.py", [
    ('"""UI V2 completion live session host:',
     '"""(RUNTIME-PROFILES-INTEG copy of the canonical UI V2 harness docs/ui_v2/postint/evidence/harness/live_session.py;\n'
     'changes: paths, and --profile <ctx>,<vision>,<mtp> starts the Brain host on a derived resource profile through the\n'
     'production parser ws_brain_host.parse_profile; without --profile the frozen config is used exactly as before.)\n'
     'UI V2 completion live session host:'),
    ("SRC, RT = " + OLD_SRC + ', ROOT / "runtime2"',
     "SRC, RT = " + NEW_SRC + ', ROOT / "runtime"\n'
     'PROFILE = sys.argv[sys.argv.index("--profile") + 1] if "--profile" in sys.argv else None'),
    ("from uri_operational_intelligence import gpu_lease as G, runtime_v1 as R  # noqa: E402",
     "from uri_operational_intelligence import gpu_lease as G, runtime_v1 as R  # noqa: E402\n"
     "from uri_operational_intelligence import runtime_profiles as RP  # noqa: E402\n"
     "from scripts.ws_brain_host import parse_profile  # noqa: E402"),
    ("    cfg = R.load_config()\n",
     "    cfg = R.load_config()\n    if PROFILE:\n        cfg = RP.derive_config(cfg, *parse_profile(PROFILE))\n"),
    ("    record = dict(label=LABEL, port=port, started_utc=now(), no_brain=NO_BRAIN,",
     "    record = dict(label=LABEL, port=port, started_utc=now(), no_brain=NO_BRAIN, profile_arg=PROFILE,\n"
     "                  profile=RP.describe(cfg),"),
])
edit("run_live_ui.py", [
    ('"""Run the UI V2 completion driver',
     '"""(RUNTIME-PROFILES-INTEG copy of the canonical harness; only SRC changed.)\nRun the UI V2 completion driver'),
    ("SRC = " + OLD_SRC, "SRC = " + NEW_SRC),
])
print("patched")
