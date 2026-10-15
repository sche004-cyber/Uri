"""O2 readiness real-application session host (owner directive 2026-10-15, Office audit and O2 repairs).

Copied from the O2 qualification harness (uri-o2-live-20261015). Change: the runtime is materialized from the
readiness candidate WITH uri_office and pypdf (B4/O2-RT-1); the app starts Office from the client manifest.


    runtime\\.venv\\Scripts\\python.exe -B -I harness\\o2q_session.py <run-name> [--brain] [--minutes 60]

Owns, for one native UI run of the ORIGINAL production main():
  * the materialized runtime's integrated paired Core server for installation o2q-a (port 18327), verified against the
    candidate source first (scripts/ws_materialized_verify.py);
  * with --brain: one Runtime v1 Brain through the accepted WS Brain host and the machine-wide GPU lease, WITHOUT the
    contention override (owner 2026-10-15: "not authorization to bypass leases"). The Brain starts BEFORE the UI is
    allowed to launch, so the lease's fit check sees only foreign GPU use; the UI and Office then join, and the Brain's
    residency (dedicated / non-local GPU memory of llama-server) is sampled to see whether Office causes demotion;
  * the URI Office service ONLY when the driver asks for it (fixtures/<run>/office-start-request.json), i.e. when the
    application itself cannot start it. The request and the reason are recorded.

Samples every 5 s: GPU census (gpu_lease.census), per-process dedicated and non-local GPU memory for owned processes
and Office workers, RSS of owned processes. Stops when the driver writes ui-finished.json, on timeout, or on
fixtures/<run>/stop. Never touches port 8000, other sessions' processes, scheduled tasks or the owner's preferences.
"""
import datetime, hashlib, json, os, pathlib, subprocess, sys, threading, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
# Fixtures (documents, saved outputs, redirected profile) stay under the user profile: the Office service only
# opens files inside the user home by default (M1 AC7, finding UX-ROOT-1), and C: is short of space, so only
# these small files live there; runtime, build and evidence are on D:.
FXR = pathlib.Path(r"C:\Users\cheta\uri-o2r-fixtures")
RUN = sys.argv[1]
BRAIN = "--brain" in sys.argv
MINUTES = float(sys.argv[sys.argv.index("--minutes") + 1]) if "--minutes" in sys.argv else 60
SRC, RT = ROOT / "candidate", ROOT / "runtime"
sys.path.insert(0, str(SRC))
import psutil  # noqa: E402
from scripts import ws_materialized_verify as V  # noqa: E402
from scripts.ws_brain_host import Host  # noqa: E402
from uri_operational_intelligence import gpu_lease as G, runtime_v1 as R  # noqa: E402

