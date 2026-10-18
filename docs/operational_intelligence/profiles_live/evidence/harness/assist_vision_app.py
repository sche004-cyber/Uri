"""URI Assist on-demand vision through the APPLICATION PATH on a Brain resource profile (Assist owner checklist item 7).

What runs for real: the production Brain host (`scripts/ws_brain_host.py --profile ...`, port 18470, GPU lease,
calibration), the production `uri_assist.bridge.AssistCommands` (grant -> OBSERVE -> screenshot -> VisionGate
masking/downscale/freshness -> loopback Brain request -> answer), and the production loopback Brain client.
What is a test stand-in (and why): the capture adapter is the existing test `FakeAdapter`
(tests/assist/test_a0_access_perception.py), because no real Assist capture adapter exists yet (browser channel,
UI Automation and screen capture are owner-gated, Assist checklist items 8-10). `vision_qualified=True` is set only
in this harness; the product worker keeps it False. This is NOT a real-UI Assist qualification.

Measures per profile: answer correctness on a synthetic settings screenshot (error code 401 + the two toggles that
are on), end-to-end ask latency, plain decode before/after (host calibration-style probe), Brain residency.

    <runtime>\\.venv\\Scripts\\python.exe -B -I tools\\assist_vision_app.py <label> --profile 65536,gpu,0 [--reps 3]
"""
from __future__ import annotations

import io
import json
import pathlib
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = pathlib.Path(r"D:\uri-dev\uri-runtime-profiles-integ")
RT = ROOT / "runtime-e"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(SRC / "model_lab"))
import httpx  # noqa: E402
from uri_operational_intelligence import brain_health as BH, gpu_lease as G  # noqa: E402
from uri_assist import bridge as B, access as AC  # noqa: E402
from uri_web.local_brain import loopback_client  # noqa: E402
from tests.assist.test_a0_access_perception import FakeAdapter, dom_snapshot  # noqa: E402
from lab import vision as V  # noqa: E402

LABEL = sys.argv[1]
PROFILE = sys.argv[sys.argv.index("--profile") + 1]
REPS = int(sys.argv[sys.argv.index("--reps") + 1]) if "--reps" in sys.argv else 3
OUT = ROOT / "evidence" / "assist" / LABEL
REP = OUT / "control"
REP.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:18470"
QUESTION = "What error message is shown on this screen, and which toggles are switched on? Answer in one sentence."


def read_report():
    try:
        return json.loads((REP / BH.REPORT_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def decode_probe():
    r = httpx.post(BASE + "/completion", json={"prompt": "Here is a numbered list of forty everyday household objects, one per line:\n1.",
                                               "n_predict": 160, "temperature": 0, "cache_prompt": False,
                                               "ignore_eos": True}, timeout=120)
    return round(float((r.json().get("timings") or {}).get("predicted_per_second") or 0), 1)


def png():
    buf = io.BytesIO()
    V.img_ui().save(buf, format="PNG")
    return buf.getvalue()


def main():
    rec = {"label": LABEL, "profile_arg": PROFILE, "started": time.time(), "classification": "STARTED",
           "stand_ins": ["capture adapter = tests.assist FakeAdapter (no real adapter exists)",
                         "vision_qualified=True in this harness only"]}
    import binding
    rec["binding"] = binding.require(RT)
    stop = RT / "work" / "oi" / "state" / "runtime_v1.stop"
    stop.unlink(missing_ok=True)
    log = open(OUT / "host.log", "wb")
    host = subprocess.Popen([str(RT / ".venv/Scripts/python.exe"), "-B", "-I", str(RT / "scripts" / "ws_brain_host.py"), "--report-dir",
                             str(REP), "--minutes", "20", "--profile", PROFILE], cwd=str(RT), stdout=log,
                            stderr=subprocess.STDOUT)
    try:
        t0 = time.monotonic()
        while time.monotonic() - t0 < 900:
            rep = read_report()
            if rep.get("state") in ("READY", "DEGRADED", "FAILED"):
                break
            time.sleep(1)
        rec["host_ready"] = {k: rep.get(k) for k in ("state", "detail", "profile", "calibration", "residency")}
        rec["host_ready_s"] = round(time.monotonic() - t0, 1)
        if rep.get("state") != "READY":
            rec["classification"] = "FAILED"
            rec["error"] = "BRAIN_NOT_READY:%s" % rep.get("state")
            return rec
        rec["decode_before"] = decode_probe()
        snap = dom_snapshot(url="https://settings.example/sync", title="URI Settings", text="", headings=["URI Settings"],
                            fields=[])
        ad = FakeAdapter("browser_tab", snap, targets=[{"target_id": "t", "label": "URI Settings"}], png=png())
        br = B.AssistCommands(adapters={AC.ScopeKind.BROWSER_TAB: ad}, brain_client=loopback_client(BASE),
                              brain_idle=lambda: True, vision_qualified=True)
        br.handle("assist_grant", {"command": "assist_grant", "kind": "browser_tab", "target_id": "t",
                                   "permissions": ["observe"], "confirm_screen": False})
        asks = []
        for i in range(REPS):
            if i:
                time.sleep(5.2)                         # VisionGate debounce (5 s)
            t = time.monotonic()
            started = br.handle("assist_ask", {"command": "assist_ask", "question": QUESTION, "use_screenshot": True})
            br.wait(120)
            res = br.handle("assist_ask_status", {"command": "assist_ask_status", "ask_id": started["ask_id"]})
            ans = res.get("answer") or ""
            asks.append({"method": res.get("method"), "status": res.get("status"), "wall_s": round(time.monotonic() - t, 2),
                         "answer": ans[:400], "mentions_401": "401" in ans,
                         "toggles_ok": ("voice" in ans.lower() and "gmail" in ans.lower())})
        rec["asks"] = asks
        rec["decode_after"] = decode_probe()
        rec["residency_after"] = next((p for p in G.census().get("processes", []) if p.get("name") == "llama-server.exe"), None)
        br.close()
        ok = all(a["status"] == "COMPLETE" and a["method"] == "vision" and a["mentions_401"] and a["toggles_ok"] for a in asks)
        rec["correct_all"] = ok
        rec["classification"] = "COMPLETED_WITH_RESULT"
        return rec
    except Exception as exc:
        rec["classification"] = "FAILED"
        rec["error"] = f"{type(exc).__name__}: {exc}"
        return rec
    finally:
        stop.parent.mkdir(parents=True, exist_ok=True)
        stop.write_text("assist vision app-path test done")
        try:
            host.wait(120)
        except subprocess.TimeoutExpired:
            host.terminate()
        rec["host_exit"] = host.returncode
        rec["lease_after"] = G.peek().get("state")
        (OUT / "assist_vision.json").write_text(json.dumps(rec, indent=1, default=str), encoding="utf-8")
        print(json.dumps({k: rec.get(k) for k in ("label", "classification", "error", "host_ready_s", "decode_before",
                                                  "decode_after", "correct_all", "host_exit", "lease_after")}, default=str))
        for a in rec.get("asks", []):
            print(json.dumps(a))


if __name__ == "__main__":
    main()
