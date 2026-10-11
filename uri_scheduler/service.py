"""Scheduler service process: single-instance run loop + local HTTP API + CLI.

  python -m uri_scheduler.service run    --state <dir> [--mode live|fixture] [--client-home <dir>] [--client-root <dir>]
                                         [--qualification phase2d|probe] [--port 18520] [--tick-s 15]
  python -m uri_scheduler.service status --state <dir>
  python -m uri_scheduler.service propose-festivals --state <dir> --owner <principal> [--festivals a,b] [--time 09:00]
  python -m uri_scheduler.service festivals
  python -m uri_scheduler.service secure-state --state <dir>

The service needs no Brain, no UI window and no conversation. It holds `scheduler.lock` (a second instance on the same
state dir exits with SCHEDULER_ALREADY_RUNNING) and the supervisor's own lock. The HTTP API binds 127.0.0.1 only and
requires the bearer token written to `<state>/api-token`. The state folder must be restricted to the current Windows user
(created that way when new; an existing one is checked, never repaired) and the token file is user-only before it is
written (SCHED-TOKEN-ACL-1); otherwise the service refuses to start (exit 4). `secure-state --state <dir>` moves an older
state folder into a new locked one once (scheduler stopped). Other
processes of the same user can still read it (same-user trust limit as Phase 1 C1). Persistent operation while URI is closed needs an OS launcher (Task Scheduler logon task); that
registration is an owner decision and is NOT performed here (see docs/scheduler/SCHEDULER_ARCHITECTURE.md).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .a2ui_host import A2uiHostError, A2uiInvalid, SchedulerA2ui
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
        self.a2ui = SchedulerA2ui(sched, owner, gate_snapshot=lambda: self._gate_cache[1])

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
                elif u.path == "/a2ui/surfaces":
                    self._send(200, {"messages": svc.a2ui.open_messages()})
                elif u.path == "/a2ui/calendar":
                    self._send(200, svc.a2ui.calendar_surface())
                elif u.path == "/festivals":
                    self._send(200, s.calendar.festivals("in_festivals"))
                elif u.path == "/calendar":
                    self._send(200, {"calendar_id": "in_festivals", "version": s.calendar.version("in_festivals"),
                                     "records": s.calendar.records("in_festivals"),
                                     "corrections": s._corrections("in_festivals")})
                else:
                    self._send(404, {"error": "NOT_FOUND"})
            except (SchedulerError, A2uiHostError) as exc:
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
                elif u.path == "/a2ui/propose":
                    r = svc.a2ui.propose_from_request(b["request"])
                elif u.path == "/a2ui/action":
                    r = svc.a2ui.action(b["action"])
                elif u.path == "/tick":
                    svc.poke()
                    r = {"poked": True}
                else:
                    self._send(404, {"error": "NOT_FOUND"})
                    return
                svc.poke()
                self._send(200, r)
            except (SchedulerError, A2uiHostError) as exc:
                self._send(400, {"error": exc.code, "detail": exc.detail})
            except A2uiInvalid as exc:
                self._send(400, {"error": "A2UI_INVALID", "detail": exc.errors[:10]})
            except (KeyError, ValueError) as exc:
                self._send(400, {"error": "BAD_REQUEST", "detail": str(exc)})
            except Exception as exc:              # noqa: BLE001
                self._send(500, {"error": type(exc).__name__, "detail": str(exc)})

    return H


class StateAclError(Exception):
    pass


_WINDOWS = os.name == "nt"
_REPARSE = 0x400                                          # FILE_ATTRIBUTE_REPARSE_POINT


def _user_sid() -> str:
    r = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=30)
    sid = r.stdout.strip().rsplit(",", 1)[-1].strip('"') if r.returncode == 0 else ""
    if not re.fullmatch(r"S-1-[0-9-]+", sid):
        raise StateAclError("no current user SID")
    return sid


def _is_link(path: Path) -> bool:
    """A symlink, junction or other reparse point, read with lstat so it is never followed."""
    st = os.lstat(path)
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & _REPARSE)


def user_only_sddl(sid: str) -> str:
    """The state folder's one allowed security descriptor: the user owns it, and its protected DACL holds only the
    user's inheritable full-control entry."""
    return f"O:{sid}D:P(A;OICI;FA;;;{sid})"


