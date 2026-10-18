"""BRAIN-QC-20261018: run the Quick Controls driver through the ORIGINAL production main() of the candidate on Windows.

    python -B -I run_qc_ui.py <label>

Waits for live/<label>/brain-ready.json (qc_session.py). Copies qc_driver.dart to
<candidate>/uri_ui/integration_test/qc_native_test.dart (temporary, removed afterwards; the tracked tree stays clean).
APPDATA / LOCALAPPDATA / TEMP and the preference store are redirected into scratch fixtures, so the owner's real
preferences are never touched.
"""
import datetime
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

LABEL = sys.argv[1]
HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "live" / LABEL
OUT.mkdir(parents=True, exist_ok=True)
SRC = HERE.parents[3].parent            # docs/operational_intelligence/brain_quick_controls/evidence/harness -> repo
UI = SRC / "uri_ui"
RT = pathlib.Path(r"C:\Users\cheta\AppData\Local\Temp\claude\brain_qc\runtime2")
FX = pathlib.Path(r"C:\Users\cheta\AppData\Local\Temp\claude\brain_qc\fixtures") / LABEL
current = json.loads((RT / "work/c1/ws-current.json").read_text())
if "--fresh-prefs" in sys.argv and FX.exists():
    shutil.rmtree(FX)
prefs, local = FX / "prefs", FX / "local"
for p in (prefs, local / "roaming", local / "temp"):
    p.mkdir(parents=True, exist_ok=True)
deadline = time.monotonic() + 3 * 3600
while "--ui-first" not in sys.argv and not (OUT / "brain-ready.json").exists():
    if time.monotonic() > deadline or (OUT / "stop-session").exists():
        sys.exit("NO_BRAIN_READY")
    time.sleep(2)
# --driver uiv2: the canonical UI V2 journeys (the runtime-profiles copy of the canonical driver, unchanged) as a
# regression run of the candidate UI on the Standard Brain. Default: the Quick Controls driver.
UIV2 = "--driver" in sys.argv and sys.argv[sys.argv.index("--driver") + 1] == "uiv2"
driver_src = (SRC / "docs/operational_intelligence/profiles_live/evidence/harness/uiv2_driver.dart") if UIV2 \
    else HERE / "qc_driver.dart"
driver = UI / ("integration_test/uiv2_native_test.dart" if UIV2 else "integration_test/qc_native_test.dart")
shutil.copy2(driver_src, driver)
env = dict(os.environ, URI_CLIENT_MANIFEST=current["client_manifest"], URI_QUAL_PREFS=str(prefs),
           URI_QUAL_UI_OUT=str(OUT), LOCALAPPDATA=str(local), APPDATA=str(local / "roaming"),
           TEMP=str(local / "temp"), TMP=str(local / "temp"), PYTHONDONTWRITEBYTECODE="1")
env.pop("URI_LIVING_SKIP_ONBOARDING", None)
if "--dry" in sys.argv:
    env["URI_QC_DRY"] = "1"
if UIV2:
    env.update(URI_QUAL_MODE=sys.argv[sys.argv.index("--mode") + 1] if "--mode" in sys.argv else "main",
               URI_UI_VISUAL="v2", URI_QUAL_FIRST_RUN="1" if "--fresh-prefs" in sys.argv else "0")
command = [r"C:\Users\cheta\flutter\bin\flutter.bat", "test", "integration_test/" + driver.name, "-d", "windows",
           "--no-pub"]
git = lambda *a: subprocess.check_output(["git", *a], cwd=SRC, text=True).strip()
record = dict(label=LABEL, source_head=git("rev-parse", "HEAD"), source_tree=git("rev-parse", "HEAD^{tree}"),
              source_status_before=git("status", "--porcelain", "--untracked-files=no"), port=current["port"],
              command=command, driver_sha256=hashlib.sha256(driver_src.read_bytes()).hexdigest(),
              entry="original production main() via integration_test (Debug build); taps and TestTextInput",
              physical_keyboard_qualified=False, physical_mouse_qualified=False,
              started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
t = time.monotonic()
p = None
try:
    with (OUT / "flutter-test.log").open("w", encoding="utf-8") as log:
        p = subprocess.Popen(command, cwd=UI, env=env, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            p.wait(timeout=2700)
        except subprocess.TimeoutExpired:
            p.terminate()
            p.wait(timeout=20)
            record["timeout"] = True
finally:
    driver.unlink(missing_ok=True)
    if not (OUT / "ui-finished.json").exists():
        (OUT / "ui-finished.json").write_text(json.dumps({"by": "runner", "reason": "driver did not finish"}))
record.update(exit_code=p.returncode if p else None, elapsed_s=round(time.monotonic() - t, 2),
              finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              source_status_after=git("status", "--porcelain", "--untracked-files=no"))
exe = UI / "build/windows/x64/runner/Debug/uri_ui.exe"
if exe.exists():
    record["ui_binary_sha256"] = hashlib.sha256(exe.read_bytes()).hexdigest()
(OUT / "native-execution.json").write_text(json.dumps(record, indent=1))
print(json.dumps({k: record[k] for k in ("label", "exit_code", "elapsed_s", "source_status_after")}, indent=1))
