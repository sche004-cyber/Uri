r"""Integration live check: Brain vision availability per Quick Controls profile (Standard vs Long context).

    D:\uri-dev\uri-integ-rt\.venv\Scripts\python.exe -B -I vision_check.py <label>

For each profile (standard = frozen default start; long = --profile 65536,off,0) it starts the PRODUCTION Brain host
of the materialized integration runtime under the machine-wide GPU lease (no override), waits for READY, sends one
image request in the production Assist format (uri_assist.vision.build_request) to OUR Brain (server pid must match
the host report), records the answer or the refusal, then stops the host through its own stop file. A red square on
white is asked about; "red" in the answer = vision works. Never touches another session's Brain or lease.
"""
import datetime, io, json, pathlib, subprocess, sys, time, urllib.request, urllib.error

RT = pathlib.Path(r"D:\uri-dev\uri-integ-rt")
sys.path.insert(0, str(RT))
from PIL import Image  # noqa: E402
from uri_operational_intelligence import gpu_lease as G, runtime_v1 as R, brain_health as BH  # noqa: E402
from uri_assist.vision import build_request  # noqa: E402

LABEL = sys.argv[1]
OUT = pathlib.Path(__file__).resolve().parent / LABEL
OUT.mkdir(parents=True, exist_ok=True)
PY = RT / ".venv/Scripts/python.exe"
HOST_STOP = RT / "work/oi/state/runtime_v1.stop"
PROFILES = [("standard", None), ("long", "65536,off,0")]


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def png():
    im = Image.new("RGB", (512, 512), "white")
    im.paste((220, 20, 20), (128, 128, 384, 384))
    b = io.BytesIO(); im.save(b, "PNG")
    return b.getvalue()


def ask(port):
    body = build_request("What colour is the large square in the middle? Answer with one word.", png())
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read())
        text = data["choices"][0]["message"].get("content") or ""
        return {"ok": True, "http": 200, "answer": text.strip()[:300], "s": round(time.monotonic() - t, 2),
                "timings": data.get("timings")}
    except urllib.error.HTTPError as e:
        return {"ok": False, "http": e.code, "error": e.read().decode("utf-8", "replace")[:500],
                "s": round(time.monotonic() - t, 2)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": repr(e)[:500], "s": round(time.monotonic() - t, 2)}


def main():
    cfg = R.load_config()
    port = int(cfg["runtime"]["port"])
    record = {"label": LABEL, "started_utc": now(), "config_sha256_before": R.config_digest(cfg), "runs": []}
    for name, prof in PROFILES:
        run = {"profile": name, "argv_profile": prof}
        while G.peek().get("state") != "FREE":
            time.sleep(10)
        assert R._listener_pid(port) is None, "Brain port busy (foreign Brain)"
        ctl = OUT / f"control-{name}"
        ctl.mkdir(exist_ok=True)
        HOST_STOP.unlink(missing_ok=True)
        argv = [str(PY), "-B", "-I", str(RT / "scripts/ws_brain_host.py"), "--report-dir", str(ctl), "--minutes", "15"]
        if prof:
            argv += ["--profile", prof]
        log = (OUT / f"host-{name}.log").open("w", encoding="utf-8")
        host = subprocess.Popen(argv, cwd=str(RT), stdout=log, stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        run["host_pid"], run["start_utc"] = host.pid, now()
        end = time.monotonic() + 900
        rep = {}
        while time.monotonic() < end and host.poll() is None:
            rep, _ = BH.read_host_report(ctl)
            rep = rep or {}
            if rep.get("state") in ("READY", "DEGRADED", "FAILED"):
                break
            time.sleep(1)
        run["host_state"] = rep.get("state")
        run["host_profile"] = rep.get("profile")
        run["calibration"] = rep.get("calibration")
        run["fit"] = (rep.get("gpu") or {}).get("fit")
        srv = (rep.get("server") or {})
        run["server_pid_report"] = srv.get("pid")
        run["listener_pid"] = R._listener_pid(port)
        run["our_brain"] = run["listener_pid"] is not None and run["listener_pid"] == srv.get("pid")
        if rep.get("state") in ("READY", "DEGRADED") and run["our_brain"]:
            run["vision_request"] = ask(port)
            ans = (run["vision_request"].get("answer") or "").lower()
            run["vision_works"] = run["vision_request"].get("ok") and "red" in ans
        HOST_STOP.write_text("integration vision check")
        try:
            host.wait(timeout=180)
        except subprocess.TimeoutExpired:
            run["host_stop_timeout"] = True
        HOST_STOP.unlink(missing_ok=True)
        run["host_exit"] = host.returncode
        run["end_utc"] = now()
        record["runs"].append(run)
        (OUT / "vision_check.json").write_text(json.dumps(record, indent=1, default=str))
        time.sleep(5)
    record.update(finished_utc=now(), config_sha256_after=R.config_digest(R.load_config()), lease_after=G.peek(),
                  brain_listener_after=R._listener_pid(port))
    (OUT / "vision_check.json").write_text(json.dumps(record, indent=1, default=str))
    print(json.dumps([{k: r.get(k) for k in ("profile", "host_state", "our_brain", "vision_works")} for r in record["runs"]]))


if __name__ == "__main__":
    main()
