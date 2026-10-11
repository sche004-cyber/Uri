"""Process containment for lifecycle workers and gate commands (DEV-LIFECYCLE-2 F1/F2).

Every worker and gate command is started with ``spawn()`` and ended with ``finish()``; ``precheck()`` runs before each
worker. ``contained`` is True only when the platform confirms that nothing the worker or command started is still
running. Anything else is ``contained=False`` (fail closed): a real milestone review then does not count.

* Linux (DEV-LIFECYCLE-1 R8-01): the command runs in its own session; afterwards its process group is killed and the
  driver, as child subreaper, kills every adopted orphan (``lifecycle_providers.sweep_orphans``).
* Windows: one Job Object per worker or command, through stdlib ``ctypes`` only. The child is created suspended,
  assigned to the job and only then resumed, so it cannot start a process outside the job. The job has
  ``JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`` and no breakaway flag, so a ``CREATE_BREAKAWAY_FROM_JOB`` request fails. After
  the worker or command the job is terminated and must report ``ActiveProcesses == 0``; the job handle is kept until
  the next ``precheck()`` has confirmed again that it is empty, also when termination or the check failed. A worker or
  command that ran without a job taints the driver: every later ``precheck()`` is ``contained=False`` (R1-01).
* Elsewhere: no containment (``contained=False``).

Not covered on any platform (disclosed, see DEV_LIFECYCLE_2_PLAN_AND_ACCEPTANCE.md): processes started by other routes
(Windows: Task Scheduler, WMI, services, COM out-of-process servers; Linux: systemd-run, cron/at, D-Bus activation,
any already-running daemon acting on a worker's request).
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

WINDOWS = sys.platform == "win32"

# Windows constants (winbase.h / winnt.h)
CREATE_SUSPENDED = 0x00000004
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
JOB_OBJECT_LIMIT_BREAKAWAY_OK = 0x00000800
JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK = 0x00001000
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION = 1
JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
TH32CS_SNAPTHREAD = 0x00000004
THREAD_SUSPEND_RESUME = 0x0002
EMPTY_WAIT_S = 5.0
# The only limit a worker's job gets: everything in it dies with the job; breakaway is NOT allowed (DEV-LIFECYCLE-2).
JOB_LIMIT_FLAGS = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE


class WinJobApi:
    """The few kernel32 calls containment needs. Every failure raises OSError. Tests replace it with a fake."""

    def __init__(self):
        import ctypes
        from ctypes import wintypes as w
        self._c, self._w = ctypes, w
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        H, B, D = w.HANDLE, w.BOOL, w.DWORD

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(n, ctypes.c_ulonglong) for n in ("ReadOperationCount", "WriteOperationCount",
                                                          "OtherOperationCount", "ReadTransferCount",
                                                          "WriteTransferCount", "OtherTransferCount")]

        class BASIC_LIMIT(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                        ("LimitFlags", D), ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", D),
                        ("Affinity", ctypes.c_size_t), ("PriorityClass", D), ("SchedulingClass", D)]

        class EXTENDED_LIMIT(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", BASIC_LIMIT), ("IoInfo", IO_COUNTERS),
                        ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]

        class BASIC_ACCOUNTING(ctypes.Structure):
            _fields_ = [("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
                        ("ThisPeriodTotalUserTime", ctypes.c_int64), ("ThisPeriodTotalKernelTime", ctypes.c_int64),
                        ("TotalPageFaultCount", D), ("TotalProcesses", D), ("ActiveProcesses", D),
                        ("TotalTerminatedProcesses", D)]

        class THREADENTRY32(ctypes.Structure):
            _fields_ = [("dwSize", D), ("cntUsage", D), ("th32ThreadID", D), ("th32OwnerProcessID", D),
                        ("tpBasePri", w.LONG), ("tpDeltaPri", w.LONG), ("dwFlags", D)]

        self.EXTENDED_LIMIT, self.BASIC_ACCOUNTING, self.THREADENTRY32 = EXTENDED_LIMIT, BASIC_ACCOUNTING, THREADENTRY32
        sig = {
            "CreateJobObjectW": (H, [w.LPVOID, w.LPCWSTR]),
            "SetInformationJobObject": (B, [H, ctypes.c_int, w.LPVOID, D]),
            "QueryInformationJobObject": (B, [H, ctypes.c_int, w.LPVOID, D, ctypes.POINTER(D)]),
            "AssignProcessToJobObject": (B, [H, H]),
            "TerminateJobObject": (B, [H, ctypes.c_uint]),
            "CloseHandle": (B, [H]),
            "CreateToolhelp32Snapshot": (H, [D, D]),
            "Thread32First": (B, [H, ctypes.POINTER(THREADENTRY32)]),
            "Thread32Next": (B, [H, ctypes.POINTER(THREADENTRY32)]),
            "OpenThread": (H, [D, B, D]),
            "ResumeThread": (D, [H]),
        }
        for name, (res, args) in sig.items():
            f = getattr(k, name)
            f.restype, f.argtypes = res, args
        self.k = k

    def _fail(self, what):
        raise OSError(self._c.get_last_error(), f"{what} failed")

    def create(self):
        job = self.k.CreateJobObjectW(None, None)
        if not job:
            self._fail("CreateJobObjectW")
        info = self.EXTENDED_LIMIT()
        info.BasicLimitInformation.LimitFlags = JOB_LIMIT_FLAGS   # kill on close, and no breakaway flag
        if not self.k.SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, self._c.byref(info),
                                              self._c.sizeof(info)):
            self.k.CloseHandle(job)
            self._fail("SetInformationJobObject")
        return job

    def limit_flags(self, job) -> int:
        info = self.EXTENDED_LIMIT()
        if not self.k.QueryInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, self._c.byref(info),
                                                self._c.sizeof(info), None):
            self._fail("QueryInformationJobObject(limits)")
        return info.BasicLimitInformation.LimitFlags

    def assign(self, job, process_handle) -> None:
        if not self.k.AssignProcessToJobObject(job, int(process_handle)):
            self._fail("AssignProcessToJobObject")

    def resume(self, pid: int) -> int:
        """Resume every thread of a suspended process; the number of threads resumed."""
        snap = self.k.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
        if not snap or snap == self._w.HANDLE(-1).value:
            self._fail("CreateToolhelp32Snapshot")
        n = 0
        try:
            te = self.THREADENTRY32()
            te.dwSize = self._c.sizeof(te)
            ok = self.k.Thread32First(snap, self._c.byref(te))
            while ok:
                if te.th32OwnerProcessID == pid:
                    th = self.k.OpenThread(THREAD_SUSPEND_RESUME, False, te.th32ThreadID)
                    if not th:
                        self._fail("OpenThread")
                    try:
                        if self.k.ResumeThread(th) == 0xFFFFFFFF:
                            self._fail("ResumeThread")
                        n += 1
                    finally:
                        self.k.CloseHandle(th)
                ok = self.k.Thread32Next(snap, self._c.byref(te))
        finally:
            self.k.CloseHandle(snap)
        if not n:
            raise OSError(0, "no thread of the suspended process was found")
        return n

    def terminate(self, job) -> None:
        if not self.k.TerminateJobObject(job, 1):
            self._fail("TerminateJobObject")

    def active(self, job) -> int:
        info = self.BASIC_ACCOUNTING()
        if not self.k.QueryInformationJobObject(job, JOB_OBJECT_BASIC_ACCOUNTING_INFORMATION, self._c.byref(info),
                                                self._c.sizeof(info), None):
            self._fail("QueryInformationJobObject(accounting)")
        return int(info.ActiveProcesses)

    def close(self, job) -> None:
        self.k.CloseHandle(job)


_API = None
_OPEN_JOBS: list = []   # Windows jobs ended by finish(), kept until precheck() has confirmed them empty again
_TAINTED: list = []     # Windows: why something ran outside any job; nothing it left can be verified (R1-01)


def win_api():
    """The kernel32 wrapper, or None where it cannot be loaded (then nothing is contained)."""
    global _API
    if _API is None and WINDOWS:
        try:
            _API = WinJobApi()
        except (OSError, AttributeError, ImportError):
            _API = False
    return _API or None


def kill_pid_tree(pid: int) -> None:
    """Best effort: end ``pid``'s process group (POSIX) or tree (Windows). Never raises; an exited pid is fine."""
    if hasattr(os, "killpg") and hasattr(signal, "SIGKILL"):
        try:
            os.killpg(pid, signal.SIGKILL)
        except OSError:
            pass
        return
    if WINDOWS:
        try:
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(int(pid))], capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError, ValueError):
            pass


