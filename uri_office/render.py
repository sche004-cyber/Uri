"""LibreOffice engine manager (plan §5 `render.py`; A1 §A3 XLSX rules; spikes S1, S3, S4, S6, S7).

One persistent headless LibreOffice listener on a random named pipe, inside a Job Object, with a private profile
under `<state>/lo-profile/` that is re-seeded with the hardened settings at every start, and `TMP`/`TEMP` pointed at
`<state>/lo-tmp/` (emptied after each job and at shutdown). A UNO bridge (`workers/lo_bridge.py`, LibreOffice's own
python.exe under `-I`, hash-checked run copy) does the conversions.

* Integrity: `EngineIntegrity.launch_check()` before every start, including a restart after idle shutdown.
* One queue, two priorities: previews before conversions. A queued job is dropped when its owner (document or
  workflow) closes.
* Timeouts: 90 s to start, 60 s per conversion. After a crash or timeout the engine restarts once for that job.
* Idle: no queued or running job. After `idle_seconds` (600) the engine stops; the next job starts it again.
"""
from __future__ import annotations

import heapq
import itertools
import os
import shutil
import threading
import time
import uuid
from concurrent.futures import Future
from pathlib import Path

from . import engines as E
from . import jobobject as J
from .errors import OfficeError
from .workerproc import Worker, WorkerFailed

PREVIEW, CONVERT = 0, 1
START_TIMEOUT = 90.0
CONVERT_TIMEOUT = 60.0
IDLE_SECONDS = 600.0
SOFFICE_MEMORY = 3 * 2**30          # per process; LibreOffice on a 60-page document peaked at ~410 MB (2026-10-15)
BRIDGE_MEMORY = 512 * 2**20

# Hardened profile (lo_qualify 2026-10-15, plus plan F8 and A1-M3 settings). Values checked against the engine's own
# main.xcd/onlineupdate.xcd schema on 2026-10-15:
#   Writer Content/Update/Link: 0 always, 1 on request, 2 never.  Calc Content/Update/Link: 0 always, 1 never,
#   2 on request.  Calc Formula/Load *RecalcMode: 0 always, 1 never, 2 prompt.
HARDENED_XCU = """<?xml version="1.0" encoding="UTF-8"?>
<oor:items xmlns:oor="http://openoffice.org/2001/registry" xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="DisableMacrosExecution" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="BlockUntrustedRefererLinks" oor:op="fuse"><value>true</value></prop></item>
<item oor:path="/org.openoffice.Inet/Settings"><prop oor:name="ooInetProxyType" oor:op="fuse"><value>2</value></prop></item>
<item oor:path="/org.openoffice.Inet/Settings"><prop oor:name="ooInetHTTPProxyName" oor:op="fuse"><value>127.0.0.1</value></prop></item>
<item oor:path="/org.openoffice.Inet/Settings"><prop oor:name="ooInetHTTPProxyPort" oor:op="fuse"><value>9</value></prop></item>
<item oor:path="/org.openoffice.Inet/Settings"><prop oor:name="ooInetHTTPSProxyName" oor:op="fuse"><value>127.0.0.1</value></prop></item>
<item oor:path="/org.openoffice.Inet/Settings"><prop oor:name="ooInetHTTPSProxyPort" oor:op="fuse"><value>9</value></prop></item>
<item oor:path="/org.openoffice.Inet/Settings"><prop oor:name="ooInetFTPProxyName" oor:op="fuse"><value>127.0.0.1</value></prop></item>
<item oor:path="/org.openoffice.Inet/Settings"><prop oor:name="ooInetFTPProxyPort" oor:op="fuse"><value>9</value></prop></item>
<item oor:path="/org.openoffice.Inet/Settings"><prop oor:name="ooInetNoProxy" oor:op="fuse"><value></value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="UseOpenCL" oor:op="fuse"><value>false</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="CollectUsageInformation" oor:op="fuse"><value>false</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="CrashReport" oor:op="fuse"><value>false</value></prop></item>
<item oor:path="/org.openoffice.Office.Common/Misc"><prop oor:name="ShowTipOfTheDay" oor:op="fuse"><value>false</value></prop></item>
<item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>2</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>1</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="OOXMLRecalcMode" oor:op="fuse"><value>1</value></prop></item>
<item oor:path="/org.openoffice.Office.Calc/Formula/Load"><prop oor:name="ODFRecalcMode" oor:op="fuse"><value>1</value></prop></item>
<item oor:path="/org.openoffice.Office.Jobs/Jobs/org.openoffice.Office.Jobs:Job['UpdateCheck']/Arguments"><prop oor:name="AutoCheckEnabled" oor:op="fuse"><value>false</value></prop></item>
</oor:items>
"""


class _Job:
    __slots__ = ("prio", "seq", "owner", "src", "dst", "future", "cancelled")

    def __init__(self, prio, seq, owner, src, dst):
        self.prio, self.seq, self.owner, self.src, self.dst = prio, seq, owner, src, dst
        self.future: Future = Future()
        self.cancelled = False

    def __lt__(self, other):
        return (self.prio, self.seq) < (other.prio, other.seq)


