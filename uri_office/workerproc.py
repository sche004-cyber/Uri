"""A JSON-lines worker process inside its own Job Object (plan §5, A1 §A3, AC-O2-20).

The worker prints one `{"ready": true}` line, then answers one JSON line per request. The client:
* starts the worker suspended, puts it in a Job Object with a memory limit, then resumes it (`jobobject.spawn`);
* sends one request at a time (a lock), waits up to `timeout` seconds for the answer on a reader thread;
* on a timeout, a crash, a broken pipe or a non-JSON answer, closes the job (which kills the worker and anything it
  started) and raises `WorkerFailed`; the next request starts a fresh worker.
The service process never parses untrusted documents itself; only these workers do.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
import uuid

from . import jobobject as J


class WorkerFailed(Exception):
    def __init__(self, code: str, detail: str = ""):
        self.code, self.detail = code, detail
        super().__init__(f"{code}: {detail}")


class Worker:
    def __init__(self, name: str, make_args, *, memory_limit: int, start_timeout: float = 30.0,
                 env: dict | None = None, cwd: str | None = None, on_exit=None):
        """`make_args()` returns the argument list for a fresh start (it may write a run copy of a script and return
        a cleanup callable as the second item)."""
        self.name = name
        self._make_args = make_args
        self.memory_limit = memory_limit
        self.start_timeout = start_timeout
        self.env, self.cwd = env, cwd
        self._lock = threading.RLock()
        self._p = None
        self._job = None
        self._q: queue.Queue | None = None
        self._cleanup = None
        self.starts = 0
        self.last_used = 0.0
        self.peak_memory: int | None = None
        self._on_exit = on_exit

    @property
    def running(self) -> bool:
        return self._p is not None and self._p.poll() is None

    def pid(self) -> int | None:
        return self._p.pid if self.running else None

    def _reader(self, p, q):
        try:
            for line in p.stdout:
                q.put(line)
        finally:
            q.put(None)

    def _start(self, start_timeout: float | None = None):
        made = self._make_args()
        args, self._cleanup = (made if isinstance(made, tuple) else (made, None))
        self._job = J.Job(memory_limit=self.memory_limit)
        try:
            self._p = J.spawn(args, self._job, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", bufsize=1,
                              env=self.env, cwd=self.cwd)
        except BaseException:
            self._job.close()
            self._job = None
            if self._cleanup:
                try:
                    self._cleanup()
                except OSError:
                    pass
                self._cleanup = None
            raise
        self._q = queue.Queue()
        threading.Thread(target=self._reader, args=(self._p, self._q), daemon=True,
                         name=f"{self.name}-reader").start()
        self.starts += 1
        first = self._get(self.start_timeout if start_timeout is None else min(self.start_timeout, start_timeout))
        if not first.get("ok") or not first.get("ready"):
            code = first.get("error") or "WORKER_START_FAILED"
            self.stop()
            raise WorkerFailed(code, "worker did not become ready")

    def _get(self, timeout: float) -> dict:
        try:
            line = self._q.get(timeout=timeout)
        except queue.Empty:
            self.stop()
            raise WorkerFailed("TIMEOUT", f"{self.name} did not answer in {timeout:.0f} s") from None
        if line is None:
            self.stop()
            raise WorkerFailed("CRASHED", f"{self.name} stopped")
        try:
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError
            return obj
        except ValueError:
            self.stop()
            raise WorkerFailed("PROTOCOL", f"{self.name} sent an unreadable answer") from None

    def request(self, op: str, timeout: float = 60.0, total_timeout: bool = False, **fields) -> dict:
        """`timeout` bounds the wait for the answer. With `total_timeout` (FB4 R5-06) it bounds the whole call:
        waiting for another request on this worker (the lock), starting the worker and the answer; a lock that does
        not come free in time is `BUSY`."""
        t0 = time.monotonic()
        if total_timeout:
            if not self._lock.acquire(timeout=max(0.0, timeout)):
                raise WorkerFailed("BUSY", f"{self.name} was busy for {timeout:.0f} s")
        else:
            self._lock.acquire()
        try:
            return self._request(op, timeout, t0 if total_timeout else None, fields)
        finally:
            self._lock.release()

    def _request(self, op, timeout, t0, fields) -> dict:
        if not self.running:
            self._start(None if t0 is None else max(0.01, t0 + timeout - time.monotonic()))
        rid = uuid.uuid4().hex[:12]
        try:
            self._p.stdin.write(json.dumps({"id": rid, "op": op, **fields}) + "\n")
            self._p.stdin.flush()
        except OSError:
            self.stop()
            raise WorkerFailed("CRASHED", f"{self.name} stopped") from None
        deadline = (t0 if t0 is not None else time.monotonic()) + timeout
        while True:
            obj = self._get(max(0.01, deadline - time.monotonic()))
            if obj.get("id") == rid:
                self.last_used = time.monotonic()
                if self._job is not None:
                    self.peak_memory = self._job.peak_process_memory()
                return obj

    def stop(self):
        with self._lock:
            p, job, self._p, self._job = self._p, self._job, None, None
            if p is not None and p.poll() is None:
                try:
                    p.stdin.write(json.dumps({"id": None, "op": "quit"}) + "\n")
                    p.stdin.flush()
                    p.wait(2)
                except (OSError, subprocess.TimeoutExpired, ValueError):
                    pass
            if job is not None:
                job.close()
            if p is not None:
                try:
                    p.wait(5)
                except subprocess.TimeoutExpired:
                    p.kill()
                for s in (p.stdin, p.stdout):
                    try:
                        s.close()
                    except (OSError, ValueError):
                        pass
            if self._cleanup:
                try:
                    self._cleanup()
                except OSError:
                    pass
                self._cleanup = None
            if self._on_exit:
                self._on_exit(self)


def python_exe() -> str:
    """The interpreter that runs the service also runs the pypdf worker (it has pypdf installed)."""
    import sys
    return sys.executable


def powershell_exe() -> str:
    root = os.environ.get("SystemRoot", r"C:\Windows")
    return os.path.join(root, "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
