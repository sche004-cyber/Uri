"""UI-CONTROLS-TYPO-20261018 copy of the BRAIN-QC live session host (paths changed; --inject-fail-once <profile id>
starts the production host through inject_host.py, which fails the FIRST start of that profile inside a switch,
before anything is spawned; everything else is the unchanged production host).

BRAIN-QC-20261018 live session host: the materialized candidate runtime's integrated server plus the PRODUCTION
Brain host (`scripts/ws_brain_host.py`, started as its own process exactly as the launcher starts it, no override)
for one native UI run of the Quick Controls driver.

    <runtime>\\.venv\\Scripts\\python.exe -B -I qc_session.py <label> [--minutes 45]

* Waits for a FREE machine-wide GPU lease before starting the Brain host (the host then takes the lease itself and
  waits/explains on contention). Never stops, signals or overrides another holder.
* Brain first: brain-ready.json is written when the host reports READY / DEGRADED / FAILED, then the UI runner starts.
* Samples every 2 s: the host report (state, profile, profile_switch, calibration, residency, last request), the GPU
  census (per-process dedicated / non-local MiB of llama-server, uri_ui, dwm), the llama-server pid, the integrated
  worker pid(s) of this client, and the lease state. Written to samples.json.
* Stops when the driver writes ui-finished.json, on timeout, or on stop-<label>: writes the host's stop file (the
  host stops its own server and releases the lease), then ends the integrated server it started.
"""
import datetime
import json
import pathlib
import subprocess
import sys
import threading
import time

LABEL = sys.argv[1]
MINUTES = float(sys.argv[sys.argv.index("--minutes") + 1]) if "--minutes" in sys.argv else 45
# Do not take a FREE lease before this local time (HH:MM): another session's announced live window comes first.
NOT_BEFORE = sys.argv[sys.argv.index("--not-before") + 1] if "--not-before" in sys.argv else None
HERE = pathlib.Path(__file__).resolve().parent
EVID = HERE.parent
OUT = EVID / "live" / LABEL
OUT.mkdir(parents=True, exist_ok=True)
RT = pathlib.Path(r"D:\uri-dev\uri-ui-typo-live\runtime")
CURRENT = json.loads((RT / "work/c1/ws-current.json").read_text())
sys.path.insert(0, str(RT))
import psutil  # noqa: E402
from uri_operational_intelligence import gpu_lease as G, runtime_v1 as R  # noqa: E402
from uri_operational_intelligence import brain_health as BH  # noqa: E402

