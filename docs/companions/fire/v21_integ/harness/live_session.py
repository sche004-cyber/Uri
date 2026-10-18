"""EMBER-V21-INTEG live session host (adapted from the UI V2 freeze harness live_session.py).

    D:\\uri-dev\\uri-ember-rt\\.venv\\Scripts\\python.exe -B -I tools\\live_session.py <run-label> [--minutes 60] [--no-brain]

Owns only installation ws-ember of runtime D:\\uri-dev\\uri-ember-rt (materialized from the candidate) and one
Runtime v1 Brain started through the machine-wide GPU lease WITHOUT the contention override. Order is UI first
(launcher order, P-GOV-1; also needed to observe Initializing): the server starts, then the Brain host starts only
when the driver writes ui-ready.json. stop-brain.json stops our Brain (unavailable journey); restart-brain.json starts
it again (recovery journey). Samples GPU memory of owned processes and the UI every 3 s. Stops when the driver writes
ui-finished.json, on timeout, or on fixtures/stop-<label>. Never touches other sessions' processes or leases, port
8000, scheduled tasks or the owner's preferences.
"""
import datetime, hashlib, json, os, pathlib, subprocess, sys, threading, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LABEL = sys.argv[1]
MINUTES = float(sys.argv[sys.argv.index("--minutes") + 1]) if "--minutes" in sys.argv else 60
NO_BRAIN = "--no-brain" in sys.argv
SRC, RT = pathlib.Path(r"D:\uri-dev\uri-ember-v21-integ"), pathlib.Path(r"D:\uri-dev\uri-ember-rt2")
sys.path.insert(0, str(SRC))
import psutil  # noqa: E402
from scripts.ws_brain_host import Host  # noqa: E402
from uri_operational_intelligence import gpu_lease as G, runtime_v1 as R  # noqa: E402

OUT = ROOT / f"evidence/live/{LABEL}"
OUT.mkdir(parents=True, exist_ok=True)
STOP = ROOT / f"fixtures/stop-{LABEL}"
STOP.parent.mkdir(exist_ok=True)
STOP.unlink(missing_ok=True)
CURRENT = json.loads((ROOT / "evidence/runtime/ws-current.json").read_text())


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def verify_runtime():
    receipt = json.loads((RT / "OI_MATERIALIZATION_RECEIPT.json").read_text())
    bad = [rel for rel, digest in receipt["oi_files_copied"].items()
           if sha(RT / rel) != digest or not (SRC / rel).exists() or sha(SRC / rel) != digest]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SRC, text=True).strip()
    return dict(ok=not bad and receipt["head_is_base"], mismatched=bad[:20], checked_files=len(receipt["oi_files_copied"]),
                runtime_head=receipt["head"], materialized_from=receipt["candidate_head"], source_head=head)


def main():
    verified = verify_runtime()
    assert verified["ok"], verified
    port = CURRENT["port"]
    assert R._listener_pid(port) is None, f"port {port} busy"
    manifest = json.loads(pathlib.Path(CURRENT["server_manifest"]).read_text())
    state = pathlib.Path(manifest["state_root"])
    cfg = R.load_config()
    record = dict(label=LABEL, port=port, started_utc=now(), no_brain=NO_BRAIN, verified=verified,
                  brain_config_sha256_before=sha(R.CONFIG_PATH), lease_before=G.peek(), override=False)
    samples, owned = [], {}

    def census():
        c = G.census()
        for p in psutil.process_iter(["name"]):
            try:
                if ((p.info["name"] or "").lower() == "llama-server.exe"
                        and os.getpid() in {a.pid for a in p.parents()}):
                    owned["llama-server"] = p.pid          # only our own Brain, never another session's
            except psutil.Error:
                pass
        gpu = {str(x["pid"]): dict(name=x.get("name"), dedicated_mib=x["dedicated_mib"], non_local_mib=x.get("non_local_mib"))
               for x in c.get("processes", []) if x.get("name") in ("uri_ui.exe", "llama-server.exe", "dwm.exe")}
        samples.append(dict(utc=now(), adapter_dedicated_mib=c.get("adapter_dedicated_mib"), card_mib=c.get("card_mib"),
                            gpu=gpu, owned=dict(owned), lease=G.peek().get("state")))
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
    hosts, phases = [], []
    deadline = time.monotonic() + MINUTES * 60

    def finished():
        return (OUT / "ui-finished.json").exists() or STOP.exists() or server.poll() is not None or time.monotonic() > deadline

    def run_brain(n):
        host = Host(pathlib.Path(CURRENT["client_root"]) / "control/oi", minutes=MINUTES, override=False, cfg=cfg,
                    state_dir=ROOT / f"fixtures/brain-state-{LABEL}", census=G.census)
        host.state_dir.mkdir(parents=True, exist_ok=True)
        cache = pathlib.Path(r"C:\Users\cheta\Development\uri-core-live-verification-20261014") / "fixtures/brain-artifact-cache/artifact_hash_cache.json"
        if cache.exists():
            (host.state_dir / "artifact_hash_cache.json").write_bytes(cache.read_bytes())
        hosts.append(host)
        done = threading.Event()
        t_load = time.monotonic()
        ready_name = "brain-ready.json" if n == 0 else f"brain-ready-{n}.json"

        def watch():
            while not done.wait(0.5):
                st = host.report.get("state")
                if not phases or phases[-1]["state"] != st or phases[-1]["run"] != n:
                    phases.append(dict(run=n, state=st, t=round(time.monotonic() - t_load, 2), utc=now(),
                                       explain=host.report.get("explain"), detail=host.report.get("detail")))
                    (OUT / "brain-phases.json").write_text(json.dumps(phases, indent=1))
                if st in ("READY", "DEGRADED", "FAILED") and not (OUT / ready_name).exists():
                    (OUT / ready_name).write_text(json.dumps(dict(state=st, load_s=round(time.monotonic() - t_load, 2),
                                                                  utc=now(), host=host.report), indent=1, default=str))
                if finished() or (OUT / "stop-brain.json").exists():
                    host.stop_file.parent.mkdir(parents=True, exist_ok=True)
                    host.stop_file.write_text("EMBER-V21-INTEG session step")
                    if (OUT / "stop-brain.json").exists():
                        (OUT / "stop-brain.json").rename(OUT / f"stop-brain.done-{n}.json")
        threading.Thread(target=watch, daemon=True).start()
        record[f"brain_exit_code_{n}"] = host.run()
        done.set()
        host.stop_file.unlink(missing_ok=True)

    try:
        if NO_BRAIN:
            (OUT / "brain-ready.json").write_text(json.dumps(dict(state="NO_BRAIN_BY_DESIGN", utc=now())))
        else:
            while not ((OUT / "ui-ready.json").exists() or finished()):
                time.sleep(0.5)
            record["ui_ready_seen_utc"] = now()
            n = 0
            if not finished():
                run_brain(n)
            while not finished():
                if (OUT / "restart-brain.json").exists():
                    (OUT / "restart-brain.json").rename(OUT / f"restart-brain.done-{n + 1}.json")
                    n += 1
                    run_brain(n)
                time.sleep(0.5)
        while not finished():
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
                      server_listener_after=R._listener_pid(port),
                      host_final=[h.report for h in hosts])
        (OUT / "session-final.json").write_text(json.dumps(record, indent=1, default=str))
        print(json.dumps({k: record.get(k) for k in ("label", "server_exit", "lease_after",
                                                     "brain_listener_after_3s", "server_listener_after")}, default=str), flush=True)


if __name__ == "__main__":
    main()
