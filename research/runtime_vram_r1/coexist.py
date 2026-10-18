"""Coexistence of one Brain profile with the URI UI window and an ordinary browser workload (no stress test).

Phases, each with the Brain's residency (dedicated / non-local), the census of other GPU users and a decode probe
(URI JSON task + prose):
  A  Brain loaded, desktop as found;
  B  + URI UI window (canonical 25048709 release build of uri_ui, no backend manifest: it shows its start screen; this
     is a GPU-memory consumer proxy, NOT a real-app qualification). APPDATA/LOCALAPPDATA/TEMP are redirected to a lab
     folder and the owner's real uri_ui preference file is hashed before and after (restored byte-exact if changed);
  C  + isolated Chrome (own --user-data-dir in the lab folder; the owner's Chrome is never touched), 6 public tabs;
  D  both closed: does the Brain recover, or is a demotion sticky for the process lifetime?
Only processes this script started are closed (by pid / by the lab profile dir).

    python -I coexist.py <name> --ctx 65536 [--no-mtp] [--vision off|gpu]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "model_lab"))
import vlab  # noqa: E402
import speed  # noqa: E402
import run_probe as RP  # noqa: E402

UI_EXE = HERE.parents[1] / "uri_ui" / "build" / "windows" / "x64" / "runner" / "Release" / "uri_ui.exe"
LAB = Path(r"D:\uri-dev\uri-vram-r1-coexist")
OWNER_PREFS = Path(os.environ["APPDATA"]) / "com.example" / "uri_ui" / "shared_preferences.json"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
TABS = ["https://www.youtube.com/watch?v=aqz-KE-bpKQ", "https://webglsamples.org/aquarium/aquarium.html",
        "https://www.google.com/maps/@27.3314,88.6138,4000m/data=!3m1!1e3", "https://github.com/ggml-org/llama.cpp",
        "https://en.wikipedia.org/wiki/Sikkim", "https://docs.python.org/3/library/asyncio.html"]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None


def probe(srv, label):
    c = vlab.census_brief()
    j = speed.stream_chat(srv.url, [{"role": "system", "content": RP.URI_SYSTEM},
                                    {"role": "user", "content": RP.URI_TASKS[1] + RP.URI_FORMAT}], max_tokens=400)
    p = speed.stream_chat(srv.url, [{"role": "user", "content": speed.FIXED_PROMPT}], max_tokens=300)
    out = {"phase": label, "t": round(time.time(), 1), "server": vlab.process_gpu_mib(srv.proc.pid),
           "others": [(x["name"], x["dedicated_mib"]) for x in c.get("processes", []) if x["pid"] != srv.proc.pid][:8],
           "adapter_mib": c.get("adapter_dedicated_mib"), "uri_json_tps": j.get("decode_tps"),
           "uri_json_total_s": j.get("total_s"), "prose_tps": p.get("decode_tps")}
    print(json.dumps(out), flush=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--ctx", type=int, default=65536)
    ap.add_argument("--no-mtp", action="store_true")
    ap.add_argument("--vision", default="off")
    ap.add_argument("--settle", type=float, default=30.0)
    a = ap.parse_args()
    prof = vlab.Profile(a.name, ctx=a.ctx, mtp=not a.no_mtp, vision=a.vision)
    run_dir = vlab.EVIDENCE / "coexist" / f"{time.strftime('%Y%m%d-%H%M%S')}_{a.name}"
    srv = vlab.Server(prof, run_dir, max_hold_s=900)
    rec = srv.record
    prefs_before = OWNER_PREFS.read_bytes() if OWNER_PREFS.exists() else None
    rec["owner_prefs_sha256_before"] = sha(OWNER_PREFS)
    ui = chrome = None
    chrome_dir = LAB / "chrome-profile"
    try:
        srv.start()
        rec["A"] = probe(srv, "A_desktop")
        local = LAB / "ui-local"
        for d in (local / "roaming", local / "temp"):
            d.mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, LOCALAPPDATA=str(local), APPDATA=str(local / "roaming"), TEMP=str(local / "temp"),
                   TMP=str(local / "temp"), URI_UI_VISUAL="v2")
        env.pop("URI_CLIENT_MANIFEST", None)
        ui = subprocess.Popen([str(UI_EXE)], env=env, cwd=str(UI_EXE.parent))
        time.sleep(a.settle)
        rec["ui_gpu"] = vlab.process_gpu_mib(ui.pid)
        rec["B"] = probe(srv, "B_plus_uri_ui")
        if chrome_dir.exists():
            shutil.rmtree(chrome_dir, ignore_errors=True)
        chrome = subprocess.Popen([CHROME, f"--user-data-dir={chrome_dir}", "--no-first-run", "--no-default-browser-check",
                                   "--autoplay-policy=no-user-gesture-required", "--new-window"] + TABS)
        time.sleep(45)
        rec["C"] = probe(srv, "C_plus_chrome")
        rec["classification"] = "COMPLETED_WITH_RESULT"
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
        rec["classification"] = "FAILED"
    finally:
        if chrome is not None:
            subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | Where-Object { $_.CommandLine -like "
                            f"'*{chrome_dir}*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force }}"],
                           capture_output=True, timeout=60)
        if ui is not None and ui.poll() is None:
            ui.terminate()
            try:
                ui.wait(20)
            except subprocess.TimeoutExpired:
                ui.kill()
        time.sleep(15)
        try:
            if srv.proc and srv.proc.poll() is None and rec.get("classification") == "COMPLETED_WITH_RESULT":
                rec["D"] = probe(srv, "D_both_closed")
        except Exception as exc:
            rec["error_d"] = f"{type(exc).__name__}: {exc}"
        srv.stop()
        rec["owner_prefs_sha256_after"] = sha(OWNER_PREFS)
        if prefs_before is not None and OWNER_PREFS.read_bytes() != prefs_before:
            OWNER_PREFS.write_bytes(prefs_before)
            rec["owner_prefs_restored"] = True
        vlab.save(run_dir, "coexist", rec)
        print("EVIDENCE", run_dir, rec.get("classification"), flush=True)


if __name__ == "__main__":
    main()
