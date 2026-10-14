r"""Run the Ember live qualification driver on the real Windows app.

    <runtime>\.venv\Scripts\python.exe -B docs\companions\fire\live\run_fire_live.py

UI first: the driver starts the production main() and writes ui-ready.json; only then is the Brain host started
through the guarded launcher (-NoUi -OverrideGpu, owner-authorized for this run, see
OWNER_GPU_OVERRIDE_AUTHORIZATION.json). On stop-brain.json the Brain host this script started is stopped (the
recoverable-error journey); on restart-brain.json it is started again. Owner preferences are never touched
(APPDATA/LOCALAPPDATA redirected, preference store redirected). GPU counters for the window are sampled every 5 s.
"""
import datetime, json, os, pathlib, shutil, subprocess, time

import psutil

SRC = pathlib.Path(r"C:\Users\cheta\Development\uri-fire-companion")
RT = pathlib.Path(r"C:\Users\cheta\Development\uri-fire-companion-rt")
LIVE = pathlib.Path(r"C:\Users\cheta\Development\uri-fire-companion-live")
UI = SRC / "uri_ui"
OUT = LIVE / "evidence"
FX = LIVE / "fixtures"
current = json.loads((RT / "work/c1/ws-current.json").read_text())
for p in (OUT, FX / "prefs", FX / "local/roaming", FX / "local/temp"):
    p.mkdir(parents=True, exist_ok=True)
driver = UI / "integration_test/fire_live_test.dart"
# Read from the live folder: the UI tree itself must stay at the runtime receipt's commit.
shutil.copy2(LIVE / "fire_live_driver.dart", driver)
nuget = pathlib.Path(r"C:\Users\cheta\Development\uri-windows-live-qualification-20261013\candidate\uri_ui\build\windows\x64\nuget.exe")
dest = UI / "build/windows/x64/nuget.exe"
if nuget.exists() and not dest.exists():
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(nuget, dest)
env = dict(os.environ, URI_CLIENT_MANIFEST=current["client_manifest"], URI_LIVING_SKIP_ONBOARDING="1",
           URI_QUAL_PREFS=str(FX / "prefs"), URI_QUAL_UI_OUT=str(OUT), LOCALAPPDATA=str(FX / "local"),
           APPDATA=str(FX / "local/roaming"), TEMP=str(FX / "local/temp"), TMP=str(FX / "local/temp"),
           PATH=str(nuget.parent) + os.pathsep + os.environ["PATH"], PYTHONDONTWRITEBYTECODE="1")
launcher = ["powershell", "-NoProfile", "-File", str(SRC / "scripts/launch_uri_working_system.ps1"),
            "-RuntimeRoot", str(RT), "-UiRoot", str(SRC), "-NoUi", "-OverrideGpu", "-BrainMinutes", "90"]
log = []


def note(event, **kw):
    log.append(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), event=event, **kw))
    (OUT / "runner-log.json").write_text(json.dumps(log, indent=1))


def brain_hosts():
    out = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        cl = " ".join(p.info["cmdline"] or [])
        if "ws_brain_host.py" in cl and str(RT).lower() in cl.lower():
            out.append(p)
    return out


def gpu_sample(pids):
    ps = (r"$c=Get-Counter '\GPU Process Memory(*)\Dedicated Usage','\GPU Engine(*engtype_3D)\Utilization Percentage' -EA 0;"
          r"$c.CounterSamples | ? { $_.CookedValue -gt 0 } | % { $_.InstanceName + '|' + $_.Path + '|' + $_.CookedValue }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60)
    rows = {}
    for line in r.stdout.splitlines():
        try:
            inst, path, val = line.rsplit("|", 2)
        except ValueError:
            continue
        pid = inst.split("_")[1] if inst.startswith("pid_") else None
        key = "vram_mb" if "dedicated" in path else "gpu3d_pct"
        rows.setdefault(pid, {}).setdefault(key, 0.0)
        rows[pid][key] += float(val) / (1048576 if key == "vram_mb" else 1)
    return {pid: v for pid, v in rows.items() if pid in pids}


note("start", manifest=current["client_manifest"], port=current["port"])
cmd = [r"C:\Users\cheta\flutter\bin\flutter.bat", "test", "integration_test/fire_live_test.dart", "-d", "windows"]
flog = (OUT / "flutter-test.log").open("w", encoding="utf-8")
proc = subprocess.Popen(cmd, cwd=UI, env=env, stdout=flog, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW)
started_brain = stopped = restarted = False
samples = []
t0 = time.monotonic()
try:
    while proc.poll() is None:
        time.sleep(5)
        if not started_brain and (OUT / "ui-ready.json").exists():
            note("ui ready -> launcher -NoUi -OverrideGpu")
            r = subprocess.run(launcher, capture_output=True, text=True, timeout=600)
            note("launcher", rc=r.returncode, out=r.stdout[-1500:], err=r.stderr[-800:])
            started_brain = True
        if started_brain and not stopped and (OUT / "stop-brain.json").exists():
            hosts = brain_hosts()
            for h in hosts:
                for c in h.children(recursive=True):
                    c.kill()
                h.kill()
            note("brain host stopped (recoverable-error journey)", pids=[h.pid for h in hosts])
            stopped = True
        if stopped and not restarted and (OUT / "restart-brain.json").exists():
            r = subprocess.run(launcher, capture_output=True, text=True, timeout=600)
            note("brain host restarted", rc=r.returncode, out=r.stdout[-800:])
            restarted = True
        uis = [str(p.pid) for p in psutil.process_iter(["name", "exe"]) if (p.info["name"] or "").lower() == "uri_ui.exe"
               and str(UI).lower() in (p.info["exe"] or "").lower()]
        llama = [str(p.pid) for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "llama-server.exe"]
        g = gpu_sample(set(uis + llama))
        rss = {pid: round(psutil.Process(int(pid)).memory_info().rss / 1048576, 1) for pid in uis if psutil.pid_exists(int(pid))}
        bh = RT / "work/c1/ws-fire/client/control/oi/brain_host.json"
        state = json.loads(bh.read_text()).get("state") if bh.exists() else None
        samples.append(dict(t=round(time.monotonic() - t0, 1), ui=uis, llama=llama, gpu=g, ui_rss_mb=rss, brain_state=state))
        (OUT / "gpu-samples.json").write_text(json.dumps(samples))
        if time.monotonic() - t0 > 60 * 60:
            note("runner timeout")
            proc.kill()
finally:
    flog.close()
    note("flutter test finished", rc=proc.returncode)
    for f in ("brain_host.json",):
        p = RT / "work/c1/ws-fire/client/control/oi" / f
        if p.exists():
            shutil.copy2(p, OUT / f)
    driver.unlink(missing_ok=True)
    note("driver removed")