class LibreOffice:
    def __init__(self, state: Path, integrity: E.EngineIntegrity | None = None, *, idle_seconds=IDLE_SECONDS,
                 convert_timeout=CONVERT_TIMEOUT):
        self.state = Path(state)
        self.integrity = integrity or E.EngineIntegrity("libreoffice", self.state)
        self.profile = self.state / "lo-profile"
        self.tmp = self.state / "lo-tmp"
        self.work_root = self.state / "files"
        self.work_root.mkdir(parents=True, exist_ok=True)
        self.idle_seconds, self.convert_timeout = idle_seconds, convert_timeout
        self._cv = threading.Condition()
        self._heap: list = []
        self._seq = itertools.count()
        self._busy = False
        self._last_activity = time.monotonic()
        self._soffice = None
        self._job: J.Job | None = None
        self._bridge: Worker | None = None
        self._stopped = False
        self.starts = 0
        self.last_start_seconds: float | None = None
        self.last_error: str | None = None
        self.tmp_after_job: dict | None = None
        threading.Thread(target=self._loop, daemon=True, name="lo-queue").start()

    # ---- public --------------------------------------------------------------------------------------------------
    def submit(self, src: Path, dst: Path, *, owner: str, priority: int = CONVERT) -> Future:
        """Queue a conversion of `src` (inside the work root) to the PDF `dst`. Returns a Future of
        {"seconds", "restarted"}; it raises OfficeError on failure."""
        for p in (src, dst.parent):
            if not _inside(Path(p), self.work_root):
                raise OfficeError("PATH_REFUSED", "engine paths must be inside the work folder", 400)
        job = _Job(priority, next(self._seq), owner, Path(src), Path(dst))
        with self._cv:
            heapq.heappush(self._heap, job)
            self._cv.notify_all()
        return job.future

    def cancel_owner(self, owner: str) -> int:
        """Drop every queued job of `owner` (its document or workflow closed). Returns how many were dropped."""
        n = 0
        with self._cv:
            for j in self._heap:
                if j.owner == owner and not j.cancelled:
                    j.cancelled = True
                    j.future.set_exception(OfficeError("CANCELLED", "", 409))
                    n += 1
        return n

    def status(self) -> dict:
        st = self.integrity.status()
        if self._running():
            st["state"] = "running"
        elif self.starts and st["state"] == "ready":
            st["state"] = "idle_stopped"
        st.update({"queued": len([j for j in self._heap if not j.cancelled]), "busy": self._busy,
                   "starts": self.starts, "last_start_seconds": self.last_start_seconds,
                   "last_error": self.last_error})
        st["pids"] = self.pids()
        return st

    def pids(self) -> list:
        out = []
        if self._soffice is not None and self._soffice.poll() is None:
            out.append(self._soffice.pid)
        if self._bridge is not None and self._bridge.pid():
            out.append(self._bridge.pid())
        return out

    def shutdown(self):
        with self._cv:
            self._stopped = True
            for j in self._heap:
                if not j.cancelled:
                    j.cancelled = True
                    j.future.set_exception(OfficeError("CANCELLED", "", 409))
            self._heap.clear()
            self._cv.notify_all()
        self._stop_engine()

    # ---- engine lifecycle ------------------------------------------------------------------------------------------
    def _running(self) -> bool:
        return self._soffice is not None and self._soffice.poll() is None and self._bridge is not None \
            and self._bridge.running

    def _seed_profile(self):
        user = self.profile / "user"
        user.mkdir(parents=True, exist_ok=True)
        (user / "registrymodifications.xcu").write_text(HARDENED_XCU, encoding="utf-8")
        for name in ("crash", "extensions", "uno_packages"):
            shutil.rmtree(user / name, ignore_errors=True)

    def _empty_tmp(self):
        if self.tmp.exists():
            for p in self.tmp.iterdir():
                if p.is_dir() and not p.is_symlink():
                    shutil.rmtree(p, ignore_errors=True)
                else:
                    try:
                        p.unlink()
                    except OSError:
                        pass
        self.tmp.mkdir(parents=True, exist_ok=True)

    def _env(self) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("PYTHON", "URE_", "UNO_"))}
        env["TMP"] = env["TEMP"] = str(self.tmp)
        for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
            env.pop(k, None)
        return env

    def _start_engine(self):
        if os.name != "nt":
            raise OfficeError("ENGINE_UNAVAILABLE", "the document engine runs on Windows only", 503)
        t0 = time.perf_counter()
        self.integrity.launch_check()               # raises ENGINE_MISSING / ENGINE_INTEGRITY / ENGINE_UNAVAILABLE
        self._seed_profile()
        self._empty_tmp()
        program = self.integrity.root / "program"
        pipe = f"uri_office_{uuid.uuid4().hex}"
        env = self._env()
        self._job = J.Job(memory_limit=SOFFICE_MEMORY)
        import subprocess
        self._soffice = J.spawn([str(program / "soffice.com"), f"-env:UserInstallation={self.profile.as_uri()}",
                                 "--headless", "--invisible", "--norestore", "--nolockcheck", "--nodefault",
                                 "--nologo", "--nofirststartwizard",
                                 f"--accept=pipe,name={pipe};urp;StarOffice.ComponentContext"],
                                self._job, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, env=env, cwd=str(self.tmp))

        def bridge_args():
            copy = E.run_copy("lo_bridge.py", self.state)
            return [str(program / "python.exe"), "-I", str(copy), pipe, str(self.work_root)], copy.unlink

        self._bridge = Worker("lo_bridge", bridge_args, memory_limit=BRIDGE_MEMORY, start_timeout=START_TIMEOUT,
                              env=env, cwd=str(self.tmp))
        try:
            self._bridge.request("ping", timeout=START_TIMEOUT)
        except WorkerFailed as e:
            self._stop_engine()
            raise OfficeError("ENGINE_START_FAILED", e.code, 503) from None
        self.starts += 1
        self.last_start_seconds = round(time.perf_counter() - t0, 2)

    def _stop_engine(self):
        b, self._bridge = self._bridge, None
        if b is not None:
            b.stop()
        job, self._job = self._job, None
        if job is not None:
            job.close()
        p, self._soffice = self._soffice, None
        if p is not None:
            try:
                p.wait(10)
            except Exception:  # noqa: BLE001
                p.kill()
        self._empty_tmp()

    # ---- queue ---------------------------------------------------------------------------------------------------
    def _next(self):
        with self._cv:
            while True:
                if self._stopped:
                    return None
                while self._heap and self._heap[0].cancelled:
                    heapq.heappop(self._heap)
                if self._heap:
                    self._busy = True
                    return heapq.heappop(self._heap)
                idle_for = time.monotonic() - self._last_activity
                if self._soffice is not None and idle_for >= self.idle_seconds:
                    self._cv.release()
                    try:
                        self._stop_engine()
                    finally:
                        self._cv.acquire()
                    continue
                self._cv.wait(timeout=max(0.5, min(30.0, self.idle_seconds - idle_for)))

    def _loop(self):
        while True:
            job = self._next()
            if job is None:
                return
            try:
                if not job.future.set_running_or_notify_cancel():
                    continue
                job.future.set_result(self._run(job))
            except OfficeError as e:
                self.last_error = e.code
                job.future.set_exception(e)
            except Exception as e:  # noqa: BLE001
                self.last_error = type(e).__name__
                job.future.set_exception(OfficeError("ENGINE_CRASHED", type(e).__name__, 503))
            finally:
                with self._cv:
                    self._busy = False
                    self._last_activity = time.monotonic()
                self.tmp_after_job = _tree_summary(self.tmp)

    def _empty_tmp_files(self):
        try:
            self._empty_tmp()
        except OSError:
            pass

    def _run(self, job: _Job) -> dict:
        restarted = False
        for attempt in (1, 2):
            if not self._running():
                self._stop_engine()
                self._start_engine()
            try:
                r = self._bridge.request("convert", timeout=self.convert_timeout, **{"in": str(job.src),
                                                                                    "out": str(job.dst)})
            except WorkerFailed as e:
                self._stop_engine()
                if attempt == 1:
                    restarted = True
                    continue
                raise OfficeError("ENGINE_TIMEOUT" if e.code == "TIMEOUT" else "ENGINE_CRASHED", e.code,
                                  503) from None
            if r.get("ok"):
                if not job.dst.is_file():
                    raise OfficeError("ENGINE_CRASHED", "no output", 503)
                return {"seconds": r.get("seconds"), "restarted": restarted}
            if r.get("error") == "PATH_REFUSED":
                raise OfficeError("PATH_REFUSED", "engine path refused", 400)
            # The engine answered but could not load or export: a document problem, not an engine crash.
            if self._soffice is None or self._soffice.poll() is not None:
                self._stop_engine()
                if attempt == 1:
                    restarted = True
                    continue
            raise OfficeError("PREVIEW_UNAVAILABLE", r.get("detail", "convert failed"), 422)
        raise OfficeError("ENGINE_CRASHED", "", 503)


def _tree_summary(root: Path) -> dict:
    """Files left in the engine's temp folder after a job (count and bytes; no names or content)."""
    n = size = 0
    if root.exists():
        for dirpath, _, files in os.walk(root):
            for f in files:
                n += 1
                try:
                    size += os.path.getsize(os.path.join(dirpath, f))
                except OSError:
                    pass
    return {"files": n, "bytes": size}


def _inside(p: Path, root: Path) -> bool:
    a = os.path.normcase(os.path.realpath(p))
    b = os.path.normcase(os.path.realpath(root))
    try:
        return os.path.commonpath([a, b]) == b
    except ValueError:
        return False
