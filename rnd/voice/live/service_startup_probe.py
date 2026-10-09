"""Voice process start-up and idle cost (report section 4).

Five cold starts: time from process start to the `model` event (ready). Then, in
one instance: CPU seconds used by the service interpreter over 10 s idle, and over
10 s with the microphone open while nobody speaks.
Usage: python -I service_startup_probe.py <out.json>
"""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PY = Path(os.environ["LOCALAPPDATA"]) / "URI" / "voice" / "venv" / "Scripts" / "python.exe"
SVC = ROOT / "uri_ui" / "assets" / "voice" / "uri_voice_service.py"


def start():
    p = subprocess.Popen([str(PY), "-I", str(SVC)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    ev = []
    t0 = time.perf_counter()
    threading.Thread(target=lambda: [ev.append((round(time.perf_counter() - t0, 3), json.loads(l))) for l in p.stdout],
                     daemon=True).start()
    return p, ev


def send(p, **c):
    p.stdin.write((json.dumps(c) + "\n").encode())
    p.stdin.flush()


def child_pid(pid):
    ps = "(Get-CimInstance Win32_Process -Filter 'ParentProcessId=%d' | Where-Object Name -eq 'python.exe').ProcessId" % pid
    for _ in range(50):
        o = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.strip()
        if o:
            return int(o.split()[0])
        time.sleep(0.2)
    return pid


def cpu(pid):
    o = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-Process -Id %d).TotalProcessorTime.TotalSeconds" % pid],
                       capture_output=True, text=True).stdout
    return float(o.strip() or 0)


res = {"cold_starts": []}
for i in range(5):
    p, ev = start()
    send(p, cmd="hello")
    end = time.time() + 60
    while time.time() < end and not any(e["ev"] == "model" for _, e in ev):
        time.sleep(0.05)
    m = next(((t, e) for t, e in ev if e["ev"] == "model"), None)
    res["cold_starts"].append({"seconds_to_model_event": m[0] if m else None, "model": m[1] if m else "NO MODEL EVENT IN 60 s"})
    if i < 4:
        send(p, cmd="shutdown")
        p.wait(10)
kid = child_pid(p.pid)
a = cpu(kid)
time.sleep(10)
b = cpu(kid)
send(p, cmd="listen_start", id="x")
time.sleep(0.5)
c = cpu(kid)
time.sleep(10)
d = cpu(kid)
send(p, cmd="listen_cancel", id="x")
send(p, cmd="shutdown")
p.wait(10)
res["cpu_seconds_idle_10s"] = round(b - a, 3)
res["cpu_seconds_open_microphone_no_speech_10s"] = round(d - c, 3)
res["note"] = "open-microphone figure depends on room noise; the speakers were silent during this run"
Path(sys.argv[1]).write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps(res, indent=1))
