r"""Run the EMBER-V21-INTEG driver through the ORIGINAL production main() of the candidate on Windows.

    python -B -I tools\run_live_ui.py <run-label> <first|returning> [--fresh-prefs]

UI first (launcher order): starts at once; the session host starts the Brain when the driver writes ui-ready.json.
Copies tools/ember_live_driver.dart to the candidate's uri_ui/integration_test/ember_live_test.dart (temporary,
removed afterwards; the tracked tree stays clean). APPDATA/LOCALAPPDATA/TEMP and the preference store are redirected
into fixtures so the owner's real preferences are never touched.
"""
import datetime, hashlib, json, os, pathlib, shutil, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LABEL, MODE = sys.argv[1], sys.argv[2]
FRESH = "--fresh-prefs" in sys.argv
SRC = pathlib.Path(r"D:\uri-dev\uri-ember-v21-integ")
UI = SRC / "uri_ui"
current = json.loads((ROOT / "evidence/runtime/ws-current.json").read_text())
out = ROOT / f"evidence/live/{LABEL}"
out.mkdir(parents=True, exist_ok=True)
fx = ROOT / "fixtures/native-prefs"
if FRESH and fx.exists():
    shutil.rmtree(fx)
prefs, local = fx / "prefs", fx / "local"
for p in (prefs, local / "roaming", local / "temp"):
    p.mkdir(parents=True, exist_ok=True)
driver_src = ROOT / "tools/ember_live_driver.dart"
driver = UI / "integration_test/ember_live_test.dart"
shutil.copy2(driver_src, driver)
env = dict(os.environ, URI_CLIENT_MANIFEST=current["client_manifest"], URI_QUAL_PREFS=str(prefs), URI_QUAL_MODE=MODE,
           URI_QUAL_UI_OUT=str(out), URI_UI_VISUAL="v2", LOCALAPPDATA=str(local), APPDATA=str(local / "roaming"),
           TEMP=str(local / "temp"), TMP=str(local / "temp"), PYTHONDONTWRITEBYTECODE="1",
           URI_LIVING_SKIP_ONBOARDING="1")
command = [r"C:\Users\cheta\flutter\bin\flutter.bat", "test", "integration_test/ember_live_test.dart", "-d", "windows",
           "--no-pub"]
git = lambda *a: subprocess.check_output(["git", *a], cwd=SRC, text=True).strip()
record = dict(label=LABEL, mode=MODE, fresh_prefs=FRESH, source_head=git("rev-parse", "HEAD"),
              source_tree=git("rev-parse", "HEAD^{tree}"),
              source_status_before=git("status", "--porcelain", "--untracked-files=no"), port=current["port"],
              command=command, driver_sha256=hashlib.sha256(driver_src.read_bytes()).hexdigest(),
              entry="original production main() via integration_test; window checks via Win32 probe with SendInput",
              physical_keyboard_qualified=False, physical_mouse_qualified=False, microphone_qualified=False,
              started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
t = time.monotonic()
try:
    with (out / "flutter-test.log").open("w", encoding="utf-8") as log:
        p = subprocess.Popen(command, cwd=UI, env=env, stdout=log, stderr=subprocess.STDOUT)
        record["rc"] = p.wait(timeout=95 * 60)
finally:
    driver.unlink(missing_ok=True)
    if not (out / "ui-finished.json").exists():
        (out / "ui-finished.json").write_text(json.dumps({"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                                         "by": "runner", "rc": record.get("rc")}))
    record.update(seconds=round(time.monotonic() - t, 1), source_status_after=git("status", "--porcelain", "--untracked-files=no"),
                  finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (out / "native-execution.json").write_text(json.dumps(record, indent=1))
print(json.dumps({k: record.get(k) for k in ("label", "rc", "seconds", "source_status_after")}))
