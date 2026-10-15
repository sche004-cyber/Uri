"""Run the O2 native driver against the ORIGINAL production main() of the candidate (one run).

    python -B -I harness\\run_ui.py <run-name> [mode]

Waits for fixtures/<run>/ui-may-start.json (written by o2q_session.py once the Core server listens and, in Brain
runs, the Brain is READY), copies harness/drivers/o2q_main.dart into candidate/uri_ui/integration_test/ (removed
afterwards; the tracked tree stays clean), starts harness/dialog_helper.py, and runs `flutter test -d windows`.
APPDATA/LOCALAPPDATA/TEMP and the preference store are redirected into fixtures/<run>/ so the owner's preferences and
URI state are never touched (first-time profile). The Office page bundle is the recorded, hash-checked build from
the implementation worktree (URI_OFFICE_PAGE_DIR; the app verifies its hash itself).
"""
import datetime, hashlib, json, os, pathlib, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Fixtures (documents, saved outputs, redirected profile) stay under the user profile: the Office service only
# opens files inside the user home by default (M1 AC7, finding UX-ROOT-1), and C: is short of space, so only
# these small files live there; runtime, build and evidence are on D:.
FXR = pathlib.Path(r"C:\Users\cheta\uri-o2r-fixtures")
RUN = sys.argv[1]
MODE = sys.argv[2] if len(sys.argv) > 2 else "main"
SRC = ROOT / "candidate"
UI = SRC / "uri_ui"
import psutil  # noqa: E402

current = json.loads((ROOT / "evidence/ws-current-o2q-c.json").read_text())
out = ROOT / f"evidence/live/{RUN}"
out.mkdir(parents=True, exist_ok=True)
fx = FXR / f"{RUN}"
prefs, local = fx / "prefs", fx / "local"
for p in (prefs, local / "roaming", local / "temp"):
    p.mkdir(parents=True, exist_ok=True)
nuget = pathlib.Path(r"C:\Users\cheta\Development\uri-windows-live-qualification-20261013\candidate\uri_ui\build\windows\x64\nuget.exe")
dest = UI / "build/windows/x64/nuget.exe"
dest.parent.mkdir(parents=True, exist_ok=True)
if not dest.exists() and nuget.exists():
    shutil.copy2(nuget, dest)
driver_src = ROOT / "harness/drivers/o2q_main.dart"
driver = UI / "integration_test/o2q_native_test.dart"
page_dir = SRC / "uri_ui" / "assets" / "office"
while not (fx / "ui-may-start.json").exists():
    if (fx / "stop").exists():
        sys.exit("STOPPED_BEFORE_UI")
    time.sleep(1)
shutil.copy2(driver_src, driver)
office_state = local / "URI" / "office"
env = dict(os.environ, URI_CLIENT_MANIFEST=current["client_manifest"], URI_LIVING_SKIP_ONBOARDING="1",
           URI_QUAL_PREFS=str(prefs), URI_QUAL_MODE=MODE, URI_QUAL_UI_OUT=str(out), URI_QUAL_FX=str(fx),
           URI_OFFICE_PAGE_DIR=str(page_dir), URI_OFFICE_STATE=str(office_state),
           URI_ENGINES_ROOT=str(pathlib.Path(os.environ["LOCALAPPDATA"]) / "URI" / "engines"),
           # B4/O2-RT-1: no URI_OFFICE_PYTHON / URI_OFFICE_SOURCE. The app starts Office from the client
           # manifest (interpreter + source_root of the materialized runtime, which holds uri_office and pypdf).
           LOCALAPPDATA=str(local), APPDATA=str(local / "roaming"), TEMP=str(local / "temp"), TMP=str(local / "temp"),
           PATH=str(nuget.parent) + os.pathsep + os.environ["PATH"], PYTHONDONTWRITEBYTECODE="1")
command = [r"C:\Users\cheta\flutter\bin\flutter.bat", "test", "integration_test/o2q_native_test.dart", "-d", "windows"]
if (UI / ".dart_tool/package_config.json").exists():
    command.append("--no-pub")
git = lambda *a: subprocess.check_output(["git", *a], cwd=SRC, text=True).strip()
record = dict(run=RUN, mode=MODE, source_head=git("rev-parse", "HEAD"), source_tree=git("rev-parse", "HEAD^{tree}"),
              source_status_before=git("status", "--porcelain", "--untracked-files=no"), port=current["port"],
              command=command, driver_sha256=hashlib.sha256(driver_src.read_bytes()).hexdigest(),
              entry="original production main() via integration_test (debug build); pointer and text through Flutter "
                    "WidgetTester; file dialogs are the real Windows dialogs filled by dialog_helper.py",
              physical_input_qualified=False, page_dir=str(page_dir),
              started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
helper = subprocess.Popen([sys.executable, "-B", "-I", str(ROOT / "harness/dialog_helper.py"), RUN],
                          creationflags=subprocess.CREATE_NO_WINDOW)
t = time.monotonic()
samples = []
p = None
try:
    with (out / "flutter-test.log").open("w", encoding="utf-8") as log:
        p = subprocess.Popen(command, cwd=UI, env=env, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        deadline = time.monotonic() + 3000
        while p.poll() is None and time.monotonic() < deadline:
            rows = []
            try:
                for c in psutil.Process(p.pid).children(recursive=True):
                    try:
                        rows.append(dict(pid=c.pid, name=c.name(), rss_mib=round(c.memory_info().rss / 2**20, 1)))
                    except psutil.Error:
                        pass
            except psutil.Error:
                pass
            samples.append(dict(t=round(time.monotonic() - t, 1), procs=rows))
            time.sleep(5)
        if p.poll() is None:
            p.kill()
            record["timeout"] = True
    record["exit_code"] = p.returncode
finally:
    driver.unlink(missing_ok=True)
    if not (out / "ui-finished.json").exists():
        (out / "ui-finished.json").write_text(json.dumps({"finished": False, "exit_code": record.get("exit_code")}))
    time.sleep(2)
    helper.terminate()
    record.update(seconds=round(time.monotonic() - t, 1), finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  source_status_after=git("status", "--porcelain", "--untracked-files=no"))
    (out / "ui-run.json").write_text(json.dumps(record, indent=1))
    (out / "ui-proc-samples.json").write_text(json.dumps(samples))
    print(json.dumps({k: record.get(k) for k in ("run", "exit_code", "seconds", "source_head")}))
