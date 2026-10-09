"""Voice process footprint (AC-4): working set and CPU time of uri_voice_service.py
idle (model loaded) and across one real-microphone utterance plus one spoken reply.
The talker is a Windows voice through the speakers. Usage: python -I voice_footprint.py <out.json>
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


def real_pid(launcher_pid):
    """The venv python.exe is a launcher that starts the base interpreter as its
    child; the service runs in that child."""
    ps = "(Get-CimInstance Win32_Process -Filter 'ParentProcessId=%d' | Where-Object Name -eq 'python.exe' | Select-Object -First 1).ProcessId" % launcher_pid
    for _ in range(50):
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout.strip()
        if out:
            return int(out)
        time.sleep(0.2)
    return launcher_pid


def proc_stats(pid):
    ps = ("$p=Get-Process -Id %d; $c=Get-CimInstance Win32_Process -Filter 'ParentProcessId=%d';"
          "$k=@($c | ForEach-Object { Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue });"
          "@{ws=$p.WorkingSet64; cpu=$p.TotalProcessorTime.TotalSeconds; threads=$p.Threads.Count;"
          "child_ws=($k | Measure-Object WorkingSet64 -Sum).Sum; child_cpu=($k | ForEach-Object {$_.TotalProcessorTime.TotalSeconds} | Measure-Object -Sum).Sum} | ConvertTo-Json -Compress") % (pid, pid)
    out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True).stdout
    d = json.loads(out)
    return {"ws_mb": round(d["ws"] / 2**20, 1), "cpu_s": round(d["cpu"], 2),
            "child_ws_mb": round((d["child_ws"] or 0) / 2**20, 1), "child_cpu_s": round(d["child_cpu"] or 0, 2)}


p = subprocess.Popen([str(PY), "-I", str(SVC)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
events = []
threading.Thread(target=lambda: [events.append(json.loads(l)) for l in p.stdout], daemon=True).start()


def send(**c):
    p.stdin.write((json.dumps(c) + "\n").encode())
    p.stdin.flush()


def wait(ev, i=None, t=60):
    end = time.time() + t
    while time.time() < end:
        for e in events:
            if e["ev"] == ev and (i is None or e.get("id") == i):
                return e
        time.sleep(0.05)
    raise SystemExit(f"no {ev}")


send(cmd="hello")
r = wait("ready")
SPID = real_pid(p.pid)
wait("model", None, 120)
time.sleep(2)
res = {"service_pid": SPID, "model": [e for e in events if e["ev"] == "model"][0], "idle_after_load": proc_stats(SPID)}
before = proc_stats(SPID)
send(cmd="listen_start", id="f1")
wait("listen.started", "f1")
time.sleep(0.4)
ps = "Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; $s.Speak($env:T); $s.Dispose()"
subprocess.run(["powershell", "-NoProfile", "-Command", ps],
               env={**os.environ, "T": "Please prepare a short note for the director about the training schedule next week."})
time.sleep(0.3)
during = proc_stats(SPID)
send(cmd="listen_stop", id="f1")
fin = wait("listen.final", "f1")
after_listen = proc_stats(SPID)
send(cmd="speak", id="u1", text="The note is ready on screen. Please review it before it goes to the director.", voice={}, final=True)
wait("speak.ended", "u1", 60)
after_speak = proc_stats(SPID)
send(cmd="shutdown")
p.wait(10)
res.update({
    "final": {k: fin[k] for k in ("text", "audio_ms", "transcribe_ms")},
    "while_capturing": during,
    "after_final": after_listen,
    "after_reply": after_speak,
    "cpu_s_for_utterance_incl_partials": round(after_listen["cpu_s"] - before["cpu_s"], 2),
    "cpu_s_for_reply_python": round(after_speak["cpu_s"] - after_listen["cpu_s"], 2),
    "cpu_s_for_reply_engine_bridge": round(after_speak["child_cpu_s"] - after_listen["child_cpu_s"], 2),
    "gpu": "none requested: device=cpu, compute_type=int8; the process is absent from per-process GPU memory samples (threshold 32 MiB)",
})
Path(sys.argv[1]).write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps(res, indent=1))
