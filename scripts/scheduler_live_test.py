"""Short-horizon end-to-end qualification of the URI Scheduler through the REAL service process and HTTP API.

  python scripts/scheduler_live_test.py --evidence <dir> --mode fixture            # synthetic stand-in (labelled)
  python scripts/scheduler_live_test.py --evidence <dir> --mode live --client-home <dir> [--qualification probe|phase2d]
                                        [--client-root <dir>]
  python scripts/scheduler_live_test.py --evidence <dir> --mode live ... --expect-blocked   # unavailable-Claude leg

Steps (each timestamped into <evidence>/journal.json):
  1 start `python -m uri_scheduler.service run` (separate process, own state dir)
  2 create a one-time task due `--lead-s` seconds from now (Asia/Kolkata) through POST /jobs/propose + /confirm
  3 verify it is persisted (scheduler.db row) BEFORE its due time and nothing ran early
  4 wait for the scheduler to trigger it at the due time (no manual tick)
  5 the harness runs (LIVE = real Claude CLI under the client profile; FIXTURE = synthetic stand-in)
  6 GIF produced and verified independently here (signature, frames, animation)
  7 artifact appears in GET /overview pending approvals
  8 request one refinement ("More floral energy")
  9 revised candidate v2 produced (parent = v1)
  10 approve v2 by sha256; confirm v1 superseded, nothing published
Nothing here logs in, reads credentials, registers OS tasks or publishes anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
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
J = []


def log(step, **kw):
    rec = {"t_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "step": step, **kw}
    J.append(rec)
    print(json.dumps(rec, default=str)[:600], flush=True)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Api:
    def __init__(self, port, state):
        self.port, self.state = port, Path(state)

    def call(self, method, path, body=None, raw=False):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", method=method,
                                     data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Authorization", "Bearer " + (self.state / "api-token").read_text(encoding="utf-8"))
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
                return r.status, (data if raw else json.loads(data))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())


def wait(pred, timeout, every=1.0, what=""):
    end = time.time() + timeout
    while time.time() < end:
        v = pred()
        if v:
            return v
        time.sleep(every)
    raise TimeoutError(what)


def verify_gif(data: bytes) -> dict:
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(data))
    n = getattr(im, "n_frames", 1)
    hashes = set()
    for i in range(0, n, max(1, n // 6)):
        im.seek(i)
        hashes.add(hashlib.sha256(im.convert("RGB").tobytes()).hexdigest())
    return {"signature": data[:6].decode("latin-1"), "format": im.format, "is_animated": bool(getattr(im, "is_animated", False)),
            "n_frames": n, "size": list(im.size), "distinct_sampled_frames": len(hashes), "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", required=True)
    ap.add_argument("--mode", choices=("live", "fixture"), required=True)
    ap.add_argument("--client-home")
    ap.add_argument("--client-root")
    ap.add_argument("--qualification", default="probe", choices=("probe", "phase2d"))
    ap.add_argument("--lead-s", type=int, default=75)
    ap.add_argument("--timeout-s", type=float, default=900)
    ap.add_argument("--expect-blocked", action="store_true")
    ap.add_argument("--festival", default="diwali")
    a = ap.parse_args()
    ev = Path(a.evidence).resolve()
    if ev.exists():
        shutil.rmtree(ev)
    ev.mkdir(parents=True)
    state = ev / "state"
    port = free_port()
    cmd = [sys.executable, "-m", "uri_scheduler.service", "run", "--state", str(state), "--mode", a.mode, "--port", str(port),
           "--tick-s", "5", "--timeout-s", str(a.timeout_s), "--inactivity-s", "600", "--qualification", a.qualification]
    if a.mode == "fixture":
        cmd += ["--fixture-script", str(FAKE)]
    if a.client_home:
        cmd += ["--client-home", a.client_home]
    if a.client_root:
        cmd += ["--client-root", a.client_root]
    env = dict(os.environ, PYTHONPATH=str(ROOT), URI_FAKE_SCENARIO="honest")
    out = open(ev / "service.stdout.log", "wb")
    err = open(ev / "service.stderr.log", "wb")
    p = subprocess.Popen(cmd, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=err,
                         creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    ready = json.loads(p.stdout.readline().decode())
    log("1.service_started", pid=p.pid, port=port, mode=a.mode, ready=ready, argv=cmd)
    api = Api(port, state)
    result = {"mode": a.mode, "simulated": a.mode == "fixture", "steps": {}}
    try:
        cal = json.loads((ROOT / "uri_scheduler" / "data" / "in_festivals.json").read_text(encoding="utf-8"))
        fest = next(f for f in cal["festivals"] if f["festival_key"] == a.festival)
        occ26 = next(o for o in fest["occurrences"] if o["status"] == "published" and o["start"] >= "2026-10-09")
        due_local = (datetime.now(IST) + timedelta(seconds=a.lead_s)).replace(microsecond=0, tzinfo=None)
        code, prop = api.call("POST", "/jobs/propose", {
            "principal": "owner", "title": f"LIVE TEST {a.mode}: {fest['name']} GIF", "template_id": "festival_gif.v1",
            "params": {"festival": {"key": fest["festival_key"], "name": fest["name"], "date": occ26["start"]}},
            "schedule": {"kind": "once", "at": due_local.isoformat(), "tz": "Asia/Kolkata"}})
        assert code == 200, prop
        log("2a.proposed", job_id=prop["job_id"], interpretation=prop["interpretation"], upcoming=prop["upcoming"])
        code, job = api.call("POST", f"/jobs/{prop['job_id']}/confirm", {"principal": "owner", "proposal_sha256": prop["proposal_sha256"]})
        assert code == 200 and job["state"] == "ACTIVE", job
        log("2b.confirmed", state=job["state"], due_local=due_local.isoformat())
        db = sqlite3.connect(f"file:{state / 'scheduler.db'}?mode=ro", uri=True)
        row = db.execute("SELECT occ_id, state, due_at_us FROM occurrence").fetchone()
        db.close()
        assert row and row[1] == "SCHEDULED"
        due_us = row[2]
        log("3.persisted_before_due", occ_id=row[0], state=row[1], due_utc=datetime.fromtimestamp(due_us / 1e6, tz=timezone.utc).isoformat(),
            seconds_until_due=round(due_us / 1e6 - time.time(), 1))
        result["steps"]["persisted"] = True

        def occ_state():
            c, ov = api.call("GET", "/overview?owner=owner")
            for k in ("upcoming", "errors", "pending_approvals", "approved"):
                for o in ov.get(k, []):
                    if o["occ_id"] == row[0]:
                        return o["state"], o, ov
            return None, None, ov

        st, _, _ = occ_state()
        assert st == "SCHEDULED", st
        claimed_at = wait(lambda: (lambda s: time.time() if s[0] not in ("SCHEDULED",) else None)(occ_state()), a.lead_s + 120, 0.5,
                          "trigger")
        log("4.triggered", state=occ_state()[0], trigger_delay_s=round(claimed_at - due_us / 1e6, 2))
        result["steps"]["trigger_delay_s"] = round(claimed_at - due_us / 1e6, 2)
        if a.expect_blocked:
            st, o, ov = wait(lambda: (lambda s: s if s[0] == "BLOCKED_HARNESS" else None)(occ_state()), 120, 1, "blocked")
            c, evs = api.call("GET", "/events?limit=100")
            blocked = [e for e in evs if e["kind"] == "harness.unavailable"]
            log("5.harness_unavailable_recorded", reason=o["reason"], event=blocked[0]["payload"] if blocked else None,
                harness=ov["harness"])
            result["steps"]["blocked"] = {"reason": o["reason"], "event": blocked[0]["payload"] if blocked else None}
            result["verdict"] = "BLOCKED_AS_EXPECTED"
            return 0
        st, o, ov = wait(lambda: (lambda s: s if s[0] in ("AWAITING_REVIEW", "FAILED", "BLOCKED_HARNESS", "NEEDS_ATTENTION",
                                                           "QUOTA_DEFERRED") else None)(occ_state()), a.timeout_s + 300, 2, "v1")
        log("5.harness_finished", state=st, reason=o.get("reason"))
        if st != "AWAITING_REVIEW":
            result["verdict"] = "FAILED_" + st
            return 1
        c1 = o["candidates"][0]
        code, data = api.call("GET", f"/artifacts/{c1['artifact_id']}/file", raw=True)
        g1 = verify_gif(data)
        (ev / "v1.gif").write_bytes(data)
        assert g1["sha256"] == c1["sha256"] and g1["is_animated"] and g1["n_frames"] >= 8 and g1["signature"] == "GIF89a"
        log("6.gif_v1_verified", **g1, quality=c1["info"]["quality"], mode=c1["info"]["mode"])
        log("7.in_review_interface", artifact_id=c1["artifact_id"], version=c1["version"], concept=c1["concept"][:400])
        code, r = api.call("POST", f"/artifacts/{c1['artifact_id']}/review", {"principal": "owner", "action": "refine",
                                                                              "sha256": c1["sha256"], "instruction": "More floral energy"})
        assert code == 200, r
        log("8.refine_requested", occ_state=r["occurrence"]["state"])
        def v2_or_failure():
            s_ = occ_state()
            if s_[0] in ("FAILED", "BLOCKED_HARNESS", "NEEDS_ATTENTION", "QUOTA_DEFERRED"):
                return s_
            if s_[0] == "AWAITING_REVIEW" and s_[1]["candidates"] and s_[1]["candidates"][0]["version"] == 2:
                return s_
            return None

        st, o, ov = wait(v2_or_failure, a.timeout_s + 300, 2, "v2")
        if st != "AWAITING_REVIEW":
            log("9.refine_failed", state=st, reason=o.get("reason"))
            result["verdict"] = "FAILED_REFINE_" + st
            return 1
        c2 = o["candidates"][0]
        code, data2 = api.call("GET", f"/artifacts/{c2['artifact_id']}/file", raw=True)
        g2 = verify_gif(data2)
        (ev / "v2.gif").write_bytes(data2)
        assert c2["parent_artifact_id"] == c1["artifact_id"] and g2["sha256"] != g1["sha256"] and g2["is_animated"]
        log("9.gif_v2_verified", **g2, parent=c2["parent_artifact_id"], concept=c2["concept"][:600])
        code, r = api.call("POST", f"/artifacts/{c2['artifact_id']}/review", {"principal": "owner", "action": "approve",
                                                                              "sha256": c2["sha256"]})
        assert code == 200 and r["occurrence"]["state"] == "APPROVED", r
        code, a1 = api.call("GET", f"/artifacts/{c1['artifact_id']}")
        log("10.approved_v2", occ_state=r["occurrence"]["state"], v2_status=r["artifact"]["status"], v1_status=a1["status"],
            reviews=r["artifact"]["reviews"])
        code, evs = api.call("GET", "/events?limit=500")
        assert not any(e["payload"].get("published") for e in evs if e["kind"].startswith("review."))
        code, status = api.call("GET", "/status")
        result.update(verdict="PASS", v1=g1, v2=g2, chain=status["chain"], harness=status["harness"])
        return 0
    finally:
        try:
            c, evs = api.call("GET", "/events?limit=1000")
            (ev / "events.json").write_text(json.dumps(list(reversed(evs)), indent=1, default=str), encoding="utf-8")
            c, ov = api.call("GET", "/overview?owner=owner")
            (ev / "overview.json").write_text(json.dumps(ov, indent=1, default=str), encoding="utf-8")
            db = sqlite3.connect(f"file:{state / 'scheduler.db'}?mode=ro", uri=True)
            db.row_factory = sqlite3.Row
            (ev / "attempts.json").write_text(json.dumps([dict(r) for r in db.execute("SELECT * FROM attempt")], indent=1, default=str),
                                              encoding="utf-8")
            db.close()
        except Exception as exc:     # noqa: BLE001
            log("evidence_export_error", error=str(exc))
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
        p.wait(30)
        out.close()
        err.close()
        (ev / "journal.json").write_text(json.dumps(J, indent=1, default=str), encoding="utf-8")
        (ev / "result.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