def spawn(argv, **kw) -> subprocess.Popen:
    """Start a worker or command inside containment. On Windows the process is created suspended, assigned to a new
    job and resumed; if the job cannot be created or assigned it still runs, but ``finish()`` reports
    ``contained=False``. A process that cannot be resumed is killed and OSError is raised."""
    if not WINDOWS:
        return subprocess.Popen(argv, start_new_session=True, **kw)
    api = win_api()
    job, why = None, None
    if api is None:
        why = "job objects unavailable"
    else:
        try:
            job = api.create()
        except OSError as e:
            why = f"job not created: {e}"
    kw["creationflags"] = kw.get("creationflags", 0) | CREATE_SUSPENDED | CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(argv, **kw)
    if job is not None:
        try:
            api.assign(job, proc._handle)
        except OSError as e:
            why = f"process not assigned to the job: {e}"
            api.close(job)
            job = None
    try:
        if api is None:
            raise OSError(0, "cannot resume a suspended process without kernel32")
        api.resume(proc.pid)
    except OSError:
        proc.kill()
        if job is not None:
            api.terminate(job)
            api.close(job)
        proc.wait()
        raise
    proc._uri_job, proc._uri_job_error = job, why
    return proc


def kill_tree(proc) -> None:
    """End a running worker or command and everything it started, without waiting (timeouts)."""
    job = getattr(proc, "_uri_job", None)
    if job is not None:
        try:
            win_api().terminate(job)
            return
        except OSError:
            pass
    kill_pid_tree(proc.pid)
    try:
        proc.kill()
    except OSError:
        pass


