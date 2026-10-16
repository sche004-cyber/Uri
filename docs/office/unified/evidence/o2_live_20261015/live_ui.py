"""Runs the O2 UI live check: a real Office service (own state folder, --enable-printing) and the release build of
`uri_ui/lib/office_o2_live_check.dart` against it, with synthetic fixtures. Outputs (screenshots, result.json, the
service log) go to <out>. The virtual-printer folder is emptied at the end (OD-U13).

    python live_ui.py <fixtures folder from live_service.py> <out>
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
src, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
shutil.rmtree(out, ignore_errors=True)
out.mkdir(parents=True)
fx = out / "fixtures"
fx.mkdir()
for name in ("official_letter.docx", "budget.xlsx"):
    shutil.copy2(src / "fixtures" / name, fx / name)
shutil.copy2(src / "saved" / "tender60.pdf", fx / "tender60.pdf")
shots, pdir, state = out / "shots", out / "virtual_print", out / "state"
shots.mkdir()
pdir.mkdir()
env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PYTHON")}
log = open(out / "service.log", "ab")
svc = subprocess.Popen([sys.executable, "-m", "uri_office.service", "run", "--state", str(state), "--port", "0",
                        "--allow-root", str(out), "--enable-printing"], cwd=str(REPO), stdout=subprocess.PIPE,
                       stderr=log, env=env)
port = json.loads(svc.stdout.readline().decode())["port"]
time.sleep(25)                                         # first-start engine verification (about 18 s, cached tree)
exe = REPO / "uri_ui" / "build" / "windows" / "x64" / "runner" / "Release" / "uri_ui.exe"
appenv = dict(os.environ, URI_OFFICE_PAGE_DIR=str(REPO / "uri_ui" / "assets" / "office"), URI_OFFICE_STATE=str(state), URI_O2_LIVE_DOCX=str(fx / "official_letter.docx"),
              URI_O2_LIVE_PDF=str(fx / "tender60.pdf"), URI_O2_LIVE_XLSX=str(fx / "budget.xlsx"),
              URI_O2_LIVE_OUT=str(shots), URI_O2_LIVE_PRINT_DIR=str(pdir))
t0 = time.time()
try:
    app = subprocess.run([str(exe)], env=appenv, timeout=900)
    rc = app.returncode
except subprocess.TimeoutExpired:
    rc = "timeout"
finally:
    svc.terminate()
    svc.wait(30)
printed = sorted(p.name for p in pdir.iterdir())
for p in pdir.iterdir():
    p.unlink()
(out / "run.json").write_text(json.dumps({"app_rc": rc, "seconds": round(time.time() - t0, 1), "port": port,
                                          "virtual_print_outputs_before_cleanup": printed,
                                          "virtual_print_dir_empty": not any(pdir.iterdir())}, indent=1))
print(json.dumps({"app_rc": rc, "printed": printed}))
