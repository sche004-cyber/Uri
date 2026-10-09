"""Scheduler service process: single-instance run loop + local HTTP API + CLI.

  python -m uri_scheduler.service run    --state <dir> [--mode live|fixture] [--client-home <dir>] [--client-root <dir>]
                                         [--qualification phase2d|probe] [--port 18520] [--tick-s 15]
  python -m uri_scheduler.service status --state <dir>
  python -m uri_scheduler.service propose-festivals --state <dir> --owner <principal> [--festivals a,b] [--time 09:00]
  python -m uri_scheduler.service festivals

The service needs no Brain, no UI window and no conversation. It holds `scheduler.lock` (a second instance on the same
state dir exits with SCHEDULER_ALREADY_RUNNING) and the supervisor's own lock. The HTTP API binds 127.0.0.1 only and
requires the bearer token written to `<state>/api-token` (readable by the same Windows user; same-user trust limit as
Phase 1 C1). Persistent operation while URI is closed needs an OS launcher (Task Scheduler logon task); that
registration is an owner decision and is NOT performed here (see docs/scheduler/SCHEDULER_ARCHITECTURE.md).
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .engine import Scheduler, SchedulerAlreadyRunning, SchedulerError
from .harness import ClaudeHarness

MAJOR_DEFAULT = ("holi", "ram_navami", "mahavir_jayanti", "buddha_purnima", "eid_ul_fitr", "eid_ul_zuha", "janmashtami",
                 "dussehra", "diwali", "guru_nanak_jayanti", "christmas", "milad_un_nabi")


def festival_job_request(owner, festivals=None, time_hhmm="09:00", style=None) -> dict:
    """The interpretation of: 'make me a GIF two days before every major Indian festival and bring it to me for approval'."""
    sel = list(festivals or MAJOR_DEFAULT)
    return {"owner": owner, "title": "Festival greeting GIF, 2 days before each selected festival",
            "template_id": "festival_gif.v1", "params": {"style": style} if style else {},
            "schedule": {"kind": "calendar_relative", "calendar": "in_festivals", "selection": sel, "offset_days": -2,
                         "time": time_hhmm, "tz": "Asia/Kolkata"}}


class Service:
    """One service instance serves exactly ONE principal (`--owner`). The API token authenticates that principal; a request
    can never name another one (review round 1, F1)."""

    def __init__(self, sched: Scheduler, *, tick_s=15.0, owner="owner"):
        self.s = sched
        self.owner = owner
        self.tick_s = float(tick_s)
        self._stop = threading.Event()
        self._wake = threading.Event()
        self.last_tick = None
        self.last_error = None
        self._gate_cache = (0.0, None)

    def gate_cached(self, ttl=60):
        t, g = self._gate_cache
        if g is None or time.time() - t > ttl:
            g = self.s.harness.gate().to_json() if self.s.harness else None
            self._gate_cache = (time.time(), g)
        return g

    def loop(self):
        while not self._stop.is_set():
            try:
                self.s.tick()
                self.last_tick = time.time()
                self.last_error = None
            except Exception as exc:          # noqa: BLE001 - the loop must survive; the error is visible in /status
                self.last_error = f"{type(exc).__name__}: {exc}"
                traceback.print_exc()
            self._wake.wait(self.tick_s)
            self._wake.clear()

    def poke(self):
        self._wake.set()

    def stop(self):
        self._stop.set()
        self._wake.set()


def make_handler(svc: Service, token: str):
    s = svc.s

    class H(BaseHTTPRequestHandler):
        server_version = "uri-scheduler/1"

        def log_message(self, *a):
            pass

        def _send(self, code, obj):
            body = json.dumps(obj, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _auth(self):
            if self.headers.get("Authorization") != "Bearer " + token:
                self._send(401, {"error": "UNAUTHORIZED"})
                return False
            return True

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > 64 * 1024:
                raise SchedulerError("BODY_TOO_LARGE")
            return json.loads(self.rfile.read(n) or b"{}")

        def do_GET(self):
            if not self._auth():
                return
            u = urlparse(self.path)
            qs = parse_qs(u.query)
            try:
                if u.path == "/status":
                    self._send(200, {"last_tick": svc.last_tick, "last_error": svc.last_error, "harness": svc.gate_cached(),
                                     "chain": s.store.verify_chain()})
                elif u.path == "/overview":
                    ov = s.overview(owner=svc.owner, include_harness=False)
                    ov["harness"] = svc.gate_cached()     # a live auth probe per UI poll would be wasteful
                    self._send(200, ov)
                elif u.path.startswith("/artifacts/") and u.path.endswith("/file"):
                    art = s.artifact(int(u.path.split("/")[2]))
                    s._owner_check(s.job(s.occurrence(art["occ_id"])["job_id"]), svc.owner)
                    data = Path(art["path"]).read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "image/gif")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                elif u.path.startswith("/artifacts/"):
                    art = s.artifact(int(u.path.split("/")[2]))
                    s._owner_check(s.job(s.occurrence(art["occ_id"])["job_id"]), svc.owner)
                    self._send(200, art)
                elif u.path.startswith("/events"):
                    own = {r[0] for r in s.store.q("SELECT job_id FROM job WHERE owner=?", (svc.owner,))}
                    evs = s.store.events(job_id=qs.get("job", [None])[0], limit=int(qs.get("limit", ["200"])[0]))
                    self._send(200, [e for e in evs if e["job_id"] is None or e["job_id"] in own])
                elif u.path == "/festivals":
                    self._send(200, s.calendar.festivals("in_festivals"))
                elif u.path == "/calendar":
                    self._send(200, {"calendar_id": "in_festivals", "version": s.calendar.version("in_festivals"),
                                     "records": s.calendar.records("in_festivals"),
                                     "corrections": s._corrections("in_festivals")})
                else:
                    self._send(404, {"error": "NOT_FOUND"})
            except SchedulerError as exc:
                self._send(400, {"error": exc.code, "detail": exc.detail})
            except Exception as exc:              # noqa: BLE001
                self._send(500, {"error": type(exc).__name__, "detail": str(exc)})

        def do_POST(self):
            if not self._auth():
                return
            u = urlparse(self.path)
            try:
                b = self._body()
                p = svc.owner
                if b.get("principal") not in (None, p):
                    self._send(403, {"error": "PRINCIPAL_MISMATCH", "detail": "this service acts only for its owner"})
                    return
                if u.path == "/jobs/propose":
                    r = s.propose(owner=p, title=b["title"], template_id=b["template_id"], params=b.get("params", {}),
                                  schedule=b["schedule"], policy=b.get("policy"))
                elif u.path == "/jobs/propose-festivals":
                    req = festival_job_request(p, b.get("festivals"), b.get("time", "09:00"), b.get("style"))
                    r = s.propose(**req, policy=b.get("policy"))
                elif u.path.startswith("/jobs/") and u.path.endswith("/confirm"):
                    r = s.confirm(u.path.split("/")[2], p, b["proposal_sha256"])
                elif u.path.startswith("/jobs/") and u.path.split("/")[-1] in ("pause", "resume", "cancel"):
                    jid, act = u.path.split("/")[2], u.path.split("/")[-1]
                    r = {"pause": s.pause, "resume": s.resume, "cancel": s.cancel_job}[act](jid, p)
                elif u.path.startswith("/occurrences/"):
                    oid, act = int(u.path.split("/")[2]), u.path.split("/")[-1]
                    if act == "cancel":
                        r = s.cancel_occurrence(oid, p)
                    elif act == "retry":
                        r = s.retry_occurrence(oid, p)
                    elif act == "confirm":
                        r = s.confirm_occurrence(oid, p)
                    elif act == "reschedule":
                        r = s.reschedule_occurrence(oid, p, b["local"])
                    else:
                        raise SchedulerError("UNKNOWN_ACTION", act)
                elif u.path.startswith("/artifacts/") and u.path.endswith("/review"):
                    r = s.review(int(u.path.split("/")[2]), p, b["action"], expected_sha256=b.get("sha256"),
                                 instruction=b.get("instruction"))
                elif u.path == "/calendar/correct":
                    r = s.correct_calendar(p, "in_festivals", b["festival_key"], b["year"], b["action"],
                                           start=b.get("start"), end=b.get("end"), note=b.get("note", ""))
                elif u.path == "/tick":
                    svc.poke()
                    r = {"poked": True}
                else:
                    self._send(404, {"error": "NOT_FOUND"})
                    return
                svc.poke()
                self._send(200, r)
            except SchedulerError as exc:
                self._send(400, {"error": exc.code, "detail": exc.detail})
            except (KeyError, ValueError) as exc:
                self._send(400, {"error": "BAD_REQUEST", "detail": str(exc)})
            except Exception as exc:              # noqa: BLE001
                self._send(500, {"error": type(exc).__name__, "detail": str(exc)})

    return H


def build(args) -> Scheduler:
    harness = ClaudeHarness(args.state, mode=args.mode, client_home=args.client_home, client_root=args.client_root,
                            qualification=args.qualification, fixture_script=args.fixture_script,
                            timeout_s=args.timeout_s, inactivity_s=args.inactivity_s)
    return Scheduler(args.state, harness=harness)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="uri_scheduler")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("--state", required=True)
    run.add_argument("--mode", choices=("live", "fixture"), default="live")
    run.add_argument("--client-home")
    run.add_argument("--client-root")
    run.add_argument("--qualification", choices=("phase2d", "probe"), default="phase2d")
    run.add_argument("--fixture-script")
    run.add_argument("--port", type=int, default=18520)
    run.add_argument("--owner", default="owner", help="the one principal this service acts for")
    run.add_argument("--tick-s", type=float, default=15.0)
    run.add_argument("--timeout-s", type=float, default=900.0)
    run.add_argument("--inactivity-s", type=float, default=300.0)
    st = sub.add_parser("status")
    st.add_argument("--state", required=True)
    fe = sub.add_parser("festivals")
    a = ap.parse_args(argv)
    if a.cmd == "festivals":
        from .calendar_store import Calendar
        c = Calendar.default()
        for e in sorted(c.all_events("in_festivals", include_unschedulable=True), key=lambda e: e.start):
            print(f"{e.start}  {e.festival_key:22} {e.status:10} {e.category:20} {e.name}")
        return 0
    if a.cmd == "status":
        from .store import Store
        st = Store(Path(a.state) / "scheduler.db")
        rows = st.q("SELECT state, COUNT(*) FROM occurrence GROUP BY state")
        print(json.dumps({"occurrences": {r[0]: r[1] for r in rows}, "chain": st.verify_chain()}, indent=1))
        return 0
    try:
        sched = build(a).start()
    except SchedulerAlreadyRunning as exc:
        print(json.dumps({"error": exc.code, "detail": exc.detail}))
        return 3
    token_path = Path(a.state) / "api-token"
    token = secrets.token_urlsafe(32)
    token_path.write_text(token, encoding="utf-8")
    svc = Service(sched, tick_s=a.tick_s, owner=a.owner)
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(svc, token))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    (Path(a.state) / "service.json").write_text(json.dumps({"port": a.port, "mode": a.mode, "pid": __import__("os").getpid(),
                                                            "started": time.time(), "token_file": str(token_path)}), encoding="utf-8")
    print(json.dumps({"ready": True, "port": a.port, "mode": a.mode, "startup": sched.startup}, default=str), flush=True)
    try:
        svc.loop()
    except KeyboardInterrupt:
        pass
    finally:
        svc.stop()
        srv.shutdown()
        sched.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
