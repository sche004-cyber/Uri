"""Conversation continuity through live Brain profile switches (RUNTIME-PROFILES-INTEG LQ-4; repair CONTEXT-1).

Everything is the product path except the user: the integrated server, the production Brain host
(`ws_brain_host.py --profile`), and the integrated worker spawned exactly as the app spawns it (manifest
interpreter, `-B -I <source_root>/scripts/run_uri_integrated_worker.py --manifest <client manifest>`, cwd = client
root), driven over its frame protocol with the same commands the app sends (`preflight`, `brain_status`,
`brain_health`, `oi_turn`). No UI is involved: this verifies the worker/Brain side of continuity, which the UI V2
driver's R-conversation check does not cover (reviewer R1-01).

Sequence: P2 (64K main only) -> tell a fact -> recall it -> switch the host to P3 (32K + GPU vision) with the worker
kept running -> recall it -> switch back to P2 -> recall it. Per switch: stop -> VRAM release time -> start -> READY
seen by the worker -> the worker's health names the new profile. Also samples system commit (CRASH-1 research E0).

    <runtime-c>\\.venv\\Scripts\\python.exe -B -I tools\\switch_live.py <label>
"""
from __future__ import annotations

import json
import pathlib
import struct
import subprocess
import sys
import threading
import time
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[1]
RT = ROOT / "runtime-e"
SRC = pathlib.Path(r"D:\uri-dev\uri-runtime-profiles-integ")
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tools"))
import psutil  # noqa: E402
from uri_operational_intelligence import brain_health as BH, gpu_lease as G, runtime_v1 as R  # noqa: E402
from uri_operational_intelligence import runtime_profile_selection as PS  # noqa: E402

LABEL = sys.argv[1]
OUT = ROOT / "evidence" / "switch_live" / LABEL
OUT.mkdir(parents=True, exist_ok=True)
INST = json.loads((ROOT / "evidence" / "provision-e.json").read_text())
CLIENT = pathlib.Path(INST["client_root"])
CONTROL = CLIENT / "control" / "oi"
HOST_STATE = ROOT / "fixtures" / f"brain-state-{LABEL}"
SESSION = str(uuid.uuid4())
FACT = "4817"          # the recall turn asks for the number given at the start, which needs the earlier turn in context
SECRET = "4817"
P2, P3 = (65536, "off", False), (32768, "gpu", False)


def now():
    return round(time.time(), 2)


