"""PROCESS-LEVEL A2UI check: the real Flutter renderer/hub against a real scheduler service process.

  python scripts/a2ui_live_check.py --out docs/a2ui/evidence/live_<stamp>

1. Starts `python -m uri_scheduler.service run` (fixture executor: the SYNTHETIC stand-in, labelled FIXTURE, not Claude)
   on a fresh state dir; produces one candidate GIF through a confirmed one-time job so a review surface exists.
2. Interprets the owner's sentence with the worker's interpreter (uri_operational_intelligence.schedule_intent).
3. Phase a (flutter test, URI_A2UI_PHASE=a): handoff -> proposal surface, edit, refused confirm of an un-proposed draft,
   revise, artifact review (image bytes SHA-256 checked) -> approve, calendar dispute.
4. Kills the service process (taskkill /F /T) and restarts it on the same state dir.
5. Phase b: the open proposal re-renders from the stored record; a forged action with the pre-revision digest is refused;
   confirm -> ACTIVE.
6. Checks every outcome through the scheduler API (job state and schedule, artifact status, calendar correction, hash
   chain) and writes `a2ui_live_result.json` with the renderer's timings.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAKE = ROOT / "tests" / "scheduler" / "helpers" / "fake_claude.py"
IST = timezone(timedelta(hours=5, minutes=30))
OWNER = ("URI, schedule Claude to create a festival GIF two days before each major Indian festival and bring it to me "
         "for approval.")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(state, port, log):
    env = dict(os.environ, URI_FAKE_SCENARIO="honest", PYTHONPATH=str(ROOT))
    p = subprocess.Popen([sys.executable, "-m", "uri_scheduler.service", "run", "--state", str(state), "--mode", "fixture",
                          "--fixture-script", str(FAKE), "--port", str(port), "--tick-s", "1", "--owner", "owner"],
                         cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=open(log, "ab"),
                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    ready = json.loads(p.stdout.readline().decode())
    assert ready.get("ready"), ready
    return p


def kill(p):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    p.wait(30)


def api(port, state, method, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    req.add_header("Authorization", "Bearer " + (Path(state) / "api-token").read_text(encoding="utf-8"))
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def flutter(phase, env_extra, out_file, log):
    env = dict(os.environ, URI_A2UI_LIVE="1", URI_A2UI_PHASE=phase, URI_A2UI_OUT=str(out_file), **env_extra)
    t0 = time.time()
    r = subprocess.run(["flutter", "test", "test/a2ui/a2ui_service_live_test.dart"], cwd=str(ROOT / "uri_ui"), env=env,
                       capture_output=True, text=True, timeout=900, shell=True)
    Path(log).write_text(r.stdout + "\n" + r.stderr, encoding="utf-8")
    return r.returncode, round(time.time() - t0, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    state = out / "state"
    port = free_port()
    res = {"started_utc": datetime.now(timezone.utc).isoformat(), "evidence_level": "P (process: real service + real "
           "renderer; executor is the SYNTHETIC fixture, not Claude)", "checks": {}}
    svc = start(state, port, out / "service.stderr.log")
    try:
        # A candidate artifact for the review journey (one-time job due in a few seconds, FIXTURE executor).
        due = (datetime.now(IST) + timedelta(seconds=3)).replace(microsecond=0, tzinfo=None).isoformat()
        code, prop = api(port, state, "POST", "/jobs/propose", {
            "title": "A2UI live check: Diwali GIF", "template_id": "festival_gif.v1",
            "params": {"festival": {"key": "diwali", "name": "Diwali (Deepavali)", "date": "2026-11-08"}},
            "schedule": {"kind": "once", "at": due, "tz": "Asia/Kolkata"}})
        assert code == 200, prop
        assert api(port, state, "POST", f"/jobs/{prop['job_id']}/confirm", {"proposal_sha256": prop["proposal_sha256"]})[0] == 200
        t0 = time.time()
        while time.time() - t0 < 300:
            ov = api(port, state, "GET", "/overview")[1]
            if ov["pending_approvals"]:
                break
            time.sleep(1)
        assert ov["pending_approvals"], "no candidate artifact"
        res["checks"]["fixture_artifact_ready_s"] = round(time.time() - t0, 1)

        sys.path.insert(0, str(ROOT))
        from uri_operational_intelligence.schedule_intent import interpret
        handoff = interpret(OWNER)
        (out / "handoff.json").write_text(json.dumps(handoff, indent=1), encoding="utf-8")
        env = {"URI_SCHEDULER_STATE": str(state), "URI_A2UI_HANDOFF": str(out / "handoff.json")}
        rc_a, dur_a = flutter("a", env, out / "phase_a.json", out / "phase_a.log")
        res["phase_a"] = {"exit": rc_a, "seconds": dur_a}
        assert rc_a == 0, (out / "phase_a.log").read_text(encoding="utf-8")[-3000:]
        pa = json.loads((out / "phase_a.json").read_text(encoding="utf-8"))

        kill(svc)
        res["checks"]["service_killed_and_restarted"] = True
        svc = start(state, port, out / "service.stderr.log")
        rc_b, dur_b = flutter("b", dict(env, URI_A2UI_SURFACE=pa["surface"], URI_A2UI_STALE=pa["stale_digest"]),
                              out / "phase_b.json", out / "phase_b.log")
        res["phase_b"] = {"exit": rc_b, "seconds": dur_b}
        assert rc_b == 0, (out / "phase_b.log").read_text(encoding="utf-8")[-3000:]

        # Authority-side verification of every outcome.
        ov = api(port, state, "GET", "/overview")[1]
        jobs = {j["job_id"]: j for j in ov["jobs"]}
        active = [j for j in jobs.values() if j["template_id"] == "festival_gif.v1" and j["schedule"]["kind"] == "calendar_relative"
                  and j["state"] == "ACTIVE"]
        assert len(active) == 1, jobs
        sch = active[0]["schedule"]
        res["checks"]["activated_schedule"] = {"selection": sch["selection"], "time": sch["time"], "offset_days": sch["offset_days"]}
        assert sorted(sch["selection"]) == ["diwali", "holi"] and sch["time"] == "08:30" and sch["offset_days"] == -2
        cancelled = [j for j in jobs.values() if j["schedule"]["kind"] == "calendar_relative" and j["state"] == "CANCELLED"]
        res["checks"]["superseded_proposals_cancelled"] = len(cancelled)
        assert len(cancelled) == 1
        assert ov["approved"], "artifact not approved"
        res["checks"]["artifact_approved_occurrences"] = len(ov["approved"])
        cal = api(port, state, "GET", "/calendar")[1]
        corr = [c for c in cal["corrections"] if c["festival_key"] == "karva_chauth"]
        assert corr and corr[0]["action"] == "dispute"
        res["checks"]["calendar_correction"] = {k: corr[0][k] for k in ("festival_key", "year", "action", "note")}
        st = api(port, state, "GET", "/status")[1]
        res["checks"]["hash_chain"] = st["chain"]
        assert st["chain"]["ok"]
        evs = api(port, state, "GET", "/events?limit=500")[1]
        acts = [e["payload"] for e in evs if e["kind"] == "a2ui.action"]
        res["checks"]["a2ui_actions_audited"] = [(x["name"], x["result"]) for x in reversed(acts)]
        res["renderer_timings_ms"] = {"phase_a": pa.get("timings"), "phase_b": json.loads((out / "phase_b.json").read_text(
            encoding="utf-8")).get("timings")}
        res["verdict"] = "PASS"
    except AssertionError as exc:
        res["verdict"] = "FAILED"
        res["error"] = str(exc)[:4000]
    finally:
        kill(svc)
        res["finished_utc"] = datetime.now(timezone.utc).isoformat()
        (out / "a2ui_live_result.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
        print(json.dumps({k: res[k] for k in ("verdict", "checks") if k in res}, indent=1, default=str)[:3000])
    return 0 if res.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