PY = RT / ".venv/Scripts/python.exe"
CONTROL = pathlib.Path(CURRENT["client_root"]) / "control" / "oi"
STOP = OUT / "stop-session"
HOST_STOP = RT / "work/oi/state/runtime_v1.stop"


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    record = {"label": LABEL, "started_utc": now(), "runtime": str(RT), "port": CURRENT["port"],
              "receipt": {k: v for k, v in json.loads((RT / "OI_MATERIALIZATION_RECEIPT.json").read_text()).items()
                          if k in ("head", "candidate_head", "candidate_tree", "candidate_source")},
              "brain_config_sha256_before": R.config_digest(R.load_config()), "override": False}
    # Every file the materializer copied from the candidate is still byte-identical in the runtime AND in the
    # candidate checkout (the runtime runs exactly the candidate's Python code).
    import hashlib
    receipt = json.loads((RT / "OI_MATERIALIZATION_RECEIPT.json").read_text())
    src = pathlib.Path(receipt["candidate_source"])
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    bad = [rel for rel, d in receipt["oi_files_copied"].items()
           if sha(RT / rel) != d or not (src / rel).exists() or sha(src / rel) != d]
    record["runtime_verified"] = {"ok": not bad, "checked": len(receipt["oi_files_copied"]), "mismatched": bad[:20]}
    assert not bad, bad[:20]
    assert R._listener_pid(CURRENT["port"]) is None, "server port busy"
    man = json.loads(pathlib.Path(CURRENT["server_manifest"]).read_text())
    srv_log = (OUT / "integrated-server.log").open("w", encoding="utf-8")
    server = subprocess.Popen([str(PY), "-B", "-I", str(RT / "scripts/run_uri_integrated_server.py"),
                               "--manifest", CURRENT["server_manifest"]], cwd=man["state_root"],
                              stdin=subprocess.DEVNULL, stdout=srv_log, stderr=subprocess.STDOUT,
                              creationflags=subprocess.CREATE_NO_WINDOW)
    t0 = time.monotonic()
    while R._listener_pid(CURRENT["port"]) is None and server.poll() is None and time.monotonic() - t0 < 60:
        time.sleep(0.2)
    record.update(server_pid=server.pid, server_listening=R._listener_pid(CURRENT["port"]) is not None)
    print(json.dumps({"server_listening": record["server_listening"]}), flush=True)
    samples, done = [], threading.Event()
    host = None

    def sample():
        while not done.wait(2):
            try:
                rep, alive = BH.read_host_report(CONTROL)
                c = G.census()
                gpu = {str(x["pid"]): {"name": x.get("name"), "dedicated_mib": x["dedicated_mib"],
                                       "non_local_mib": x.get("non_local_mib")}
                       for x in c.get("processes", []) if x.get("name") in ("uri_ui.exe", "llama-server.exe", "dwm.exe")}
                workers = []
                for p in psutil.process_iter(["name", "cmdline"]):
                    try:
                        cl = " ".join(p.info["cmdline"] or [])
                        if "run_uri_integrated_worker.py" in cl and CURRENT["client_manifest"].lower() in cl.lower():
                            workers.append({"pid": p.pid, "create_time": round(p.create_time(), 3)})
                    except psutil.Error:
                        pass
                rep = rep or {}
                samples.append({"utc": now(), "t": round(time.time(), 3), "host_alive": alive,
                                "state": rep.get("state"), "detail": rep.get("detail"), "profile": rep.get("profile"),
                                "profile_switch": rep.get("profile_switch"), "server": rep.get("server"),
                                "calibration": {k: (rep.get("calibration") or {}).get(k)
                                                for k in ("decode_tps", "server_pid", "t", "reason")},
                                "residency": rep.get("residency"), "residency_alert": rep.get("residency_alert"),
                                "fit": ((rep.get("gpu") or {}).get("fit") or {}).get("verdict"),
                                "fit_margin_mib": ((rep.get("gpu") or {}).get("fit") or {}).get("margin_mib"),
                                "last_request": rep.get("last_request"), "gpu": gpu, "workers": workers,
                                "selection_file": (CONTROL / "brain_profile.json").read_text()
                                if (CONTROL / "brain_profile.json").exists() else None,
                                "lease": G.peek().get("holder", {}).get("expected_vram_mib")
                                if G.peek().get("state") == "HELD" else G.peek().get("state")})
                (OUT / "samples.json").write_text(json.dumps(samples, indent=1, default=str))
            except Exception as exc:          # sampling never stops the session
                samples.append({"utc": now(), "sample_error": repr(exc)})
    threading.Thread(target=sample, daemon=True).start()
    try:
        if "--no-brain" in sys.argv:
            (OUT / "brain-ready.json").write_text(json.dumps({"state": "NO_BRAIN_BY_DESIGN", "utc": now()}))
            end = time.monotonic() + MINUTES * 60
            while not ((OUT / "ui-finished.json").exists() or STOP.exists() or time.monotonic() > end):
                time.sleep(1)
            record["result"] = "COMPLETED_NO_BRAIN"
            return
        if NOT_BEFORE:
            hh, mm = (int(x) for x in NOT_BEFORE.split(":"))
            while datetime.datetime.now().time() < datetime.time(hh, mm):
                if STOP.exists():
                    record["result"] = "STOPPED_BEFORE_WINDOW"
                    return
                time.sleep(15)
            record["not_before"] = NOT_BEFORE
        deadline = time.monotonic() + MINUTES * 60
        while G.peek().get("state") != "FREE":
            if time.monotonic() > deadline or STOP.exists():
                record["result"] = "LEASE_NEVER_FREE"
                return
            time.sleep(10)
        record["lease_free_utc"] = now()
        HOST_STOP.unlink(missing_ok=True)
        cache = pathlib.Path(r"D:\uri-dev\uri-profiles-live\runtime-c\work\oi\state\artifact_hash_cache.json")
        (RT / "work/oi/state").mkdir(parents=True, exist_ok=True)
        if cache.exists() and not (RT / "work/oi/state/artifact_hash_cache.json").exists():
            (RT / "work/oi/state/artifact_hash_cache.json").write_bytes(cache.read_bytes())   # metadata-keyed
        host_log = (OUT / "brain-host.log").open("w", encoding="utf-8")
        INJ = sys.argv[sys.argv.index("--inject-fail-once") + 1] if "--inject-fail-once" in sys.argv else None
        entry = [str(HERE / "inject_host.py"), str(RT), INJ, str(OUT / "injection.json")] if INJ else \
            [str(RT / "scripts/ws_brain_host.py")]
        record["inject_fail_once"] = INJ
        # Owner instruction 2026-10-18 ("try with no mtp and 32k context size"): when the desktop leaves too little GPU
        # memory for Standard, the production host starts on P3 with its own --profile argument.
        PROF = ["--profile", sys.argv[sys.argv.index("--host-profile") + 1]] if "--host-profile" in sys.argv else []
        record["host_profile_arg"] = PROF
        host = subprocess.Popen([str(PY), "-B", "-I", *entry, "--report-dir",
                                 str(CONTROL), "--minutes", str(int(MINUTES)), *PROF], cwd=str(RT),
                                stdout=host_log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        record["host_pid"] = host.pid
        record["host_argv"] = ["ws_brain_host.py", "--report-dir", str(CONTROL), "--minutes", str(int(MINUTES)), *PROF]
        brain_stopped_by_driver = False
        while not ((OUT / "ui-finished.json").exists() or STOP.exists() or time.monotonic() > deadline
                   or (host.poll() is not None and not brain_stopped_by_driver)):
            if (OUT / "stop-brain.json").exists():
                # UI V2 driver journey J12 (failure and recovery): the Brain stops, the server stays for the UI.
                HOST_STOP.write_text("UI V2 driver J12")
                (OUT / "stop-brain.json").rename(OUT / "stop-brain.done.json")
                brain_stopped_by_driver = True
                record["brain_stopped_by_driver_utc"] = now()
            rep, _ = BH.read_host_report(CONTROL)
            st = (rep or {}).get("state")
            if st in ("READY", "DEGRADED", "FAILED") and not (OUT / "brain-ready.json").exists():
                (OUT / "brain-ready.json").write_text(json.dumps({"state": st, "utc": now(), "host": rep},
                                                                 indent=1, default=str))
            time.sleep(1)
        record["end_reason"] = ("ui-finished" if (OUT / "ui-finished.json").exists() else
                                "stop" if STOP.exists() else "host-exited" if host.poll() is not None else "timeout")
        record["result"] = "COMPLETED"
    finally:
        if host is not None and host.poll() is None:
            HOST_STOP.write_text("UI-TYPO session end")
            try:
                host.wait(timeout=120)
            except subprocess.TimeoutExpired:
                record["host_stop_timeout"] = True
        HOST_STOP.unlink(missing_ok=True)
        time.sleep(3)
        done.set()
        for p in sorted({c.pid for c in psutil.Process(server.pid).children(recursive=True)}) if server.poll() is None else []:
            try:
                psutil.Process(p).terminate()
            except psutil.Error:
                pass
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
        rep, _ = BH.read_host_report(CONTROL)
        record.update(finished_utc=now(), host_exit=host.returncode if host else None, host_final=rep,
                      lease_after=G.peek(), brain_config_sha256_after=R.config_digest(R.load_config()),
                      brain_listener_after=R._listener_pid(R.load_config()["runtime"]["port"]))
        (OUT / "session.json").write_text(json.dumps(record, indent=1, default=str))
        print(json.dumps({k: record.get(k) for k in ("result", "end_reason", "host_exit", "lease_after")},
                         default=str), flush=True)


if __name__ == "__main__":
    main()