def _win32():
    import ctypes
    from ctypes import wintypes as w
    adv, k32 = ctypes.WinDLL("advapi32", use_last_error=True), ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = w.HANDLE
    k32.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE]
    k32.CreateDirectoryW.argtypes = [w.LPCWSTR, ctypes.c_void_p]
    k32.GetFileInformationByHandle.argtypes = [w.HANDLE, ctypes.c_void_p]
    k32.CloseHandle.argtypes = [w.HANDLE]
    k32.LocalFree.argtypes = [ctypes.c_void_p]
    adv.GetSecurityInfo.argtypes = [w.HANDLE, ctypes.c_int, w.DWORD] + [ctypes.POINTER(ctypes.c_void_p)] * 5
    adv.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        ctypes.c_void_p, w.DWORD, w.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    adv.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
        w.LPCWSTR, w.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
    return ctypes, adv, k32


def security_of(path: Path):
    """(owner SID, DACL as SDDL, is a link) of the object at `path` itself, read through one handle opened without
    following a symlink or junction, so all three describe the same object."""
    ctypes, adv, k32 = _win32()
    h = k32.CreateFileW(str(path), 0x20000, 7, None, 3, 0x02000000 | 0x00200000, None)   # READ_CONTROL, share all,
    if h in (None, ctypes.c_void_p(-1).value):                                           # OPEN_EXISTING, BACKUP_SEM.,
        raise StateAclError(f"cannot open {path.name}")                                  # OPEN_REPARSE_POINT
    sd, text, info = ctypes.c_void_p(), ctypes.c_void_p(), (ctypes.c_uint32 * 13)()
    try:
        if not k32.GetFileInformationByHandle(h, info) or adv.GetSecurityInfo(
                h, 1, 0x1 | 0x4, None, None, None, None, ctypes.byref(sd)):              # OWNER | DACL
            raise StateAclError(f"cannot read the ACL of {path.name}")
        if not adv.ConvertSecurityDescriptorToStringSecurityDescriptorW(sd, 1, 0x1 | 0x4, ctypes.byref(text), None):
            raise StateAclError(f"cannot read the ACL of {path.name}")
        sddl = ctypes.wstring_at(text.value)
    finally:
        k32.LocalFree(sd)
        k32.LocalFree(text)
        k32.CloseHandle(h)
    m = re.fullmatch(r"O:(S-[0-9-]+|[A-Z]{2})D:(.*)", sddl)
    if not m:
        raise StateAclError(f"unexpected ACL on {path.name}")
    return m.group(1), m.group(2), bool(info[0] & _REPARSE)


def _create_locked_folder(path: Path, sid: str):
    """CreateDirectoryW with the user-only descriptor, so the folder is never open, not even for an instant."""
    ctypes, adv, k32 = _win32()

    class SA(ctypes.Structure):
        _fields_ = [("n", ctypes.c_uint32), ("sd", ctypes.c_void_p), ("inherit", ctypes.c_int)]
    sd = ctypes.c_void_p()
    if not adv.ConvertStringSecurityDescriptorToSecurityDescriptorW(user_only_sddl(sid), 1, ctypes.byref(sd), None):
        raise StateAclError("could not build the user-only ACL")
    try:
        if not k32.CreateDirectoryW(str(path), ctypes.byref(SA(ctypes.sizeof(SA), sd, 0))):
            raise OSError(ctypes.get_last_error(), "CreateDirectoryW failed", str(path))
    finally:
        k32.LocalFree(sd)


def check_state_folder(path: Path):
    """SCHED-TOKEN-ACL-1 (redesign): the state folder is checked, never repaired. It must be a plain folder the
    current user owns, with exactly the user-only DACL, and nothing inside may be a link or owned, or accessible
    through an explicit entry, by anyone else. Repairing a folder another principal could write to raced that
    principal at every step (lifecycle 1b rounds 1-5); refusing is simple and closes the whole class. An existing
    install is moved over once with `secure-state`. POSIX: owned by the user, no links, folder mode 0700."""
    if not _WINDOWS:
        return _check_posix(path)
    sid = _user_sid()
    owner, dacl, link = security_of(path)
    # "P" (protected) is required; Windows may add AI/AR when it stores the descriptor
    if link or owner != sid or not re.fullmatch(rf"P(AR)?(AI)?\(A;OICI;FA;;;{sid}\)", dacl):
        raise StateAclError("the state folder is not restricted to the current user; stop the scheduler and run "
                            "`python -m uri_scheduler.service secure-state --state <folder>`")
    for root, dirs, files in os.walk(path):
        for name in dirs + files:
            owner, dacl, link = security_of(Path(root) / name)
            trustees = set(re.findall(r";([^;()]+)\)", dacl))
            if link or owner != sid or trustees - {sid}:
                raise StateAclError(f"{name} in the state folder is a link or belongs to another user; run "
                                    "`secure-state`")


