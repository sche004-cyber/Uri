"""(RUNTIME-PROFILES-INTEG copy of the canonical UI V2 harness docs/ui_v2/postint/evidence/harness/live_session.py;
changes: paths, and --profile <ctx>,<vision>,<mtp> starts the Brain host on a derived resource profile through the
production parser ws_brain_host.parse_profile; without --profile the frozen config is used exactly as before.)
UI V2 completion live session host: candidate runtime's integrated server + one Runtime v1 Brain for a native UI run.

    runtime\\.venv\\Scripts\\python.exe -B -I tools\\live_session.py <run-label> [--minutes 50] [--no-brain]

Owns only installation uiv2c-a (port 18341) and one Brain started through the machine-wide GPU lease WITHOUT the
contention override (owner rule 2026-10-15: Brain/GPU allowed under the lease, no override). Brain first: the UI is
told to start (brain-ready.json) only after the Brain is READY, so the lease fit sees only foreign GPU use. Samples
GPU per-process memory, CPU and RSS of owned processes and of the UI every 3 s. Stops when the driver writes
ui-finished.json, on timeout, or on fixtures/stop-<label>. Never touches port 8000, other sessions' processes,
scheduled tasks or the owner's preferences.
"""
import datetime, hashlib, json, os, pathlib, subprocess, sys, threading, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LABEL = sys.argv[1]
MINUTES = float(sys.argv[sys.argv.index("--minutes") + 1]) if "--minutes" in sys.argv else 50
NO_BRAIN = "--no-brain" in sys.argv
SRC, RT = pathlib.Path(r"D:\uri-dev\uri-runtime-profiles-integ"), ROOT / "runtime-e"
PROFILE = sys.argv[sys.argv.index("--profile") + 1] if "--profile" in sys.argv else None
sys.path.insert(0, str(SRC))
import psutil  # noqa: E402
from scripts.ws_brain_host import Host  # noqa: E402
from uri_operational_intelligence import gpu_lease as G, runtime_v1 as R  # noqa: E402
from uri_operational_intelligence import runtime_profiles as RP  # noqa: E402
from scripts.ws_brain_host import parse_profile  # noqa: E402

OUT = ROOT / f"evidence/live/{LABEL}"
OUT.mkdir(parents=True, exist_ok=True)
STOP = ROOT / f"fixtures/stop-{LABEL}"
STOP.parent.mkdir(exist_ok=True)
STOP.unlink(missing_ok=True)
CURRENT = json.loads((ROOT / "evidence/runtime/ws-current.json").read_text())
UI_EXE = str(SRC / "uri_ui/build/windows/x64/runner/Debug/uri_ui.exe").lower()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def verify_runtime():
    """Every file the materializer copied from the candidate is still byte-identical in the runtime and in the
    candidate checkout (only uri_ui changed since; it runs from the candidate, not from the runtime)."""
    receipt = json.loads((RT / "OI_MATERIALIZATION_RECEIPT.json").read_text())
    bad = [rel for rel, digest in receipt["oi_files_copied"].items()
           if sha(RT / rel) != digest or not (SRC / rel).exists() or sha(SRC / rel) != digest]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SRC, text=True).strip()
    return dict(ok=not bad and receipt["head_is_base"], mismatched=bad[:20], checked_files=len(receipt["oi_files_copied"]),
                runtime_head=receipt["head"], materialized_from=receipt["candidate_head"], source_head=head)