def _wait_empty(api, job, wait_s: float) -> int:
    deadline = time.monotonic() + wait_s
    while True:
        n = api.active(job)
        if n == 0 or time.monotonic() >= deadline:
            return n
        time.sleep(0.05)


def finish(proc, sweep=None, wait_s: float = EMPTY_WAIT_S) -> dict:
    """After a worker or command ended (or timed out): end everything it started and report whether that is
    confirmed. ``sweep`` is the POSIX orphan sweep (lifecycle_providers.sweep_orphans)."""
    if not WINDOWS:
        kill_pid_tree(proc.pid)
        return sweep() if sweep else {"contained": False, "reason": "no sweep"}
    job = getattr(proc, "_uri_job", None)
    api = win_api()
    if job is None or api is None:
        kill_pid_tree(proc.pid)
        why = getattr(proc, "_uri_job_error", None) or "no job object"
        _TAINTED.append(f"pid {proc.pid} ran outside a job ({why})")
        return {"contained": False, "reason": why}
    _OPEN_JOBS.append(job)      # even when the check below fails: precheck() must verify it again (R1-01)
    proc._uri_job = None
    try:
        api.terminate(job)
        n = _wait_empty(api, job, wait_s)
    except OSError as e:
        kill_pid_tree(proc.pid)
        return {"contained": False, "reason": f"job not verified: {e}"}
    if n:
        return {"contained": False, "reason": f"{n} process(es) still active in the job after termination"}
    return {"contained": True, "killed": "job terminated", "active_processes": 0}


def precheck(sweep=None, wait_s: float = EMPTY_WAIT_S) -> dict:
    """Before a worker starts: nothing from an earlier worker or command may still run. POSIX: the orphan sweep.
    Windows: every earlier job must (still, or after another termination) report ActiveProcesses == 0."""
    if not WINDOWS:
        return sweep() if sweep else {"contained": False, "reason": "no sweep"}
    api = win_api()
    if api is None:
        return {"contained": False, "killed": 0, "reason": "job objects unavailable"}
    if _TAINTED:
        return {"contained": False, "killed": 0, "reason": "earlier process(es) ran outside a job: "
                                                           + "; ".join(_TAINTED)}
    left, killed = [], 0
    for job in list(_OPEN_JOBS):
        try:
            n = api.active(job)
            if n:
                killed += n
                api.terminate(job)
                n = _wait_empty(api, job, wait_s)
        except OSError as e:
            return {"contained": False, "killed": killed, "reason": f"earlier job not verified: {e}"}
        if n:
            left.append(n)
        else:
            api.close(job)
            _OPEN_JOBS.remove(job)
    if left:
        return {"contained": False, "killed": killed, "reason": f"{sum(left)} process(es) from earlier jobs remain"}
    return {"contained": True, "killed": killed}
