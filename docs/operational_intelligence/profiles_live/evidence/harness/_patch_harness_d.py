"""One-off (review R2-02): every harness runs the host from the materialized runtime-d (code 07dca2a8) and records a
clean source binding (tools/binding.py); live_session refuses to start without it."""
from pathlib import Path

T = Path(__file__).resolve().parent


def edit(name, pairs):
    p = T / name
    s = p.read_bytes().decode()
    crlf = "\r\n" in s
    s = s.replace("\r\n", "\n")
    for a, b in pairs:
        assert s.count(a) == 1, (name, a)
        s = s.replace(a, b)
    if crlf:
        s = s.replace("\n", "\r\n")
    p.write_bytes(s.encode())


HOST_SOAK = ('    host = subprocess.Popen([sys.executable, "-B", "-I", str(SRC / "scripts" / "ws_brain_host.py"), "--report-dir",\n'
             '                             str(REP), "--minutes", str(MINUTES + 15), "--profile", PROFILE], cwd=str(SRC),')
edit("soak.py", [
    ('SRC = pathlib.Path(r"D:\\uri-dev\\uri-runtime-profiles-integ")\n',
     'SRC = pathlib.Path(r"D:\\uri-dev\\uri-runtime-profiles-integ")\nRT = ROOT / "runtime-d"\n'),
    ('    stop = SRC / "work" / "oi" / "state" / "runtime_v1.stop"\n',
     '    import binding\n    rec["binding"] = binding.require(RT)\n'
     '    stop = RT / "work" / "oi" / "state" / "runtime_v1.stop"\n'),
    (HOST_SOAK,
     '    host = subprocess.Popen([str(RT / ".venv/Scripts/python.exe"), "-B", "-I", str(RT / "scripts" / "ws_brain_host.py"), "--report-dir",\n'
     '                             str(REP), "--minutes", str(MINUTES + 15), "--profile", PROFILE], cwd=str(RT),'),
])
edit("assist_vision_app.py", [
    ('SRC = pathlib.Path(r"D:\\uri-dev\\uri-runtime-profiles-integ")\n',
     'SRC = pathlib.Path(r"D:\\uri-dev\\uri-runtime-profiles-integ")\nRT = ROOT / "runtime-d"\n'),
    ('    stop = SRC / "work" / "oi" / "state" / "runtime_v1.stop"\n',
     '    import binding\n    rec["binding"] = binding.require(RT)\n'
     '    stop = RT / "work" / "oi" / "state" / "runtime_v1.stop"\n'),
    ('    host = subprocess.Popen([sys.executable, "-B", "-I", str(SRC / "scripts" / "ws_brain_host.py"), "--report-dir",\n'
     '                             str(REP), "--minutes", "20", "--profile", PROFILE], cwd=str(SRC), stdout=log,',
     '    host = subprocess.Popen([str(RT / ".venv/Scripts/python.exe"), "-B", "-I", str(RT / "scripts" / "ws_brain_host.py"), "--report-dir",\n'
     '                             str(REP), "--minutes", "20", "--profile", PROFILE], cwd=str(RT), stdout=log,'),
])
edit("switch_live.py", [
    ('RT = ROOT / "runtime-c"\n', 'RT = ROOT / "runtime-d"\n'),
    ('INST = json.loads((ROOT / "evidence" / "provision-c.json").read_text())',
     'INST = json.loads((ROOT / "evidence" / "provision-d.json").read_text())'),
    ('    rec = {"label": LABEL, "session_id": SESSION, "steps": [], "commit": [], "classification": "STARTED"}\n',
     '    import binding\n'
     '    rec = {"label": LABEL, "session_id": SESSION, "steps": [], "commit": [], "classification": "STARTED",\n'
     '           "binding": binding.require(RT)}\n'),
])
edit("live_session.py", [
    ('ROOT / "runtime-c"\n', 'ROOT / "runtime-d"\n'),
    ('    verified = verify_runtime()\n',
     '    verified = verify_runtime()\n    sys.path.insert(0, str(ROOT / "tools"))\n    import binding\n'
     '    verified["binding"] = binding.require(RT)\n'),
])
print("patched-d")
