"""Sustained operation of one Brain profile next to an ordinary desktop workload (RUNTIME-PROFILES-INTEG LQ-3).

Real parts: the production Brain host (`ws_brain_host.py --profile`, port 18470, lease, calibration, residency alert)
and the URI app window (canonical release build of uri_ui from the candidate, no backend manifest: its start screen;
a GPU-memory consumer next to the Brain, NOT a journey run - the journeys are qualified by the UI V2 driver runs).
An isolated Chrome (own profile dir in the lab folder; the owner's Chrome is never touched) with the 6 tabs of the
research coexistence test is open for the middle third of the soak.
Every 30 s: one URI-style decision turn (fixed system prompt + rotating task, JSON answer) straight to the Brain
endpoint, timings from llama-server; every sample: Brain dedicated / non-local GPU memory, UI and Chrome GPU memory,
host report state (READY / DEGRADED / residency_alert). Ordinary load only; no stress.

    <runtime>\\.venv\\Scripts\\python.exe -B -I tools\\soak.py <label> --profile 65536,gpu,0 [--minutes 60]
"""
from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = pathlib.Path(r"D:\uri-dev\uri-runtime-profiles-integ")
LAB = pathlib.Path(r"D:\uri-dev\uri-runtime-vram-r1\research\runtime_vram_r1")
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(LAB))
import httpx  # noqa: E402
from uri_operational_intelligence import brain_health as BH, gpu_lease as G  # noqa: E402
import run_probe as RP  # noqa: E402

LABEL = sys.argv[1]
PROFILE = sys.argv[sys.argv.index("--profile") + 1]
MINUTES = float(sys.argv[sys.argv.index("--minutes") + 1]) if "--minutes" in sys.argv else 60.0
OUT = ROOT / "evidence" / "soak" / LABEL
REP = OUT / "control"
REP.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:18470"
UI_EXE = SRC / "uri_ui" / "build" / "windows" / "x64" / "runner" / "Release" / "uri_ui.exe"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_DIR = ROOT / "lab" / "chrome-profile"
TABS = ["https://www.youtube.com/watch?v=aqz-KE-bpKQ", "https://webglsamples.org/aquarium/aquarium.html",
        "https://www.google.com/maps/@27.3314,88.6138,4000m/data=!3m1!1e3", "https://github.com/ggml-org/llama.cpp",
        "https://en.wikipedia.org/wiki/Sikkim", "https://docs.python.org/3/library/asyncio.html"]
OWNER_PREFS = pathlib.Path(os.environ["APPDATA"]) / "com.example" / "uri_ui" / "shared_preferences.json"


