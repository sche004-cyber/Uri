"""Supervised test runs (LIFECYCLE-V3.1-STORAGE): completion from the real exit status, never from log text.

    python -m scripts.dev_workflow.testrun start --name N --timeout S [--stall S] [--kill-on-stall] [--cwd D]
                                                 [--lock auto|none|<class>] [--reuse] [--task T --actor A] -- <cmd>
    python -m scripts.dev_workflow.testrun status <run-id|name>
    python -m scripts.dev_workflow.testrun wait <run-id|name> --timeout S
    python -m scripts.dev_workflow.testrun list
    python -m scripts.dev_workflow.testrun select --base <rev> [--head <rev>] [--repo D]

Each run lives in ``<runs>/<run-id>/`` (``URI_DEV_RUNS``, default ``~/.uri-dev/runs``): ``output.log`` (stdout and
stderr streamed while the command runs) and ``run.json`` (written atomically at start, at every heartbeat and once
more, final, from the process exit status). The command runs inside ``containment.spawn`` (a Windows Job Object), so
a timeout or stall kill ends its whole process tree.

Why (2026-10-22 Phase 1 watcher incident, P0_CLOSURE_20261022.md Addendum L): a shell loop waited ~307 min for
``^rc=`` in a log the producer never wrote to. ``wait`` here waits on a run id with a mandatory bound, returns at once
for an unknown or finished run and reports MISSING_MARKER when the supervisor died without a final record.

Boundary Guarantee: Development tooling only. Not part of the URI runtime. It never weakens a lifecycle gate: a
reused result is reported as REUSED with the original run id and exit code, and ``select`` is advisory only.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

from scripts.dev_workflow import containment
from scripts.dev_workflow.task_ledger import redact
from scripts.dev_workflow.milestones.store import StoreError, atomic_write_bytes, file_sha256, os_lock

FINAL = ("COMPLETED", "FAILED", "TIMED_OUT", "STALLED_KILLED", "INTERRUPTED", "CONTAINMENT_FAILED")
MAX_TIMEOUT_S = 86400.0
HEARTBEAT_S = 5.0
POLL_S = 0.25
LOCK_WAIT_S = 0.5
# Exit codes. COMPLETED/FAILED return the command's own exit code (FAILED with no exit code: 127).
EXIT = {"TIMED_OUT": 124, "STALLED_KILLED": 125, "INTERRUPTED": 130, "CONTAINMENT_FAILED": 126,
        "DUPLICATE_RUN": 75, "NOT_FOUND": 3,
        "MISSING_MARKER": 4, "WAIT_TIMEOUT": 6, "USAGE": 2}
GIT = ["git", "--no-optional-locks", "--no-replace-objects", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false"]

# Environmental failure signatures, matched on the tail of a failed run's log. They label a failure; they never
# change its exit code or turn it into a pass.
ENV_PATTERNS = [
    ("ENV_MISSING_MODULE", re.compile(r"ModuleNotFoundError: No module named '([\w.]+)'")),
    ("ENV_BROWSER_MISSING", re.compile(r"(?i)(playwright[^\n]*(not installed|executable doesn't exist|not found)|"
                                       r"Executable doesn't exist at)")),
    ("ENV_GPU_BUSY", re.compile(r"(?i)gpu[ _]lease[^\n]*(refused|busy)")),
    ("ENV_DISK_FULL", re.compile(r"(?i)(No space left on device|There is not enough space on the disk|ENOSPC)")),
    ("ENV_PORT_IN_USE", re.compile(r"(?i)(Address already in use|WinError 10048|EADDRINUSE)")),
]
ENV_TAIL_BYTES = 256 * 1024


class RunError(Exception):
    def __init__(self, code: str, msg: str):
        super().__init__(msg)
        self.code = code


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def runs_dir(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit)
    env = os.environ.get("URI_DEV_RUNS")
    return Path(env) if env else Path.home() / ".uri-dev" / "runs"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


SECRET_FLAG_WORDS = {"password", "passwd", "pass", "pwd", "secret", "token", "key", "apikey", "pat", "credential",
                     "credentials", "auth", "authorization", "bearer", "cookie", "sig", "signature"}
_HEADER_SECRET = re.compile(r"(?i)^(\s*(?:proxy-)?(?:authorization|cookie|x-api-key|x-auth-token)\s*:\s*).+")
_BEARER = re.compile(r"(?i)\b(bearer|basic|token)\s+\S+")


def _secret_flag(arg: str) -> bool:
    """A flag whose name has a secret word as one of its parts (--db-password, --aws-secret-access-key,
    --github-token, --key, --pat ...; FB-1 N-03)."""
    if not arg.startswith("-") or arg == "-":
        return False
    if arg == "-p":
        return True
    name = arg.lstrip("-").split("=", 1)[0].lower()
    return any(part in SECRET_FLAG_WORDS for part in re.split(r"[-_.]", name) if part)


def _safe_argv(argv: list[str]) -> list[str]:
    """Keep command identity raw while making persisted and returned argv display-safe."""
    safe = [redact(arg)[0] for arg in argv]
    mark = "[REDACTED:cli_secret]"
    for i, arg in enumerate(argv):
        if _secret_flag(arg):
            if "=" in arg:
                safe[i] = arg.split("=", 1)[0] + "=" + mark
            elif i + 1 < len(argv):
                safe[i + 1] = mark
        if arg in ("-u", "--user") and i + 1 < len(argv) and ":" in argv[i + 1]:
            safe[i + 1] = argv[i + 1].split(":", 1)[0] + ":" + mark
        if _HEADER_SECRET.match(safe[i]):
            safe[i] = _HEADER_SECRET.sub(lambda m: m.group(1) + mark, safe[i])
        elif _BEARER.search(safe[i]):
            safe[i] = _BEARER.sub(lambda m: m.group(1) + " " + mark, safe[i])
    return safe


def _git(cwd, *args) -> tuple[int, str]:
    try:
        p = subprocess.run([*GIT, "-C", str(cwd), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return 1, str(e)
    return p.returncode, p.stdout.strip()


def tree_state(cwd: Path) -> dict:
    """Git identity of the working directory: repository root, HEAD, HEAD's tree id and whether anything (tracked
    or untracked, not ignored) differs from HEAD. Outside git everything is None (no reuse, no ledger record)."""
    rc, root = _git(cwd, "rev-parse", "--show-toplevel")
    if rc:
        return {"repo": None, "head": None, "tree": None, "dirty": None, "rel_cwd": None}
    _, head = _git(cwd, "rev-parse", "HEAD")
    _, tree = _git(cwd, "rev-parse", "HEAD^{tree}")
    rc_s, status = _git(cwd, "status", "--porcelain", "--untracked-files=normal")
    rel = os.path.relpath(os.path.realpath(cwd), os.path.realpath(root)).replace("\\", "/")
    return {"repo": root, "head": head or None, "tree": tree or None, "dirty": bool(status) if rc_s == 0 else None,
            "rel_cwd": rel}


def env_fingerprint() -> dict:
    # Hash the complete inherited environment: recording its values would leak credentials into run.json.
    env = json.dumps(sorted(os.environ.items()), ensure_ascii=False, separators=(",", ":"))
    return {"python": sys.version, "executable": os.path.normcase(os.path.realpath(sys.executable)),
            "environ_sha256": _sha(env)}


def reuse_key(argv: list[str], ts: dict) -> str | None:
    if not ts["tree"] or ts["dirty"] is not False:
        return None
    return _sha(json.dumps({"argv": argv, "repo": os.path.normcase(os.path.realpath(ts["repo"])),
                            "cwd": ts["rel_cwd"], "tree": ts["tree"], "env": env_fingerprint()},
                           sort_keys=True))


def source_file_identity(ts: dict) -> str | None:
    """Detect a tracked file rewritten and restored while the command runs.

    Only tracked files are fingerprinted. Directory mtimes are not (M-01): a test that creates and deletes a temporary
    file changes its directory's mtime, which made every full tests/dev_workflow gate "source changed" (measured
    2026-10-23: only the mtime of tests/dev_workflow changed). Untracked files still present at the end are caught by the
    final git status; an untracked file created and removed during the run is not detected (documented limit)."""
    if not ts["repo"] or ts["dirty"] is not False:
        return None
    rc, names = _git(Path(ts["repo"]), "ls-files", "-z")
    if rc:
        return None
    digest = hashlib.sha256()
    try:
        for name in names.split("\0"):
            if not name:
                continue
            st = (Path(ts["repo"]) / name).lstat()
            digest.update(json.dumps([name, st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns],
                                     separators=(",", ":")).encode("utf-8"))
    except OSError:
        return None
    return digest.hexdigest()


def lock_name(mode: str, argv: list[str], cwd: Path) -> str | None:
    if mode == "none":
        return None
    if mode == "auto":
        return "auto-" + _sha(json.dumps([argv, os.path.normcase(os.path.realpath(cwd))]))[:24]
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", mode):
        raise RunError("USAGE", f"lock class must match [A-Za-z0-9_.-]{{1,64}}; got {mode!r}")
    return "class-" + mode


def classify_env(log: Path) -> list[str]:
    try:
        with log.open("rb") as f:
            f.seek(max(0, log.stat().st_size - ENV_TAIL_BYTES))
            tail = f.read().decode("utf-8", "replace")
    except OSError:
        return []
    found = []
    for label, rx in ENV_PATTERNS:
        for m in rx.finditer(tail):
            tag = f"{label}:{m.group(1)}" if label == "ENV_MISSING_MODULE" else label
            if tag not in found:
                found.append(tag)
    return found


# --------------------------------------------------------------------------- process identity

def _proc_ctime(pid) -> float | None:
    """Creation time of ``pid`` or None if it does not exist. A pid alone is not an identity (pids are reused)."""
    if not pid:
        return None
    try:
        import psutil
    except ImportError:      # psutil is declared in requirements.txt; without it liveness cannot be proven
        return None
    try:
        return psutil.Process(int(pid)).create_time()
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError, OSError):
        return None


def _alive(pid, ctime) -> bool:
    now = _proc_ctime(pid)
    return now is not None and ctime is not None and abs(now - float(ctime)) < 1.0


# --------------------------------------------------------------------------- run records

def _write(run_dir: Path, rec: dict) -> None:
    atomic_write_bytes(run_dir / "run.json", (json.dumps(rec, indent=1, sort_keys=True) + "\n").encode("utf-8"))


def _load(run_dir: Path) -> dict | None:
    try:
        rec = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
        if isinstance(rec.get("argv"), list) and all(isinstance(arg, str) for arg in rec["argv"]):
            rec["argv"] = _safe_argv(rec["argv"])
        return rec
    except (OSError, ValueError):
        return None


def all_runs(root: Path) -> list[dict]:
    out = []
    if root.is_dir():
        for d in sorted(root.iterdir()):
            rec = _load(d) if d.is_dir() else None
            if rec and rec.get("id") == d.name:
                out.append(rec)
    return out


def find_run(root: Path, ident: str) -> Path | None:
    """Resolve a run id exactly. Name lookup is a separate status-only operation."""
    if re.fullmatch(r"[A-Za-z0-9_.-]+", ident or "") and (root / ident / "run.json").is_file():
        return root / ident
    return None


def find_latest_named_run(root: Path, name: str) -> Path | None:
    """Explicit convenience lookup for status, never for wait."""
    named = [r for r in all_runs(root) if r.get("name") == name]
    return root / max(named, key=lambda r: r["started_at"])["id"] if named else None


def status(root: Path, ident: str) -> dict:
    d = find_run(root, ident) or find_latest_named_run(root, ident)
    if d is None:
        return {"id": ident, "state": "NOT_FOUND"}
    rec = _load(d)
    if rec is None or rec.get("id") != d.name:
        return {"id": ident, "state": "MISSING_MARKER", "why": "run.json unreadable or run id mismatch"}
    out = {k: rec.get(k) for k in ("id", "name", "argv", "cwd", "head", "started_at", "ended_at", "exit_code",
                                   "duration_s", "log", "log_sha256", "env_failures", "reused_from", "lock",
                                   "contained")}
    if rec.get("final"):
        out["state"] = rec["state"]
        return out
    if _alive(rec.get("supervisor_pid"), rec.get("supervisor_ctime")):
        # Idle time comes from the supervisor's heartbeat (it measures log growth through its own handle); NTFS may
        # update the mtime of a file that is still open only lazily, so the file's mtime is not used.
        if rec.get("heartbeat_at"):
            idle = float(rec.get("idle_s") or 0.0) + max(0.0, time.time() - _ts(rec["heartbeat_at"]))
        else:
            idle = max(0.0, time.time() - _ts(rec["started_at"]))
        stall = rec.get("stall_s")
        out["idle_s"] = round(idle, 1)
        out["state"] = "STALLED" if stall and idle > stall else "RUNNING"
        return out
    out["state"] = "MISSING_MARKER"
    out["why"] = "supervisor is gone and no final record was written (crash, kill or reboot)"
    out["child_alive"] = _alive(rec.get("child_pid"), rec.get("child_ctime"))
    return out


def _ts(iso: str) -> float:
    return datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%S.%fZ").replace(
        tzinfo=datetime.timezone.utc).timestamp()


def wait(root: Path, ident: str, timeout_s: float, poll_s: float = 2.0) -> dict:
    if not 0 < timeout_s <= MAX_TIMEOUT_S:
        raise RunError("USAGE", f"--timeout must be in (0, {MAX_TIMEOUT_S:.0f}] seconds")
    deadline = time.monotonic() + timeout_s
    while True:
        d = find_run(root, ident)
        st = status(root, d.name) if d else {"id": ident, "state": "NOT_FOUND"}
        if st["state"] not in ("RUNNING", "STALLED"):
            return st
        if time.monotonic() >= deadline:
            return {**st, "state": "WAIT_TIMEOUT", "run_state": st["state"]}
        time.sleep(min(poll_s, max(0.05, deadline - time.monotonic())))


def _find_reusable(root: Path, key: str) -> dict | None:
    for rec in sorted(all_runs(root), key=lambda r: r["started_at"], reverse=True):
        if (rec.get("reuse_key") != key or rec.get("source_stable") is not True or
                not rec.get("final") or rec.get("state") not in ("COMPLETED", "FAILED")):
            continue
        if rec.get("reused_from"):
            continue
        log = Path(rec.get("log") or "")
        try:
            if log.is_file() and file_sha256(log) == rec.get("log_sha256"):
                return rec
        except OSError:
            continue
    return None


def _record_ledger(rec: dict, task: str, actor: str, ledger_path: str | None) -> dict:
    if rec["state"] not in ("COMPLETED", "FAILED"):
        return {"recorded": False, "why": f"state {rec['state']} is not a test result"}
    if rec.get("dirty") is not False or not rec.get("head") or rec.get("source_changed"):
        return {"recorded": False, "why": "tree not clean (or not git): a result cannot be bound to a commit"}
    from scripts.dev_workflow.task_ledger import Ledger, LedgerError
    try:
        lg = Ledger(ledger_path)
        try:
            summary = f"testrun {rec['id']} {rec['name']}: {rec['state']} exit {rec['exit_code']}"
            if rec.get("env_failures"):
                summary += " env " + ",".join(rec["env_failures"])
            lg.record_test(task, actor, rec["head"], rec["exit_code"] == 0, summary, rec["log"])
        finally:
            lg.close()
    except (LedgerError, OSError) as e:
        return {"recorded": False, "why": str(e)}
    return {"recorded": True, "task": task}


def start(argv: list[str], *, name: str, timeout_s: float, cwd: str | None = None, stall_s: float | None = None,
          kill_on_stall: bool = False, lock: str = "auto", reuse: bool = False, task: str | None = None,
          actor: str | None = None, root: Path | None = None, ledger: str | None = None,
          heartbeat_s: float = HEARTBEAT_S) -> dict:
    if not argv:
        raise RunError("USAGE", "no command given (put it after --)")
    if not 0 < timeout_s <= MAX_TIMEOUT_S:
        raise RunError("USAGE", f"--timeout must be in (0, {MAX_TIMEOUT_S:.0f}] seconds")
    if stall_s is not None and stall_s <= 0:
        raise RunError("USAGE", "--stall must be positive")
    if bool(task) != bool(actor):
        raise RunError("USAGE", "--task and --actor go together")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", name or ""):
        raise RunError("USAGE", "--name must match [A-Za-z0-9_.-]{1,64}")
    root = root or runs_dir()
    wd = Path(cwd or os.getcwd()).resolve()
    ts = tree_state(wd)
    key = reuse_key(argv, ts)
    if reuse and key:
        # Revalidate the source and inherited environment immediately before selecting evidence.
        prev = _find_reusable(root, key) if reuse_key(argv, tree_state(wd)) == key else None
        if prev is not None:
            return {**{k: prev.get(k) for k in ("exit_code", "log", "log_sha256", "head", "env_failures")},
                    "id": prev["id"], "name": name, "state": "REUSED", "reused_state": prev["state"],
                    "reused_from": prev["id"]}
    lname = lock_name(lock, argv, wd)
    root.mkdir(parents=True, exist_ok=True)
    if lname is None:
        return _run(argv, name, timeout_s, wd, ts, key, stall_s, kill_on_stall, None, task, actor, root, ledger,
                    heartbeat_s)
    try:
        with os_lock(root / "locks" / f"{lname}.lock", timeout=LOCK_WAIT_S):
            return _run(argv, name, timeout_s, wd, ts, key, stall_s, kill_on_stall, lname, task, actor, root,
                        ledger, heartbeat_s)
    except StoreError as e:
        if e.code != "LOCK_TIMEOUT":
            raise
        active = [r["id"] for r in all_runs(root) if r.get("lock") == lname and not r.get("final")
                  and _alive(r.get("supervisor_pid"), r.get("supervisor_ctime"))]
        return {"state": "DUPLICATE_RUN", "name": name, "lock": lname, "active_runs": active}


def _run(argv, name, timeout_s, wd, ts, key, stall_s, kill_on_stall, lname, task, actor, root, ledger,
         heartbeat_s) -> dict:
    # The queue/lock may have waited while another process changed the checkout.
    entry = tree_state(wd)
    if reuse_key(argv, entry) != key:
        key = None
    ts = entry
    source_identity = source_file_identity(entry) if key else None
    if source_identity is None:
        key = None
    run_id = f"{name}-{datetime.datetime.now(datetime.timezone.utc):%Y%m%dT%H%M%SZ}-{secrets.token_hex(3)}"
    d = root / run_id
    d.mkdir(parents=True)
    log = d / "output.log"
    me = os.getpid()
    rec = {"schema": "uri-testrun/1", "id": run_id, "name": name,
           "argv": _safe_argv(argv), "cwd": str(wd),
           "repo": ts["repo"], "head": ts["head"], "tree": ts["tree"], "dirty": ts["dirty"], "reuse_key": key,
           "env": env_fingerprint(), "lock": lname, "timeout_s": timeout_s, "stall_s": stall_s,
           "kill_on_stall": kill_on_stall, "started_at": utcnow(), "supervisor_pid": me,
           "supervisor_ctime": _proc_ctime(me), "child_pid": None, "child_ctime": None, "state": "RUNNING",
           "final": False, "log": str(log), "task": task}
    _write(d, rec)
    t0 = time.monotonic()
    state, rc, contained = None, None, None
    with log.open("wb") as logf:
        try:
            proc = containment.spawn(argv, cwd=str(wd), stdout=logf, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL)
        except OSError as e:
            safe_error = redact(str(e))[0]
            logf.write(f"[testrun] launch failed: {safe_error}\n".encode("utf-8", "replace"))
            state, rc = "FAILED", None
            rec["launch_error"] = safe_error
            proc = None
        if proc is not None:
            if containment.WINDOWS and getattr(proc, "_uri_job", None) is None:
                containment.kill_tree(proc)
                proc.wait()
                contained = containment.finish(proc)
                rec["containment_error"] = "Windows Job Object assignment unavailable"
                state, rc = "CONTAINMENT_FAILED", None
                proc = None
        if proc is not None:
            rec.update(child_pid=proc.pid, child_ctime=_proc_ctime(proc.pid))
            _write(d, rec)
            last_size, last_out, next_beat = 0, time.monotonic(), 0.0
            try:
                while True:
                    rc = proc.poll()
                    if rc is not None:
                        state = "COMPLETED" if rc == 0 else "FAILED"
                        break
                    now = time.monotonic()
                    size = log.stat().st_size
                    if size != last_size:
                        last_size, last_out = size, now
                    idle = now - last_out
                    if now - t0 > timeout_s:
                        containment.kill_tree(proc)
                        proc.wait()
                        state, rc = "TIMED_OUT", proc.returncode
                        break
                    if stall_s and idle > stall_s and kill_on_stall:
                        containment.kill_tree(proc)
                        proc.wait()
                        state, rc = "STALLED_KILLED", proc.returncode
                        break
                    if now >= next_beat:
                        rec.update(state="STALLED" if stall_s and idle > stall_s else "RUNNING",
                                   heartbeat_at=utcnow(), idle_s=round(idle, 1), log_bytes=size)
                        _write(d, rec)
                        next_beat = now + heartbeat_s
                    time.sleep(POLL_S)
            except KeyboardInterrupt:
                containment.kill_tree(proc)
                proc.wait()
                state, rc = "INTERRUPTED", proc.returncode
            contained = containment.finish(proc)
            if containment.WINDOWS and not contained.get("contained"):
                state, rc = "CONTAINMENT_FAILED", None
    final_tree = tree_state(wd) if key else None
    if key and (reuse_key(argv, final_tree) != key or source_file_identity(final_tree) != source_identity):
        key = None
        rec["source_changed"] = True
    rec["reuse_key"] = key
    rec["source_stable"] = bool(key) and state in ("COMPLETED", "FAILED")
    rec.update(state=state, final=True, exit_code=rc, ended_at=utcnow(),
               duration_s=round(time.monotonic() - t0, 3), log_sha256=file_sha256(log), contained=contained,
               env_failures=classify_env(log) if state != "COMPLETED" else [])
    rec.pop("idle_s", None)
    if task:
        rec["ledger"] = _record_ledger(rec, task, actor, ledger)
    _write(d, rec)
    return rec


def exit_code_for(rec: dict) -> int:
    st = rec["state"]
    if st in ("COMPLETED", "FAILED", "REUSED"):
        rc = rec.get("exit_code")
        return rc if isinstance(rc, int) else 127
    return EXIT.get(st, 1)


# --------------------------------------------------------------------------- advisory test selection

def _module_of(path: str) -> str | None:
    if not path.endswith(".py"):
        return None
    mod = path[:-3].replace("/", ".")
    return mod[: -len(".__init__")] if mod.endswith(".__init__") else mod


def select_tests(repo: Path, base: str, head: str | None = None) -> dict:
    """Advisory: tests that import a changed module (or are changed). Never a substitute for mandatory gates."""
    args = ["diff", "--name-only", base] + ([head] if head else [])
    rc, out = _git(repo, *args)
    if rc:
        raise RunError("USAGE", f"git diff failed: {out}")
    changed = [p for p in out.splitlines() if p]
    mods = {m for m in (_module_of(p) for p in changed) if m}
    tests = sorted({p.relative_to(repo).as_posix() for p in list((repo / "tests").rglob("test_*.py"))
                    + list(repo.glob("test_*.py"))} if (repo / "tests").is_dir() else
                   {p.name for p in repo.glob("test_*.py")})
    imp = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", re.M)
    selected, reasons = [], {}
    for t in tests:
        if t in changed:
            selected.append(t)
            reasons[t] = "test file changed"
            continue
        try:
            text = (repo / t).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        hits = set()
        for m in imp.finditer(text):
            name = m.group(1) or m.group(2)
            for cm in mods:
                if name == cm or name.startswith(cm + ".") or cm.startswith(name + "."):
                    hits.add(cm)
        if hits:
            selected.append(t)
            reasons[t] = "imports " + ", ".join(sorted(hits))
    unmapped = [p for p in changed if not p.endswith(".py")]
    return {"base": base, "head": head or "WORKTREE", "changed": changed, "selected": selected, "reasons": reasons,
            "unmapped_changes": unmapped,
            "rule": "advisory only: mandatory lifecycle gates still run in full; non-Python changes are unmapped"}


# --------------------------------------------------------------------------- CLI

def _out(obj) -> None:
    sys.stdout.write(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):   # a Windows pipe defaults to the ANSI code page
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd_argv: list[str] = []
    if "--" in argv:
        i = argv.index("--")
        argv, cmd_argv = argv[:i], argv[i + 1:]
    ap = argparse.ArgumentParser(prog="testrun", description=__doc__.split("\n\n")[0])
    ap.add_argument("--runs", help="runs directory (default $URI_DEV_RUNS or ~/.uri-dev/runs)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start")
    p.add_argument("--name", required=True)
    p.add_argument("--timeout", type=float, required=True, help="seconds; mandatory, the tree is killed after it")
    p.add_argument("--stall", type=float, help="seconds without new output that count as a stall")
    p.add_argument("--kill-on-stall", action="store_true")
    p.add_argument("--cwd")
    p.add_argument("--lock", default="auto", help="auto (same command+cwd), none, or a class name")
    p.add_argument("--reuse", action="store_true", help="reuse a final result of the identical clean tree")
    p.add_argument("--task"); p.add_argument("--actor"); p.add_argument("--ledger")
    p = sub.add_parser("status"); p.add_argument("run")
    p = sub.add_parser("wait"); p.add_argument("run"); p.add_argument("--timeout", type=float, required=True)
    p.add_argument("--poll", type=float, default=2.0)
    sub.add_parser("list")
    p = sub.add_parser("select"); p.add_argument("--base", required=True); p.add_argument("--head")
    p.add_argument("--repo", default=".")
    a = ap.parse_args(argv)
    root = runs_dir(a.runs)
    try:
        if a.cmd == "start":
            rec = start(cmd_argv, name=a.name, timeout_s=a.timeout, cwd=a.cwd, stall_s=a.stall,
                        kill_on_stall=a.kill_on_stall, lock=a.lock, reuse=a.reuse, task=a.task, actor=a.actor,
                        root=root, ledger=a.ledger)
            _out(rec)
            return exit_code_for(rec)
        if a.cmd == "status":
            st = status(root, a.run)
            _out(st)
            return EXIT["NOT_FOUND"] if st["state"] == "NOT_FOUND" else 0
        if a.cmd == "wait":
            st = wait(root, a.run, a.timeout, a.poll)
            _out(st)
            if st["state"] in ("COMPLETED", "FAILED"):
                return exit_code_for(st)
            return EXIT.get(st["state"], 1)
        if a.cmd == "list":
            _out([{k: r.get(k) for k in ("id", "name", "state", "final", "exit_code", "started_at", "head")}
                  for r in all_runs(root)])
            return 0
        if a.cmd == "select":
            _out(select_tests(Path(a.repo).resolve(), a.base, a.head))
            return 0
    except RunError as e:
        sys.stderr.write(f"ERROR {e.code}: {e}\n")
        return EXIT.get(e.code, 2)
    return 2


if __name__ == "__main__":
    sys.exit(main())
