"""Run the UI V2 completion driver through the ORIGINAL production main() of the candidate on Windows.

    python -B -I tools\\run_live_ui.py <run-label> <mode> [--visual living|v2] [--fresh-prefs]

Waits for <run-label>/brain-ready.json (written by live_session.py). Copies tools/uiv2_driver.dart to
candidate/uri_ui/integration_test/uiv2_native_test.dart (temporary, removed afterwards; tracked tree stays clean).
APPDATA/LOCALAPPDATA/TEMP and the preference store are redirected into fixtures so the owner's real preferences are
never touched. Input is Flutter TestTextInput and synthesized key events (automation), not a physical keyboard or
mouse; recorded in every run.
"""
import datetime, hashlib, json, os, pathlib, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LABEL, MODE = sys.argv[1], sys.argv[2]
VISUAL = sys.argv[sys.argv.index("--visual") + 1] if "--visual" in sys.argv else "v2"
FRESH = "--fresh-prefs" in sys.argv
SRC = pathlib.Path(r"C:\Users\cheta\Development\uri-ui-v2c")
UI = SRC / "uri_ui"
import psutil  # noqa: E402

current = json.loads((ROOT / "evidence/runtime/ws-current-b.json").read_text())
out = ROOT / f"evidence/live/{LABEL}"
out.mkdir(parents=True, exist_ok=True)
# One preference folder per visual composition, shared by its runs: a returning-user run reads what the first-time
# run saved. --fresh-prefs empties it first (first-time user).
fx = ROOT / f"fixtures/native-prefs-{VISUAL}"
if FRESH and fx.exists():
    shutil.rmtree(fx)
prefs, local = fx / "prefs", fx / "local"
for p in (prefs, local / "roaming", local / "temp"):
    p.mkdir(parents=True, exist_ok=True)
deadline = time.monotonic() + 1800
while not (out / "brain-ready.json").exists():
    if time.monotonic() > deadline or (ROOT / f"fixtures/stop-{LABEL}").exists():
        sys.exit("NO_BRAIN_READY")
    time.sleep(2)
brain_ready = json.loads((out / "brain-ready.json").read_text())
driver_src = ROOT / "tools/uiv2_driver.dart"
driver = UI / "integration_test/uiv2_native_test.dart"
shutil.copy2(driver_src, driver)
env = dict(os.environ, URI_CLIENT_MANIFEST=current["client_manifest"], URI_QUAL_PREFS=str(prefs), URI_QUAL_MODE=MODE,
           URI_QUAL_UI_OUT=str(out), URI_UI_VISUAL=VISUAL, LOCALAPPDATA=str(local), APPDATA=str(local / "roaming"),
           TEMP=str(local / "temp"), TMP=str(local / "temp"), PYTHONDONTWRITEBYTECODE="1",
           URI_QUAL_FIRST_RUN="1" if FRESH else "0")
env.pop("URI_LIVING_SKIP_ONBOARDING", None)
command = [r"C:\Users\cheta\flutter\bin\flutter.bat", "test", "integration_test/uiv2_native_test.dart", "-d", "windows",
           "--no-pub"]
git = lambda *a: subprocess.check_output(["git", *a], cwd=SRC, text=True).strip()
record = dict(label=LABEL, mode=MODE, visual=VISUAL, fresh_prefs=FRESH, source_head=git("rev-parse", "HEAD"),
              source_tree=git("rev-parse", "HEAD^{tree}"),
              source_status_before=git("status", "--porcelain", "--untracked-files=no"), port=current["port"],
              command=command, driver_sha256=hashlib.sha256(driver_src.read_bytes()).hexdigest(), brain_ready=brain_ready,
              entry="original production main() via integration_test; keyboard via Flutter TestTextInput and synthesized key events",
              physical_keyboard_qualified=False, physical_mouse_qualified=False, microphone_qualified=False,
              started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
t = time.monotonic()
p = None
try:
    with (out / "flutter-test.log").open("w", encoding="utf-8") as log:
        p = subprocess.Popen(command, cwd=UI, env=env, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=subprocess.CREATE_NO_WINDOW)
        record["runner_pid"] = p.pid
        try:
            p.wait(timeout=2700)
        except subprocess.TimeoutExpired:
            p.terminate(); p.wait(timeout=20)
            record["timeout"] = True
finally:
    driver.unlink(missing_ok=True)
    if not (out / "ui-finished.json").exists():
        (out / "ui-finished.json").write_text(json.dumps({"by": "runner", "reason": "driver did not finish"}))
record.update(exit_code=p.returncode if p else None, elapsed_s=round(time.monotonic() - t, 2),
              finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              source_status_after=git("status", "--porcelain", "--untracked-files=no"))
exe = UI / "build/windows/x64/runner/Debug/uri_ui.exe"
if exe.exists():
    record["ui_binary_sha256"] = hashlib.sha256(exe.read_bytes()).hexdigest()
(out / "native-execution.json").write_text(json.dumps(record, indent=1))
print(json.dumps({k: record[k] for k in ("label", "mode", "visual", "exit_code", "elapsed_s", "source_status_after")}, indent=1))