def report():
    try:
        return json.loads((REP / BH.REPORT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def turn(i):
    msgs = [{"role": "system", "content": RP.URI_SYSTEM},
            {"role": "user", "content": RP.URI_TASKS[i % len(RP.URI_TASKS)] + RP.URI_FORMAT}]
    t = time.monotonic()
    r = httpx.post(BASE + "/v1/chat/completions", json={"model": "local", "messages": msgs, "max_tokens": 300,
                                                       "temperature": 0.0, "chat_template_kwargs": {"enable_thinking": False}},
                   timeout=180)
    j = r.json()
    tim = j.get("timings") or {}
    text = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    try:
        json.loads(text[text.index("{"):text.rindex("}") + 1])
        valid = True
    except ValueError:
        valid = False
    return {"status": r.status_code, "wall_s": round(time.monotonic() - t, 2), "decode_tps": tim.get("predicted_per_second"),
            "prompt_tps": tim.get("prompt_per_second"), "cache_n": tim.get("cache_n"), "valid_json": valid}


def gpu(pids):
    c = G.census()
    out = {"adapter_mib": c.get("adapter_dedicated_mib")}
    for p in c.get("processes", []):
        n = (p.get("name") or "").lower()
        if n in ("llama-server.exe", "uri_ui.exe", "dwm.exe") or p["pid"] in pids:
            key = n if n != "chrome.exe" else "chrome"
            prev = out.get(key)
            if key == "chrome" and prev:
                out[key] = {"dedicated_mib": round(prev["dedicated_mib"] + p["dedicated_mib"], 1)}
            else:
                out[key] = {"dedicated_mib": p["dedicated_mib"], "non_local_mib": p.get("non_local_mib")}
    return out


def chrome_pids():
    import psutil
    pids = set()
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            if (p.info["name"] or "").lower() == "chrome.exe" and str(CHROME_DIR) in " ".join(p.info["cmdline"] or []):
                pids.add(p.pid)
        except Exception:
            pass
    return pids


def close_chrome():
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | Where-Object { $_.CommandLine -like "
                    f"'*{CHROME_DIR}*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"],
                   capture_output=True, timeout=60)


def main():
    rec = {"label": LABEL, "profile_arg": PROFILE, "minutes": MINUTES, "classification": "STARTED", "samples": [],
           "events": []}
    prefs_before = OWNER_PREFS.read_bytes() if OWNER_PREFS.exists() else None
    stop = SRC / "work" / "oi" / "state" / "runtime_v1.stop"
    stop.unlink(missing_ok=True)
    host = subprocess.Popen([sys.executable, "-B", "-I", str(SRC / "scripts" / "ws_brain_host.py"), "--report-dir",
                             str(REP), "--minutes", str(MINUTES + 15), "--profile", PROFILE], cwd=str(SRC),
                            stdout=open(OUT / "host.log", "wb"), stderr=subprocess.STDOUT)
    ui = chrome = None
    try:
        t0 = time.monotonic()
        while time.monotonic() - t0 < 900 and report().get("state") not in ("READY", "DEGRADED", "FAILED"):
            time.sleep(1)
        rep = report()
        rec["host_ready"] = {k: rep.get(k) for k in ("state", "detail", "profile", "calibration")}
        if rep.get("state") != "READY":
            rec["classification"], rec["error"] = "FAILED", "BRAIN_NOT_READY:%s" % rep.get("state")
            return
        local = ROOT / "lab" / "ui-local"
        for d in (local / "roaming", local / "temp"):
            d.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, LOCALAPPDATA=str(local), APPDATA=str(local / "roaming"), TEMP=str(local / "temp"),
                   TMP=str(local / "temp"), URI_UI_VISUAL="v2")
        env.pop("URI_CLIENT_MANIFEST", None)
        ui = subprocess.Popen([str(UI_EXE)], env=env, cwd=str(UI_EXE.parent))
        rec["events"].append({"t": 0, "event": "ui_open"})
        start = time.monotonic()
        third = MINUTES * 60 / 3
        i = 0
        while time.monotonic() - start < MINUTES * 60:
            el = time.monotonic() - start
            if chrome is None and el >= third and el < 2 * third:
                if CHROME_DIR.exists():
                    shutil.rmtree(CHROME_DIR, ignore_errors=True)
                chrome = subprocess.Popen([CHROME, f"--user-data-dir={CHROME_DIR}", "--no-first-run",
                                           "--no-default-browser-check", "--autoplay-policy=no-user-gesture-required",
                                           "--new-window"] + TABS)
                rec["events"].append({"t": round(el), "event": "chrome_open"})
            if chrome is not None and el >= 2 * third and not any(e["event"] == "chrome_closed" for e in rec["events"]):
                close_chrome()
                rec["events"].append({"t": round(el), "event": "chrome_closed"})
            if host.poll() is not None:
                rec["events"].append({"t": round(el), "event": "host_exited", "code": host.returncode})
                break
            row = {"t": round(el), "host_state": report().get("state"), "residency_alert": report().get("residency_alert")}
            try:
                row["turn"] = turn(i)
            except Exception as exc:
                row["turn"] = {"error": f"{type(exc).__name__}: {exc}"}
            row["gpu"] = gpu(chrome_pids())
            rec["samples"].append(row)
            (OUT / "soak.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
            i += 1
            time.sleep(max(0.0, 30 - (time.monotonic() - start - el)))
        turns = [s["turn"] for s in rec["samples"] if "decode_tps" in s.get("turn", {})]
        rec["summary"] = {"turns": len(rec["samples"]), "ok_turns": sum(1 for s in rec["samples"] if s.get("turn", {}).get("status") == 200),
                          "valid_json": sum(1 for t in turns if t.get("valid_json")),
                          "decode_min": min((t["decode_tps"] for t in turns), default=None),
                          "decode_median": sorted(t["decode_tps"] for t in turns)[len(turns) // 2] if turns else None,
                          "max_brain_non_local": max((s["gpu"].get("llama-server.exe", {}).get("non_local_mib") or 0
                                                      for s in rec["samples"]), default=None),
                          "min_brain_dedicated": min((s["gpu"].get("llama-server.exe", {}).get("dedicated_mib") or 0
                                                      for s in rec["samples"]), default=None),
                          "host_exited": any(e["event"] == "host_exited" for e in rec["events"])}
        rec["classification"] = "COMPLETED_WITH_RESULT"
    except Exception as exc:
        rec["classification"], rec["error"] = "FAILED", f"{type(exc).__name__}: {exc}"
    finally:
        if chrome is not None:
            close_chrome()
        if ui is not None and ui.poll() is None:
            ui.terminate()
        stop.parent.mkdir(parents=True, exist_ok=True)
        stop.write_text("soak done")
        try:
            host.wait(120)
        except subprocess.TimeoutExpired:
            host.terminate()
        rec["host_exit"] = host.returncode
        rec["host_final"] = report()
        rec["lease_after"] = G.peek().get("state")
        if prefs_before is not None and OWNER_PREFS.exists() and OWNER_PREFS.read_bytes() != prefs_before:
            OWNER_PREFS.write_bytes(prefs_before)
            rec["owner_prefs_restored"] = True
        (OUT / "soak.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
        print(json.dumps({k: rec.get(k) for k in ("label", "classification", "error", "summary", "host_exit", "lease_after")},
                         default=str))


if __name__ == "__main__":
    main()