def main():
    verified = verify_runtime()
    sys.path.insert(0, str(ROOT / "tools"))
    import binding
    verified["binding"] = binding.require(RT)
    assert verified["ok"], verified
    port = CURRENT["port"]
    assert R._listener_pid(port) is None, f"port {port} busy"
    manifest = json.loads(pathlib.Path(CURRENT["server_manifest"]).read_text())
    state = pathlib.Path(manifest["state_root"])
    cfg = R.load_config()
    from uri_operational_intelligence import runtime_profile_selection as PS
    sel = PS.selection_path(CURRENT["client_root"])
    if PROFILE:
        cfg = RP.derive_config(cfg, *parse_profile(PROFILE))
        PS.write(CURRENT["client_root"], *parse_profile(PROFILE))   # the worker verifies the same profile
    else:
        sel.unlink(missing_ok=True)                                  # frozen: no selection file
    record = dict(label=LABEL, port=port, started_utc=now(), no_brain=NO_BRAIN, profile_arg=PROFILE,
                  profile=RP.describe(cfg),
                  verified=verified,
                  brain_config_sha256_before=sha(R.CONFIG_PATH), lease_before=G.peek(), override=False)
    samples, owned = [], {}
    cpu_seen = {}

    def proc_row(name, p):
        try:
            key = (p.pid, p.create_time())
            if key not in cpu_seen:
                cpu_seen[key] = p
                p.cpu_percent(None)
                cpu = None
            else:
                cpu = cpu_seen[key].cpu_percent(None)
            return dict(name=name, pid=p.pid, rss_mib=round(p.memory_info().rss / 2**20, 1), cpu_pct=cpu)
        except psutil.Error:
            return None

    def census():
        c = G.census()
        procs = []
        for name, pid in list(owned.items()):
            try:
                row = proc_row(name, psutil.Process(pid))
                if row:
                    procs.append(row)
            except psutil.Error:
                pass
        for p in psutil.process_iter(["name", "exe"]):
            try:
                if (p.info["name"] or "").lower() == "uri_ui.exe" and (p.info["exe"] or "").lower() == UI_EXE:
                    row = proc_row("uri_ui", p)
                    if row:
                        procs.append(row)
                if ((p.info["name"] or "").lower() == "llama-server.exe" and p.pid not in owned.values()
                        and os.getpid() in {a.pid for a in p.parents()}):
                    owned["llama-server"] = p.pid          # only our own Brain, never another session's
            except psutil.Error:
                pass
        gpu = {str(x["pid"]): dict(name=x.get("name"), dedicated_mib=x["dedicated_mib"], non_local_mib=x.get("non_local_mib"))
               for x in c.get("processes", []) if x.get("name") in ("uri_ui.exe", "llama-server.exe", "dwm.exe")}
        vm = psutil.virtual_memory()
        try:
            sw = psutil.swap_memory()
            commit_free = round((vm.available + sw.free) / 2**20)
        except Exception:
            commit_free = None
        samples.append(dict(utc=now(), adapter_dedicated_mib=c.get("adapter_dedicated_mib"), card_mib=c.get("card_mib"),
                            commit_free_est_mib=commit_free,
                            gpu=gpu, owned=procs, ram_available_mib=round(psutil.virtual_memory().available / 2**20),
                            lease=G.peek().get("state")))
        (OUT / "resource-samples.json").write_text(json.dumps(samples, indent=1, default=str))

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
    print(json.dumps({k: record[k] for k in ("label", "port", "server_pid", "server_listen_s", "server_listening")}), flush=True)
    sampling = threading.Event()

    def sampler():
        while not sampling.wait(3):
            try:
                census()
            except Exception as exc:  # sampling must never stop the session
                samples.append(dict(utc=now(), sample_error=repr(exc)))
    threading.Thread(target=sampler, daemon=True).start()
    host = None
    try:
        deadline = time.monotonic() + MINUTES * 60
        if NO_BRAIN:
            (OUT / "brain-ready.json").write_text(json.dumps(dict(state="NO_BRAIN_BY_DESIGN", utc=now())))
            while not ((OUT / "ui-finished.json").exists() or STOP.exists() or server.poll() is not None
                       or time.monotonic() > deadline):
                time.sleep(1)
        else:
            host = Host(pathlib.Path(CURRENT["client_root"]) / "control/oi", minutes=MINUTES, override=False, cfg=cfg,
                        state_dir=ROOT / f"fixtures/brain-state-{LABEL}", census=G.census)
            host.state_dir.mkdir(parents=True, exist_ok=True)
            cache = ROOT.parent / "uri-core-live-verification-20261014/fixtures/brain-artifact-cache/artifact_hash_cache.json"
            if cache.exists():
                (host.state_dir / "artifact_hash_cache.json").write_bytes(cache.read_bytes())
            done = threading.Event()
            phases = []

            def watch():
                t_load = time.monotonic()
                while not done.wait(0.5):
                    st = host.report.get("state")
                    if not phases or phases[-1]["state"] != st:
                        phases.append(dict(state=st, t=round(time.monotonic() - t_load, 2), explain=host.report.get("explain"),
                                           detail=host.report.get("detail")))
                        (OUT / "brain-phases.json").write_text(json.dumps(phases, indent=1))
                    if st in ("READY", "DEGRADED", "FAILED") and not (OUT / "brain-ready.json").exists():
                        (OUT / "brain-ready.json").write_text(json.dumps(dict(state=st, load_s=round(time.monotonic() - t_load, 2),
                                                                              utc=now(), host=host.report), indent=1, default=str))
                    if ((OUT / "ui-finished.json").exists() or STOP.exists() or server.poll() is not None
                            or (OUT / "stop-brain.json").exists()):
                        host.stop_file.parent.mkdir(parents=True, exist_ok=True)
                        host.stop_file.write_text("UI V2 completion session step")
                        if (OUT / "stop-brain.json").exists():
                            (OUT / "stop-brain.json").rename(OUT / "stop-brain.done.json")
            threading.Thread(target=watch, daemon=True).start()
            record["brain_exit_code"] = host.run()
            done.set()
            # A deliberate Brain stop (failure journey) leaves the server running until the UI finishes.
            while not ((OUT / "ui-finished.json").exists() or STOP.exists() or server.poll() is not None
                       or time.monotonic() > deadline):
                time.sleep(1)
    finally:
        sampling.set()
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
                      server_listener_after=R._listener_pid(port), host_final=host.report if host else None)
        wi = pathlib.Path(CURRENT["client_root"]) / "control" / "worker-instance.json"
        if wi.exists():
            (OUT / "worker-instance.json").write_bytes(wi.read_bytes())
        (OUT / "session-final.json").write_text(json.dumps(record, indent=1, default=str))
        print(json.dumps({k: record.get(k) for k in ("label", "server_exit", "brain_exit_code", "lease_after",
                                                     "brain_listener_after_3s", "server_listener_after")}, default=str), flush=True)


if __name__ == "__main__":
    main()