OUT = ROOT / f"evidence/live/{RUN}"
OUT.mkdir(parents=True, exist_ok=True)
FX = FXR / f"{RUN}"
FX.mkdir(parents=True, exist_ok=True)
STOP = FX / "stop"
STOP.unlink(missing_ok=True)
CURRENT = json.loads((ROOT / "evidence/ws-current-o2q-c.json").read_text())
SYSTEM_PY = r"C:\Users\cheta\AppData\Local\Programs\Python\Python313\python.exe"   # base interpreter of the runtime venv
REAL_ENGINES = pathlib.Path(os.environ["LOCALAPPDATA"]) / "URI" / "engines"


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def gpu_per_process(pids):
    """Dedicated and non-local GPU memory (MiB) per pid from the Windows GPU Process Memory counters."""
    if not pids:
        return {}
    ps = ("$ErrorActionPreference='SilentlyContinue';"
          "$s=(Get-Counter '\\GPU Process Memory(*)\\Dedicated Usage','\\GPU Process Memory(*)\\Non Local Usage').CounterSamples;"
          "$s | ForEach-Object { '{0}|{1}|{2}' -f $_.Path,$_.InstanceName,$_.CookedValue }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60)
    out = {}
    for line in r.stdout.splitlines():
        try:
            path, inst, val = line.rsplit("|", 2)
            pid = int(inst.split("_")[1])
        except (ValueError, IndexError):
            continue
        if pid not in pids:
            continue
        kind = "dedicated_mib" if "dedicated usage" in path.lower() else "nonlocal_mib"
        row = out.setdefault(pid, {"dedicated_mib": 0.0, "nonlocal_mib": 0.0})
        row[kind] += float(val) / 2**20
    return {p: {k: round(v, 1) for k, v in d.items()} for p, d in out.items()}


def main():
    verified = V.verify(SRC, RT)
    assert verified["ok"], verified
    port = CURRENT["port"]
    assert R._listener_pid(port) is None, f"port {port} busy"
    manifest = json.loads(pathlib.Path(CURRENT["server_manifest"]).read_text())
    state = pathlib.Path(manifest["state_root"])
    cfg = R.load_config()
    record = dict(run=RUN, brain_mode=BRAIN, port=port, started_utc=now(),
                  verified={k: verified.get(k) for k in ("ok", "source_head", "source_tree", "checked_files")},
                  brain_config_sha256_before=sha(R.CONFIG_PATH), lease_before=G.peek(),
                  gpu_authority="owner directive 2026-10-15 B5: Brain/GPU testing under the existing GPU lease, "
                                "runtime safety and permission controls; no contention override")
    samples, owned = [], {}
    office = {"proc": None}

    def office_family():
        p = office["proc"]
        pids = set()
        if p is not None and p.poll() is None:
            try:
                pids = {p.pid} | {c.pid for c in psutil.Process(p.pid).children(recursive=True)}
            except psutil.Error:
                pass
        # Office processes the application started itself (after the O2 repair) are found by command line.
        for c in psutil.process_iter(["pid", "cmdline"]):
            try:
                cl = " ".join(c.info["cmdline"] or [])
            except psutil.Error:
                continue
            if "uri_office" in cl and str(ROOT) in cl:
                pids.add(c.info["pid"])
                try:
                    pids |= {x.pid for x in psutil.Process(c.info["pid"]).children(recursive=True)}
                except psutil.Error:
                    pass
        return pids

    office_cmdlines = {}

    def census():
        c = G.census()
        fam = office_family()
        for pid in fam:                      # B4 evidence: which interpreter and source the app started Office from
            if pid not in office_cmdlines:
                try:
                    office_cmdlines[pid] = psutil.Process(pid).cmdline()
                except psutil.Error:
                    pass
        record["office_cmdlines"] = {str(k): v for k, v in office_cmdlines.items()}
        watch = {pid for pid in owned.values()} | fam
        brain_pid = R._listener_pid(cfg["runtime"]["port"])
        if brain_pid:
            watch.add(brain_pid)
        ui = [p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "uri_ui.exe"]
        watch |= set(ui)
        gpu = gpu_per_process(watch)
        procs = []
        for pid in sorted(watch):
            try:
                p = psutil.Process(pid)
                procs.append(dict(pid=pid, name=p.name(), rss_mib=round(p.memory_info().rss / 2**20, 1),
                                  cpu_pct=p.cpu_percent(None), gpu=gpu.get(pid), ppid=p.ppid(),
                                  created=round(p.create_time(), 1),
                                  ours=str(ROOT).lower() in " ".join(p.cmdline()).lower() or
                                  any(str(ROOT).lower() in " ".join(a.cmdline()).lower() for a in p.parents()[:4])))
            except psutil.Error:
                pass
        samples.append(dict(utc=now(), census=c, fit=G.assess_fit(c), brain_pid=brain_pid, watched=procs,
                            ram_available_mib=round(psutil.virtual_memory().available / 2**20)))
        (OUT / "resource-samples.json").write_text(json.dumps(samples, indent=1, default=str))
        return c

    command = [str(RT / ".venv/Scripts/python.exe"), "-B", "-I", str(RT / "scripts/run_uri_integrated_server.py"),
               "--manifest", CURRENT["server_manifest"]]
    log = (OUT / "integrated-server.log").open("w", encoding="utf-8")
    t0 = time.monotonic()
    server = subprocess.Popen(command, cwd=state, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    owned["server"] = server.pid

    def family():
        try:
            return {server.pid} | {c.pid for c in psutil.Process(server.pid).children(recursive=True)}
        except psutil.Error:
            return {server.pid}
    while R._listener_pid(port) not in family() and server.poll() is None and time.monotonic() - t0 < 60:
        time.sleep(0.1)
    lp = R._listener_pid(port)
    record.update(server_pid=server.pid, server_listener_pid=lp, server_listen_s=round(time.monotonic() - t0, 3),
                  server_listening=lp in family())
    if not record["server_listening"]:
        STOP.write_text("SERVER_NOT_LISTENING")
    (OUT / "session-start.json").write_text(json.dumps(record, indent=1, default=str))
    print(json.dumps({k: record[k] for k in ("run", "port", "server_pid", "server_listen_s", "server_listening")}),
          flush=True)
    host = None
    brain_thread = None
    done = threading.Event()
    deadline = time.monotonic() + MINUTES * 60
    try:
        if BRAIN:
            host = Host(pathlib.Path(CURRENT["client_root"]) / "control/oi", minutes=MINUTES, override=False, cfg=cfg,
                        state_dir=FX / "brain-state", census=census)
            host.state_dir.mkdir(parents=True, exist_ok=True)
            phases = []
            result = {}

            def run_host():
                result["exit"] = host.run()
            brain_thread = threading.Thread(target=run_host, daemon=True)
            brain_thread.start()
            t_load = time.monotonic()
            while True:
                st = host.report.get("state")
                if not phases or phases[-1]["state"] != st:
                    phases.append(dict(state=st, t=round(time.monotonic() - t_load, 2), explain=host.report.get("explain"),
                                       utc=now()))
                    (OUT / "brain-phases.json").write_text(json.dumps(phases, indent=1, default=str))
                if st in ("READY", "DEGRADED", "FAILED"):
                    (OUT / "brain-startup.json").write_text(json.dumps(dict(state=st, load_s=round(time.monotonic() - t_load, 2),
                                                                            host=host.report), indent=1, default=str))
                    break
                if time.monotonic() > deadline or STOP.exists() or server.poll() is not None or not brain_thread.is_alive():
                    raise SystemExit("BRAIN_NOT_READY")
                if int(time.monotonic()) % 5 == 0:
                    census()
                time.sleep(1)
        if BRAIN:
            r = subprocess.run([SYSTEM_PY, "-B", str(ROOT / "harness/classify_probe.py"), RUN,
                                f"http://127.0.0.1:{cfg['runtime']['port']}"], capture_output=True, text=True, timeout=600)
            (OUT / "classify_probe.log").write_text(r.stdout + r.stderr)
            census()
            r = subprocess.run([SYSTEM_PY, "-B", str(ROOT / "harness/brain_bench.py"), RUN, "brain-only-before-ui",
                                f"http://127.0.0.1:{cfg['runtime']['port']}"], capture_output=True, text=True, timeout=600)
            (OUT / "brain_bench.log").write_text(r.stdout + r.stderr)
        (FX / "ui-may-start.json").write_text(json.dumps({"utc": now(), "brain": BRAIN}))
        print(json.dumps({"ui_may_start": True, "brain": BRAIN}), flush=True)
        while not (OUT / "ui-finished.json").exists():
            if time.monotonic() > deadline or STOP.exists() or server.poll() is not None:
                break
            req = FX / "office-start-request.json"
            if req.exists() and office["proc"] is None:
                ask = json.loads(req.read_text())
                env = dict(os.environ, URI_ENGINES_ROOT=str(REAL_ENGINES), PYTHONDONTWRITEBYTECODE="1")
                args = [SYSTEM_PY, "-B", "-m", "uri_office.service", "run", "--state", ask["state"]]
                if BRAIN:
                    args += ["--brain-url", f"http://127.0.0.1:{cfg['runtime']['port']}"]
                olog = (OUT / "office-service.log").open("w", encoding="utf-8")
                office["proc"] = subprocess.Popen(args, cwd=SRC, env=env, stdin=subprocess.DEVNULL, stdout=olog,
                                                  stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
                record["office_started_by_harness"] = dict(utc=now(), reason=ask.get("reason"), args=args,
                                                           pid=office["proc"].pid)
                (OUT / "session-start.json").write_text(json.dumps(record, indent=1, default=str))
            for breq in sorted(FX.glob("bench-request-*.json")):
                tag = breq.stem[len("bench-request-"):]
                if not (FX / f"bench-done-{tag}.json").exists():
                    census()
                    r = subprocess.run([SYSTEM_PY, "-B", str(ROOT / "harness/brain_bench.py"), RUN, tag,
                                        f"http://127.0.0.1:{cfg['runtime']['port']}"], capture_output=True, text=True,
                                       timeout=600)
                    with (OUT / "brain_bench.log").open("a") as fh:
                        fh.write(r.stdout + r.stderr)
                    census()
                    (FX / f"bench-done-{tag}.json").write_text(json.dumps({"rc": r.returncode}))
            creq = FX / "corpus-request.json"
            if BRAIN and creq.exists() and not (FX / "corpus-done.json").exists():
                t_c = time.monotonic()
                r = subprocess.run([SYSTEM_PY, "-B", str(ROOT / "harness/brain_corpus.py"), RUN], capture_output=True,
                                   text=True, timeout=1800)
                (OUT / "brain_corpus.log").write_text(r.stdout + r.stderr)
                (FX / "corpus-done.json").write_text(json.dumps({"rc": r.returncode,
                                                                  "seconds": round(time.monotonic() - t_c, 1)}))
            if int(time.monotonic()) % 5 == 0:
                census()
            time.sleep(1)
        record["ui_finished_utc"] = now()
        if BRAIN and host is not None:
            # Phase D (readiness run): is the Brain's demotion sticky once the app has exited? Wait for the app's
            # processes to go, then the same 3-run calibration bench as before the UI.
            for _ in range(60):
                if not [p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "uri_ui.exe"]:
                    break
                time.sleep(1)
            time.sleep(10)
            census()
            r = subprocess.run([SYSTEM_PY, "-B", str(ROOT / "harness/brain_bench.py"), RUN, "after-ui-exit",
                                f"http://127.0.0.1:{cfg['runtime']['port']}"], capture_output=True, text=True, timeout=600)
            with (OUT / "brain_bench.log").open("a") as fh:
                fh.write(r.stdout + r.stderr)
            census()
        census()
        # Idle observation: Office workers and their GPU memory after the UI is done (release after idle).
        idle_end = time.monotonic() + (90 if (OUT / "ui-finished.json").exists() else 0)
        while time.monotonic() < idle_end and not STOP.exists():
            census()
            time.sleep(10)
    finally:
        done.set()
        if host is not None:
            host.stop_file.parent.mkdir(parents=True, exist_ok=True)
            host.stop_file.write_text("O2 qualification session complete")
            if brain_thread is not None:
                brain_thread.join(timeout=120)
        p = office["proc"]
        if p is not None and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=20)
            except subprocess.TimeoutExpired:
                p.kill()
        for pid in sorted(family() - {server.pid}):
            try:
                psutil.Process(pid).terminate()
            except psutil.Error:
                pass
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill(); server.wait(timeout=10)
        log.close()
        time.sleep(3)
        record.update(finished_utc=now(), server_exit=server.returncode, brain_config_sha256_after=sha(R.CONFIG_PATH),
                      lease_after=G.peek(), brain_listener_after_3s=R._listener_pid(cfg["runtime"]["port"]),
                      server_listener_after=R._listener_pid(port), host_final=host.report if host else None,
                      office_left=sorted(office_family()))
        (OUT / "session-final.json").write_text(json.dumps(record, indent=1, default=str))
        print(json.dumps({k: record.get(k) for k in ("run", "server_exit", "lease_after", "brain_listener_after_3s",
                                                     "server_listener_after", "office_left")}, default=str), flush=True)


if __name__ == "__main__":
    main()