def _check_posix(path: Path):
    for p in [path] + [Path(r) / n for r, ds, fs in os.walk(path) for n in ds + fs]:
        st = os.lstat(p)
        if stat.S_ISLNK(st.st_mode) or st.st_uid != os.geteuid():
            raise StateAclError(f"{p.name} is a link or belongs to another user; run `secure-state`")
    if stat.S_IMODE(os.lstat(path).st_mode) & 0o077:
        raise StateAclError("the state folder is open to other users; run `secure-state`")


def make_state_folder(path: Path):
    """Create the state folder locked to the current user from the start; an existing one is only checked."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not os.path.lexists(path):
            if _WINDOWS:
                _create_locked_folder(path, _user_sid())
            else:
                os.mkdir(path, 0o700)
                os.chmod(path, 0o700)
        check_state_folder(path)
    except (OSError, subprocess.SubprocessError) as exc:
        raise StateAclError(f"state folder: {type(exc).__name__}: {exc}") from None


def secure_state(path: Path) -> Path:
    """One-off move of an existing state folder into a new locked one: the old folder is renamed aside (kept, never
    deleted) and its plain files and folders are copied in; a link inside it stops the move before anything changes.
    The copies are new files owned by the user that inherit the user-only entry. Run with the scheduler stopped."""
    if _running_instance(path):
        raise StateAclError("the scheduler is running; stop it first")
    links = [Path(r) / n for r, ds, fs in os.walk(path) for n in ds + fs if _is_link(Path(r) / n)]
    if _is_link(path) or links:
        raise StateAclError(f"links in the state folder, remove them first: {[str(x) for x in links][:5]}")
    old = path.with_name(f"{path.name}.pre-acl-{int(time.time())}")
    os.rename(path, old)
    make_state_folder(path)
    import shutil
    for item in old.iterdir():
        (shutil.copytree if item.is_dir() else shutil.copyfile)(item, path / item.name)
    check_state_folder(path)
    return old


def _running_instance(state: Path) -> bool:
    """True when another process holds `<state>/scheduler.lock` (the Scheduler's single-instance lock). Probed before
    the ACL of a possibly live state folder is touched; the probe lock is released at once (R1-01)."""
    path = state / "scheduler.lock"
    if not path.exists():
        return False
    try:
        fh = open(path, "a+b")
    except OSError:
        return False
    try:
        fh.seek(0)
        if _WINDOWS:
            import msvcrt
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        return False
    except OSError:
        return True
    finally:
        fh.close()


def write_token_file(path: Path, token: str):
    """A new token file on every launch: created empty inside the checked folder (so it inherits only the user's
    entry), given its own user-only entry, then written. On failure no token is left on disk; OS failures surface as
    StateAclError so the service exits 4 instead of crashing."""
    try:
        if path.exists():
            path.unlink()
        path.write_bytes(b"")
        if _WINDOWS:
            r = subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"*{_user_sid()}:F"],
                               capture_output=True, text=True, timeout=30)
            if r.returncode:
                raise StateAclError("could not restrict the token file to the current user")
        else:
            os.chmod(path, 0o600)
        path.write_text(token, encoding="utf-8")
    except (OSError, subprocess.SubprocessError, StateAclError) as exc:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        if isinstance(exc, StateAclError):
            raise
        raise StateAclError(f"token file failed: {type(exc).__name__}") from None


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
    sec = sub.add_parser("secure-state", help="move an existing state folder into a new one locked to this user")
    sec.add_argument("--state", required=True)
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
    state = Path(a.state)
    try:
        if a.cmd == "secure-state":
            print(json.dumps({"secured": str(state), "previous_kept_at": str(secure_state(state))}))
            return 0
        make_state_folder(state)                    # before the database or the token exists (SCHED-TOKEN-ACL-1)
    except (OSError, StateAclError) as exc:
        print(json.dumps({"error": "STATE_ACL_FAILED", "detail": str(exc)}))
        return 4
    try:
        sched = build(a).start()
    except SchedulerAlreadyRunning as exc:
        print(json.dumps({"error": exc.code, "detail": exc.detail}))
        return 3
    token_path = Path(a.state) / "api-token"
    token = secrets.token_urlsafe(32)
    try:
        write_token_file(token_path, token)
    except StateAclError as exc:
        sched.close()
        print(json.dumps({"error": "STATE_ACL_FAILED", "detail": str(exc)}))
        return 4
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