def commit():
    import ctypes

    class MEM(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MEM()
    m.dwLength = ctypes.sizeof(MEM)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return {"avail_phys_mib": m.ullAvailPhys >> 20, "commit_limit_mib": m.ullTotalPageFile >> 20,
            "commit_free_mib": m.ullAvailPageFile >> 20}


class Worker:
    def __init__(self, manifest_path):
        m = json.loads(pathlib.Path(manifest_path).read_text())
        entry = str(pathlib.Path(m["source_root"]) / "scripts" / "run_uri_integrated_worker.py")
        self.p = subprocess.Popen([m["interpreter"], "-B", "-I", entry, "--manifest", str(manifest_path)],
                                  cwd=m["client_root"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=open(OUT / "worker.err", "wb"))
        self.events, self.replies = [], []
        self.cv = threading.Condition()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        while True:
            h = self.p.stdout.read(4)
            if len(h) < 4:
                break
            data = self.p.stdout.read(struct.unpack(">I", h)[0])
            frame = json.loads(data)
            with self.cv:
                (self.events if "event" in frame else self.replies).append(frame)
                self.cv.notify_all()

    def call(self, command, timeout=60):
        n = len(self.replies)
        data = json.dumps(command, sort_keys=True, separators=(",", ":")).encode()
        self.p.stdin.write(struct.pack(">I", len(data)) + data)
        self.p.stdin.flush()
        with self.cv:
            self.cv.wait_for(lambda: len(self.replies) > n, timeout)
            return self.replies[n] if len(self.replies) > n else {"result": "TIMEOUT"}

    def turn(self, text, timeout=180):
        r = self.call({"command": "oi_turn", "session_id": SESSION, "text": text, "depth": "fast"})
        tid = (r.get("value") or {}).get("turn_id")
        t0 = time.monotonic()
        with self.cv:
            self.cv.wait_for(lambda: any(e["event"].get("turn_id") == tid and e["event"].get("type") in
                                         ("answer.done", "turn.finished", "turn.failed", "turn.done", "core.result")
                                         for e in self.events), timeout)
        for _ in range(60):                         # the worker is idle again before the next turn is sent
            st = (self.call({"command": "oi_turn_status"}).get("value") or {})
            if not st.get("busy"):
                break
            time.sleep(0.5)
        evs = [e["event"] for e in self.events if e["event"].get("turn_id") == tid]
        text_out = "".join((e.get("data") or {}).get("text", "") for e in evs if e.get("type") == "answer.delta")
        routed = [(e.get("data") or {}).get("route") for e in evs if e.get("type") == "turn.routed"]
        core = [(e.get("data") or {}) for e in evs if e.get("type") == "core.result"]
        (OUT / f"turn-{len(list(OUT.glob('turn-*.json')))}.json").write_text(json.dumps({"text": text, "events": evs}, indent=1, default=str))
        return {"reply": r.get("result"), "error": r.get("error") or r.get("code"), "turn_id": tid,
                "seconds": round(time.monotonic() - t0, 2), "answer": text_out[:500], "route": routed,
                "core": json.dumps(core, default=str)[:300], "types": sorted({e.get("type") for e in evs})}


def wait_ready(w, want_id, timeout=600):
    t0 = time.monotonic()
    last = None
    while time.monotonic() - t0 < timeout:
        st = (w.call({"command": "brain_status"}).get("value") or {})
        last = st.get("state")
        if last == "READY":
            hv = (w.call({"command": "brain_health"}).get("value") or {})
            prof = ((hv.get("backend") or {}).get("profile") or {}).get("id")
            return {"state": last, "seconds": round(time.monotonic() - t0, 1), "worker_profile": prof,
                    "profile_ok": prof == want_id, "detail": st.get("detail")}
        time.sleep(2)
    return {"state": last, "seconds": None, "profile_ok": False}


def start_host(prof):
    PS.write(CLIENT, *prof)                          # what the worker will verify against
    (HOST_STATE / "runtime_v1.stop").unlink(missing_ok=True)
    HOST_STATE.mkdir(parents=True, exist_ok=True)
    arg = f"{prof[0]},{prof[1]},{1 if prof[2] else 0}"
    return subprocess.Popen([str(RT / ".venv/Scripts/python.exe"), "-B", "-I", str(RT / "scripts/ws_brain_host.py"),
                             "--report-dir", str(CONTROL), "--minutes", "40", "--profile", arg],
                            cwd=str(RT), stdout=open(OUT / f"host-{arg}.log", "wb"), stderr=subprocess.STDOUT)


def stop_host(host):
    t0 = time.monotonic()
    # the host reads its stop file from its own state dir (DEFAULT_STATE of the runtime it runs from)
    stop = RT / "work" / "oi" / "state" / "runtime_v1.stop"
    stop.parent.mkdir(parents=True, exist_ok=True)
    stop.write_text("switch")
    host.wait(120)
    stopped = round(time.monotonic() - t0, 1)
    t1 = time.monotonic()
    while time.monotonic() - t1 < 90:
        big = [p for p in G.census().get("processes", []) if (p.get("dedicated_mib") or 0) > 2048]
        if not big:
            break
        time.sleep(1)
    stop.unlink(missing_ok=True)
    return {"stop_s": stopped, "vram_release_s": round(time.monotonic() - t1, 1)}


def main():
    import binding
    rec = {"label": LABEL, "session_id": SESSION, "steps": [], "commit": [], "classification": "STARTED",
           "binding": binding.require(RT)}
    man = json.loads(pathlib.Path(INST["server_manifest"]).read_text())
    srv = subprocess.Popen([str(RT / ".venv/Scripts/python.exe"), "-B", "-I", str(RT / "scripts/run_uri_integrated_server.py"),
                            "--manifest", INST["server_manifest"]], cwd=man["state_root"], stdin=subprocess.DEVNULL,
                           stdout=open(OUT / "server.log", "wb"), stderr=subprocess.STDOUT)
    host = w = None
    try:
        t0 = time.monotonic()
        while R._listener_pid(INST["port"]) is None and time.monotonic() - t0 < 60:
            time.sleep(0.2)
        dry = "--dry" in sys.argv
        if not dry:
            host = start_host(P2)
        w = Worker(INST["client_manifest"])
        pre = w.call({"command": "preflight"}, timeout=120)
        rec["preflight_ok"] = (pre.get("value") or {}).get("worker_profile")
        if dry:
            rec["dry_brain_status"] = w.call({"command": "brain_status"}).get("value")
            rec["dry_brain_health_profile"] = ((w.call({"command": "brain_health"}).get("value") or {}).get("backend") or {}).get("profile")
            rec["classification"] = "DRY_RUN"
            return
        rec["steps"].append({"step": "ready-P2", **wait_ready(w, "c64k-visoff-mtpoff")})
        rec["commit"].append({"t": now(), **commit()})
        rec["steps"].append({"step": "tell", **w.turn(f"Quick arithmetic game. The secret number is {SECRET}. Reply with just OK.")})
        rec["steps"].append({"step": "recall-P2", **w.turn("What was the secret number I gave you at the start of this conversation? Reply with the number only.")})
        for label, prof, pid in (("P3", P3, "c32k-visgpu-mtpoff"), ("P2-again", P2, "c64k-visoff-mtpoff")):
            rel = stop_host(host)
            host = start_host(prof)
            ready = wait_ready(w, pid)
            rec["steps"].append({"step": f"switch-to-{label}", **rel, **ready})
            rec["commit"].append({"t": now(), **commit()})
            rec["steps"].append({"step": f"recall-{label}", **w.turn("Once more: what was the secret number I gave you at the start of this conversation? Reply with the number only.")})
        recalls = [s for s in rec["steps"] if s["step"].startswith("recall")]
        rec["all_recalled"] = all(FACT in (s.get("answer") or "") for s in recalls)
        rec["all_answer_route"] = all(s.get("route") == ["answer"] for s in recalls)
        rec["all_switches_ready_on_new_profile"] = all(s.get("profile_ok") for s in rec["steps"]
                                                       if s["step"].startswith(("switch", "ready")))
        rec["worker_pid_constant"] = w.p.poll() is None
        rec["classification"] = "COMPLETED_WITH_RESULT"
    except Exception as exc:
        rec["classification"], rec["error"] = "FAILED", f"{type(exc).__name__}: {exc}"
    finally:
        try:
            if w is not None and w.p.poll() is None:
                w.call({"command": "close"}, timeout=20)
                w.p.stdin.close()
                w.p.wait(30)
        except Exception:
            if w is not None and w.p.poll() is None:
                w.p.kill()
        if host is not None and host.poll() is None:
            stop_host(host)
        if srv.poll() is None:
            srv.terminate()
            srv.wait(20)
        rec["lease_after"] = G.peek().get("state")
        rec["worker_instance"] = json.loads((CLIENT / "control" / "worker-instance.json").read_text()) \
            if (CLIENT / "control" / "worker-instance.json").exists() else None
        (OUT / "switch_live.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
        print(json.dumps({k: rec.get(k) for k in ("classification", "error", "all_recalled", "all_answer_route",
                                                  "all_switches_ready_on_new_profile", "worker_pid_constant", "lease_after")}))
        for s in rec["steps"]:
            print(json.dumps({k: s.get(k) for k in ("step", "state", "seconds", "worker_profile", "stop_s",
                                                    "vram_release_s", "answer", "route", "core", "error")})[:400])


if __name__ == "__main__":
    main()
