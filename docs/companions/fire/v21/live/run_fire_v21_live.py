r"""Run the Ember V2.1 live qualification driver (V2 runner retargeted; OD-V21-1 extends OD-8) on the real Windows app (mode: first | returning).

    <runtime>\.venv\Scripts\python.exe -B docs\companions\fire\v21\live\run_fire_v21_live.py first|returning

V2 changes from the V1 runner: paths point at the V2 worktree and its own disposable runtime; two modes (first-time
user with fresh preferences, then returning user with the same preferences); in returning mode no Brain is started.
GPU lease (owner decision OD-8): the Brain host is started by the guarded launcher and WAITS for the machine-wide
lease (WAITING_FOR_LEASE); this runner never touches another session's lease, Brain or processes. -OverrideGpu
relaxes only the free-VRAM check. Stops are graceful through this runtime's own stop file.

UI first: the driver starts the production main() and writes ui-ready.json; only then is the Brain host started
through the guarded launcher (-NoUi -OverrideGpu, owner-authorized for this run, see
OWNER_GPU_OVERRIDE_AUTHORIZATION.json). On stop-brain.json the Brain host this script started is stopped (the
recoverable-error journey); on restart-brain.json it is started again. Owner preferences are never touched
(APPDATA/LOCALAPPDATA redirected, preference store redirected). GPU counters for the window are sampled every 5 s.
"""
import datetime, json, os, pathlib, shutil, subprocess, sys, time

import psutil

MODE = sys.argv[1] if len(sys.argv) > 1 else "first"
assert MODE in ("first", "returning"), MODE
SRC = pathlib.Path(r"C:\Users\cheta\Development\uri-fire-companion-v21")
RT = pathlib.Path(r"C:\Users\cheta\Development\uri-fire-companion-v2-rt")
LIVE = pathlib.Path(r"C:\Users\cheta\Development\uri-fire-companion-v21-live")
UI = SRC / "uri_ui"
OUT = LIVE / "evidence"
FX = LIVE / "fixtures"
current = json.loads((RT / "work/c1/ws-current.json").read_text())
for p in (OUT, FX / "prefs", FX / "local/roaming", FX / "local/temp"):
    p.mkdir(parents=True, exist_ok=True)
driver = UI / "integration_test/fire_v21_live_test.dart"
# Read from the live folder: the UI tree itself must stay at the runtime receipt's commit.
shutil.copy2(LIVE / "fire_v21_live_driver.dart", driver)
nuget = pathlib.Path(r"C:\Users\cheta\Development\uri-windows-live-qualification-20261013\candidate\uri_ui\build\windows\x64\nuget.exe")
dest = UI / "build/windows/x64/nuget.exe"
if nuget.exists() and not dest.exists():
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(nuget, dest)
env = dict(os.environ, URI_CLIENT_MANIFEST=current["client_manifest"], URI_LIVING_SKIP_ONBOARDING="1",
           URI_QUAL_PREFS=str(FX / "prefs"), URI_QUAL_UI_OUT=str(OUT), LOCALAPPDATA=str(FX / "local"),
           APPDATA=str(FX / "local/roaming"), TEMP=str(FX / "local/temp"), TMP=str(FX / "local/temp"),
           URI_QUAL_MODE=MODE, URI_QUAL_BRAIN_HOST=str(pathlib.Path(current["client_root"]) / "control/oi/brain_host.json"), URI_QUAL_BRAIN_WAIT_MIN=os.environ.get("URI_QUAL_BRAIN_WAIT_MIN", "30"),
           PATH=str(nuget.parent) + os.pathsep + os.environ["PATH"], PYTHONDONTWRITEBYTECODE="1")
launcher = ["powershell", "-NoProfile", "-File", str(SRC / "scripts/launch_uri_working_system.ps1"),
            "-RuntimeRoot", str(RT), "-UiRoot", str(SRC), "-NoUi", "-OverrideGpu", "-BrainMinutes", "90"]
log = []


def note(event, **kw):
    log.append(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), event=event, **kw))
    (OUT / f"runner-log-{MODE}.json").write_text(json.dumps(log, indent=1))


STOP_FILE = RT / "work/oi/state/runtime_v1.stop"


def stop_brain_hosts(reason, wait_s=150):
    """Graceful stop through the host's own stop file, so it stops the server
    and releases the GPU lease itself; kill only what is left after wait_s."""
    hosts = brain_hosts()
    if not hosts:
        return []
    STOP_FILE.parent.mkdir(parents=True, exist_ok=True)
    STOP_FILE.write_text(json.dumps({"by": "run_fire_live", "reason": reason}))
    end = time.monotonic() + wait_s
    while time.monotonic() < end and any(h.is_running() for h in hosts):
        time.sleep(2)
    killed = []
    for h in hosts:
        try:
            if h.is_running():
                for c in h.children(recursive=True):
                    c.kill()
                h.kill()
                killed.append(h.pid)
        except psutil.NoSuchProcess:
            pass
    STOP_FILE.unlink(missing_ok=True)
    note("brain host stop", reason=reason, pids=[h.pid for h in hosts], killed_after_wait=killed)
    return hosts


def brain_hosts():
    out = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        cl = " ".join(p.info["cmdline"] or [])
        if "ws_brain_host.py" in cl and str(RT).lower() in cl.lower():
            out.append(p)
    return out


GUARD_WAIT_MIN = float(os.environ.get("URI_QUAL_BRAIN_WAIT_MIN", "30"))


def lease_state():
    r = subprocess.run([str(RT / ".venv/Scripts/python.exe"), "-m", "uri_operational_intelligence.gpu_lease", "status"],
                       cwd=RT, capture_output=True, text=True, timeout=120)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"state": "UNKNOWN", "raw": r.stdout[-300:]}


def lease_free_and_no_brain():
    if any((p.info["name"] or "").lower() == "llama-server.exe" for p in psutil.process_iter(["name"])):
        return False
    return lease_state().get("state") == "FREE"


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
cmd = [r"C:\Users\cheta\flutter\bin\flutter.bat", "test", "integration_test/fire_v21_live_test.dart", "-d", "windows"]
flog = (OUT / f"flutter-test-{MODE}.log").open("w", encoding="utf-8")
for stale in ("ui-ready.json", "stop-brain.json", "restart-brain.json"):
    (OUT / stale).unlink(missing_ok=True)
proc = subprocess.Popen(cmd, cwd=UI, env=env, stdout=flog, stderr=subprocess.STDOUT,
                        creationflags=subprocess.CREATE_NO_WINDOW)
started_brain = stopped = restarted = False
samples = []
t0 = time.monotonic()
try:
    while proc.poll() is None:
        time.sleep(5)
        if time.monotonic() - t0 > 60 * 60:
            note("runner timeout")
            proc.kill()
            break
        if MODE == "first" and not started_brain and (OUT / "ui-ready.json").exists():
            # OD-8 guard (live run 1, 2026-10-15): the launcher ATTACHES to any Runtime v1 server already
            # listening, so with another session's Brain running our turns would go to that session's Brain.
            # Start only when the lease is FREE and no llama-server runs; otherwise wait, then give up (the
            # driver records BLOCKED because the Brain is not ours).
            if not lease_free_and_no_brain():
                if time.monotonic() - t0 < 60 * GUARD_WAIT_MIN:
                    continue
                note("Brain not started: lease held or another session's llama-server running", lease=lease_state())
                started_brain = True
                continue
            note("ui ready -> launcher -NoUi -OverrideGpu", lease=lease_state())
            r = subprocess.run(launcher, capture_output=True, text=True, timeout=600)
            note("launcher", rc=r.returncode, out=r.stdout[-1500:], err=r.stderr[-800:])
            started_brain = True
        if started_brain and not stopped and (OUT / "stop-brain.json").exists():
            stop_brain_hosts("recoverable-error journey")
            stopped = True
        if stopped and not restarted and (OUT / "restart-brain.json").exists():
            STOP_FILE.unlink(missing_ok=True)
            r = subprocess.run(launcher, capture_output=True, text=True, timeout=600)
            note("brain host restarted", rc=r.returncode, out=r.stdout[-800:])
            restarted = True
        try:
            uis = [str(p.pid) for p in psutil.process_iter(["name", "exe"]) if (p.info["name"] or "").lower() == "uri_ui.exe"
                   and str(UI).lower() in (p.info["exe"] or "").lower()]
            llama = [str(p.pid) for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "llama-server.exe"]
            g = gpu_sample(set(uis + llama))
            rss = {pid: round(psutil.Process(int(pid)).memory_info().rss / 1048576, 1) for pid in uis}
        except (psutil.NoSuchProcess, psutil.AccessDenied, subprocess.TimeoutExpired):
            continue
        bh = pathlib.Path(current["client_root"]) / "control/oi/brain_host.json"
        state = json.loads(bh.read_text()).get("state") if bh.exists() else None
        samples.append(dict(t=round(time.monotonic() - t0, 1), ui=uis, llama=llama, gpu=g, ui_rss_mb=rss, brain_state=state))
        (OUT / f"gpu-samples-{MODE}.json").write_text(json.dumps(samples))
finally:
    if proc.poll() is None:
        proc.kill()
    flog.close()
    note("flutter test finished", rc=proc.returncode)
    # Leave nothing running that this run started: the Brain host (graceful,
    # lease released) and any test window of this UI tree.
    stop_brain_hosts("end of run")
    for p in psutil.process_iter(["name", "exe"]):
        try:
            if (p.info["name"] or "").lower() == "uri_ui.exe" and str(UI).lower() in (p.info["exe"] or "").lower():
                p.kill()
                note("orphan test window closed", pid=p.pid)
        except psutil.NoSuchProcess:
            pass
    for f in ("brain_host.json",):
        p = pathlib.Path(current["client_root"]) / "control/oi" / f
        if p.exists():
            shutil.copy2(p, OUT / f"{MODE}-{f}")
    driver.unlink(missing_ok=True)
    note("driver removed")
